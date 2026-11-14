"""Scope-mapped, specification-only natural-language test generation."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from rsa_formalizer.bobcat.trace import provision_ids_overlap, scope_statute_anchor
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.utils import usage as usage_tracking
from rsa_formalizer.stages.validation import information_extraction as ie
from . import generate_llm_trace


GENERATION_FORMAT = "scope_mapped_nl_tests_v2"
GROUNDING_FORMAT = "scope_mapped_nl_grounding_v1"
_BLOCK_DETAILS = re.compile(r"<!-- rsa-block-id: ([^;]+);[^>]*provision-id: ([^;]+);")
_FENCE = re.compile(r"^```(?:catala[^\n]*)?$", re.MULTILINE)
_LABELED = re.compile(r"^\[([^\]\n]+)\]", re.MULTILINE)
_SCOPE_LINE = re.compile(r"^\s*scope\s+([A-Za-z_][A-Za-z0-9_]*)\s*:")
_DEFINITION_LINE = re.compile(r"^\s*definition\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_SCOPE_OUTPUT = re.compile(r"^\s*output\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_SCOPE_CALL = re.compile(
    r"output\s+of\s+([A-Za-z_][A-Za-z0-9_]*)\s+with\s+\{.*?"
    r"\}\s*\)\.([A-Za-z_][A-Za-z0-9_]*)",
    re.DOTALL,
)


def _source_scope_model(path: Path) -> dict[str, dict[str, Any]]:
    """Extract definition dependencies and mappings without exposing code to an LLM."""
    model: dict[str, dict[str, Any]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    marker: str | None = None
    index = 0
    while index < len(lines):
        found = _BLOCK_DETAILS.search(lines[index])
        if found:
            marker = found.group(2) if found.group(2) != "none" else None
        if lines[index].startswith("```catala") and not lines[index].startswith(
            "```catala-metadata"
        ):
            code: list[str] = []
            index += 1
            while index < len(lines) and lines[index] != "```":
                code.append(lines[index])
                index += 1
            current_scope: str | None = None
            definition_starts: list[tuple[int, str, str]] = []
            for line_index, line in enumerate(code):
                scope_match = _SCOPE_LINE.match(line)
                if scope_match:
                    current_scope = scope_match.group(1)
                    model.setdefault(current_scope, {"definitions": {}, "outputs": []})
                    continue
                definition_match = _DEFINITION_LINE.match(line)
                if definition_match and current_scope:
                    definition_starts.append(
                        (line_index, current_scope, definition_match.group(1))
                    )
            for position, (start, scope_name, variable) in enumerate(definition_starts):
                end = (
                    definition_starts[position + 1][0]
                    if position + 1 < len(definition_starts)
                    else len(code)
                )
                model[scope_name]["definitions"][variable] = {
                    "body": "\n".join(code[start:end]),
                    "provision": marker,
                }
            # A mapping comment belongs to the immediately following code block.
            marker = None
        index += 1

    in_metadata = False
    declared_scope: str | None = None
    for line in lines:
        if line.startswith("```catala-metadata"):
            in_metadata = True
            continue
        if in_metadata and line == "```":
            in_metadata = False
            declared_scope = None
            continue
        if not in_metadata:
            continue
        declaration = re.match(
            r"^\s*declaration\s+scope\s+([A-Za-z_][A-Za-z0-9_]*)\s*:",
            line,
        )
        if declaration:
            declared_scope = declaration.group(1)
            model.setdefault(declared_scope, {"definitions": {}, "outputs": []})
            continue
        output = _SCOPE_OUTPUT.match(line)
        if output and declared_scope:
            model[declared_scope]["outputs"].append(output.group(1))
    return model


def _output_sensitive_provisions(
    snapshot: Path, plan: dict[str, dict[str, Any]], root_id: str
) -> list[str]:
    """Follow only definitions feeding requested outputs, including scope calls."""
    models: dict[str, dict[str, dict[str, Any]]] = {}
    by_scope: dict[str, list[str]] = {}
    for identifier, record in plan.items():
        source = (
            record.get("source") or record.get("compiler_file") or record.get("file")
        )
        if not source or not (snapshot / source).is_file():
            continue
        models.setdefault(source, _source_scope_model(snapshot / source))
        by_scope.setdefault(record["scope"], []).append(identifier)

    provisions: list[str] = []
    visited: set[tuple[str, str]] = set()

    def visit(identifier: str, requested: list[str] | None = None) -> bool:
        record = plan.get(identifier)
        if not record:
            return False
        source = (
            record.get("source") or record.get("compiler_file") or record.get("file")
        )
        scope_name = record["scope"]
        scope_model = models.get(source, {}).get(scope_name)
        if not scope_model:
            return False
        definitions = scope_model["definitions"]
        roots = requested or (
            [record["output"]]
            if isinstance(record.get("output"), str)
            else scope_model["outputs"]
        )
        pending = [name for name in roots if name in definitions]
        found_call = False
        while pending:
            variable = pending.pop(0)
            key = (identifier, variable)
            if key in visited:
                continue
            visited.add(key)
            definition = definitions[variable]
            provision = definition.get("provision")
            if provision and provision not in provisions:
                provisions.append(provision)
            body = definition["body"]
            words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", body))
            pending.extend(
                name
                for name in definitions
                if name in words and (identifier, name) not in visited
            )
            for called_scope, output in _SCOPE_CALL.findall(body):
                candidates = by_scope.get(called_scope, [])
                if not candidates:
                    continue
                found_call = True
                visit(candidates[0], [output])
        return found_call

    found_explicit_call = visit(root_id)
    if not found_explicit_call:
        # Older/generated Catala may hide the call syntax from this lightweight
        # parser. Retain the safe transitive-scope fallback in that case.
        pending = list(plan.get(root_id, {}).get("dependencies", []))
        while pending:
            identifier = pending.pop(0)
            if visit(identifier):
                pass
            pending.extend(plan.get(identifier, {}).get("dependencies", []))
    return provisions


def _scope_provisions(snapshot: Path, source: str, scope: str) -> list[str]:
    """Return provision IDs whose mapped code fences implement one scope."""
    path = snapshot / source
    if not path.is_file():
        return []
    heading = re.compile(
        r"^\s*(?:declaration\s+)?scope\s+" + re.escape(scope) + r"\s*:"
    )
    marker: str | None = None
    in_code = False
    result: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        found = _BLOCK_DETAILS.search(line)
        if found:
            marker = found.group(2) if found.group(2) != "none" else None
        if line.startswith("```catala"):
            in_code = True
        elif line == "```":
            in_code = False
        elif in_code and marker and heading.match(line) and marker not in result:
            result.append(marker)
    return result


def mapped_provision_ids(
    snapshot: Path, state: dict[str, Any], scope: dict[str, Any]
) -> list[str]:
    """Map a scope and its declared scope dependencies to statutory segments."""
    plan = {
        record["id"]: record
        for record in state.get("recursive_repair_plan", [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    root_id = scope.get("id") or f"{scope['source']}::{scope['scope']}"
    plan.setdefault(root_id, scope)
    output_sensitive = _output_sensitive_provisions(snapshot, plan, root_id)
    if output_sensitive:
        return output_sensitive
    pending = [root_id]
    visited: set[str] = set()
    provisions: list[str] = []
    while pending:
        identifier = pending.pop(0)
        if identifier in visited:
            continue
        visited.add(identifier)
        record = plan.get(identifier)
        if not record:
            continue
        source = (
            record.get("source") or record.get("compiler_file") or record.get("file")
        )
        for provision in _scope_provisions(snapshot, source, record["scope"]):
            if provision not in provisions:
                provisions.append(provision)
        pending.extend(
            dependency
            for dependency in record.get("dependencies", [])
            if dependency not in visited
        )
    if provisions:
        return provisions
    source = scope.get("source") or scope.get("compiler_file") or scope.get("file")
    return [scope_statute_anchor(snapshot, source, scope["scope"])]


def _labeled_passages(run_directory: Path) -> list[tuple[str, str]]:
    manifest = exp.load_json(run_directory / "input/RSA_MANIFEST.json")
    passages: list[tuple[str, str]] = []
    for document in manifest.get("documents", []):
        path = run_directory / "input" / document["path"]
        text = path.read_text(encoding="utf-8")
        pieces = _FENCE.split(text)
        prose = "".join(piece for index, piece in enumerate(pieces) if index % 2 == 0)
        labeled = generate_llm_trace._labeled_statute_prose(prose)
        matches = list(_LABELED.finditer(labeled))
        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start() if index + 1 < len(matches) else len(labeled)
            )
            passages.append((match.group(1), labeled[match.start() : end].strip()))
    return passages


def statute_context(
    run_directory: Path, provision_ids: list[str]
) -> tuple[str, list[str]]:
    """Select authoritative NL passages overlapping the scope mapping."""
    selected: list[str] = []
    selected_ids: list[str] = []
    for identifier, passage in _labeled_passages(run_directory):
        if any(provision_ids_overlap(identifier, mapped) for mapped in provision_ids):
            selected.append(passage)
            selected_ids.append(identifier)
    if not selected:
        raise exp.RunnerError(
            "scope provision mapping selected no authoritative prose: "
            + ", ".join(provision_ids)
        )
    return "\n\n".join(selected), selected_ids


def _reasoning_step_schema(provisions: list[str]) -> dict[str, Any]:
    provision_options: list[dict[str, Any]] = [{"type": "null"}]
    if provisions:
        provision_options.insert(0, {"type": "string", "enum": provisions})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "claim", "provision", "premises"],
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "claim": {"type": "string", "minLength": 1},
            "provision": {"anyOf": provision_options},
            "premises": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0},
            },
        },
    }


def _generation_schema(max_cases: int, provisions: list[str]) -> dict[str, Any]:
    case = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "title",
            "test_purpose",
            "facts",
            "material_facts",
            "question",
            "expected_answer",
            "reasoning_steps",
        ],
        "properties": {
            "id": {"type": "string", "pattern": "^nl-[0-9]+$"},
            "title": {"type": "string", "minLength": 1},
            "test_purpose": {"type": "string", "minLength": 1},
            "facts": {"type": "string", "minLength": 1},
            "material_facts": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "question": {"type": "string", "minLength": 1},
            "expected_answer": {"type": "string", "minLength": 1},
            "reasoning_steps": {
                "type": "array",
                "minItems": 1,
                "items": _reasoning_step_schema(provisions),
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["cases"],
        "properties": {
            "cases": {
                "type": "array",
                "minItems": max_cases,
                "maxItems": max_cases,
                "items": case,
            }
        },
    }


def _generation_prompt(statutes: str, max_cases: int) -> str:
    """This prompt is deliberately sealed from schemas, tests, and Catala code."""
    return f"""Design natural-language legal test cases using only the authoritative
