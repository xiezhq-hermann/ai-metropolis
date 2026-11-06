import datetime
def reflection_trigger(persona):
    """
    Given the current persona, determine whether the persona should run a 
    reflection. 
    
    Our current implementation checks for whether the sum of the new importance
    measure has reached the set (hyper-parameter) threshold.

    INPUT: 
        persona: Current Persona object
    Output: 
        True if we are running a new reflection. 
        False otherwise. 
    """
    print (persona.name, "persona.scratch.importance_trigger_curr::", persona.scratch.importance_trigger_curr)
    print (persona.scratch.importance_trigger_max)

    if (persona.scratch.importance_trigger_curr <= 0 and 
        0 != persona.event_count + persona.thought_count): 
        return True 
    return False

def reset_reflection_counter(persona): 
  """
  We reset the counters used for the reflection trigger. 

  INPUT: 
    persona: Current Persona object
  Output: 
    None
  """
  persona_imt_max = persona.scratch.importance_trigger_max
  persona.scratch.importance_trigger_curr = persona_imt_max
  persona.scratch.importance_ele_n = 0

def run_reflect(persona):
    """
    Run the actual reflection. We generate the focal points, retrieve any 
    relevant nodes, and generate thoughts and insights. 

    INPUT: 
        persona: Current Persona object
    Output: 
        None
    """
def reflect(persona):
    if reflection_trigger(persona): 
        run_reflect(persona)
        reset_reflection_counter(persona)
    if persona.scratch.chatting_end_time: 
        if persona.scratch.curr_time + datetime.timedelta(0,10) == persona.scratch.chatting_end_time:
            all_utt = "" 
            if persona.scratch.chat:
                for row in persona.scratch.chat:  
                    all_utt += f"{row[0]}: {row[1]}\n"
        
            evidence = [persona.a_mem_get_last_chat(persona.scratch.chatting_with).node_id]
            #### TODO write openai api
            planning_thought = generate_planning_thought_on_convo(persona, all_utt)
            planning_thought = f"For {persona.scratch.name}'s planning: {planning_thought}"
            created = persona.scratch.curr_time
            expiration = persona.scratch.curr_time + datetime.timedelta(days=30)
            s, p, o = generate_action_event_triple(planning_thought, persona)
            keywords = set([s, p, o])
            thought_poignancy = generate_poig_score(persona, "thought", planning_thought)
            thought_embedding_pair = (planning_thought, get_embedding(planning_thought))
            persona.a_mem.add_thought(created, expiration, s, p, o, 
                                planning_thought, keywords, thought_poignancy, 
                                thought_embedding_pair, evidence)
            
            memo_thought = generate_memo_on_convo(persona, all_utt)
            memo_thought = f"{persona.scratch.name} {memo_thought}"
            created = persona.scratch.curr_time
            expiration = persona.scratch.curr_time + datetime.timedelta(days=30)
            s, p, o = generate_action_event_triple(memo_thought, persona)
            keywords = set([s, p, o])
            thought_poignancy = generate_poig_score(persona, "thought", memo_thought)
            thought_embedding_pair = (memo_thought, get_embedding(memo_thought))
            persona.a_mem_add(created, expiration, s, p, o, location,
                                memo_thought, keywords, thought_poignancy, 
                                thought_embedding_pair, evidence,"thought")
