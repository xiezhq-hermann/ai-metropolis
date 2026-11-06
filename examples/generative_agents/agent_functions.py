from aimetropolis.backends import OpenAIBackend, SGLangBackend
import openai
from openai import OpenAI
import os
import json
import re
import datetime
import math
from retrieve import new_retrieve
# def common_llm_call(persona_name, step, prompt, max_tokens, stop):

#     return SGLangBackend.generate(prompt,
#                                    max_tokens=max_tokens,
#                                    step=step,
#                                    stop=stop,)

sector_warning = '''
* Stay in the current area if the activity can be done there. Only go out if the activity needs to take place in another place.
* Must be one of the "Area options," verbatim.
'''

arena_warning = """
* Stay in the current area if the activity can be done there. 
* NEVER go into other people's rooms unless necessary.
"""

def get_embedding(text, model="text-embedding-ada-002"):
    text = text.replace("\n", " ")
    if not text:
        text = "this is blank"
    return openai.embeddings.create(input=[text], model=model).data[0].embedding
def generate_event_poig_score(persona_name, persona_iss, event, step):
    # return prompt and max_tokens
    s = ""
    s += "Here is a brief description of " + persona_name + ".\n"
    s += persona_iss + "\n"
    s += "On the scale of 1 to 10, where 1 is purely mundane (e.g., brushing teeth, making bed) and 10 is extremely poignant (e.g., a break up, college acceptance), rate the likely poignancy of the following event for"
    s += persona_name + ".\n\n"

    s += "Event: " + event
    s += "Rate (only return a number between 1 to 10):"
    regex_constraint = r"^[1-9]|10$"
    return common_llm_call(persona_name, step, s, 2, None, regex_constraint)[0]
    

def generate_chat_poig_score(persona_name,  persona_iss, event, step):
    # return prompt and max_tokens
    s = ""
    s += "Here is a brief description of " + persona_name + ".\n"
    s += persona_iss + "\n"
    s += "On the scale of 1 to 10, where 1 is purely mundane (e.g., routine morning greetings) and 10 is extremely poignant (e.g., a conversation about breaking up, a fight), rate the likely poignancy of the following conversation for"
    s += persona_name + ".\n\n"
    s += "Event: " + event
    s += "Rate (return a number between 1 to 10):"
    regex_constraint = r"^[1-9]|10$"
    return common_llm_call(persona_name, step, s, 2, None, regex_constraint)[0]


def generate_wake_up_hour(persona, step, debug):
    ### 
    s = ""
    s += "Here is a brief description of " + persona.name + ".\n"
    s += persona.get_str_iss() + "\n"
    
    s += "What time does " + persona.name + " usually wake up in the morning?"
    s += "answer with the format of hour and just return an integer within 0 and 12 (e.g., 7)"
    regex_constraint = r"^[1-9]|10|11|12$"
    result = common_llm_call(persona.name, step, s, 2, None, regex_constraint)

    if len(result) > 0:
        if len(result) > 1:
            return int(result[0:2])
        else:
            return int(result[0])
    else:
        return 8
    

def generate_first_daily_plan(persona, wakeup_hour, step):
    daily_plan = persona.meta_info["daily_plan_req"]
    s = ""
    s += "Here is a brief description of " + persona.name + ".\n"
    s += persona.get_str_iss() + "\n"
    # s += f"wake up hour {str(wakeup_hour)}:00 am" + "\n"
    # s += "Generate a daily plan for " + persona.name + " starting from the time " + str(wakeup_hour) + ":00 am in broad-strokes (with the time of the day. e.g., "
    # s += eg + ")." + "\n"
    # s += "Please genearte according to the example without anyting else and separate each activity with a comma. Also must contain a time to go to bed before 12:00 pm."
    s += f"In general, {daily_plan}"+ "\n"
    s += f"Today is {str(persona.get_full_curr_time())}. Here is {persona.name}'s daily plan today in broad-strokes (with the time of the day. e.g., have a lunch at 12:00 pm, watch TV from 7 to 8 pm): 1) wake up and complete the morning routine at 6:00 am,"
    first_plan = f"wake up and complete the morning routine at {str(wakeup_hour)}:00 am"
    ### split the prompt
    response = common_llm_call(persona.name, step, s, 500, None)[0]
    # response = OpenAIBackend.generate(s, max_tokens=500, trace_id=f"{persona.name}:{step}")
    reponse_list = re.findall(r'\d\) ([^,]+)', response)
    reponse_list.insert(0, first_plan)
    return reponse_list
# def single_request(prompt):
    
def Single_request(persona,prompt):
    return common_llm_call(persona.name, persona.step, prompt, 500, None)

    
