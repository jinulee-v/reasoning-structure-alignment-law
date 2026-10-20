import json
import tempfile
import unittest
from pathlib import Path

from bobcatlib import branches, coverage, dataset, paths
from bobcatlib.coverage import Position
from bobcatlib.parse import parse_run


class NativeCoverageTest(unittest.TestCase):
    def test_index_prunes_targets_removed_from_automatic_census(self):
        old_dataset = paths.dataset
        with tempfile.TemporaryDirectory() as directory:
            paths.dataset = lambda port: Path(directory)
            try:
                for name in ("automatic", "obsolete_custom"):
                    (Path(directory) / f"{name}.jsonl").write_text("\n")
                common = {
                    "port": "sara", "scope": "S", "harness": "h",
                    "modules": [], "note": "", "command": [],
                    "coverage_file": None, "coverage_paths": 0, "paths": 0,
                    "repeated_inputs": 0, "distinct_outputs": 0,
                    "errors": 0, "inexact": 0, "unparsed": 0,
                    "finished": True, "incomplete": False,
                    "timed_out": False, "returncode": 0, "seconds": 0,
                }
                old_entries = [
                    {**common, "name": name, "file": f"{name}.jsonl"}
                    for name in ("automatic", "obsolete_custom")
                ]
                (Path(directory) / "INDEX.json").write_text(json.dumps({
                    "targets": old_entries,
                }))
                index = dataset.write_index(
                    "sara", [], valid_names={"automatic"})
                self.assertEqual(
                    [entry["name"] for entry in index["targets"]],
                    ["automatic"],
                )
            finally:
                paths.dataset = old_dataset

    def test_statement_attribution_accepts_french_catala_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "loi.catala_fr"
            source.write_text(
                "```catala\n"
                "declaration résultat content boolean equals true\n"
                "```\n")
            pos = Position("loi.catala_fr", 2, 1, 2, 12)
            attributed = coverage.attribute({pos: True}, [Path(directory)])
            self.assertIn("loi.catala_fr", attributed)
            self.assertEqual(attributed["loi.catala_fr"][0].positions, 1)
            self.assertEqual(attributed["loi.catala_fr"][0].reached, 1)

    def test_result_stream_attaches_coverage_to_its_path(self):
        run = parse_run("""
[RESULT] CONCOLIC_COVERAGE_REACHABLE aa
[RESULT] CONCOLIC_COVERAGE_INITIAL bb
[RESULT] CONCOLIC_BRANCH_MANIFEST ["d/o1","d/o2"]
[RESULT] Evaluating with inputs:
[RESULT] . input_in = true
[RESULT] Output of scope after evaluation:
[RESULT] . output = false
[RESULT] CONCOLIC_COVERAGE_PATH 0 cc
[RESULT] CONCOLIC_BRANCH_PATH 0 ["d/o2"]
[RESULT] CONCOLIC_BRANCH_PROGRESS 0 1.250000 1 2
[RESULT] Concolic interpreter done
""")
        self.assertEqual(run.coverage_reachable, "aa")
        self.assertEqual(run.coverage_initial, "bb")
        self.assertEqual(run.paths[0].coverage, "cc")
        self.assertEqual(run.branch_manifest, ["d/o1", "d/o2"])
        self.assertEqual(run.paths[0].branches, ["d/o2"])
        self.assertEqual(run.paths[0].coverage_seconds, 1.25)
        self.assertEqual(run.paths[0].branches_covered, 1)
        self.assertEqual(run.paths[0].branches_total, 2)
        self.assertTrue(run.finished)
        self.assertEqual(run.unparsed, [])

    def test_final_incompleteness_warning_is_preserved(self):
        run = parse_run(
            "[RESULT] Concolic interpreter done\n",
            "[WARNING] Please note that the concolic execution may be "
            "incomplete: a solver candidate was dropped.\n",
        )
        self.assertTrue(run.incomplete)

    def test_empty_manifest_means_branchless_not_missing(self):
        run = parse_run(
            "[RESULT] CONCOLIC_BRANCH_MANIFEST []\n"
            "[RESULT] Concolic interpreter done\n"
        )
        self.assertEqual(run.branch_manifest, [])
        self.assertIsNone(parse_run("[RESULT] Concolic interpreter done\n")
                          .branch_manifest)

    def test_native_loader_returns_only_rows_missing_a_dump(self):
        old = paths.coverage
        with tempfile.TemporaryDirectory() as directory:
            paths.coverage = lambda port: Path(directory)
            try:
                records = [
                    {"kind": "reachable", "coverage": "aa"},
                    {"kind": "initial", "coverage": "bb"},
                    {"kind": "path", "path": 0, "coverage": "cc"},
                ]
                (Path(directory) / "sample.jsonl").write_text(
                    "".join(json.dumps(r) + "\n" for r in records))
                rows = [{"path": 0}, {"path": 1}]
                dumps, missing = coverage.native_dumps("sara", "sample",
                                                       rows)
                self.assertEqual(dumps, ["aa", "bb", "cc"])
                self.assertEqual(missing, [{"path": 1}])
            finally:
                paths.coverage = old

    def test_native_branch_trace_uses_exact_source_outcomes(self):
        old = paths.coverage
        with tempfile.TemporaryDirectory() as directory:
            paths.coverage = lambda port: Path(directory)
            try:
                pair1 = ("if@law/main.catala_en:10:2-10:30/"
                         "branch@law/main.catala_en:10:20-10:21")
                pair2 = ("if@law/main.catala_en:10:2-10:30/"
                         "branch@law/main.catala_en:10:28-10:29")
                # A different source decision may legitimately reuse an
                # outcome span. Exact IDs must not collapse it.
                pair3 = ("match@law/main.catala_en:9:1-11:30/"
                         "branch@law/main.catala_en:10:20-10:21")
                records = [
                    {"kind": "branch_manifest",
                     "branches": [pair1, pair2, pair3]},
                    {"kind": "branch_path", "path": 0,
                     "branches": [pair2]},
                ]
                (Path(directory) / "sample.jsonl").write_text(
                    "".join(json.dumps(r) + "\n" for r in records))
                manifest, reached = branches.native_trace("sara", "sample")
                self.assertEqual(manifest, {pair1, pair2, pair3})
                self.assertEqual(reached, {pair2})
                self.assertEqual(branches.native_positions(manifest), {
                    Position("law/main.catala_en", 10, 20, 10, 21),
                    Position("law/main.catala_en", 10, 28, 10, 29),
                })
                self.assertEqual(branches.native_totals(manifest, reached), {
                    "decisions": 2,
                    "decisions_full": 0,
                    "decisions_partial": 1,
                    "outcomes": 3,
                    "outcomes_covered": 1,
                })
            finally:
                paths.coverage = old

    def test_replay_refinement_is_machine_readable(self):
        run = parse_run(
            '[RESULT] BOBCAT_REFINEMENT {"input":{"x":1},'
            '"predicted":["d/o1"],"observed":[],'
            '"reason":"prediction mismatch"}\n'
        )
        self.assertEqual(len(run.refinements), 1)
        self.assertEqual(run.refinements[0]["predicted"], ["d/o1"])

    def test_bobcat_timing_is_machine_readable(self):
        run = parse_run(
            '[RESULT] BOBCAT_TIMING {"phase":"slice_compilation",'
            '"objectives":["d/o1"],"cpu_ms":12.5}\n'
        )
        self.assertEqual(run.timings, [{
            "phase": "slice_compilation",
            "objectives": ["d/o1"],
            "cpu_ms": 12.5,
        }])
        self.assertEqual(run.unparsed, [])


if __name__ == "__main__":
    unittest.main()
