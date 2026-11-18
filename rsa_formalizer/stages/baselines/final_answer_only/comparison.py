"""Compare only final Catala and LLM answers for the paired baseline."""

from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from rsa_formalizer.bobcat import compiled_json
from rsa_formalizer.bobcat.trace import schema_scopes
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment.generate_llm_trace import parse_final_answer
from rsa_formalizer.stages.validation.information_extraction import _validation_schema


def compare(run: Path, state: dict, symbolic, natural: list[dict]) -> dict:
    stage = exp.stage_directory(run, state)
    formats_path = stage / "tests_bobcat_symbolic_results/input_formats.json"
    scopes = schema_scopes(exp.load_json(formats_path)) if formats_path.is_file() else []
    schemas = {(item["compiler_file"], item["scope"]): item["output_schema"]
               for item in scopes}
    counts = {name: sum(item["scope"] == name for item in scopes)
              for name in {item["scope"] for item in scopes}}
    unique = {item["scope"]: item["output_schema"] for item in scopes
              if counts[item["scope"]] == 1}
    by_id = {item["id"]: item for item in natural}
    records = []
    for formal in symbolic:
        response = by_id.get(formal["id"], {})
        answer, parse_error = parse_final_answer(response.get("output_text"))
        schema = (schemas.get((formal.get("source"), formal.get("target")))
                  or unique.get(formal.get("target"), {}))
        output_name = formal.get("output_name")
        if output_name:
            schema = compiled_json.named_output_schema(schema, output_name)
        code_error = formal.get("error")
        llm_error = response.get("error") or parse_error
        if output_name and not llm_error:
            try:
                answer = compiled_json.named_answer(answer, output_name)
                issues = list(Draft202012Validator(_validation_schema(schema)).iter_errors(answer))
                if issues:
                    llm_error = "invalid answer: " + issues[0].message
            except ValueError as error:
                llm_error = str(error)
        catala = (compiled_json.project_output_json(formal["output"], schema)
                  if schema else formal["output"])
        if output_name and not code_error:
            if not isinstance(catala, dict) or any(
                    name not in catala for name in schema.get("required", [])):
                code_error = f"execution did not return the named output {output_name}"
        if code_error:
            catala = None
        if llm_error:
            answer = None
        aligned = (None if code_error or llm_error else
                   compiled_json.json_equivalent(answer, catala, schema))
        records.append({
            "id": formal["id"], "inputs": formal.get("inputs"),
            "catala_answer": catala, "llm_final_answer": answer,
            "code_execution_error": bool(code_error),
            "code_execution_diagnostic": str(code_error) if code_error else None,
            "llm_reasoning_error": bool(llm_error),
            "llm_reasoning_diagnostic": str(llm_error) if llm_error else None,
            "final_answer_parse_error": parse_error,
            "final_answer_aligned": aligned,
        })
    summary = {
        "total": len(records),
        "final_answers_parsed": sum(row["llm_final_answer"] is not None for row in records),
        "final_answers_aligned": sum(row["final_answer_aligned"] is True for row in records),
        "final_answers_misaligned": sum(row["final_answer_aligned"] is False for row in records),
        "cases": records,
    }
    exp.atomic_json(stage / "tests_final_answer_comparison/summary.json", summary)
    return summary