def run_gpt_prompt_generate_hourly_schedule(persona, 
                                            curr_hour_str,
                                            previous_plan, 
                                            step):
    ### Here
    s = f"Generate the hourly schedule of {persona.name}.\n"
    s += "Here is the brief introduction of " + persona.name + ".\n"
    s += persona.get_str_iss() + "\n"
    # s += "Now the time is " + curr_hour_str + ".\n !Very Important!:Generate plan according to the time, if it is time for breakfast/lunch/dinner and it does include in previous plan, be sure to add them if at appropriate time,. If time is late generate going to bed and then when next time asked generate sleeping till the end of the day. Also, try to avoid generating single plan for over 2 hours and doing one thing many hours\n"
    # s += "And previous plan start from 0:00 AM today is (the form is [plan, duration hours])\n"
    # s += str(previous_plan) + ".\n"
    # s += "Just return one action(no need for \" or \') and its duration in hours(must be integer) of the day with [] without anything else. (e.g. [waking up and starting her morning routine, 1], [working on her painting, 3])"
    ### generate previou plan
    
    for hour,plan in enumerate(previous_plan):
        if hour <= 12:
            s += "At " + str(hour) + ":00 AM, " + persona.name + " is " + plan[0] + ".\n"
        else:
            s += "At " + str(hour) + ":00 PM, " + persona.name + " is " + plan[0] + ".\n"
    s += "Here the originally inteded hourly schedule of " + persona.name + " today:\n"
    s += str(persona.meta_info["daily_req"])
    s += "Just return the action without anything else and only return one action without any other possible choices."
    s += "At " + curr_hour_str + ", " + persona.name + " is "
    return common_llm_call(persona.name, step, s, 50, None)
    

    
def generate_hourly_schedule(persona, step, wakeup_hour, debug = False):
    hour_str = ["00:00 AM", "01:00 AM", "02:00 AM", "03:00 AM", "04:00 AM", 
              "05:00 AM", "06:00 AM", "07:00 AM", "08:00 AM", "09:00 AM", 
              "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", 
              "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM", "07:00 PM",
              "08:00 PM", "09:00 PM", "10:00 PM", "11:00 PM"]
    n_m1_activity = []
    n_m1_activity.append(["sleeping", wakeup_hour])
    i = 0
    while(i < 24):
        curr_hour_str = hour_str[i]
        if i < wakeup_hour: 
            i += 1
            continue
        new_act = run_gpt_prompt_generate_hourly_schedule(
            persona, curr_hour_str, n_m1_activity, step)


     
        new_act = [new_act, 1]
        
        n_m1_activity.append(new_act)
        
            
        i += int(new_act[1])
    # hour to minute

    compressed_plan = []
    for i,item in enumerate(n_m1_activity):
        if len(compressed_plan) == 0:
            compressed_plan.append([item[0], int(item[1])])
        elif item[0] == compressed_plan[-1][0]:
            compressed_plan[-1][1] += int(item[1])
        else:
            compressed_plan.append([item[0], int(item[1])])
        # n_m1_activity[i] = [item[0], int(item[1]) * 60]S
    for i in range(len(compressed_plan)):
        compressed_plan[i][1] = compressed_plan[i][1] * 60
        
    

    return compressed_plan
def generate_task_decomp(persona,task,duration,step,debug = False):
    def extract_action_and_duration(input_string):
    # Extracting the part after 'is' and before '('
        match_action = re.search(r'is\s(.*?)\s\(', input_string)
        action = match_action.group(1) if match_action else ""

        # Extracting the duration number
        match_duration = re.search(r'\d+', input_string)
        duration = match_duration.group(0) if match_duration else ""

        return action, duration
    #### TODO need to change here

    curr_f_org_index = persona.get_f_daily_schedule_hourly_org_index()
    all_indices = []
    all_indices += [curr_f_org_index]
    if curr_f_org_index+1 <= len(persona.meta_info["f_daily_schedule_hourly_org"]): 
        all_indices += [curr_f_org_index+1]
    if curr_f_org_index+2 <= len(persona.meta_info["f_daily_schedule_hourly_org"]): 
        all_indices += [curr_f_org_index+2]
    curr_time_range = ""
    summ_str = f'Today is {persona.get_curr_time("%B %d, %Y")}. '
    for index in all_indices: 
          if index < len(persona.meta_info["f_daily_schedule_hourly_org"]): 
            start_min = 0
            daily_schedule_hourly_org = persona.meta_info["f_daily_schedule_hourly_org"]
            for i in range(index): 
                start_min += persona.meta_info["f_daily_schedule_hourly_org"][i][1]
                end_min = start_min + persona.meta_info["f_daily_schedule_hourly_org"][index][1]
                start_time = (datetime.datetime.strptime("00:00:00", "%H:%M:%S") 
                            + datetime.timedelta(minutes=start_min)) 
                end_time = (datetime.datetime.strptime("00:00:00", "%H:%M:%S") 
                            + datetime.timedelta(minutes=end_min)) 
                start_time_str = start_time.strftime("%H:%M%p")
                end_time_str = end_time.strftime("%H:%M%p")
                summ_str += f"{start_time_str} ~ {end_time_str}, {persona.name} is planning on {daily_schedule_hourly_org[index][0]}, "
                if curr_f_org_index+1 == index:
                    curr_time_range = f'{start_time_str} ~ {end_time_str}'
    summ_str = summ_str[:-2] + "." + "\n"
    summ_str += f"In 5 min increments, list the subtasks {persona.name} does when {persona.name} is {task} from {curr_time_range} (total duration in minutes {duration}):" + "\n"
    summ_str += f"Generate subtasks in the format of 1) {persona.name} is <task> (duration in minutes <duration>, minutes left <left>, 2) {persona.name} is <task> (duration in minutes <duration>, minutes left <left>)"
    # summ_str += 
    result = common_llm_call(persona.name, step, summ_str, 1000, None)
    
    lines = result.strip().split('\n')

    return_dict = []
    for line in lines:
        action, time = extract_action_and_duration(line)
        # print("action time",action, time)
        return_dict.append([action, int(time)])

    return return_dict
