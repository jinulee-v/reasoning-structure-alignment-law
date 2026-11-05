"""Coordinate BOBCat generation, replay, LLM reasoning, and comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair
from rtdf_formalizer.bobcat.comparison import compare, refresh_completed_comparison
from rtdf_formalizer.bobcat.replay import replay_compiled
from rtdf_formalizer.bobcat.trace import DEFAULTS, backfill_options, target_name
from .generate_bobcat_test import generate_tests
from .generate_llm_trace import (
    _reasoning_without_answer,
    _sample,
    parse_final_answer,
    reason,
)

__all__ = [
    "DEFAULTS",
    "_reasoning_without_answer",
    "_sample",
    "backfill_options",
    "compare",
    "generate_tests",
    "parse_final_answer",
    "reason",
    "refresh_completed_comparison",
    "replay_compiled",
    "run",
]


def run(run_directory: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    options = backfill_options(run_directory, config)
    cases = generate_tests(run_directory, config, state, options)
    if "bobcat" not in state["completed_stages"]:
        state["completed_stages"].append("bobcat")
    state["next_stage"] = "compiled_replay"
    exp.atomic_json(run_directory / "state.json", state)
    symbolic = replay_compiled(run_directory, config, state, cases)
    if "compiled_replay" not in state["completed_stages"]:
        state["completed_stages"].append("compiled_replay")
    state["next_stage"] = "reasoning"
    exp.atomic_json(run_directory / "state.json", state)
    answer_only = repair.mode(config) is repair.RepairMode.ANSWER_ONLY
    authorized = (
        state.get("reasoning_authorized_iteration") == state.get("iteration")
        if answer_only
        else False
    )
    if (answer_only and not authorized) or (
        not answer_only
        and config.get("reasoning_trace_diff_fuzzing", {}).get(
            "stop_before_reasoning", False
        )
    ):
        if answer_only:
            state.update(status="awaiting_reasoning", updated_at=exp.utc_now())
            exp.atomic_json(run_directory / "state.json", state)
        return
    natural = reason(run_directory, config, state, cases)
    if "reasoning" not in state["completed_stages"]:
        state["completed_stages"].append("reasoning")
    state["next_stage"] = "comparison"
    exp.atomic_json(run_directory / "state.json", state)
    summary = compare(run_directory, state, symbolic, natural)
    bobcat_root = exp.stage_directory(run_directory, state) / "tests_bobcat"
    eligible_scopes = exp.load_json(bobcat_root / "scopes.json")["scopes"]
    summary["bobcat_scope_errors"] = sum(
        "error" in exp.load_json(path)
        for scope in eligible_scopes
        if (
            path := bobcat_root
            / f"{target_name(scope['compiler_file'], scope['scope'])}.json"
        ).is_file()
    )
    summary["compiled_execution_errors"] = sum(
        bool(row.get("error")) for row in symbolic
    )
    summary["dynamic_slice_errors"] = sum(
        bool(row.get("dynamic_slice_error")) for row in symbolic
    )
    summary["missing_reasoning_outputs"] = sum(
        bool(row.get("error"))
        or not isinstance(row.get("output_text"), str)
        or not row["output_text"].strip()
        for row in natural
    )
    comparison_file = bobcat_root.parent / "tests_bobcat_comparison/summary.json"
    exp.atomic_json(comparison_file, summary, indent=4)
    if "comparison" not in state["completed_stages"]:
        state["completed_stages"].append("comparison")
    if "reasoning_trace_diff_fuzzing" not in state["completed_stages"]:
        state["completed_stages"].append("reasoning_trace_diff_fuzzing")
    state.update(
        next_stage="finished",
        status="compared",
        comparison_summary={
            key: value for key, value in summary.items() if key != "cases"
        },
        updated_at=exp.utc_now(),
    )
    exp.atomic_json(run_directory / "state.json", state)
