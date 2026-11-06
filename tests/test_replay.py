"""End-to-end replay against Redis and a fake LLM server.

This test flushes Redis databases 0-2 on localhost:6379, so it only runs when asked to:

    redis-server --save "" &
    AIMETROPOLIS_TEST_REDIS=1 python -m unittest discover tests

Every scheduling mode has to replay the same LLM calls and end in the same world
state. That is the property out-of-order execution must preserve.
"""
import collections
import json
import os
import sys
import threading
import unittest
from pathlib import Path

import redis

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

BASE_STEP, TARGET_STEP = 2160, 2220
ENABLED = os.environ.get("AIMETROPOLIS_TEST_REDIS") == "1"


@unittest.skipUnless(ENABLED, "set AIMETROPOLIS_TEST_REDIS=1 to run (flushes Redis databases 0-2)")
class ReplayTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from fake_sglang_server import serve
        cls.server = serve(port=30000, slots=8, ms_per_token=0.1)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.traces = json.load(open(REPO / "dataset" / "sample" / "trace.json"))
        cls.movements = json.load(open(REPO / "dataset" / "sample" / "movement.json"))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def replay(self, mode):
        from aimetropolis import Simulator
        from aimetropolis.generative_agents_simple import SimpleAgent, TheVille
        from aimetropolis.utils import build_dependency_graph, clear_all_db, find_critical_path

        clear_all_db()
        sim = Simulator(TheVille,
                        base_step=BASE_STEP,
                        env_args={
                            "num_agents": 25,
                            "cache": False,
                            "recorded_movement": self.movements,
                            "recorded_traces": self.traces
                        })
        if mode in ("oracle", "critical"):
            forward, reverse = build_dependency_graph(self.movements, BASE_STEP, TARGET_STEP)
            for key in forward:
                for blocking_key in forward[key]:
                    sim.env.db.sadd(f"oracle_dependency:{key}", blocking_key)
                for update_key in reverse[key]:
                    sim.env.db.sadd(f"oracle_dependency_current:{key}", update_key)
            if mode == "critical":
                path = find_critical_path(forward, self.traces)
                for key in sim.env.db.keys("recorded_calls:*"):
                    if ":".join(key.split(":")[1:]) not in path:
                        sim.env.db.delete(key)
        sim.run(TARGET_STEP, SimpleAgent, num_processes=8, mode=mode, priority=True)

        # the backend records one trace entry per LLM call in database 2
        replayed = collections.Counter()
        db = redis.Redis(host="localhost", port=6379, db=2, decode_responses=True)
        for key in db.keys("*"):
            persona, step = key.split(":")
            replayed[(persona, int(step))] = db.get(key).count("__TRACE__") + 1
        positions = {p: sim.env.get_persona_position(p) for p in sim.env.persona_names}
        return replayed, positions

    def expected_calls(self):
        calls = collections.Counter()
        for step, personas in self.traces.items():
            for persona, funcs in personas.items():
                if funcs:
                    calls[(persona, int(step))] = len(funcs)
        return calls

    def test_all_modes_replay_the_same_calls_and_reach_the_same_state(self):
        expected = self.expected_calls()
        self.assertGreater(sum(expected.values()), 50)
        final = {p: tuple(m[TARGET_STEP]) for p, m in self.movements.items()}
        for mode in ("single-thread", "sync", "async", "oracle"):
            with self.subTest(mode=mode):
                replayed, positions = self.replay(mode)
                self.assertEqual(replayed, expected)
                self.assertEqual(positions, final)

    def test_critical_mode_replays_a_subset(self):
        replayed, positions = self.replay("critical")
        expected = self.expected_calls()
        self.assertTrue(replayed)
        for key, count in replayed.items():
            self.assertEqual(count, expected[key])
        self.assertEqual(positions, {p: tuple(m[TARGET_STEP]) for p, m in self.movements.items()})


if __name__ == "__main__":
    unittest.main()
