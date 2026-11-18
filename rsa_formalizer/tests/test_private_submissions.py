from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.validation import submissions
from rsa_formalizer.stages.reasoning_structure_alignment import candidate_review as rsa_review
from rsa_formalizer.stages.baselines.final_answer_only import candidate_review as baseline_review


class PrivateSubmissionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run = Path(temporary.name) / "run"
        for name in ("input", "workspace"):
            path = self.run / name
            path.mkdir(parents=True)
            (path / "law.catala_en").write_text("original source")
        exp.atomic_json(self.run / "state.json", {"status": "running", "next_stage": "provision_repair"})
        self.summary = {"total": 97, "passed": 84, "failed": 13,
                        "errors": 0, "skipped": 0, "accuracy": 84 / 97}

    def verify(self, run, config, state):
        self.assertNotEqual(run, self.run)
        self.assertEqual((run / "snapshot/law.catala_en").read_text(), "original source")
        (self.run / "workspace/law.catala_en").write_text("later edit while scoring")
        exp.atomic_json(run / "validation/results.json", {"summary": self.summary})
        exp.atomic_json(run / "state.json", {"status": "verified"})

    def test_snapshot_score_logs_and_rollout_are_private_and_live_state_is_unchanged(self):
        agent = self.run / "provision_repair/session/agent"
        agent.mkdir(parents=True)
        (agent / "stdout.jsonl").write_text('{"type":"thread.started","thread_id":"example"}\n')
        home = self.run / "runtime/agent-home"
        sessions = home / ".codex/sessions/2026/11/18"
        sessions.mkdir(parents=True)
        (sessions / "rollout-example.jsonl").write_text("saved conversation")
        counts = {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}
        exp.atomic_json(agent / "codex_token_usage.json", counts)
        before = (self.run / "state.json").read_bytes()
        with mock.patch.object(submissions, "run_verification_stage", side_effect=self.verify), \
             mock.patch.object(submissions.usage, "capture_codex_usage"):
            result = submissions.record(self.run, {"repair": {"mode": "reasoning_structure_alignment"}},
                                        self.run / "workspace", trigger="replay", agent_home=home)
        self.assertIsNone(result)
        private = self.run / "private_submissions/submission-0001"
        record = exp.load_json(private / "record.json")
        self.assertEqual(record["validation"], self.summary)
        self.assertEqual(record["token_usage"], counts)
        self.assertEqual((private / "snapshot/law.catala_en").read_text(), "original source")
        self.assertEqual((private / "agent_home/.codex/sessions/2026/11/18/rollout-example.jsonl").read_text(), "saved conversation")
        self.assertEqual((private / "stdout.jsonl").read_bytes(), (agent / "stdout.jsonl").read_bytes())
        self.assertEqual((self.run / "state.json").read_bytes(), before)
        self.assertFalse((self.run / "provision_repair/feedback").exists())

    def test_repeat_submissions_are_separate_records(self):
        def verify(run, config, state):
            exp.atomic_json(run / "validation/results.json", {"summary": self.summary})
        with mock.patch.object(submissions, "run_verification_stage", side_effect=verify) as score:
            for _ in range(2):
                submissions.record(self.run, {}, self.run / "workspace", trigger="replay")
        index = exp.load_json(self.run / "private_submissions/index.json")["submissions"]
        self.assertEqual(score.call_count, 2)
        self.assertEqual([row["submission"] for row in index], [1, 2])
        self.assertEqual(index[0]["snapshot_sha256"], index[1]["snapshot_sha256"])

    def test_scoring_failure_is_recorded_without_agent_feedback(self):
        with mock.patch.object(submissions, "run_verification_stage", side_effect=RuntimeError("private diagnostic")):
            self.assertIsNone(submissions.record(self.run, {}, self.run / "workspace", trigger="submission_check"))
        row = exp.load_json(self.run / "private_submissions/submission-0001/record.json")
        self.assertEqual(row["status"], "error")
        self.assertIsNone(row["validation"])
        self.assertIn("private diagnostic", row["error"])

    def test_both_review_modes_record_cached_submissions_without_changing_public_response(self):
        # A cached replay still represents a new submission. Its private score
        # must not appear in the response or read-only feedback tree.
        for review in (rsa_review, baseline_review):
            with self.subTest(review=review.__name__), tempfile.TemporaryDirectory() as directory:
                run = Path(directory)
                (run / "workspace").mkdir()
                (run / "workspace/law.catala_en").write_text("source")
                exp.copy_project(run / "workspace", run / "input")
                prior = run / "provision_repair/session/candidate_reviews/attempt-1"
                exp.copy_project(run / "workspace", prior / "snapshot")
                exp.atomic_json(prior / "tests_bobcat_symbolic_results/build_errors.json", {})
                report = {"reviewed_cases": 382, "candidate_final_answers_aligned": 313,
                          "remaining_case_ids": [],
                          "evidence_index": "/rsa/feedback/replays/attempt-1/index.json"}
                exp.atomic_json(prior / "review.json", report)
                exp.atomic_json(run / "provision_repair/feedback/replays/attempt-1/index.json", {})
                def verify(private_run, config, state):
                    exp.atomic_json(private_run / "validation/results.json", {"summary": self.summary})

                with mock.patch.object(exp, "validate_workspace"), \
                     mock.patch.object(submissions, "run_verification_stage", side_effect=verify), \
                     mock.patch.object(submissions, "record", wraps=submissions.record) as record:
                    self.assertEqual(review.review(run, {}), report)
                record.assert_called_once()
                snapshot = record.call_args.args[2]
                self.assertEqual(snapshot.name, "snapshot")
                self.assertEqual(record.call_args.kwargs["trigger"], "replay")
                private = exp.load_json(run / "private_submissions/submission-0001/record.json")
                self.assertEqual(private["validation"], self.summary)
                feedback = run / "provision_repair/feedback"
                self.assertFalse(list(feedback.rglob("results.json")))


if __name__ == "__main__":
    unittest.main()