provisions below. Generate exactly {max_cases} concrete and internally consistent cases.

Each case must state ordinary real-world facts, a precise legal question answered by
the supplied provisions, the expected answer, and a minimal step-by-step derivation.
State every fact needed for the expected answer; do not silently assume an unstated
fact. List those legally material facts separately using the same meaning as the case.
When a value or condition is legally evaluated at a particular time or over a
particular period, state that time or period explicitly in the facts.
Prefer primitive observable facts—events, relationships, dates, and component
amounts. Do not use a legally defined aggregate, eligibility result, status, or other
intermediate conclusion as an input fact when the supplied provisions are meant to
derive it. Do not replace facts with an umbrella statement that no exception applies;
state the concrete facts needed to rule out every exception on which the answer relies.
Do not state as an input fact a legal conclusion that these provisions are supposed
to derive. Make the question and expected answer cover all concrete legal
classifications or values directly determined by the supplied provisions for that
fact pattern, rather than selecting one convenient sub-question and leaving the other
mapped determinations unspecified.
The case must determine the ultimate legal result produced after applying the full
supplied provision set. Do not generate a case whose expected answer stops at an
intermediate status, eligibility finding, deduction, component amount, or branch
selection while facts needed for the ultimate result remain unstated. If several
components contribute to that result, state enough primitive facts to determine all
of them, including components that are zero or inapplicable.