def generate_action_sector_again(act_descp, persona, env,step):
    file_path = "./new_template/generate_action_sector.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()
    living_place = persona.meta_info["living_area"] # sector
    living_sector = living_place.split(":")[0]
    possible_smem_arena_living_place = list(env.sector_arena_tree[living_sector].keys())
    states = env.db.hgetall(f"persona:{persona.name}")
    location = env.get_location_info(states["x"], states["y"])
    if location == "the Ville":
        possible_smem_arena_location = "Nothing"
    else:
        location = location.split(":")[1]
        possible_smem_arena_location = list(env.sector_arena_tree[location].keys())
    smem_all_possible_sector = list(env.sector_arena_tree.keys())
    
    for possible_sector in smem_all_possible_sector:
        if "'s house" in possible_sector:
            if persona.name.split(" ")[1] not in possible_sector:
                smem_all_possible_sector.remove(possible_sector)
    smem_all_possible_sector_list = smem_all_possible_sector
    smem_all_possible_sector = "{" + ", ".join(smem_all_possible_sector_list) + "}"
    living_sector = "{" + living_sector + "}"
    location = "{" + location + "}"
    daily_plan_req = persona.meta_info["daily_plan_req"]
    eg += ".\n"
    eg += f"{persona.name} lives in {living_sector} that has {possible_smem_arena_living_place}.\n"
    eg += f"{persona.name} is currently in {location} that has {possible_smem_arena_location}.\n"
    eg += f"{daily_plan_req}\n"
    eg += f"Area options:{smem_all_possible_sector}.\n"
    eg += sector_warning
    eg += "\n"
    eg += "Important: only choose from Area options!"
    eg += "\n"
    eg += f"{persona.name} is {act_descp}. For {act_descp}, {persona.name} should go to the following area:" +"{"
    # place = OpenAIBackend.generate(eg, max_tokens=15, trace_id=f"{persona.name}:{step}")
    place = common_llm_call(persona.name, step, eg, 15, None)
    for sector in smem_all_possible_sector_list:
        if sector in place:
            return sector
    print("warning, another false generation")
    
    return living_sector.strip("{").strip("}")
def generate_action_sector(act_descp, persona, env,step):
    file_path = "./new_template/generate_action_sector.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()
    #### TODO ask how to get that in env
    living_place = persona.meta_info["living_area"] # sector
    living_sector = living_place.split(":")[0]
    possible_smem_arena_living_place = persona.get_location_arena_smem(living_sector)
    if possible_smem_arena_living_place =="":
        possible_smem_arena_living_place = "{"+living_place.split(":")[1]+"}"
    states = env.db.hgetall(f"persona:{persona.name}")
    location = env.get_location_info(states["x"], states["y"])
    if location == "the Ville":
        possible_smem_arena_location = "Nothing"
    else:
        location = location.split(":")[1]
        possible_smem_arena_location = persona.get_location_arena_smem(location)
        possible_smem_arena_location = "{" + ", ".join(possible_smem_arena_location) + "}"
    smem_all_possible_sector = persona.get_location_sector_smem()
    if smem_all_possible_sector == "":
        smem_all_possible_sector = [living_sector,location]
    if living_sector not in smem_all_possible_sector:
        smem_all_possible_sector.append(living_sector)
    if location not in smem_all_possible_sector:
        smem_all_possible_sector.append(location)
    ## do not go to others places
    for possible_sector in smem_all_possible_sector:
        if "'s house" in possible_sector:
            if persona.name.split(" ")[1] not in possible_sector:
                smem_all_possible_sector.remove(possible_sector)
    #### will never choose the ville as the possible sector
    if "the Ville" in smem_all_possible_sector:
        smem_all_possible_sector.remove("the Ville")
    smem_all_possible_sector_list = smem_all_possible_sector
    smem_all_possible_sector = "{" + ", ".join(smem_all_possible_sector_list) + "}"
    living_sector = "{" + living_sector + "}"
    location = "{" + location + "}"
    daily_plan_req = persona.meta_info["daily_plan_req"]

    eg += ".\n"
    eg += f"{persona.name} lives in {living_sector} that has {possible_smem_arena_living_place}.\n"
    eg += f"{persona.name} is currently in {location} that has {possible_smem_arena_location}.\n"
    eg += f"{daily_plan_req}\n"
    eg += f"Area options:{smem_all_possible_sector}.\n"
    eg += sector_warning
    eg += "\n"
    eg += "only choose from Area options"
    eg += "\n"
    eg += f"{persona.name} is {act_descp}. For {act_descp}, {persona.name} should go to the following area:" +"{"
    #### TODO 

    # place = OpenAIBackend.generate(eg, max_tokens=15, trace_id=f"{persona.name}:{step}")
    place = common_llm_call(persona.name, step, eg, 15, None)

    for sector in smem_all_possible_sector_list:
        if sector in place:
            return sector
    #### regenerate

    print("False generateion on ---generate_action_sector---")

    
    return generate_action_sector_again(act_descp, persona, env,step)

