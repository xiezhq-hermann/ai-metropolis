from typing import List

from numpy import dot
from numpy.linalg import norm
import sys

sys.path.append("../")
from agent_functions import *


def normalize_dict_floats(d, target_min, target_max):
    """
    This function normalizes the float values of a given dictionary 'd' between
    a target minimum and maximum value. The normalization is done by scaling the
    values to the target range while maintaining the same relative proportions
    between the original values.

    INPUT:
      d: Dictionary. The input dictionary whose float values need to be
         normalized.
      target_min: Integer or float. The minimum value to which the original
                  values should be scaled.
      target_max: Integer or float. The maximum value to which the original
                  values should be scaled.
    OUTPUT:
      d: A new dictionary with the same keys as the input but with the float
         values normalized between the target_min and target_max.

    Example input:
      d = {'a':1.2,'b':3.4,'c':5.6,'d':7.8}
      target_min = -5
      target_max = 5
    """
    min_val = min(val for val in d.values())
    max_val = max(val for val in d.values())
    range_val = max_val - min_val

    if range_val == 0:
        for key, val in d.items():
            d[key] = (target_max - target_min) / 2
    else:
        for key, val in d.items():
            d[key] = (val - min_val) * (
                target_max - target_min
            ) / range_val + target_min
    return d


def extract_recency(persona, nodes):
    """
    Gets the current Persona object and a list of nodes that are in a
    chronological order, and outputs a dictionary that has the recency score
    calculated.

    INPUT:
      persona: Current persona whose memory we are retrieving.
      nodes: A list of Node object in a chronological order.
    OUTPUT:
      recency_out: A dictionary whose keys are the node.node_id and whose values
                   are the float that represents the recency score.
    """
    recency_vals = [
        persona.meta_info["recency_decay"]**i for i in range(1, len(nodes) + 1)
    ]

    recency_out = dict()
    for count, node in enumerate(nodes):
        recency_out[node.key_id] = recency_vals[count]

    return recency_out


def extract_importance(persona, nodes):
    """
    Gets the current Persona object and a list of nodes that are in a
    chronological order, and outputs a dictionary that has the importance score
    calculated.

    INPUT:
      persona: Current persona whose memory we are retrieving.
      nodes: A list of Node object in a chronological order.
    OUTPUT:
      importance_out: A dictionary whose keys are the node.node_id and whose
                      values are the float that represents the importance score.
    """
    importance_out = dict()
    for count, node in enumerate(nodes):
        importance_out[node.key_id] = node.poignancy

    return importance_out


def cos_sim(a, b):
    """
    This function calculates the cosine similarity between two input vectors
    'a' and 'b'. Cosine similarity is a measure of similarity between two
    non-zero vectors of an inner product space that measures the cosine
    of the angle between them.

    INPUT:
      a: 1-D array object
      b: 1-D array object
    OUTPUT:
      A scalar value representing the cosine similarity between the input
      vectors 'a' and 'b'.

    Example input:
      a = [0.3, 0.2, 0.5]
      b = [0.2, 0.2, 0.5]
    """
    return dot(a, b) / (norm(a) * norm(b))


def extract_relevance(persona, nodes, focal_pt):
    """
    Gets the current Persona object, a list of nodes that are in a
    chronological order, and the focal_pt string and outputs a dictionary
    that has the relevance score calculated.

    INPUT:
        persona: Current persona whose memory we are retrieving.
        nodes: A list of Node object in a chronological order.
        focal_pt: A string describing the current thought of revent of focus.
    OUTPUT:
        relevance_out: A dictionary whose keys are the node.node_id and whose values
                    are the float that represents the relevance score.
    """
    focal_embedding = get_embedding(focal_pt)

    relevance_out = dict()
    for count, node in enumerate(nodes):
        #### Warning need to store embeddings now!!!
        node_embedding = persona.embeddings[node.embedding_key]
        relevance_out[node.node_id] = cos_sim(node_embedding, focal_embedding)

    return relevance_out


