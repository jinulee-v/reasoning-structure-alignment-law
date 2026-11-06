"""Durable, deduplicated accounting for API requests and agent attempts."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

from .common import RunnerError
from .workspace_validation import workspace_fence_progress


_LOCK = threading.Lock()


def api_counts(usage: dict[str, Any]) -> dict[str, Any]:
    inputs = usage.get("input_tokens", usage.get("prompt_tokens"))
    outputs = usage.get("output_tokens", usage.get("completion_tokens"))
    cached = (
        usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    ).get("cached_tokens", usage.get("cache_read_input_tokens"))
    written = usage.get("cache_creation_input_tokens")
    # Anthropic separates cached tokens from its base input count.
    if inputs is not None and (
        "cache_read_input_tokens" in usage or "cache_creation_input_tokens" in usage
    ):
        inputs += (cached or 0) + (written or 0)
    return {
        "input_tokens": inputs,
        "output_tokens": outputs,
        "uncached_input_tokens": max(0, inputs - (cached or 0))
        if inputs is not None
        else None,
        "cached_input_tokens": cached,
        "cache_write_tokens": written,
        "reasoning_tokens": (
            usage.get("output_tokens_details")
            or usage.get("completion_tokens_details")
            or {}
        ).get("reasoning_tokens"),
        "total_tokens": usage.get(
            "total_tokens",
            inputs + outputs if inputs is not None and outputs is not None else None,
        ),
        "count_source": "provider-reported"
        if inputs is not None and outputs is not None
        else "unavailable",
    }


def record(run: Path, usage_id: str, value: dict[str, Any]) -> None:
    # Upsert one physical call; an interrupted ledger write is recoverable.
    from rtdf_formalizer.stages import utils as exp

    events = run / "usage_events"
    events.mkdir(parents=True, exist_ok=True)
    filename = hashlib.sha256(usage_id.encode()).hexdigest() + ".json"
    with _LOCK, (run / ".usage.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        event = {**value, "usage_id": usage_id}
        exp.atomic_json(events / filename, event)
        _reconcile_locked(run, event)


def _reconcile_locked(run: Path, updated: dict[str, Any] | None = None) -> None:
    from rtdf_formalizer.stages import utils as exp

    ledger = run / "usage.jsonl"
    rows = []
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    indexed = {row["usage_id"]: row for row in rows if row.get("usage_id")}
    legacy = [row for row in rows if not row.get("usage_id")]
    if updated is None:
        for path in sorted((run / "usage_events").glob("*.json")):
            value = exp.load_json(path)
            indexed[value["usage_id"]] = value
    else:
        indexed[updated["usage_id"]] = updated
    # Upgrading a cached request must not count its old ledger row again.
    identities = {
        (row.get("iteration"), row.get("stage"), row.get("request_id"))
        for row in indexed.values()
        if row.get("request_id")
    }
    legacy = [
        row
        for row in legacy
        if (row.get("iteration"), row.get("stage"), row.get("request_id"))
        not in identities
    ]
    temporary = run / ".usage.jsonl.tmp"
    with temporary.open("w", encoding="utf-8") as output:
        for row in [*legacy, *indexed.values()]:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(ledger)


def reconcile(run: Path) -> None:
    if not (run / "usage_events").is_dir():
        return
    with _LOCK, (run / ".usage.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        from rtdf_formalizer.stages import utils as exp

        for path in (run / "api_calls").glob("*.json"):
            saved = exp.load_json(path)
            filename = hashlib.sha256(saved["usage_id"].encode()).hexdigest() + ".json"
            exp.atomic_json(
                run / "usage_events" / filename,
                {**saved["accounting"], "usage_id": saved["usage_id"]},
            )
        _reconcile_locked(run)


def api_call(
    run: Path,
    context: dict[str, Any],
    fingerprint: str,
    call: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    # Persist responses before downstream parsing, and reuse them on resume.
    from rtdf_formalizer.stages import utils as exp

    key = exp.sha256_bytes(json.dumps([context, fingerprint], sort_keys=True).encode())
    response_path = run / "api_calls" / f"{key}.json"
    if response_path.is_file():
        saved = exp.load_json(response_path)
        record(run, saved["usage_id"], saved["accounting"])
        return saved["response"]
    usage_id = f"api:{uuid.uuid4().hex}"
    started = time.monotonic()
    accounting = {
        **context,
        "recorded_at": exp.utc_now(),
        "request_id": None,
        "status": "started",
        **api_counts({}),
    }
    record(run, usage_id, accounting)
    try:
        response = call()
    except BaseException as error:
        record(
            run,
            usage_id,
            {
                **accounting,
                "status": "failed-or-interrupted",
                "diagnostic": f"{type(error).__name__}: {error}",
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        raise
    usage = response.get("usage") or {}
    response["_usage_id"] = usage_id
    accounting.update(
        status="completed",
        usage=usage,
        **api_counts(usage),
        request_id=response.get("request_id"),
        elapsed_seconds=time.monotonic() - started,
    )
    exp.atomic_json(
        response_path,
        {"usage_id": usage_id, "accounting": accounting, "response": response},
    )
    record(run, usage_id, accounting)
    return response


def cached_response(
    run: Path, context: dict[str, Any], response: dict[str, Any], key: str
) -> None:
    # Backfill accounting for legacy caches without double-counting new calls.
    from rtdf_formalizer.stages import utils as exp

    if response.get("_usage_id"):
        return
    usage = response.get("usage") or {}
    record(
        run,
        f"cached:{context['iteration']}:{context['stage']}:{key}",
        {
            **context,
            "request_id": response.get("request_id"),
            "usage": usage,
            **api_counts(usage),
            "status": "cached",
            "recorded_at": exp.utc_now(),
        },
    )


TOKEN_KEYS = {
    "input_tokens": ("input_tokens", "inputTokens"),
    "output_tokens": ("output_tokens", "outputTokens"),
    "reasoning_tokens": ("reasoning_tokens", "reasoningTokens"),
    "cached_input_tokens": (
        "cached_input_tokens",
        "cachedInputTokens",
        "cache_read_input_tokens",
    ),
    "cache_write_tokens": (
        "cache_write_tokens",
        "cacheWriteTokens",
        "cache_creation_input_tokens",
    ),
    "total_tokens": ("total_tokens", "totalTokens"),
}


def find_usage_objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if any(key in value for aliases in TOKEN_KEYS.values() for key in aliases):
            yield value
        for nested in value.values():
            yield from find_usage_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from find_usage_objects(nested)


def extract_usage(stdout_path: Path, prompt: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    claude_messages: dict[str, dict[str, Any]] = {}
    final_usage = False
    for raw_line in stdout_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") in ("result", "turn.completed") and isinstance(
            event.get("usage"), dict
        ):
            final_usage = True
        message = event.get("message")
        if (
            event.get("type") == "assistant"
            and isinstance(message, dict)
            and message.get("id")
            and isinstance(message.get("usage"), dict)
        ):
            claude_messages[message["id"]] = api_counts(message["usage"])
        candidates.extend(find_usage_objects(event))

    if claude_messages and not final_usage:
        keys = (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "reasoning_tokens",
            "total_tokens",
        )
        counts = {
            key: sum(row.get(key) or 0 for row in claude_messages.values())
            if all(row.get(key) is not None for row in claude_messages.values())
            else None
            for key in keys
        }
        return {
            **counts,
            "uncached_input_tokens": (
                counts["input_tokens"] - (counts["cached_input_tokens"] or 0)
                if counts["input_tokens"] is not None
                else None
            ),
            "count_source": "provider-reported-partial",
        }

    if candidates:

        def direct_core_count(candidate: dict[str, Any]) -> int:
            return sum(
                isinstance(candidate.get(key), (int, float))
                for normalized in ("input_tokens", "output_tokens", "total_tokens")
                for key in TOKEN_KEYS[normalized]
            )

        # Aggregate/final usage objects normally have both core counts.
        selected = max(
            enumerate(candidates),
            key=lambda item: (direct_core_count(item[1]), item[0]),
        )[1]

        def nested_number(value: Any, aliases: tuple[str, ...]) -> int | None:
            if isinstance(value, dict):
                for key in aliases:
                    found = value.get(key)
                    if isinstance(found, (int, float)):
                        return int(found)
                for nested in value.values():
                    found = nested_number(nested, aliases)
                    if found is not None:
                        return found
            elif isinstance(value, list):
                for nested in value:
                    found = nested_number(nested, aliases)
                    if found is not None:
                        return found
            return None

        counts: dict[str, int | None] = {}
        for normalized, aliases in TOKEN_KEYS.items():
            counts[normalized] = nested_number(selected, aliases)
        if counts["input_tokens"] is not None and (
            "cache_read_input_tokens" in selected
            or "cache_creation_input_tokens" in selected
        ):
            counts["input_tokens"] += (counts["cached_input_tokens"] or 0) + (
                counts["cache_write_tokens"] or 0
            )
        if counts["total_tokens"] is None:
            known_total = (counts["input_tokens"] or 0) + (counts["output_tokens"] or 0)
            counts["total_tokens"] = known_total or None
        uncached_input = None
        if counts["input_tokens"] is not None:
            uncached_input = max(
                0,
                counts["input_tokens"] - (counts["cached_input_tokens"] or 0),
            )
        return {
            **counts,
            "uncached_input_tokens": uncached_input,
            "count_source": "provider-reported"
            if counts["input_tokens"] is not None
            and counts["output_tokens"] is not None
            else "unavailable",
        }

    # Agent logs do not expose the complete prompt/tool context.
    return {
        "input_tokens": None,
        "uncached_input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "cached_input_tokens": None,
        "cache_write_tokens": None,
        "total_tokens": None,
        "count_source": "unavailable",
    }


class AgentProgress:
    # Incrementally summarize a coding agent's JSONL stream and workspace.

    def __init__(
        self, stdout_path: Path, input_directory: Path, workspace: Path
    ) -> None:
        self.stdout_path = stdout_path
        self.input_directory = input_directory
        self.workspace = workspace
        self.offset = 0
        self.partial = b""
        self.tool_ids: set[str] = set()
        self.openc_input = 0
        self.openc_cached = 0
        self.openc_output = 0
        self.openc_total = 0
        self.openc_steps = 0
        self.claude_messages: dict[str, tuple[int, int, int, int]] = {}
        self.final_usage: tuple[int, int, int, int] | None = None

    @staticmethod
    def _number(value: Any, *keys: str) -> int:
        if not isinstance(value, dict):
            return 0
        for key in keys:
            found = value.get(key)
            if isinstance(found, (int, float)):
                return int(found)
        return 0

    def _record_tool(self, identifier: Any) -> None:
        if isinstance(identifier, str) and identifier:
            self.tool_ids.add(identifier)

    def _consume_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        part = event.get("part")
        if event_type == "step_finish" and isinstance(part, dict):
            tokens = part.get("tokens")
            if isinstance(tokens, dict):
                cache = tokens.get("cache")
                uncached = self._number(tokens, "input")
                cached = self._number(cache, "read") + self._number(cache, "write")
                output = self._number(tokens, "output")
                self.openc_input += uncached + cached
                self.openc_cached += self._number(cache, "read")
                self.openc_output += output
                self.openc_total += (
                    self._number(tokens, "total") or uncached + cached + output
                )
                self.openc_steps += 1

        if event_type == "tool_use" and isinstance(part, dict):
            self._record_tool(part.get("callID") or part.get("id"))

        message = event.get("message")
        if event_type == "assistant" and isinstance(message, dict):
            for content in message.get("content", []):
                if isinstance(content, dict) and content.get("type") == "tool_use":
                    self._record_tool(content.get("id"))
            usage = message.get("usage")
            message_id = message.get("id")
            if isinstance(usage, dict) and isinstance(message_id, str):
                base_input = self._number(usage, "input_tokens", "inputTokens")
                cached = self._number(usage, "cache_read_input_tokens")
                cache_write = self._number(usage, "cache_creation_input_tokens")
                output = self._number(usage, "output_tokens", "outputTokens")
                total_input = base_input + cached + cache_write
                self.claude_messages[message_id] = (
                    total_input,
                    cached,
                    output,
                    total_input + output,
                )

        item = event.get("item")
        if event_type in ("item.started", "item.completed") and isinstance(item, dict):
            if item.get("type") not in (None, "agent_message", "reasoning"):
                self._record_tool(item.get("id"))

        usage = event.get("usage")
        if event_type in ("turn.completed", "result") and isinstance(usage, dict):
            input_tokens = self._number(usage, "input_tokens", "inputTokens")
            cached = self._number(
                usage, "cached_input_tokens", "cache_read_input_tokens"
            )
            # Claude's result usage separates cache reads/creation from base input; Codex reports cached tokens as a subset of input.
            if "cache_creation_input_tokens" in usage:
                input_tokens += cached + self._number(
                    usage, "cache_creation_input_tokens"
                )
            output = self._number(usage, "output_tokens", "outputTokens")
            total = self._number(usage, "total_tokens", "totalTokens")
            self.final_usage = (
                input_tokens,
                cached,
                output,
                total or input_tokens + output,
            )

    def refresh(self) -> None:
        try:
            with self.stdout_path.open("rb") as stream:
                stream.seek(self.offset)
                chunk = stream.read()
                self.offset = stream.tell()
        except FileNotFoundError:
            return
        lines = (self.partial + chunk).split(b"\n")
        self.partial = lines.pop()
        for raw_line in lines:
            try:
                event = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(event, dict):
                self._consume_event(event)

    def tokens(self) -> tuple[int, int, int, int] | None:
        if self.openc_steps:
            return (
                self.openc_input,
                self.openc_cached,
                self.openc_output,
                self.openc_total,
            )
        if self.final_usage is not None:
            return self.final_usage
        if self.claude_messages:
            columns = zip(*self.claude_messages.values())
            return tuple(sum(column) for column in columns)  # type: ignore[return-value]
        return None

    def report(self, elapsed: float) -> None:
        self.refresh()
        token_counts = self.tokens()
        if token_counts is None:
            token_text = "tokens=n/a"
        else:
            input_tokens, cached_tokens, output_tokens, total_tokens = token_counts
            token_text = (
                f"tokens={total_tokens:,} (in={input_tokens:,}, "
                f"cached={cached_tokens:,}, out={output_tokens:,})"
            )
        try:
            fences = workspace_fence_progress(self.input_directory, self.workspace)
            fence_text = (
                f"catala={fences['filled']}/{fences['total']} filled, "
                f"{fences['valid']}/{fences['total']} code-valid, "
                f"{fences['changed']} changed"
            )
        except (OSError, RunnerError):
            # The agent can be between writes when this snapshot is taken.
            fence_text = "catala=updating"
        minutes, seconds = divmod(int(elapsed), 60)
        hours, minutes = divmod(minutes, 60)
        elapsed_text = f"{hours:d}:{minutes:02d}:{seconds:02d}"
        print(
            f"[progress] elapsed={elapsed_text} {token_text} "
            f"tools={len(self.tool_ids)} {fence_text}",
            file=sys.stderr,
            flush=True,
        )


def extract_request_metadata(stdout_path: Path) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    identifier_keys = ("request_id", "response_id", "thread_id", "session_id")

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key in identifier_keys:
                identifier = value.get(key)
                if isinstance(identifier, str) and identifier:
                    identifiers[key] = identifier
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    for raw_line in stdout_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            visit(json.loads(raw_line))
        except json.JSONDecodeError:
            continue
    return identifiers