def generate_action_arena(act_desp, persona, env, act_sector,step):
    #### TODO
    file_path = "./new_template/generate_action_arena.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()


    arena_list = list(env.sector_arena_tree[act_sector].keys())

    arena_list_str = "{" + ", ".join(arena_list) + "}"

    eg += f"{persona.name} is going to {act_sector} that has the following areas{arena_list_str}." + "\n"
    eg += arena_warning
    eg += "\n"
    eg += f"{persona.name} is {act_desp}. For {act_desp}, {persona.name} should go to the following area in {act_sector}(Must pick one in {arena_list_str}):"
    eg += "\n"
    eg += "Answer: {"

    # place = OpenAIBackend.generate(eg, max_tokens=15, trace_id=f"{persona.name}:{step}")
    place = common_llm_call(persona.name, step, eg, 15, None)
    for arena in arena_list:
        if arena in place:
            return arena
    print("False generateion on ---generate_action_arena---")
    print("arena place",place)
    print("arena_list",arena_list)
    return arena_list[0]
def generate_action_game_object(act_desp, act_sector,act_arena, persona, env,step):
    #### TODO
    file_path = "./new_template/generate_action_object.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()

    # game_object_list = persona.get_location_obj_smem(act_sector, act_arena)
    # if game_object_list == "":
    #     #### Cheanting!!!

    game_object_list = list(env.sector_arena_tree[act_sector][act_arena])
    game_object_list_str = "{" + ", ".join(game_object_list) + "}"
    eg += f"Current activity: {act_desp}.\n"
    eg += f"Ojbects available: {game_object_list_str}.\n"
    eg += "Pick ONE most relevant object from the objects available:"
    # result = OpenAIBackend.generate(eg, max_tokens=30, trace_id=f"{persona.name}:{step}")
    result = common_llm_call(persona.name, step, eg, 30, None)
    for game_object in game_object_list:
        if game_object in result:
            return game_object
    print(env.sector_arena_tree[act_sector][act_arena])
    print(result)
    print(game_object_list)
    return game_object_list[0]
    # raise ValueError("False generation on ---generate_action_game_object---")
def generate_action_pronunciatio(act_desp, persona,step):
    eg = ""
    eg += "Convert an action description to an emoji(important: use two or less emojis)." + "\n"
    eg == "Action description: " + act_desp + "\n"
    
    # emojis = OpenAIBackend.generate(eg, max_tokens=15, trace_id=f"{persona.name}:{step}")
    emojis = common_llm_call(persona.name, step, eg, 15, None)
    return emojis
def generate_action_event_triple(act_desp, persona, step):
    file_path = "./new_template/generate_event_triple_v1.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()
    eg += "Inmportant, only return one set of triplets" + "\n"
    eg += f"Input: {persona.name} is {act_desp}." + "\n"
    eg += f"Output: ({persona.name},"
    results = common_llm_call(persona.name, step, eg, 30, None)
    # results = OpenAIBackend.generate(eg, max_tokens=30, trace_id=f"{persona.name}:{step}")
    print("results",results)
    if ")" in results:
        results = results.strip(")")
    if len(results.split(",")) >=2 :
        predicate = results.split(",")[0]
        object = results.split(",")[1]
    else:
        predicate = results.split(",")[0]
        object = ""
        


    return  (persona.name,predicate, object)
def generate_act_obj_desc(act_game_object, act_desp, persona, step):
    eg = ""
    eg += "Task: We want to understand the state of an object that is being used by someone." + "\n"
    eg += "Return 15 words at most." + "\n"
    eg += "Let's think step by step. " + "\n"
    eg += f"We want to know about {act_game_object}'s state." + "\n"
    eg += f"Step 1: {persona.name} is at/using the {act_desp}." + "\n"
    eg += f"Step 2: Describe the state of {act_game_object}: {act_game_object} is"
    # results = OpenAIBackend.generate(eg, max_tokens=30, trace_id=f"{persona.name}:{step}")
    results = common_llm_call(persona.name, step, eg, 30, None)

    return f"{act_game_object} is {results}"
