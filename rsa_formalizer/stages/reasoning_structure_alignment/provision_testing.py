"""Provision-targeted, specification-first tests and deterministic evidence reports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.bobcat import compiled_json
from rsa_formalizer.bobcat.trace import schema_scopes
from rsa_formalizer.stages.reasoning_structure_alignment import generate_llm_trace as reasoning
from rsa_formalizer.stages.validation.information_extraction import _validation_schema
from rsa_formalizer.stages.utils import usage as usage_tracking
from rsa_formalizer.stages.utils.prompt_cache import CacheablePrompt
from rsa_formalizer.stages.utils.input_contract import field_descriptions
from rsa_formalizer.stages.utils.input_history import compact


FORMAT = "provision_full_input_diverse_v6_shared"
INPUT_RESPONSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["inputs_json", "condition_explanation"],
    "properties": {"inputs_json": {"type": "string"},
                   "condition_explanation": {"type": "string"}},
}


def entry_points(snapshot: Path, formats: dict) -> list[dict]:
    """Resolve public program contracts, never an internal provision scope."""
    available = schema_scopes(formats)
    mapping = exp.load_requirement_outputs(snapshot, require_resolved=True)
    if not mapping:
        if len(available) != 1:
            raise exp.RunnerError("provision testing needs an explicit public API entry-point contract")
        scope = available[0]
        return [{**scope, "source": scope.get("compiler_file") or scope["file"]}]
    endpoints = []
    for contract in mapping["requirements"]:
        matches = [scope for scope in available if scope["scope"] == contract["scope"]
                   and contract["file"] in (scope.get("compiler_file"), scope.get("file"))]
        if len(matches) != 1:
            raise exp.RunnerError(f"public API has no unique usable schema: {contract['file']}::{contract['scope']}")
        scope = matches[0]
        endpoints.append({**scope, "source": scope.get("compiler_file") or scope["file"],
                          "requirement_id": contract["requirement_id"], "output": contract["output"]})
    return endpoints


def all_provisions(run: Path, config: dict) -> str:
    """Read the complete frozen natural-language specification, without code."""
    statutes = reasoning._statutes(run, config)
    return re.sub(r"^([ \t]*(?:\[[^\]\n]+\][ \t]*)?)>[ \t]*(?:Module|Using)\b[^\n]*",
                  r"\1", statutes, flags=re.MULTILINE).strip()


def input_prompt(statutes: str, schema: dict, target: str, failures: list[dict],
                 field_documentation: str = "", previous_inputs: list[dict] | None = None) -> str:
    contract = (f"\nINPUT FIELD DESCRIPTIONS\n{field_documentation}\n"
                if field_documentation else "")
    prefix = f"""Generate one complete executable test input for the whole program.
The natural-language specification below is authoritative. The target provision
selects the condition to exercise; the input schema is the complete public
entry-point contract. Do not isolate the scope implementing the provision.
Supply concrete facts satisfying the target provision's operative conditions.
For an exception, supply its triggering facts. Include all facts needed to
determine the final program result under ALL supplied provisions, including
interactions, exceptions, classifications, and temporal rules.

Return inputs_json as a string containing exactly one JSON object conforming to
the supplied input schema, plus a short condition_explanation identifying the
concrete supplied facts that trigger the target. Do not return an expected
answer or a separate narrative case. The JSON is the entire authoritative case:
facts asserted only in condition_explanation do not exist for the reasoner or
program. Use primitive facts wherever the schema accepts them; do not substitute
an unstated derived conclusion. Populate every required nested field and use
consistent identities, dates, units, and factual relationships. Omit irrelevant
events rather than padding lists. Use actual values, not placeholders. Correct
the specific failures below and generate a different candidate after rejection.
Generate a materially different applicable configuration from previous inputs.
Discover possible variations yourself from the specification and schema. Merely
renaming identifiers, reordering facts, or changing numbers without changing
material circumstances is insufficient. Prefer a distinct applicable route,
combination of facts, temporal arrangement, or factual representation. Do not
sacrifice applicability or completeness for novelty. In condition_explanation,
explain the material difference as well as why the target applies.

