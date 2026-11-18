"""Coding-agent formalization stage."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from rsa_formalizer import agents
from rsa_formalizer.agents import apptainer
from rsa_formalizer.agents.base import (
    AgentConfigurationError,
)

from .utils import usage as usage_tracking
from .utils import (
    ROOT,
    AgentProgress,
    RunnerError,
    atomic_json,
    cleanup_clerk_artifacts,
    extract_request_metadata,
    extract_usage,
    integrity_manifest_matches,
    load_json,
    load_requirement_outputs,
    publish_copy,
    publish_stage_snapshot,
    sha256_file,
    stage_directory,
    unreachable_catala_blocks,
    utc_now,
    validate_workspace,
)


def commit_agent_result_if_complete(run_directory: Path, state: dict[str, Any]) -> bool:
    agent_directory = stage_directory(run_directory, state) / "agent"
    summary_path = agent_directory / "result.json"
    if not summary_path.is_file():
        return False
    summary = load_json(summary_path)
    if summary.get("status") != "completed":
        return False
    config = load_json(run_directory / "config.json")
    if (config.get("repair", {}).get("mode") in {"reasoning_structure_alignment", "baseline_final_answer_only"}
            and config.get("repair", {}).get("require_case_diagnoses", True)):
        from .reasoning_structure_alignment import case_diagnoses
        case_diagnoses.validate(
            agent_directory / case_diagnoses.FILENAME,
            run_directory / (state.get("provision_feedback") or "provision_repair/feedback"),
            remaining_only=True,
            workspace=run_directory / "workspace",
        )
    # Revalidate on every resume; a manually changed workspace invalidates the checkpoint.
    integrity = validate_workspace(run_directory / "input", run_directory / "workspace")
    if not integrity_manifest_matches(summary.get("integrity"), integrity):
        raise RunnerError(
            "workspace no longer matches the completed agent-stage integrity manifest"
        )
    if "agent" not in state["completed_stages"]:
        state["completed_stages"].append("agent")
    publish_stage_snapshot(run_directory, state)
    if "snapshot" not in state["completed_stages"]:
        state["completed_stages"].append("snapshot")
    state.update(
        next_stage="validation",
        status="agent_completed",
        updated_at=utc_now(),
    )
    atomic_json(run_directory / "state.json", state)
    return True


def record_agent_usage(
    run_directory: Path,
    config: dict[str, Any],
    artifacts: Path,
    *,
    elapsed: float | None = None,
    status: str = "interrupted-or-recovered",
) -> dict[str, Any]:
    stdout = artifacts / "stdout.jsonl"
    prompt_path = artifacts / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    usage = (
        extract_usage(stdout, prompt)
        if stdout.is_file()
        else usage_tracking.api_counts({})
    )
    metadata = extract_request_metadata(stdout) if stdout.is_file() else {}
    invocation_path = artifacts / "invocation.json"
    invocation = load_json(invocation_path) if invocation_path.is_file() else {}
    session_id = invocation.get("session_id") or artifacts.name
    result = {
        "run_id": config["run_id"],
        "stage": "agent",
        "session_id": session_id,
        "framework": config["agent"]["framework"],
        "provider": config["agent"]["provider"],
        "model": config["agent"]["model"],
        "request_id": (
            metadata.get("request_id")
            or metadata.get("response_id")
            or metadata.get("thread_id")
            or metadata.get("session_id")
        ),
        "request_metadata": metadata,
        "elapsed_seconds": elapsed,
        "status": status,
        **usage,
        "recorded_at": utc_now(),
    }
    usage_tracking.record(run_directory, f"agent:{session_id}", result)
    return result


def recover_agent_usage(run_directory: Path, config: dict[str, Any]) -> None:
    ledger = run_directory / "usage.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()] if ledger.is_file() else []
    legacy = [row for row in rows if not row.get("usage_id")]
    inherited_sessions = {
        row.get("source_session_id") or row.get("session_id")
        for row in rows
        if row.get("source_session_id") or row.get("run_id") != config.get("run_id")
    }
    agents = [run_directory / "initial/agent", run_directory / "provision_repair/session/agent"]
    agents += list(
        (run_directory / "refinement").glob("*/revisions/*/session/agent")
    )
    sessions = []
    for agent in agents:
        sessions.append(agent)
        sessions.extend(sorted((agent / "recovery").glob("*")))
    for artifacts in sessions:
        if not (artifacts / "invocation.json").is_file():
            continue
        if artifacts == run_directory / "initial/agent":
            session_id = load_json(artifacts / "invocation.json").get("session_id")
            if session_id and session_id in inherited_sessions:
                # Copied initial records already belong to the shared physical call.
                continue
        result_path = artifacts / "result.json"
        result = load_json(result_path) if result_path.is_file() else {}
        if result.get("usage") in legacy:
            # Older sessions without request IDs cannot be safely deduplicated by provider ID.
            legacy.remove(result["usage"])
            continue
        record_agent_usage(
            run_directory,
            config,
            artifacts,
            elapsed=result.get("elapsed_seconds"),
            status=result.get("status", "interrupted-or-recovered"),
        )


def archive_interrupted_session(agent_directory: Path) -> None:
    names = (
        "prompt.txt", "invocation.json", "stdout.jsonl", "stderr.log", "result.json",
        "codex_token_usage.json",
        "case_diagnoses.json",
        "case_diagnoses_replay.json",
    )
    existing = [agent_directory / name for name in names if (agent_directory / name).exists()]
    if not existing:
        return
    invocation = (
        load_json(agent_directory / "invocation.json")
        if (agent_directory / "invocation.json").is_file()
        else {}
    )
    session_id = invocation.get("session_id") or uuid.uuid4().hex
    recovery = agent_directory / "recovery" / session_id
    recovery.mkdir(parents=True, exist_ok=False)
    for path in existing:
        shutil.move(path, recovery / path.name)


def progress_reference(run_directory: Path, state: dict[str, Any]) -> Path:
    """Compare scope edits with that revision's immutable pre-session snapshot."""
    if state.get("provision_baseline"):
        reference = Path(state["provision_baseline"])
    else:
        reference = run_directory / "input"
    if not reference.is_dir():
        raise RunnerError(f"missing progress baseline: {reference}")
    return reference


