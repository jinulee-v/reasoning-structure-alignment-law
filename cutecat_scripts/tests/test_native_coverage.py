import json
import tempfile
import unittest
from pathlib import Path

from cutecatlib import coverage, paths
from cutecatlib.parse import parse_run


class NativeCoverageTest(unittest.TestCase):
    def test_result_stream_attaches_coverage_to_its_path(self):
        run = parse_run("""
[RESULT] CONCOLIC_COVERAGE_REACHABLE aa
[RESULT] CONCOLIC_COVERAGE_INITIAL bb
[RESULT] Evaluating with inputs:
[RESULT] . input_in = true
[RESULT] Output of scope after evaluation:
[RESULT] . output = false
[RESULT] CONCOLIC_COVERAGE_PATH 0 cc
[RESULT] Concolic interpreter done
""")
        self.assertEqual(run.coverage_reachable, "aa")
        self.assertEqual(run.coverage_initial, "bb")
        self.assertEqual(run.paths[0].coverage, "cc")
        self.assertTrue(run.finished)
        self.assertEqual(run.unparsed, [])

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


if __name__ == "__main__":
    unittest.main()
