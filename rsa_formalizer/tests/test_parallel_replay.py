"""Concurrent replay overlaps execution while preserving records and failures."""
import io
import json
import subprocess
import tempfile
import threading
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from rsa_formalizer.bobcat import replay
from rsa_formalizer.stages import utils as exp


class ParallelReplayTest(unittest.TestCase):
    def run_cases(self, run, jobs, execute):
        stage = run / 'stage'
        (stage / 'snapshot').mkdir(parents=True, exist_ok=True)
        (stage / 'tests_bobcat_symbolic_results/project').mkdir(parents=True, exist_ok=True)
        executable = run / 'bridge'
        executable.touch()
        cases = [dict(id=f'case-{i}', source='Api.catala_en', target='Entry',
                      inputs={'value': i}, branches=[], statute_ids=[]) for i in range(4)]
        config = {'dataset': {'name': 'sara'}, 'runtime': {'timeout_seconds': 30},
                  'execution': {'replay_jobs': jobs, 'replay_trace_mode': 'full'}}
        state = {'_stage_directory': str(stage)}
        with ExitStack() as stack:
            patches = {
                'exp.extract_input_formats': mock.Mock(return_value={'scopes': []}),
                'exp.toolchain_environment': mock.Mock(return_value={}),
                'compiled_json.build_bridges': mock.Mock(return_value={}),
                'compiled_json.compiled_path': mock.Mock(return_value=executable),
                '_compiler_dependencies': mock.Mock(return_value={}),
                'execution_tree': lambda events, **kw: events,
                'slice_execution_tree': lambda tree, *args: tree,
                'execution_tree_events': lambda tree: tree,
                'traced_provision_path': lambda *args: [],
                'subprocess.run': mock.Mock(side_effect=execute),
            }
            mocks = {}
            for name, value in patches.items():
                mocks[name] = stack.enter_context(mock.patch(
                    f'rsa_formalizer.bobcat.replay.{name}', value))
            stack.enter_context(redirect_stdout(io.StringIO()))
            records = replay.replay_compiled(run, config, state, cases)
        return list(records), mocks

    @staticmethod
    def successful(command, **kwargs):
        value = json.loads(kwargs['input'])['value']
        observed = {'result': {'value': value}, 'events': [{'value': value}],
                    'dependency_semantics': replay.DYNAMIC_SLICE_DEPENDENCY_SEMANTICS}
        return subprocess.CompletedProcess(command, 0, json.dumps(observed), '')

    def test_parallel_execution_overlaps_and_matches_serial_records(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        active = peak = 0

        def execute(command, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                # A serial implementation would time out here.
                barrier.wait(timeout=5)
                return self.successful(command, **kwargs)
            finally:
                with lock:
                    active -= 1

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parallel, _ = self.run_cases(root / 'parallel', 2, execute)
            serial, _ = self.run_cases(root / 'serial', 1, self.successful)
            self.assertEqual(peak, 2)
            self.assertEqual([r['id'] for r in parallel], [f'case-{i}' for i in range(4)])
            # Commands contain variant-specific executable paths; all data agrees.
            for records in (serial, parallel):
                for record in records:
                    record.pop('execution')
            self.assertEqual(parallel, serial)
            _, mocks = self.run_cases(root / 'parallel', 2, self.successful)
            mocks['subprocess.run'].assert_not_called()
            mocks['compiled_json.build_bridges'].assert_not_called()

    def test_case_failures_do_not_drop_other_cases(self):
        def execute(command, **kwargs):
            value = json.loads(kwargs['input'])['value']
            if value == 1:
                return subprocess.CompletedProcess(command, 2, '', 'bad input')
            if value == 2:
                raise subprocess.TimeoutExpired(command, 600)
            return self.successful(command, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            records, _ = self.run_cases(Path(directory), 2, execute)
        self.assertEqual([r['id'] for r in records], [f'case-{i}' for i in range(4)])
        self.assertIsNone(records[0]['error'])
        self.assertIn('exited 2', records[1]['error'])
        self.assertIn('TimeoutExpired', records[2]['error'])
        self.assertIsNone(records[3]['error'])

    def test_invalid_worker_counts_are_rejected_before_work(self):
        for jobs in (0, -1, True, '4', 1.5):
            with self.subTest(jobs=jobs), self.assertRaisesRegex(ValueError, 'positive integer'):
                replay.replay_compiled(Path('/unused'), {'execution': {'replay_jobs': jobs}}, {}, [])


if __name__ == '__main__':
    unittest.main()
