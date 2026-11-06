"""Unit tests that need neither Redis nor an LLM server: python -m unittest discover tests"""
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import aimetropoliscpp  # noqa: F401
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

REPO = Path(__file__).resolve().parents[1]


def load_download_script():
    spec = importlib.util.spec_from_file_location("dataset_download", REPO / "dataset" / "download.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((REPO / "dataset" / "MANIFEST.json").read_text())

    def test_archives_cover_every_file(self):
        files = self.manifest["files"]
        self.assertEqual(sum(a["files"] for a in self.manifest["archives"].values()), len(files))
        for path, entry in files.items():
            self.assertRegex(path, r"^(replay|raw)/")
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_every_world_has_files_and_a_listed_source(self):
        files = self.manifest["files"]
        for status, count in (("busy", 40), ("quiet", 56)):
            worlds = self.manifest["worlds"][status]
            self.assertEqual(len(worlds), count)
            for world, record in worlds.items():
                self.assertIn(f"replay/{status}/{world}_trace.json", files)
                self.assertIn(f"replay/{status}/{world}_movement.json", files)
                self.assertIn(record["source"], files)
                self.assertIn(record["source"].replace("_llm.json", "_location.json"), files)

    def test_repeated_worlds_really_are_identical(self):
        files = self.manifest["files"]
        for status, worlds in self.manifest["worlds"].items():
            for world, record in worlds.items():
                if "same_trace_as_world" in record:
                    other = record["same_trace_as_world"]
                    self.assertEqual(files[f"replay/{status}/{world}_trace.json"]["sha256"],
                                     files[f"replay/{status}/{other}_trace.json"]["sha256"])


class DownloadTest(unittest.TestCase):

    def make_archive(self, directory, members):
        path = Path(directory) / "archive.tar.xz"
        with tarfile.open(path, "w:xz") as tar:
            for name, payload in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
        return path

    def selected_archives(self, *argv):
        download = load_download_script()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(download, "fetch") as fetch, \
                mock.patch.object(download, "unpack", return_value=0), \
                mock.patch("builtins.print"), \
                mock.patch("sys.argv", ["download.py", "--output", directory, "--keep-archives", *argv]):
            download.main()
        return [call.args[1].name for call in fetch.call_args_list]

    def test_defaults_to_the_replay_subset(self):
        self.assertEqual(self.selected_archives(), ["aimetropolis-replay-v1.tar.xz"])

    def test_selects_named_and_all_subsets(self):
        self.assertEqual(self.selected_archives("raw-hours"), ["aimetropolis-raw-hours-v1.tar.xz"])
        self.assertEqual(len(self.selected_archives("--all")), 3)

    def test_rejects_unknown_subsets(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()):
            self.selected_archives("nope")

    def test_unpack_verifies_and_writes_listed_files(self):
        download = load_download_script()
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_archive(directory, {"replay/a.json": b"{}"})
            digest = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
            count = download.unpack(path, Path(directory), {"replay/a.json": {"sha256": digest}})
            self.assertEqual(count, 1)
            self.assertEqual((Path(directory) / "replay" / "a.json").read_bytes(), b"{}")

    def test_unpack_rejects_unlisted_entries(self):
        download = load_download_script()
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_archive(directory, {"../escape.json": b"{}"})
            with self.assertRaises(SystemExit):
                download.unpack(path, Path(directory), {})
            self.assertFalse((Path(directory).parent / "escape.json").exists())

    def test_unpack_rejects_corrupted_content(self):
        download = load_download_script()
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_archive(directory, {"replay/a.json": b"tampered"})
            with self.assertRaises(SystemExit):
                download.unpack(path, Path(directory), {"replay/a.json": {"sha256": "0" * 64}})
            self.assertFalse((Path(directory) / "replay" / "a.json").exists())


@unittest.skipUnless(ENGINE_AVAILABLE, "aimetropoliscpp is not built")
class DependencyGraphTest(unittest.TestCase):

    def test_distant_agents_only_depend_on_themselves(self):
        from aimetropolis.utils import build_dependency_graph
        movements = {"a": [(0, 0)] * 4, "b": [(50, 50)] * 4}
        forward, reverse = build_dependency_graph(movements, 0, 3)
        self.assertEqual(forward["a:0"], ["a:1"])
        self.assertEqual(reverse["b:2"], ["b:1"])

    def test_agents_in_view_synchronize_before_and_after_the_step(self):
        from aimetropolis.utils import build_dependency_graph
        movements = {"a": [(0, 0), (0, 0), (0, 0)], "b": [(50, 50), (2, 0), (50, 50)]}
        forward, reverse = build_dependency_graph(movements, 0, 3)
        self.assertIn("a:0", reverse["b:1"])
        self.assertIn("b:0", reverse["a:1"])
        self.assertIn("a:2", forward["b:1"])
        self.assertIn("b:2", forward["a:1"])

    def test_critical_path_follows_the_heaviest_chain(self):
        from aimetropolis.utils import find_critical_path
        dag = {"a:0": ["a:1"], "a:1": [], "b:0": ["b:1"], "b:1": ["b:2"], "b:2": []}
        call = {"prompt": "long", "reference_output": "long"}
        traces = {str(step): {"b": [call]} for step in range(3)}
        traces["0"]["a"] = [{"prompt": "x", "reference_output": "x"}]
        with mock.patch("aimetropolis.utils.build_dependency.count_tokens", len), mock.patch("builtins.print"):
            self.assertEqual(find_critical_path(dag, traces), ["b:0", "b:1", "b:2"])


@unittest.skipUnless(ENGINE_AVAILABLE, "aimetropoliscpp is not built")
class ParsingTest(unittest.TestCase):

    def test_locations_are_parsed_without_evaluating_code(self):
        from aimetropolis.utils.parse_movements import change_format
        steps = {f"location:a:{i}": {"location": f"[{i}, 0]"} for i in range(5)}
        movements, _ = change_format(steps, 0, 3)
        self.assertEqual(movements["a"], [[0, 0], [1, 0], [2, 0], [3, 0]])
        steps["location:a:4"] = {"location": "__import__('os').getcwd()"}
        with self.assertRaises(ValueError):
            change_format(steps, 0, 3)

    def test_movement_gaps_are_filled_one_tile_at_a_time(self):
        from aimetropolis.utils.parse_movements import validation
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("builtins.print"):
                filled = validation({"a": [[0, 0], [2, 1]]}, os.path.join(directory, "m.json"))
        self.assertEqual(filled["a"], [[0, 0], [1, 0], [2, 0], [2, 1]])

    def test_raw_calls_become_replay_calls(self):
        from aimetropolis.utils import parse_traces
        raw = {
            "a:7:run_gpt_prompt_x:1.5": {"input": "in", "output": "out", "start_time": "1", "end_time": "2"},
            "run": {"first_name": "Peter"},
        }
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(parse_traces, "count_tokens", lambda text: 3), mock.patch("builtins.print"):
                traces = parse_traces.change_format(raw, 5, 10, os.path.join(directory, "t.json"))
        self.assertEqual(sorted(traces), [5, 6, 7, 8, 9])
        call = traces[7]["a"][0]
        self.assertEqual((call["func_name"], call["prompt"], call["reference_output"]), ("run_gpt_prompt_x", "in", "out"))
        self.assertEqual((call["max_tokens"], call["ignore_eos"], call["stop"]), (3, True, None))


@unittest.skipUnless(ENGINE_AVAILABLE, "aimetropoliscpp is not built")
class DatasetPathTest(unittest.TestCase):

    def test_override_and_missing_file_message(self):
        from aimetropolis.utils import replay_path
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {"AIMETROPOLIS_DATASET": directory}):
            with self.assertRaisesRegex(FileNotFoundError, "download.py"):
                replay_path("busy", "0_trace.json")
            target = Path(directory, "replay", "busy", "0_trace.json")
            target.parent.mkdir(parents=True)
            target.touch()
            self.assertEqual(replay_path("busy", "0_trace.json"), str(target))


@unittest.skipUnless(ENGINE_AVAILABLE, "aimetropoliscpp is not built")
class BackendTest(unittest.TestCase):

    def test_generate_forwards_arguments_and_retries_invalid_responses(self):
        from aimetropolis.backends import OpenAIBackend
        calls = []

        def fake_call(prompt, max_tokens, stop, ignore_eos, step, regex_constrain):
            calls.append((prompt, max_tokens, stop, ignore_eos, step, regex_constrain))
            return "no" if len(calls) == 1 else "7"

        with mock.patch.object(OpenAIBackend, "api_call", fake_call), mock.patch.object(OpenAIBackend, "INSTRUMENTATION", False):
            result = OpenAIBackend.generate("p", 2, step=3, stop="\n", regex_constrain=r"\d", trace_id="a:3")
        self.assertEqual(result, "7")
        self.assertEqual(calls, [("p", 2, "\n", False, 3, r"\d")] * 2)


if __name__ == "__main__":
    unittest.main()