def top_highest_x_values(d, x):
    """
    This function takes a dictionary 'd' and an integer 'x' as input, and
    returns a new dictionary containing the top 'x' key-value pairs from the
    input dictionary 'd' with the highest values.

    INPUT:
      d: Dictionary. The input dictionary from which the top 'x' key-value pairs
         with the highest values are to be extracted.
      x: Integer. The number of top key-value pairs with the highest values to
         be extracted from the input dictionary.
    OUTPUT:
      A new dictionary containing the top 'x' key-value pairs from the input
      dictionary 'd' with the highest values.

    Example input:
      d = {'a':1.2,'b':3.4,'c':5.6,'d':7.8}
      x = 3
    """
    top_v = dict(sorted(d.items(), key=lambda item: item[1], reverse=True)[:x])
    return top_v


def generative_retrieve(persona, perceived,debug):
    """
    This function takes the events that are perceived by the persona as input
    and returns a set of related events and thoughts that the persona would
    need to consider as context when planning.

    INPUT:
    perceived: a list of event <ConceptNode>s that represent any of the events
    `         that are happening around the persona. What is included in here
                are controlled by the att_bandwidth and retention
                hyper-parameters.
    OUTPUT:
    retrieved: a dictionary of dictionary. The first layer specifies an event,
                while the latter layer specifies the "curr_event", "events",
                and "thoughts" that are relevant.
    """
    retrieved = dict()
    if len(perceived) == 0:
        return retrieved
    for event in perceived:
        retrieved[event.description] = dict()
        retrieved[event.description]["curr_event"] = event
        relevant_events = persona.a_mem_retrieve_events(
            event.subject, event.predicate, event.object
        )
        
        retrieved[event.description]["events"] = list(relevant_events)

        relevant_thoughts = persona.a_mem_retrieve_thoughts(
            event.subject, event.predicate, event.object
        )

        retrieved[event.description]["thoughts"] = list(relevant_thoughts)
    return retrieved


def new_retrieve(persona, focal_points, n_count=30):
    ### used in plan to retrieve events and thoughts happened recently
    retrieved = dict()
    for focal_pt in focal_points:
        thoughts_list = persona.a_mem_get_all_thoughts()
        event_list = persona.a_mem_get_all_events()
        nodes = thoughts_list + event_list
        new_nodes = [i for i in nodes if "idle" not in i.embedding_key]
        if len(new_nodes) == 0:
            continue
        time_sorted_nodes = sorted(new_nodes, key=lambda x: x.last_accessed)
        # Calculating the component dictionaries and normalizing them.
        recency_out = extract_recency(persona, time_sorted_nodes)
        recency_out = normalize_dict_floats(recency_out, 0, 1)
        importance_out = extract_importance(persona, time_sorted_nodes)
        importance_out = normalize_dict_floats(importance_out, 0, 1)
        relevance_out = extract_relevance(persona, time_sorted_nodes, focal_pt)
        relevance_out = normalize_dict_floats(relevance_out, 0, 1)
        #### Warning gw can be learnt from a RL algorithms, how about we ask them??
        gw = [0.5, 3, 2]
        master_out = dict()
        for key in recency_out.keys():
            master_out[key] = (
                persona.scratch.recency_w * gw[0] * recency_out[key]
                + persona.scratch.relevance_w * gw[1] * importance_out[key]
                + persona.scratch.importance_w * gw[2] * relevance_out[key]
            )
            #### Warning need to double check if output is correct

        master_out = top_highest_x_values(master_out, n_count)
        master_nodes = [
            persona.get_event_from_amem(key) for key in list(master_out.keys())
        ]
        #### Warning need to store back to db
        for n in master_nodes:
            n.last_accessed = persona.step
            persona.update_a_mem_with_event(n)
        retrieved[focal_pt] = master_nodes
    return retrieved
