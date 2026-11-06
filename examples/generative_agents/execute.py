import random
from aimetropolis.action import AgentChat,AgentMove,ChangeObjectStatus
import json
import ast
def generative_execute(persona,env,plan):
    def distance(x1,y1,x2,y2):
        return abs(x1-x2) + abs(y1-y2)
    #### TODO need to keep different persona have different path
    if "<random>" in plan and persona.meta_info["planned_path"] == []: 
        persona.meta_info["act_path_set"] = False
    if not persona.meta_info["act_path_set"]: 
        
        if "<persona>" in plan: 
            ### persona persona interaction
            target_p = plan.split("<persona>")[-1].strip()
            target_states = env.db.hgetall(f"persona:{target_p}")
            start_states = env.db.hgetall(f"persona:{persona.name}")
            target_tile = (int(target_states["x"]), int(target_states["y"]))
            start_tile = (int(start_states["x"]), int(start_states["y"]))
            potential_path = env.path_finding_v2(start_tile, target_tile)
            if len(potential_path) <= 2:
                ### arive at target
                next_tile = potential_path[0]
                potential_path = []
            else:
                next_tile = potential_path[0]
        elif "<waiting>" in plan: 
            x = int(plan.split()[1])
            y = int(plan.split()[2])
            next_tile = (x,y)
        elif "<random>" in plan: 
            possible_set = [(0,1),(1,0),(0,-1),(-1,0)]
            next_tile = random.choice(possible_set)
            curr_tile = env.db.hgetall(f"persona:{persona.name}")
            start_tile_set = (int(curr_tile["x"] + next_tile[0]), int(curr_tile["y"] + next_tile[1]))
            ### TODO
        else:
            #### general execution
            world = plan.split(":")[0]
            sector = plan.split(":")[1]
            arena = plan.split(":")[2]
            game_objects = plan.split(":")[3]
            start_states = env.db.hgetall(f"persona:{persona.name}")
            start_tile = (int(start_states["x"]), int(start_states["y"]))
            if env.check_legal_obj(world,sector,arena,game_objects,"the Ville"):
                plan_without_world = ":".join(plan.split(":")[1:])
                obj_info = env.get_object(plan_without_world)
                obj_tile = obj_info["center"]

                obj_tile = list(ast.literal_eval(obj_tile))
                target_tile = (int(obj_tile[0]),int(obj_tile[1]))
            else:
                print(env.sector_arena_tree)
                print("illegal plan",plan)
                raise ValueError("Illegal object")
            #### Warning maybe multiple target??
            print("start_tile: ",start_tile,"target_tile: ",target_tile)
            potential_path = env.path_finding_v2(start_tile, target_tile)
            if len(potential_path) == 1:
                ### arive at target
                next_tile = potential_path[0]
                potential_path = []
            elif len(potential_path) != 0:
                next_tile = potential_path[0]
            else:
                next_tile = start_tile
        if potential_path:
            persona.meta_info["planned_path"] = potential_path[1:]
        else:
            persona.meta_info["planned_path"] = []
        persona.meta_info["act_path_set"] = True
    else:
        if len(persona.meta_info["planned_path"]) >= 2:
            next_tile = persona.meta_info["planned_path"][0]
            persona.meta_info["planned_path"] = persona.meta_info["planned_path"][1:]
        elif len(persona.meta_info["planned_path"]) == 1:
            next_tile = persona.meta_info["planned_path"][0]
            persona.meta_info["planned_path"] = []
        elif len(persona.meta_info["planned_path"]) == 0:
            curr_info = env.db.hgetall(f"persona:{persona.name}")
            curr_tile = (int(curr_info["x"]), int(curr_info["y"]))
            next_tile = curr_tile
            persona.meta_info["planned_path"] = []
    if len(persona.meta_info["planned_path"]) != 0:
        last_access = persona.meta_info["planned_path"][-1]
    else:
        last_access = next_tile
    print("persona_name: ",persona.name,"next_tile: ",next_tile, "target_tile: ",last_access)
    #### chat
    if persona.meta_info["chatting_with"] is not None:
        init_tile = env.db.hgetall(f"persona:{persona.name}")
        target_tile = env.db.hgetall(f"persona:{persona.meta_info['chatting_with']}")
        init_tile = (int(init_tile["x"]), int(init_tile["y"]))
        target_tile = (int(target_tile["x"]), int(target_tile["y"]))
        if distance(init_tile[0],init_tile[1],target_tile[0],target_tile[1]) <= 2:
            agent_chat = AgentChat(persona.step + 1,persona.name,persona.meta_info["chatting_with"])
            return agent_chat
    #### obj interaction
    elif "<waiting>" not in plan:
        if persona.meta_info["planned_path"] == []:
            persona.meta_info["obj_set"] = False
            obj_str = persona.meta_info["act_address"]
            obj_name = obj_str.split(":")[-1]
            agent_interact = ChangeObjectStatus(persona.step + 1, persona.name, obj_str,"used")
            return agent_interact
        if persona.meta_info["obj_set"] is False:
            #### set back obj state, TODO return two actions
            obj_str = persona.meta_info["previous_plan"]
            if len(obj_str.split(":")) >= 4:
                world = obj_str.split(":")[0]
                sector = obj_str.split(":")[1]
                arena = obj_str.split(":")[2]
                game_objects = obj_str.split(":")[3]
                if env.check_legal_obj(world,sector,arena,game_objects,"the Ville"):
                    agent_interact = ChangeObjectStatus(persona.step + 1, persona.name, obj_str,"idle")
            persona.meta_info["obj_set"] = True
            
            return agent_interact
            
    agent_move = AgentMove(persona.step + 1,persona.name, next_tile)
    
    return agent_move
    # next_tile and persona.meta_info["planned_path"] is set
    
        
            
            
            
        