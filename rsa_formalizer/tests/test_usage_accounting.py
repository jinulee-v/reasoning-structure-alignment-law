import json
import tempfile
import unittest
from pathlib import Path

from rsa_formalizer.stages.utils import usage


class CodexUsageAccountingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stdout = self.root / "stdout.jsonl"
        self.stdout.write_text(json.dumps({"type": "thread.started", "thread_id": "main-thread"}) + "\n")
        self.home = self.root / "home"
        sessions = self.home / ".codex/sessions"
        sessions.mkdir(parents=True)
        self.session = sessions / "rollout-main-thread.jsonl"
        snapshots = [self.event(1000, 800, 200, 50), self.event(1500, 1200, 300, 100)]
        self.session.write_text("\n".join(json.dumps(event) for event in [*snapshots, snapshots[-1]]) + '\n{"incomplete":')
        (sessions / "rollout-other-thread.jsonl").write_text(json.dumps(self.event(9999, 0, 9999, 0)) + "\n")

    @staticmethod
    def event(inputs, cached, outputs, reasoning):
        return {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": inputs, "cached_input_tokens": cached,
                                  "output_tokens": outputs, "reasoning_output_tokens": reasoning,
                                  "cache_write_input_tokens": 0, "total_tokens": inputs + outputs}
        }}}

    def test_cumulative_counts_are_not_added_or_mixed_across_threads(self):
        counts = usage.capture_codex_usage(self.home, self.stdout)
        self.assertEqual(counts["input_tokens"], 1500)
        self.assertEqual(counts["uncached_input_tokens"], 300)
        self.assertEqual(counts["cached_input_tokens"], 1200)
        self.assertEqual(counts["output_tokens"], 300)
        self.assertEqual(counts["reasoning_tokens"], 100)
        self.assertEqual(counts["total_tokens"], 1800)
        self.session.unlink()
        # Counts survive deletion of the temporary agent home on interruption.
        self.assertEqual(usage.extract_usage(self.stdout, ""), counts)

    def test_live_progress_and_final_usage_agree_without_double_counting(self):
        progress = usage.AgentProgress(self.stdout, self.root, self.root, codex_home=self.home)
        progress.refresh()
        self.assertEqual(progress.tokens(), (1500, 1200, 300, 1800))
        final = {"type": "turn.completed", "usage": {
            "input_tokens": 1500, "cached_input_tokens": 1200, "output_tokens": 300,
        }}
        with self.stdout.open("a") as stream:
            stream.write(json.dumps(final) + "\n")
        progress.refresh()
        self.assertEqual(progress.tokens(), (1500, 1200, 300, 1800))
        counts = usage.extract_usage(self.stdout, "")
        self.assertEqual(counts["total_tokens"], 1800)
        self.assertEqual(counts["reasoning_tokens"], 100)
        self.assertEqual(counts["count_source"], "provider-reported")

    def test_ledger_replaces_live_counts_for_the_same_session(self):
        partial = usage.capture_codex_usage(self.home, self.stdout)
        usage.record(self.root, "agent:one", {"status": "running", **partial})
        usage.record(self.root, "agent:one", {**partial, "status": "completed"})
        usage.reconcile(self.root)
        rows = [json.loads(line) for line in (self.root / "usage.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_tokens"], 1800)
        self.assertEqual(rows[0]["status"], "completed")

    def test_restarted_session_cannot_inherit_previous_token_counts(self):
        from rsa_formalizer.stages.formalization import archive_interrupted_session

        usage.capture_codex_usage(self.home, self.stdout)
        (self.root / "invocation.json").write_text(json.dumps({"session_id": "first"}))
        archive_interrupted_session(self.root)
        self.assertTrue((self.root / "recovery/first/codex_token_usage.json").is_file())
        self.stdout.write_text("")
        self.assertEqual(usage.extract_usage(self.stdout, "")["count_source"], "unavailable")


class ScopeProgressAndClaudeUsageTest(unittest.TestCase):
    def test_provision_progress_counts_only_edits_since_repair_start(self):
        import contextlib
        import io
        import shutil
        from unittest import mock
        from rsa_formalizer.stages import formalization
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'input';before=root/'analysis/snapshot';workspace=root/'workspace'
            for p in [original,before,workspace]:p.mkdir(parents=True)
            (original/'law.catala_en').write_text('```catala\n```\n```catala\n```\n')
            text='```catala\ndeclaration x content integer equals 1\n```\n```catala\ndeclaration y content integer equals 2\n```\n'
            (before/'law.catala_en').write_text(text);shutil.copy2(before/'law.catala_en',workspace/'law.catala_en')
            reference=formalization.progress_reference(root,{'provision_baseline':str(before)})
            self.assertEqual(reference,before)
            progress=usage.AgentProgress(root/'stdout.jsonl',reference,workspace,change_context='scope')
            output=io.StringIO()
            with contextlib.redirect_stderr(output):progress.report(1)
            self.assertIn('0 changed this scope',output.getvalue())
            (workspace/'law.catala_en').write_text(text.replace('equals 2','equals 3'))
            output=io.StringIO()
            with contextlib.redirect_stderr(output):progress.report(2)
            self.assertIn('1 changed this scope',output.getvalue())
            self.assertEqual(usage.workspace_fence_progress(original,workspace)['changed'],2)

    def test_claude_aggregate_usage_wins_over_model_breakdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stdout=root/'stdout.jsonl'
            aggregate={'input_tokens':10,'cache_read_input_tokens':100,'cache_creation_input_tokens':20,'output_tokens':30}
            event={'type':'result','usage':aggregate,'modelUsage':{
                'opus':{'inputTokens':80,'outputTokens':20},
                'other':{'inputTokens':50,'outputTokens':10},
            }}
            stdout.write_text(json.dumps(event)+'\n')
            counts=usage.extract_usage(stdout,'')
            self.assertEqual(counts['input_tokens'],130)
            self.assertEqual(counts['total_tokens'],160)
            progress=usage.AgentProgress(stdout,root,root);progress.refresh()
            self.assertEqual(progress.tokens(),(130,100,30,160))

    def test_claude_cache_reads_without_creation_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stdout=root/'stdout.jsonl'
            stdout.write_text(json.dumps({'type':'result','usage':{'input_tokens':2,'cache_read_input_tokens':90,'output_tokens':8}})+'\n')
            progress=usage.AgentProgress(stdout,root,root);progress.refresh()
            self.assertEqual(progress.tokens(),(92,90,8,100))
            self.assertEqual(usage.extract_usage(stdout,'')['total_tokens'],100)

    def test_reasoning_calls_update_log_and_ledger_once_including_tree_extraction(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=io.StringIO();calls=[]
            def request():
                calls.append(1)
                return {'request_id':'req-'+str(len(calls)),'usage':{
                    'input_tokens':100,'input_tokens_details':{'cached_tokens':80},
                    'output_tokens':20,'output_tokens_details':{'reasoning_tokens':5},
                    'total_tokens':120}}
            with contextlib.redirect_stderr(output):
                usage.api_call(root,{'stage':'reasoning','case_id':'case-1'},'answer',request)
                usage.api_call(root,{'stage':'reasoning-tree-extraction','case_id':'case-1'},'tree',request)
                usage.api_call(root,{'stage':'reasoning','case_id':'case-1'},'answer',request)
            rows=[json.loads(line) for line in (root/'usage.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),2);self.assertEqual(len(calls),2)
            self.assertEqual(sum(r['total_tokens'] for r in rows),240)
            self.assertIn('recorded_run_tokens=240',output.getvalue())
            self.assertEqual(output.getvalue().count('request_tokens=120'),2)