Previous inputs are comparison examples, not authority or expected answers.
Their lossless table encoding uses columns to name row fields, rows for values,
and present masks to distinguish omitted properties from explicit null. An
$object array escapes literal reserved keys. Return ordinary schema-conforming
JSON for the new input, not the history encoding.

ALL NATURAL-LANGUAGE PROVISIONS
{statutes}

COMPLETE PROGRAM INPUT SCHEMA
{json.dumps(schema, ensure_ascii=False, sort_keys=True)}
{contract}
"""
    suffix = f"""TARGET PROVISION
{target}

PREVIOUS FAILURE REASONS
{json.dumps(failures, ensure_ascii=False)}

PREVIOUS SCHEMA-VALID INPUTS
{json.dumps(compact(previous_inputs or []), ensure_ascii=False, separators=(',', ':'))}
"""
    return CacheablePrompt(prefix, suffix, "provision-input-generation")


def _sample_input(run: Path, config: dict, prompt: str, key: str, case_id: str) -> dict:
    settings = config["reasoning_trace"]
    return usage_tracking.api_call(run, {
        "run_id": config["run_id"], "stage": "provision-input-generation", "framework": "api",
        "provider": settings["provider"], "model": settings["model"], "case_id": case_id,
    }, key, lambda: reasoning._sample(config, prompt, INPUT_RESPONSE_SCHEMA))


def _schema_errors(value: Any, schema: dict) -> list[dict]:
    validator = Draft202012Validator(_validation_schema(schema), format_checker=FormatChecker())
    return [{"path": list(error.absolute_path), "message": error.message}
            for error in validator.iter_errors(value)]


def local_id(identifier: str) -> str:
    return identifier.rsplit("/", 1)[-1]


def cites_target(text: str, target: str) -> bool:
    """Require a literal leaf citation in reasoning prose, not the final answer."""
    body = reasoning._reasoning_without_answer(text)
    identifier = local_id(target)
    number = identifier.removeprefix("section")
    suffix = re.escape(number).replace(r"\(", r"\s*\(")
    pattern = r"(?<![\w])(?:section\s*|§\s*)?" + suffix + r"(?![\w]|\s*\()"
    return re.search(pattern, body, flags=re.IGNORECASE) is not None


def discover_targets(snapshot: Path, manifest: dict, formats: dict) -> list[dict]:
    """Read existing XML comments linking Catala fences to provision IDs."""
    endpoints = entry_points(snapshot, formats)
    grouped: dict[str, dict] = {}
    for document in manifest["documents"]:
        source = document["path"]
        text = (snapshot / source).read_text(encoding="utf-8")
        markers = list(re.finditer(r"<!--\s*rsa-block-id:\s*([^;]+);[\s\S]*?-->", text))
        regions = {match.group(1).strip(): text[match.end(): markers[index + 1].start()
                   if index + 1 < len(markers) else len(text)]
                   for index, match in enumerate(markers)}
        for block in document.get("blocks", []):
            provision = block.get("provision_id")
            if not provision or provision == "none" or block.get("kind") != "catala":
                continue
            block_id = block["block_id"]
            if block_id not in regions:
                # The manifest also describes structural/inherited provisions
                # whose code has no attached XML comment in this baseline.
                continue
            region = regions.get(block_id, "")
            fence = re.search(r"^```catala[^\S\n]*\n([\s\S]*?)```", region, re.MULTILINE)
            if fence is None:
                raise exp.RunnerError(f"provision annotation has no Catala fence: {block_id}")
            target = grouped.setdefault(provision, {"provision_id": provision, "blocks": [],
                                                    "entry_points": endpoints})
            target["blocks"].append({"source": source, "block_id": block_id})
    return list(grouped.values())


def target_slug(provision: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", provision) + "-" + hashlib.sha256(provision.encode()).hexdigest()[:10]


def generate_target(run: Path, config: dict, target: dict, baseline: Path,
                    formats: dict, max_attempts: int) -> dict:
    root = run / "provision_repair/tests" / target_slug(target["provision_id"])
    root.mkdir(parents=True, exist_ok=True)
    result_file = root / "result.json"
    statutes = all_provisions(run, config)
    documentation = [field_descriptions(run, endpoint["input_schema"])
                     for endpoint in target.get("entry_points", [])]
    fingerprint = hashlib.sha256(json.dumps([FORMAT, target, statutes, documentation, exp.tree_hash(baseline),
        config.get("reasoning_trace"), config.get("repair", {}).get("computation_graph_alignment"),
        max_attempts], sort_keys=True).encode()).hexdigest()
    if result_file.is_file():
        cached = exp.load_json(result_file)
        if cached.get("fingerprint") != fingerprint:
            raise exp.RunnerError(f"stale provision tests at {root}; archive/reconfigure the paused run before regenerating")
        return cached
    failures = []
    history = []
    accepted = []
    if not target.get("entry_points"):
        result = {"format": FORMAT, "fingerprint": fingerprint, "target": target,
                  "status": "unmapped_entry_point", "attempts": [],
                  "attempt_count": 0, "accepted_tests": []}
        exp.atomic_json(result_file, result)
        return result
    for index in range(max_attempts):
        attempt = root / f"attempt-{index:03d}"
        attempt.mkdir(parents=True, exist_ok=True)
        if not (attempt / "snapshot").exists():
            exp.publish_copy(baseline, attempt / "snapshot")
        exp.atomic_json(attempt / "tests_bobcat_symbolic_results/input_formats.json", formats)
        endpoint = target["entry_points"][index % len(target["entry_points"])]
        state = {"_stage_directory": str(attempt),
                 "_reasoning_cache_nonce": str(attempt.relative_to(run)),
                 "_usage_stage": "provision-reasoning",
                 "_skip_reasoning_structure_extraction": True}
        try:
            case_id = f"provision-{target_slug(target['provision_id'])}-{index:03d}"
            prompt = input_prompt(statutes, endpoint["input_schema"], target["provision_id"], failures,
                                  documentation[index % len(documentation)], history)
            prompt_hash = hashlib.sha256((fingerprint + prompt).encode()).hexdigest()
            (attempt / "input.prompt.txt").write_text(prompt, encoding="utf-8")
            sampled_file = attempt / "input_generation.json"
            cached = exp.load_json(sampled_file) if sampled_file.is_file() else {}
            sampled = cached.get("sampled") if cached.get("prompt_sha256") == prompt_hash else None
            if sampled is None:
                sampled = _sample_input(run, config, prompt, prompt_hash, case_id)
                exp.atomic_json(sampled_file, {"format": FORMAT, "prompt_sha256": prompt_hash, "sampled": sampled})
            if sampled.get("error"):
                raise ValueError(sampled["error"])
            response = json.loads(sampled.get("output_text") or "")
            Draft202012Validator(INPUT_RESPONSE_SCHEMA).validate(response)
            inputs = json.loads(response["inputs_json"])
            issues = _schema_errors(inputs, endpoint["input_schema"])
            if not isinstance(inputs, dict) or issues:
                failure = {"attempt": index, "reason": "invalid_input_schema", "errors": issues,
                           "detail": "input must be a complete entry-point JSON object"}
                failures.append(failure)
                exp.atomic_json(attempt / "rejection.json", failure)
                continue
            history.append({"attempt": index, "source": endpoint["source"],
                            "scope": endpoint["scope"], "inputs": inputs})
            case = {"id": case_id, "target": endpoint["scope"], "source": endpoint["source"],
                    "inputs": inputs, "branches": [], "statute_ids": [], "exact": True,
                    "case_origin": "provision", "test_strategy": "full_input_provision_condition",
                    "input_authority": "structured_json", "statute_context": statutes,
                    "test_rationale": response["condition_explanation"],
                    "target_provision": target["provision_id"],
                    "required_provision": target["provision_id"]}
            if endpoint.get("output"):
                case["output_name"] = endpoint["output"]
            if endpoint.get("requirement_id"):
                case["requirement_id"] = endpoint["requirement_id"]
            exp.atomic_json(attempt / "candidate.json", case)
            try:
                response = reasoning.reason(run, config, state, [case])[0]
            except Exception as error:
                response = {"id": case_id, "output_text": "",
                            "error": f"{type(error).__name__}: {error}"}
            from . import computation_alignment
            try:
                graph = computation_alignment.extract_before_replay(
                    run, config, baseline, case, response)
            except Exception as error:
                graph = {"status": "extraction_error", "error": f"{type(error).__name__}: {error}"}
                folder = baseline.parent / "computation_graph_results" / case_id
                exp.atomic_json(folder / "result.json", graph)
            record = {"attempt": index, "case": case, "reasoning": response,
                      "computation_graph_status": graph.get("status")}
            accepted.append(record)
            exp.atomic_json(attempt / "accepted.json", record)
            continue
        except Exception as error:
            failure = {"attempt": index, "reason": "generation_error", "detail": f"{type(error).__name__}: {error}"}
        failures.append(failure)
        exp.atomic_json(attempt / "rejection.json", failure)
    result = {"format": FORMAT, "fingerprint": fingerprint,
              "target": target, "status": "accepted" if accepted else "attempt_budget_exhausted",
              "attempts": failures, "attempt_count": max_attempts, "accepted_tests": accepted}
    exp.atomic_json(result_file, result)
    return result


def accepted_tests(result: dict) -> list[dict]:
    """Read current collections and historical single-case evidence reports."""
    if "accepted_tests" in result:
        return result["accepted_tests"]
    if result.get("status") == "accepted":
        return [{"attempt": result.get("accepted_attempt"),
                 "case": result["case"], "reasoning": result["reasoning"]}]
    return []


def select_by_computation_graph(results: list[dict], oracles: dict, *, reject_unapplied: bool = True) -> list[dict]:
    """Apply the sole structured target-use gate after graph extraction.

    A failed extraction is inconclusive and retains the candidate. With
    reject_unapplied=False, target use is diagnostic metadata, never a gate.
    """
    from .computation_alignment import target_application

    selected = []
    for result in results:
        kept = []
        failures = list(result.get("attempts", []))
        for test in accepted_tests(result):
            case = test["case"]
            finding = target_application(oracles.get(case["id"], {}),
                                         result["target"]["provision_id"],
                                         test["reasoning"].get("output_text", ""))
            if reject_unapplied and finding["status"] == "not_applied":
                failures.append({"attempt": test.get("attempt"),
                                 "reason": "target_not_used_in_computation_graph",
                                 "detail": finding["reason"], "case_id": case["id"]})
            else:
                kept.append({**test, "computation_graph_selection": finding})
        selected.append({**result, "accepted_tests": kept, "attempts": failures,
                         "status": "accepted" if kept else "attempt_budget_exhausted"})
    return selected


def write_reports(root: Path, results: list[dict], summary: dict,
                  symbolic: list[dict] | None = None) -> dict:
    """Route raw evidence to the agent; no model-written diagnosis or summary."""
    config_path = root.parent / "config.json"
    config = exp.load_json(config_path) if config_path.is_file() else {}
    reuse_run = config.get("repair", {}).get("feedback_reuse_from")
    reuse_before = Path(reuse_run) / "provision_repair/before.json" if reuse_run else None
    reuse_rows = ({row["id"]: row for row in exp.load_json(reuse_before)["cases"]}
                  if reuse_before and reuse_before.is_file() else {})
    by_case = {test["case"]["id"]: {**test, "target": item["target"]}
               for item in results for test in accepted_tests(item)}
    feedback = root / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    reports = []
    diagnostics = []
    by_symbolic = symbolic if hasattr(symbolic, "case_files") else {row["id"]: row for row in symbolic or []}
    all_targets = {item["target"]["provision_id"]: item["target"] for item in results}
    from rsa_formalizer.bobcat.trace import provision_ids_overlap
    for row in summary.get("cases", []):
        result = by_case[row["id"]]
        graph = row.get("computation_graph_alignment")
        structure_mismatch = bool((graph or {}).get("value_mismatches"))
        diagnostic = bool(row.get("code_execution_error") or row.get("llm_reasoning_error")
            or row.get("llm_execution_tree_extraction_error")
            or (graph is not None and graph.get("status") != "compared"))
        mismatch = row.get("final_answer_aligned") is False or structure_mismatch
        if not mismatch and not diagnostic:
            continue
        provision = result["target"]["provision_id"]
        destination = feedback / target_slug(provision) / target_slug(row["id"])
        destination.mkdir(parents=True, exist_ok=True)
        steps = (graph or {}).get("value_mismatches", [])
        related = {p for step in steps for p in step.get("catala_provisions", [])}
        related.update(step["llm_provision"] for step in steps if step.get("llm_provision"))
        linked = {provision: result["target"]}
        for candidate, target in all_targets.items():
            if any(provision_ids_overlap(candidate, p) for p in related):
                linked[candidate] = target
        report = {"target_provision": provision, "target_blocks": result["target"]["blocks"],
                  "linked_provisions": [{"provision": p, "blocks": t["blocks"]} for p, t in sorted(linked.items())],
                  "case": result["case"], "comparison": row,
                  "earliest_comparable_mismatches": (graph or {}).get("earliest_comparable_mismatches", []),
                  "answer_misaligned": row.get("final_answer_aligned") is False,
                  "structure_misaligned": structure_mismatch,
                  "computation_graph_selection": result.get("computation_graph_selection"),
                  "report_reasons": (["final_answer_failure"] if row.get("final_answer_aligned") is False else [])
                    + (["intermediate_value_divergence"] if structure_mismatch else [])}
        reusable = (reuse_rows.get(row["id"]) == row
                    and (destination / "report.json").is_file()
                    and exp.load_json(destination / "report.json") == report
                    and (destination / "catala_replay.json").is_file()
                    and (graph is None or (destination / "computation_graph_alignment.json").is_file())
                    and (destination / "llm_reasoning.txt").is_file()
                    and (destination / "llm_reasoning.txt").read_text(encoding="utf-8")
                    == result["reasoning"]["output_text"])
        if not reusable:
            exp.atomic_json(destination / "report.json", report)
            exp.atomic_json(destination / "catala_replay.json", by_symbolic.get(row["id"], {}))
            if graph is not None:
                exp.atomic_json(destination / "computation_graph_alignment.json", graph)
            (destination / "llm_reasoning.txt").write_text(result["reasoning"]["output_text"], encoding="utf-8")
        report_path = str((destination / "report.json").relative_to(feedback))
        if diagnostic:
            diagnostics.append({"case_id": row["id"], "target_provision": provision,
                "report": report_path, "execution_error": row.get("code_execution_diagnostic"),
                "reasoning_error": row.get("llm_reasoning_diagnostic"),
                "extraction_error": row.get("llm_execution_tree_extraction_error"),
                "computation_graph_diagnostic": graph if graph and graph.get("status") != "compared" else None})
        if mismatch:
            reports.append({"provision": provision, "case_id": row["id"], "report": report_path,
                            "report_reasons": report["report_reasons"],
                            "linked_provisions": sorted(linked)})
    index = {"reports": reports, "diagnostics": diagnostics,
             "generation_gaps": [{"provision": item["target"]["provision_id"], "status": item["status"],
                                  "attempts": item["attempts"]} for item in results if item["status"] != "accepted"],
             "report_method": "deterministic_raw_evidence_no_llm_summary"}
    exp.atomic_json(feedback / "index.json", index)
    return index
