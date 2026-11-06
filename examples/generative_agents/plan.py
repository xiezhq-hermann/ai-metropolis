from utils import *
import datetime
from retrieve import new_retrieve
import random
import sys
from agent_functions import *
sys.path.append("../")
from agent_functions import *


def revise_identity(persona):
    p_name = persona.name

    focal_points = [
        f"{p_name}'s plan for {persona.get_curr_date()}.",
        f"Important recent events for {p_name}'s life.",
    ]
    retrieved = new_retrieve(persona, focal_points)

    statements = "[Statements]\n"
    if len(retrieved) == 0:
        statements += f"{p_name} has no recent events.\n"
    else:
        for key, val in retrieved.items():
            for i in val:
                #### Warning need to look at this after fixed
                statements += f"{persona.from_step_to_time(i.created).strftime('%A %B %d -- %H:%M %p')}: {i.embedding_key}\n"

    # print (";adjhfno;asdjao;idfjo;af", p_name)
    plan_prompt = statements + "\n"
    plan_prompt += f"Given the statements above, is there anything that {p_name} should remember as they plan for"
    curr_time = persona.get_curr_time("%Y-%m-%d")
    plan_prompt += f" *{curr_time}*? "
    plan_prompt += f"If there is any scheduling information, be as specific as possible (include date, time, and location if stated in the statement)\n\n"
    plan_prompt += f"Write the response from {p_name}'s perspective."
    plan_note = Single_request(plan_prompt,persona)
    # print (plan_note)

    thought_prompt = statements + "\n"
    thought_prompt += f"Given the statements above, how might we summarize {p_name}'s feelings about their days up to now?\n\n"
    thought_prompt += f"Write the response from {p_name}'s perspective."
    thought_note = Single_request(thought_prompt,persona)
    # print (thought_note)
    currently = persona.meta_info["currently"]
    #### Warning need to look at this after fix step and time
    currently_prompt = f"{p_name}'s status from {(persona.get_full_curr_time() - datetime.timedelta(days=1)).strftime('%A %B %d')}(one day from now):\n"
    currently_prompt += f"{currently}\n\n"
    currently_prompt += f"{p_name}'s thoughts at the end of {(persona.get_full_curr_time() - datetime.timedelta(days=1)).strftime('%A %B %d')}(one day from now):\n"
    currently_prompt += (plan_note + thought_note).replace("\n", "") + "\n\n"
    currently_prompt += f"It is now {curr_time}. Given the above, write {p_name}'s status for {persona.get_full_curr_time().strftime('%A %B %d')} that reflects {p_name}'s thoughts at the end of {(persona.get_full_curr_time() - datetime.timedelta(days=1)).strftime('%A %B %d')}. Write this in third-person talking about {p_name}."
    currently_prompt += f"If there is any scheduling information, be as specific as possible (include date, time, and location if stated in the statement).\n\n"
    currently_prompt += "Follow this format below:\nStatus: <new status>"
    # print ("DEBUG ;adjhfno;asdjao;asdfsidfjo;af", p_name)
    # print (currently_prompt)
    new_currently = Single_request(currently_prompt,persona)
    # print (new_currently)
    # print (new_currently[10:])
    #### Warning what is this
    persona.meta_info["currently"] = new_currently

    daily_req_prompt = persona.get_str_iss() + "\n"
    daily_req_prompt += f"Today is {persona.get_full_curr_time().strftime('%A %B %d')}. Here is {persona.name}'s plan today in broad-strokes (with the time of the day. e.g., have a lunch at 12:00 pm, watch TV from 7 to 8 pm).\n\n"
    daily_req_prompt += (
        f"Follow this format (the list should have 4~6 items but no more):\n"
    )
    daily_req_prompt += f"1. wake up and complete the morning routine at <time>, 2. ..."

    new_daily_req = Single_request(daily_req_prompt,persona)
    new_daily_req = new_daily_req.replace("\n", " ")


    persona.meta_info["daily_plan_req"] = new_daily_req








