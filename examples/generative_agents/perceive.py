# from llm_utils import *
import sys
from agent_functions import *
sys.path.append("../")
# from agent_functions import *

#### Need to change in future
def generate_poig_score(persona, event_type, description):

    if "is idle" in description:
        return 1

    if event_type == "event":

        return int(generate_event_poig_score(persona.name,persona.get_str_iss(), description, persona.step)[0])
    elif event_type == "chat":
        return int(generate_chat_poig_score(
            persona.name,persona.get_str_iss(), description, persona.step
        ))


def generative_perceive(persona, env,debug = False):
    # return a list of events, currently set raduis to 4
    #### TODO might need to change
    perceived_objs = env.perceive_object_events(persona.name)


    for objs in perceived_objs:
        persona.smem_add(objs)
    perceived_events = env.perceive_persona_events(persona.name)

    ret_events = []
    for event in perceived_events:
        subject, predicate, object, description = (
            event.subject,
            event.predicate,
            event.object,
            event.description,
        )
        
        if not predicate:
            predicate = "is"
            object = "idle"
            description = "idle"
        ## same with old code

        # description = f"{subject.split(':')[-1]} is {description}"
        event.subject, event.predicate, event.object = subject, predicate, object

        # retrive latest events, list of diction
        latest_env = persona.get_summarized_latest_event_amem(persona.meta_info["retention"])
        ### TODO not sure if things would work
        spo_summary_event = (event.subject, event.predicate, event.object)
        if spo_summary_event not in latest_env:
            ### get location
            states = env.db.hgetall(f"persona:{persona.name}")

            location = env.get_location_info(states["x"], states["y"])
            location = str(location)

            ### managing keywords
            keywords = set()
            subect = event.subject
            object = event.object
            if ":" in subect:
                subect = subect.split(":")[-1]
            if ":" in object:
                object = object.split(":")[-1]
            keywords.update([subect, object])

            # Get event embedding

            desc_embedding_in = description
            if "(" in description:
                desc_embedding_in = (
                    desc_embedding_in.split("(")[1].split(")")[0].strip()
                )
            ### TODO I did not store embedding here
            if debug:
                event_poignancy = 2
                event_embedding = [1.3, 1.4, 1.5, 1.6, 1.7]
                event_embedding_pair = (desc_embedding_in, event_embedding)
            else:

                if desc_embedding_in in persona.embeddings:
                    event_embedding = persona.embeddings[desc_embedding_in]
                else:
                    event_embedding = get_embedding(desc_embedding_in)
                event_embedding_pair = (desc_embedding_in, event_embedding)

                event_poignancy = generate_poig_score(persona, "event", desc_embedding_in)
            ### detect self chat

            if subect == f"{persona.name}" and event.predicate == "chat with":
                ## 3 item pair

                curr_event = persona.meta_info["act_event"]

                act_description = persona.meta_info["act_description"]
    
                if persona.meta_info["act_description"] in persona.embeddings:
                    chat_embedding = persona.embeddings[persona.meta_info["act_description"]]
                else:
                    chat_embedding = get_embedding(act_description)
                chat_embedding_pair = (act_description, chat_embedding)

                chat_poignancy = generate_poig_score(persona, "chat", act_description)
                ### Warning did not store chat embedding and need to get the place of persona, currtime -> step
                ### get these from env.db
                # if debug == False:
                #     location = persona.location
                # else:
                #     location = "home"
                
                input_dict = {
                    "created": persona.step,
                    "expiration": None,
                    "subject": curr_event[0],
                    "predicate": curr_event[1],
                    "object": curr_event[2],
                    "location" : location,
                    "description": act_description,
                    "keywords": keywords,
                    "poignancy": chat_poignancy,
                    "embedding_pair" : chat_embedding_pair,
                    "filling": persona.meta_info["chat"],
                }
                chat_node = persona.amem_add(
                    input_dict,
                    "chat",
                )


            input_dict = {
                "created": persona.step,
                "expiration": None,
                "subject": subject,
                "predicate": predicate,
                "object": object,
                "location" : location,
                "description": description,
                "keywords": keywords,
                "poignancy": event_poignancy,
                "embedding_pair": event_embedding_pair,
                "filling": persona.meta_info["chat"],
                "last_accessed": persona.step,
            }

            ret_events += [
                persona.amem_add(
                    input_dict,
                    "event",
                )
            ]
            persona.meta_info["importance_trigger_curr"] -= event_poignancy
            persona.meta_info["importance_ele_n"] += 1

    return ret_events
