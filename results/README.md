# Benchmark results

Raw logs from our A100 benchmark runs, one JSON object per run, in the format `benchmark/scaling` writes.
They are the logs that survived, not a complete record: treat them as a reference for what these experiments
look like, and use the paper for the full numbers. The `tp2dp3` runs use 6 GPUs and are not in the paper.

| File | Model | GPUs | SGLang settings |
| --- | --- | --- | --- |
| `llama-3-70b/tp4dp1.jsonl` | Llama-3-70B-Instruct | 4 A100 | `--tp 4 --dp 1` |
| `llama-3-70b/tp4dp2.jsonl` | Llama-3-70B-Instruct | 8 A100 | `--tp 4 --dp 2` |
| `llama-3-70b/tp2dp4.jsonl` | Llama-3-70B-Instruct | 8 A100 | `--tp 2 --dp 4` |
| `mixtral-8x7b/tp2dp4.jsonl` | Mixtral-8x7B-Instruct | 8 A100 | `--tp 2 --dp 4` |
| `mixtral-8x7b/tp2dp3.jsonl` | Mixtral-8x7B-Instruct | 6 A100 | `--tp 2 --dp 3` |

Each line has these fields:

| Field | Meaning |
| --- | --- |
| `setting` | scheduling mode, see [the mapping to the paper](../README.md#reproducing-the-paper) |
| `interval` | `busy` (12 p.m. to 1 p.m.) or `quiet` (6 a.m. to 7 a.m.) |
| `num_agents` | number of agents, 25 per concatenated SmallVille |
| `base_step`, `target_step` | the simulated steps replayed |
| `duration` | wall-clock seconds for the run |
| `duration_net` | seconds from the first LLM request to the last |

Some things to know when reading these:

- `duration_net` is `0` where the post-run trace dump came back empty. Use `duration` for those runs.
- Coverage is uneven. For example, the 8-GPU Llama-3-70B busy hour has no `sync` run at 500 or 1000 agents.
- There are no logs here for the Llama-3 8B experiments on L4 GPUs, or for the full-day runs.
