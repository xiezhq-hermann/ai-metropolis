import json
import argparse

from aimetropolis.utils.tokens import count_tokens


def change_format(traces, base_step=0, target_step=8640, output_file="new_traces.json"):
    new_traces = {}
    min_time, max_time = float("inf"), 0
    input_tokens, output_tokens = 0, 0
    trace_count = 0
    for i in range(base_step, target_step):
        new_traces[i] = {}
    for key in traces:
        try:
            persona, step, func_name, _ = key.split(":")
        except:
            print("Error in key:", key)
            continue
        min_time = min(min_time, float(traces[key]["start_time"]))
        max_time = max(max_time, float(traces[key]["end_time"]))
        step = int(step)
        if step not in new_traces:
            continue
        trace = {
            "func_name": func_name,
            "prompt": traces[key]["input"],
            "max_tokens": count_tokens(traces[key]["output"]),
            "ignore_eos": True,
            "stop": None,
            "reference_output": traces[key]["output"]
        }
        trace_count += 1
        input_tokens += count_tokens(trace["prompt"])
        output_tokens += count_tokens(trace["reference_output"])
        if persona not in new_traces[step]:
            new_traces[step][persona] = [trace]
        else:
            new_traces[step][persona].append(trace)
    json.dump(new_traces, open(output_file, "w"), indent=4)
    print(f"durations: {(max_time - min_time) / 3600} hours")
    print(f"trace count: {trace_count}")
    print(f"input tokens: {input_tokens}, output tokens: {output_tokens}")
    return new_traces


def visual_distribution(traces):
    segment_call_count = {i: 0 for i in range(0, 24)}
    for step in traces:
        for persona in traces[step]:
            segment_call_count[step // 360] += len(traces[step][persona])
    print(segment_call_count, f"sum: {sum(segment_call_count.values())}")


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--trace-file", type=str, help="input trace file")
    parser.add_argument("-b", "--base-step", type=int, default=0, help="base step")
    parser.add_argument("-t", "--target-step", type=int, default=8640, help="target step")
    parser.add_argument("-o", "--output-file", type=str, default="new_traces.json", help="output file")

    traces = json.load(open(parser.parse_args().trace_file, "r"))
    new_traces = change_format(traces,
                               parser.parse_args().base_step,
                               parser.parse_args().target_step,
                               parser.parse_args().output_file)
