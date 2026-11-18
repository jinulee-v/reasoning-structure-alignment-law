from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment import artifact_retention


class ArtifactRetentionTest(unittest.TestCase):
    def test_completed_run_prunes_only_reproducible_data_and_restores_a_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            base = run / "provision_repair"
            case = {"id": "case-1", "source": "law.catala_en", "target": "Answer",
                    "inputs": {}, "branches": [], "statute_ids": []}
            exp.atomic_json(run / "state.json", {"status": "completed", "provision_phase": "finished"})
            exp.atomic_json(run / "config.json", {"repair": {"mode": "reasoning_structure_alignment"}})
            exp.atomic_json(base / "summary.json", {"validation": {"passed": 1}})
            exp.atomic_json(base / "executable_tests.json", {"results": [{
                "target": {"provision_id": "law/section1"}, "status": "accepted",
                "accepted_tests": [{"case": case, "reasoning": {"id": "case-1"}}]}]})
            exp.atomic_json(base / "computation_oracles.json", {"cases": {"case-1": {}}})
            exp.atomic_json(base / "before.json", {"final_answers_aligned": 1})
            exp.atomic_json(base / "after.json", {"final_answers_aligned": 1})
            stage = base / "analysis"
            (stage / "snapshot").mkdir(parents=True)
            (stage / "snapshot/law.catala_en").write_text("law")
            replay = stage / "tests_bobcat_symbolic_results"
            exp.atomic_json(replay / "input_formats.json", {"scopes": []})
            exp.atomic_json(replay / "case-1.json", {"execution_tree": ["large"]})
            (replay / "project").mkdir()
            (replay / "project/compiled").write_text("compiled")
            exp.atomic_json(stage / "tests_bobcat_comparison/summary.json", {"cases": ["large"]})
            feedback = base / "feedback" / "law" / "case-1"
            exp.atomic_json(feedback / "report.json", {"case": case})
            exp.atomic_json(feedback / "catala_replay.json", {"execution_tree": ["large"]})
            private = run / "private_submissions/submission-0001"
            exp.atomic_json(private / "record.json", {"validation": {"passed": 1}})
            exp.atomic_json(private / "validation/results.json", {"summary": {"passed": 1}})
            (private / "snapshot").mkdir()
            (private / "snapshot/law.catala_en").write_text("submitted law")

            manifest = artifact_retention.prune_completed(run)
            self.assertGreater(manifest["removed_bytes"], 0)
            for retained in (replay / "input_formats.json", stage / "snapshot/law.catala_en",
                             base / "executable_tests.json", base / "before.json",
                             feedback / "report.json", base / "summary.json",
                             private / "record.json", private / "validation/results.json",
                             private / "snapshot/law.catala_en"):
                self.assertTrue(retained.is_file(), retained)
            for removed in (replay / "case-1.json", replay / "project/compiled",
                            stage / "tests_bobcat_comparison/summary.json",
                            feedback / "catala_replay.json"):
                self.assertFalse(removed.exists(), removed)

            symbolic = {"case-1": {"id": "case-1", "output": {"result": 1}}}
            with mock.patch.object(artifact_retention, "replay_compiled", return_value=symbolic), \
                 mock.patch("rsa_formalizer.bobcat.comparison.compare",
                            return_value={"final_answers_aligned": 1}):
                result = artifact_retention.restore(run, "analysis")
            self.assertEqual(result["cases"], 1)
            self.assertEqual(exp.load_json(feedback / "catala_replay.json"), symbolic["case-1"])

    def test_incomplete_run_cannot_be_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            exp.atomic_json(run / "state.json", {"status": "running", "provision_phase": "evaluate"})
            with self.assertRaisesRegex(exp.RunnerError, "completed run"):
                artifact_retention.prune_completed(run)
