"""Unlimited agent sessions retain normal process and artifact handling."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from rsa_formalizer.agents.apptainer import execute


class AgentTimeoutTest(unittest.TestCase):
    def test_unlimited_deadline_executes_and_captures_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout, stderr = root / 'stdout', root / 'stderr'
            code, timed_out, elapsed = execute(
                [sys.executable, '-c', 'import sys; print(sys.stdin.read())'],
                'continue', stdout, stderr, None, os.environ.copy(),
                progress_interval=0,
            )
            self.assertEqual(code, 0)
            self.assertFalse(timed_out)
            self.assertGreaterEqual(elapsed, 0)
            self.assertEqual(stdout.read_text().strip(), 'continue')
            self.assertEqual(stderr.read_text(), '')

    def test_finite_deadline_still_terminates_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, timed_out, _ = execute(
                [sys.executable, '-c', 'import time; time.sleep(30)'],
                '', root / 'stdout', root / 'stderr', 0.05, os.environ.copy(),
                progress_interval=0,
            )
            self.assertTrue(timed_out)
            self.assertNotEqual(code, 0)
