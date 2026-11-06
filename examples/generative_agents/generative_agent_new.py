from aimetropolis import Action, Agent, Env
from generative_memory_new import GenerativeMemory, GenerativeEventMemoryNode
import json
import pickle
import datetime
from perceive import generative_perceive
from retrieve import generative_retrieve
from plan import generative_plan
from execute import generative_execute
from aimetropolis.action import AgentMove
class GenerativeAgent(Agent):
    def __init__(self, name: str, step: int, env: Env):
        super().__init__(name, step, env)
        self.memory = GenerativeMemory(name)
        self.meta_info = json.loads(self.memory.db.get(f"{name}:meta_info"))

        self.step = step
        self.retention = int(self.meta_info["retention"])
        self.embeddings = self.get_embeddings()
        self.action_lock = False
        #### might need to fix
        self.start_time = datetime.datetime.strptime("2024-03-01 00:00:00", "%Y-%m-%d %H:%M:%S")
        #### TODO change to second perstep
        self.sec_per_step = datetime.timedelta(seconds=env.sec_per_step)
        if "act_event" not in self.meta_info:
            self.meta_info["act_event"] = [self.name, "is", "idle"]
        if "act_description" not in self.meta_info:
            self.meta_info["act_description"] = None
        if "chat" not in self.meta_info:
            self.meta_info["chat"] = None
        if "act_address" not in self.meta_info:
            self.meta_info["act_address"] = None
        if "act_start_step" not in self.meta_info:
            self.meta_info["act_start_time"] = 0
        if "act_duration" not in self.meta_info:
            self.meta_info["act_duration"] = 0
        if "importance_trigger_curr" not in self.meta_info:
            self.meta_info["importance_trigger_curr"] = 64
        if "importance_ele_n" not in self.meta_info:
            self.meta_info["importance_ele_n"] = 0
        if "recency_decay" not in self.meta_info:
            self.meta_info["recency_decay"] = 0.99
        if "chatting_with_buffer" not in self.meta_info:
            self.meta_info["chatting_with_buffer"] = dict()
        if "chatting_with" not in self.meta_info:
            self.meta_info["chatting_with"] = None
        if "planned_path" not in self.meta_info:
            self.meta_info["planned_path"] = []
        #### TODO need to change here
        if "f_daily_schedule" not in self.meta_info:
            self.meta_info["f_daily_schedule"] = [["sleep",60] for i in range(24)]
        if "act_start_time" not in self.meta_info:
            self.meta_info["act_start_time"] = 0
        if"previous_plan" not in self.meta_info:
            self.meta_info["previous_plan"] = None
        if "obj_set" not in self.meta_info:
            self.meta_info["obj_set"] = False
    def get_daily_schedule_idx(self,advance = 0):
        currtime = self.start_time + self.step * self.sec_per_step
        current_minute = currtime.minute + currtime.hour * 60
        current_minute += advance
        curr_index = 0
        elapsed = 0
        for task, duration in self.meta_info["f_daily_schedule"]:
            elapsed += duration
            if elapsed > current_minute: 
                return curr_index
            curr_index += 1

        return curr_index
    def get_f_daily_schedule_hourly_org_index(self,advance = 0):
        currtime = self.start_time + self.step * self.sec_per_step
        current_minute = currtime.minute + currtime.hour * 60
        current_minute += advance
        curr_index = 0
        elapsed = 0
        for task, duration in self.meta_info["f_daily_schedule_hourly_org"]:
            elapsed += duration
            if elapsed > current_minute: 
                return curr_index
            curr_index += 1

        return curr_index
    def add_new_action(self, 
                     action_address, 
                     action_duration,
                     action_description,
                     action_pronunciatio, 
                     act_event,
                     chatting_with, 
                     chat, 
                     chatting_with_buffer,
                     chatting_end_time,
                     act_obj_description, 
                     act_obj_pronunciatio, 
                     act_obj_event, 
                     act_start_time=None):
        self.meta_info["act_address"] = action_address
        self.meta_info["act_duration"] = action_duration
        self.meta_info["act_description"] = action_description
        self.meta_info["act_pronunciatio"] = action_pronunciatio
        self.meta_info["act_event"] = act_event
        self.meta_info["chatting_with"] = chatting_with
        self.meta_info["chat"] = chat
        if chatting_with_buffer:
            self.meta_info["chatting_with_buffer"].update(chatting_with_buffer)
        self.meta_info["chatting_end_time"] = chatting_end_time
        
        self.meta_info["act_obj_description"] = act_obj_description
        self.meta_info["act_obj_pronunciatio"] = act_obj_pronunciatio
        self.meta_info["act_obj_event"] = act_obj_event
        self.meta_info["act_start_time"] = self.get_curr_time(string_format=False)
        self.meta_info["act_start_step"] = self.step
        self.meta_info["act_path_set"] = False
            
        
        
        
        
        
    def act_check_finished(self):
        if self.meta_info["act_address"] is None:
            return True
        if self.meta_info["act_start_step"] + self.meta_info["act_duration"] < self.step:
            return True
        else:
            return False
    def from_step_to_time(self, step):
        return self.start_time + step * self.sec_per_step 
    def get_embeddings(self):
        key_pattern = f"metadata:{self.name}:embeddings"
        retrieved_binary_embeddings = self.memory.hgetall(key_pattern)
        retrieved_data = {}
        for key, value in retrieved_binary_embeddings:
            retrieved_data[key] = pickle.loads(value)
        return retrieved_data
    def smem_add(self,event):
        # print("add_smem",event.subject, event.predicate, event.object,event.location)
        self.memory.add_smem(event.subject, event.predicate, event.object,event.location)
    def get_location_arena_smem(self,sector):
        smem_list = self.memory.get_all_smem()
        ret_list = []
        for smem_event in smem_list:
            if sector in smem_event.location:
                if smem_event.location.split(":")[2] not in ret_list:
                    ret_list.append(smem_event.location.split(":")[2])
        if len(ret_list) > 0:
            return ret_list
        return ""
    def get_location_sector_smem(self):
        smem_list = self.memory.get_all_smem()
        ret_list = []
        for smem_event in smem_list:
            if smem_event.location.split(":")[1] not in ret_list:
                ret_list.append(smem_event.location.split(":")[1])
        if len(ret_list) > 0:
            return ret_list
        return ""
    def get_location_obj_smem(self,sector,arena):
        smem_list = self.memory.get_all_smem()
        ret_list = []
        for smem_event in smem_list:
            if sector in smem_event.location and arena in smem_event.location:
                if smem_event.sub not in ret_list:
                    ret_list.append(smem_event.sub)
        if len(ret_list) > 0:
            return ret_list
        return ""
    def amem_add(self, diction,event_type):
        embedding_pair = diction["embedding_pair"]
        diction["embedding_key"] = embedding_pair[0]
        self.embeddings[embedding_pair[0]] = embedding_pair[1]

        memory_node = self.memory.add_amem(diction,event_type)
        return memory_node
    def get_summarized_latest_event_amem(self, retention):
        return self.memory.get_summarized_latest_events_amem(retention)

    def a_mem_retrieve_events(self, s_content, p_content, o_content):
        ret = []
        key_pattern = f"associative:{self.name}:event:"
        #### HERE
        for event_id in range(1, self.memory.event_counter + 1):
            event = self.memory.get_event(f"{key_pattern}{event_id}")
            if (
                event.subject == s_content
                or event.object == o_content
                or event.predicate == p_content
            ):
                ret.append(event)

        return ret
    def a_mem_retrieve_thoughts(self, s_content, p_content, o_content):
        ret = []
        key_pattern = f"associative:{self.name}:thought:"
        for thought_id in range(1, self.memory.thought_counter + 1):
            thought = self.memory.get_event(f"{key_pattern}{thought_id}")
            if (
                thought.subject == s_content
                or thought.object == o_content
                or thought.predicate == p_content
            ):
                ret.append(thought)

        return ret
    def a_mem_get_all_thoughts(self):
        ret = []
        key_pattern = f"associative:{self.name}:thought:"
        for thought_id in range(1, self.memory.thought_counter + 1):
            thought = self.memory.get_event(f"{key_pattern}{thought_id}")
            ret.append(thought)

        return ret
    def a_mem_get_all_events(self):
        ret = []
        key_pattern = f"associative:{self.name}:event:"
        for event_id in range(1, self.memory.event_counter + 1):
            event = self.memory.get_event(f"{key_pattern}{event_id}")
            ret.append(event)

        return ret
    def get_str_iss(self):
        commonset = ""
        commonset += f"Name: {self.name}\n"
        curr_time = str(self.start_time + self.step * self.sec_per_step)
        
        age = self.meta_info["age"]
        innate = self.meta_info["innate"]
        learned = self.meta_info["learned"]
        currently = self.meta_info["currently"]
        lifestyle = self.meta_info["lifestyle"]
        daily_plan_req = self.meta_info["daily_plan_req"]
        commonset += f"Age: {age}\n"
        commonset += f"Innate traits: {innate}\n"
        commonset += f"Learned traits: {learned}\n"
        commonset += f"Currently: {currently}\n"
        commonset += f"Lifestyle: {lifestyle}\n"
        commonset += f"Daily plan requirement: {daily_plan_req}\n"
        commonset += f"Current Date: {curr_time}\n"
        return commonset
    def get_curr_time(self,string_format):
        
        currtime = self.start_time + self.step * self.sec_per_step
        
        if string_format:
            currtime = currtime.strftime(string_format)
            return str(currtime)
        else:
            return currtime
    def get_curr_date(self):
        currtime = self.start_time + self.step * self.sec_per_step
        return currtime.strftime("%Y-%m-%d")
    def get_full_curr_time(self):
        currtime = self.start_time + self.step * self.sec_per_step
        currtime = currtime
        return currtime
    def perceive(self, debug = False):
        return generative_perceive(persona = self,env = self.env,debug = debug)

    def retrieve(self, perceived, debug = False):
        return generative_retrieve(persona = self,perceived=perceived,debug = debug)
    def plan(self, persona_dict, new_day, retrieved, debug = False):
        return generative_plan(persona = self,env = self.env, personas = persona_dict, new_day = new_day, retrieved = retrieved, debug = debug)
    # def execute(self, env, planned):
    #     current_position = self.env.get_persona_position(self.name)
    #     next_positions = [
    #         (current_position[0] + m[0], current_position[1] + m[1]) for m in [(0, 0), (0, 1), (1, 0), (0, -1), (-1, 0)]
    #     ]
    #     record_key = f"recorded_movement:{self.name}:{self.step+1}"
    #     next_x = self.env.db.hget(record_key, "x")
    #     next_y = self.env.db.hget(record_key, "y")
    #     next_position = (int(next_x), int(next_y))
    #     assert (next_position in next_positions)

    #     return AgentMove(self.step + 1, self.name, next_position)
    def execute(self, env, planned):
        return generative_execute(persona = self,env = env, plan = planned)
    def proceed(self, persona_dict,new_day,debug = False):
        perceived = self.perceive(debug = debug)
        retrieved = self.retrieve(perceived,debug = debug)
        planned = self.plan(persona_dict, new_day, retrieved, debug = debug)
        action = self.execute(self.env,planned)
        
        return action
    def get_last_chat(self,name = None):
        if name is None:
            key = f"associative:{self.name}:chat:{self.memory.chat_counter - 1}"
            last_chat_event = self.memory.get_event(key)
            if last_chat_event is not None:
                return last_chat_event
            else:
                return None
        else:
            key_pattern = f"associative:{self.name}:chat:"
            for chat_id in range(self.memory.chat_counter, 0, -1):
                chat = self.memory.get_event(f"{key_pattern}{chat_id}")
                if chat.object == name:
                    return chat
            return None
    def get_related_last_chat(self, target_persona_name,limit_minute):
        key_pattern = f"associative:{self.name}:chat:"
        curr_step = self.step
        for chat_id in range(self.memory.chat_counter, 0, -1):
            chat = self.memory.get_event(f"{key_pattern}{chat_id}")
            if chat.object == target_persona_name:
                created_step = chat.created
                minute_per_step = self.env.sec_per_step / 60
                if (curr_step - created_step) * minute_per_step < limit_minute:
                    return chat
        return None
    def get_date(self):
        curr_time = self.start_time + self.step * self.sec_per_step
        return curr_time.replace(hour=0, minute=0, second=0, microsecond=0)
        

