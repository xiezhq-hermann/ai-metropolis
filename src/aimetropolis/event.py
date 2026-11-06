class Event:

    def __init__(self, subject: str, predicate: str, object: str, location: str, description: str) -> None:
        self.subject = subject
        self.predicate = predicate
        self.object = object
        self.location = location
        if description is None:
            self.description = f"{subject} {predicate} {object} at {location}"
        else:
            self.description = description

    def __str__(self) -> str:
        return f"Event({self.subject}, {self.predicate}, {self.object}, {self.location}, {self.description})"

    def __eq__(self, other) -> bool:
        return str(self) == str(other)


class ChatEvent(Event):

    def __init__(self, persona_0: str, persona_1: str, object: str, location: str, description: str):
        super().__init__(f"{persona_0} and {persona_1}", "are conversing about", object, location, description)

    # def __str__(self) -> str:
    #     return f"ChatEvent({self.subject}, {self.predicate}, {self.object}, {self.location}, {self.description}, {self.chat})"