def _long_term_planning(persona, new_day,env, debug = False):
    wake_up_hour = generate_wake_up_hour(persona, persona.step, debug = False)
    wake_up_hour = int(wake_up_hour)
    if new_day == "First day":
        if wake_up_hour <= 8 :
            wake_up_hour = 8
            persona.meta_info["daily_req"] = generate_first_daily_plan(persona, wake_up_hour,persona.step)


    elif new_day == "New day":
        revise_identity(persona)
        # persona.scratch.daily_req = persona.scratch.daily_req
    ### list of list 
    # [['sleeping', 6], ['waking up and starting her morning routine', 1], 
    # ['eating breakfast', 1], ['getting ready for the day', 1], 
    # ['working on her painting', 2], ['taking a break', 1], 
    # ['having lunch', 1], ['working on her painting', 3], 
    # ['taking a break', 2], ['working on her painting', 2], 
    # ['relaxing and watching TV', 1], ['going to bed', 1], ['sleeping', 2]]
    # print(f"daily_plan,{persona.name}",persona.meta_info["daily_req"])
    persona.meta_info["f_daily_schedule"] = generate_hourly_schedule(persona,persona.step,wake_up_hour, debug=False)[:]
    # print(f"hourly schedule,{persona.name}",persona.meta_info["f_daily_schedule"])
    
    persona.meta_info["f_daily_schedule_hourly_org"] = persona.meta_info["f_daily_schedule"][:]
    
    curr_day = persona.get_curr_time("%Y-%m-%d")
    thought = f"This is {persona.name}'s plan for {curr_day}:"
    for i in persona.meta_info["daily_req"]:
        thought += f"\n{i}"
    thought = thought[:-1] + "."
    created = persona.step
    # expiration = persona.get_full_curr_time() + datetime.timedelta(days=30)
    expiration = persona.step + 30 * 6 * 60 * 24 ## 30 days
    s, p, o = (persona.name, "plan", curr_day)
    keywords = set(["plan"])
    thought_poignancy = 5
    thought_embedding_pair = (thought, get_embedding(thought))

    states = env.db.hgetall(f"persona:{persona.name}")

    location = env.get_location_info(states["x"], states["y"])
    location = str(location)
    input_dict = {
        "created": created,
        "expiration": expiration,
        "subject": s,
        "predicate": p,
        "object": o,
        "location" : location,
        "description": thought,
        "keywords": keywords,
        "poignancy": thought_poignancy,
        "embedding_pair": thought_embedding_pair,
        "filling": None,
        "last_accessed": persona.step,
        }
    persona.amem_add(
        input_dict,
        "thought",
    )





