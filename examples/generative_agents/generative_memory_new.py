from aimetropolis import Memory
import json
import os
import pickle
from aimetropolis.memory import EventMemoryNode
import pandas as pd
class GenerativeSmemNode(EventMemoryNode):
    def __init__(self,information_dict):
        self.sub = information_dict["sub"]
        self.predicate = information_dict["predicate"]
        self.statues = information_dict["statues"]
        self.location = information_dict["location"]
    def to_json(self):



        return json.dumps(self.__dict__)

class GenerativeEventMemoryNode(EventMemoryNode):
    def __init__(self,information_dict):
        self.key_id = information_dict["key_id"]
        self.event_count = information_dict["event_count"]
        self.type_event_count = information_dict["type_event_count"]
        self.event_type = information_dict["event_type"]
        # self.depth = information_dict["depth"]
        self.created = information_dict["created"]
        self.expiration = information_dict["expiration"]
        self.subject = information_dict["subject"]
        self.predicate = information_dict["predicate"]
        self.object = information_dict["object"]
        self.description = information_dict["description"]
        self.embedding_key = information_dict["embedding_key"]
        self.poignancy = int(information_dict["poignancy"])
        self.keywords = str(information_dict["keywords"])
        self.filling = information_dict["filling"]
        self.location = information_dict["location"]
        self.last_accessed = int(information_dict["last_accessed"])
        if self.last_accessed is None:
            self.last_accessed = self.created
        self.embedding_pair = information_dict["embedding_pair"]
    def to_json(self):
        embedding_pair = self.__dict__.pop("embedding_pair")


        return json.dumps(self.__dict__),embedding_pair
    def spo_summary(self):
        return (self.subject, self.predicate, self.object)
    
def from_dict_to_event(event_dict_list,event_embedding_dict_list):
    ret_list = []
    if len(event_dict_list) == 0:
        return ret_list

    for i, event in enumerate(event_dict_list):
        event_dict = json.loads(event)
        if i >= len(event_embedding_dict_list):
            event_dict["embedding_pair"] = "None"
        else:
            event_dict["embedding_pair"] = event_embedding_dict_list[i]
        memory_node = GenerativeEventMemoryNode(event_dict)
        ret_list.append(
            memory_node
        )
    return ret_list


def read_or_create_file(file_path):
    # Check if file exists
    if os.path.exists(file_path):
        # File exists, so read its contents
        with open(file_path, 'r') as file:
            data = json.load(file)

    else:
        # File doesn't exist, create it with an empty dictionary
        data = {}
        with open(file_path, 'w') as file:
            json.dump(data, file)
    return data



