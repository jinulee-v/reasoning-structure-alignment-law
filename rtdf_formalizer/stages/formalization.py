"""Coding-agent formalization stage."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from rtdf_formalizer import agents
from rtdf_formalizer.agents import apptainer
from rtdf_formalizer.agents.base import (
    AgentConfigurationError,
)

from .utils import usage as usage_tracking
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair
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
    next_attempt_directory,
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
        active_attempt=None,
        updated_at=utc_now(),
    )
    atomic_json(run_directory / "state.json", state)
    return True


def record_agent_usage(
    run_directory: Path,
    config: dict[str, Any],
    iteration: int,
    attempt: Path,
    *,
    elapsed: float | None = None,
    status: str = "interrupted-or-recovered",
) -> dict[str, Any]:
    stdout = attempt / "stdout.jsonl"
    prompt_path = attempt / "prompt.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    usage = (
        extract_usage(stdout, prompt)
        if stdout.is_file()
        else usage_tracking.api_counts({})
    )
    metadata = extract_request_metadata(stdout) if stdout.is_file() else {}
    result = {
        "run_id": config["run_id"],
        "iteration": iteration,
        "stage": "agent",
        "attempt": attempt.name,
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
    usage_tracking.record(
        run_directory, f"agent:{attempt.relative_to(run_directory).as_posix()}", result
    )
    return result


def recover_agent_usage(run_directory: Path, config: dict[str, Any]) -> None:
    ledger = run_directory / "usage.jsonl"
    legacy = (
        [
            row
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
            if not (row := json.loads(line)).get("usage_id")
        ]
        if ledger.is_file()
        else []
    )
    attempts = list((run_directory / "iterations").glob("*/agent/attempt-*"))
    attempts += list((run_directory / "initial/agent").glob("attempt-*"))
    attempts += list(
        (run_directory / "refinement").glob("*/revisions/*/session/agent/attempt-*")
    )
    for attempt in sorted(attempts):
        if not (attempt / "invocation.json").is_file():
            continue
        result_path = attempt / "result.json"
        result = load_json(result_path) if result_path.is_file() else {}
        if result.get("usage") in legacy:
            # Older attempts without request IDs cannot be safely deduplicated by provider ID.
            legacy.remove(result["usage"])
            continue
        iteration = (
            int(attempt.parent.parent.name)
            if attempt.parent.parent.name.isdigit()
            else 0
        )
        record_agent_usage(
            run_directory,
            config,
            iteration,
            attempt,
            elapsed=result.get("elapsed_seconds"),
            status=result.get("status", "interrupted-or-recovered"),
        )


def run_agent_stage(
    run_directory: Path, config: dict[str, Any], state: dict[str, Any]
) -> None:
    repair.prepare_agent(run_directory, config, state)
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

    iteration_directory = stage_directory(run_directory, state)
    agent_directory = iteration_directory / "agent"
    agent_directory.mkdir(parents=True, exist_ok=True)
    attempt = next_attempt_directory(agent_directory)
    attempt.mkdir()

    selected_mode = repair.mode(config)
    feedback_available = (
        selected_mode is None
        and state["iteration"] > 0
        and (
            run_directory / "iterations" / f"{state['iteration'] - 1:03d}" / "feedback"
        ).is_dir()
    )
    prompt = agents.get(config["agent"]["framework"]).prompt_builder(
        config["dataset"]["name"], feedback_available
    )
    if selected_mode is not None:
        focus = None
        if (
            selected_mode is repair.RepairMode.RECURSIVE
            and state.get("recursive_phase") == "scope"
        ):
            from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
                recursive as recursive_repair,
            )

            focus = recursive_repair.current_scope(state)
        prompt = repair.prompt(prompt, selected_mode, int(state["iteration"]), focus)
    prompt_path = attempt / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="rtdf-apptainer-") as runtime_workdir_name:
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
            run_directory / "iterations" / f"{state['iteration'] - 1:03d}" / "feedback"
            if feedback_available
            else None
        )
        if selected_mode is repair.RepairMode.RECURSIVE and state.get(
            "recursive_scope_task"
        ):
            feedback = run_directory / state["recursive_scope_task"]
        submission_check_directory = runtime_workdir / "submission-check"
        submission_check_directory.mkdir()
        submission_check_socket = submission_check_directory / "validator.sock"

        def check_submission() -> tuple[bool, str]:
            cleanup_clerk_artifacts(run_directory / "workspace")
            try:
                validate_workspace(run_directory / "input", run_directory / "workspace")
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
            "started_at": utc_now(),
            "runtime": "apptainer",
            "image": config["agent"]["image"],
            "command": command,
            "forwarded_environment_names": config["agent"]["environment"],
            "prompt_sha256": sha256_file(prompt_path),
        }
        atomic_json(attempt / "invocation.json", invocation)
        state.update(active_attempt=attempt.name, updated_at=utc_now())
        atomic_json(run_directory / "state.json", state)

        started = time.monotonic()
        record_agent_usage(
            run_directory, config, int(state["iteration"]), attempt, status="started"
        )
        try:
            try:
                progress_interval = float(
                    config["runtime"].get("progress_interval_seconds", 30.0)
                )
                progress = AgentProgress(
                    attempt / "stdout.jsonl",
                    run_directory / "input",
                    run_directory / "workspace",
                )
                if progress_interval > 0:
                    print(
                        f"agent attempt started: {attempt}",
                        file=sys.stderr,
                        flush=True,
                    )
                with apptainer.submission_check_service(
                    submission_check_socket, check_submission
                ):
                    exit_code, timed_out, elapsed = apptainer.execute(
                        command,
                        prompt,
                        attempt / "stdout.jsonl",
                        attempt / "stderr.log",
                        int(config["runtime"]["timeout_seconds"]),
                        apptainer.environment(config, submission_check=True),
                        progress.report,
                        progress_interval,
                    )
            except AgentConfigurationError as error:
                raise RunnerError(str(error)) from error
        finally:
            record_agent_usage(
                run_directory,
                config,
                int(state["iteration"]),
                attempt,
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
        int(state["iteration"]),
        attempt,
        elapsed=round(elapsed, 3),
        status="completed" if exit_code == 0 and not timed_out else "failed",
    )

    integrity: dict[str, Any] | None = None
    error: str | None = None
    recursive_session = (
        repair.mode(config) is repair.RepairMode.RECURSIVE
        and state.get("recursive_phase") == "scope"
    )
    if (exit_code == 0 and not timed_out) or recursive_session:
        try:
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
    attempt_result = {
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
    atomic_json(attempt / "result.json", attempt_result)
    state.update(active_attempt=None, updated_at=utc_now())
    atomic_json(run_directory / "state.json", state)
    if error is not None:
        raise RunnerError(f"agent attempt failed: {error}; artifacts: {attempt}")

    summary = {**attempt_result, "attempt": attempt.name}
    atomic_json(agent_directory / "result.json", summary)
    if not commit_agent_result_if_complete(run_directory, state):
        raise RunnerError("failed to commit the completed agent stage")


def run(run_directory: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    run_agent_stage(run_directory, config, state)