def _determine_action(persona, env):
    ### TODO here
    def determine_decomp(act_desp, act_dura):
        if "sleep" not in act_desp and "bed" not in act_desp:
            return True
        elif "sleeping" in act_desp or "asleep" in act_desp or "in bed" in act_desp:
            return False
        elif "sleep" in act_desp or "bed" in act_desp:
            if act_dura > 60:
                return False
        return True

    curr_index = persona.get_daily_schedule_idx()
    curr_index_60 = persona.get_daily_schedule_idx(advance=60)
    # print("daily_plan_req",persona.meta_info["daily_plan_req"])
    # print("determin",curr_index,curr_index_60)
    if curr_index == 0:
        act_desp, act_dura = persona.meta_info["f_daily_schedule"][curr_index]
        if act_dura >= 60:
            if determine_decomp(act_desp, act_dura):
                persona.meta_info["f_daily_schedule"][
                    curr_index : curr_index + 1
                ] = generate_task_decomp(persona, act_desp, act_dura,persona.step)
    if curr_index_60 + 1 < len(persona.meta_info["f_daily_schedule"]):
        act_desp, act_dura = persona.meta_info["f_daily_schedule"][curr_index_60 + 1]
        if act_dura >= 60:
            if determine_decomp(act_desp, act_dura):
                persona.meta_info["f_daily_schedule"][
                    curr_index_60 + 1 : curr_index_60 + 2
                 ] = generate_task_decomp(persona, act_desp, act_dura,persona.step)
    if curr_index_60 < len(persona.meta_info["f_daily_schedule"]):
        if persona.get_curr_time(string_format = False).hour < 23:
            act_desp, act_dura = persona.meta_info["f_daily_schedule"][curr_index_60]
            if act_dura >= 60:
                if determine_decomp(act_desp, act_dura):
                    persona.meta_info["f_daily_schedule"][
                        curr_index_60 : curr_index_60 + 1
                    ] = generate_task_decomp(persona, act_desp, act_dura,persona.step)


    x_emergency = 0
    # print(f"daily_schedule{persona.name}",persona.meta_info["f_daily_schedule"])
    for i in persona.meta_info["f_daily_schedule"]:
        x_emergency += i[1]
    if 1440 - x_emergency > 0:
        print("idle plan at night, directly sleep")
    
    persona.meta_info["f_daily_schedule"] += [["sleeping", 1440 - x_emergency]]
    act_desp, act_dura = persona.meta_info["f_daily_schedule"][curr_index]
    # Finding the target location of the action and creating action-related
    # variables.
    #### TODO need to implement these
    
    states = env.db.hgetall(f"persona:{persona.name}")

    location = env.get_location_info(states["x"], states["y"])
    location_list = location.split(":")
    act_world = location_list[0]

    # act_sector = maze.access_tile(persona.scratch.curr_tile)["sector"]
    act_sector = generate_action_sector(act_desp, persona, env ,persona.step)
    act_arena = generate_action_arena(act_desp, persona, env, act_sector,persona.step)

    act_game_object = generate_action_game_object(act_desp,act_sector, act_arena, persona, env,persona.step)
    new_address = f"{act_world}:{act_sector}:{act_arena}:{act_game_object}"
    # print("persona:",persona.name,"new_address",new_address)
    act_pron = generate_action_pronunciatio(act_desp, persona,persona.step)
    act_event = generate_action_event_triple(act_desp, persona,persona.step)
    # Persona's actions also influence the object states. We set those up here.
    act_obj_desp = generate_act_obj_desc(act_game_object, act_desp, persona,persona.step)
    act_obj_pron = generate_action_pronunciatio(act_obj_desp, persona,persona.step)
    act_obj_event = generate_act_obj_event_triple(
        act_game_object, act_obj_desp, persona,persona.step
    )
    ### new action unlock
    if persona.action_lock:
        persona.action_lock = False
    persona.add_new_action(
        new_address,
        int(act_dura),
        act_desp,
        act_pron,
        act_event,
        None,
        None,
        None,
        None,
        act_obj_desp,
        act_obj_pron,
        act_obj_event,
    )


def _choose_retrieved(persona, retrieved):
    #### Warning what is the form of this retrieved

    copy_retrieved = retrieved.copy()
    for event_desc, rel_ctx in copy_retrieved.items():
        curr_event = rel_ctx["curr_event"]
        if curr_event.subject == persona.name:
            del retrieved[event_desc]
    priority = []
    for event_desc, rel_ctx in retrieved.items():
        curr_event = rel_ctx["curr_event"]
        if ":" not in curr_event.subject and curr_event.subject != persona.name:
            priority += [rel_ctx]
    if priority:
        return random.choice(priority)
    for event_desc, rel_ctx in retrieved.items():
        curr_event = rel_ctx["curr_event"]
        if "is idle" not in event_desc:
            priority += [rel_ctx]
    if priority:
        return random.choice(priority)
    return None


