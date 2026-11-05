"""Extract and evaluate natural-language cases against candidate interfaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.utils import usage as usage_tracking
from rtdf_formalizer.bobcat.compiled_json import (
    build_bridges,
    compiled_path,
    json_equivalent,
    project_output_json,
    schema_at_path,
)


EXTRACTION_SCHEMA_VERSION = 3
COMPARISONS = (
    "reference_value",
    "direct_boolean",
    "equals_claim",
    "canonical_equals_claim",
    "rounded_equals_claim",
)


def _case_id(relative: str, line_number: int, row: dict[str, Any]) -> str:
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:12]
    return f"original:{relative}:{line_number}:{digest}"


def _rows(directory: Path) -> Iterable[tuple[str, int, dict[str, Any]]]:
    for path in sorted(directory.glob("*.json")):
        yield path.name, 1, exp.load_json(path)
    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    yield path.name, line_number, json.loads(line)


def _sara_question_label(question: str) -> tuple[str, bool | None]:
    # Return proposition text and its explicit SARA label, when present.
    match = re.search(r"\s+(Entailment|Contradiction)\s*$", question)
    if match is None:
        return question, None
    return question[: match.start()].rstrip(), match.group(1) == "Entailment"


def natural_case(dataset: str, row: dict[str, Any]) -> dict[str, Any]:
    # Normalize one case read directly from a ``tests_nl`` directory.
    canonical = dataset.casefold().replace("-", "_")
    try:
        text = str(row["text"])
        question = str(row["question"])
        label = str(row["label"])
    except KeyError as error:
        raise exp.RunnerError(
            f"natural-language test is missing {error.args[0]!r}"
        ) from error
    if canonical == "sara":
        # Numeric SARA questions state the claimed amount in the source case.
        return {
            "facts": text,
            "question": f"{question} ${label}",
            "reference_verdict": True,
        }
    if canonical == "airline":
        # RuleArena's human-authored cases omit neutral attributes by convention.
        neutral = (
            "The passenger has no airline loyalty status at ticketing or check-in, "
            "is not an eligible airline cardmember, is not travelling as military "
            "personnel, did not buy a Flagship fare product, and has no accompanying "
            "children."
        )
        return {"facts": f"{text} {neutral}", "question": question}
    raise exp.RunnerError(
        f"natural-language original-test extraction is not implemented for {dataset!r}"
    )


def _call_openai(
    settings: dict[str, Any],
    prompt: str,
    schema: dict[str, Any],
    *,
    name: str,
) -> dict[str, Any]:
    from openai import OpenAI

    provider = settings.get("provider", "openai").lower()
    if provider != "openai":
        raise exp.RunnerError(f"unsupported extraction provider: {provider!r}")
    key_name = settings.get("api_key_env", "OPENAI_API_KEY")
    key = os.environ.get(key_name)
    if not key:
        raise exp.RunnerError(
            f"extraction API key environment variable is missing: {key_name}"
        )
    client = OpenAI(api_key=key, base_url=settings.get("base_url"))
    response = client.responses.create(
        model=settings["model"],
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": _openai_schema(schema),
            }
        },
    )
    raw = response.model_dump(mode="json")
    # Preserve the response/usage even when structured output is malformed.
    try:
        parsed, parse_error = json.loads(response.output_text), None
    except (ValueError, TypeError) as error:
        parsed, parse_error = None, str(error)
    return {
        "parsed": parsed,
        "parse_error": parse_error,
        "raw_response": raw,
        "request_id": raw.get("id"),
        "usage": raw.get("usage") or {},
    }


def _validation_schema(schema: dict[str, Any]) -> dict[str, Any]:
    # Normalize Catala's draft-04 schema without changing its optional fields.
    value = copy.deepcopy(schema)
    reference = value.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/definitions/"):
        name = reference.removeprefix("#/definitions/")
        definition = value.get("definitions", {}).get(name)
        if isinstance(definition, dict):
            definitions = value.get("definitions")
            value = copy.deepcopy(definition)
            if definitions:
                value["definitions"] = definitions

    def normalize(node: Any) -> None:
        if isinstance(node, dict):
            if "oneOf" in node:
                node["anyOf"] = node.pop("oneOf")
            node.pop("$schema", None)
            for nested in node.values():
                normalize(nested)
        elif isinstance(node, list):
            for nested in node:
                normalize(nested)

    normalize(value)
    return value


def _allows_null(schema: dict[str, Any]) -> bool:
    value_type = schema.get("type")
    if value_type == "null" or (isinstance(value_type, list) and "null" in value_type):
        return True
    return any(
        isinstance(branch, dict) and _allows_null(branch)
        for keyword in ("anyOf", "oneOf")
        for branch in schema.get(keyword, [])
    )


def _strict_extraction_schema(schema: dict[str, Any]) -> dict[str, Any]:
    # Adapt a Catala schema to OpenAI's strict Structured Outputs subset.
    value = _validation_schema(schema)

    def strictify(node: Any) -> None:
        if isinstance(node, list):
            for nested in node:
                strictify(nested)
            return
        if not isinstance(node, dict):
            return

        properties = node.get("properties")
        if isinstance(properties, dict):
            originally_required = set(node.get("required", []))
            for name, property_schema in list(properties.items()):
                strictify(property_schema)
                if (
                    name not in originally_required
                    and isinstance(property_schema, dict)
                    and not _allows_null(property_schema)
                ):
                    properties[name] = {"anyOf": [property_schema, {"type": "null"}]}
            node["required"] = list(properties)
            node["additionalProperties"] = False

        for key, nested in node.items():
            if key != "properties":
                strictify(nested)

    strictify(value)
    return value


def _strip_optional_nulls(value: Any, schema: dict[str, Any]) -> Any:
    # Turn OpenAI's null sentinels back into omitted defaulted Catala inputs.
    normalized = _validation_schema(schema)
    definitions = normalized.get("definitions", {})

    def resolve(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            target = definitions.get(reference.removeprefix("#/definitions/"))
            if isinstance(target, dict):
                return target
        return node

    def clean(item: Any, node: Any) -> Any:
        node = resolve(node)
        if not isinstance(node, dict):
            return item
        if isinstance(item, dict):
            properties = node.get("properties", {})
            required = set(node.get("required", []))
            return {
                key: clean(nested, properties.get(key, {}))
                for key, nested in item.items()
                if not (nested is None and key in properties and key not in required)
            }
        if isinstance(item, list):
            element_schema = node.get("items", {})
            return [clean(element, element_schema) for element in item]
        return item

    return clean(value, normalized)


def _openai_schema(schema: dict[str, Any]) -> dict[str, Any]:
    # Backward-compatible name for the strict extraction schema adapter.
    return _strict_extraction_schema(schema)


def _root_properties(schema: dict[str, Any]) -> dict[str, Any]:
    node = schema
    reference = node.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/definitions/"):
        node = schema.get("definitions", {}).get(
            reference.removeprefix("#/definitions/"), {}
        )
    properties = node.get("properties", {}) if isinstance(node, dict) else {}
    return properties if isinstance(properties, dict) else {}


def _plan_schema(
    scope_ids: list[str], requirement_ids: list[str] | None = None
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "supported": {"type": "boolean"},
        "reason": {"type": "string"},
        "comparison": {"type": "string", "enum": list(COMPARISONS)},
        "claim": {"type": "string"},
    }
    required = ["supported", "reason", "comparison", "claim"]
    if requirement_ids is None:
        properties.update(
            {
                "scope_id": {"type": "string", "enum": scope_ids},
                "output_path": {"type": "array", "items": {"type": "string"}},
            }
        )
        required.extend(("scope_id", "output_path"))
    else:
        properties["requirement_id"] = {
            "type": "string",
            "enum": requirement_ids,
        }
        required.append("requirement_id")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _scope_catalog(scopes: list[dict[str, Any]]) -> str:
    records = []
    for scope in scopes:
        records.append(
            {
                "scope_id": f"{scope['file']}::{scope['scope']}",
                "input_schema": scope["input_schema"],
                "output_schema": scope["output_schema"],
            }
        )
    return json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True)


def _plan_prompt(
    dataset: str,
    natural: dict[str, str],
    scopes: list[dict[str, Any]],
    requirement_outputs: dict[str, Any] | None = None,
) -> str:
    mapped = requirement_outputs is not None
    expected_rule = (
        "The benchmark observes only the itinerary's total cost. Use comparison "
        "`reference_value` and an empty claim."
        if dataset.casefold().replace("-", "_") == "airline"
        else "The benchmark records whether the proposition in the question is true. "
        "Use `direct_boolean` if the selected output directly states that proposition. "
        "Use `equals_claim`, `canonical_equals_claim`, or `rounded_equals_claim` if "
        "the output is a value that must be compared with the value stated in the "
        "question; put only that stated value in claim."
    )
    selection = (
        "Select the one declared requirement that answers this human-authored case. "
        "The scope and top-level output variable are fixed by that requirement; "
        "return only its requirement_id."
        if mapped
        else "Select the one candidate Catala scope that answers this human-authored case."
    )
    output_instruction = (
        "Do not invent a different scope or output variable."
        if mapped
        else "output_path is a sequence of JSON object keys from the scope output root "
        "to the observed value."
    )
    if mapped:
        mapped_scope_ids = {
            f"{entry['file']}::{entry['scope']}"
            for entry in requirement_outputs["requirements"]
        }
        mapped_scopes = [
            scope
            for scope in scopes
            if f"{scope['file']}::{scope['scope']}" in mapped_scope_ids
        ]
        catalog = json.dumps(
            {
                "requirements": requirement_outputs["requirements"],
                "scopes": [
                    {
                        "scope_id": f"{scope['file']}::{scope['scope']}",
                        "input_schema": scope["input_schema"],
                        "output_schema": scope["output_schema"],
                    }
                    for scope in mapped_scopes
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    else:
        catalog = _scope_catalog(scopes)
    catalog_heading = (
        "Declared requirements, mapped scopes, output variables, and extracted schemas:"
        if mapped
        else "Callable candidate scopes and exact JSON schemas:"
    )
    return f"""{selection}

