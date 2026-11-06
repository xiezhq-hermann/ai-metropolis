# Benchmarks

See [Reproducing the paper](../README.md#reproducing-the-paper) for how to set up the servers and which
command matches which experiment. All of these replay recorded traces, so install the dataset first with
`python dataset/download.py`.

| Directory | What it replays | Options |
| --- | --- | --- |
| `original/` | One full day of 25 agents in SmallVille | `python benchmark.py --help` |
| `scaling/` | Busy and quiet hours for 25 to 1000 agents in LargeVille | `python benchmark.py --help` |
| `priority/` | The oracle dependency graph alone, without the simulation engine | `python benchmark.py --help` |

`original/` and `scaling/` append one line per run to `logs.jsonl`. Each run also writes:

- `benchmark_<setting>_...`, the Redis dumps for that run
- `translated_*.json`, the trace in Chrome trace format, viewable in `chrome://tracing` or Perfetto
- `*_outstanding_requests.png`, the number of in-flight requests over time

`duration` is the wall-clock time of the run and `duration_net` is the span from the first request to the last.
LargeVille concatenates up to 40 SmallVilles for busy hours and 56 for quiet hours, so `--num-agents` must be
a multiple of 25 and at most 1000 or 1400 respectively.

`priority/` takes pre-computed inputs from `dataset/replay/priority`, which cover 8:00 to 8:30 a.m. rather than the
intervals in the paper. `--priority predefined` uses the priority stored with each call, and `--priority step`
orders work by simulation step.
