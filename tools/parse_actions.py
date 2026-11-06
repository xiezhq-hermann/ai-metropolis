import sys
import json

import matplotlib.pyplot as plt


def plot_steps(agents):
    plt.figure(figsize=(10, 6))

    for p, time_step_dict in agents.items():
        sorted_steps = sorted(time_step_dict.items(), key=lambda x: x[1])

        # Prepare the data for step plot
        times = []
        steps = []

        for i in range(len(sorted_steps) - 1):
            step, time = sorted_steps[i]
            next_time = sorted_steps[i + 1][1]

            # Add the current step and time
            times.append(time)
            steps.append(step)

            # Add the current step at the next time
            times.append(next_time)
            steps.append(step)

        # Add the last step and its time
        last_step, last_time = sorted_steps[-1]
        times.append(last_time)
        steps.append(last_step)
        plt.step(times, steps, where='post', marker='o', label=p)

        # Plot the data
    plt.xlabel('Time (seconds)')
    plt.ylabel('Step')
    plt.title('Step Changes Over Time')
    plt.grid(True)
    plt.savefig(f'step_changes_over_time.png')


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python parse_actions.py traces")
        sys.exit(1)
    env_file = json.load(open(sys.argv[1]))

    start_time = 0xffffffff
    agent_dict = {}

    for key, value_str in env_file.items():
        if "action:" in key:
            value = json.loads(value_str)
            assert value["type"] == "AgentMove"
            persona = value["persona"]
            if persona not in agent_dict:
                agent_dict[persona] = {}
            effective_time = value["effective_time"]
            start_time = min(start_time, effective_time)
            async_step = value["step"]
            base_step = key.split(":")[-1]
            assert async_step not in agent_dict[persona]
            agent_dict[persona][async_step] = effective_time
    for p in agent_dict:
        for s in agent_dict[p]:
            agent_dict[p][s] -= start_time

    plot_steps(agent_dict)
