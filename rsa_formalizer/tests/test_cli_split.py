"""Naming and phase boundaries for the two public experiment entry points."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from rsa_formalizer import main_initial, main_repair
from rsa_formalizer import pipeline
from rsa_formalizer.agents import apptainer
from rsa_formalizer.utils.run_names import initial_name, repair_name
from rsa_formalizer.stages import utils as exp, formalization
from rsa_formalizer.stages.reasoning_structure_alignment import experiment


class SplitCliTest(unittest.TestCase):
    def test_repair_inherits_initial_timestamp_model_dataset_and_suffix(self):
        name = initial_name("openai/gpt-6-luna", "sara", "trial-2", timestamp="20261117-1234")
        self.assertEqual(name, "20261117-1234-initial-openai-gpt-6-luna-sara-trial-2")
        self.assertEqual(repair_name(name, "reasoning_structure_alignment"),
                         "20261117-1234-repair-reasoning-structure-alignment-openai-gpt-6-luna-sara-trial-2")
        self.assertEqual(repair_name(name, "baseline_final_answer_only"),
                         "20261117-1234-repair-baseline-final-answer-only-openai-gpt-6-luna-sara-trial-2")
        for suffix in ("../bad", "/absolute", "contains space"):
            with self.assertRaises(exp.RunnerError):
                initial_name("model", "sara", suffix)
        with self.assertRaises(exp.RunnerError):
            repair_name("arbitrary-run", "reasoning_structure_alignment")

    def test_repair_cli_rejects_naming_and_generation_options(self):
        base = ["start", "--from-run", "initial", "--mode", "reasoning-structure-alignment"]
        for option in ("--run-id", "--suffix", "--reasoning-trace-model", "--generation-jobs"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main_repair.argument_parser().parse_args(base + [option, "x"])
        args = main_repair.argument_parser().parse_args(base)
        self.assertFalse(args.filter_by_target_provision_reachability)
        self.assertEqual(args.replay_jobs, 4)
        args = main_repair.argument_parser().parse_args(base + ["--replay-jobs", "2"])
        self.assertEqual(args.replay_jobs, 2)
        for value in ("0", "-1"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main_repair.argument_parser().parse_args(base + ["--replay-jobs", value])
        args = main_repair.argument_parser().parse_args(base + ["--filter-by-target-provision-reachability"])
        self.assertTrue(args.filter_by_target_provision_reachability)
        args = main_repair.argument_parser().parse_args(base + ["--no-filter-by-target-provision-reachability"])
        self.assertFalse(args.filter_by_target_provision_reachability)

    def test_initial_finishes_generation_without_entering_repair(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            exp.atomic_json(run / "config.json", {"repair": {"mode": "initial_validation"}})
            exp.atomic_json(run / "state.json", {"next_stage": "formalization"})
            calls = []
            with mock.patch.object(pipeline, "drive", side_effect=lambda *a, **kw: calls.append(kw)), \
                 mock.patch.object(experiment, "prepare_initial", side_effect=lambda r: calls.append("prepare")):
                main_initial.complete_initial(run)
            self.assertEqual(calls, [{"until": "initial_validation"}, "prepare", {}])

    def test_prepare_and_fork_preserve_initial_records_and_usage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root / "20261117-1234-initial-model-law-example"
            suite = root / "gold/tests_catala"
            suite.mkdir(parents=True)
            (suite / "test.catala_en").write_text("protected")
            for part in ("initial/snapshot", "workspace", "input"):
                directory = run / part
                directory.mkdir(parents=True)
                (directory / "law.catala_en").write_text("original")
            exp.atomic_json(run / "input/RSA_MANIFEST.json", {})
            exp.atomic_json(run / "initial/validation/input_formats.json", {"candidate": {"scopes": []}})
            exp.atomic_json(run / "initial/validation/results.json", {"summary": {"passed": 1, "total": 1}})
            exp.atomic_json(run / "config.json", {"run_id": run.name, "dataset": {"name": "law"},
                "repair": {"mode": "initial_validation"}, "test_generation": {"jobs": 2, "graph_extraction_jobs": 3}})
            exp.atomic_json(run / "state.json", {"next_stage": "finished", "verification_summary": {"passed": 1}})
            with mock.patch.object(exp, "resolve_gold_dataset", return_value=suite.parent), \
                 mock.patch.object(experiment, "discover_targets", return_value=[{"provision_id": "law/one"}]):
                experiment.prepare_initial(run)
                config = exp.load_json(run / "config.json")
                self.assertEqual(config["repair"]["generation_jobs"], 2)
                self.assertEqual(config["repair"]["computation_graph_alignment"]["jobs"], 3)
                self.assertEqual(exp.load_json(run / "state.json")["provision_phase"], "generate")
                # Recover the interrupted config/state transition without another agent call.
                exp.atomic_json(run / "state.json", {"next_stage": "finished"})
                with mock.patch.object(pipeline, "drive"):
                    main_initial.complete_initial(run)
                self.assertEqual(exp.load_json(run / "state.json")["provision_phase"], "generate")
            exp.atomic_json(run / "state.json", {"provision_phase": "fork_ready", "provision_total": 1})
            for name in ("tests.json", "computation_oracles.json"):
                exp.atomic_json(run / "provision_repair" / name, {})
            event = {"usage_id": "api:one", "run_id": run.name, "total_tokens": 123}
            (run / "usage.jsonl").write_text(json.dumps(event) + "\n")
            (run / "run.log").write_text("original generation log\n")
            with mock.patch.object(exp, "RUNS", root):
                child = experiment.fork(run, "reasoning_structure_alignment")
            self.assertEqual(child.name, "20261117-1234-repair-reasoning-structure-alignment-model-law-example")
            self.assertTrue(exp.load_json(child / "config.json")["repair"]["require_case_diagnoses"])
            self.assertEqual((child / "usage.jsonl").read_text(), (run / "usage.jsonl").read_text())
            self.assertEqual((child / "initial/validation/results.json").read_bytes(),
                             (run / "initial/validation/results.json").read_bytes())
            self.assertIn("main_repair resume", (child / "run.sh").read_text())
            with mock.patch.object(exp, "RUNS", root), self.assertRaises(exp.RunnerError):
                experiment.fork(run, "reasoning_structure_alignment")

    def test_repair_options_are_saved_before_selection_runs(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            exp.atomic_json(run / "config.json", {
                "repair": {"mode": "reasoning_structure_alignment"}, "runtime": {"timeout_seconds": 10}})
            observed = []
            def resume(path):
                observed.append(exp.load_json(path / "config.json"))
                return {"status": "completed"}
            with mock.patch.object(main_repair, "load_dotenv"), \
                 mock.patch.object(experiment, "fork", return_value=run), \
                 mock.patch.object(main_repair, "complete_repair", side_effect=resume), \
                 redirect_stdout(io.StringIO()):
                result = main_repair.main(["start", "--from-run", "initial",
                    "--mode", "reasoning-structure-alignment",
                    "--no-filter-by-target-provision-reachability", "--timeout", "30",
                    "--replay-jobs", "2"])
            self.assertEqual(result, 0)
            self.assertFalse(observed[0]["repair"]["filter_by_target_provision_reachability"])
            self.assertEqual(observed[0]["runtime"]["timeout_seconds"], 30)
            self.assertEqual(observed[0]["execution"]["replay_jobs"], 2)
            self.assertIn("completed", (run / "run.log").read_text())

    def test_resume_saves_replay_jobs_before_running(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            exp.atomic_json(run / "config.json", {})
            def resume(path):
                self.assertEqual(exp.load_json(path / "config.json")["execution"]["replay_jobs"], 3)
                return {"status": "completed"}
            with mock.patch.object(main_repair, "load_dotenv"), \
                 mock.patch.object(main_repair, "complete_repair", side_effect=resume), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(main_repair.main(["resume", str(run), "--replay-jobs", "3"]), 0)

    def test_resume_disables_agent_deadline_without_disabling_tool_timeouts(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            exp.atomic_json(run / "config.json", {"runtime": {"timeout_seconds": 7200}})
            def resume(path):
                runtime = exp.load_json(path / "config.json")["runtime"]
                self.assertIsNone(runtime["agent_timeout_seconds"])
                self.assertEqual(runtime["timeout_seconds"], 7200)
                return {"status": "completed"}
            with mock.patch.object(main_repair, "load_dotenv"), \
                 mock.patch.object(main_repair, "complete_repair", side_effect=resume), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(main_repair.main(["resume", str(run), "--timeout", "0"]), 0)

    def test_recover_usage_keeps_inherited_physical_initial_call(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as d:
                run = Path(d)
                exp.atomic_json(run / "initial/agent/invocation.json", {"session_id": "initial-session"})
                row = {"run_id": "parent", "session_id": "initial-session",
                       "usage_id": "agent:initial-session", "total_tokens": 123}
                if legacy:
                    row.update(run_id="child", usage_id="inherited:parent:agent:initial-session",
                               source_session_id="initial-session")
                (run / "usage.jsonl").write_text(json.dumps(row) + "\n")
                with mock.patch.object(formalization, "record_agent_usage") as record:
                    formalization.recover_agent_usage(run, {"run_id": "child"})
                record.assert_not_called()

    def test_resume_dispatches_initial_formalization_and_both_repair_methods(self):
        for mode in ("initial_validation", "reasoning_structure_alignment", "baseline_final_answer_only"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                run = Path(d)
                exp.atomic_json(run / "config.json", {"schema_version": exp.SCHEMA_VERSION,
                    "run_id": run.name, "reasoning_trace": {"jobs": 8}, "repair": {"mode": mode}})
                state = {"schema_version": exp.SCHEMA_VERSION, "run_id": run.name,
                         "next_stage": "formalization" if mode == "initial_validation" else "provision_repair"}
                exp.atomic_json(run / "state.json", state)
                if mode == "initial_validation":
                    handler = "rsa_formalizer.stages.formalization.run"
                elif mode == "reasoning_structure_alignment":
                    handler = "rsa_formalizer.stages.reasoning_structure_alignment.provision_repair.run"
                else:
                    handler = "rsa_formalizer.stages.baselines.final_answer_only.provision_repair.run"
                with mock.patch.object(pipeline.formalization, "recover_agent_usage"), \
                     mock.patch(handler, return_value=state) as execute:
                    self.assertEqual(pipeline.resume_run(run), state)
                execute.assert_called_once()
                self.assertEqual(execute.call_args.args[0], run)

    def test_candidate_replay_helper_is_available_from_utils(self):
        self.assertTrue(apptainer.REPLAY_CANDIDATE_HELPER_SOURCE.is_file())
        self.assertEqual(apptainer.REPLAY_CANDIDATE_HELPER_SOURCE.parent.name, "utils")

    def test_initial_and_repair_resume_reject_wrong_phase(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            exp.atomic_json(run / "config.json", {"repair": {"mode": "reasoning_structure_alignment"}})
            with self.assertRaisesRegex(exp.RunnerError, "main_repair"):
                main_initial.complete_initial(run)
            exp.atomic_json(run / "config.json", {"repair": {"mode": "provision_shared"}})
            with self.assertRaisesRegex(exp.RunnerError, "main_initial"):
                main_repair.complete_repair(run)


if __name__ == "__main__":
    unittest.main()