def _should_react(persona, retrieved, personas):
    
    def lets_talk(init_persona, target_persona, retrieved):
        ## init no plan no place to go
        if (
            not target_persona.meta_info["act_address"]
            or not target_persona.meta_info["act_description"]
            or not init_persona.meta_info["act_address"]
            or not init_persona.meta_info["act_description"]
        ):

            return False
        ## sleep
        if (
            "sleeping" in target_persona.meta_info["act_description"]
            or "sleeping" in init_persona.meta_info["act_description"]
        ):
            return False
        ## too late no talk
        if init_persona.get_curr_time(string_format = False).hour == 23:

            return False

        # if "<waiting>" in target_persona.meta_info["act_address"]:

        #     return False
        # lock action
        if target_persona.action_lock or init_persona.action_lock:
            return False
        # if target_persona.meta_info["chatting_with"] or init_persona.meta_info["chatting_with"]:

        #     return False

        if target_persona.name in init_persona.meta_info["chatting_with_buffer"]:
            if init_persona.meta_info["chatting_with_buffer"][target_persona.name] > 0:
                return False
        #### TODO need to implement these
        if generate_decide_to_talk(init_persona, target_persona, retrieved,init_persona.step):
            ### set lock
            init_persona.action_lock = True
            target_persona.action_lock = True
            return True

        return False

    def lets_react(init_persona, target_persona, retrieved):
        #### init 
        if (
            not target_persona.meta_info["act_address"]
            or not target_persona.meta_info["act_description"]
            or not init_persona.meta_info["act_address"]
            or not init_persona.meta_info["act_description"]
        ):
            return False
        #### sleep
        if (
            "sleeping" in target_persona.meta_info["act_description"]
            or "sleeping" in init_persona.meta_info["act_description"]
        ):
            return False

        # return False
        if init_persona.action_lock or target_persona.action_lock:
            return False
        if init_persona.get_curr_time(string_format = False).hour == 23:
            return False

        if "waiting" in target_persona.meta_info["act_description"]:
            return False
        if init_persona.scratch.planned_path == []:
            return False

        if init_persona.meta_info["act_address"] != target_persona.meta_info["act_address"]:
            return False
        #### TODO need to implement these
        react_mode = generate_decide_to_react(init_persona, target_persona, retrieved,init_persona.step)

        if react_mode == "1":
            # wait_until = (
            #     target_persona.meta_info["act_start_time"]
            #     + datetime.timedelta(minutes=target_persona.meta_info["act_duration"] - 1)
            # ).strftime("%B %d, %Y, %H:%M:%S")
            wait_until = int(target_persona.meta_info["act_start_time"] + target_persona.meta_info["act_duration"] - init_persona.step)
            return f"wait: {wait_until}"
        elif react_mode == "2":
            return False
        else:
            return False  # "keep"

    # If the persona is chatting right now, default to no reaction
    # if persona.meta_info["chatting_with"]:
    #     return False
    # if "<waiting>" in persona.meta_info["act_address"]:
    #     return False
    if persona.action_lock:
        return False
    
    
    
    # Recall that retrieved takes the following form:
    # dictionary {["curr_event"] = <ConceptNode>,
    #             ["events"] = [<ConceptNode>, ...],
    #             ["thoughts"] = [<ConceptNode>, ...]}
    curr_event = retrieved["curr_event"]

    if ":" not in curr_event.subject:
        # this is a persona event.
        if lets_talk(persona, personas[curr_event.subject], retrieved):
            return f"chat with {curr_event.subject}"
        react_mode = lets_react(persona, personas[curr_event.subject], retrieved)
        return react_mode
    return False


