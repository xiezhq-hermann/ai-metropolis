# Generative Agents on AI Metropolis

A port of [Generative Agents](https://github.com/joonspk-research/generative_agents) to the AI Metropolis
interfaces, covering perception, retrieval, planning, reflection and execution. Unlike the replay agent in
`src/aimetropolis/generative_agents_simple`, these agents make live LLM calls and generate new behavior.

This is research code from the development of the paper, kept for reference. The paper's evaluation replays
recorded traces and does not use it. Be aware of the following before building on it:

- `simulator_generative.py` predates the current scheduler, and its call to `Env.geo_clustering` no longer
  matches that method's signature. It needs updating before `simulation_test.py` can run.
- `ville.py` has `REPLAY = True` by default, which expects recorded data that is not included. Set it to
  `False` for a live run.
- It needs `OPENAI_API_KEY` for embeddings and an SGLang or OpenAI backend for completions.
- Scripts must be run from this directory, because assets and prompts are read through relative paths.

`NOTES.md` has the original notes on how memory and state are laid out in Redis.
