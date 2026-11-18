"""Execute and resume initial and repair pipelines from their durable state."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rsa_formalizer.stages import formalization, validation
from rsa_formalizer.stages.utils import usage
from rsa_formalizer.stages.utils.common import (
    SCHEMA_VERSION, RunnerError, atomic_json, load_json, run_lock,
)
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment import experiment
from rsa_formalizer.utils.cli_support import pair_summary


REASONING_STEPS = {
    "bobcat",
    "compiled_replay",
    "reasoning",
    "comparison",
    "scope_analysis",
    "scope_result",
    "scope_finalize",
}


def _canonicalize_stage(state: dict[str, Any]) -> bool:
    stage = state.get("next_stage")
    if stage == "agent":
        initial = state.get("recursive_phase", "initial") == "initial"
        canonical = "formalization" if initial else "reasoning_structure_alignment"
    elif stage in REASONING_STEPS:
        canonical = "reasoning_structure_alignment"
    else:
        canonical = stage
    if canonical == stage:
        return False
    if canonical == "reasoning_structure_alignment":
        state["reasoning_structure_alignment_step"] = stage
    state["next_stage"] = canonical
    return True


def resume_run(run_directory: Path) -> dict[str, Any]:
    run_directory = run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise RunnerError(f"run directory does not exist: {run_directory}")
    with run_lock(run_directory):
        config = load_json(run_directory / "config.json")
        state = load_json(run_directory / "state.json")
        if _canonicalize_stage(state):
            atomic_json(run_directory / "state.json", state)
        if "jobs" not in config["reasoning_trace"]:
            config["reasoning_trace"]["jobs"] = 8
            atomic_json(run_directory / "config.json", config)
        usage.reconcile(run_directory)
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

        mode = config.get("repair", {}).get("mode")
        if mode in {"provision_shared", "reasoning_structure_alignment"}:
            from rsa_formalizer.stages.reasoning_structure_alignment import provision_repair
            return provision_repair.run(run_directory, config, state)
        if mode == "baseline_final_answer_only":
            from rsa_formalizer.stages.baselines.final_answer_only import provision_repair
            return provision_repair.run(run_directory, config, state)

        stage = state["next_stage"]
        if stage == "formalization":
            formalization.run(run_directory, config, state)
        elif stage == "validation":
            if not validation.run(run_directory, config, state):
                raise RunnerError("recursive repair requires validation/scoring support")
        elif stage == "reasoning_structure_alignment":
            raise RunnerError(
                "legacy recursive alignment is no longer supported; use main_initial.py "
                "to generate tests and main_repair.py to repair"
            )
        elif stage != "finished":
            raise RunnerError(f"unsupported next stage: {stage}")
        return load_json(run_directory / "state.json")


def drive(run_directory: Path, *, until: str = "finished") -> dict:
    """Advance one durable stage at a time, resuming from saved state."""
    run_directory = run_directory.resolve()
    try:
        while True:
            state = exp.load_json(run_directory / "state.json")
            if (state.get("next_stage") in {"finished", "fork_ready"}
                    or (until == "initial_validation" and state.get("verification_summary"))):
                exp.atomic_json(run_directory / "driver_status.json", {
                    "status": state.get("status"), "stage": state.get("next_stage"),
                    "verification_summary": state.get("verification_summary"),
                    "updated_at": exp.utc_now()})
                return state
            exp.atomic_json(run_directory / "driver_status.json", {
                "status": "running", "stage": state["next_stage"],
                "updated_at": exp.utc_now()})
            previous = state
            state = resume_run(run_directory)
            if state == previous:
                raise exp.RunnerError("pipeline made no state transition")
    except BaseException as error:
        exp.atomic_json(run_directory / "driver_status.json", {
            "status": "stopped" if isinstance(error, KeyboardInterrupt) else "failed",
            "error": str(error), "updated_at": exp.utc_now()})
        raise


def complete_initial(run: Path):
    config = exp.load_json(run / "config.json")
    if config.get("repair", {}).get("mode") not in {"initial_validation", "provision_shared"}:
        raise exp.RunnerError("use main_repair.py to resume a repair run")
    state = exp.load_json(run / "state.json")
    if config.get("repair", {}).get("mode") == "initial_validation":
        drive(run, until="initial_validation")
        experiment.prepare_initial(run)
    elif "provision_phase" not in state:
        # Recover an interruption between the generation config and state writes.
        experiment.prepare_initial(run)
    return drive(run)


def complete_repair(run: Path):
    if exp.load_json(run / "config.json").get("repair", {}).get("mode") not in experiment.MODES:
        raise exp.RunnerError("use main_initial.py to resume an initial run")
    return drive(run)


def run_pair(shared: Path) -> dict:
    """Wait for shared evidence, then run the two independent repairs in order."""
    shared = shared.resolve()
    while True:
        state = exp.load_json(shared / "state.json")
        if state.get("provision_phase") == "fork_ready":
            break
        driver = shared / "driver_status.json"
        status = exp.load_json(driver) if driver.is_file() else {}
        if status.get("status") == "failed":
            raise exp.RunnerError(f"shared generation failed: {status.get('error')}")
        if state.get("status") not in {"running", "ready"}:
            raise exp.RunnerError(f"shared generation stopped at {state.get('status')}")
        time.sleep(10)
    existing = shared / "forks.json"
    forks = exp.load_json(existing) if existing.is_file() else {}
    for mode in experiment.MODES:
        run = Path(forks[mode]) if mode in forks else experiment.fork(shared, mode)
        drive(run)
        forks = exp.load_json(shared / "forks.json")
    return pair_summary(shared)
