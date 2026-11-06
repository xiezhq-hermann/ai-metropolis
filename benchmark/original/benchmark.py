"""SmallVille benchmark: replay one full simulated day with the 25 agents of the Generative Agents paper."""
import argparse
import json
import multiprocessing
import time

from aimetropolis import Simulator
from aimetropolis.generative_agents_simple import SimpleAgent, TheVille
from aimetropolis.utils import (build_dependency_graph, clear_all_db, dump_all_db, find_critical_path, replay_path,
                                translate_traces)

SETTINGS = ["critical", "oracle", "async", "sync", "single-thread"]
NUM_AGENTS = 25


def run_setting(setting, base_step, target_step, priority, log_file):
    clear_all_db()
    sim = Simulator(TheVille, base_step=base_step, env_args={"num_agents": NUM_AGENTS})
    if setting == "oracle" or setting == "critical":
        movements = json.load(open(replay_path("full_day", "movement.json")))
        dependency_dag, dependency_reverse_dag = build_dependency_graph(movements, base_step, target_step)
        for key in dependency_dag:
            assert key in dependency_reverse_dag
            for blocking_key in dependency_dag[key]:
                sim.env.db.sadd(f"oracle_dependency:{key}", blocking_key)
            for update_key in dependency_reverse_dag[key]:
                sim.env.db.sadd(f"oracle_dependency_current:{key}", update_key)

        if setting == "critical":
            traces = json.load(open(replay_path("full_day", "trace.json")))
            critical_path = find_critical_path(dependency_dag, traces)
            # only keep the requests on the critical path
            for key in sim.env.db.keys("recorded_calls:*"):
                if ":".join(key.split(":")[1:]) not in critical_path:
                    sim.env.db.delete(key)

    print(f"Running benchmark for {setting}")
    tic = time.time()
    sim.run(target_step, SimpleAgent, num_processes=NUM_AGENTS, mode=setting, priority=priority)
    duration = time.time() - tic

    log_dir = f"benchmark_{setting}_{NUM_AGENTS}_{base_step}_{target_step}"
    dump_all_db(log_dir)
    duration_net = translate_traces(f"{log_dir}/trace_db.json")
    print(f"Simulation for {setting} from step {base_step} to {target_step} "
          f"for {NUM_AGENTS} agents took {duration:.2f}/{duration_net:.2f} seconds.")

    with open(log_file, "a") as f:
        f.write(
            json.dumps({
                "setting": setting,
                "num_agents": NUM_AGENTS,
                "base_step": base_step,
                "target_step": target_step,
                "priority": priority,
                "duration": duration,
                "duration_net": duration_net
            }) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", nargs="+", default=SETTINGS, choices=SETTINGS)
    parser.add_argument("--base-step", type=int, default=0)
    parser.add_argument("--target-step", type=int, default=8640)
    parser.add_argument("--no-priority", action="store_true", help="use FIFO task queues")
    parser.add_argument("--log-file", default="logs.jsonl")
    args = parser.parse_args()

    multiprocessing.freeze_support()
    for setting in args.settings:
        run_setting(setting, args.base_step, args.target_step, not args.no_priority, args.log_file)
