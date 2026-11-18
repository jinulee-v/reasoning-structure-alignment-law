import base64
import concurrent.futures
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from rsa_formalizer.agents import codex
from rsa_formalizer.agents.base import AgentConfigurationError
from rsa_formalizer.stages.utils import subscription_api as api
from rsa_formalizer.stages.utils.common import RunnerError
from rsa_formalizer.stages.validation import information_extraction as extraction


def jwt(exp):
    claims = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"header.{claims}.signature"


def stream(*events):
    return io.BytesIO(b": keepalive\n\n" + b"".join(
        b"data: " + json.dumps(event).encode() + b"\r\n\r\n" for event in events))


class SubscriptionAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "auth.json"
        patcher = mock.patch.dict(os.environ, {"CODEX_HOME": self.directory.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, token, **extra):
        data = {"auth_mode": "chatgpt", "tokens": {
            "access_token": token, "refresh_token": "refresh-secret", "account_id": "account"}, **extra}
        self.path.write_text(json.dumps(data))

    def test_valid_cli_credentials_do_not_refresh_or_change_auth(self):
        token = jwt(time.time() + 3600)
        self.write(token)
        before = self.path.read_bytes()
        with mock.patch.object(codex.urllib.request, "urlopen") as sent:
            self.assertEqual(codex.subscription_auth(), (token, "account"))
        sent.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_expired_credentials_refresh_once_and_persist_rotation(self):
        self.write(jwt(0), custom="preserved")
        fresh = jwt(time.time() + 3600)
        reply = {"access_token": fresh, "refresh_token": "rotated", "id_token": "identity"}
        with mock.patch.object(codex.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as sent:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
                results = list(workers.map(lambda _: codex.subscription_auth(), range(8)))
        self.assertEqual(results, [(fresh, "account")] * 8)
        sent.assert_called_once()
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["tokens"]["refresh_token"], "rotated")
        self.assertEqual(saved["custom"], "preserved")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_rejected_old_token_does_not_refresh_new_credentials(self):
        self.write("new-token")
        with mock.patch.object(codex.urllib.request, "urlopen") as sent:
            self.assertEqual(codex.subscription_auth(rejected_token="old-token")[0], "new-token")
        sent.assert_not_called()

    def test_api_key_login_and_malformed_auth_fail_without_api_fallback(self):
        for data in ({"auth_mode": "apikey", "OPENAI_API_KEY": "secret"}, {}):
            self.path.write_text(json.dumps(data))
            with self.assertRaises(AgentConfigurationError):
                codex.subscription_auth()

    def test_refresh_failure_preserves_credentials_and_hides_server_body(self):
        self.write(jwt(0))
        before = self.path.read_bytes()
        error = urllib.error.HTTPError("https://auth.openai.com/oauth/token", 400, "bad", {}, io.BytesIO(b"refresh-secret"))
        with mock.patch.object(codex.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(AgentConfigurationError) as raised:
                codex.subscription_auth()
        self.assertNotIn("refresh-secret", str(raised.exception))
        self.assertEqual(self.path.read_bytes(), before)


class SubscriptionTransportTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(codex, "subscription_auth", return_value=("oauth-secret", "account"))
        self.auth = patcher.start()
        self.addCleanup(patcher.stop)
        self.raw = {"id": "resp-1", "status": "completed", "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": '{"ok":true}'}]}],
            "usage": {"input_tokens": 10, "output_tokens": 4}}

    def test_codex_forwards_schema_and_collects_final_response(self):
        request = {"model": "model", "input": "question", "text": {"format": {
            "type": "json_schema", "name": "answer", "strict": True, "schema": {"type": "object"}}}}
        with mock.patch.object(api.urllib.request, "urlopen", return_value=stream(
            {"type": "response.output_text.delta", "delta": "ignored partial"},
            {"type": "response.completed", "response": self.raw})) as sent:
            result = api.codex_response(request, {"reasoning_effort": "high"})
        outbound = sent.call_args.args[0]
        body = json.loads(outbound.data)
        self.assertEqual(outbound.full_url, api.CODEX_URL)
        self.assertEqual(outbound.get_header("Authorization"), "Bearer oauth-secret")
        self.assertEqual(outbound.get_header("Chatgpt-account-id"), "account")
        self.assertTrue(body["stream"])
        self.assertFalse(body["store"])
        self.assertEqual(body["text"], request["text"])
        self.assertEqual(body["input"], [{"role": "user", "content": "question"}])
        self.assertEqual(body["reasoning"], {"effort": "high"})
        self.assertNotIn("tools", body)
        self.assertEqual(result, self.raw)
        self.assertEqual(api.output_text(result), '{"ok":true}')

    def test_codex_401_refreshes_and_retries_once(self):
        error = urllib.error.HTTPError(api.CODEX_URL, 401, "expired", {}, io.BytesIO())
        with mock.patch.object(api.urllib.request, "urlopen", side_effect=[error, stream(
            {"type": "response.completed", "response": self.raw})]):
            self.assertEqual(api.codex_response({"model": "m", "input": "q"}, {}), self.raw)
        self.auth.assert_called_with(rejected_token="oauth-secret")

    def test_codex_rejects_failed_incomplete_and_truncated_streams(self):
        for events in ([], [{"type": "response.incomplete"}], [{"type": "response.failed"}], [{"type": "error"}]):
            with self.subTest(events=events), mock.patch.object(api.urllib.request, "urlopen", return_value=stream(*events)):
                with self.assertRaises(RunnerError):
                    api.codex_response({"model": "m", "input": "q"}, {})

    def test_no_credentials_are_forwarded_to_custom_endpoints(self):
        with mock.patch.object(api.urllib.request, "urlopen") as sent:
            for call in (lambda: api.codex_response({"input": "q"}, {"base_url": "https://example.com"}),
                         lambda: api.claude_response({"base_url": "https://example.com"}, "q")):
                with self.assertRaises(RunnerError):
                    call()
        sent.assert_not_called()

    def test_claude_uses_agent_oauth_not_api_key_and_preserves_thinking(self):
        raw = {"id": "msg-1", "content": [{"type": "thinking", "thinking": "trace"},
            {"type": "text", "text": "answer"}], "usage": {"input_tokens": 8}}
        schema = {"type": "object"}
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "cc-secret", "ANTHROPIC_API_KEY": "unused"}), mock.patch.object(
            api.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(raw).encode())) as sent:
            self.assertEqual(api.claude_response({"model": "claude-model", "instructions": "Custom instructions"}, "q", schema), raw)
        outbound = sent.call_args.args[0]
        self.assertEqual(outbound.get_header("Authorization"), "Bearer cc-secret")
        self.assertIsNone(outbound.get_header("X-api-key"))
        body = json.loads(outbound.data)
        self.assertEqual(body["output_config"]["format"]["schema"], schema)
        self.assertEqual(body["system"], [
            {"type": "text", "text": api.CLAUDE_SUBSCRIPTION_IDENTITY},
            {"type": "text", "text": "Custom instructions"}])
        self.assertIn("oauth-2025-04-20", outbound.get_header("Anthropic-beta"))

    def test_claude_rejection_has_no_paid_fallback(self):
        error = urllib.error.HTTPError(api.CLAUDE_URL, 403, "restricted", {}, io.BytesIO(b"cc-secret"))
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "cc-secret"}), mock.patch.object(api.urllib.request, "urlopen", side_effect=error) as sent:
            with self.assertRaisesRegex(RunnerError, "HTTP 403") as raised:
                api.claude_response({"model": "claude"}, "q")
        sent.assert_called_once()
        self.assertNotIn("cc-secret", str(raised.exception))

    def test_extraction_legacy_openai_alias_uses_subscription_with_schema(self):
        with mock.patch.object(api, "codex_response", return_value=self.raw) as sent:
            result = extraction._call_model({"provider": "openai", "model": "model"}, "q", {"type": "object"}, name="test")
        self.assertEqual(result["parsed"], {"ok": True})
        self.assertEqual(result["usage"], self.raw["usage"])
        self.assertTrue(sent.call_args.args[0]["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
