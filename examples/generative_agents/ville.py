import csv
import json

from aimetropolis import Env

# todo, remove hard coded replay
REPLAY = True


class TheVille(Env):

    def __init__(self, base_step: int = 0):
        self._base_step = base_step
        super().__init__(base_step=base_step)

    def init_env_from_files(self):
        # read csv files containing tile information
        meta_data = {"persona_names": [], "agent_vision_radius": 4, "sec_per_step": 10}
        with open("assets/maze_meta_info.json") as f:
            ville_info = json.load(f)
            meta_data["name"] = 'the_ville'
            meta_data["x_dim"] = ville_info['maze_width']
            meta_data["y_dim"] = ville_info['maze_height']

        maze = [[{
            "world": "the Ville",
            "sector": "",
            "arena": "",
            "passable": 1,
        } for _ in range(meta_data["y_dim"])] for _ in range(meta_data["x_dim"])]

        sector_mapping = {}
        arena_mapping = {}
        object_mapping = {}
        self.sector_arena_tree = {}
        with open("assets/maze/sector_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                sector_mapping[int(row[0])] = row[2]
                self.sector_arena_tree[row[2]] = {}
        with open("assets/maze/arena_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                arena_mapping[int(row[0])] = row[3]
                self.sector_arena_tree[row[2]][row[3]] = []
        with open("assets/maze/game_object_blocks.csv") as f:
            for row in f.readlines():
                row = row.rstrip().split(", ")
                object_mapping[int(row[0])] = row[3]

        # objects_points = {object_name: [] for object_name in object_mapping.values()}
        #### new added


        with open("assets/maze/sector_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, sector_id in enumerate(raw_maze):
                x = i // meta_data["y_dim"]
                y = i % meta_data["y_dim"]
                if sector_id == 0:
                    continue
                maze[x][y]["sector"] = sector_mapping[sector_id]

        with open("assets/maze/arena_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, arena_id in enumerate(raw_maze):
                x = i // meta_data["y_dim"]
                y = i % meta_data["y_dim"]
                if arena_id == 0:
                    continue
                maze[x][y]["arena"] = arena_mapping[arena_id]

        with open("assets/maze/arena_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, arena_id in enumerate(raw_maze):
                x = i // meta_data["y_dim"]
                y = i % meta_data["y_dim"]
                if arena_id == 0:
                    continue
                maze[x][y]["passable"] = 0
        objects_points = {}
        with open("assets/maze/game_object_maze.csv") as f:
            raw_maze = [int(i) for i in list(csv.reader(f))[0]]
            for i, object_id in enumerate(raw_maze):
                x = i // meta_data["y_dim"]
                y = i % meta_data["y_dim"]
                if object_id == 0:
                    continue
                ### Warning
                arena = maze[x][y]["arena"]
                sector = maze[x][y]["sector"]
                object_id_full = f"{sector}:{arena}:{object_mapping[object_id]}"
                if object_id_full not in objects_points:
                    objects_points[object_id_full] = []
                objects_points[object_id_full].append((x, y))
                
                if object_mapping[object_id] not in self.sector_arena_tree[sector][arena]:
                    self.sector_arena_tree[sector][arena].append(object_mapping[object_id])


              

        for x in range(meta_data["x_dim"]):
            for y in range(meta_data["y_dim"]):
                self.add_static_tile(x, y, attributes=maze[x][y])

        for obj in objects_points:

            self.add_object(obj, objects_points[obj])

        if REPLAY:
            with open("assets/personas/movement_5000steps.json") as f:
                movements = json.load(f)
                for persona, movement in movements.items():
                    for step, (x, y) in enumerate(movement):
                        self.db.hset(f"recorded_movement:{persona}:{step}", "x", x)
                        self.db.hset(f"recorded_movement:{persona}:{step}", "y", y)

            with open("assets/traces_25agents_8am_10am.json") as f:
                traces = json.load(f)
                for step, personas in traces.items():
                    for persona, funcs in personas.items():
                        self.db.set(f"recorded_calls:{persona}:{step}", json.dumps(funcs))

        with open("assets/personas/n25.json") as f:
            personas = json.load(f)
            for p, v in personas.items():
                if self._base_step > 0:
                    assert self._base_step < len(movements[p])
                    self.add_persona(p,
                                     movements[p][self._base_step][0],
                                     movements[p][self._base_step][1],
                                     base_step=self._base_step)
                else:
                    self.add_persona(p, v["x"], v["y"])
                meta_data["persona_names"].append(p)

        self.db.set("meta_data", json.dumps(meta_data))
        return

    def get_location_info(self, x, y) -> str:
        key = f"grid:{x}:{y}"
        grid_info = [self.db.hget(key, k) for k in ["world", "sector", "arena"]]
        
        return ":".join([i for i in grid_info if i])
    def check_legal_obj(self,world,sector,arena,game_objects,match_world):
        if world == match_world:
            if sector in self.sector_arena_tree:
                if arena in self.sector_arena_tree[sector]:
                    if game_objects in self.sector_arena_tree[sector][arena]:
                        return True
        return False

if __name__ == "__main__":
    ville = TheVille()
    print(ville.get_location_info(1, 2))
    print(ville.get_location_info(50, 90))
    print(ville.get_location_info(99, 99))
