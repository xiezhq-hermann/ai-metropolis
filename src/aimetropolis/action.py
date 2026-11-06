import json
import time
import redis
from typing import Tuple, List


class Action:

    def __init__(self, step: int, persona: str, description: str):
        self.step = step
        self.persona = persona
        self.description = description

        self.effective_time = 0
        self.cluster_action_counter = 0

    def to_json(self) -> str:
        return json.dumps({
            "type": self.__class__.__name__,
            "step": self.step,
            "persona": self.persona,
            "description": self.description,
            "effective_time": self.effective_time,
            "cluster_action_counter": self.cluster_action_counter
        })

    def apply(self, env, cluster_action_counter: int = 0):
        env.db.hset(f"persona:{self.persona}", "step", self.step)
        env.db.hset(f"persona:{self.persona}", "action", self.description)
        # env.update_persona_status(self.persona, "idle")

        self.effective_time = time.time()
        self.cluster_action_counter = cluster_action_counter

        # for each action applied, we save this action log into the database for future replay
        env.db.set(f"action:{self.persona}:{self.step}:{env.base_step}", self.to_json())

    def __str__(self) -> str:
        return f"At {self.step}, {self.persona} was {self.description}"

    @staticmethod
    def action_resolver(actions: List["Action"]) -> List["Action"]:
        # todo: resolve actions conflict
        # faithfully apply all actions for now
        return actions

    @staticmethod
    def apply_actions(env, actions: List["Action"]):
        resolved_actions = Action.action_resolver(actions)
        cluster_action_counter = env.db.incr("counter:cluster_action_counter")
        for a in resolved_actions:
            a.apply(env, cluster_action_counter)
        return


class AgentMove(Action):

    def __init__(self, step: int, persona: str, movement: Tuple[int, int]):
        self.movement = movement
        super().__init__(step, persona, f"going to ({self.movement})")

    def to_json(self) -> str:
        return json.dumps({
            "type": self.__class__.__name__,
            "step": self.step,
            "persona": self.persona,
            "movement": self.movement,
            "effective_time": self.effective_time,
            "cluster_action_counter": self.cluster_action_counter
        })

    def apply(self, env, cluster_action_counter: int = 0):
        x, y = env.get_persona_position(self.persona)
        old_grid_key = f"grid:{x}:{y}"
        new_x, new_y = self.movement
        new_grid_key = f"grid:{new_x}:{new_y}"

        # transactional update on the original grid
        while True:
            try:
                with env.db.pipeline() as pipe:
                    pipe.watch(old_grid_key)
                    personas = pipe.hget(old_grid_key, "personas").split(":")
                    assert self.persona in personas
                    personas.remove(self.persona)
                    # print("remaining personas", personas)
                    pipe.multi()
                    if len(personas) == 0:
                        pipe.hdel(old_grid_key, "personas")
                    else:
                        pipe.hset(old_grid_key, "personas", ":".join(personas))
                    pipe.execute()
                    break
            except redis.exceptions.WatchError:
                continue

        env.db.hset(f"persona:{self.persona}", "x", new_x)
        env.db.hset(f"persona:{self.persona}", "y", new_y)

        # transactional update on the new grid
        while True:
            try:
                with env.db.pipeline() as pipe:
                    pipe.watch(new_grid_key)
                    personas = pipe.hget(new_grid_key, "personas") or b""
                    personas = personas.split(":") if personas else []
                    personas.append(self.persona)
                    pipe.multi()
                    pipe.hset(new_grid_key, mapping={"personas": ":".join(personas)})
                    pipe.execute()
                    break
            except redis.exceptions.WatchError:
                continue

        return super().apply(env, cluster_action_counter)


class AgentChat(Action):

    def __init__(self, step: int, persona: str, target_persona: str):
        super().__init__(step, persona, f"chating with {target_persona}")
        self.target_persona = target_persona

    def to_json(self) -> str:
        return json.dumps({
            "type": self.__class__.__name__,
            "step": self.step,
            "persona": self.persona,
            "target_persona": self.target_persona,
            "effective_time": self.effective_time,
            "cluster_action_counter": self.cluster_action_counter
        })

    def apply(self, env, cluster_action_counter: int = 0):
        return super().apply(env, cluster_action_counter)


class ChangeObjectStatus(Action):

    def __init__(self, step: int, persona: str, object: str, new_state: str):
        super().__init__(step, persona, f"interacting with {object}")
        self.object = object
        self.new_state = new_state

    def to_json(self) -> str:
        return json.dumps({
            "type": self.__class__.__name__,
            "step": self.step,
            "persona": self.persona,
            "object": self.object,
            "new_state": self.new_state,
            "effective_time": self.effective_time,
            "cluster_action_counter": self.cluster_action_counter
        })

    def apply(self, env, cluster_action_counter: int = 0):
        env.db.hset(f"object:{self.object}", "status", self.new_state)
        return super().apply(env, cluster_action_counter)
