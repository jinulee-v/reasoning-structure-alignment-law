"""Merge the parent initial-stage provenance into a paired experiment."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.utils import usage as usage_tracking


MARKER = "=== Inherited initial formalization and validation ==="


def merge_initial_artifacts(shared: Path, *, finalize_log: bool = False) -> dict:
    """Import one physical agent call; defer log replacement until its writer exits."""
    shared = shared.resolve()
    config = exp.load_json(shared / "config.json")
    parent = Path(config["parent_run"]).resolve()
    initial = exp.load_json(parent / "initial/agent/result.json")
    agent_usage = initial["usage"]
    session = agent_usage["session_id"]
    origin_id = f"agent:{session}"
    imported_id = f"inherited:{parent.name}:{origin_id}"
    event = {**agent_usage, "run_id": config["run_id"],
             "stage": "initial-formalization", "source_run_id": parent.name,
             "source_usage_id": origin_id, "source_session_id": session}
    usage_tracking.record(shared, imported_id, event)

    parent_log = (parent / "run.log").read_text(encoding="utf-8")
    lines = parent_log.splitlines(keepends=True)
    cutoff = next((i for i, line in enumerate(lines)
                   if line.startswith("User-requested clean recursive restart")
                   or line.startswith("Starting stage: reasoning_structure_alignment")), len(lines))
    initial_log = "".join(lines[:cutoff])
    validation = exp.load_json(parent / "initial/validation/results.json")["summary"]
    initial_log += (f"[initial validation] {validation['passed']}/{validation['total']} passed; "
                    f"{validation['failed']} failed; {validation['errors']} errors\n")
    prefix_path = shared / "initial_stages.log"
    prefix_path.write_text(initial_log, encoding="utf-8")
    summary = {
        "source_run": str(parent), "initial_agent_session": session,
        "initial_agent_tokens": agent_usage.get("total_tokens"),
        "validation_model_tokens": 0,
        "validation": validation,
        "initial_log_sha256": hashlib.sha256(initial_log.encode()).hexdigest(),
        "imported_usage_id": imported_id,
    }
    exp.atomic_json(shared / "initial_provenance.json", summary)

    if finalize_log:
        state = exp.load_json(shared / "state.json")
        if state.get("provision_phase") != "fork_ready":
            raise exp.RunnerError("shared generation is still writing run.log")
        log = shared / "run.log"
        # The generator writes its final state before printing the last line.
        for _ in range(10):
            before = log.stat()
            time.sleep(1)
            after = log.stat()
            if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns):
                break
        else:
            raise exp.RunnerError("run.log is still changing")
        current = log.read_text(encoding="utf-8")
        if MARKER not in current:
            temporary = log.with_name(".run.log.merged.tmp")
            temporary.write_text(f"{MARKER}\n{initial_log}\n=== Shared provision generation ===\n" + current,
                                 encoding="utf-8")
            os.replace(temporary, log)
        summary["run_log_merged"] = True
        exp.atomic_json(shared / "initial_provenance.json", summary)
    return summary