def generate_act_obj_event_triple(act_game_object, act_obj_desc, persona, step):
    eg = ""
    eg += "Task: Turn the input into (subject, predicate, object)." + "\n"
    eg += "return only one set in the format of (subject, predicate, object)." + "\n"
    eg += f"Input: {act_game_object} is {act_obj_desc}." + "\n"
    eg += "Output:"
    results = common_llm_call(persona.name, step, eg, 30, None)
    # results = OpenAIBackend.generate(eg, max_tokens=30, trace_id=f"{persona.name}:{step}")
    results = results.strip(")").split("(")
    

    return (act_game_object, "is", "idle")
def generate_decide_to_talk(init_persona, target_persona, retrieved,step): 
    file_path = "./new_template/decide_to_talk_v2.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()
    #### create context
    last_chat = init_persona.get_last_chat(target_persona.name)
    if last_chat: 
        last_chatted_time = init_persona.from_step_to_time(last_chat.created).strftime("%B %d, %Y, %H:%M:%S")
        last_chat_about = last_chat.description
    context = ""
    for event_node in retrieved["events"]:
        curr_desc = event_node.description.replace("is", "was")
        curr_desc = " ".join(curr_desc)
        context +=  f"{curr_desc}. "
    context += "\n"
    for thought_node in retrieved["thoughts"]:
        context +=  f"{thought_node.description}. "
    curr_time = init_persona.get_curr_time("%B %d, %Y, %H:%M:%S %p")
    init_act_desc = init_persona.meta_info["act_description"]
    
    if len(init_persona.meta_info["planned_path"]) == 0 and "waiting" not in init_act_desc: 
        init_p_desc = f"{init_persona.name} is already {init_act_desc}"
    elif "waiting" in init_act_desc:
        init_p_desc = f"{init_persona.name} is {init_act_desc}"
    else: 
        init_p_desc = f"{init_persona.name} is on the way to {init_act_desc}"
    target_act_desc = target_persona.meta_info["act_description"]
    if len(target_persona.scratch.planned_path) == 0 and "waiting" not in init_act_desc: 
        target_p_desc = f"{target_persona.name} is already {target_act_desc}"
    elif "waiting" in init_act_desc:
        target_p_desc = f"{init_persona.name} is {init_act_desc}"
      
    else: 
        target_p_desc = f"{target_persona.name} is on the way to {target_act_desc}"
    eg += f"Context: {context}" + "\n"
    if last_chat is not None:
        eg += f"Right now, it is {curr_time}. {init_persona.name} and {target_persona.name} last chatted at {last_chatted_time} about {last_chat_about}." + "\n"
    else:
        eg += f"Right now, it is {curr_time}. {init_persona.name} and {target_persona.name} have not chatted yet." + "\n"
    eg +=f"{init_p_desc}." + "\n"
    eg += f"{target_p_desc}." + "\n"
    eg += f"uestion: Would {init_persona.name} initiate a conversation with {target_persona.name}? Answer yes or no" +'\n'
    eg += "Reasoning: Let's think step by step. " + "\n"
    results = common_llm_call(init_persona.name, step, eg, 100, None)
    # results = OpenAIBackend.generate(eg, max_tokens=50, trace_id=f"{init_persona.name}:{step}")
    if "yes" in results:
        return True
    elif "no" in results:
        return False
    
    raise ValueError("False generation on ---generate_decide_to_talk---")

def generate_decide_to_react(init_persona, target_persona, retrieved,step): 
    file_path = "./new_template/decide_to_talk_v2.txt"
    with open(file_path, 'r', encoding='utf-8') as file:
        eg = file.read()
    context = ""
    for event_node in retrieved["events"]:
        curr_desc = event_node.description.replace("is", "was")
        curr_desc = " ".join(curr_desc)
        context +=  f"{curr_desc}. "
    context += "\n"
    for thought_node in retrieved["thoughts"]:
        context +=  f"{thought_node.description}. "
    curr_time = init_persona.get_curr_time("%B %d, %Y, %H:%M:%S %p")
    init_act_desc = init_persona.meta_info["act_description"]
    if len(init_persona.meta_info["planned_path"]) == 0: 
        loc = ""
        if ":" in init_persona.meta_info["act_address"]:
            loc = init_persona.meta_info["act_address"].split(":")[-1] + " in " + init_persona.meta_info["act_address"].split(":")[-2]
        init_p_desc = f"{init_persona.name} is already {init_act_desc} at {loc}"
    else:
        loc = ""
        if ":" in init_persona.meta_info["act_address"]:
            loc = init_persona.meta_info["act_address"].split(":")[-1] + " in " + init_persona.meta_info["act_address"].split(":")[-2]
        init_p_desc = f"{init_persona.name} is on the way to {init_act_desc} at {loc}"
    target_act_desc = target_persona.meta_info["act_description"]
    if len(target_persona.meta_info["planned_path"]) == 0: 
        loc = ""
        if ":" in target_persona.meta_info["act_address"]:
            loc = target_persona.meta_info["act_address"].split(":")[-1] + " in " + target_persona.meta_info["act_address"].split(":")[-2]
        target_p_desc = f"{target_persona.name} is already {target_act_desc} at {loc}"
    else:
        loc = ""
        if ":" in target_persona.meta_info["act_address"]:
            loc = target_persona.meta_info["act_address"].split(":")[-1] + " in " + target_persona.meta_info["act_address"].split(":")[-2]
        target_p_desc = f"{target_persona.name} is on the way to {target_act_desc} at {loc}"
    eg += f"Context: {context}" + "\n"
    eg += f"Right now, it is {curr_time}." + "\n"
    eg += f"{init_p_desc}." + "\n"
    eg += f"{target_p_desc}." + "\n"
    eg += f"My question: Let's think step by step. Of the following three options, what should {init_persona.name} do?" + "\n"
    eg += f"Option 1: Wait on {init_act_desc} until {target_persona.name} is done {target_act_desc}" + "\n"
    eg += f"Option 2: Continue on to {init_act_desc} now." + "\n"
    eg += f"Return with 1 or 2 only."
    results = common_llm_call(init_persona.name, step, eg, 50, None)
    # results = OpenAIBackend.generate(eg, max_tokens=50, trace_id=f"{init_persona.name}:{step}")
    if "2" in results:
        return "2"
    elif "1" in results:
        return "1"
    raise ValueError("False generation on ---generate_decide_to_react---")
