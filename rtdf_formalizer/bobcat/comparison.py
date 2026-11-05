"""Structured comparison of Catala replay and LLM traces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.generate_llm_trace import (
    parse_final_answer,
)
from . import compiled_json
from .trace import (
    compare_provision_ids,
    execution_blocks,
    execution_statute_tree,
    execution_tree_size,
    reasoning_tree_provision_ids,
    schema_scopes,
    statute_tree_ids,
)


def compare(
    run_directory: Path,
    state: dict[str, Any],
    symbolic: list[dict[str, Any]],
    natural: list[dict[str, Any]],
) -> dict[str, Any]:
    root = exp.stage_directory(run_directory, state) / "tests_bobcat_comparison"
    root.mkdir(parents=True, exist_ok=True)
    by_id = {record["id"]: record for record in natural}
    formats_path = (
        exp.stage_directory(run_directory, state)
        / "tests_bobcat_symbolic_results/input_formats.json"
    )
    format_scopes = (
        schema_scopes(exp.load_json(formats_path)) if formats_path.is_file() else []
    )
    schemas = {
        (item["compiler_file"], item["scope"]): item["output_schema"]
        for item in format_scopes
    }
    scope_counts: dict[str, int] = {}
    for item in format_scopes:
        scope_counts[item["scope"]] = scope_counts.get(item["scope"], 0) + 1
    schemas_by_unique_scope = {
        item["scope"]: item["output_schema"]
        for item in format_scopes
        if scope_counts[item["scope"]] == 1
    }
    records = []
    for formal in symbolic:
        response = by_id.get(formal["id"], {})
        final_answer, parse_error = parse_final_answer(response.get("output_text"))
        schema = schemas.get(
            (formal.get("source"), formal.get("target"))
        ) or schemas_by_unique_scope.get(formal.get("target"), {})
        output_name = formal.get("output_name")
        if output_name:
            schema = compiled_json.named_output_schema(schema, output_name)
        code_error = formal.get("error")
        llm_error = response.get("error") or parse_error
        if output_name and not llm_error:
            try:
                final_answer = compiled_json.named_answer(final_answer, output_name)
                from jsonschema import Draft202012Validator
                from rtdf_formalizer.stages.validation.information_extraction import (
                    _validation_schema,
                )

                issues = list(
                    Draft202012Validator(_validation_schema(schema)).iter_errors(
                        final_answer
                    )
                )
                if issues:
                    llm_error = "invalid answer: " + issues[0].message
            except ValueError as error:
                llm_error = str(error)
        catala_answer = (
            compiled_json.project_output_json(formal["output"], schema)
            if schema
            else formal["output"]
        )
        if output_name and not code_error:
            if not isinstance(catala_answer, dict) or any(
                name not in catala_answer for name in schema.get("required", [])
            ):
                code_error = f"execution did not return the named output {output_name}"
        if code_error:
            catala_answer = None
        if llm_error:
            final_answer = None
        aligned = (
            None
            if llm_error or code_error
            else compiled_json.json_equivalent(final_answer, catala_answer, schema)
        )
        iteration = exp.stage_directory(run_directory, state)
        snapshot = iteration / "snapshot"
        execution_nodes = execution_tree_size(formal.get("execution_tree", []))
        slice_nodes = execution_tree_size(formal.get("dynamic_slice_tree", []))
        executed_blocks = execution_blocks(snapshot, formal.get("execution_tree", []))
        sliced_blocks = execution_blocks(snapshot, formal.get("dynamic_slice_tree", []))
        if not set(sliced_blocks) <= set(executed_blocks):
            raise ValueError(
                "dynamic-slice blocks are not contained in execution blocks"
            )
        catala_execution_statutes = execution_statute_tree(
            snapshot, formal.get("execution_tree", [])
        )
        catala_slice_statutes = execution_statute_tree(
            snapshot, formal.get("dynamic_slice_tree", [])
        )
        llm_execution_tree = response.get("execution_tree")
        provision_alignment = compare_provision_ids(
            statute_tree_ids(catala_slice_statutes),
            reasoning_tree_provision_ids(llm_execution_tree),
        )
        records.append(
            {
                "id": formal["id"],
                "inputs": formal.get("inputs"),
                "source": formal.get("source"),
                "target": formal.get("target"),
                "requirement_id": formal.get("requirement_id"),
                "output_name": output_name,
                "code_execution_error": bool(code_error),
                "code_execution_diagnostic": str(code_error) if code_error else None,
                "llm_reasoning_error": bool(llm_error),
                "llm_reasoning_diagnostic": llm_error,
                "catala_output": formal["output"],
                "catala_answer": catala_answer,
                "catala_execution_blocks": executed_blocks,
                "catala_dynamic_slice_blocks": sliced_blocks,
                "catala_execution_block_count": len(executed_blocks),
                "catala_dynamic_slice_block_count": len(sliced_blocks),
                "catala_slice_reduction_blocks": (
                    len(executed_blocks) - len(sliced_blocks)
                ),
                "catala_execution_event_nodes": execution_nodes,
                "catala_dynamic_slice_event_nodes": slice_nodes,
                "catala_execution_tree": catala_execution_statutes,
                "catala_dynamic_slice_tree": catala_slice_statutes,
                "llm_reasoning_trace": response.get("output_text"),
                "llm_execution_tree": llm_execution_tree,
                "llm_execution_tree_extraction_error": response.get(
                    "execution_tree_extraction_error"
                ),
                "provision_alignment": provision_alignment,
                "llm_final_answer": final_answer,
                "final_answer_parse_error": parse_error,
                "final_answer_aligned": aligned,
            }
        )
    summary = {
        "total": len(records),
        "llm_traces_generated": sum(
            not row["llm_reasoning_error"]
            and isinstance(row["llm_reasoning_trace"], str)
            and bool(row["llm_reasoning_trace"].strip())
            for row in records
        ),
        "llm_execution_trees_extracted": sum(
            isinstance(row.get("llm_execution_tree"), dict)
            and isinstance(row["llm_execution_tree"].get("steps"), list)
            for row in records
        ),
        "llm_execution_tree_extraction_errors": sum(
            bool(row.get("llm_execution_tree_extraction_error")) for row in records
        ),
        "final_answers_parsed": sum(
            not row["llm_reasoning_error"] and row["final_answer_parse_error"] is None
            for row in records
        ),
        "final_answers_aligned": sum(
            row["final_answer_aligned"] is True for row in records
        ),
        "final_answers_misaligned": sum(
            row["final_answer_aligned"] is False for row in records
        ),
        "final_answer_parse_errors": sum(
            row["final_answer_parse_error"] is not None for row in records
        ),
        "block_sizes": {
            "execution_blocks": sum(
                row["catala_execution_block_count"] for row in records
            ),
            "dynamic_slice_blocks": sum(
                row["catala_dynamic_slice_block_count"] for row in records
            ),
            "reduction_blocks": sum(
                row["catala_slice_reduction_blocks"] for row in records
            ),
            "reduced_cases": sum(
                row["catala_slice_reduction_blocks"] > 0 for row in records
            ),
            "equal_cases": sum(
                row["catala_slice_reduction_blocks"] == 0 for row in records
            ),
        },
        "trace_event_counts": {
            "execution_nodes": sum(
                row["catala_execution_event_nodes"] for row in records
            ),
            "dynamic_slice_nodes": sum(
                row["catala_dynamic_slice_event_nodes"] for row in records
            ),
        },
        "cases": records,
    }
    exp.atomic_json(root / "summary.json", summary, indent=4)
    print(
        f"Generated reasoning traces for {summary['llm_traces_generated']} of "
        f"{summary['total']} tasks; parsed {summary['final_answers_parsed']} final "
        f"answers and aligned {summary['final_answers_aligned']} with Catala.",
        flush=True,
    )
    return summary


def refresh_completed_comparison(
    run_directory: Path, state: dict[str, Any]
) -> dict[str, Any]:
    # Upgrade an existing completed comparison using saved answers only.
    iteration = exp.stage_directory(run_directory, state)
    summary = exp.load_json(iteration / "tests_bobcat_comparison/summary.json")
    symbolic, natural = [], []
    for row in summary["cases"]:
        symbolic.append(
            exp.load_json(
                iteration / "tests_bobcat_symbolic_results" / f"{row['id']}.json"
            )
        )
        response = (
            iteration / "tests_bobcat_natural_language_results" / f"{row['id']}.json"
        )
        if response.is_file():
            natural.append(exp.load_json(response))
    refreshed = compare(run_directory, state, symbolic, natural)
    for key in (
        "bobcat_scope_errors",
        "compiled_execution_errors",
        "dynamic_slice_errors",
        "missing_reasoning_outputs",
    ):
        if key in summary:
            refreshed[key] = summary[key]
    exp.atomic_json(
        iteration / "tests_bobcat_comparison/summary.json", refreshed, indent=4
    )
    return refreshed


run = compare
