import json

from aimetropolis import Memory, Event, Action
from .ville import ASSEST_PATH


class SimpleMemory(Memory):

    def __init__(self, persona_name: str):
        super().__init__(persona_name)
        # todo: checkpointing
        self.db.set(f"counter:{persona_name}:events:Event", 0)
        self.db.set(f"counter:{persona_name}:events:ChatEvent", 0)

    def init_agent_from_files(self):
        with open(ASSEST_PATH + "personas/n25_iss.json") as f:
            # todo fix the hack for duplication
            meta_info = json.load(f)[self.persona.split("_")[0]]
            self.db.set(f"{self.persona}:meta_info", json.dumps(meta_info))
            if "daily_plan_req" in meta_info:
                self.set_scratch("daily_plan_req", meta_info["daily_plan_req"])
            # if "daily_req" in meta_info:
            #     self.set_scratch("daily_req", meta_info["daily_req"])

    def increment_event_counter(self):
        return self.db.incr(f"counter:{self.persona}:events")

    def put_event_into_memory(self, event: Event, step: int, poigance: int):
        super().put_event_into_memory(event, step, {"poigance": poigance})

    @property
    def daily_plan(self):
        return self.db.get(f"scratch:{self.persona}:daily_plan")

    @daily_plan.setter
    def daily_plan(self, plan):
        self.db.set(f"scratch:{self.persona}:daily_plan", plan)

    @property
    def hourly_schedule(self):
        return self.db.get(f"scratch:{self.persona}:hourly_schedule")

    @hourly_schedule.setter
    def hourly_schedule(self, schedule):
        self.db.set(f"scratch:{self.persona}:hourly_schedule", schedule)

    @property
    def current_action(self):
        return self.db.get(f"scratch:{self.persona}:current_action")

    @current_action.setter
    def current_action(self, action: Action):
        self.db.set(f"scratch:{self.persona}:current_action", action)

    @property
    def action_completion_step(self):
        step = self.db.get(f"scratch:{self.persona}:action_completion_step")
        return int(step) if step else 0

    def set_scratch(self, key, value):
        return super().set_scratch(key, value)

    def get_scratch(self, key):
        return super().get_scratch(key)