def generate_convo(env, init_persona, target_persona, step):
    curr_chat = []
    for i in range(8):
        focal_points = [f"{target_persona.name}"]
        retrieved = new_retrieve(init_persona, focal_points, 50)
        relationship = generate_summarize_agent_relationship(init_persona, target_persona, retrieved, step)
        last_chat = ""
        target_act_description = target_persona.meta_info["act_description"]
        for i in curr_chat[-4:]:
            last_chat += ": ".join(i) + "\n"
        if last_chat: 
            focal_points = [f"{relationship}", 
                        f"{target_persona.name} is {target_act_description}", 
                        last_chat]
        else: 
            focal_points = [f"{relationship}", 
                        f"{target_persona.name} is {target_act_description}"]
        retrieved = new_retrieve(init_persona, focal_points, 15)
        utt, end = generate_one_utterance(env, init_persona, target_persona, retrieved, curr_chat,step)
        curr_chat.append([init_persona.scratch.name, utt])
        if end:
            break
        focal_points = [f"{init_persona.scratch.name}"]
        retrieved = new_retrieve(target_persona, focal_points, 50)
        relationship = generate_summarize_agent_relationship(target_persona, init_persona, retrieved)
        last_chat = ""
        for i in curr_chat[-4:]:
            last_chat += ": ".join(i) + "\n"
            init_act_description = init_persona.meta_info["act_description"]
        if last_chat: 
            focal_points = [f"{relationship}", 
                            f"{init_persona.name} is {init_act_description}", 
                            last_chat]
        else: 
            focal_points = [f"{relationship}", 
                            f"{init_persona.name} is {init_act_description}"]
        retrieved = new_retrieve(target_persona, focal_points, 15)
        utt, end = generate_one_utterance(env, target_persona, init_persona, retrieved, curr_chat)
        curr_chat.append([target_persona.scratch.name, utt])
        if end:
            break
    all_utt = ""

    for row in curr_chat: 
        speaker = row[0]
        utt = row[1]
        all_utt += f"{speaker}: {utt}\n"
    convo_length = math.ceil(int(len(all_utt)/8) / 30)
    return curr_chat, convo_length
def generate_one_utterance(env, init_persona, target_persona, retrieved, curr_chat,step):
    init_act_description = init_persona.meta_info["act_description"]
    target_act_description = target_persona.meta_info["act_description"]
    curr_context = (f"{init_persona.name} " + 
              f"was {init_act_description} " + 
              f"when {init_persona.name} " + 
              f"saw {target_persona.name} " + 
              f"in the middle of {target_act_description}.\n")
    curr_context += (f"{init_persona.scratch.name} " +
                f"is initiating a conversation with " +
                f"{target_persona.scratch.name}.")
    
    utt, end = generate_iterative_chat_utterance(env, init_persona, target_persona, retrieved, curr_context, curr_chat,step)
    return utt, end
    
    