def _create_react(
    persona,
    inserted_act,
    inserted_act_dur,
    act_address,
    act_event,
    chatting_with,
    chat,
    chatting_with_buffer,
    chatting_end_time,
    act_pronunciatio,
    act_obj_description,
    act_obj_pronunciatio,
    act_obj_event,
    act_start_time=None,
):
    p = persona

    min_sum = 0
    for i in range(p.get_f_daily_schedule_hourly_org_index()):
        min_sum += p.meta_info["f_daily_schedule_hourly_org"][i][1]
    start_hour = int(min_sum / 60)

    if (
        p.meta_info["f_daily_schedule_hourly_org"][
            p.get_f_daily_schedule_hourly_org_index()
        ][1]
        >= 120
    ):
        end_hour = (
            start_hour
            + p.meta_info["f_daily_schedule_hourly_org"][
                p.get_f_daily_schedule_hourly_org_index()
            ][1]
            / 60
        )

    elif (
        p.meta_info["f_daily_schedule_hourly_org"][
            p.get_f_daily_schedule_hourly_org_index()
        ][1]
        + p.meta_info["f_daily_schedule_hourly_org"][
            p.get_f_daily_schedule_hourly_org_index() + 1
        ][1]
    ):
        end_hour = start_hour + (
            (
                p.meta_info["f_daily_schedule_hourly_org"][
                    p.get_f_daily_schedule_hourly_org_index()
                ][1]
                + p.meta_info["f_daily_schedule_hourly_org"][
                    p.get_f_daily_schedule_hourly_org_index() + 1
                ][1]
            )
            / 60
        )

    else:
        end_hour = start_hour + 2
    end_hour = int(end_hour)

    dur_sum = 0
    count = 0
    start_index = None
    end_index = None
    for act, dur in p.meta_info["f_daily_schedule"]:
        if dur_sum >= start_hour * 60 and start_index == None:
            start_index = count
        if dur_sum >= end_hour * 60 and end_index == None:
            end_index = count
        dur_sum += dur
        count += 1

    ret = generate_new_decomp_schedule(
        p, inserted_act, inserted_act_dur, start_hour, end_hour
    )
    p.meta_info["f_daily_schedule"][start_index:end_index] = ret
    p.add_new_action(
        act_address,
        inserted_act_dur,
        inserted_act,
        act_pronunciatio,
        act_event,
        chatting_with,
        chat,
        chatting_with_buffer,
        chatting_end_time,
        act_obj_description,
        act_obj_pronunciatio,
        act_obj_event,
        act_start_time,
    )


def _chat_react(env, persona, focused_event, reaction_mode, personas):
    init_persona = persona
    target_persona = personas[reaction_mode[9:].strip()]
    # curr_personas = [init_persona, target_persona]
    # TODO can change generation here to make better system performance
    convo, duration_min = generate_convo(env, init_persona, target_persona,init_persona.step)
    convo_summary = generate_convo_summary(init_persona, convo,init_persona.step)
    inserted_act = convo_summary
    inserted_act_dur = duration_min
    act_start_time = target_persona.meta_info["act_start_time"]
    curr_time = target_persona.get_curr_time(string_format = False)
    if curr_time.second != 0:
        temp_curr_time = curr_time + datetime.timedelta(seconds=60 - curr_time.second)
        chatting_end_time = temp_curr_time + datetime.timedelta(
            minutes=inserted_act_dur
        )
    else:
        chatting_end_time = curr_time + datetime.timedelta(minutes=inserted_act_dur)
    for role, p in [("init", init_persona), ("target", target_persona)]:
        if role == "init":
            act_address = f"<persona> {target_persona.name}"
            act_event = (p.name, "chat with", target_persona.name)
            chatting_with = target_persona.name
            chatting_with_buffer = {}
            chatting_with_buffer[target_persona.name] = 800
        elif role == "target":
            act_address = f"<persona> {init_persona.name}"
            act_event = (p.name, "chat with", init_persona.name)
            chatting_with = init_persona.name
            chatting_with_buffer = {}
            chatting_with_buffer[init_persona.name] = 800
        act_pronunciatio = "💬"
        act_obj_description = None
        act_obj_pronunciatio = None
        act_obj_event = (None, None, None)

        _create_react(
            p,
            inserted_act,
            inserted_act_dur,
            act_address,
            act_event,
            chatting_with,
            convo,
            chatting_with_buffer,
            chatting_end_time,
            act_pronunciatio,
            act_obj_description,
            act_obj_pronunciatio,
            act_obj_event,
            act_start_time,
        )


