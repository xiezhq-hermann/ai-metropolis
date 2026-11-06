import csv
import json
import matplotlib.pyplot as plt
import argparse
from collections import defaultdict


def process_and_visualize_trace(csv_file):
    transitions = defaultdict(list)

    # Read the CSV file and compute the total and average durations
    with open(csv_file, 'r') as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            transition = f"{row['Start']} to {row['End']}"
            duration = int(row["Duration (microseconds)"]) / 1e3
            transitions[transition].append(duration)

    aggregated_data = []
    for transition, durations in transitions.items():
        total_duration = sum(durations) / 1e3
        average_duration = total_duration / len(durations)
        aggregated_data.append({
            "transition": transition,
            "total_duration": total_duration,
            "average_duration": average_duration,
            "count": len(durations)
        })

    max_duration = max([entry["total_duration"] for entry in aggregated_data])
    filtered_transitions = [
        entry["transition"] for entry in aggregated_data if entry["total_duration"] > max_duration / 100
    ]
    for f in filtered_transitions:
        print("range of durations for transition", f, ":", min(transitions[f]), max(transitions[f]))
        plt.figure(figsize=(10, 6))
        plt.hist(transitions[f], bins=50, color='skyblue', edgecolor='black')
        plt.title(f"Distribution of Durations for Transition: {f}")
        plt.xlabel("Duration (ms)")
        plt.ylabel("Frequency")
        plt.grid(True)

        # Save the figure
        output_file = f"distribution_{f.replace(' ', '_').replace('to', 'to').replace(':', '').replace(',', '')}.png"
        plt.savefig(output_file)
        plt.close()

    # print(aggregated_data)
    print(sorted(aggregated_data, key=lambda x: x["total_duration"], reverse=True))
    json.dump(aggregated_data, open("aggregated_and_average_durations.json", "w"), indent=4)


def main():
    parser = argparse.ArgumentParser(
        description="Process CSV trace file and visualize the aggregated and average durations.")
    parser.add_argument("csv_file", help="Path to the CSV trace file.")

    args = parser.parse_args()
    process_and_visualize_trace(args.csv_file)


if __name__ == "__main__":
    main()
