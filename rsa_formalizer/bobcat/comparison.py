"""Structured comparison of Catala replay and LLM traces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rsa_formalizer.stages import utils as exp
from . import compiled_json, computation_graph
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
    from rsa_formalizer.stages.reasoning_structure_alignment.generate_llm_trace import parse_final_answer

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
    graph_source = None
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
                from rsa_formalizer.stages.validation.information_extraction import (
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
        stage_root = exp.stage_directory(run_directory, state)
        snapshot = stage_root / "snapshot"
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
        graph_record = response.get("computation_graph")
        graph_only = graph_record is not None and formal.get("case_origin") == "provision"
        llm_execution_tree = None if graph_only else response.get("execution_tree")
        provision_alignment = (None if graph_only else compare_provision_ids(
            statute_tree_ids(catala_slice_statutes),
            reasoning_tree_provision_ids(llm_execution_tree),
        ))
        generated_reasoning_tree = formal.get("generated_reasoning_tree")
        generation_provision_alignment = (
            compare_provision_ids(
                statute_tree_ids(catala_slice_statutes),
                reasoning_tree_provision_ids(generated_reasoning_tree),
            )
            if isinstance(generated_reasoning_tree, dict)
            else None
        )
        graph_alignment = None
        if graph_record is not None:
            graph_alignment = {"status": graph_record.get("status"), "error": graph_record.get("error")}
            if code_error:
                graph_alignment = {"status": "execution_error", "error": str(code_error)}
            elif graph_record.get("status") == "complete":
                try:
                    if graph_source is None:
                        graph_source = computation_graph.source_catalog(snapshot)
                    prepared = computation_graph.prepare(formal.get("execution_tree", []), snapshot,
                        formal.get("inputs"), formal.get("dynamic_slice_tree"), graph_source)
                    graph_alignment = computation_graph.compare(prepared, graph_record["graph"],
                        response.get("output_text") or "", graph_record["catalog"])
                except (ValueError, KeyError, TypeError) as error:
                    graph_alignment = {"status": "comparison_error", "error": f"{type(error).__name__}: {error}"}
        records.append(
            {
                "id": formal["id"],
                "inputs": formal.get("inputs"),
                "source": formal.get("source"),
                "target": formal.get("target"),
                "requirement_id": formal.get("requirement_id"),
                "output_name": output_name,
                "case_origin": formal.get("case_origin", "bobcat"),
                "test_strategy": formal.get("test_strategy"),
                "test_rationale": formal.get("test_rationale"),
                "natural_language_facts": formal.get("natural_language_facts"),
                "natural_language_question": formal.get("natural_language_question"),
                "generated_expected_answer": formal.get("generated_expected_answer"),
                "generated_reasoning_tree": generated_reasoning_tree,
                "generation_provision_alignment": generation_provision_alignment,
                "mapped_provision_ids": formal.get("mapped_provision_ids"),
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
                "llm_execution_tree_extraction_error": (None if graph_only else response.get(
                    "execution_tree_extraction_error"
                )),
                "provision_alignment": provision_alignment,
                "computation_graph_alignment": graph_alignment,
                "llm_final_answer": final_answer,
                "final_answer_parse_error": parse_error,
                "final_answer_aligned": aligned,
            }
        )
    summary = {
        "computation_graphs_compared": sum((r.get("computation_graph_alignment") or {}).get("status") == "compared" for r in records),
        "computation_value_mismatch_cases": sum(bool((r.get("computation_graph_alignment") or {}).get("value_mismatches")) for r in records),
        "computation_attribution_difference_cases": sum(bool((r.get("computation_graph_alignment") or {}).get("provision_attribution_differences")) for r in records),
        "computation_graph_diagnostics": sum(r.get("computation_graph_alignment") is not None and r["computation_graph_alignment"].get("status") != "compared" for r in records),
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
        "by_case_origin": {
            origin: {
                "total": sum(row["case_origin"] == origin for row in records),
                "aligned": sum(
                    row["case_origin"] == origin and row["final_answer_aligned"] is True
                    for row in records
                ),
                "misaligned": sum(
                    row["case_origin"] == origin
                    and row["final_answer_aligned"] is False
                    for row in records
                ),
            }
            for origin in sorted({row["case_origin"] for row in records})
        },
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
    generation_summary = (
        exp.stage_directory(run_directory, state) / "tests_llm_generated/summary.json"
    )
    if generation_summary.is_file():
        summary["llm_nl_test_generation"] = exp.load_json(generation_summary)
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
    stage_root = exp.stage_directory(run_directory, state)
    summary = exp.load_json(stage_root / "tests_bobcat_comparison/summary.json")
    symbolic, natural = [], []
    for row in summary["cases"]:
        symbolic.append(
            exp.load_json(
                stage_root / "tests_bobcat_symbolic_results" / f"{row['id']}.json"
            )
        )
        response = (
            stage_root / "tests_bobcat_natural_language_results" / f"{row['id']}.json"
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
        stage_root / "tests_bobcat_comparison/summary.json", refreshed, indent=4
    )
    return refreshed


run = compare