def _wait_react(persona, reaction_mode,env):
    p = persona

    inserted_act = f'waiting to start {p.meta_info["act_description"].split("(")[-1][:-1]}'
    end_time = datetime.datetime.strptime(
        reaction_mode[6:].strip(), "%B %d, %Y, %H:%M:%S"
    )
    inserted_act_dur = (
        (end_time.minute + end_time.hour * 60)
        - (p.get_curr_time(string_format = False).minute + p.get_curr_time(string_format = False).hour * 60)
        + 1
    )

    states = env.db.hgetall(f"persona:{persona.name}")
    x,y = states["x"],states["y"]
    act_address = f"<waiting> {x} {y}"
    act_event = (
        p.name,
        "waiting to start",
        p.meta_info["act_description"].split("(")[-1][:-1],
    )
    chatting_with = None
    chat = None
    chatting_with_buffer = None
    chatting_end_time = None

    act_pronunciatio = "⌛"
    act_obj_description = None
    act_obj_pronunciatio = None
    act_obj_event = (None, None, None)

    _create_react(
        p,
        inserted_act,
        inserted_act_dur,
        act_address,
        act_event,
        chatting_with,
        chat,
        chatting_with_buffer,
        chatting_end_time,
        act_pronunciatio,
        act_obj_description,
        act_obj_pronunciatio,
        act_obj_event,
    )


def generative_plan(persona, env, personas, new_day, retrieved, debug = False):
    # PART 1: Generate the hourly schedule.
    
    if new_day:
        _long_term_planning(persona, new_day,env)
    # PART 2: If the current action has expired, we want to create a new plan.
    if persona.act_check_finished():
        _determine_action(persona, env)
    # PART 3: If you perceived an event that needs to be responded to (saw
    # another persona), and retrieved relevant information.
    # Step 1: Retrieved may have multiple events represented in it. The first
    #         job here is to determine which of the events we want to focus
    #         on for the persona.
    #         <focused_event> takes the form of a dictionary like this:
    #         dictionary {["curr_event"] = <ConceptNode>,
    #                     ["events"] = [<ConceptNode>, ...],
    #                     ["thoughts"] = [<ConceptNode>, ...]}
    focused_event = False
    #### TODO here is a big bug, if retrieved just choose one event, and this is 
    #### not about conflict persona, then they might do things together. 
    if retrieved.keys():
        #### Warning have not been here
        focused_event = _choose_retrieved(persona, retrieved)
        
    # Step 2: Once we choose an event, we need to determine whether the
    #         persona will take any actions for the perceived event. There are
    #         three possible modes of reaction returned by _should_react.
    #         a) "chat with {target_persona.name}"
    #         b) "react"
    #         c) False     
    if focused_event:
        reaction_mode = _should_react(persona, focused_event, personas)
        if reaction_mode:
            # If we do want to chat, then we generate conversation
            # if reaction_mode[:9] == "chat with":
            if "chat with" in reaction_mode:
                _chat_react(env, persona, focused_event, reaction_mode, personas)
            # elif reaction_mode[:4] == "wait":
            elif "wait" in reaction_mode:
                _wait_react(persona, reaction_mode,env)
    # Step 3: Chat-related state clean up.
    # If the persona is not chatting with anyone, we clean up any of the
    # chat-related states here.
    if persona.meta_info["act_event"][1] != "chat with":
        persona.meta_info["chatting_with"] = None
        persona.meta_info["chat"] = None
        persona.meta_info["chatting_end_time"] = None
    # We want to make sure that the persona does not keep conversing with each
    # other in an infinite loop. So, chatting_with_buffer maintains a form of
    # buffer that makes the persona wait from talking to the same target
    # immediately after chatting once. We keep track of the buffer value here.
    curr_persona_chat_buffer = persona.meta_info["chatting_with_buffer"]
    for persona_name, buffer_count in curr_persona_chat_buffer.items():
        if persona_name != persona.meta_info["chatting_with"]:
            persona.meta_info["chatting_with_buffer"][persona_name] -= 1
    
    ### new decision new plan
    if persona.meta_info["act_address"] != persona.meta_info["previous_plan"]:
        persona.meta_info["previous_plan"] = persona.meta_info["act_address"]
        persona.meta_info["act_path_set"] = False
        print("name",persona.name,"step",persona.step)
        print("meta_info")
        print(persona.meta_info)
    print(persona.meta_info["act_address"],persona.from_step_to_time(persona.step))
    return persona.meta_info["act_address"]
