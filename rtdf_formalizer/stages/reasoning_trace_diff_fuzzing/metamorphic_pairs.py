"""Generate and validate provision-preserving metamorphic test pairs."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from rtdf_formalizer.bobcat.trace import (
    branch_provision_outcomes,
    execution_statute_tree,
    statute_tree_ids,
)
from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.utils import usage as usage_tracking
from . import generate_llm_trace
from .generate_llm_test import statute_context


FORMAT = "provision_metamorphic_pairs_v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _branch_map(snapshot: Path, row: dict[str, Any]) -> dict[str, set[Any]]:
    result: dict[str, set[Any]] = {}
    for branch in branch_provision_outcomes(
        snapshot, row.get("dynamic_slice_tree") or row.get("execution_tree") or []
    ):
        result.setdefault(branch["provision"], set()).add(branch.get("outcome"))
    return result


def bobcat_pairs(
    snapshot: Path, symbolic: list[dict[str, Any]], max_pairs: int
) -> list[dict[str, Any]]:
    """Pair BOBCat cases at exact mapped branches with divergent outcomes."""
    if max_pairs <= 0:
        return []
    candidates = [row for row in symbolic if row.get("case_origin", "bobcat") == "bobcat"]
    candidates_by_provision: dict[str, list[dict[str, Any]]] = {}
    for left, right in itertools.combinations(candidates, 2):
        if left.get("error") or right.get("error"):
            continue
        if _canonical(left.get("output")) == _canonical(right.get("output")):
            continue
        left_branches = _branch_map(snapshot, left)
        right_branches = _branch_map(snapshot, right)
        witnesses = [
            provision
            for provision in left_branches.keys() & right_branches.keys()
            if left_branches[provision] != right_branches[provision]
        ]
        if not witnesses:
            continue
        for provision in sorted(witnesses):
            candidates_by_provision.setdefault(provision, []).append({
                "origin": "bobcat",
                "left_case_id": left["id"],
                "right_case_id": right["id"],
                "property": {
                    "output_relation": "different",
                    "divergence_provision": provision,
                    "left_branch_outcomes": sorted(
                        left_branches[provision], key=str
                    ),
                    "right_branch_outcomes": sorted(
                        right_branches[provision], key=str
                    ),
                },
                "preserved": True,
            })
    # Cover distinct branch-attached provisions before taking additional pairs
    # from a provision that is already represented.
    pairs = [
        candidates_by_provision[provision][0]
        for provision in sorted(candidates_by_provision)
    ][:max_pairs]
    if len(pairs) < max_pairs:
        for provision in sorted(candidates_by_provision):
            for pair in candidates_by_provision[provision][1:]:
                pairs.append(pair)
                if len(pairs) >= max_pairs:
                    return pairs
    return pairs


def _schema(case_ids: list[str], provisions: list[str], max_pairs: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["pairs"],
        "properties": {
            "pairs": {
                "type": "array",
                "maxItems": max_pairs,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "left_case_id",
                        "right_case_id",
                        "output_relation",
                        "exclusive_provision",
                        "executed_in",
                        "rationale",
                    ],
                    "properties": {
                        "left_case_id": {"type": "string", "enum": case_ids},
                        "right_case_id": {"type": "string", "enum": case_ids},
                        "output_relation": {
                            "type": "string",
                            "const": "different",
                        },
                        "exclusive_provision": {
                            "type": "string",
                            "enum": provisions,
                        },
                        "executed_in": {"type": "string", "enum": ["left", "right"]},
                        "rationale": {"type": "string", "minLength": 1},
                    },
                },
            }
        },
    }


def _prompt(statutes: str, cases: list[dict[str, Any]], max_pairs: int) -> str:
    return f"""Select at most {max_pairs} metamorphic pairs from the natural-language
legal test cases below. Use only the authoritative provisions and stated facts.

For each pair, the expected legal outputs must differ. Name the most specific supplied
provision that the legal derivation executes for exactly one member, and say whether it
is executed in the left or right member. The named provision must be genuinely needed
to derive that member's answer, not merely mentioned or generally relevant. Explain
the legal contrast briefly. Maximize coverage of distinct exclusive provisions and
distinct factual contrasts across the selected pairs. Do not discuss software, code,
schemas, or existing tests.

AUTHORITATIVE PROVISIONS
========================
{statutes}