Make the cases materially distinct by exercising different operative conditions,
exceptions, thresholds, time periods, or interactions actually present in the text.
Distribute the cases across distinct provisions and legal pathways instead of
concentrating on one familiar rule. Where supported by the supplied text, include a
mix of ordinary applications, conditions just below and just above thresholds,
exceptions, temporal transitions, and interactions among multiple provisions. Each
case's test purpose must identify the particular legal contrast it exercises. Use the
available case budget for discriminating cases rather than superficial paraphrases.
Do not create paired variants unless both are independently useful.

Reasoning steps must be topologically ordered with contiguous zero-based IDs. Cite
only a supplied provision ID, and cite the most specific applicable provision. A fact
step may use null. Every premise must refer only to an earlier step.

Do not mention or assume anything about software, source code, APIs, fields, variable
names, data formats, schemas, implementations, or existing tests.

AUTHORITATIVE PROVISIONS
========================
{statutes}
"""


def _validate_generated(
    value: Any, allowed: set[str], expected_count: int | None = None
) -> str | None:
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        return "generation output has no cases array"
    if expected_count is not None and len(value["cases"]) != expected_count:
        return (
            f"generation returned {len(value['cases'])} cases; "
            f"expected exactly {expected_count}"
        )
    seen: set[str] = set()
    for case in value["cases"]:
        identifier = case.get("id") if isinstance(case, dict) else None
        if not isinstance(identifier, str) or identifier in seen:
            return "generated case IDs are missing or duplicated"
        seen.add(identifier)
        for expected, step in enumerate(case.get("reasoning_steps", [])):
            if step.get("id") != expected:
                return f"{identifier} reasoning step IDs are not contiguous"
            if step.get("provision") is not None and step["provision"] not in allowed:
                return f"{identifier} cites an unavailable provision"
            premises = step.get("premises", [])
            if len(premises) != len(set(premises)) or any(
                not isinstance(item, int) or item < 0 or item >= expected
                for item in premises
            ):
                return f"{identifier} has invalid reasoning premises"
    return None


def _audit_schema(generated: dict[str, Any]) -> dict[str, Any]:
    fixed_facts = [
        fact
        for case in generated.get("cases", [])
        for fact in case.get("material_facts", [])
    ]
    narrative_facts = [
        sentence.strip()
        for case in generated.get("cases", [])
        for sentence in re.split(r"(?<=[.!?])\s+", case.get("facts", ""))
        if sentence.strip()
    ]
    allowed_facts = list(dict.fromkeys([*fixed_facts, *narrative_facts]))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["cases"],
        "properties": {
            "cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "status", "facts"],
                    "properties": {
                        "id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": [
                                "representable",
                                "possible_gap",
                                "invalid_test",
                                "unclear",
                            ],
                        },
                        "facts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "fact",
                                    "status",
                                    "candidate_requirements",
                                    "explanation",
                                ],
                                "properties": {
                                    # Constrain structured output to the fixed
                                    # test text; otherwise models sometimes
                                    # helpfully paraphrase or combine facts.
                                    "fact": {
                                        "type": "string",
                                        "enum": allowed_facts,
                                    },
                                    "status": {
                                        "type": "string",
                                        "enum": [
                                            "represented",
                                            "partial",
                                            "missing",
                                            "underspecified",
                                            "unclear",
                                        ],
                                    },
                                    "candidate_requirements": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "explanation": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
    }


def _audit_prompt(
    generated: dict[str, Any],
    input_schema: dict[str, Any],
    statutes: str,
) -> str:
    fixed = [
        {
            "id": case["id"],
            "full_facts": case["facts"],
            "material_facts": case["material_facts"],
        }
        for case in generated.get("cases", [])
    ]
    return f"""Audit whether each material fact in these already-fixed legal test cases
