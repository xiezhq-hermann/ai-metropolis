"""Scaling benchmark: replay busy and quiet hours of concatenated SmallVilles (LargeVille)."""
import argparse
import json
import multiprocessing
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from aimetropolis import Simulator
from aimetropolis.generative_agents_simple import SimpleAgent, TheVille
from aimetropolis.generative_agents_simple.agent_functions import common_llm_call
from aimetropolis.utils import (build_dependency_graph, clear_all_db, dump_all_db, find_critical_path, replay_path,
                                translate_traces)

INTERVALS = {"quiet": (2160, 2520), "busy": (4320, 4680)}
SETTINGS = ["no-dependency", "critical", "oracle", "async", "sync", "single-thread"]
AGENTS_PER_WORLD = 25
MAZE_HEIGHT = 100


def concat_traces(num_worlds, status):
    new_traces = {}
    new_movements = {}
    for i in range(num_worlds):
        for step, personas in json.load(open(replay_path(status, f"{i}_trace.json"))).items():
            if step not in new_traces:
                new_traces[step] = personas
            else:
                for persona, funcs in personas.items():
                    persona = f"{persona}_{i}"
                    assert persona not in new_traces[step]
                    new_traces[step][persona] = funcs
        for persona, movements in json.load(open(replay_path(status, f"{i}_movement.json"))).items():
            if persona not in new_movements:
                new_movements[persona] = movements
            else:
                persona = f"{persona}_{i}"
                movements = [(x, y + i * MAZE_HEIGHT) for x, y in movements]
                assert persona not in new_movements
                new_movements[persona] = movements
    return new_traces, new_movements


def bench_no_dependency(traces):
    calls = [call for v in traces.values() for call_list in v.values() for call in call_list]
    progress_bar = tqdm(total=len(calls))

    def worker(c):
        common_llm_call("", 0, c["prompt"], c["max_tokens"], c["stop"], c["ignore_eos"])
        progress_bar.update(1)

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=os.cpu_count() * 8) as executor:
        futures = [executor.submit(worker, c) for c in calls]

        for future in as_completed(futures):
            future.result()

    print(f"Time taken: {time.time() - start_time}")


def run_setting(setting, interval, num_agents, priority, log_file):
    clear_all_db()
    base_step, target_step = INTERVALS[interval]
    num_processes = min(os.cpu_count(), num_agents)
    traces, movements = concat_traces(num_agents // AGENTS_PER_WORLD, interval)

    if setting != "no-dependency":
        sim = Simulator(TheVille,
                        base_step=base_step,
                        env_args={
                            "num_agents": num_agents,
                            "cache": False,
                            "recorded_movement": movements,
                            "recorded_traces": traces
                        })

    if setting == "oracle" or setting == "critical":
        dependency_dag, dependency_reverse_dag = build_dependency_graph(movements, base_step, target_step)
        for key in dependency_dag:
            assert key in dependency_reverse_dag
            for blocking_key in dependency_dag[key]:
                sim.env.db.sadd(f"oracle_dependency:{key}", blocking_key)
            for update_key in dependency_reverse_dag[key]:
                sim.env.db.sadd(f"oracle_dependency_current:{key}", update_key)

        if setting == "critical":
            critical_path = find_critical_path(dependency_dag, traces)
            # only keep the requests on the critical path
            for key in sim.env.db.keys("recorded_calls:*"):
                if ":".join(key.split(":")[1:]) not in critical_path:
                    sim.env.db.delete(key)

    print(f"Running benchmark for {setting} {interval} with {num_agents} agents.")
    tic = time.time()
    if setting == "no-dependency":
        bench_no_dependency(traces)
    else:
        sim.run(target_step, SimpleAgent, num_processes=num_processes, mode=setting, priority=priority)
    duration = time.time() - tic

    log_dir = f"benchmark_{setting}_{interval}_{num_agents}_{base_step}_{target_step}"
    dump_all_db(log_dir)
    duration_net = translate_traces(f"{log_dir}/trace_db.json")
    print(f"Simulation for {setting} {interval} from step {base_step} to {target_step} "
          f"for {num_agents} agents took {duration:.2f}/{duration_net:.2f} seconds.")

    with open(log_file, "a") as f:
        f.write(
            json.dumps({
                "setting": setting,
                "interval": interval,
                "num_agents": num_agents,
                "base_step": base_step,
                "target_step": target_step,
                "priority": priority,
                "duration": duration,
                "duration_net": duration_net
            }) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-agents", type=int, nargs="+", default=[25, 100, 500, 1000])
    parser.add_argument("--intervals", nargs="+", default=list(INTERVALS), choices=list(INTERVALS))
    parser.add_argument("--settings", nargs="+", default=SETTINGS, choices=SETTINGS)
    parser.add_argument("--no-priority", action="store_true", help="use FIFO task queues (Table 1 in the paper)")
    parser.add_argument("--log-file", default="logs.jsonl")
    args = parser.parse_args()

    for num_agents in args.num_agents:
        if num_agents % AGENTS_PER_WORLD:
            parser.error(f"--num-agents must be a multiple of {AGENTS_PER_WORLD}, got {num_agents}")

    multiprocessing.freeze_support()
    for num_agents in args.num_agents:
        for interval in args.intervals:
            for setting in args.settings:
                run_setting(setting, interval, num_agents, not args.no_priority, args.log_file)