Do not select a self-test, demonstration, fixture, or input-free scope. Do not solve
the statute. Do not derive or invent an input fact. A scope is unsupported
if it requires a legal conclusion that the case does not explicitly supply, cannot
represent a needed fact, or has no output corresponding to the question.
{output_instruction}
Judge representability independently of the expected result: negative and
counterexample cases intentionally contain facts that do not establish the queried
proposition. A mismatch of years, people, amounts, or other values between a premise
and the question must be preserved, not treated as missing support. An explicitly
stated statutory premise may be encoded as such when the candidate provides a field
for supplied assumptions.
{expected_rule}

Facts:
{natural["facts"]}

Question:
{natural["question"]}

{catalog_heading}
{catalog}
"""


def _catala_code(project: Path, relative: str) -> str:
    text = (project / relative).read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(r"(?ms)^```catala(?:-metadata)?[^\n]*\n(.*?)^```\s*$", text)
    return "\n\n".join(blocks)


def _relevant_input_descriptions(
    schema: dict[str, Any], registry: dict[str, Any]
) -> dict[str, dict[str, str]]:
    # Select global descriptions referenced by one chosen input schema.
    inventory = exp._input_description_inventory(schema)
    return {
        category: {
            name: (
                registry[category][name]["description"]
                if category == "fields"
                else registry[category][name]
            )
            for name in names
        }
        for category, names in zip(("fields", "enums", "structs"), inventory)
    }


def _input_prompt(
    natural: dict[str, str],
    scope: dict[str, Any],
    project: Path,
    input_descriptions: dict[str, Any] | None = None,
) -> str:
    description_section = (
        "Natural-language definitions for this scope's input fields, enums, and structs:\n"
        + json.dumps(
            {
                "fields": input_descriptions["fields"],
                "enums": input_descriptions["enums"],
                "structs": input_descriptions["structs"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n\n"
        if input_descriptions is not None
        else ""
    )
    return f"""Extract only the factual information stated in this case into the exact
