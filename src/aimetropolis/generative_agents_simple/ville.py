import os
import csv
import json
from tqdm import tqdm

from aimetropolis import Env
from aimetropolis.utils import replay_path

# Get the directory of the current file
ASSEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets/")


class TheVille(Env):

    def __init__(self,
                 base_step: int = 0,
                 num_agents=25,
                 replay=True,
                 cache=False,
                 recorded_movement=None,
                 recorded_traces=None):
        self._base_step = base_step
        self.duplication = num_agents // 25
        self.replay = replay
        self.cache = cache
        self.recorded_movement = recorded_movement
        self.recorded_traces = recorded_traces
        super().__init__(base_step=base_step)

    def init_static_world(self, meta_data, ville_info):
        maze = [[{
            "world": "the Ville",
            "sector": "",
            "arena": "",
            "passable": 1,
        } for _ in range(meta_data["y_dim"])] for _ in range(meta_data["x_dim"])]

        sector_mapping = {}
        arena_mapping = {}
        object_mapping = {}
        with open(ASSEST_PATH + "maze/sector_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                sector_mapping[int(row[0])] = row[2]

        with open(ASSEST_PATH + "maze/arena_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                arena_mapping[int(row[0])] = row[3]

        with open(ASSEST_PATH + "maze/game_object_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                object_mapping[int(row[0])] = row[3]

        objects_points = {object_name: [] for object_name in object_mapping.values()}
        with open(ASSEST_PATH + "maze/sector_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, sector_id in enumerate(raw_maze):
                x = i // ville_info['maze_height']
                y = i % ville_info['maze_height']
                if sector_id == 0:
                    continue
                for i in range(self.duplication):
                    maze[x][y + i * ville_info['maze_height']]["sector"] = sector_mapping[sector_id]

        with open(ASSEST_PATH + "maze/arena_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, arena_id in enumerate(raw_maze):
                x = i // ville_info['maze_height']
                y = i % ville_info['maze_height']
                if arena_id == 0:
                    continue
                for i in range(self.duplication):
                    maze[x][y + i * ville_info['maze_height']]["sector"] = arena_mapping[arena_id]

        with open(ASSEST_PATH + "maze/arena_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, arena_id in enumerate(raw_maze):
                x = i // ville_info['maze_height']
                y = i % ville_info['maze_height']
                if arena_id == 0:
                    continue
                for i in range(self.duplication):
                    maze[x][y + i * ville_info['maze_height']]["passable"] = 0

        with open(ASSEST_PATH + "maze/game_object_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, object_id in enumerate(raw_maze):
                x = i // ville_info['maze_height']
                y = i % ville_info['maze_height']
                if object_id == 0:
                    continue
                for i in range(self.duplication):
                    objects_points[object_mapping[object_id]].append((x, y + i * ville_info['maze_height']))

        print("loading static tiles...")
        for x in tqdm(range(meta_data["x_dim"])):
            for y in range(meta_data["y_dim"]):
                self.add_static_tile(x, y, attributes=maze[x][y])

        for obj in objects_points:
            self.add_object(obj, objects_points[obj])

    def init_records(self, ville_info):
        if self.recorded_movement is None:
            # default to the full day replayed in the SmallVille benchmark
            self.recorded_movement = json.load(open(replay_path("full_day", "movement.json")))
            self.recorded_traces = json.load(open(replay_path("full_day", "trace.json")))

        if self.cache:
            return self.recorded_movement

        print("loading recorded movements and function calls ...")
        for persona, movement in tqdm(self.recorded_movement.items()):
            pipeline = self.db.pipeline()
            # for i in range(self.duplication):
            for step, (x, y) in enumerate(movement):
                pipeline.hset(f"recorded_movement:{persona}:{step}", "x", x)
                pipeline.hset(f"recorded_movement:{persona}:{step}", "y", y)
            pipeline.execute()
        for step, personas in tqdm(self.recorded_traces.items()):
            pipeline = self.db.pipeline()
            # for step, personas in traces.items():
            for persona, funcs in personas.items():
                # for i in range(self.duplication):
                pipeline.set(f"recorded_calls:{persona}:{step}", json.dumps(funcs))
                # pipeline.set(f"recorded_calls:{persona}_{i}:{int(step)+i}", json.dumps(funcs))
            pipeline.execute()

        return self.recorded_movement

    def init_env_from_files(self):
        # read csv files containing tile information
        meta_data = {"persona_names": [], "agent_vision_radius": 4, "sec_per_step": 10}
        with open(ASSEST_PATH + "maze_meta_info.json") as f:
            ville_info = json.load(f)
            meta_data["name"] = 'the_ville'
            meta_data["x_dim"] = ville_info['maze_width']
            meta_data["y_dim"] = ville_info['maze_height'] * self.duplication

        if not self.cache:
            self.init_static_world(meta_data, ville_info)

        if self.replay:
            movements = self.init_records(ville_info)
        personas = json.load(open(ASSEST_PATH + "personas/n25.json"))
        for p, v in personas.items():
            for i in range(self.duplication):
                persona = f"{p}_{i}" if i != 0 else p
                if self._base_step > 0:
                    assert self.replay
                    assert self._base_step < len(movements[p])
                    self.add_persona(persona,
                                     movements[persona][self._base_step][0],
                                     movements[persona][self._base_step][1],
                                     base_step=self._base_step)
                else:
                    self.add_persona(persona, v["x"], v["y"])
                meta_data["persona_names"].append(persona)

        self.db.set("meta_data", json.dumps(meta_data))
        return

    def get_location_info(self, x, y) -> str:
        key = f"grid:{x}:{y}"
        grid_info = [self.db.hget(key, k) for k in ["world", "sector", "arena"]]
        return ":".join([i for i in grid_info if i])


if __name__ == "__main__":
    ville = TheVille()
    print(ville.get_location_info(1, 2))
    print(ville.get_location_info(50, 90))
    ville = TheVille(num_agents=500)
    print(ville.get_location_info(1, 2))
    print(ville.get_location_info(50, 90))
    print(ville.get_location_info(99, 99))
    print(ville.get_location_info(99, 199))