def run_agent_stage(
    run_directory: Path, config: dict[str, Any], state: dict[str, Any]
) -> None:
    if commit_agent_result_if_complete(run_directory, state):
        return

    definition = agents.get(config["agent"]["framework"])
    try:
        if definition.prepare_auth is not None:
            definition.prepare_auth(ROOT)
        missing = [
            name
            for name in config["agent"].get("environment", [])
            if name not in os.environ
        ]
        if missing:
            raise AgentConfigurationError(
                "host environment variables are not set: " + ", ".join(missing)
            )
    except AgentConfigurationError as error:
        raise RunnerError(str(error)) from error

    stage_root = stage_directory(run_directory, state)
    agent_directory = stage_root / "agent"
    agent_directory.mkdir(parents=True, exist_ok=True)
    archive_interrupted_session(agent_directory)
    session_id = uuid.uuid4().hex

    prompt = agents.get(config["agent"]["framework"]).prompt_builder(
        config["dataset"]["name"], False
    )
    focus = None
    repair_mode = config.get("repair", {}).get("mode")
    require_case_diagnoses = (
        repair_mode in {"reasoning_structure_alignment", "baseline_final_answer_only"}
        and config.get("repair", {}).get("require_case_diagnoses", True)
    )
    remaining_diagnoses_only = repair_mode in {"reasoning_structure_alignment", "baseline_final_answer_only"}
    case_diagnosis_error = None
    if repair_mode == "reasoning_structure_alignment":
        from .reasoning_structure_alignment.provision_repair import AGENT_PROMPT
        prompt = AGENT_PROMPT
    elif repair_mode == "baseline_final_answer_only":
        from .baselines.final_answer_only.provision_repair import AGENT_PROMPT
        prompt = AGENT_PROMPT
    resume_context = config.get("repair", {}).get("resume_context")
    if resume_context:
        prompt += "\n\nInterrupted-run recovery context:\n" + resume_context + "\n"
    progress_baseline = progress_reference(run_directory, state)
    prompt_path = agent_directory / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="rsa-apptainer-") as runtime_workdir_name:
        runtime_workdir = Path(runtime_workdir_name)
        agent_home = runtime_workdir / "agent-home"
        agent_home.mkdir()
        home_seed = config["agent"].get("home_seed")
        if home_seed:
            shutil.copytree(home_seed, agent_home, dirs_exist_ok=True)
        try:
            if definition.stage_auth is not None:
                definition.stage_auth(agent_home)
        except AgentConfigurationError as error:
            raise RunnerError(str(error)) from error
        feedback = (
            run_directory / (state.get("provision_feedback") or state["recursive_scope_task"])
            if state.get("provision_feedback") or state.get("recursive_scope_task")
            else None
        )
        submission_check_directory = runtime_workdir / "submission-check"
        submission_check_directory.mkdir()
        submission_check_socket = submission_check_directory / "validator.sock"

        def save_case_diagnoses() -> None:
            if require_case_diagnoses:
                from .reasoning_structure_alignment import case_diagnoses
                rows = case_diagnoses.validate(
                    submission_check_directory / case_diagnoses.FILENAME, feedback,
                    remaining_only=remaining_diagnoses_only,
                    workspace=run_directory / "workspace",
                )
                atomic_json(agent_directory / case_diagnoses.FILENAME, rows)
                if remaining_diagnoses_only:
                    replay = case_diagnoses.latest_replay(feedback, run_directory / "workspace")
                    atomic_json(agent_directory / "case_diagnoses_replay.json", {
                        **replay,
                        "report_sha256": sha256_file(agent_directory / case_diagnoses.FILENAME),
                    })

        def check_submission() -> tuple[bool, str]:
            cleanup_clerk_artifacts(run_directory / "workspace")
            if repair_mode in {"reasoning_structure_alignment", "baseline_final_answer_only"}:
                from .validation import submissions
                submissions.record(run_directory, config, run_directory / "workspace",
                                   trigger="submission_check", agent_home=agent_home)
            try:
                validate_workspace(run_directory / "input", run_directory / "workspace")
                save_case_diagnoses()
                mapping = load_requirement_outputs(
                    run_directory / "workspace", require_resolved=True
                )
                unreachable = (
                    unreachable_catala_blocks(run_directory / "workspace", mapping)
                    if mapping is not None
                    else []
                )
            except RunnerError as validation_error:
                return False, str(validation_error)
            if unreachable:
                return True, (
                    "Catala blocks unreachable from the union of contracted outputs:\n- "
                    + "\n- ".join(unreachable)
                )
            return True, (
                "All Catala blocks are reachable from the union of contracted outputs."
            )

        commands = {}
        if repair_mode in {"reasoning_structure_alignment", "baseline_final_answer_only"}:
            if repair_mode == "reasoning_structure_alignment":
                from .reasoning_structure_alignment import candidate_review as provision_candidate_review
            else:
                from .baselines.final_answer_only import candidate_review as provision_candidate_review
            def replay_candidate() -> dict:
                return provision_candidate_review.review(run_directory, config, agent_home=agent_home)
            commands["replay_candidate"] = replay_candidate

        command = apptainer.invocation(
            config,
            run_directory,
            prompt_path,
            runtime_workdir,
            agent_home,
            feedback,
            submission_check_directory,
        )
        invocation = {
            "session_id": session_id,
            "started_at": utc_now(),
            "runtime": "apptainer",
            "image": config["agent"]["image"],
            "command": command,
            "forwarded_environment_names": config["agent"]["environment"],
            "prompt_sha256": sha256_file(prompt_path),
            "progress_baseline": str(progress_baseline.relative_to(run_directory)),
            "repair_scope": focus["id"] if focus else None,
        }
        atomic_json(agent_directory / "invocation.json", invocation)
        state.update(updated_at=utc_now())
        atomic_json(run_directory / "state.json", state)

        started = time.monotonic()
        record_agent_usage(
            run_directory, config, agent_directory, status="started"
        )
        try:
            try:
                progress_interval = float(
                    config["runtime"].get("progress_interval_seconds", 30.0)
                )
                progress = AgentProgress(
                    agent_directory / "stdout.jsonl",
                    progress_baseline,
                    run_directory / "workspace",
                    change_context="scope" if focus else "run",
                    codex_home=agent_home if definition.name == "codex" else None,
                )
                def report_progress(elapsed_seconds: float) -> None:
                    progress.report(elapsed_seconds)
                    record_agent_usage(
                        run_directory, config, agent_directory,
                        elapsed=round(elapsed_seconds, 3), status="running",
                    )
                if progress_interval > 0:
                    print(
                        f"agent session started: {agent_directory}",
                        file=sys.stderr,
                        flush=True,
                    )
                with apptainer.submission_check_service(
                    submission_check_socket,
                    check_submission,
                    commands,
                ):
                    exit_code, timed_out, elapsed = apptainer.execute(
                        command,
                        prompt,
                        agent_directory / "stdout.jsonl",
                        agent_directory / "stderr.log",
                        config["runtime"].get("agent_timeout_seconds"),
                        apptainer.environment(config, submission_check=True),
                        report_progress,
                        progress_interval,
                    )
            except AgentConfigurationError as error:
                raise RunnerError(str(error)) from error
        finally:
            try:
                save_case_diagnoses()
            except RunnerError as diagnosis_error:
                case_diagnosis_error = str(diagnosis_error)
            if definition.name == "codex":
                usage_tracking.capture_codex_usage(
                    agent_home, agent_directory / "stdout.jsonl"
                )
            if repair_mode in {"reasoning_structure_alignment", "baseline_final_answer_only"}:
                from .validation import submissions
                submissions.record(run_directory, config, run_directory / "workspace",
                                   trigger="agent_exit", agent_home=agent_home)
            record_agent_usage(
                run_directory,
                config,
                agent_directory,
                elapsed=round(time.monotonic() - started, 3),
            )
            try:
                if definition.persist_auth is not None:
                    definition.persist_auth(agent_home)
            except AgentConfigurationError as error:
                raise RunnerError(str(error)) from error
            finally:
                cleanup_clerk_artifacts(run_directory / "workspace")
    usage_record = record_agent_usage(
        run_directory,
        config,
        agent_directory,
        elapsed=round(elapsed, 3),
        status="completed" if exit_code == 0 and not timed_out else "failed",
    )

    integrity: dict[str, Any] | None = None
    error: str | None = None
    recursive_session = state.get("recursive_phase") == "scope"
    if (exit_code == 0 and not timed_out) or recursive_session:
        try:
            if case_diagnosis_error:
                raise RunnerError(case_diagnosis_error)
            integrity = validate_workspace(
                run_directory / "input", run_directory / "workspace"
            )
        except RunnerError as validation_error:
            error = str(validation_error)
    else:
        error = (
            "agent container timed out"
            if timed_out
            else f"agent container exited with status {exit_code}"
        )
    rejected_error = None
    if error is not None and recursive_session:
        rejected_error = error
        rejected = stage_directory(run_directory, state) / "rejected_workspace"
        if rejected.exists():
            shutil.rmtree(rejected)
        shutil.move(run_directory / "workspace", rejected)
        before = (
            stage_directory(
                run_directory,
                {
                    **state,
                    "recursive_step": "analysis",
                },
            )
            / "snapshot"
        )
        publish_copy(before, run_directory / "workspace")
        integrity = validate_workspace(
            run_directory / "input", run_directory / "workspace"
        )
        error = None
    session_result = {
        "status": "completed" if error is None else "failed",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "integrity": integrity,
        "error": error,
        "rejected_workspace_error": rejected_error,
        "usage": usage_record,
        "finished_at": utc_now(),
    }
    atomic_json(agent_directory / "result.json", session_result)
    state.update(updated_at=utc_now())
    atomic_json(run_directory / "state.json", state)
    if error is not None:
        raise RunnerError(f"agent session failed: {error}; artifacts: {agent_directory}")

    if not commit_agent_result_if_complete(run_directory, state):
        raise RunnerError("failed to commit the completed agent stage")


def run(run_directory: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    run_agent_stage(run_directory, config, state)
