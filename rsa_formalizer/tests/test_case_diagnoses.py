"""A repair cannot substitute an incomplete case list for a complete diagnosis."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from contextlib import contextmanager

from rsa_formalizer.stages import formalization
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment import case_diagnoses
from rsa_formalizer.stages.reasoning_structure_alignment import candidate_review


class CaseDiagnosesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.feedback = self.root / 'feedback'
        self.feedback.mkdir()
        (self.feedback / 'index.json').write_text(json.dumps({
            'reports': [{'case_id': 'case-a'}, {'case_id': 'case-b'}]}))
        self.path = self.root / case_diagnoses.FILENAME
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        (self.workspace / 'law.catala_en').write_text('current law')
        self.rows = [
            {'case_id': 'case-a', 'diagnosis': 'Catala uses the wrong threshold for this filer.',
             'classification': 'Catala wrong'},
            {'case_id': 'case-b', 'diagnosis': 'The input lacks the worker’s employment location.',
             'classification': 'Unresolved'},
        ]

    def validate(self, rows):
        self.path.write_text(json.dumps(rows))
        return case_diagnoses.validate(self.path, self.feedback)

    def test_accepts_complete_report_and_all_four_classifications(self):
        for classification in case_diagnoses.CLASSIFICATIONS:
            rows = copy.deepcopy(self.rows)
            rows[0]['classification'] = classification
            self.assertEqual(self.validate(rows), rows)

    def test_rejects_missing_duplicate_and_unknown_cases(self):
        for rows, message in [
            (self.rows[:1], 'missing='),
            (self.rows + self.rows[:1], 'duplicate'),
            ([{**self.rows[0], 'case_id': 'unknown'}, self.rows[1]], 'unexpected='),
        ]:
            with self.subTest(message=message), self.assertRaisesRegex(exp.RunnerError, message):
                self.validate(rows)

    def test_rejects_invalid_report_shape_and_diagnoses(self):
        invalid = [
            {'cases': self.rows},
            [{**self.rows[0], 'extra': 'field'}, self.rows[1]],
            [{**self.rows[0], 'classification': 'Looks fine'}, self.rows[1]],
            [{**self.rows[0], 'classification': []}, self.rows[1]],
            [{**self.rows[0], 'diagnosis': ''}, self.rows[1]],
            [{**self.rows[0], 'diagnosis': 'First line.\nSecond line.'}, self.rows[1]],
            [{**self.rows[0], 'diagnosis': 'x' * 601}, self.rows[1]],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(exp.RunnerError):
                self.validate(rows)

    def test_rejects_missing_malformed_and_symlink_report(self):
        with self.assertRaisesRegex(exp.RunnerError, 'missing or invalid'):
            case_diagnoses.validate(self.path, self.feedback)
        self.path.write_text('{')
        with self.assertRaisesRegex(exp.RunnerError, 'missing or invalid'):
            case_diagnoses.validate(self.path, self.feedback)
        self.path.unlink()
        self.path.symlink_to(self.feedback / 'index.json')
        with self.assertRaisesRegex(exp.RunnerError, 'symlink'):
            case_diagnoses.validate(self.path, self.feedback)

    def publish(self, ids, attempt=1):
        stage = self.root / f'session/candidate_reviews/attempt-{attempt}'
        exp.copy_project(self.workspace, stage / 'snapshot')
        case_diagnoses.publish_replay(self.feedback, stage, {
            'remaining_case_ids': ids, 'evidence_index': f'/rsa/feedback/replays/attempt-{attempt}/index.json'})

    def validate_remaining(self, rows):
        self.path.write_text(json.dumps(rows))
        return case_diagnoses.validate(self.path, self.feedback, remaining_only=True,
                                       workspace=self.workspace)

    def test_remaining_mode_uses_exact_latest_cases_including_new_disagreements(self):
        self.publish(['case-b', 'case-c'])
        current = [self.rows[1], {**self.rows[0], 'case_id': 'case-c'}]
        self.assertEqual(self.validate_remaining(current), current)
        for rows in [[], current[:1], self.rows, current + self.rows[:1], current + current[:1]]:
            self.path.write_text(json.dumps(rows))
            with self.assertRaises(exp.RunnerError):
                case_diagnoses.validate(self.path, self.feedback, remaining_only=True,
                                        workspace=self.workspace)

    def test_empty_report_only_when_latest_replay_has_no_remaining_cases(self):
        self.publish([])
        self.assertEqual(self.validate_remaining([]), [])
        with self.assertRaisesRegex(exp.RunnerError, 'unexpected='):
            self.validate_remaining(self.rows)

    def test_later_replay_replaces_original_and_previous_remaining_sets(self):
        self.publish(['case-a'])
        self.assertEqual(self.validate_remaining(self.rows[:1]), self.rows[:1])
        self.publish(['case-b'], attempt=2)
        with self.assertRaisesRegex(exp.RunnerError, 'coverage mismatch'):
            self.validate_remaining(self.rows[:1])
        self.assertEqual(self.validate_remaining(self.rows[1:]), self.rows[1:])

    def test_cached_replay_of_an_earlier_snapshot_becomes_latest(self):
        self.publish(['case-a'])
        (self.workspace / 'law.catala_en').write_text('different law')
        self.publish(['case-b'], attempt=2)
        (self.workspace / 'law.catala_en').write_text('current law')
        stage = self.root / 'session/candidate_reviews/attempt-1'
        case_diagnoses.publish_replay(self.feedback, stage, {
            'remaining_case_ids': ['case-a'],
            'evidence_index': '/rsa/feedback/replays/attempt-1/index.json',
        })
        self.assertEqual(self.validate_remaining(self.rows[:1]), self.rows[:1])

    def test_source_edits_and_incomplete_replay_block_submission(self):
        self.publish(['case-a'])
        (self.workspace / 'law.catala_en').write_text('later edit')
        with self.assertRaisesRegex(exp.RunnerError, 'workspace changed'):
            self.validate_remaining(self.rows[:1])
        case_diagnoses.begin_replay(self.feedback, exp.tree_hash(self.workspace))
        with self.assertRaisesRegex(exp.RunnerError, 'incomplete'):
            self.validate_remaining(self.rows[:1])

    def test_remaining_mode_requires_a_replay(self):
        with self.assertRaisesRegex(exp.RunnerError, 'Replay the current workspace'):
            self.validate_remaining([])

    def test_recovery_for_running_sessions_without_latest_marker(self):
        stage = self.root / 'session/candidate_reviews/attempt-1'
        exp.copy_project(self.workspace, stage / 'snapshot')
        exp.atomic_json(stage / 'review.json', {'remaining_case_ids': ['case-b']})
        exp.atomic_json(self.feedback / 'replays/attempt-1/index.json', {'remaining_case_ids': ['case-b']})
        self.assertEqual(self.validate_remaining(self.rows[1:]), self.rows[1:])

    def run_fake_agent(self, submit_report, remaining_only=True, mode='reasoning_structure_alignment'):
        run = self.root / 'run'
        for part in ['input', 'workspace']:
            (run / part).mkdir(parents=True)
        (run / 'input/law.catala_en').write_text('law')
        feedback = run / 'provision_repair/feedback'
        feedback.mkdir(parents=True)
        (feedback / 'index.json').write_bytes((self.feedback / 'index.json').read_bytes())
        (feedback.parent / 'before.json').write_text(json.dumps({
            'cases': [{'id': 'case-a'}, {'id': 'case-b'}]}))
        config = {'dataset': {'name': 'law'},
                  'agent': {'framework': 'codex', 'environment': [], 'image': 'test.sif'},
                  'repair': {'mode': mode, 'require_case_diagnoses': True},
                  'runtime': {'timeout_seconds': 30, 'progress_interval_seconds': 0}}
        if remaining_only:
            config['repair']['case_diagnoses_scope'] = 'remaining'
        state = {'_stage_directory': str(run / 'provision_repair/session'),
                 'provision_feedback': 'provision_repair/feedback', 'completed_stages': []}
        definition = SimpleNamespace(name='test', prepare_auth=None, stage_auth=None,
                                     persist_auth=None, prompt_builder=lambda *a: '')
        service = {}

        def review_candidate(*args, **kwargs):
            if remaining_only:
                stage = run / 'provision_repair/session/candidate_reviews/attempt-1'
                if not (stage / 'snapshot').exists():
                    exp.copy_project(run / 'workspace', stage / 'snapshot')
                case_diagnoses.publish_replay(feedback, stage, {
                    'remaining_case_ids': ['case-a', 'case-b'],
                    'evidence_index': '/rsa/feedback/replays/attempt-1/index.json',
                })
            return {'reviewed_cases': 2}

        @contextmanager
        def check_service(socket_path, check, commands):
            service.update(directory=socket_path.parent, check=check, commands=commands)
            yield

        def execute(command, prompt, stdout, stderr, *args):
            stdout.write_text('')
            stderr.write_text('')
            # Missing reports block both checker paths before replay starts.
            accepted, message = service['check']()
            self.assertFalse(accepted)
            self.assertIn('case_diagnoses.json', message)
            if remaining_only:
                self.assertEqual(service['commands']['replay_candidate'](), {'reviewed_cases': 2})
            else:
                with self.assertRaises(exp.RunnerError):
                    service['commands']['replay_candidate']()
            if submit_report:
                (service['directory'] / case_diagnoses.FILENAME).write_text(json.dumps(self.rows))
                self.assertTrue(service['check']()[0])
                self.assertEqual(service['commands']['replay_candidate'](), {'reviewed_cases': 2})
            return 0, False, 0.1

        with mock.patch.object(formalization.agents, 'get', return_value=definition), \
             mock.patch.object(formalization, 'commit_agent_result_if_complete', side_effect=[False, True]), \
             mock.patch.object(formalization, 'record_agent_usage', return_value={}), \
             mock.patch.object(formalization, 'AgentProgress'), \
             mock.patch.object(formalization, 'validate_workspace', return_value={}), \
             mock.patch.object(formalization, 'load_requirement_outputs', return_value=None), \
             mock.patch.object(formalization.apptainer, 'submission_check_service', side_effect=check_service), \
             mock.patch.object(formalization.apptainer, 'invocation', return_value=['agent']), \
             mock.patch.object(formalization.apptainer, 'environment', return_value={}), \
             mock.patch.object(formalization.apptainer, 'execute', side_effect=execute), \
             mock.patch.object(candidate_review, 'review', side_effect=review_candidate) as review, \
             mock.patch('rsa_formalizer.stages.baselines.final_answer_only.candidate_review.review',
                        side_effect=review_candidate) as baseline_review:
            formalization.run_agent_stage(run, config, state)
            self.assertEqual(review.call_count + baseline_review.call_count,
                             int(submit_report) + int(remaining_only))
        return run

    def test_service_requires_report_and_persists_it_after_agent_exits(self):
        run = self.run_fake_agent(submit_report=True)
        saved = run / 'provision_repair/session/agent/case_diagnoses.json'
        self.assertEqual(json.loads(saved.read_text()), self.rows)

    def test_remaining_mode_does_not_gate_replay_on_report(self):
        self.run_fake_agent(submit_report=True, remaining_only=True)

    def test_baseline_reports_are_bound_to_the_latest_repaired_source(self):
        run = self.run_fake_agent(submit_report=True, remaining_only=True, mode='baseline_final_answer_only')
        binding = exp.load_json(run / 'provision_repair/session/agent/case_diagnoses_replay.json')
        self.assertEqual(binding['remaining_case_ids'], ['case-a', 'case-b'])
        self.assertEqual(binding['candidate_snapshot_sha256'], exp.tree_hash(run / 'workspace'))

    def test_baseline_replay_exposes_remaining_final_answers_without_graphs(self):
        from rsa_formalizer.stages.baselines.final_answer_only import candidate_review as baseline
        run = self.root / 'baseline'
        workspace = run / 'workspace'
        workspace.mkdir(parents=True)
        (workspace / 'law.catala_en').write_text('current code')
        base = run / 'provision_repair'
        tests = [{'case': {'id': identifier, 'inputs': {'x': 1}},
                  'reasoning': {'id': identifier, 'output_text': 'Frozen reasoning'}}
                 for identifier in ['fixed', 'new']]
        exp.atomic_json(base / 'executable_tests.json', {'results': [{'accepted_tests': tests}]})
        exp.atomic_json(base / 'before.json', {
            'cases': [{'id': 'fixed', 'catala_answer': 0, 'final_answer_aligned': False},
                      {'id': 'new', 'catala_answer': 0, 'final_answer_aligned': True}],
            'final_answers_aligned': 1,
        })
        exp.atomic_json(base / 'feedback/index.json', {'reports': [{'case_id': 'fixed'}]})
        comparison = {'cases': [
            {'id': 'fixed', 'catala_answer': 1, 'llm_final_answer': 1, 'final_answer_aligned': True},
            {'id': 'new', 'catala_answer': 1, 'llm_final_answer': 0, 'final_answer_aligned': False}],
            'final_answers_aligned': 1}

        def replay(run, config, state, cases, **kwargs):
            exp.atomic_json(Path(state['_stage_directory']) / 'tests_bobcat_symbolic_results/build_errors.json', {})
            return []

        with mock.patch.object(exp, 'validate_workspace'), \
             mock.patch.object(baseline.submissions, 'record'), \
             mock.patch.object(baseline, 'replay_compiled', side_effect=replay) as replayed, \
             mock.patch.object(baseline.comparison, 'compare', return_value=comparison):
            report = baseline.review(run, {})
            self.assertEqual(baseline.review(run, {}), report)
            self.assertEqual(replayed.call_count, 1)
        self.assertEqual(report['remaining_case_ids'], ['new'])
        latest = case_diagnoses.latest_replay(base / 'feedback', workspace)
        self.assertEqual(latest['remaining_case_ids'], ['new'])
        evidence = exp.load_json(base / 'feedback/replays/attempt-1/new/report.json')
        self.assertEqual(evidence['comparison']['catala_answer'], 1)
        self.assertNotIn('computation_graph_alignment', evidence['comparison'])
        final_report = run / 'case_diagnoses.json'
        rows = [{'case_id': 'new', 'diagnosis': 'The current result is 1, while the frozen answer is 0.',
                 'classification': 'Catala wrong'}]
        exp.atomic_json(final_report, rows)
        self.assertEqual(case_diagnoses.validate(final_report, base / 'feedback',
                                                remaining_only=True, workspace=workspace), rows)

    def test_successful_process_without_report_cannot_complete_agent_stage(self):
        with self.assertRaisesRegex(exp.RunnerError, 'case_diagnoses.json'):
            self.run_fake_agent(submit_report=False)


if __name__ == '__main__':
    unittest.main()
