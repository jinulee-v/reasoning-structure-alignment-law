"""Run creation, snapshot publication, and migration."""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from rsa_formalizer import agents
from rsa_formalizer.agents import apptainer
from rsa_formalizer.agents.base import AgentConfigurationError
from .guidance import canonical_dataset_name, without_input_description_guidance
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
from .workspace_validation import validate_workspace


def resolve_dataset(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        named_dataset = ROOT / "data" / "raw" / value
        candidate = named_dataset if named_dataset.is_dir() else ROOT / candidate
    candidate = candidate.resolve()
    if not candidate.is_dir():
        raise RunnerError(f"dataset directory does not exist: {candidate}")
    if not (candidate / "RSA_MANIFEST.json").is_file():
        raise RunnerError(f"dataset has no RSA_MANIFEST.json: {candidate}")
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


def snapshot_manifest(snapshot: Path) -> dict[str, Any]:
    # Describe an immutable copy of the agent workspace.
    files = {
        relative: sha256_file(path)
        for relative, path in sorted(relative_files(snapshot).items())
    }
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "tree_sha256": tree_hash(snapshot),
        "files": files,
    }


def stage_directory(run_directory: Path, state: dict[str, Any]) -> Path:
    # Resolve the initial draft and recursive scope revisions through one boundary.
    if state.get("_stage_directory"):
        return Path(state["_stage_directory"])
    if state.get("recursive_phase") == "initial":
        return run_directory / "initial"
    if state.get("recursive_phase") == "scope":
        from rsa_formalizer.stages.reasoning_structure_alignment.repair import (
            recursive as recursive_repair,
        )

        return recursive_repair.revision_directory(run_directory, state)
    raise RunnerError("run state has no recursive phase")


def publish_stage_snapshot(run_directory: Path, state: dict[str, Any]) -> Path:
    # Publish or validate the frozen workspace used by the active stage.
    stage_root = stage_directory(run_directory, state)
    snapshot = stage_root / "snapshot"
    manifest_path = stage_root / "snapshot.json"

    if not snapshot.exists():
        validate_workspace(run_directory / "input", run_directory / "workspace")
        publish_copy(run_directory / "workspace", snapshot)
    elif not snapshot.is_dir():
        raise RunnerError(f"stage snapshot is not a directory: {snapshot}")
    validate_workspace(run_directory / "input", snapshot)
    expected = snapshot_manifest(snapshot)
    if manifest_path.is_file():
        if load_json(manifest_path) != expected:
            raise RunnerError(f"stage snapshot no longer matches {manifest_path}")
    else:
        atomic_json(manifest_path, expected)
    return snapshot


def create_run(args: Any) -> Path:
    from rsa_formalizer.stages.reasoning_structure_alignment import repair

    repair_settings = {
        "max_revisions_per_scope": getattr(args, "max_scope_revisions", 2),
        "scope_selection": getattr(args, "repair_scope_selection", "all"),
    }
    repair.max_revisions_per_scope({"repair": repair_settings})
    repair.scope_selection({"repair": repair_settings})
    dataset = resolve_dataset(args.dataset)
    reasoning_trace_provider = (
        getattr(args, "reasoning_trace_provider", None) or args.agent_provider
    )
    reasoning_trace_model = (
        getattr(args, "reasoning_trace_model", None) or args.agent_model
    )
    run_id = args.run_id or new_run_id(
        dataset, args.agent, args.agent_model, reasoning_trace_model
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
            "provider": reasoning_trace_provider,
            "model": reasoning_trace_model,
            "jobs": getattr(args, "reasoning_jobs", 8),
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
            "model": getattr(args, "extraction_model", None) or "gpt-6-luna",
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
        "reasoning_structure_alignment": {
            "bobcat_timeout_seconds": getattr(args, "bobcat_timeout_seconds", 1800),
            "bobcat_positive_hundred_money_inputs": getattr(
                args, "bobcat_positive_hundred_money_inputs", True
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
            "llm_generated_tests_per_scope": getattr(
                args, "llm_generated_tests_per_scope", 6
            ),
            "metamorphic_pairs_per_scope": getattr(
                args, "metamorphic_pairs_per_scope", 6
            ),
            "statute_source": getattr(args, "statute_source", "gold"),
        },
        "runtime": runtime,
    }
    try:
        atomic_json(staging_directory / "config.json", config)
        publish_copy(dataset, staging_directory / "input")
        (staging_directory / "input" / "INPUT_VARIABLE_DESCRIPTION.json").unlink(
            missing_ok=True
        )
        # Oracle tests are kept outside the coding agent's editable workspace.
        shutil.rmtree(staging_directory / "input" / "tests_catala", ignore_errors=True)
        canonical_name = canonical_dataset_name(dataset.name)
        if canonical_name is not None:
            guidance_path = staging_directory / "input" / f"{canonical_name}.md"
            if guidance_path.is_file():
                guidance_path.write_text(
                    without_input_description_guidance(
                        guidance_path.read_text(encoding="utf-8")
                    ) + "\n",
                    encoding="utf-8",
                )
        publish_copy(staging_directory / "input", staging_directory / "workspace")
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "completed_stages": ["initialized"],
            "next_stage": "formalization",
            "status": "running",
            "updated_at": utc_now(),
        }
        state["recursive_phase"] = "initial"
        atomic_json(staging_directory / "state.json", state)
        os.replace(staging_directory, run_directory)
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
    return run_directory
