import json
import random

from aimetropolis import Action, Agent
from aimetropolis.action import AgentMove
from aimetropolis.generative_agents_simple import TheVille, SimpleMemory

from aimetropolis.generative_agents_simple.agent_functions import generate_event_poig_score, common_llm_call


class SimpleAgent(Agent):

    def __init__(self, persona_name: str, step: int, env: TheVille):
        super().__init__(persona_name, step, env)
        self.memory = SimpleMemory(persona_name)
        meta_info = json.loads(self.memory.db.get(f"{persona_name}:meta_info"))
        self.age = meta_info["age"]
        self.innate = meta_info["innate"]
        self.learned = meta_info["learned"]
        self.currently = meta_info["currently"]
        self.lifestyle = meta_info["lifestyle"]

        self.daily_plan_req = self.memory.get_scratch("daily_plan_req")
        self.iss = self.get_str_iss()

    def get_str_iss(self):
        """
        ISS stands for "identity stable set." This describes the commonset summary
        of this persona -- basically, the bare minimum description of the persona
        that gets used in almost all prompts that need to call on the persona. 

        INPUT
        None
        OUTPUT
        the identity stable set summary of the persona in a string form.
        EXAMPLE STR OUTPUT
        "Name: Dolores Heitmiller
        Age: 28
        Innate traits: hard-edged, independent, loyal
        Learned traits: Dolores is a painter who wants live quietly and paint 
            while enjoying her everyday life.
        Currently: Dolores is preparing for her first solo show. She mostly 
            works from home.
        Lifestyle: Dolores goes to bed around 11pm, sleeps for 7 hours, eats 
            dinner around 6pm.
        Daily plan requirement: Dolores is planning to stay at home all day and 
            never go out."
        """
        commonset = ""
        commonset += f"Name: {self.name}\n"
        commonset += f"Age: {self.age}\n"
        commonset += f"Innate traits: {self.innate}\n"
        commonset += f"Learned traits: {self.learned}\n"
        commonset += f"Currently: {self.currently}\n"
        commonset += f"Lifestyle: {self.lifestyle}\n"
        commonset += f"Daily plan requirement: {self.daily_plan_req}\n"
        commonset += f"Current Date: {self.get_time()}\n"
        return commonset

    def process_perceived_events(self, perceived_events):
        latest_events_memory = self.memory.get_latest_events_memory()
        for event in perceived_events:
            if event in latest_events_memory:
                continue
            event_poigance = 1
            self.memory.put_event_into_memory(event, self.step, event_poigance)

    def retrieve_memory(self, events):
        # todo: retrieve RELEVANT events and thoughts
        return self.memory.get_latest_events_memory()

    def generate_wake_up_hour(self):
        # todo: connect to LLM API
        return 6

    def generate_daily_plan(self, wake_up_hour: int):
        return ""

    def generate_hourly_schedule(self, wake_up_hour: int):
        return ""

    def start_new_daily_plan(self):
        wake_up_hour = self.generate_wake_up_hour()
        self.memory.daily_plan = self.generate_daily_plan(wake_up_hour)
        self.memory.hourly_schedule = self.generate_daily_plan(wake_up_hour)
        return

    def determine_action(self):
        current_position = self.env.get_persona_position(self.name)
        next_position = [
            (current_position[0] + m[0], current_position[1] + m[1]) for m in [(0, 1), (1, 0), (0, -1), (-1, 0)]
        ]
        valid_next_position = [p for p in next_position if self.env.tile_passable(*p)]

        return AgentMove(self.step + 1, self.name, random.choice(valid_next_position))

    def determine_action_replay(self):
        recorded_calls = self.env.db.get(f"recorded_calls:{self.name}:{self.step}")
        if recorded_calls:
            recorded_calls = json.loads(recorded_calls)
            for c in recorded_calls:
                common_llm_call(self.name,
                                self.step,
                                c["prompt"],
                                c["max_tokens"],
                                c["stop"],
                                ignore_eos=c["ignore_eos"] if "ignore_eos" in c else False,
                                trace_label=c["func_name"] if "func_name" in c else None)

        record_key = f"recorded_movement:{self.name}:{self.step+1}"
        next_x = self.env.db.hget(record_key, "x")
        next_y = self.env.db.hget(record_key, "y")
        next_position = (int(next_x), int(next_y))

        return AgentMove(self.step + 1, self.name, next_position)

    def should_react(self, events) -> bool:
        return False

    def plan(self, events):
        if self.step % (24 * 3600 / self.env.sec_per_step) == 0:
            self.start_new_daily_plan()

        if self.should_react(events):
            pass

        if self.memory.action_completion_step > self.step:
            return self.memory.current_action
        else:
            return self.determine_action_replay()

    def proceed(self) -> Action:
        perceived_events = self.perceive()
        self.process_perceived_events(perceived_events)
        retrieved_memory = self.retrieve_memory(perceived_events)
        action = self.plan(retrieved_memory)
        return action
