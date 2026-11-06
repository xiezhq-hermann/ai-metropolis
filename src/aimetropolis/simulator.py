import queue
import asyncio
import threading
from tqdm import tqdm
from typing import Type
from multiprocessing import Queue, Process
from concurrent.futures import ThreadPoolExecutor
from queue import PriorityQueue

from multiprocessing.managers import SyncManager

from aimetropolis import Env
from aimetropolis import Agent
from aimetropolis import Action

SyncManager.register('PriorityQueue', PriorityQueue)
_sync_manager = None


def get_sync_manager() -> SyncManager:
    # started on first use: at import time it would fail under the spawn start method (the macOS default)
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
        _sync_manager.start()
    return _sync_manager


async def cluster_task(agent_class: Type[Agent],
                       persona_names: str,
                       step: int,
                       local_env: Env,
                       ack_queue: Queue,
                       update_dep=True) -> Action:

    def agent_thread(agent_class: Type[Agent], persona_name: str, step: int, local_env: Env) -> Action:
        agent = agent_class(persona_name, step, local_env)
        action = agent.proceed()
        return action

    with ThreadPoolExecutor(max_workers=len(persona_names)) as executor:
        futures = [executor.submit(agent_thread, agent_class, name, step, local_env) for name in persona_names]
        actions = await asyncio.gather(*[asyncio.wrap_future(future) for future in futures])

    Action.apply_actions(local_env, actions)
    if update_dep:
        local_env.persona_dependency.update_dist(persona_names, step + 1)
    ack_queue.put((step + 1, persona_names))


async def cluster_task_blocking(agent_class: Type[Agent], persona_names: str, step: int, local_env: Env,
                                ack_queue: Queue) -> Action:

    actions = []
    for persona in persona_names:
        agent = agent_class(persona, step, local_env)
        action = agent.proceed()
        actions.append(action)

    Action.apply_actions(local_env, actions)
    ack_queue.put((step + 1, persona_names))


async def pull_cluster(local_env: Env,
                       task_queue: Queue,
                       ack_queue: Queue,
                       agent_class: Type[Agent],
                       target_step: int,
                       update_dep: bool = True) -> None:
    ongoing_tasks = []
    while local_env.base_step < target_step:
        # Check ongoing tasks and remove completed ones
        ongoing_tasks = [task for task in ongoing_tasks if not task.done()]

        try:
            step, persona_names = task_queue.get(block=False)
        except queue.Empty:
            await asyncio.sleep(0.1)
            continue
        new_task = asyncio.create_task(cluster_task(agent_class, persona_names, step, local_env, ack_queue, update_dep))
        ongoing_tasks.append(new_task)
    return


async def pull_cluster_blocking(local_env: Env, task_queue: Queue, ack_queue: Queue, agent_class: Type[Agent],
                                target_step: int) -> None:
    while local_env.base_step < target_step:
        try:
            step, persona_names = task_queue.get(block=True, timeout=1)
        except:
            continue
        await cluster_task_blocking(agent_class, persona_names, step, local_env, ack_queue)
    return


def cluster_process(task_queue: Queue,
                    ack_queue: Queue,
                    env_class: Type[Env],
                    agent_class: Type[Agent],
                    target_step: int,
                    process_id: int = 0,
                    blocking: bool = False,
                    update_dep: bool = True):
    local_env = env_class()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if blocking:
        loop.run_until_complete(pull_cluster_blocking(local_env, task_queue, ack_queue, agent_class, target_step))
    else:
        loop.run_until_complete(pull_cluster(local_env, task_queue, ack_queue, agent_class, target_step, update_dep))
    return


