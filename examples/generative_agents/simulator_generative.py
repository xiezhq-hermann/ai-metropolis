import time
import queue
from typing import Type
from multiprocessing import Queue, Process
from concurrent.futures import ThreadPoolExecutor

from aimetropolis import Env
from aimetropolis import Agent
from aimetropolis import Action


def agent_thread(agent_class_dict: Type[Agent], persona_name: str, step: int, env: Env) -> Action:
    agent = agent_class_dict[persona_name]
    if step == 0:
        new_day = "First day"
    elif step % (24 * 6) == 0:
        new_day = "New day"
    else:
        new_day = None
    return agent.proceed(agent_class_dict,new_day)


def cluster_process(task_queue: Queue,
                    ack_queue: Queue,
                    env_class: Type[Env],
                    agent_class_dict: Type[Agent],
                    target_step: int,
                    process_id: int = 0):
    local_env = env_class()
    while local_env.base_step < target_step:
        try:
            step, persona_names = task_queue.get(block=False)
        except queue.Empty:
            # to avoid busy waiting
            time.sleep(0.5)
            continue
        # if step > local_env.base_step:
        #     print(f"Process {process_id} is processing step {step} while base step is {local_env.base_step}")
        actions = []
        with ThreadPoolExecutor(max_workers=len(persona_names)) as executor:
            for name in persona_names:
                future = executor.submit(agent_thread, agent_class_dict, name, step, local_env)
                actions.append(future.result())

        Action.apply_actions(local_env, actions)
        ack_queue.put((step + 1, persona_names))

    return


class Simulator:

    def __init__(self, env_class: Type[Env], base_step: int = 0):
        # only a single thread is used to initialize the environment
        self.env = env_class(base_step=base_step)
        self.base_step = base_step

    def checkpoint(self):
        # wait till all personas proceed to the same step

        # save meta data of the game into a json file

        # save redis db (game states) to disk
        # save personas' memory to disk
        pass

    def replay(self):
        pass

    def run(self, target_step: int, agent_class: Type[Agent], speculation=True, num_processes=4):
        task_queue = Queue()
        ack_queue = Queue()
        idle_agents = self.env.persona_names
        print(idle_agents)
        persona_dict = {}
        for p in idle_agents:
            persona_dict[p] = agent_class(p, 0, self.env)
        
        processes = [
            Process(target=cluster_process,
                    args=(task_queue, ack_queue, self.env.__class__, persona_dict, target_step, i))
            for i in range(num_processes)
        ]
        for p in processes:
            p.start()

        
        num_agents = len(idle_agents)
        completed_agents = []
        processed_agent_steps = 0

        while len(completed_agents) < num_agents:
            # if speculation is off, wait for all agents to finish the current step
            if speculation or len(idle_agents) + len(completed_agents) == num_agents:
                agent_clusters = self.env.geo_clustering(idle_agents, speculation=speculation)
                for step, coupled_agents in agent_clusters:
                    assert step < target_step
                    task_queue.put((step, coupled_agents))
                    idle_agents = [agent for agent in idle_agents if agent not in coupled_agents]

            try:
                proceeded_step, proceeded_agent = ack_queue.get(block=False)
                if proceeded_step == target_step:
                    completed_agents.extend(proceeded_agent)
                else:
                    idle_agents.extend(proceeded_agent)
                processed_agent_steps += len(proceeded_agent)
                if processed_agent_steps >= (self.env.base_step - self.base_step + 1) * num_agents:
                    self.env.update_base_step()
            except queue.Empty:
                # to avoid busy waiting
                time.sleep(0.1)


if __name__ == "__main__":
    # testing small scale simulation here
    pass