class GenerativeMemory(Memory):
    def __init__(self, personan_name):
        super().__init__(personan_name)
        

    def increment_event_counter(self):
        return self.db.incr(f"counter:{self.persona}:event")
    def increment_thought_counter(self):
        return self.db.incr(f"counter:{self.persona}:thought")
    def increment_chat_counter(self):
        return self.db.incr(f"counter:{self.persona}:chat")
    def increment_obj_counter(self):

        return self.db.incr(f"counter:{self.persona}:obj")
    @property
    def event_counter(self):
        return int(self.db.get(f"counter:{self.persona}:event"))
    @property
    def thought_counter(self):
        return int(self.db.get(f"counter:{self.persona}:thought"))
    @property
    def chat_counter(self):
        return int(self.db.get(f"counter:{self.persona}:chat"))
    @property
    def obj_counter(self):
        return int(self.db.get(f"counter:{self.persona}:obj"))
    @property
    def total_event_count(self):
        return self.event_counter + self.thought_counter + self.chat_counter
    def init_agent_from_files(self):

        persona_iss_path = "assets/personas/new_n25_iss.json"
        directory = f"assets/personas/{self.persona}"
        amem_file = f"{directory}/associative_memory.json"
        smem_file = f"{directory}/spatial_memory.json"
        embedding_file = f"{directory}/embeddings.json"

        with open(persona_iss_path) as f:
            meta_data = json.load(f)[self.persona]
            self.db.set(f"{self.persona}:meta_info", json.dumps(meta_data))
        if not os.path.exists(directory):
            os.makedirs(directory)
        amem_dict = read_or_create_file(amem_file)
        smem_dict = read_or_create_file(smem_file)
        embedding_dict = read_or_create_file(embedding_file)
        if len(embedding_dict) != 0:
            for embedding_key, embedding_pair in embedding_dict:
                self.db.set(embedding_key, json.dumps(embedding_pair))
        if len(smem_dict) != 0: 
            for smem_event_id, smem_event_dict in smem_dict:
                self.db.set(smem_event_id, json.dumps(smem_event_dict))
                self.increment_obj_counter()
        if len(embedding_dict) != 0:
            self.embeddings = {}
            for key in embedding_dict:
                self.embeddings[key] = pickle.dumps(json.loads(embedding_dict[key]))
            self.db.hset(f"metadata:{self.persona}:embeddings",mapping=embedding_dict)

        if len(amem_dict) == 0:
            self.db.set(f"counter:{self.persona}:event", 0)
            self.db.set(f"counter:{self.persona}:thought", 0)
            self.db.set(f"counter:{self.persona}:chat", 0)


        if len(smem_dict) == 0:

            self.db.set(f"counter:{self.persona}:obj", 0)

        for amem_id, amem_dict in amem_dict:
            if "event" in amem_id:
                self.db.set(amem_id, json.dumps(amem_dict))
                self.increment_event_counter()
            elif "thought" in amem_id:
                self.db.set(amem_id, json.dumps(amem_dict))
                self.increment_thought_counter()
            elif "chat" in amem_id:
                self.db.set(amem_id, json.dumps(amem_dict))
                self.increment_chat_counter()
    
    def hgetall(self,key,decode = True):
        if decode:
            return self.db.hgetall(key)
        else:
            return self.db.execute_command("HGETALL", key, NEVER_DECODE = True)
    def mget(self, key_list):
        ret_list = []
        for key in key_list:
            node = self.db.get(key)
            if not node:
                continue
            ret_list.append(node)
        return ret_list
    def mhget(self,key_list):
        ret_list = []
        for key in key_list:
            # NEVER_DECODE to avoid decode the binary data
            node = self.db.execute_command("HGETALL", key, NEVER_DECODE = True)
            if not node:
                continue
            for key, value in node.items():
                node[key] = pickle.loads(value)
            ret_list.append(node)
        return ret_list

    def add_smem(self,sub, predicate, statues,location):
        key = f"smem:{self.persona}:{self.increment_obj_counter()}"

        memory_node = GenerativeSmemNode({"sub":sub,"predicate":predicate,"statues":statues,"location":location})
        # print("add_smem,",key, memory_node.to_json())
        self.db.set(key, memory_node.to_json())
    def get_all_smem(self):
        key_pattern = f"smem:{self.persona}"
        smem_dict_list = [key_pattern+f":{i}" for i in range(1,self.obj_counter+1)]
        ret_list = []
        for smem_dict in smem_dict_list:
            
            dict_smem_event = json.loads(self.db.get(smem_dict))
            # print(dict_smem_event)
            ret_list.append(GenerativeSmemNode(dict_smem_event))
   
        
        return ret_list
    def add_amem(self,event_diction,type):
        if type == "event":
            self.increment_event_counter()
            event_diction["type_event_count"] = self.event_counter
            event_diction["event_type"] = "event"
            event_diction["event_count"] = self.total_event_count

            key_id = f"associative:{self.persona}:event:{str(self.event_counter)}"
            event_diction["key_id"] = key_id
            description = event_diction["description"]
            if "(" in description:
                description = (
                    " ".join(description.split()[:3])
                    + " "
                    + description.split("(")[-1][:-1]
                )
            event_diction["description"] = description
        elif type == "chat":
            self.increment_chat_counter()
            event_diction["type_event_count"] = self.chat_counter
            event_diction["event_type"] = "chat"
            event_diction["event_count"] = self.total_event_count
            key_id = f"associative:{self.persona}:chat:{str(self.chat_counter)}"
            event_diction["key_id"] = key_id
        elif type == "thought":
            self.increment_thought_counter()
            event_diction["type_event_count"] = self.thought_counter
            event_diction["event_type"] = "thought"
            event_diction["event_count"] = self.total_event_count
            key_id = f"associative:{self.persona}:thought:{str(self.thought_counter)}"
            event_diction["key_id"] = key_id
        memory_node = GenerativeEventMemoryNode(event_diction)
        json_dump,embedding_pair = memory_node.to_json()

        self.db.set(key_id, json_dump)
        
        self.db.hset(key_id+":embedding",mapping = {embedding_pair[0]:pickle.dumps(embedding_pair[1])})

        
        return memory_node
    def get_summarized_latest_events_amem(self, retention: int):
        name = self.persona

        
        event_count = self.event_counter
        chat_count = self.chat_counter
        thought_count = self.thought_counter
        total_env_count = event_count + chat_count + thought_count

        event_key_pattern = f"associative:{name}:event"
        chat_key_pattern = f"associative:{name}:chat"
        thought_key_pattern = f"associative:{name}:thought"
        ret_list = []
        # return all events
        if event_count <= retention:
            event_key_pattern_list = [
                event_key_pattern + f":{i}" for i in range(1,event_count+1)
            ]
        else:
            event_key_pattern_list = [
                event_key_pattern + f":{i}"
                for i in range(event_count - retention, event_count+1)
            ]
        event_embedding_key_pattern_list = [
            event_key_pattern + f":embedding:{i}" for i in range(event_count - retention, event_count+1)
        ]
        # chat_key_pattern_list = [chat_key_pattern+f":{i}" for i in range(chat_count)]
        # thought_key_pattern_list = [thought_key_pattern+f":{i}" for i in range(thought_count)]
        if chat_count <= retention:
            chat_key_pattern_list = [
                chat_key_pattern + f":{i}" for i in range(1,chat_count+1)
            ]
        else:
            chat_key_pattern_list = [
                chat_key_pattern + f":{i}"
                for i in range(chat_count - retention, chat_count+1)
            ]
        chat_embedding_key_pattern_list = [
            chat_key_pattern + f":embedding:{i}" for i in range(chat_count - retention, chat_count+1)
        ]
        if thought_count <= retention:
            thought_key_pattern_list = [
                thought_key_pattern + f":{i}" for i in range(1,thought_count+1)
            ]
        else:
            thought_key_pattern_list = [
                thought_key_pattern + f":{i}"
                for i in range(thought_count - retention+1, thought_count+1)
            ]
        thought_embedding_key_pattern_list = [
            thought_key_pattern + f":embedding:{i}" for i in range(thought_count - retention, thought_count+1)
        ]
        event_dict_list = self.mget(event_key_pattern_list)
        chat_dict_list = self.mget(chat_key_pattern_list)
        thought_dict_list = self.mget(thought_key_pattern_list)
        event_embedding_dict_list = self.mhget(event_embedding_key_pattern_list)
        chat_embedding_dict_list = self.mhget(chat_embedding_key_pattern_list)
        thought_embedding_dict_list = self.mhget(thought_embedding_key_pattern_list)
        # print(chat_dict_list)
        # print(thought_dict_list)
        event_dict_list = from_dict_to_event(event_dict_list,event_embedding_dict_list)
        chat_dict_list = from_dict_to_event(chat_dict_list,chat_embedding_dict_list)
        thought_dict_list = from_dict_to_event(thought_dict_list,thought_embedding_dict_list)
        ret_list = event_dict_list + chat_dict_list + thought_dict_list
        ## check if these event need to all returned
        new_ret_set = set()
        for event in ret_list:
            if event.event_count >= total_env_count - retention:
                new_ret_set.add(event.spo_summary())
        return new_ret_set
    
    def get_event(self, key):
        if not self.check_key(key):
            return None
        embedding_key = key + ":embedding"
        event_dict = json.loads(self.db.get(key))

        embedding_dict = self.db.execute_command("HGETALL", embedding_key, NEVER_DECODE = True)

        if embedding_dict is not None:
            for key, value in embedding_dict.items():
                embedding_dict[key] = pickle.loads(value)
        event_dict["embedding_pair"] = embedding_dict
        return GenerativeEventMemoryNode(event_dict)
    # def store_to_file(self):
    #     directory = f"assets/personas/{self.persona}"
    #     amem_file = f"{directory}/associative_memory.json"
    #     smem_file = f"{directory}/spatial_memory.json"
    #     embedding_file = f"{directory}/embeddings.json"

        
