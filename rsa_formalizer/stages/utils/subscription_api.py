"""Direct inference using the coding agents' subscription credentials.

No CLI agent loop, workspace context, tools, or API-key billing fallback.
Codex's streaming transport is collected into the final Responses object.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from rsa_formalizer.agents import claude_code, codex
from rsa_formalizer.agents.base import AgentConfigurationError
from .common import ROOT, RunnerError

CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_SUBSCRIPTION_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."


def _http_detail(error, token: str) -> str:
    """Expose only the structured provider message, with credentials redacted."""
    try:
        payload = json.load(error)
        detail = payload.get("error", {})
        message = detail.get("message", "") if isinstance(detail, dict) else ""
        return str(message).replace(token, "[redacted]")[:1000]
    except (ValueError, TypeError, AttributeError):
        return ""
    finally:
        error.close()


def _events(response):
    """Parse SSE frames, including multiline data and a final unterminated frame."""
    data = []
    for line in response:
        line = line.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                payload = "\n".join(data)
                data = []
                if payload != "[DONE]":
                    yield json.loads(payload)
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data and "\n".join(data) != "[DONE]":
        yield json.loads("\n".join(data))


def output_text(raw: dict[str, Any]) -> str:
    return "".join(
        part.get("text", "")
        for item in raw.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    )


def codex_response(request: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    if settings.get("base_url"):
        raise RunnerError("Codex subscription calls use the fixed Codex endpoint; remove base_url")
    body = dict(request)
    body.update(stream=True, store=False)
    body.setdefault("instructions", settings.get("instructions", "You are a helpful assistant."))
    if isinstance(body["input"], str):
        body["input"] = [{"role": "user", "content": body["input"]}]
    if settings.get("reasoning_effort"):
        body["reasoning"] = {"effort": settings["reasoning_effort"]}
    # Explicit public API cache options are not supported by this endpoint.
    if "extra_body" in body:
        raise RunnerError("Public API extra_body options are unsupported by Codex subscriptions")
    try:
        token, account = codex.subscription_auth()
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                       "Accept": "text/event-stream"}
            if account:
                headers["ChatGPT-Account-ID"] = account
            outbound = urllib.request.Request(CODEX_URL, data=json.dumps(body).encode(), headers=headers)
            try:
                with urllib.request.urlopen(outbound, timeout=settings.get("timeout", 600)) as response:
                    for event in _events(response):
                        kind = event.get("type")
                        if kind == "response.completed":
                            raw = event.get("response")
                            if not isinstance(raw, dict) or raw.get("status") not in (None, "completed"):
                                raise RunnerError("Codex returned an invalid final response")
                            return raw
                        if kind in {"error", "response.failed", "response.incomplete"}:
                            raise RunnerError(f"Codex subscription stream ended with {kind}")
                raise RunnerError("Codex subscription stream closed without response.completed")
            except urllib.error.HTTPError as error:
                if error.code == 401 and attempt == 0:
                    error.close()
                    token, account = codex.subscription_auth(rejected_token=token)
                    continue
                status = error.code
                detail = _http_detail(error, token)
                raise RunnerError(f"Codex subscription request failed (HTTP {status}); check login, model access and quota. {detail}") from None
    except AgentConfigurationError as error:
        raise RunnerError(str(error)) from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise RunnerError(f"Codex subscription transport failed ({type(error).__name__})") from None


def claude_response(settings: dict[str, Any], prompt: str,
                    schema: dict[str, Any] | None = None) -> dict[str, Any]:
    if settings.get("base_url"):
        raise RunnerError("Claude subscription calls use the fixed Anthropic endpoint; remove base_url")
    try:
        claude_code.prepare_auth(ROOT)
    except AgentConfigurationError as error:
        raise RunnerError(str(error)) from error
    token = os.environ[claude_code.OAUTH_VARIABLE]
    body: dict[str, Any] = {
        "model": settings["model"], "max_tokens": settings.get("max_output_tokens", 4096),
        "messages": [{"role": "user", "content": str(prompt)}],
        # The subscription endpoint validates this first system block. Keep it
        # explicit: unlike Codex, Claude OAuth cannot use arbitrary instructions
        # alone. See anthropics/claude-code issues #87420 and #103731.
        "system": [{"type": "text", "text": CLAUDE_SUBSCRIPTION_IDENTITY}],
    }
    if settings.get("instructions"):
        body["system"].append({"type": "text", "text": settings["instructions"]})
    if schema is not None:
        body["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    request = urllib.request.Request(
        CLAUDE_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "anthropic-version": "2023-06-01",
                 "anthropic-beta": "oauth-2025-04-20,claude-code-20250219", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.get("timeout", 600)) as response:
            raw = json.load(response)
    except urllib.error.HTTPError as error:
        status = error.code
        detail = _http_detail(error, token)
        raise RunnerError(
            f"Claude subscription request failed (HTTP {status}); OAuth inference may be restricted "
            f"to Claude Code. Check token, model access and quota; no API-key fallback was used. {detail}"
        ) from None
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise RunnerError(f"Claude subscription transport failed ({type(error).__name__})") from None
    if raw.get("type") == "error" or raw.get("stop_reason") in {"max_tokens", "refusal"}:
        raise RunnerError("Claude subscription returned an error or incomplete response")
    return raw
