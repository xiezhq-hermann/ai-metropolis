# AI Metropolis

AI Metropolis is a simulation engine for agents powered by large language models (LLMs). It speeds up
multi-agent simulations with out-of-order execution: instead of synchronizing every agent at every time
step, it tracks which agents can actually affect each other and lets the rest move ahead. More requests can
then be in flight at once, so LLM serving engines run at larger batch sizes.

In the paper this achieves speedups of 1.3× to 4.15× over parallel simulation with global synchronization,
approaching optimal performance as the number of agents grows.

**Paper:** [AI Metropolis: Scaling Large Language Model-based Multi-Agent Simulation with Out-of-order
Execution](https://arxiv.org/abs/2411.03519), MLSys 2025.

This repository contains the engine, the benchmarks from the paper, and
[the LLM call traces](dataset/README.md) collected from [Generative
Agents](https://github.com/joonspk-research/generative_agents).

## Installation

You need Python 3.8+, a C++17 compiler, Redis and hiredis.

```bash
# Ubuntu
sudo apt-get install redis-server libhiredis-dev
# macOS
brew install redis hiredis

git clone https://github.com/xiezhq-hermann/ai-metropolis.git
cd ai-metropolis
python -m pip install -e .
```

If hiredis is somewhere unusual, set `HIREDIS_PREFIX` to the directory containing its `include` and `lib`.

Then fetch the replay traces (about 1 GB unpacked), which every benchmark needs:

```bash
python dataset/download.py
```

## Try it without a GPU

`tests/fake_sglang_server.py` stands in for the LLM server, so you can watch the engine replay a simulated
hour on a laptop. Its timings say nothing about real inference performance.

> [!WARNING]
> The benchmarks flush Redis databases 0, 1 and 2 on `localhost:6379`. Use a dedicated Redis instance.

```bash
redis-server --save "" &
python tests/fake_sglang_server.py --ms-per-token 2 &

cd benchmark/scaling
python benchmark.py --num-agents 25 --intervals quiet --settings async sync
```

Results are appended to `logs.jsonl`. Each run also leaves a directory of database dumps and a plot of
outstanding requests over time.

The two settings take about the same time here, because a quiet hour at this latency barely loads the server.
To see the effect of out-of-order execution, restart the fake server with `--ms-per-token 10` and use
`--intervals busy`. That takes about 15 minutes, and `async` finishes about twice as fast as `sync`.

To run the tests:

```bash
python -m unittest discover tests                            # no services needed
AIMETROPOLIS_TEST_REDIS=1 python -m unittest discover tests  # also replays through Redis, see above
```

## Reproducing the paper

Start Redis and an [SGLang](https://github.com/sgl-project/sglang) server on port 30000. The paper used
SGLang v0.1.17 with its radix cache disabled, so that results are stable across runs:

```bash
python -m sglang.launch_server --model-path meta-llama/Meta-Llama-3-70B-Instruct \
    --port 30000 --disable-radix-cache --tp 4 --dp 2
```

| Paper | Model and GPUs | `sglang.launch_server` settings |
| --- | --- | --- |
| Llama-3 8B | 1 to 8 NVIDIA L4 | `--dp` 1 to 8 |
| Llama-3 70B | 4 or 8 NVIDIA A100-80GB | `--tp 4 --dp 1` or `--tp 4 --dp 2` |
| Mixtral 8×7B | 8 NVIDIA A100-80GB | `--tp 2 --dp 4` |

Then run the experiment:

| Experiment | Command |
| --- | --- |
| Full day in SmallVille (§4.2) | `cd benchmark/original && python benchmark.py` |
| Scaling to 1000 agents (§4.3) | `cd benchmark/scaling && python benchmark.py` |
| Priority breakdown (§4.4) | `cd benchmark/scaling && python benchmark.py --num-agents 500 --intervals busy --settings async oracle`, then again with `--no-priority` |

The settings in the benchmarks map to the paper as follows:

| `--settings` value | Name in the paper |
| --- | --- |
| `async` | AI Metropolis |
| `sync` | parallel-sync |
| `single-thread` | single-thread |
| `oracle` | oracle |
| `critical` | critical |
| `no-dependency` | no-dependency |

[`results/`](results/README.md) holds the raw logs we kept from these runs.

> [!NOTE]
> The paper's priority scheduling also orders requests inside the serving engine, using a modified SGLang
> that is not part of this repository. Stock SGLang serves requests in arrival order, so with it `--no-priority`
> changes only the engine's own task and acknowledgement queues.

## How the code maps to the paper

| Paper | Code |
| --- | --- |
| Controller and workers (Algorithm 2) | `Simulator.run` and `cluster_process` in [`simulator.py`](src/aimetropolis/simulator.py) |
| Dependency rules, spatiotemporal dependency graph (§3.2, §3.3) | `update_dependency_dist` in [`persona_dependency.cpp`](csrc/persona_dependency.cpp) |
| Agent clustering (§3.4) | `geo_clustering` in [`persona_dependency.cpp`](csrc/persona_dependency.cpp) |
| Priority scheduling (§3.5) | the priority queues in `Simulator.run` |
| Oracle and critical path baselines (§4.2) | [`build_dependency.py`](src/aimetropolis/utils/build_dependency.py) |
| Replay of Generative Agents traces (§4.1) | [`generative_agents_simple/`](src/aimetropolis/generative_agents_simple) |

## Building your own simulation

Subclass `Env` to describe the world and `Agent` to define what an agent does each step, then hand both to
`Simulator`. `TheVille` and `SimpleAgent` are a complete example:

```python
from aimetropolis import Simulator
from aimetropolis.generative_agents_simple import SimpleAgent, TheVille

if __name__ == "__main__":
    sim = Simulator(TheVille, base_step=0, env_args={"num_agents": 25})
    sim.run(target_step=8640, agent_class=SimpleAgent, mode="async", num_processes=25)
```

The engine expects Redis on `localhost:6379` and SGLang on `localhost:30000`. Set `OPENAI_API_KEY` to call
OpenAI models through `OpenAIBackend`.

## Repository layout

```
csrc/          dependency tracking and clustering, in C++
src/           the aimetropolis Python package
benchmark/     the experiments from the paper
dataset/       documentation, manifest and tools for the traces, plus a small sample
results/       raw benchmark logs
examples/      a port of the full Generative Agents simulation
tools/         plots of movement, instrumentation and agent progress
tests/         unit and end-to-end tests
```

[`examples/generative_agents`](examples/generative_agents/README.md) is research code that generates new
behavior with live LLM calls. The paper's evaluation replays recorded traces instead and does not use it.

## Citation

```bibtex
@inproceedings{xie2025metropolis,
  title     = {{AI Metropolis}: Scaling Large Language Model-based Multi-Agent Simulation with Out-of-order Execution},
  author    = {Xie, Zhiqiang and Kang, Hao and Sheng, Ying and Krishna, Tushar and Fatahalian, Kayvon and Kozyrakis, Christos},
  booktitle = {Proceedings of Machine Learning and Systems (MLSys)},
  year      = {2025}
}
```

## License

Apache License 2.0, see [LICENSE](LICENSE). This project builds on Generative Agents, see [NOTICE](NOTICE).
