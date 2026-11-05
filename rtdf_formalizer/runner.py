"""Run the three durable formalization pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .stages import formalization
from .stages import reasoning_trace_diff_fuzzing
from .stages import validation
from .stages.utils import usage
from .stages.utils.common import (
    ROOT,
    RUNS,
    SCHEMA_VERSION,
    RunnerError,
    atomic_json,
    load_json,
    run_lock,
)
from .stages.utils.run_state import create_run as _create_run
from .stages.utils.run_state import migrate_run_snapshots as _migrate_run_snapshots

__all__ = ["ROOT", "RUNS", "RunnerError", "create_run", "resume_run"]

PIPELINE_STAGES = (
    "formalization",
    "validation",
    "reasoning_trace_diff_fuzzing",
)
REASONING_STEPS = {
    "bobcat",
    "compiled_replay",
    "reasoning",
    "comparison",
    "scope_analysis",
    "scope_result",
    "scope_finalize",
}


def create_run(args: Any) -> Path:
    return _create_run(args)


def migrate_run_snapshots(runs_directory: Path = RUNS) -> list[Path]:
    return _migrate_run_snapshots(runs_directory)


def _canonicalize_stage(state: dict[str, Any]) -> bool:
    stage = state.get("next_stage")
    if stage == "agent":
        initial = state.get("recursive_phase", "initial") == "initial"
        canonical = "formalization" if initial else "reasoning_trace_diff_fuzzing"
    elif stage in REASONING_STEPS:
        canonical = "reasoning_trace_diff_fuzzing"
    else:
        canonical = stage
    if canonical == stage:
        return False
    if canonical == "reasoning_trace_diff_fuzzing":
        state["reasoning_trace_diff_fuzzing_step"] = stage
    state["next_stage"] = canonical
    return True


def resume_run(
    run_directory: Path, *, continue_reasoning: bool = False
) -> dict[str, Any]:
    run_directory = run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise RunnerError(f"run directory does not exist: {run_directory}")
    with run_lock(run_directory):
        config = load_json(run_directory / "config.json")
        state = load_json(run_directory / "state.json")
        if _canonicalize_stage(state):
            atomic_json(run_directory / "state.json", state)
        selected_mode = reasoning_trace_diff_fuzzing.repair.mode(config)
        if selected_mode is not None and "max_iteration" not in config["repair"]:
            config["repair"]["max_iteration"] = (
                reasoning_trace_diff_fuzzing.repair.DEFAULT_MAX_ITERATION
            )
            atomic_json(run_directory / "config.json", config)
        usage.reconcile(run_directory)
        reasoning_trace_diff_fuzzing.backfill_options(run_directory, config)
        if (
            config.get("schema_version") != SCHEMA_VERSION
            or state.get("schema_version") != SCHEMA_VERSION
        ):
            raise RunnerError("unsupported run schema version")
        if config.get("run_id") != state.get(
            "run_id"
        ) or run_directory.name != config.get("run_id"):
            raise RunnerError("run ID differs between directory, config, and state")
        formalization.recover_agent_usage(run_directory, config)

        stage = state["next_stage"]
        if stage == "formalization":
            formalization.run(run_directory, config, state)
        elif stage == "validation":
            if not validation.run(run_directory, config, state) and selected_mode:
                raise RunnerError("repair requires validation/scoring support")
        elif stage == "reasoning_trace_diff_fuzzing":
            if selected_mode is None:
                if continue_reasoning:
                    raise RunnerError(
                        "--continue-reasoning requires answer-only repair mode"
                    )
                reasoning_trace_diff_fuzzing.run(run_directory, config, state)
            else:
                return reasoning_trace_diff_fuzzing.repair.resume(
                    run_directory,
                    config,
                    state,
                    selected_mode,
                    continue_reasoning=continue_reasoning,
                )
        elif stage != "finished":
            raise RunnerError(f"unsupported next stage: {stage}")
        return load_json(run_directory / "state.json")