can be faithfully represented by the selected Catala input schema. Do not edit,
weaken, replace, or regenerate a test.

The full_facts narrative is authoritative context for its material_facts summaries.
If a summary uses an umbrella phrase but full_facts states the underlying details,
audit those details rather than treating the summary alone as underspecified.
Return every material_facts entry exactly once. If full_facts contains an additional
legally material fact omitted from material_facts, also audit it by copying one whole
sentence from full_facts verbatim. Never paraphrase, combine, or invent a fact.

Use represented only for the same real-world fact with the required subject,
relationship direction, time period, units, and semantics. Use underspecified when
the fixed NL fact itself omits a time, subject, value, or other detail required to
answer the legal question; this is a defective test, not an input-schema gap. Use
partial only when the NL fact is complete but the Catala input loses material
semantics, missing when a complete fact has no input, and unclear when documentation
is insufficient. A derived legal conclusion is not a substitute for underlying facts.
If the test supplies only a derived conclusion where underlying facts are required,
classify it as underspecified rather than as a schema gap.
Do not call a fact partial merely because the input category omits a distinction that
has no legal effect on this test (for example, two subtypes covered by the same listed
relationship category).
Use the authoritative provisions below to decide which distinctions have legal effect.
If an input can represent every legally relevant part of a fact, mark it represented
even when it omits narrative detail that no supplied provision tests. Conversely, do
not infer that a distinction is irrelevant merely because the input schema omits it.
Candidate requirement names must occur verbatim in the supplied schema. Mark a case
possible_gap if any material fact is partial or missing; otherwise mark it invalid_test
if any fact is underspecified; otherwise mark it unclear if any fact is unclear.

FIXED MATERIAL FACTS
====================
{json.dumps(fixed, ensure_ascii=False, indent=2)}

CATALA INPUT JSON SCHEMA
========================
{json.dumps(input_schema, ensure_ascii=False, indent=2, sort_keys=True)}

