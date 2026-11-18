"""Checks for the shared-generation fork and final-answer baseline boundary."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rsa_formalizer.bobcat.records import ReplayRecords
from rsa_formalizer import pipeline
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.baselines.final_answer_only import reports
from rsa_formalizer.stages.baselines.final_answer_only import comparison as final_comparison
from rsa_formalizer.stages.validation import verification
from rsa_formalizer.stages.reasoning_structure_alignment import provision_repair, provision_testing
from rsa_formalizer.stages.reasoning_structure_alignment import experiment


class PairedProvisionTest(unittest.TestCase):
    def test_baseline_repair_keeps_case_without_target_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            base = run / "provision_repair"
            snapshot = base / "analysis/snapshot"
            snapshot.mkdir(parents=True)
            (snapshot / "law.catala_en").write_text("before")
            (run / "workspace").mkdir()
            (run / "workspace/law.catala_en").write_text("after")
            case = {"id": "one", "source": "law.catala_en", "target": "Answer"}
            result = {"target": {"provision_id": "law/a", "blocks": []},
                      "status": "accepted", "accepted_tests": [{"case": case,
                      "reasoning": {"id": "one", "output_text": '<answer>{"result":1}</answer>'}}]}
            exp.atomic_json(base / "formats.json", {"scopes": []})
            exp.atomic_json(base / "plan.json", {"targets": [result["target"]],
                                               "generation_format": provision_testing.FORMAT})
            exp.atomic_json(base / "tests.json", {"results": [result]})
            exp.atomic_json(base / "computation_oracles.json", {"cases": {
                "one": {"status": "complete", "graph": {"nodes": []}}}})
            state = {"provision_phase": "compare", "completed_stages": ["initialized"]}
            config = {"repair": {"mode": "baseline_final_answer_only",
                                 "computation_graph_alignment": {"enabled": False}}}
            symbolic = [{**case, "inputs": {}, "output": {"result": 2}, "error": None}]
            summary = {"total": 1, "final_answers_aligned": 0,
                       "cases": [{"id": "one", "final_answer_aligned": False,
                                  "catala_answer": {"result": 2},
                                  "llm_final_answer": {"result": 1}}]}
            with mock.patch.object(provision_repair, "replay_compiled", return_value=symbolic), \
                 mock.patch("rsa_formalizer.stages.baselines.final_answer_only.comparison.compare",
                            return_value=summary) as compared, \
                 mock.patch("rsa_formalizer.stages.formalization.run"), \
                 mock.patch("rsa_formalizer.stages.validation.run"), \
                 mock.patch.object(provision_repair.exp, "publish_stage_snapshot"), \
                 mock.patch("rsa_formalizer.stages.reasoning_structure_alignment.artifact_retention.prune_completed"):
                for expected_phase in ("agent", "evaluate", "finished"):
                    self.assertEqual(provision_repair.run(run, config, state)["provision_phase"],
                                     expected_phase)
            self.assertEqual(compared.call_count, 2)
            self.assertEqual(compared.call_args_list[0].args[3][0]["id"], "one")
            self.assertNotIn("computation_graph", compared.call_args_list[0].args[3][0])
            self.assertEqual(exp.load_json(base / "summary.json")["accepted_cases"], 1)

    def test_baseline_comparator_ignores_computation_and_trace_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            exp.atomic_json(stage / "tests_bobcat_symbolic_results/input_formats.json", {
                "scopes": [{"file": "law.catala_en", "compiler_file": "law.catala_en",
                            "scope": "Answer", "input_schema": {"type": "object"},
                            "output_schema": {"type": "object", "required": ["result"],
                                              "properties": {"result": {"type": "integer"}}}}]})
            symbolic = [{"id": "one", "source": "law.catala_en", "target": "Answer",
                         "inputs": {}, "output": {"result": 2}, "error": None,
                         "execution_tree": [{"unrelated": "trace"}]}]
            natural = [{"id": "one", "output_text": '<answer>{"result":1}</answer>',
                        "computation_graph": {"graph": {"nodes": ["must be ignored"]}}}]
            result = final_comparison.compare(stage, {"_stage_directory": str(stage)},
                                              symbolic, natural)
            self.assertEqual(result["final_answers_misaligned"], 1)
            self.assertNotIn("computation_graph_alignment", result["cases"][0])
            self.assertNotIn("provision_alignment", result["cases"][0])

    def test_validation_reads_gold_suite_and_ignores_raw_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            gold = root / "gold"
            snapshot = root / "run/initial/snapshot"
            for path in (raw / "tests_catala", gold / "tests_catala", snapshot):
                path.mkdir(parents=True)
            (raw / "tests_catala/Decoy.catala_en").write_text(
                "#[test]\ndeclaration scope Decoy:\n")
            (gold / "tests_catala/Good.catala_en").write_text(
                "#[test]\ndeclaration scope Good:\n")
            (snapshot / "law.catala_en").write_text("frozen")
            config = {"dataset": {"name": "law", "source": str(raw)},
                      "runtime": {"timeout_seconds": 30},
                      "validation_suite_sha256": exp.tree_hash(gold / "tests_catala")}
            report = json.dumps({"test-results": [{"file": "Good.catala_en",
                "tests": {"scopes": [{"scope_name": "Good", "success": True, "errors": []}]}}]})
            state = {"completed_stages": [], "recursive_phase": "initial"}
            with mock.patch.object(verification, "resolve_gold_dataset", return_value=gold), \
                 mock.patch.object(verification, "publish_stage_snapshot", return_value=snapshot), \
                 mock.patch.object(verification, "extract_input_formats", return_value={"scopes": []}), \
                 mock.patch.object(verification, "validate_requirement_scope_outputs", return_value=None), \
                 mock.patch.object(verification.subprocess, "run",
                                   return_value=subprocess.CompletedProcess([], 0, report, "")) as executed:
                self.assertTrue(verification.run_verification_stage(root / "run", config, state))
            self.assertIn("Good.catala_en", executed.call_args.args[0])
            self.assertNotIn("Decoy.catala_en", executed.call_args.args[0])

    def test_main_drive_stops_at_shared_fork_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            exp.atomic_json(run / "state.json", {"next_stage": "provision_repair", "status": "ready"})

            def advance(path):
                state = {"next_stage": "fork_ready", "provision_phase": "fork_ready",
                         "status": "fork_ready"}
                exp.atomic_json(path / "state.json", state)
                return state

            with mock.patch.object(pipeline, "resume_run", side_effect=advance) as resumed:
                result = pipeline.drive(run)
            self.assertEqual(result["next_stage"], "fork_ready")
            resumed.assert_called_once()

    def test_forks_copy_identical_evidence_and_have_independent_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / "20261116-1010-initial-model-law"
            base = shared / "provision_repair"
            for part in (shared / "input", shared / "workspace", base / "analysis/snapshot"):
                part.mkdir(parents=True)
                (part / "law.catala_en").write_text("frozen")
            exp.atomic_json(shared / "state.json", {"provision_phase": "fork_ready", "provision_total": 1})
            (shared / "initial").mkdir()
            exp.atomic_json(shared / "config.json", {
                "run_id": shared.name, "dataset": {"name": "law"},
                "validation_suite_sha256": "frozen-suite",
                "repair": {"mode": "provision_shared", "generation_format": provision_testing.FORMAT,
                           "computation_graph_alignment": {"enabled": True}}})
            for name in ("plan.json", "formats.json", "tests.json", "computation_oracles.json"):
                exp.atomic_json(base / name, {})
            runs = root / "runs"
            runs.mkdir()
            with mock.patch.object(experiment.exp, "RUNS", runs):
                graph = experiment.fork(shared, "reasoning_structure_alignment")
                baseline = experiment.fork(shared, "baseline_final_answer_only")
            self.assertEqual(exp.tree_hash(graph / "workspace"), exp.tree_hash(baseline / "workspace"))
            self.assertEqual(exp.load_json(graph / "config.json")["repair"]["mode"],
                             "reasoning_structure_alignment")
            self.assertEqual(exp.load_json(baseline / "config.json")["repair"]["mode"],
                             "baseline_final_answer_only")
            self.assertFalse(exp.load_json(baseline / "config.json")["repair"]
                             ["computation_graph_alignment"]["enabled"])
            self.assertEqual(set(exp.load_json(shared / "forks.json")), set(experiment.MODES))
            self.assertTrue((graph / "run.sh").is_file())

    def test_three_valid_inputs_survive_until_branch_selection(self):
        target = {"provision_id": "law/section1", "blocks": []}
        tests = [{"attempt": n, "case": {"id": f"case-{n}"},
                  "reasoning": {"output_text": "<answer>{}</answer>"}} for n in range(3)]
        result = {"target": target, "accepted_tests": tests, "attempts": [], "status": "accepted"}
        oracles = {"case-0": {"status": "complete", "graph": {"nodes": []}},
                   "case-1": {"status": "extraction_error"},
                   "case-2": {"status": "extraction_error"}}
        with mock.patch("rsa_formalizer.stages.reasoning_structure_alignment.computation_alignment.target_application",
                        side_effect=[{"status": "not_applied", "reason": "absent"},
                                     {"status": "uncertain"}, {"status": "uncertain"}]):
            graph_selected = provision_testing.select_by_computation_graph([result], oracles)
        self.assertEqual(len(result["accepted_tests"]), 3)
        self.assertEqual([t["case"]["id"] for t in graph_selected[0]["accepted_tests"]],
                         ["case-1", "case-2"])

    def test_execution_error_is_excluded_without_consulting_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for case_id, error in (("good", None), ("bad", "Catala failed")):
                exp.atomic_json(base / f"{case_id}.json",
                                {"id": case_id, "output": {"result": 1} if not error else None,
                                 "error": error})
            results = [{"target": {"provision_id": "law/a"}, "status": "accepted",
                        "accepted_tests": [{"case": {"id": name}} for name in ("good", "bad")]}]
            retained, records = provision_repair.retain_executable(
                base, results, ReplayRecords([base / "good.json", base / "bad.json"]))
            self.assertEqual([t["case"]["id"] for t in retained[0]["accepted_tests"]], ["good"])
            self.assertEqual([r["id"] for r in records], ["good"])
            self.assertEqual(exp.load_json(base / "execution_exclusions.json"),
                             {"bad": "Catala failed"})

    def test_baseline_report_contains_only_final_answer_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test = {"case": {"id": "case", "inputs": {"x": 1}},
                    "reasoning": {"output_text": "The result is 1."}}
            results = [{"target": {"provision_id": "law/a", "blocks": []},
                        "status": "accepted", "accepted_tests": [test]}]
            summary = {"cases": [{"id": "case", "final_answer_aligned": False,
                                  "catala_answer": {"x": 2}, "llm_final_answer": {"x": 1},
                                  "computation_graph_alignment": {"value_mismatches": ["secret"]}}]}
            index = reports.write_reports(root, results, summary)
            report = exp.load_json(root / "feedback" / index["reports"][0]["report"])
            self.assertNotIn("computation_graph_alignment", json.dumps(report))
            self.assertTrue(report["answer_misaligned"])


if __name__ == "__main__":
    unittest.main()
