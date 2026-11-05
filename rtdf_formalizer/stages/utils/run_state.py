"""Run creation, snapshot publication, and migration."""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from rtdf_formalizer import agents
from rtdf_formalizer.agents import apptainer
from rtdf_formalizer.agents.base import AgentConfigurationError
from .catala import tree_hash
from .common import (
    ROOT,
    RUNS,
    SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    RunnerError,
    atomic_json,
    load_json,
    relative_files,
    sha256_file,
    utc_now,
)
from .workspace_validation import integrity_manifest_matches, validate_workspace


def resolve_dataset(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        named_dataset = ROOT / "data" / "raw" / value
        candidate = named_dataset if named_dataset.is_dir() else ROOT / candidate
    candidate = candidate.resolve()
    if not candidate.is_dir():
        raise RunnerError(f"dataset directory does not exist: {candidate}")
    if not (candidate / "RTDF_MANIFEST.json").is_file():
        raise RunnerError(f"dataset has no RTDF_MANIFEST.json: {candidate}")
    return candidate


def slug(value: str, *, limit: int = 48) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-.")
    return (normalized or "unspecified")[:limit]


def new_run_id(
    dataset: Path, agent: str, agent_model: str, reasoning_trace_model: str
) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M")
    return "-".join(
        (
            timestamp,
            slug(agent),
            slug(agent_model),
            slug(reasoning_trace_model),
            slug(dataset.name),
            uuid.uuid4().hex[:8],
        )
    )


def publish_copy(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RunnerError(f"refusing to overwrite {destination}")
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copytree(source, temporary, symlinks=False)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def snapshot_manifest(snapshot: Path, iteration: int) -> dict[str, Any]:
    # Describe an immutable per-iteration copy of the agent workspace.
    files = {
        relative: sha256_file(path)
        for relative, path in sorted(relative_files(snapshot).items())
    }
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "iteration": iteration,
        "tree_sha256": tree_hash(snapshot),
        "files": files,
    }


def stage_directory(run_directory: Path, state: dict[str, Any]) -> Path:
    # Resolve legacy iterations and recursive scope revisions through one artifact boundary.
    if state.get("recursive_phase") == "initial":
        return run_directory / "initial"
    if state.get("recursive_phase") == "scope":
        from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import (
            recursive as recursive_repair,
        )

        return recursive_repair.revision_directory(run_directory, state)
    return run_directory / "iterations" / f"{int(state['iteration']):03d}"


def publish_stage_snapshot(run_directory: Path, state: dict[str, Any]) -> Path:
    # Publish or validate the frozen workspace used by the active stage.
    iteration = int(state.get("iteration", 0))
    iteration_directory = stage_directory(run_directory, state)
    snapshot = iteration_directory / "snapshot"
    manifest_path = iteration_directory / "snapshot.json"

    if not snapshot.exists():
        validate_workspace(run_directory / "input", run_directory / "workspace")
        publish_copy(run_directory / "workspace", snapshot)
    elif not snapshot.is_dir():
        raise RunnerError(f"stage snapshot is not a directory: {snapshot}")
    validate_workspace(run_directory / "input", snapshot)
    expected = snapshot_manifest(snapshot, iteration)
    if manifest_path.is_file():
        if load_json(manifest_path) != expected:
            raise RunnerError(f"stage snapshot no longer matches {manifest_path}")
    else:
        atomic_json(manifest_path, expected)
    return snapshot


def publish_iteration_snapshot(run_directory: Path, iteration: int) -> Path:
    # Publish or validate the frozen workspace used by an iteration.
    return publish_stage_snapshot(
        run_directory, {"iteration": iteration, "recursive_phase": None}
    )


def migrate_run_snapshots(runs_directory: Path = RUNS) -> list[Path]:
    # Backfill the current iteration of pre-snapshot, non-archived runs.
    migrated: list[Path] = []
    if not runs_directory.is_dir():
        return migrated
    for run_directory in sorted(runs_directory.iterdir()):
        if (
            not run_directory.is_dir()
            or run_directory.name in {"_archive", "_archives"}
            or run_directory.name.startswith(".")
            or not (run_directory / "state.json").is_file()
        ):
            continue
        state = load_json(run_directory / "state.json")
        if "agent" not in state.get("completed_stages", []):
            continue
        iteration = int(state["iteration"])
        snapshot = run_directory / "iterations" / f"{iteration:03d}" / "snapshot"
        manifest = snapshot.parent / "snapshot.json"
        changed = not snapshot.is_dir() or not manifest.is_file()
        if not snapshot.exists():
            result_path = snapshot.parent / "agent" / "result.json"
            if not result_path.is_file():
                raise RunnerError(
                    f"cannot migrate run without an agent result: {run_directory}"
                )
            result = load_json(result_path)
            integrity = validate_workspace(
                run_directory / "input", run_directory / "workspace"
            )
            if result.get("status") != "completed" or not integrity_manifest_matches(
                result.get("integrity"), integrity
            ):
                raise RunnerError(
                    f"workspace no longer matches the completed agent result: {run_directory}"
                )
        publish_iteration_snapshot(run_directory, iteration)
        if "snapshot" not in state.get("completed_stages", []):
            stages = state.setdefault("completed_stages", [])
            insertion = stages.index("agent") + 1 if "agent" in stages else len(stages)
            stages.insert(insertion, "snapshot")
            state["updated_at"] = utc_now()
            atomic_json(run_directory / "state.json", state)
            changed = True
        if changed:
            migrated.append(run_directory)
    return migrated


def create_run(args: Any) -> Path:
    from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair

    repair_settings = {
        "mode": getattr(args, "repair_mode", repair.RepairMode.NO_TESTING.value),
        "max_iteration": getattr(args, "max_iteration", repair.DEFAULT_MAX_ITERATION),
    }
    repair_config = {"repair": repair_settings}
    repair.mode(repair_config)
    repair.max_iteration(repair_config)
    dataset = resolve_dataset(args.dataset)
    run_id = args.run_id or new_run_id(
        dataset, args.agent, args.agent_model, args.reasoning_trace_model
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id):
        raise RunnerError("run ID may contain only letters, digits, '.', '_' and '-'")
    run_directory = (RUNS / run_id).resolve()
    if run_directory.parent != RUNS.resolve():
        raise RunnerError("run directory escaped the runs root")
    if run_directory.exists():
        raise RunnerError(f"run already exists; use resume: {run_directory}")

    try:
        agent, runtime = apptainer.configurations(args, agents.configuration(args))
    except AgentConfigurationError as error:
        raise RunnerError(str(error)) from error
    RUNS.mkdir(parents=True, exist_ok=True)
    staging_directory = RUNS / f".{run_id}.{uuid.uuid4().hex}.tmp"
    staging_directory.mkdir()
    config = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": utc_now(),
        "dataset": {"name": dataset.name, "source": str(dataset)},
        "agent": agent,
        "repair": repair_settings,
        "reasoning_trace": {
            "provider": args.reasoning_trace_provider,
            "model": args.reasoning_trace_model,
            **(
                {"base_url": args.reasoning_base_url}
                if getattr(args, "reasoning_base_url", None)
                else {}
            ),
            **(
                {"api_key_env": args.reasoning_api_key_env}
                if getattr(args, "reasoning_api_key_env", "OPENAI_API_KEY")
                != "OPENAI_API_KEY"
                else {}
            ),
        },
        "information_extraction": {
            "provider": getattr(args, "extraction_provider", "openai"),
            "model": getattr(args, "extraction_model", args.reasoning_trace_model),
            **(
                {"base_url": args.extraction_base_url}
                if getattr(args, "extraction_base_url", None)
                else {}
            ),
            **(
                {"api_key_env": args.extraction_api_key_env}
                if getattr(args, "extraction_api_key_env", "OPENAI_API_KEY")
                != "OPENAI_API_KEY"
                else {}
            ),
            "corpora": ["original"],
            "jobs": getattr(args, "extraction_jobs", 8),
        },
        "reasoning_trace_diff_fuzzing": {
            "bobcat_timeout_seconds": getattr(args, "bobcat_timeout_seconds", 1800),
            "bobcat_positive_hundred_money_inputs": getattr(
                args, "bobcat_positive_hundred_money_inputs", False
            ),
            "bobcat_max_list_length": getattr(args, "bobcat_max_list_length", None),
            "bobcat_representation_capacity": getattr(
                args, "bobcat_representation_capacity", 64
            ),
            "bobcat_solver_timeout_ms": getattr(args, "bobcat_solver_timeout_ms", None),
            "bobcat_solver_timeout_max_ms": getattr(
                args, "bobcat_solver_timeout_max_ms", None
            ),
            "bobcat_objective_timeout_ms": getattr(
                args, "bobcat_objective_timeout_ms", None
            ),
            "statute_source": getattr(args, "statute_source", "gold"),
            "stop_before_reasoning": getattr(args, "stop_before_reasoning", False),
        },
        "runtime": runtime,
    }
    try:
        atomic_json(staging_directory / "config.json", config)
        publish_copy(dataset, staging_directory / "input")
        publish_copy(staging_directory / "input", staging_directory / "workspace")
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "iteration": 0,
            "completed_stages": ["initialized"],
            "next_stage": "formalization",
            "status": "running",
            "active_attempt": None,
            "updated_at": utc_now(),
        }
        if repair_settings["mode"] == repair.RepairMode.RECURSIVE.value:
            state["recursive_phase"] = "initial"
        atomic_json(staging_directory / "state.json", state)
        os.replace(staging_directory, run_directory)
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
    return run_directory


def next_attempt_directory(agent_directory: Path) -> Path:
    indices = []
    for path in agent_directory.glob("attempt-*"):
        match = re.fullmatch(r"attempt-(\d+)", path.name)
        if match:
            indices.append(int(match.group(1)))
    return agent_directory / f"attempt-{max(indices, default=-1) + 1:03d}"