AUTHORITATIVE PROVISIONS
========================
{statutes}
"""


def _validate_audit(generated: dict[str, Any], audit: Any) -> str | None:
    if not isinstance(audit, dict) or not isinstance(audit.get("cases"), list):
        return "representability audit has no cases array"
    expected = {
        case["id"]: case["material_facts"] for case in generated.get("cases", [])
    }
    allowed = {
        case["id"]: set(case["material_facts"])
        | {
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", case.get("facts", ""))
            if sentence.strip()
        }
        for case in generated.get("cases", [])
    }
    observed: dict[str, list[str]] = {}
    for case in audit["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            return "representability audit contains an invalid case"
        if case["id"] in observed:
            return f"representability audit duplicates {case['id']}"
        observed[case["id"]] = [
            fact.get("fact") for fact in case.get("facts", []) if isinstance(fact, dict)
        ]
    if set(observed) != set(expected):
        return "representability audit case IDs do not match generated cases"
    for identifier, facts in expected.items():
        returned = observed[identifier]
        if len(returned) != len(set(returned)):
            return f"representability audit duplicates facts for {identifier}"
        if any(fact not in allowed[identifier] for fact in returned):
            return f"representability audit paraphrases facts for {identifier}"
        if any(fact not in returned for fact in facts):
            return f"representability audit omits material facts for {identifier}"
    return None


def _normalize_audit(generated: dict[str, Any], audit: Any) -> Any:
    """Drop auditor-invented facts and recompute the case classification."""
    if not isinstance(audit, dict) or not isinstance(audit.get("cases"), list):
        return audit
    designs = {case["id"]: case for case in generated.get("cases", [])}
    for case in audit["cases"]:
        if not isinstance(case, dict) or case.get("id") not in designs:
            continue
        design = designs[case["id"]]
        allowed = set(design.get("material_facts", [])) | {
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", design.get("facts", ""))
            if sentence.strip()
        }
        facts = [
            fact
            for fact in case.get("facts", [])
            if isinstance(fact, dict) and fact.get("fact") in allowed
        ]
        case["facts"] = facts
        statuses = {fact.get("status") for fact in facts}
        case["status"] = (
            "possible_gap"
            if statuses & {"partial", "missing"}
            else "invalid_test"
            if "underspecified" in statuses
            else "unclear"
            if "unclear" in statuses
            else "representable"
        )
    return audit


def _usage_context(
    config: dict[str, Any], scope: dict[str, Any], phase: str
) -> dict[str, Any]:
    settings = (
        config["information_extraction"]
        if phase in {"representability", "grounding"}
        else config["reasoning_trace"]
    )
    return {
        "run_id": config["run_id"],
        "stage": f"llm-nl-test-{phase}",
        "framework": "api",
        "provider": settings["provider"],
        "model": settings["model"],
        "scope": f"{scope.get('source')}::{scope.get('scope')}",
    }


def _call_ie(
    config: dict[str, Any], prompt: str, schema: dict[str, Any], name: str
) -> dict[str, Any]:
    return ie._call_openai(config["information_extraction"], prompt, schema, name=name)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _missing_fact_paths(value: Any, path: str = "$") -> list[str]:
    """Locate IE placeholder strings that must never reach Catala execution."""
    if isinstance(value, str) and re.match(
        r"^\s*MISSING(?:_|\s)+(?:REQUIRED(?:_|\s)+)?FACT\b", value, re.IGNORECASE
    ):
        return [path]
    if isinstance(value, dict):
        return [
            found
            for key, nested in value.items()
            for found in _missing_fact_paths(nested, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [
            found
            for index, nested in enumerate(value)
            for found in _missing_fact_paths(nested, f"{path}[{index}]")
        ]
    return []


def _requirement_has_value(inputs: Any, requirement: str) -> bool:
    """Return whether an audited input path survived concrete NL extraction.

    Representability is only a claim about what the interface *could* encode.  This
    second check catches a materially different failure mode: the extractor omitted
    a stated fact even though the auditor identified its destination.  ``[]`` means
    that at least one list member must contain a non-null value at the remaining path.
    """
    if not isinstance(requirement, str) or not requirement:
        return False
    nodes = [inputs]
    for component in requirement.split("."):
        repeated = component.endswith("[]")
        key = component[:-2] if repeated else component
        nested: list[Any] = []
        for node in nodes:
            if not isinstance(node, dict) or key not in node:
                continue
            value = node[key]
            if repeated:
                if isinstance(value, list):
                    nested.extend(value)
            else:
                nested.append(value)
        nodes = nested
        if not nodes:
            return False
    return any(value is not None for value in nodes)


def _grounding_fidelity(audit: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """Check that every represented material fact was actually extracted."""
    omissions: list[dict[str, Any]] = []
    for fact in audit.get("facts", []):
        if not isinstance(fact, dict) or fact.get("status") != "represented":
            continue
        missing = [
            requirement
            for requirement in fact.get("candidate_requirements", [])
            if not _requirement_has_value(inputs, requirement)
        ]
        if missing:
            omissions.append({"fact": fact.get("fact"), "missing_paths": missing})
    return {
        "status": "faithful" if not omissions else "omitted_material_facts",
        "omissions": omissions,
    }


def _design_provisions(case: dict[str, Any]) -> set[str]:
    return {
        step["provision"]
        for step in case.get("generated_reasoning_tree", {}).get("steps", [])
        if isinstance(step, dict) and isinstance(step.get("provision"), str)
    }


def _select_diverse_executable(
    candidates: list[dict[str, Any]], max_cases: int
) -> list[dict[str, Any]]:
    """Greedily retain cases that add the most new provision-level behavior."""
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    remaining = list(enumerate(candidates))
    while remaining and len(selected) < max_cases:
        best_position = max(
            range(len(remaining)),
            key=lambda position: (
                len(_design_provisions(remaining[position][1]) - covered),
                len(_design_provisions(remaining[position][1])),
                -remaining[position][0],
            ),
        )
        _, case = remaining.pop(best_position)
        selected.append(case)
        covered.update(_design_provisions(case))
    return selected


def augment_tests(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    scope: dict[str, Any],
    bobcat_cases: list[dict[str, Any]],
    max_cases: int,
) -> list[dict[str, Any]]:
    """Generate NL tests, audit representation, ground inputs, and append executable cases."""
    if max_cases <= 0 or not isinstance(scope.get("input_schema"), dict):
        return bobcat_cases
    stage_root = exp.stage_directory(run_directory, state)
    snapshot = stage_root / "snapshot"
    root = stage_root / "tests_llm_generated"
    root.mkdir(parents=True, exist_ok=True)

    mapped = mapped_provision_ids(snapshot, state, scope)
    statutes, selected_ids = statute_context(run_directory, mapped)
    # Generate a larger candidate pool because representability auditing and
    # information extraction can legitimately reject specification-only cases.
    # The configured value remains the final executable-test budget.
    candidate_budget = max_cases if max_cases <= 1 else max_cases * 3
    designer_prompt = _generation_prompt(statutes, candidate_budget)
    (root / "designer.prompt.txt").write_text(designer_prompt, encoding="utf-8")
    designer_hash = hashlib.sha256(designer_prompt.encode()).hexdigest()
    generation_file = root / "generation.json"
    generated: dict[str, Any] | None = None
    generation_record: dict[str, Any] = {}
    if generation_file.is_file():
        cached = exp.load_json(generation_file)
        if (
            cached.get("format") == GENERATION_FORMAT
            and cached.get("prompt_sha256") == designer_hash
            and not cached.get("error")
            and isinstance(cached.get("generated"), dict)
        ):
            generated = cached["generated"]
            generation_record = cached
    if generated is None:
        started = time.monotonic()
        try:
            sampled = usage_tracking.api_call(
                run_directory,
                _usage_context(config, scope, "generation"),
                hashlib.sha256(
                    (designer_hash + state.get("_reasoning_cache_nonce", "")).encode()
                ).hexdigest(),
                lambda: generate_llm_trace._sample(
                    config,
                    designer_prompt,
                    _generation_schema(candidate_budget, selected_ids),
                ),
            )
            generated = json.loads(sampled.get("output_text") or "")
            error = _validate_generated(
                generated, set(selected_ids), expected_count=candidate_budget
            )
            if error:
                generated = None
        except Exception as exception:
            sampled = {"request_id": None, "usage": None, "raw_response": None}
            error = f"{type(exception).__name__}: {exception}"
        generation_record = {
            "format": GENERATION_FORMAT,
            "prompt_sha256": designer_hash,
            "mapped_provision_ids": mapped,
            "selected_provision_ids": selected_ids,
            "elapsed_seconds": time.monotonic() - started,
            "request_id": sampled.get("request_id"),
            "usage": sampled.get("usage"),
            "error": error,
            "generated": generated,
            "raw_response": sampled.get("raw_response"),
        }
        exp.atomic_json(generation_file, generation_record, indent=2)
    if generated is None:
        exp.atomic_json(
            root / "summary.json",
            {
                "generated": 0,
                "executable": 0,
                "schema_gaps": 0,
                "error": generation_record.get("error"),
            },
            indent=2,
        )
        return bobcat_cases

    audit_prompt = _audit_prompt(generated, scope["input_schema"], statutes)
    (root / "representability.prompt.txt").write_text(audit_prompt, encoding="utf-8")
    audit_hash = hashlib.sha256(audit_prompt.encode()).hexdigest()
    audit_file = root / "representability.json"
    audit: dict[str, Any] | None = None
    if audit_file.is_file():
        cached = exp.load_json(audit_file)
        if cached.get("prompt_sha256") == audit_hash and not cached.get("error"):
            audit = cached.get("audit")
            if _validate_audit(generated, audit):
                audit = None
    if audit is None:
        try:
            sampled_audit = usage_tracking.api_call(
                run_directory,
                _usage_context(config, scope, "representability"),
                audit_hash,
                lambda: _call_ie(
                    config,
                    audit_prompt,
                    _audit_schema(generated),
                    "nl_test_representability",
                ),
            )
            audit = _normalize_audit(generated, sampled_audit.get("parsed"))
            audit_error = sampled_audit.get("parse_error") or _validate_audit(
                generated, audit
            )
            if audit_error:
                audit = None
        except Exception as exception:
            sampled_audit = {
                "request_id": None,
                "usage": None,
                "raw_response": None,
            }
            audit_error = f"{type(exception).__name__}: {exception}"
        exp.atomic_json(
            audit_file,
            {
                "format": GROUNDING_FORMAT,
                "prompt_sha256": audit_hash,
                "error": audit_error,
                "audit": audit,
                "request_id": sampled_audit.get("request_id"),
                "usage": sampled_audit.get("usage"),
                "raw_response": sampled_audit.get("raw_response"),
            },
            indent=2,
        )
    audits = {
        item.get("id"): item
        for item in (audit or {}).get("cases", [])
        if isinstance(item, dict)
    }

    source = scope.get("source") or scope.get("compiler_file") or scope.get("file")
    extraction_root = root / "extractions"
    extraction_root.mkdir(exist_ok=True)
    existing = {_canonical(case.get("inputs")) for case in bobcat_cases}
    executable: list[dict[str, Any]] = []
    grounding_records: list[dict[str, Any]] = []
    for design in generated.get("cases", []):
        design_id = design["id"]
        case_audit = audits.get(design_id)
        record: dict[str, Any] = {
            "id": design_id,
            "design": design,
            "representability": case_audit,
            "status": "schema_gap",
            "detail": None,
        }
        if case_audit is None:
            record.update(status="error", detail="representability audit is missing")
            grounding_records.append(record)
            continue
        if case_audit.get("status") != "representable":
            record["status"] = {
                "possible_gap": "schema_gap",
                "invalid_test": "invalid_test",
                "unclear": "unclear",
            }.get(case_audit.get("status"), "error")
            record["detail"] = (
                "one or more material facts did not pass representability audit"
            )
            grounding_records.append(record)
            continue
        natural = {"facts": design["facts"], "question": design["question"]}
        extraction_prompt = ie._input_prompt(
            natural,
            {**scope, "file": source, "compiler_file": source},
            snapshot,
        )
        prompt_file = extraction_root / f"{design_id}.prompt.txt"
        prompt_file.write_text(extraction_prompt, encoding="utf-8")
        extraction_hash = hashlib.sha256(extraction_prompt.encode()).hexdigest()
        destination = extraction_root / f"{design_id}.json"
        extracted: dict[str, Any] | None = None
        if destination.is_file():
            cached = exp.load_json(destination)
            if cached.get("prompt_sha256") == extraction_hash and not cached.get(
                "error"
            ):
                extracted = cached.get("inputs")
        if extracted is None:
            try:
                sampled_input = usage_tracking.api_call(
                    run_directory,
                    {
                        **_usage_context(config, scope, "grounding"),
                        "case_id": design_id,
                    },
                    extraction_hash,
                    lambda: _call_ie(
                        config,
                        extraction_prompt,
                        scope["input_schema"],
                        "nl_test_scope_input",
                    ),
                )
                if sampled_input.get("parse_error"):
                    raise ValueError(sampled_input["parse_error"])
                extracted = ie._strip_optional_nulls(
                    sampled_input["parsed"], scope["input_schema"]
                )
                Draft202012Validator(
                    ie._validation_schema(scope["input_schema"])
                ).validate(extracted)
                extraction_error = None
            except Exception as exception:
                sampled_input = {
                    "request_id": None,
                    "usage": None,
                    "raw_response": None,
                }
                extraction_error = f"{type(exception).__name__}: {exception}"
                extracted = None
            exp.atomic_json(
                destination,
                {
                    "prompt_sha256": extraction_hash,
                    "inputs": extracted,
                    "error": extraction_error,
                    "request_id": sampled_input.get("request_id"),
                    "usage": sampled_input.get("usage"),
                    "raw_response": sampled_input.get("raw_response"),
                },
                indent=2,
            )
        if extracted is None:
            record.update(status="error", detail="information extraction failed")
            grounding_records.append(record)
            continue
        missing_paths = _missing_fact_paths(extracted)
        if missing_paths:
            record.update(
                status="schema_gap",
                detail=(
                    "information extraction reported missing required facts at "
                    + ", ".join(missing_paths)
                ),
                inputs=extracted,
            )
            grounding_records.append(record)
            continue
        fidelity = _grounding_fidelity(case_audit, extracted)
        record["grounding_fidelity"] = fidelity
        if fidelity["status"] != "faithful":
            omitted = sorted(
                {
                    path
                    for omission in fidelity["omissions"]
                    for path in omission["missing_paths"]
                }
            )
            record.update(
                status="extraction_gap",
                detail=(
                    "information extraction omitted represented material facts at "
                    + ", ".join(omitted)
                ),
                inputs=extracted,
            )
            grounding_records.append(record)
            continue
        key = _canonical(extracted)
        if key in existing:
            record.update(status="duplicate", inputs=extracted)
            grounding_records.append(record)
            continue
        existing.add(key)
        digest = hashlib.sha256(key.encode()).hexdigest()[:12]
        case = {
            "id": f"{Path(source).stem}_{scope['scope']}:nl-{digest}",
            "target": scope["scope"],
            "source": source,
            "inputs": extracted,
            "branches": [],
            "statute_ids": selected_ids,
            "exact": False,
            "kind": "llm_generated_nl",
            "case_origin": "llm_generated_nl",
            "test_strategy": "specification_only",
            "test_rationale": design["test_purpose"],
            "natural_language_facts": design["facts"],
            "natural_language_question": design["question"],
            "generated_expected_answer": design["expected_answer"],
            "generated_reasoning_tree": {"steps": design["reasoning_steps"]},
            "generated_design_id": design_id,
            "grounding_fidelity": fidelity,
            "statute_context": statutes,
            "mapped_provision_ids": mapped,
        }
        if scope.get("output"):
            case["output_name"] = scope["output"]
        executable.append(case)
        record.update(status="executable", inputs=extracted, case_id=case["id"])
        grounding_records.append(record)

    executable_candidates = executable
    executable = _select_diverse_executable(executable_candidates, max_cases)
    selected_ids_set = {case["generated_design_id"] for case in executable}
    for record in grounding_records:
        if (
            record.get("status") == "executable"
            and record.get("id") not in selected_ids_set
        ):
            record.update(
                status="diversity_reserve",
                detail="valid candidate not selected within the executable-test budget",
            )
    exp.atomic_json(root / "grounding.json", {"cases": grounding_records}, indent=2)
    summary = {
        "candidate_budget": candidate_budget,
        "generated": len(generated.get("cases", [])),
        "executable": len(executable),
        "executable_candidates": len(executable_candidates),
        "diversity_reserve": sum(
            row["status"] == "diversity_reserve" for row in grounding_records
        ),
        "selected_provision_coverage": sorted(
            set().union(*(_design_provisions(case) for case in executable))
            if executable
            else set()
        ),
        "schema_gaps": sum(row["status"] == "schema_gap" for row in grounding_records),
        "extraction_gaps": sum(
            row["status"] == "extraction_gap" for row in grounding_records
        ),
        "invalid_tests": sum(
            row["status"] == "invalid_test" for row in grounding_records
        ),
        "unclear": sum(row["status"] == "unclear" for row in grounding_records),
        "duplicates": sum(row["status"] == "duplicate" for row in grounding_records),
        "errors": sum(row["status"] == "error" for row in grounding_records),
        "mapped_provision_ids": mapped,
        "selected_provision_ids": selected_ids,
    }
    exp.atomic_json(root / "cases.json", {"cases": executable}, indent=2)
    exp.atomic_json(root / "summary.json", summary, indent=2)
    return bobcat_cases + executable
