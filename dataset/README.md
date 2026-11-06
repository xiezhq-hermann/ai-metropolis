# AI Metropolis traces

LLM call traces collected from [Generative Agents](https://github.com/joonspk-research/generative_agents):
1.79 million calls from 31 simulated days of 25 agents, with the position of every agent at every step. Unlike
request logs from a chat service, these traces preserve *why* calls happen when they do: who made each call,
at which simulation step, and which other agents were close enough to matter. That dependency structure is
what serving benchmarks usually lack.

Each simulated day is 8640 steps of 10 seconds. Agents ran on OpenAI's `gpt-3.5-turbo-instruct`, using the
settings of the Generative Agents paper. Across all 31 days:

| | Mean |
| --- | --- |
| LLM calls per simulated day | 57.7k |
| Input tokens per call | 641.5 |
| Output tokens per call | 21.9 |

Token counts use the `cl100k_base` encoding. Calls follow the agents' day: almost none between 1 a.m. and 4 a.m.
while everyone sleeps, a peak of about 4.6k per hour at noon, and a mix of 26 prompt functions dominated by
`run_gpt_prompt_event_poignancy` (37.7% of calls), then conversation and action planning.

## Getting the data

The traces are attached to the [`dataset-v1` release](https://github.com/xiezhq-hermann/ai-metropolis/releases/tag/dataset-v1).
`download.py` fetches them and checks every file against the SHA-256 sums in `MANIFEST.json`:

```bash
python dataset/download.py              # replay traces, enough for every benchmark
python dataset/download.py raw-days     # the whole-day runs
python dataset/download.py --all
```

| Subset | Contents | Archive | Unpacked |
| --- | --- | --- | --- |
| `replay` | What the benchmarks replay | 12 MB | 1.0 GB |
| `raw-days` | 31 whole-day runs, with timing | 190 MB | 7.3 GB |
| `raw-hours` | 55 single-hour runs, with timing | 8 MB | 407 MB |

`sample/` is a 60-step slice of a quiet hour kept in the repository for tests and quick experiments.

## Layout

```
replay/
  full_day/{trace,movement}.json      one whole day, from day_00
  busy/<world>_{trace,movement}.json  12 p.m. to 1 p.m., steps 4320-4679, worlds 0-39
  quiet/<world>_{trace,movement}.json 6 a.m. to 7 a.m., steps 2160-2519, worlds 0-55
  priority/                           input for benchmark/priority, steps 2880-3059
raw/
  days/day_<NN>_{llm,location}.json   31 whole-day runs
  hours/<busy|quiet>_<world>_{llm,location}.json   55 single-hour runs
```

## File formats

### Raw LLM calls

`raw/**/*_llm.json` is a dump of the instrumentation database, a JSON object with one entry per call. All values
are strings.

```json
{
  "Eddy Lin:5041:run_gpt_generate_iterative_chat_utt:1720824401.7880151": {
    "persona_name": "Eddy Lin",
    "step": "5041",
    "function_name": "run_gpt_generate_iterative_chat_utt",
    "model_name": "gpt-3.5-turbo-instruct",
    "max_token": "50",
    "start_time": "1720824401.7880151",
    "end_time": "1720824403.0507534",
    "input": "<prompt>",
    "output": "<response>"
  }
}
```

Keys are `<persona>:<step>:<function>:<start time>`. Most files also contain a meaningless `"run"` entry left
over from a database test, which you should skip. Entries are in no particular order.

### Raw locations

`raw/**/*_location.json` holds one entry per agent per step:

```json
{"location:Sam Moore:6333": {"location": "[40, 60]"}}
```

### Replay traces

`replay/**/*_trace.json` groups calls by step and then by agent, in the order each agent made them:

```json
{
  "2160": {
    "Isabella Rodriguez": [
      {
        "func_name": "run_gpt_prompt_pronunciatio",
        "prompt": "<prompt>",
        "max_tokens": 6,
        "ignore_eos": true,
        "stop": null,
        "reference_output": "<response>"
      }
    ]
  }
}
```

`max_tokens` is the length of the recorded response, so that with `ignore_eos` a replay generates the same
number of tokens whatever the model. A simulated hour has an entry for every step, empty if nobody made a call.
Timing is not kept; use the raw files for that.

### Replay movements

`replay/**/*_movement.json` maps each agent to a list of `[x, y]` positions indexed by step, starting from step 0
even in hourly files. Where a recording skipped tiles, the missing positions are inserted so that agents move one
tile per step, which shifts that agent's later positions by a step or two relative to the raw file. SmallVille is
140 by 100 tiles.

### Priority inputs

`replay/priority/persona_calls.json` maps `<persona>:<step>` to its calls and a precomputed priority.
`dependency_adjacency.json` holds the `forward` and `reverse` edges of the oracle dependency graph over the same
keys.

## How the files relate

`MANIFEST.json` records, for every world, the raw run it came from, and for every raw file, its original name.

The scaling benchmark concatenates worlds in order, so a world's number is part of the experiment. To reproduce
the paper, keep the numbering even where worlds repeat.

- **Worlds 0-19** were cut from 17 of the whole-day runs (`day_00` to `day_16`).
- **Worlds 20 and up** come from runs restarted from a shared checkpoint at the start of the hour, recorded in
  `raw/hours`. Their raw files cover only that hour, and the earlier positions in `replay/` come from the
  checkpoint's run.
- **`day_17` to `day_30`** were collected later and are not used by any world.

To rebuild an excerpt, or cut a different hour from a whole-day run:

```bash
python dataset/build.py --llm dataset/raw/days/day_05_llm.json --location dataset/raw/days/day_05_location.json \
    --base-step 4320 --target-step 4680 --output my_excerpt
```

For worlds cut from whole-day runs, this reproduces the files in `replay/` byte for byte.

## Known quirks

We kept the data as it was used in the paper, including these imperfections.

- **Repeated worlds.** Some worlds replay the same trace, so busy hours have 36 distinct traces among 40 worlds
  and quiet hours 53 among 56. Busy worlds 9/11, 13/19, 17/18 and 33/34 and quiet worlds 9/11, 13/19 and 17/18
  are identical.
- **`day_02` shares locations with `day_01`.** Its location file is a byte-for-byte copy, while its LLM calls are
  distinct, so movement and calls in `day_02` (and worlds 2) do not belong together.
- **Two light days.** `day_03` and `day_04` have about half the calls of the others, at about 31.6k.
- **`day_10` is merged.** It was uploaded in two parts and is the only raw file that is not byte-identical to its
  original. It holds the union of the two parts. Worlds 10 were cut from the first part, which ends at step 8161.
- **Busy excerpts 20-39 end slightly early.** Most omit the final one or two steps of their run (4678-4679).
- **Runs do not end exactly at step 8640.** The last recorded call is anywhere from step 8544 to 8797, and a
  little activity spills past the end of the day in `day_00`, `day_06` and `day_16`.

Prompts and responses describe the fictional residents of SmallVille. Email addresses in them were invented by
the model. No real user data is involved.

## License

The dataset is released under the Apache License 2.0, like the rest of this repository. Prompts derive from
Generative Agents, see [NOTICE](../NOTICE). If you use it, please [cite the paper](../README.md#citation).
