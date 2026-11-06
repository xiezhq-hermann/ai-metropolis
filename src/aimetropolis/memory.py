import json
import redis
from aimetropolis import Event


class EventMemoryNode:

    def __init__(self, event: Event, step: int, extra_attributes: dict):
        self.subject = event.subject
        self.predicate = event.predicate
        self.object = event.object
        self.location = event.location
        self.description = event.description
        self.step = step
        self.type = event.__class__.__name__
        self.extra_attributes = extra_attributes

    def to_json(self):
        return json.dumps(self.__dict__)

    def event_str(self):
        return f"Event({self.subject}, {self.predicate}, {self.object}, {self.location}, {self.description})"

    def __str__(self) -> str:
        return f"EventMemoryNode({self.subject}, {self.predicate}, {self.object}, {self.location}, {self.description}, {self.step}, {self.type}, {self.extra_attributes})"

    def __eq__(self, other) -> bool:
        if isinstance(other, EventMemoryNode):
            return str(self) == str(other)
        elif isinstance(other, Event):
            return self.event_str() == str(other)
        else:
            return False


class Memory:

    def __init__(self, persona_name: str, host='localhost', port=6379):
        """
        memory stream for all agents
        use different prefix for keys to indicate different types of memory, e.g., "persona_name:associative", "persona_name:scratch"
        we define associative memory as the memory that stores the events that the agent has experienced
        and scratch memory as the memory that stores the temporary information that the agent needs to keep track of
        developers can define their own memory types
        """
        self.persona = persona_name
        self.db = redis.Redis(host=host, port=port, db=1, decode_responses=True)
        if not self.db.exists(f"{self.persona}:meta_data"):
            self.init_agent_from_files()
            self.db.set(f"counter:{persona_name}:events", 0)

    def init_agent_from_files(self):
        # this will be implemented in the derived classes
        raise NotImplementedError

    @property
    def event_counter(self):
        return int(self.db.get(f"counter:{self.persona}:events"))

    def increment_event_counter(self):
        return self.db.incr(f"counter:{self.persona}:events")

    def put_event_into_memory(self, event: Event, step: int, attributes: dict):
        # developers can define their own attributes
        key = f"{self.persona}:associative:{self.increment_event_counter()}"
        memory_node = EventMemoryNode(event, step, attributes)
        self.db.set(key, memory_node.to_json())

    def get_latest_events_memory(self, retentions: int = 5):
        # get the memory about latest events
        event_memory_nodes = []
        for i in range(retentions):
            key = f"associative:{self.persona}:{self.event_counter - i}"
            event_node = self.db.get(key)
            if not event_node:
                continue
                # raise ValueError(f"Event node {key} not found")
            event_memory_nodes.append(json.loads(event_node))
        return event_memory_nodes

    def set_scratch(self, key, value):
        self.db.set(f"{self.persona}:scratch:{key}", value)

    def get_scratch(self, key):
        return self.db.get(f"{self.persona}:scratch:{key}")
    def check_key(self, key):
        return self.db.exists(key)
