"""Host-only snapshots and held-out scores; never returned through agent tools."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.utils import usage
from .verification import run_verification_stage


_LOCK = threading.Lock()


def record(run: Path, config: dict, snapshot: Path, *, trigger: str,
           label: str | None = None, agent_home: Path | None = None) -> None:
    """Score an immutable copy without changing the live pipeline state.

    Each call remains a separate submission, including repeat submissions of
    identical code. Scores, diagnostics, logs, and saved Codex rollouts live
    outside all agent-visible mounts. Private scoring failures must not become
    feedback to the repair agent or prevent its public replay.
    """
    with _LOCK:
        root = run / "private_submissions"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        number = 1
        while (root / f"submission-{number:04d}").exists():
            number += 1
        destination = root / f"submission-{number:04d}"
        destination.mkdir()
        metadata = {
            "schema_version": 1, "submission": number,
            "trigger": trigger, "label": label,
            "mode": config.get("repair", {}).get("mode"),
            "recorded_at": exp.utc_now(), "status": "scoring",
            "validation": None,
        }
        exp.atomic_json(destination / "record.json", metadata)
        try:
            exp.copy_project(snapshot, destination / "snapshot")
            metadata["snapshot_sha256"] = exp.tree_hash(destination / "snapshot")
            agent = run / "provision_repair/session/agent"
            stdout = agent / "stdout.jsonl"
            if stdout.is_file():
                # A byte-bounded prefix identifies exactly the log checkpoint,
                # even if the agent emits more events while validation runs.
                size = stdout.stat().st_size
                with stdout.open("rb") as source, (destination / "stdout.jsonl").open("wb") as target:
                    remaining = size
                    while remaining:
                        chunk = source.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            break
                        target.write(chunk)
                        remaining -= len(chunk)
                metadata["agent_stdout_bytes"] = size - remaining
            for name in ("prompt.txt", "invocation.json", "stderr.log"):
                if (agent / name).is_file():
                    shutil.copy2(agent / name, destination / name)
            if agent_home is not None:
                sessions = agent_home / ".codex/sessions"
                if sessions.is_dir():
                    shutil.copytree(sessions, destination / "agent_home/.codex/sessions")
                usage.capture_codex_usage(destination / "agent_home", destination / "stdout.jsonl")
            counts = destination / "codex_token_usage.json"
            live_counts = counts.is_file()
            if not live_counts:
                counts = agent / "codex_token_usage.json"
            if counts.is_file():
                metadata["token_usage"] = exp.load_json(counts)
                metadata["token_usage_source"] = (
                    "saved-rollout" if live_counts else "last-recorded"
                )
            # The verifier commits state.json. Give it a private run directory
            # and private state so it cannot mark the live repair completed.
            exp.copy_project(run / "input", destination / "input")
            state = {"_stage_directory": str(destination), "completed_stages": []}
            run_verification_stage(destination, config, state)
            result = exp.load_json(destination / "validation/results.json")
            metadata.update(status="scored", validation=result["summary"])
        except Exception as error:
            metadata.update(status="error", error=f"{type(error).__name__}: {error}")
        metadata["finished_at"] = exp.utc_now()
        exp.atomic_json(destination / "record.json", metadata)
        exp.atomic_json(root / "index.json", {
            "schema_version": 1,
            "submissions": [exp.load_json(path) for path in sorted(root.glob("submission-*/record.json"))],
        })
