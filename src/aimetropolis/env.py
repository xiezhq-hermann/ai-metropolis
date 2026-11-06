import math
import json
import redis
import heapq
from typing import List, Tuple
from collections import deque
from aimetropolis import Event
from aimetropoliscpp import PersonaDependency

# this will be used to convert grid coordinates to geo coordinates
# in Google Map, latitude comes first before longitude
# however, in Redis, the order is reversed
DEFAULT_ORIGIN = (-122.173333, 37.43)
# default grid is 1 meter x 1 meter large
UNIT_LENGTH = 1
NORTH_CALIBRATION = 0.91e-05
EAST_CALIBRATION = 1.14e-05


class Env:

    def __init__(self, db_port=6379, db_host="localhost", base_step=0):
        '''
        This class is the base class for all environments
        Note in a distributed setting, there will be multiple envs which should be consistent with each other
            therefore, we should have a centralized database to store the environment states and only keep constant states in each instance
        '''
        # todo: compatible with other databases?
        # default configuration
        self.db = redis.Redis(host=db_host, port=db_port, db=0, decode_responses=True)
        # keys for geo indexing
        self.persona_geo_key = "geo:persona"

        if not self.db.exists("meta_data"):
            self.init_env_from_files()
            self.db.set("counter:base_step", base_step)
            self.db.set("counter:max_step", base_step)
            self.db.set("counter:cluster_action_counter", 0)

        meta_data = json.loads(self.db.get("meta_data"))
        self.x_dim = meta_data["x_dim"]
        self.y_dim = meta_data["y_dim"]
        self.sec_per_step = meta_data["sec_per_step"]
        self.persona_names = meta_data["persona_names"]
        self.agent_vision_radius = meta_data["agent_vision_radius"]
        self.agent_influence_radius = 1
        assert self.x_dim > 0 and self.y_dim > 0 and self.agent_vision_radius > 0, "Invalid meta data"
        assert len(self.persona_names) > 0, "No persona names found"

        self.persona_dependency = PersonaDependency(self.persona_names, self.agent_vision_radius, db_host, db_port, 0)

    @property
    def base_step(self) -> int:
        return int(self.db.get("counter:base_step"))

    @property
    def max_step(self) -> int:
        return int(self.db.get("counter:max_step"))

    def update_base_step(self):
        # use pipeline to accelerate I/O
        with self.db.pipeline() as pipe:
            keys = [f"persona:{persona}" for persona in self.persona_names]
            for key in keys:
                pipe.hget(key, "step")
            steps = pipe.execute()
        min_step = min([int(step) for step in steps])
        diff = min_step - self.base_step
        if diff < 0:
            raise ValueError(f"Invalid step {min_step} while current base step is {self.base_step}")
        elif diff > 0:
            self.db.set("counter:base_step", min_step)
            return diff
        else:
            return 0

    def update_max_step(self, step: int):
        if step > self.max_step:
            self.db.set("counter:max_step", step)

    def init_env_from_files(self):
        # to be implemented in derived classes
        # refer the documentation for the expected database schema
        raise NotImplementedError

    def translate_grid_to_geo(self, x: int, y: int) -> Tuple[float, float]:
        return (
            DEFAULT_ORIGIN[0] + x * EAST_CALIBRATION,
            DEFAULT_ORIGIN[1] + y * NORTH_CALIBRATION,
        )

    def translate_geo_to_grid(self, lon: float, lat: float) -> Tuple[int, int]:
        return (
            (lon - DEFAULT_ORIGIN[0]) / EAST_CALIBRATION,
            (lat - DEFAULT_ORIGIN[1]) / NORTH_CALIBRATION,
        )

    def common_insert_check(self, key: str, attributes: dict):
        if self.db.exists(key):
            raise ValueError(f"Key {key} already exists.")
        if not isinstance(attributes, dict):
            raise TypeError("Attributes must be a dictionary.")

    def add_static_tile(self, x: int, y: int, passable: int = 1, attributes: dict = {}):
        # for generative agents, location attributes like arena, sector, etc. can be added into the attributes
        key = f"grid:{x}:{y}"
        self.common_insert_check(key, attributes)
        self.db.hset(key, mapping={"passable": passable, **attributes})

    def find_closest_to_center(self,coords: List[Tuple[int, int]]) -> Tuple[int, int]:
        if not coords:
            raise ValueError("The list of coordinates is empty")
        
        # Step 1: Calculate the centroid
        x_sum = sum(x for x, y in coords)
        y_sum = sum(y for x, y in coords)
        n = len(coords)
        centroid = (x_sum / n, y_sum / n)
        
        # Step 2: Calculate the distance from each point to the centroid
        def distance(coord1: Tuple[int, int], coord2: Tuple[float, float]) -> float:
            return math.sqrt((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2)
        
        # Step 3: Find the coordinate with the minimum distance to the centroid
        closest_coord = min(coords, key=lambda coord: distance(coord, centroid))
  
        return closest_coord
    def add_object(self, object_name: str, point_set: List[Tuple[int, int]], movable: int = 0, attributes: dict = {}):
        key = f"object:{object_name}"

        self.common_insert_check(key, attributes)
        center_point = self.find_closest_to_center(point_set)

        self.db.hset(key, mapping={"status": "idle", "movable": movable,"center":str(list(center_point)), **attributes})
        # since Redis does not support polygon data type, we use a set of points to represent the object

        assert not movable, "Movable objects are not supported yet."
        for x, y in point_set:
            grid_key = f"grid:{x}:{y}"
            self.db.hset(grid_key, mapping={
                "object": object_name,
                "passable": 1,
            })
    def get_object(self,object_name: str):
        return self.db.hgetall(f"object:{object_name}")
    def add_persona(self, persona_name: str, x: int, y: int, attributes: dict = {}, base_step: int = 0):
        key = f"persona:{persona_name}"
        self.common_insert_check(key, attributes)
        self.db.hset(key, mapping={"x": x, "y": y, "step": base_step, "status": "idle", "action": "", **attributes})
        self.db.set(f"persona:{persona_name}:init_info", json.dumps({"x": x, "y": y}))

        # change to grid coordinates as the accuracy of Redis geo indexing is not sufficient
        grid_key = f"grid:{x}:{y}"
        personas = self.db.hget(grid_key, "personas")
        self.db.hset(grid_key, mapping={"personas": f"{personas}:{persona_name}" if personas else persona_name})

    def get_location_info(self, x, y) -> str:
        # to be defined in derived classes
        # return the location string of the given grid coordinates
        raise NotImplementedError

    def perceive_object_events(self, persona_name: str) -> List[Event]:
        center_x = int(self.db.hget(f"persona:{persona_name}", "x"))
        center_y = int(self.db.hget(f"persona:{persona_name}", "y"))
        objects = {}
        for x in range(center_x - self.agent_vision_radius, center_x + self.agent_vision_radius):
            for y in range(center_y - self.agent_vision_radius, center_y + self.agent_vision_radius):
                obj = self.db.hget(f"grid:{x}:{y}", "object")
                if obj and obj not in objects:
                    objects[obj] = (x, y)
        events = []
        for obj, (x, y) in objects.items():
            status = self.db.hget(f"object:{obj}", "status")
            location = self.get_location_info(x, y)
            events.append(Event(obj, "is", status, location, None))
        return events

    def geo_query_personas(self,
                           persona_name: str,
                           vision_radius: int = None,
                           withdist: bool = False,
                           closed_interval: bool = True) -> Tuple[float, float]:
        # to return all surrounding agents, optionally with the distance
        if not vision_radius:
            vision_radius = self.agent_vision_radius
        center_x, center_y = self.get_persona_position(persona_name)
        keys = []
        for x in range(center_x - vision_radius, center_x + vision_radius + 1):
            for y in range(center_y - vision_radius, center_y + vision_radius + 1):
                keys.append(f"grid:{x}:{y}")

        pipeline = self.db.pipeline()
        for key in keys:
            pipeline.hget(key, "personas")
        results = pipeline.execute()

        personas = []
        for key, result in zip(keys, results):
            if result and result != persona_name:
                x, y = key.split(":")[1:]
                dist = math.sqrt((int(x) - center_x)**2 + (int(y) - center_y)**2)
                if dist < vision_radius or (closed_interval and dist == vision_radius):
                    for p in result.split(":"):
                        if p == persona_name:
                            continue
                        if withdist:
                            personas.append((p, dist))
                        else:
                            personas.append(p)
        return personas

    def perceive_persona_events(self, persona_name: str) -> List[Event]:
        events = []
        nearby_personas = self.geo_query_personas(persona_name)
        for persona in nearby_personas:
            states = self.db.hgetall(f"persona:{persona}")
            location = self.get_location_info(states["x"], states["y"])
            events.append(Event(persona, "is", states["action"], location, None))
        return events

    def perceive_events(self, persona_name: str, blockview=False) -> List[Event]:
        return self.perceive_object_events(persona_name) + self.perceive_persona_events(persona_name)

    def tile_passable(self, x: int, y: int) -> bool:
        passable = self.db.hget(f"grid:{x}:{y}", "passable")
        return bool(int(passable)) if passable else False

    def path_finding(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        # A* algorithm using local cached static grid
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        open_list = []
        heapq.heappush(open_list, (heuristic(start, goal), 0, start))
        came_from = {}
        g_score = {start: 0}

        while open_list:
            _, current_g, current = heapq.heappop(open_list)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                next = (current[0] + dx, current[1] + dy)
                if not self.db.hget(f"grid:{next[0]}:{next[1]}", "passable") or not int(self.db.hget(f"grid:{next[0]}:{next[1]}", "passable")):
                    # if the grid is not exist or not passable, skip
                    continue
                tentative_g = current_g + 1
                
                if next not in g_score or tentative_g < g_score[next]:
                    came_from[next] = current
                    g_score[next] = tentative_g
                    heapq.heappush(
                        open_list,
                        (tentative_g + heuristic(next, goal), tentative_g, next),
                    )

    def path_finding_v2(self, start: Tuple[int, int], end: Tuple[int, int]):
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        def is_valid_move(x, y):

            if not self.db.hget(f"grid:{x}:{y}", "passable") or not int(self.db.hget(f"grid:{x}:{y}", "passable")):
                return False
            return True
        
        # four possible movement
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        
        queue = deque([(start, [start])])
        visited = set()
        visited.add(start)
        
        while queue:
            current, path = queue.popleft()
            
            if heuristic(current,end) <= 1:
                return path
            
            x, y = current
            
            for dx, dy in directions:
                next_x, next_y = x + dx, y + dy
                next_point = (next_x, next_y)
                
                if next_point not in visited and is_valid_move(next_x, next_y):
                    visited.add(next_point)
                    queue.append((next_point, path + [next_point]))
        
        return []
        
    def get_persona_position(self, persona_name: str) -> Tuple[int, int]:
        return (int(self.db.hget(f"persona:{persona_name}", "x")), int(self.db.hget(f"persona:{persona_name}", "y")))

    def can_proceed_dependency(self, persona_name: str) -> bool:
        # check whether the persona can proceed based on the dependency graph
        # return len(self.persona_dependency[persona_name]["blocked"]) == 0
        return self.persona_dependency.can_proceed(persona_name)

    def geo_clustering(self, available_agents: List[str], task_queue, speculation=True) -> List[Tuple[int, List[str]]]:
        # get clusters of agents that are close to each other
        visited = set()
        clusters = []

        for agent in available_agents:
            if agent in visited or not self.can_proceed_dependency(agent):
                # starting clustering from an available agent
                continue

            cluster = []
            queue = [agent]
            cluster_proceed_indicator = True
            cluster_step = int(self.db.hget(f"persona:{agent}", "step"))
            # exhaustive search for any other agents in the same cluster
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                cluster.append(current)

                if cluster_proceed_indicator and not self.can_proceed_dependency(current):
                    # no need to check when the cluster is already blocked
                    cluster_proceed_indicator = False

                # +1 to avoid deadlock of agents in the same step but with a distance between (radius, radius + 1]
                coupled_agents = self.geo_query_personas(current,
                                                         vision_radius=self.agent_vision_radius +
                                                         self.agent_influence_radius,
                                                         withdist=True)
                for persona, dist in coupled_agents:
                    # note, there is a potential concurrency issue where the step does match with the retrieved distance
                    persona_step = int(self.db.hget(f"persona:{persona}", "step"))

                    persona_available = bool(persona in available_agents)
                    # check whether target persona is available or not, from the database status instead of the input due to concurrency
                    # the couple agents can either be in the same step, or will be in the same step after current task

                    if not persona_available:
                        # due to concurrency, the coupled agent might already be available but the dependency graph not updated yet
                        # we will wait for the next iteration to check the dependency
                        cluster_proceed_indicator = False
                        continue

                    if dist <= self.agent_vision_radius:
                        # agents within the vision radius must be at the same step
                        assert cluster_step == persona_step, f"{current} ({cluster_step}) and {persona} ({persona_step}) with distance {dist} are not in the same step."
                        queue.append(persona)
                    else:
                        # agents in (radius, radius+1] at the same step is in the same cluster
                        # as one's influence space can overlap with the other's observation space
                        if cluster_step == persona_step:
                            queue.append(persona)
                        else:
                            # not the same cluster, leave check to the dependency graph
                            assert abs(
                                cluster_step - persona_step
                            ) == 1, f"conflicit detected between {current} ({cluster_step}) and {persona} ({persona_step}) with distance {dist}."
                            continue

            if speculation and not cluster_proceed_indicator:
                # this cluster is blocked by other agents
                continue
            clusters.append((cluster_step, cluster))
            # put the cluster into the task queue right away
            task_queue.put((cluster_step, cluster))

        return clusters

    def can_proceed_simplified(self, persona_name: str) -> bool:
        persona_step = int(self.db.hget(f"persona:{persona_name}", "step"))
        coupled_agents = self.geo_query_personas(persona_name,
                                                 vision_radius=self.agent_vision_radius + persona_step -
                                                 self.base_step + 1,
                                                 withdist=True)

        for p, dist in coupled_agents:
            coupled_step = int(self.db.hget(f"persona:{p}", "step"))
            if dist <= self.agent_vision_radius:
                assert persona_step == coupled_step, f"{persona_name} ({persona_step}) and {p} ({coupled_step}) with distance {dist} are not in the same step."
            elif dist <= persona_step - coupled_step + self.agent_vision_radius + 1:
                if persona_step > coupled_step:
                    return False
            else:
                # the two agents are far away from each other enough
                pass

        return True

    def can_proceed_cluster(self, cluster: List[str], curr_step) -> bool:
        for persona in cluster:
            if not self.can_proceed(persona, curr_step, cluster):
                return False
        return True

    def can_proceed(self, persona_name, curr_step, cluster, blockview=False) -> bool:
        coupled_agents = self.geo_query_personas(persona_name,
                                                 vision_radius=self.agent_vision_radius + curr_step - self.base_step +
                                                 2,
                                                 withdist=True)
        # todo: the dist from geo_query_personas is not accurate
        for persona, dist in coupled_agents:
            coupled_step = int(self.db.hget(f"persona:{persona}", "step"))
            if curr_step <= coupled_step:
                # agent only get block by agents behind
                if curr_step < coupled_step:
                    # make sure future agents are not perceived
                    assert dist > self.agent_vision_radius, f"{persona_name} see {persona} from the future."
                else:
                    # if coupled agents are in the same step, both of them can proceed if they are in the same cluster
                    # otherwise, they can proceed only if dist > self.agent_vision_radius + 1
                    if persona not in cluster:
                        assert dist > self.agent_vision_radius + 1, f"{persona_name} and {persona} ({dist} away) might end up in a deadlock"
                continue

            if dist <= self.agent_vision_radius:
                # agent from newly merged cluster which is not completed yet
                assert curr_step == coupled_step + 1
                return False
            else:
                if dist < curr_step - 1 - coupled_step + self.agent_vision_radius:
                    # todo, resolve the accuracy issue of geo_query_personas
                    print(
                        f"Distance between {persona_name} and {persona} is {dist}. while the expected distance is {curr_step - 1 - coupled_step + self.agent_vision_radius}"
                    )
                    print("Warning: conflict detected.")
                    # raise ValueError(f"Conflicit detected between {persona_name} and {persona}.")
                elif dist < curr_step - coupled_step + self.agent_vision_radius + 2:
                    return False
                else:
                    pass
        return True

    def detect_conflicit_and_roll_back(self):
        # todo: instead of rigidly proceeding prevention, we can also employ a rollback mechanism
        pass