JSON input schema of the selected Catala scope. Return one JSON object and nothing else.

Do not calculate a tax, fee, eligibility result, classification, threshold, or other
legal conclusion. Do not use the requested or expected answer as an input. Do not invent
defaults. If the extraction schema permits null for an input that the case does not
state, return null; the runner will omit it so that the Catala default applies. If the
case does not state a non-nullable required fact, fail rather than guessing.

Facts:
{natural["facts"]}

Question (identifies the subject and time, but is not an input answer):
{natural["question"]}

Selected scope: {scope["file"]}::{scope["scope"]}

Candidate Catala declarations and definitions:
{_catala_code(project, scope["compiler_file"])}

{description_section}Exact extraction JSON schema (null means to omit an optional defaulted input):
{json.dumps(_strict_extraction_schema(scope["input_schema"]), ensure_ascii=False, indent=2, sort_keys=True)}
"""


def _usage_context(
    config: dict[str, Any], state: dict[str, Any], phase: str
) -> dict[str, Any]:
    return {
        "run_id": config["run_id"],
        "iteration": state["iteration"],
        "stage": f"information-extraction-{phase}",
        "framework": "api",
        "provider": config["information_extraction"]["provider"],
        "model": config["information_extraction"]["model"],
    }


def extract(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    candidate: Path,
    candidate_format: dict[str, Any],
    human_tests: Path,
    artifact_directory: Path,
    requirement_outputs: dict[str, Any] | None = None,
    input_variable_descriptions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    scopes = [
        scope
        for scope in candidate_format.get("scopes", [])
        if isinstance(scope.get("input_schema"), dict)
        and isinstance(scope.get("output_schema"), dict)
        and _root_properties(scope["input_schema"])
        and not str(scope.get("scope", "")).casefold().startswith("test")
    ]
    if not scopes:
        return [
            {
                "id": _case_id(relative, line, row),
                "row": row,
                "status": "error",
                "detail": "candidate has no JSON-callable scope",
            }
            for relative, line, row in _rows(human_tests)
        ]
    by_id = {f"{scope['file']}::{scope['scope']}": scope for scope in scopes}
    description_registry = input_variable_descriptions or {}
    scope_ids = sorted(by_id)
    mapped_by_requirement: dict[str, dict[str, Any]] = {}
    if requirement_outputs is not None:
        mapped_by_requirement = {
            entry["requirement_id"]: entry
            for entry in requirement_outputs["requirements"]
        }
        unavailable = sorted(
            entry["requirement_id"]
            for entry in mapped_by_requirement.values()
            if f"{entry['file']}::{entry['scope']}" not in by_id
        )
        if unavailable:
            return [
                {
                    "id": _case_id(relative, line, row),
                    "row": row,
                    "status": "error",
                    "detail": "mapped requirements have no JSON-callable input scope: "
                    + ", ".join(unavailable),
                }
                for relative, line, row in _rows(human_tests)
            ]
    requirement_ids = sorted(mapped_by_requirement) if mapped_by_requirement else None
    settings = config["information_extraction"]
    extraction_root = artifact_directory / "extractions"
    extraction_root.mkdir(parents=True, exist_ok=True)

    def one(item: tuple[str, int, dict[str, Any]]) -> dict[str, Any]:
        relative, line_number, row = item
        identifier = _case_id(relative, line_number, row)
        stem = hashlib.sha256(identifier.encode()).hexdigest()[:20]
        destination = extraction_root / f"{stem}.json"
        natural = natural_case(config["dataset"]["name"], row)
        # The semantic label is an evaluation target, not information that should be shown to the planning or input-extraction…
        prompt_natural = {
            "facts": natural["facts"],
            "question": natural["question"],
        }
        fingerprint = exp.sha256_bytes(
            json.dumps(
                {
                    "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
                    "model": settings["model"],
                    "provider": settings["provider"],
                    "candidate_format": candidate_format,
                    "requirement_outputs": requirement_outputs,
                    "input_variable_descriptions": input_variable_descriptions,
                    "natural": prompt_natural,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        )
        if destination.is_file():
            cached = exp.load_json(destination)
            if cached.get("fingerprint") == fingerprint:
                for phase in ("plan", "input"):
                    response = cached.get(f"{phase}_response")
                    if response and not cached.get(f"{phase}_usage_id"):
                        usage_tracking.cached_response(
                            run_directory,
                            _usage_context(config, state, phase),
                            {
                                "request_id": response.get("id"),
                                "usage": response.get("usage"),
                            },
                            f"{identifier}:{fingerprint}",
                        )
                if "reference_verdict" in natural:
                    cached["reference_verdict"] = natural["reference_verdict"]
                return cached
        record: dict[str, Any] = {
            "schema_version": EXTRACTION_SCHEMA_VERSION,
            "id": identifier,
            "fingerprint": fingerprint,
            "row": row,
            "natural_language": prompt_natural,
            "reference_verdict": natural.get("reference_verdict"),
            "status": "error",
            "detail": None,
        }
        try:
            plan_prompt = _plan_prompt(
                config["dataset"]["name"], natural, scopes, requirement_outputs
            )
            (extraction_root / f"{stem}.plan.prompt.txt").write_text(
                plan_prompt, encoding="utf-8"
            )
            planned = usage_tracking.api_call(
                run_directory,
                {**_usage_context(config, state, "plan"), "case_id": identifier},
                fingerprint + exp.sha256_bytes(plan_prompt.encode()),
                lambda: _call_openai(
                    settings,
                    plan_prompt,
                    _plan_schema(scope_ids, requirement_ids),
                    name="candidate_scope_plan",
                ),
            )
            record["plan_response"] = planned["raw_response"]
            record["plan_usage_id"] = planned.get("_usage_id")
            if planned.get("parse_error"):
                raise ValueError(planned["parse_error"])
            plan = planned["parsed"]
            if mapped_by_requirement:
                mapped = mapped_by_requirement[plan["requirement_id"]]
                plan["scope_id"] = f"{mapped['file']}::{mapped['scope']}"
                plan["output_path"] = [mapped["output"]]
            record["plan"] = plan
            record["plan_response"] = planned["raw_response"]
            if not plan["supported"]:
                record["detail"] = f"unsupported candidate interface: {plan['reason']}"
            else:
                scope = by_id[plan["scope_id"]]
                relevant_descriptions = (
                    _relevant_input_descriptions(
                        scope["input_schema"], description_registry
                    )
                    if input_variable_descriptions is not None
                    else None
                )
                prompt = _input_prompt(
                    natural,
                    scope,
                    candidate,
                    relevant_descriptions,
                )
                (extraction_root / f"{stem}.input.prompt.txt").write_text(
                    prompt, encoding="utf-8"
                )
                sampled = usage_tracking.api_call(
                    run_directory,
                    {**_usage_context(config, state, "input"), "case_id": identifier},
                    fingerprint + exp.sha256_bytes(prompt.encode()),
                    lambda: _call_openai(
                        settings,
                        prompt,
                        scope["input_schema"],
                        name="candidate_scope_input",
                    ),
                )
                record["input_response"] = sampled["raw_response"]
                record["input_usage_id"] = sampled.get("_usage_id")
                if sampled.get("parse_error"):
                    raise ValueError(sampled["parse_error"])
                inputs = _strip_optional_nulls(sampled["parsed"], scope["input_schema"])
                # Catala describes integer-valued money with overlapping draft-04 `oneOf` branches (integer and number).
                Draft202012Validator(
                    _validation_schema(scope["input_schema"])
                ).validate(inputs)
                record.update(
                    status="extracted",
                    inputs=inputs,
                    input_response=sampled["raw_response"],
                )
        except Exception as error:
            record["detail"] = f"{type(error).__name__}: {error}"
        exp.atomic_json(destination, record)
        return record

    jobs = max(1, int(settings.get("jobs", 8)))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        records = list(pool.map(one, list(_rows(human_tests))))
    return records


def _parse_process_json(text: str) -> Any:
    try:
        return json.loads(text.strip(), parse_float=Decimal)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line, parse_float=Decimal)
            except json.JSONDecodeError:
                continue
    raise ValueError("candidate process emitted no JSON value")


def _execute(
    candidate: Path,
    scope: dict[str, Any],
    inputs: Any,
    environment: dict[str, str],
    timeout: int,
) -> Any:
    compiled = compiled_path(candidate, scope["file"], scope["scope"])
    command = (
        [str(compiled), scope["scope"]]
        if compiled.is_file()
        else [
            "clerk",
            "run",
            scope["compiler_file"],
            "--scope",
            scope["scope"],
            "--input",
            "-",
            "--output-format=json",
            "--color=never",
        ]
    )
    process = subprocess.Popen(
        command,
        cwd=candidate,
        env=environment,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            json.dumps(inputs, ensure_ascii=False), timeout=timeout
        )
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    if process.returncode:
        raise RuntimeError((stderr or stdout)[-2000:])
    return _parse_process_json(stdout)


def _at_path(value: Any, path: list[str], schema: dict[str, Any] | None = None) -> Any:
    # Read an output path using Catala's advertised optional-field semantics.
    normalized = _validation_schema(schema) if schema is not None else {}
    definitions = normalized.get("definitions", {})

    def resolve(node: Any) -> Any:
        if not isinstance(node, dict):
            return {}
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            target = definitions.get(reference.removeprefix("#/definitions/"))
            if isinstance(target, dict):
                return target
        return node

    node: Any = resolve(normalized)
    for component in path:
        if isinstance(value, list):
            value = value[int(component)]
            node = resolve(node).get("items", {})
        elif isinstance(value, dict):
            node = resolve(node)
            properties = node.get("properties", {})
            child_schema = properties.get(component, {})
            optional = component in properties and component not in set(
                node.get("required", [])
            )
            if component not in value:
                if optional:
                    return None
                raise KeyError(component)
            value = value[component]
            node = child_schema
        else:
            raise KeyError(f"cannot descend through output component {component!r}")
    return value


def _number(value: Any) -> Decimal:
    text = str(value).replace("$", "").replace(",", "").strip()
    return Decimal(text)


def _equivalent(left: Any, right: Any) -> bool:
    if left == right:
        return True
    try:
        return abs(_number(left) - _number(right)) <= Decimal("0.000000000001")
    except (InvalidOperation, ValueError):
        return False


def _canonical(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _observed_verdict(
    observed: Any,
    plan: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
) -> Any:
    comparison = plan["comparison"]
    if comparison in ("reference_value", "direct_boolean"):
        return observed
    if comparison == "equals_claim":
        return json_equivalent(observed, plan["claim"], output_schema)
    if comparison == "canonical_equals_claim":
        return _canonical(observed) == _canonical(plan["claim"])
    if comparison == "rounded_equals_claim":
        return _number(observed).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ) == _number(plan["claim"])
    raise ValueError(f"unsupported comparison: {comparison}")


def evaluate(
    records: list[dict[str, Any]],
    candidate: Path,
    candidate_format: dict[str, Any],
    *,
    environment: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    by_id = {
        f"{scope['file']}::{scope['scope']}": scope
        for scope in candidate_format.get("scopes", [])
    }
    selected = {
        tuple(record["plan"]["scope_id"].split("::", 1))
        for record in records
        if record.get("status") == "extracted"
    }
    bridge_errors = build_bridges(
        candidate,
        candidate_format,
        environment=environment,
        timeout=timeout,
        selected=selected,
    )
    cases = []
    for record in records:
        case = {
            "id": record["id"],
            "source": "original",
            "status": "error",
            "reference_output": record["row"].get("label"),
            "candidate_output": None,
            "detail": record.get("detail"),
        }
        if record.get("status") != "extracted":
            cases.append(case)
            continue
        try:
            plan = record["plan"]
            scope = by_id[plan["scope_id"]]
            actual = _execute(candidate, scope, record["inputs"], environment, timeout)
            projected = project_output_json(actual, scope["output_schema"])
            observed = _at_path(projected, plan["output_path"], scope["output_schema"])
            observed_schema = schema_at_path(
                scope["output_schema"], plan["output_path"]
            )
            candidate_answer = _observed_verdict(observed, plan, observed_schema)
            if plan["comparison"] == "reference_value":
                expected = record["row"]["label"]
            else:
                expected = record.get("reference_verdict")
            passed = (
                json_equivalent(candidate_answer, expected, observed_schema)
                if plan["comparison"] == "reference_value"
                else _equivalent(candidate_answer, expected)
            )
            case.update(
                status="pass" if passed else "fail",
                candidate_output=_jsonable(actual),
                detail=None
                if passed
                else f"observed {candidate_answer!r}, expected {expected!r}",
            )
        except (
            KeyError,
            IndexError,
            ValueError,
            RuntimeError,
            OSError,
            subprocess.TimeoutExpired,
        ) as error:
            case["detail"] = f"{type(error).__name__}: {error}"
        cases.append(case)
    cases.sort(key=lambda item: item["id"])
    counts = {
        status: sum(case["status"] == status for case in cases)
        for status in ("pass", "fail", "error", "skipped")
    }
    executable = counts["pass"] + counts["fail"]
    return {
        "schema_version": exp.VERIFICATION_SCHEMA_VERSION,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "errors": counts["error"],
            "skipped": counts["skipped"],
            "accuracy": counts["pass"] / executable if executable else None,
            "representability": executable / len(cases) if cases else None,
            "effective_accuracy": counts["pass"] / len(cases) if cases else None,
        },
        "compiled_bridge_errors": bridge_errors,
    }
