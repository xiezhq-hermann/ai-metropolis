from aimetropolis import Env, Event, Action


class Agent:
    '''
    This class is the base class for all agents
    The instance of the agent will be empheral and will be created and destroyed during the simulation
    '''

    def __init__(self, name: str, step: int, env: Env):
        self.name = name
        self.step = step
        self.env = env

    def get_time(self):
        num_steps_per_day = 24 * 3600 / self.env.sec_per_step
        num_steps_per_hour = 3600 / self.env.sec_per_step
        num_steps_per_minute = 60 / self.env.sec_per_step
        day = self.step // num_steps_per_day
        hour = (self.step % num_steps_per_day) // num_steps_per_hour
        minute = (self.step % num_steps_per_hour) // num_steps_per_minute
        second = (self.step % num_steps_per_minute) * self.env.sec_per_step
        return f"Day {day}, {hour}:{minute}:{second}"

    def perceive(self) -> list[Event]:
        return self.env.perceive_events(self.name)

    def proceed(self) -> Action:
        # this will be implemented in the derived classes
        raise NotImplementedError