def generate_iterative_chat_utterance(env, init_persona, target_persona, retrieved, curr_context, curr_chat,step):  
    def extract_values(str):
        utt_pattern = re.compile(r'\".*?\'s utterance\": \"(.*?)\"')
        end_pattern = re.compile(r'\"Did the conversation end with .*?\'s utterance\? \(only answer yes or no\)\": \"(.*?)\"')
        utterance_match = utt_pattern.search(str)
        end_match = end_pattern.search(str)
        if utterance_match and end_match:
            return utterance_match.group(1), end_match.group(1)
        else:
            return str, "no"
    init_iss = f"Here is Here is a brief description of {init_persona.name}.\n{init_persona.get_str_iss()}"
    retrieved_str = ""
    for key, vals in retrieved.items(): 
        for v in vals: 
            retrieved_str += f"- {v.description}\n"
    ####
    persona = init_persona
    prev_convo_insert = "\n"
    # if persona.a_mem.seq_chat: 
    #   for i in persona.a_mem.seq_chat: 
    #     if i.object == target_persona.scratch.name: 
    #       v1 = int((persona.scratch.curr_time - i.created).total_seconds()/60)
    #       prev_convo_insert += f'{str(v1)} minutes ago, {persona.scratch.name} and {target_persona.scratch.name} were already {i.description} This context takes place after that conversation.'
    #       break
    
    # if prev_convo_insert == "\n": 
    #     prev_convo_insert = ""
    # if persona.a_mem.seq_chat: 
    #     if int((persona.scratch.curr_time - persona.a_mem.seq_chat[-1].created).total_seconds()/60) > 480: 
    #         prev_convo_insert = ""
    last_relavent_chat = persona.get_related_last_chat(target_persona.name,480)
    if last_relavent_chat is None:
        prev_convo_insert = ""
    else:
        step_gap = persona.step - last_relavent_chat.created
        minutes_gap = int(step_gap * env.sec_per_step/60)
        prev_convo_insert += f'{str(minutes_gap)} minutes ago, {persona.name} and {target_persona.name} were already {last_relavent_chat.description} This context takes place after that conversation.'
    states = env.db.hgetall(f"persona:{persona.name}")

    location = env.get_location_info(states["x"], states["y"])
    
    convo_str = ""
    for i in curr_chat:
        convo_str += ": ".join(i) + "\n"
    if convo_str == "": 
        convo_str = "[The conversation has not started yet -- start it!]"
    eg = ""
    eg += "Context for the task:" + " \n"
    eg += "PART 1." + "\n"
    eg += f"{init_iss}" + "\n"
    eg += f"Here is the memory that is in {init_persona.name}'s head: " + "\n"
    eg += f"{retrieved_str}" + "\n"
    eg += "PART 2." + "\n"
    eg += "Past Context:" + "\n"
    eg += f"{prev_convo_insert}" + "\n"
    
    eg += f"Current Location: {location}"
    eg += f"Current Context:" + "\n"
    eg += f"{curr_context}" + "\n"
    eg += f"{persona.name} and {target_persona.name} are chatting. Here is their conversation so far:" + "\n"
    eg += f"{convo_str}" + "\n"
    eg == f"---" + "\n"
    eg += f"Task: Given the above, what should {persona.name} say to {target_persona.name} next in the conversation? And did it end the conversation?"
    eg += "Important, generate answer about 50 words strictly based on the Output format given below."
    eg += "Output format: only output a python diction of the following format:"
    eg += "{" + "\n"
    # eg += f"\"utterance\": \"{persona.name}'s utterance>\"" + "\n"
    # eg += f"\"end\": \"<json Boolean>\"" + "\n"
    eg += f"\"{persona.name}'s utterance\":" + "\n"
    eg += f"Did the conversation end with {persona.name}'s utterance?(only answer yes or no):" + "\n"
    eg += "}"
    results = common_llm_call(persona.name, step, eg, 100, None)
    # results = OpenAIBackend.generate(eg, max_tokens=100, trace_id=f"{init_persona.name}:{step}")
    utt, end = extract_values(results)
    if "yes" in end:
        return utt, True
    else:
        return utt, False

    
    
    
    
    
    
def generate_summarize_agent_relationship(init_persona, target_persona, retrieved,step):
    all_embedding_keys = list()
    for key, val in retrieved.items(): 
        for i in val: 
            all_embedding_keys += [i.embedding_key]
    all_embedding_key_str =""
    for i in all_embedding_keys: 
        all_embedding_key_str += f"{i}\n"
    eg = ""
    eg += "[Statements]" + "\n"
    eg += f"{all_embedding_key_str}"
    eg += f"Based on the statements above, summarize {init_persona.name} and {target_persona.name}'s relationship. What do they feel or know about each other?"
    eg += f"keep to summarization in about 30 words"
    results = common_llm_call(init_persona.name, step, eg, 50, None)
    # results = OpenAIBackend.generate(eg, max_tokens=50, trace_id=f"{init_persona.name}:{step}")
    return results
def generate_convo_summary(persona, convo,step):
    convo_str = ""
    for row in convo: 
      convo_str += f'{row[0]}: "{row[1]}"\n'

    eg = ""
    eg += "Conversation:" + "\n"
    eg += f"{convo_str}" + "\n"
    eg += "Summarize the conversation above in one sentence within 20 words:" + "\n"
    eg += "This is a conversation about"
    results = common_llm_call(persona.name, step, eg, 30, None)
    # results = OpenAIBackend.generate(eg, max_tokens=30, trace_id=f"{persona.name}:{step}")
    return results