class Simulator:

    def __init__(self, env_class: Type[Env], base_step: int = 0, env_args={"num_agents": 25, "cache": False}):
        # only a single thread is used to initialize the environment
        self.env = env_class(base_step=base_step, **env_args)
        self.start_step = base_step
        self.base_step_update_signal = threading.Event()
        self.clustering_signal = threading.Event()

    def checkpoint(self):
        # wait till all personas proceed to the same step

        # save meta data of the game into a json file

        # save redis db (game states) to disk
        # save personas' memory to disk
        pass

    def replay(self):
        pass

    def threaded_update_base_step(self, num_steps):
        progress_bar = tqdm(total=num_steps)
        while progress_bar.n < num_steps:
            # Block until there is a signal to update the base step
            self.base_step_update_signal.wait()
            self.base_step_update_signal.clear()
            update = self.env.persona_dependency.update_base_step()
            if update:
                progress_bar.update(update)

    def run(self, target_step: int, agent_class: Type[Agent], mode: str = "async", num_processes=4, priority=True):

        if priority:
            manager = get_sync_manager()
            task_queue = manager.PriorityQueue()
            ack_queue = manager.PriorityQueue()
        else:
            task_queue = Queue()
            ack_queue = Queue()
        if mode == "single-thread":
            processes = [
                Process(target=cluster_process,
                        args=(task_queue, ack_queue, self.env.__class__, agent_class, target_step, 0, True))
            ]
        else:
            processes = [
                Process(target=cluster_process,
                        args=(task_queue, ack_queue, self.env.__class__, agent_class, target_step, i, False,
                              mode == "async")) for i in range(num_processes)
            ]
        for p in processes:
            p.start()

        num_agents = len(self.env.persona_names)
        # offload base_step updating from critical path to a separate thread
        update_thread = threading.Thread(target=self.threaded_update_base_step, args=(target_step - self.start_step,))
        update_thread.daemon = True
        update_thread.start()

        def thread_update_dependency():
            processed_agent_steps = 0
            batch_update_factor = 5
            while True:
                try:
                    proceeded_step, proceeded_agents = ack_queue.get(block=True, timeout=5)
                except queue.Empty:
                    if self.env.persona_dependency.num_completed_agents() == num_agents:
                        break
                    continue
                if mode == "async":
                    proceeded_clusters = [(proceeded_step, proceeded_agents)]
                    while not ack_queue.empty() and len(proceeded_clusters) < batch_update_factor:
                        proceeded_clusters.append(ack_queue.get(block=False))
                        processed_agent_steps += len(proceeded_clusters[-1][1])
                    # dependency update is done in the cluster_task
                    self.env.persona_dependency.update_agent_status(proceeded_clusters, target_step)

                elif mode in ["single-thread", "sync"]:
                    # sync
                    self.env.persona_dependency.update_agent_status_sync(proceeded_agents, proceeded_step,
                                                                         target_step == proceeded_step)
                elif mode in ["oracle", "critical"]:
                    self.env.persona_dependency.update_agent_status_oracle(proceeded_agents, proceeded_step,
                                                                           target_step == proceeded_step)
                else:
                    raise ValueError(f"Invalid mode: {mode}")
                self.clustering_signal.set()

                processed_agent_steps += len(proceeded_agents)
                if processed_agent_steps >= (self.env.base_step - self.start_step + 1) * num_agents:
                    self.base_step_update_signal.set()

                continue

        dependency_update_thread = threading.Thread(target=thread_update_dependency)
        dependency_update_thread.daemon = True
        dependency_update_thread.start()
        self.clustering_signal.set()

        while self.env.persona_dependency.num_completed_agents() < num_agents:
            # block until more agents are ready to be clustered
            self.clustering_signal.wait()
            self.clustering_signal.clear()

            if mode in ["oracle", "critical"]:
                self.env.persona_dependency.geo_clustering_relaxed(task_queue)
            elif mode in ["single-thread", "sync", "async"]:
                if mode != "async" and self.env.persona_dependency.num_available_agents(
                ) + self.env.persona_dependency.num_completed_agents() != num_agents:
                    continue
                self.env.persona_dependency.geo_clustering(task_queue, mode == "async")
            else:
                raise ValueError(f"Invalid mode: {mode}")

        update_thread.join()
        dependency_update_thread.join()
        for p in processes:
            p.join()
        self.env.persona_dependency.dump_trace("instrumentation_trace.csv")