AVAILABLE NATURAL-LANGUAGE CASES
================================
{json.dumps(cases, ensure_ascii=False, indent=2)}
"""


def _exact_trace_ids(snapshot: Path, row: dict[str, Any]) -> set[str]:
    return set(
        statute_tree_ids(
            execution_statute_tree(
                snapshot,
                row.get("dynamic_slice_tree") or row.get("execution_tree") or [],
            )
        )
    )


def _revalidate_cached_pairs(
    snapshot: Path,
    symbolic: list[dict[str, Any]],
    cached: dict[str, Any],
    llm_eligible_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Replay fixed pair properties without asking the LLM to select new pairs."""
    by_id = {row.get("id"): row for row in symbolic}
    deterministic = []
    for pair in cached.get("bobcat_pairs", []):
        left = by_id.get(pair.get("left_case_id"))
        right = by_id.get(pair.get("right_case_id"))
        property_ = pair.get("property", {})
        provision = property_.get("divergence_provision")
        preserved = False
        if left and right and not left.get("error") and not right.get("error"):
            left_branches = _branch_map(snapshot, left)
            right_branches = _branch_map(snapshot, right)
            preserved = (
                _canonical(left.get("output")) != _canonical(right.get("output"))
                and left_branches.get(provision, set())
                == set(property_.get("left_branch_outcomes", []))
                and right_branches.get(provision, set())
                == set(property_.get("right_branch_outcomes", []))
            )
        deterministic.append({**pair, "preserved": preserved})

    generated = []
    for pair in cached.get("llm_pairs", []):
        left = by_id.get(pair.get("left_case_id"))
        right = by_id.get(pair.get("right_case_id"))
        property_ = pair.get("property", {})
        eligible = (
            llm_eligible_ids is None
            or (
                pair.get("left_case_id") in llm_eligible_ids
                and pair.get("right_case_id") in llm_eligible_ids
            )
        )
        if (
            left is None
            or right is None
            or left.get("error")
            or right.get("error")
            or not eligible
        ):
            generated.append(
                {
                    **pair,
                    "validation_status": "grounding_unavailable",
                    "catala_output_relation_preserved": None,
                    "catala_trace_property_preserved": None,
                    "preserved": False,
                }
            )
            continue
        claimed = left if property_.get("executed_in") == "left" else right
        other = right if property_.get("executed_in") == "left" else left
        claimed_ids = _exact_trace_ids(snapshot, claimed)
        other_ids = _exact_trace_ids(snapshot, other)
        provision = property_.get("exclusive_provision")
        output_differs = _canonical(left.get("output")) != _canonical(
            right.get("output")
        )
        trace_preserved = provision in claimed_ids and provision not in other_ids
        generated.append(
            {
                **pair,
                "validation_status": "validated",
                "catala_output_relation_preserved": output_differs,
                "catala_trace_property_preserved": trace_preserved,
                "preserved": output_differs and trace_preserved,
                "catala_claimed_side_provisions": sorted(claimed_ids),
                "catala_other_side_provisions": sorted(other_ids),
            }
        )
    return {
        "format": FORMAT,
        "bobcat_pairs": deterministic,
        "llm_pairs": generated,
        "llm_generation_error": cached.get("llm_generation_error"),
        "preserved": sum(pair["preserved"] for pair in deterministic + generated),
        "rejected": sum(
            pair.get("validation_status") == "validated" and not pair["preserved"]
            for pair in generated
        ),
        "grounding_unavailable": sum(
            pair.get("validation_status") == "grounding_unavailable"
            for pair in generated
        ),
        "reused_properties": True,
    }


def _complete_llm_case_ids(comparison: dict[str, Any] | None) -> set[str] | None:
    if comparison is None:
        return None
    return {
        row["id"]
        for row in comparison.get("cases", [])
        if row.get("case_origin") == "llm_generated_nl"
        and isinstance(row.get("llm_final_answer"), dict)
        and bool(row["llm_final_answer"])
        and all(value is not None for value in row["llm_final_answer"].values())
        and not row.get("llm_reasoning_error")
    }