def generate_new_decomp_schedule(persona, inserted_act, inserted_act_dur,  start_hour, end_hour): 
    p = persona
    main_act_dur = []
    truncated_act_dur = []
    dur_sum = 0 # duration sum
    count = 0 # enumerate count
    truncated_fin = False 
    today_min_pass = (int(p.get_curr_time().hour) * 60 
                    + int(p.get_curr_time().minute) + 1)
    for act, dur in persona.meta_info["f_daily_schedule"]:
        if (dur_sum >= start_hour * 60) and (dur_sum < end_hour * 60): 
            main_act_dur += [[act, dur]]
            if dur_sum <= today_min_pass:
                truncated_act_dur += [[act, dur]]
            elif dur_sum > today_min_pass and not truncated_fin: 
                truncated_act_dur += [[p.scratch.f_daily_schedule[count][0], 
                               dur_sum - today_min_pass]] 
                truncated_act_dur[-1][-1] -= (dur_sum - today_min_pass)
                truncated_fin = True
        dur_sum += dur
        count += 1
    persona_name = persona.name 
    main_act_dur = main_act_dur
    x = truncated_act_dur[-1][0].split("(")[0].strip() + " (on the way to " + truncated_act_dur[-1][0].split("(")[-1][:-1] + ")"
    truncated_act_dur[-1][0] = x 
    if "(" in truncated_act_dur[-1][0]: 
        inserted_act = truncated_act_dur[-1][0].split("(")[0].strip() + " (" + inserted_act + ")"
    
    truncated_act_dur += [[inserted_act, inserted_act_dur]]
    start_time_hour = (p.get_date()
                    + datetime.timedelta(hours=start_hour))
    end_time_hour = (p.get_date() 
                    + datetime.timedelta(hours=end_hour))
    return generate_new_decomp_schedule_llm(persona, 
                                            main_act_dur, 
                                            truncated_act_dur, 
                                            start_time_hour,
                                            end_time_hour,
                                            inserted_act,
                                            inserted_act_dur,persona.step)
def generate_new_decomp_schedule_llm(persona, 
                                       main_act_dur, 
                                       truncated_act_dur, 
                                       start_time_hour,
                                       end_time_hour, 
                                       inserted_act,
                                       inserted_act_dur,step):
    start_hour = start_time_hour.strftime("%H:%M %p")
    end_hour = end_time_hour.strftime("%H:%M %p")
    original_plan = ""
    for i in main_act_dur: 
        original_plan += f'{start_time_hour.strftime("%H:%M")} ~ {(start_time_hour + datetime.timedelta(minutes=int(i[1]))).strftime("%H:%M")} -- ' + i[0]
        original_plan += "\n"
        start_time_hour += datetime.timedelta(minutes=int(i[1]))
        
    ####
    for count, i in enumerate(truncated_act_dur): 
        new_plan_init += f'{for_time.strftime("%H:%M")} ~ {(for_time + datetime.timedelta(minutes=int(i[1]))).strftime("%H:%M")} -- ' + i[0]
        new_plan_init += "\n"
        if count < len(truncated_act_dur) - 1: 
            for_time += datetime.timedelta(minutes=int(i[1]))
    new_plan_init = ""
    new_plan_init += (start_time_hour + datetime.timedelta(minutes=int(i[1]))).strftime("%H:%M") + " ~"
    eg = ""
    eg += f"Here was {persona.name}'s originally planned schedule from {start_hour} to {end_hour}. " + "\n"
    eg += original_plan
    eg += f"But {persona.name} unexpectedly ended up {inserted_act} for {inserted_act_dur} minutes. Revise {persona.name}'s schedule from {start_hour} to {end_hour} accordingly (it has to end by {end_hour}). " + "\n"
    eg += "The revised schedule:"
    eg += new_plan_init
    result = common_llm_call(persona.name, step, eg, 1000, None)
    # result = OpenAIBackend.generate(eg, max_tokens=1000, trace_id=f"{persona.name}:{step}")
    ##### clean up
    new_schedule = eg + " " + result.strip()
    new_schedule = new_schedule.split("The revised schedule:")[-1].strip()
    new_schedule = new_schedule.split("\n")
    ret_temp = []
    for i in new_schedule: 
        ret_temp += [i.split(" -- ")]

    ret = []
    for time_str, action in ret_temp:
        start_time = time_str.split(" ~ ")[0].strip()
        end_time = time_str.split(" ~ ")[1].strip()
        delta = datetime.datetime.strptime(end_time, "%H:%M") - datetime.datetime.strptime(start_time, "%H:%M")
        delta_min = int(delta.total_seconds()/60)
        if delta_min < 0: delta_min = 0
        ret += [[action, delta_min]]
    return ret
def common_llm_call(persona_name, step, prompt, max_tokens, stop,reg = None):
    result = OpenAIBackend.generate(prompt,
                                  max_tokens=max_tokens,
                                  step=step,
                                  stop=stop,
                                  trace_id=f"{persona_name}:{step}")

    if reg is not None:
        return re.findall(reg, result)
    else:
        return result
