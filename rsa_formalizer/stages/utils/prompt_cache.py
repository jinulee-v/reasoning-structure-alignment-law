"""Explicit cache boundaries for independent calls with shared reference text."""
from __future__ import annotations

import hashlib
import json
import threading


class CacheablePrompt(str):
    """Remain string-compatible with persisted prompts and other providers."""

    def __new__(cls, prefix: str, suffix: str, group: str):
        value = super().__new__(cls, prefix + "\n\n" + suffix)
        value.prefix = prefix
        value.suffix = suffix
        value.group = group
        return value


_BASELINES: dict[str, str] = {}
_LOCK = threading.Lock()


def configure_subscription_request(request: dict, prompt: CacheablePrompt) -> str:
    """Stable routing key for Codex automatic caching; no public API TTL fields."""
    identity = hashlib.sha256(json.dumps(
        [request["model"], request.get("text"), prompt.prefix], sort_keys=True
    ).encode()).hexdigest()
    request["input"] = [
        {"role": "developer", "content": prompt.prefix},
        {"role": "user", "content": prompt.suffix},
    ]
    request["prompt_cache_key"] = identity
    return identity


def configure_request(request: dict, prompt: CacheablePrompt, settings: dict) -> str:
    ttl = settings.get("ttl", "30m")
    if ttl not in {"30m", "12h"}:
        raise ValueError("prompt cache TTL must be 30m or 12h")
    identity = hashlib.sha256(json.dumps(
        [request["model"], request.get("text"), prompt.prefix], sort_keys=True
    ).encode()).hexdigest()
    options = {"mode": "explicit", "ttl": ttl}
    with _LOCK:
        comparison = _BASELINES.get(identity)
    if settings.get("diagnostics", True) and comparison:
        options["comparison_response_id"] = comparison
    request["input"] = [
        {"role": "developer", "content": [{"type": "input_text", "text": prompt.prefix,
            "prompt_cache_breakpoint": {"mode": "explicit"}}]},
        {"role": "user", "content": [{"type": "input_text", "text": prompt.suffix}]},
    ]
    # The installed SDK predates these API fields. extra_body preserves the
    # documented options without changing SDK versions or shared dependencies.
    request["extra_body"] = {"prompt_cache_options": options}
    return identity


def record_response(identity: str, response: dict, group: str) -> dict:
    if response.get("id"):
        with _LOCK:
            _BASELINES[identity] = response["id"]
    usage = response.get("usage") or {}
    details = usage.get("input_tokens_details") or {}
    diagnostics = response.get("prompt_cache_diagnostics")
    print(f"[cache] stage={group} input={usage.get('input_tokens')} "
          f"cached={details.get('cached_tokens')} written={details.get('cache_write_tokens')} "
          f"diagnostic={json.dumps(diagnostics, separators=(',', ':'))}", flush=True)
    return {"prompt_cache_prefix_sha256": identity, "prompt_cache_group": group,
            "prompt_cache_diagnostics": diagnostics}