def llm_pairs(
    run: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    scope: dict[str, Any],
    symbolic: list[dict[str, Any]],
    max_pairs: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Ask the LLM to state pair properties, then validate them against Catala."""
    stage = exp.stage_directory(run, state)
    snapshot = stage / "snapshot"
    generation_file = stage / "tests_llm_generated/generation.json"
    if not generation_file.is_file():
        return [], None
    generation = exp.load_json(generation_file)
    generated = generation.get("generated") or {}
    designs = generated.get("cases", [])
    by_design_id = {
        row["generated_design_id"]: row
        for row in symbolic
        if isinstance(row.get("generated_design_id"), str)
        and not row.get("error")
    }
    available = [
        case
        for case in designs
        if isinstance(case.get("id"), str) and case["id"] in by_design_id
    ]
    provisions = generation.get("selected_provision_ids", [])
    if len(available) < 2 or not provisions or max_pairs <= 0:
        return [], None
    statutes, _ = statute_context(run, provisions)
    public_cases = [
        {
            key: case[key]
            for key in (
                "id",
                "facts",
                "question",
                "expected_answer",
                "reasoning_steps",
            )
        }
        for case in available
    ]
    prompt = _prompt(statutes, public_cases, max_pairs)
    schema = _schema([case["id"] for case in available], provisions, max_pairs)
    sampled = usage_tracking.api_call(
        run,
        {
            "run_id": config["run_id"],
            "stage": "metamorphic-pair-generation",
            "framework": "api",
            "provider": config["reasoning_trace"]["provider"],
            "model": config["reasoning_trace"]["model"],
            "scope": scope.get("id"),
        },
        hashlib.sha256(
            (prompt + state.get("_reasoning_cache_nonce", "")).encode()
        ).hexdigest(),
        lambda: generate_llm_trace._sample(config, prompt, schema),
    )
    value = json.loads(sampled.get("output_text") or "")
    by_id = by_design_id
    results = []
    for pair in value.get("pairs", []):
        left = by_id.get(pair["left_case_id"])
        right = by_id.get(pair["right_case_id"])
        if left is None or right is None:
            results.append(
                {
                    "origin": "llm_generated_nl",
                    "left_case_id": pair["left_case_id"],
                    "right_case_id": pair["right_case_id"],
                    "property": pair,
                    "validation_status": "grounding_unavailable",
                    "catala_output_relation_preserved": None,
                    "catala_trace_property_preserved": None,
                    "preserved": False,
                }
            )
            continue
        claimed = left if pair["executed_in"] == "left" else right
        other = right if pair["executed_in"] == "left" else left
        output_differs = _canonical(left.get("output")) != _canonical(right.get("output"))
        claimed_ids = _exact_trace_ids(snapshot, claimed)
        other_ids = _exact_trace_ids(snapshot, other)
        trace_preserved = (
            pair["exclusive_provision"] in claimed_ids
            and pair["exclusive_provision"] not in other_ids
        )
        results.append(
            {
                "origin": "llm_generated_nl",
                "left_case_id": pair["left_case_id"],
                "right_case_id": pair["right_case_id"],
                "property": pair,
                "validation_status": "validated",
                "catala_output_relation_preserved": output_differs,
                "catala_trace_property_preserved": trace_preserved,
                "preserved": output_differs and trace_preserved,
                "catala_claimed_side_provisions": sorted(claimed_ids),
                "catala_other_side_provisions": sorted(other_ids),
            }
        )
    return results, {"prompt": prompt, "response": value, "usage": sampled.get("usage")}


def evaluate_pairs(
    run: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    scope: dict[str, Any],
    symbolic: list[dict[str, Any]],
    max_pairs: int = 6,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = exp.stage_directory(run, state) / "tests_metamorphic_pairs"
    root.mkdir(parents=True, exist_ok=True)
    snapshot = exp.stage_directory(run, state) / "snapshot"
    llm_eligible_ids = _complete_llm_case_ids(comparison)
    llm_symbolic = (
        symbolic
        if llm_eligible_ids is None
        else [
            row
            for row in symbolic
            if row.get("case_origin") != "llm_generated_nl"
            or row.get("id") in llm_eligible_ids
        ]
    )
    summary_file = root / "summary.json"
    if summary_file.is_file():
        cached = exp.load_json(summary_file)
        if cached.get("format") == FORMAT:
            summary = _revalidate_cached_pairs(
                snapshot, symbolic, cached, llm_eligible_ids
            )
            exp.atomic_json(summary_file, summary, indent=2)
            return summary
    deterministic = bobcat_pairs(snapshot, symbolic, max_pairs)
    try:
        generated, generation = llm_pairs(
            run, config, state, scope, llm_symbolic, max_pairs
        )
        error = None
    except Exception as caught:
        generated, generation = [], None
        error = f"{type(caught).__name__}: {caught}"
    summary = {
        "format": FORMAT,
        "bobcat_pairs": deterministic,
        "llm_pairs": generated,
        "llm_generation_error": error,
        "preserved": sum(pair["preserved"] for pair in deterministic + generated),
        "rejected": sum(
            pair.get("validation_status") == "validated" and not pair["preserved"]
            for pair in generated
        ),
        "grounding_unavailable": sum(
            pair.get("validation_status") == "grounding_unavailable"
            for pair in generated
        ),
    }
    exp.atomic_json(root / "summary.json", summary, indent=2)
    if generation:
        (root / "llm.prompt.txt").write_text(generation["prompt"], encoding="utf-8")
        exp.atomic_json(root / "llm.response.json", generation, indent=2)
    return summary
