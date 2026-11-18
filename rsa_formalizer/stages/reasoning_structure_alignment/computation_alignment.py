"""Extract frozen computation oracles after code-blind reasoning has completed."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from rsa_formalizer.bobcat import computation_graph as graphs
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.utils import usage as usage_tracking
from rsa_formalizer.stages.utils.prompt_cache import CacheablePrompt
from . import generate_llm_trace as reasoning


def target_application(record, target, solution):
    """Check whether an extracted target step supports an explicit final answer."""
    if record.get("status") != "complete":
        return {"status": "uncertain", "reason": "graph_extraction_unavailable"}
    nodes = record.get("graph", {}).get("nodes", [])
    target_local = target.rsplit("/", 1)[-1].casefold()
    target_ids = {node["id"] for node in nodes
                  if isinstance(node.get("provision"), str)
                  and node["provision"].rsplit("/", 1)[-1].casefold() == target_local}
    if not target_ids:
        return {"status": "not_applied", "reason": "target_absent_from_computation_graph"}
    answer = reasoning._ANSWER_BLOCK.search(solution or "")
    if answer is None:
        return {"status": "uncertain", "reason": "final_answer_block_unavailable"}
    answer_values, answer_error = reasoning.parse_final_answer(solution)

    def same_value(actual, expected):
        if isinstance(expected, bool):
            return str(actual).casefold() == str(expected).casefold()
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                return Decimal(str(actual)) == Decimal(str(expected))
            except InvalidOperation:
                return False
        return str(actual) == str(expected)

    final_ids = {node["id"] for node in nodes
                 if isinstance(node.get("evidence"), str)
                 and len(node["evidence"].strip()) >= 8
                 and node["evidence"].strip() in answer.group(1)}
    if not answer_error and isinstance(answer_values, dict):
        final_ids.update(node["id"] for node in nodes
                         if isinstance(node.get("quantity"), str)
                         and any(node["quantity"].rsplit(".", 1)[-1] == key
                                 and same_value(node.get("value"), value)
                                 for key, value in answer_values.items()))
    if not final_ids:
        return {"status": "uncertain", "reason": "final_answer_not_identified_in_graph"}
    by_id = {node["id"]: node for node in nodes}
    seen = set(final_ids)
    stack = list(final_ids)
    while stack:
        for premise in by_id[stack.pop()].get("premises", []):
            if premise in by_id and premise not in seen:
                seen.add(premise)
                stack.append(premise)
    supporting = sorted(target_ids & seen)
    return ({"status": "applied", "target_node_ids": supporting, "final_node_ids": sorted(final_ids)}
            if supporting else
            {"status": "not_applied", "reason": "target_not_connected_to_final_answer",
             "target_node_ids": sorted(target_ids), "final_node_ids": sorted(final_ids)})


def enabled(config):
    return config.get("repair", {}).get("computation_graph_alignment", {}).get("enabled", False)


def extraction_prompt(catalog, context, solution, provisions):
    quantity_options = [{"type": "string", "enum": [row["quantity"] for row in catalog]}] if catalog else []
    provision_options = [{"type": "string", "enum": sorted(provisions)}] if provisions else []
    schema = {"type": "object", "additionalProperties": False, "required": ["nodes"], "properties": {
        "nodes": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "quantity", "label", "value", "provision", "premises", "evidence"],
            "properties": {
                "id": {"type": "integer"}, "quantity": {"anyOf": quantity_options + [{"type": "null"}]},
                "label": {"type": "string"}, "value": {"type": "string"},
                "provision": {"anyOf": provision_options + [{"type": "null"}]},
                "premises": {"type": "array", "items": {"type": "integer"}},
                "evidence": {"type": "string"}}}}}}
    prefix = (
        "Extract explicit facts and computations from the solution, without solving, completing, or correcting it. "
        "The catalog supplies quantity labels, type names, aliases and source provision identifiers, but no computed "
        "program values or implementation expressions. Match a quantity only when its meaning clearly matches an "
        "explicit conclusion. Otherwise use null and retain the computation under its own label. The case-specific "
        "contexts contain only public input records. Do not match statements involving different "
        "records or reversed roles; abstain if the context is ambiguous. Unobserved quantities have no confirmed "
        "runtime counterpart. Do not infer missing computations as zero, infer their values from a final answer, "
        "or invent legal applications. A final answer explicitly supplies its output values.\n\n"
        "Use one node per explicit final conclusion about a quantity in a concrete context. Values are unformatted "
        "numeric strings, true/false, or explicit string values. Node IDs must be unique and premises must reference "
        "earlier nodes actually used in the solution. Evidence must be a verbatim supporting substring from the "
        "solution. Cite a provision only when the solution attributes that step to it, otherwise null; never adopt "
        "a citation merely because it appears in the catalog. Preserve contradictions instead of resolving them.\n\n"
        "SOURCE-ONLY QUANTITY CATALOG\n" + json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    context_label = ("PUBLIC INPUT JSON (NO PROGRAM EXECUTION OBSERVED)"
                     if "public_inputs" in context else
                     "PUBLIC INPUT CONTEXTS AND OBSERVED QUANTITIES")
    suffix = (context_label + "\n" + json.dumps(context, ensure_ascii=False, sort_keys=True)
              + "\n\nORIGINAL SOLUTION\n" + solution)
    return CacheablePrompt(prefix, suffix, "provision-computation-extraction"), schema


def extract_before_replay(run, config, snapshot, case, response):
    """Extract one source-aware graph using only the public case and reasoning."""
    source = graphs.source_catalog(snapshot)
    snapshot_hash = exp.tree_hash(snapshot)
    settings = config["repair"]["computation_graph_alignment"]
    statutes = reasoning._statutes(run, config)
    identifiers = reasoning._allowed_provision_ids(statutes)
    identifiers = set(identifiers) | {value.rsplit("/", 1)[-1] for value in identifiers}
    case_id = case["id"]
    folder = snapshot.parent / "computation_graph_results" / case_id
    destination = folder / "result.json"
    solution = response.get("output_text") or ""
    fingerprint = hashlib.sha256(json.dumps([
        graphs.FORMAT, "pre_replay_public_inputs_v1", snapshot_hash, case_id,
        case.get("inputs"), solution, config["reasoning_trace"], settings,
        source["catalog"]], sort_keys=True).encode()).hexdigest()
    if destination.is_file():
        cached = exp.load_json(destination)
        if cached.get("fingerprint") != fingerprint:
            raise exp.RunnerError(f"stale computation graph at {destination}")
        return cached
    context = {"public_inputs": case.get("inputs"),
               "observed_quantity_contexts": {}, "ambiguous_quantities": []}
    prompt, schema = extraction_prompt(source["catalog"], context, solution, identifiers)
    record = {"format": graphs.FORMAT, "fingerprint": fingerprint,
              "extraction_context": "public_inputs_before_replay",
              "status": "extraction_error", "catalog": source["catalog"],
              "source_sha256": snapshot_hash, "attempts": []}
    for index in range(settings.get("max_extraction_attempts", 2)):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"attempt-{index}.prompt.txt").write_text(prompt, encoding="utf-8")
        key = hashlib.sha256((fingerprint + str(index) + str(prompt)).encode()).hexdigest()
        try:
            sampled = usage_tracking.api_call(run, {
                "run_id": config["run_id"], "case_id": case_id,
                "stage": "provision-computation-extraction", "framework": "api",
                "provider": config["reasoning_trace"]["provider"],
                "model": config["reasoning_trace"]["model"],
            }, key, lambda: reasoning._sample(config, prompt, schema))
            exp.atomic_json(folder / f"attempt-{index}.response.json", sampled)
            graph = json.loads(sampled.get("output_text") or "")
            from jsonschema import Draft202012Validator
            Draft202012Validator(schema).validate(graph)
            graph = graphs.validate_graph(graph, source["catalog"], solution)
            record.update(status="complete", graph=graph)
            record.pop("error", None)
            record["attempts"].append({"attempt": index,
                                       "request_id": sampled.get("request_id"),
                                       "status": "accepted"})
            break
        except Exception as error:
            detail = f"{type(error).__name__}: {error}"
            record["attempts"].append({"attempt": index, "status": "rejected", "error": detail})
            record["error"] = detail
            prompt = CacheablePrompt(prompt.prefix,
                prompt.suffix + "\n\nEXTRACTION VALIDATION FAILURE\n" + detail
                + "\nRegenerate the extraction. Copy exact source evidence and omit unsupported nodes. "
                  "Do not solve, correct, or add computations to the original solution.", prompt.group)
    exp.atomic_json(destination, record)
    print(f"Computation graph {case_id}: {record['status']}", flush=True)
    return record


