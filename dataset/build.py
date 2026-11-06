#!/usr/bin/env python3
"""Convert a raw run into the replay format used by the benchmarks.

    python dataset/build.py \
        --llm dataset/raw/days/day_05_llm.json --location dataset/raw/days/day_05_location.json \
        --base-step 4320 --target-step 4680 --output my_excerpt

writes my_excerpt/trace.json and my_excerpt/movement.json. This is the pipeline
that produced replay/busy and replay/quiet from the raw runs in raw/days.
"""
import argparse
import json
import os

from aimetropolis.utils import parse_movements, parse_traces


def load(path):
    with open(path) as f:
        return json.load(f)


def build(llm_path, location_path, base_step, target_step, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    parse_traces.change_format(load(llm_path), base_step, target_step, os.path.join(output_dir, "trace.json"))
    movements, _ = parse_movements.change_format(load(location_path), 0, target_step)
    parse_movements.validation(movements, os.path.join(output_dir, "movement.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a raw run into the replay format.")
    parser.add_argument("--llm", required=True, help="raw LLM call file")
    parser.add_argument("--location", required=True, help="raw location file")
    parser.add_argument("--base-step", type=int, required=True)
    parser.add_argument("--target-step", type=int, required=True)
    parser.add_argument("--output", required=True, help="output directory")
    args = parser.parse_args()
    build(args.llm, args.location, args.base_step, args.target_step, args.output)
