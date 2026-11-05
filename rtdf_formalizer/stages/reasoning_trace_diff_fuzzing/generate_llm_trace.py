"""LLM legal reasoning and structured execution-tree generation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.utils import usage as usage_tracking
from rtdf_formalizer.bobcat import compiled_json
from rtdf_formalizer.bobcat.trace import (
    requirement_descriptions,
    schema_scopes,
)

_BLOCK_DETAILS = re.compile(r"<!-- rtdf-block-id: ([^;]+);[^>]*provision-id: ([^;]+);")
_HTML_COMMENT = re.compile(r"<!--[\s\S]*?-->")
_FENCE = re.compile(r"^```(?:catala[^\n]*)?$", re.MULTILINE)
_ANSWER_BLOCK = re.compile(r"<answer>\s*([\s\S]*?)\s*</answer>", re.IGNORECASE)
_LABELED_PROVISION = re.compile(r"^\[([^\]\n]+)\]", re.MULTILINE)
REASONING_RESULT_FORMAT = "reasoning_with_json_answer_and_execution_tree"


def _labeled_statute_prose(prose: str) -> str:
    # Label every stored provision marker while retaining all statute prose.
    passages = []
    start = 0
    for comment in _HTML_COMMENT.finditer(prose):
        marker = _BLOCK_DETAILS.search(comment.group())
        if not marker or marker.group(2) == "none":
            continue
        passage = _HTML_COMMENT.sub("", prose[start : comment.start()]).strip()
        if passage:
            passages.append(f"[{marker.group(2)}] {passage}")
        else:
            passages.append(f"[{marker.group(2)}]")
        start = comment.end()
    trailing = _HTML_COMMENT.sub("", prose[start:]).strip()
    if trailing:
        passages.append(trailing)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(passages))


def _statutes(run_directory: Path, config: dict[str, Any]) -> str:
    manifest = exp.load_json(run_directory / "input/RTDF_MANIFEST.json")
    documents = []
    for document in manifest.get("documents", []):
        # The frozen input is the curated gold statute prose with provision IDs; no model-generated code appears in it.
        source = run_directory / "input" / document["path"]
        if not source.is_file():
            raise exp.RunnerError(f"gold statute is missing: {source}")
        text = source.read_text(encoding="utf-8")
        # The gold Catala document interleaves statute prose and executable code.
        pieces = _FENCE.split(text)
        prose = "".join(piece for index, piece in enumerate(pieces) if index % 2 == 0)
        documents.append(_labeled_statute_prose(prose))
    return "\n\n".join(documents)


def _output_fields(schema: dict[str, Any]) -> list[str]:
    # Keep only field names and ordinary JSON value kinds for the prompt.
    definitions = schema.get("definitions", {})

    def resolve(
        node: dict[str, Any], seen: frozenset[str] = frozenset()
    ) -> dict[str, Any]:
        reference = node.get("$ref")
        if isinstance(reference, str):
            name = reference.rsplit("/", 1)[-1]
            if name in seen or name not in definitions:
                return {}
            return resolve(definitions[name], seen | {name})
        return node

    def kind(node: dict[str, Any]) -> str:
        node = resolve(node)
        if "enum" in node:
            return "one of " + ", ".join(
                json.dumps(value, ensure_ascii=False) for value in node["enum"]
            )
        if "oneOf" in node:
            types = {kind(part) for part in node["oneOf"]}
            if types <= {"integer", "number", "string"} and types & {
                "integer",
                "number",
            }:
                return "number" if "number" in types else "integer"
            return " or ".join(sorted(types))
        value_type = node.get("type")
        if value_type == "array":
            return "array of " + kind(node.get("items", {}))
        return value_type or "JSON value"

    lines = []

    def visit(node: dict[str, Any], path: str = "") -> None:
        node = resolve(node)
        if node.get("type") == "object" and node.get("properties"):
            required = set(node.get("required", []))
            for name, field in node["properties"].items():
                child = f"{path}.{name}" if path else name
                resolved = resolve(field)
                if resolved.get("type") == "object" and resolved.get("properties"):
                    visit(resolved, child)
                else:
                    suffix = " (optional)" if name not in required else ""
                    lines.append(f"- {child}: {kind(field)}{suffix}")
        else:
            lines.append(f"- {path or 'value'}: {kind(node)}")

    visit(schema)
    return lines


def _answer_example(schema: dict[str, Any]) -> Any:
    # Build a JSON-serializable output template while preserving its shape.
    definitions = schema.get("definitions", {})

    def render(node: Any, seen: frozenset[str] = frozenset()) -> Any:
        if not isinstance(node, dict):
            return "<JSON value>"
        reference = node.get("$ref")
        if isinstance(reference, str):
            name = reference.rsplit("/", 1)[-1]
            if name in seen or name not in definitions:
                return "<JSON value>"
            return render(definitions[name], seen | {name})
        if isinstance(node.get("enum"), list):
            choices = " | ".join(str(value) for value in node["enum"])
            return f"<one of: {choices}>"
        if isinstance(node.get("oneOf"), list):
            kinds = {
                _output_fields(part)[0].split(": ", 1)[-1]
                for part in node["oneOf"]
                if isinstance(part, dict)
            }
            if kinds <= {"integer", "number", "string"} and kinds & {
                "integer",
                "number",
            }:
                return "<number>" if "number" in kinds else "<integer>"
            return "<" + " or ".join(sorted(kinds or {"JSON value"})) + ">"
        value_type = node.get("type")
        if value_type == "object":
            properties = node.get("properties", {})
            if not isinstance(properties, dict):
                return {}
            required = set(node.get("required", []))
            rendered = {}
            for name, field in properties.items():
                value = render(field, seen)
                if (
                    name not in required
                    and isinstance(value, str)
                    and value.endswith(">")
                ):
                    value = value[:-1] + "; optional—omit property if absent>"
                rendered[name] = value
            return rendered
        if value_type == "array":
            return [render(node.get("items", {}), seen)]
        return f"<{value_type or 'JSON value'}>"

    return render(schema)


def _prompt(
    statutes: str,
    case: dict[str, Any],
    output_schema: dict[str, Any],
    dataset: str | None = None,
    requirement_description: str | None = None,
) -> str:
    symbolic = case["inputs"]
    fields = _output_fields(output_schema)
    dataset_prefix = f"{dataset}/" if dataset else ""
    statutes = (
        statutes.replace(f"[{dataset_prefix}", "[") if dataset_prefix else statutes
    )
    requirement = case.get("requirement_id") or case["target"]
    description = (
        requirement_description
        or f"calculate the result specified by requirement {requirement}"
    )
    requested_list = "\n".join(
        f"- {line[2:].split(':', 1)[0]}: {description}" for line in fields
    )
    answer_example = json.dumps(
        _answer_example(output_schema), ensure_ascii=False, indent=2
    )
    return (
        f"Statutes:\n{statutes}\n\n"
        "The case is as follows (YAML):\n"
        f"{yaml.safe_dump(symbolic, allow_unicode=True, sort_keys=False)}\n"
        "Calculate these values under the supplied statutes:\n"
        f"{requested_list}\n\n"
        "Solve only the concrete case presented above.\n\n"
        "Use only the supplied statutes and their local semantics. Do not supplement, "
        "repair, update, or reinterpret them using outside legal knowledge. In "
        "particular, do not import requirements, exceptions, thresholds, definitions, "
        "tax-year rules, or other conditions that are not stated in the supplied "
        "statutes.\n\n"
        "Give a step-by-step solution that traces the concrete value flow leading to "
        "the requested output. Each step must state, as applicable:\n\n"
        "- the input facts or earlier computed values it uses;\n"
        "- the statutory condition that is evaluated and whether it is satisfied;\n"
        "- the operation or legal rule applied;\n"
        "- the resulting intermediate or final value.\n\n"
        "Explain only rules, conditions, and calculations that contribute to the "
        "requested output for this concrete case. Do not discuss alternative filing "
        "statuses, untaken branches, hypothetical facts, rejected legal routes, "
        "general background law, or provisions that do not contribute to the result.\n\n"
        "Keep each step focused on one claim or calculation. Make dependencies between "
        "steps explicit in the prose—for example, say that a calculation uses the "
        "adjusted gross income established in an earlier step. Dependencies include "
        "legal or control dependencies as well as numeric operands. When a later "
        "calculation applies a bracket, rate, deduction, exemption, or formula selected "
        "by an earlier filing-status, eligibility, classification, condition, exception, "
        "or schedule conclusion, explicitly state that it uses that earlier conclusion, "
        "even when the conclusion supplies no numeric operand. Show all arithmetic "
        "needed to reproduce the final result. Use the exact values supplied in the "
        "case; do not silently replace, combine, infer, or default values unless the "
        "supplied statutes expressly require it.\n\n"
        "Write the solution as numbered prose steps. Do not emit JSON for the steps, "
        "citation lists, premise IDs, or an execution tree; a second stage will extract "
        "that structure. Do not use square brackets as informal citations. You may "
        "identify a statutory provision in ordinary prose when it is directly applied, "
        "but do not invent a provision identifier. Only identifiers shown in square "
        "brackets in the supplied statutes are citable. Unlabeled ancestor text remains "
        "part of the rule context inherited by its labeled descendants, but must not be "
        "cited separately. Whenever you directly apply a rule, cite its labeled leaf "
        "provision. If an operation uses multiple alternatives or components, cite every "
        "labeled leaf that contributes to the operation.\n\n"
        "After the numbered steps, emit exactly one literal <answer> opening tag and "
        "one literal </answer> closing tag, each on its own line. Between them, "
        "emit only the final JSON value. These tags are required output, not "
        "example delimiters. Do not use Markdown code fences "
        "anywhere. Do not write anything after the closing tag.\n\n"
        "Produce your final answer in the question-specific JSON format shown "
        "inside <answer>. Replace every angle-bracketed placeholder with the "
        "computed JSON value of that kind, preserving the object/list structure "
        "and property names exactly except where a placeholder says to omit an "
        "optional absent property. Numeric and boolean placeholders become "
        "unquoted JSON numbers and booleans, not strings. Before submitting, "
        "verify that every intermediate value is supported by stated inputs or "
        "earlier steps, that the arithmetic reproduces the final value, and that "
        "the answer tags and JSON syntax are exact.\n\n"
        "<answer>\n"
        f"{answer_example}\n"
        "</answer>\n"
    )


def _allowed_provision_ids(statutes: str) -> list[str]:
    # Return the labeled statutory universe in stable first-occurrence order.
    return list(dict.fromkeys(_LABELED_PROVISION.findall(statutes)))


def _execution_tree_schema(provisions: list[str]) -> dict[str, Any]:
    provision_options: list[dict[str, Any]] = [{"type": "null"}]
    if provisions:
        provision_options.insert(0, {"type": "string", "enum": provisions})
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "minimum": 0},
                        "claim": {"type": "string", "minLength": 1},
                        "provision": {"anyOf": provision_options},
                        "premises": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 0},
                        },
                    },
                    "required": ["id", "claim", "provision", "premises"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def _reasoning_without_answer(text: str) -> str:
    # Remove the answer block before giving the prose to the extraction stage.
    match = _ANSWER_BLOCK.search(text)
    return text[: match.start()].rstrip() if match else text.rstrip()


def _execution_tree_prompt(candidate: str, provisions: list[str]) -> str:
    allowed = json.dumps(provisions, ensure_ascii=False, indent=2)
    return (
        "You are extracting a minimal execution tree from a candidate step-by-step solution.\n\n"
        "Do not solve the legal problem again. Do not correct the candidate solution, add "
        "missing reasoning, import outside law, or introduce a claim that the candidate did "
        "not make. Represent only the concrete reasoning actually stated in the candidate "
        "solution.\n\n"
        "Keep only claims and calculations that the candidate presents as contributing to "
        "its final answer. Omit background discussion, hypothetical facts, alternative legal "
        "routes, untaken branches, general explanations, and repeated restatements.\n\n"
        "Convert the retained reasoning into topologically ordered atomic steps.\n\n"
        "For every step:\n\n"
        "- `id` must be its zero-based position in `steps`. IDs must be contiguous: 0, 1, "
        "2, and so on.\n"
        "- `claim` must be one concise, self-contained claim, condition result, calculation, "
        "intermediate value, or final result taken from the candidate solution.\n"
        "- `provision` must be exactly one provision ID from the allowed list when that "
        "provision directly supports the claim.\n"
        "- Set `provision` to null for a purely factual, arithmetic, aggregation, or final "
        "result step that applies no statutory provision.\n"
        "- If a candidate statement relies directly on more than one provision, split it "
        "into multiple atomic steps so that each extracted step has at most one provision.\n"
        "- `premises` must contain the IDs of the earlier steps whose claims are directly "
        "required for this step.\n"
        "- Every premise ID must be smaller than the current step's ID.\n"
        "- Include only direct premises, not every transitive ancestor.\n"
        "- An input-fact step normally has no premises.\n"
        "- A statutory-condition step should depend on the input-fact or intermediate-value "
        "steps needed to evaluate it.\n"
        "- Premises include legal or control dependencies as well as data dependencies.\n"
        "- A calculation step should depend on the steps supplying its operands and on any "
        "earlier positive conclusion that selects or makes applicable the bracket, rate, "
        "deduction, exemption, formula, or other rule used by the calculation. Such a "
        "filing-status, eligibility, classification, condition, exception, or schedule step "
        "is a direct premise even when it supplies no numeric operand.\n"
        "- The final-result step should depend on the immediately preceding component or "
        "calculation steps that establish that result.\n\n"
        "Before returning the tree, audit every retained positive contributing step. Each "
        "must have a directed path to the final-result step. If a positive condition, "
        "classification, eligibility, status, exception, or schedule step would otherwise "
        "be terminal or disconnected, connect it as a direct premise of the first later "
        "step that uses its conclusion. Omit rejected alternatives and negative conclusions "
        "that do not contribute to the selected route; do not connect them merely to satisfy "
        "this audit.\n\n"
        "Do not merge distinct calculations merely because they use the same provision. "
        "Do not create a provision-only background step with no concrete effect on the "
        "candidate's result. Preserve incorrect candidate reasoning faithfully rather than "
        "repairing it.\n\n"
        f"Allowed provision IDs:\n{allowed}\n\n"
        "Candidate solution:\n<candidate_solution>\n"
        f"{candidate}\n"
        "</candidate_solution>\n"
    )


def _validate_execution_tree(value: Any, provisions: set[str]) -> str | None:
    # Validate ordering constraints that JSON Schema cannot express.
    if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
        return "execution-tree output has no steps array"
    steps = value["steps"]
    if not steps:
        return "execution-tree steps array is empty"
    for expected, step in enumerate(steps):
        if not isinstance(step, dict):
            return f"execution-tree step {expected} is not an object"
        if step.get("id") != expected:
            return f"execution-tree step ID {step.get('id')!r} must equal {expected}"
        claim = step.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            return f"execution-tree step {expected} has an empty claim"
        provision = step.get("provision")
        if provision is not None and provision not in provisions:
            return f"execution-tree step {expected} has unknown provision {provision!r}"
        premises = step.get("premises")
        if not isinstance(premises, list) or any(
            not isinstance(premise, int) or isinstance(premise, bool)
            for premise in premises
        ):
            return f"execution-tree step {expected} has invalid premises"
        if len(premises) != len(set(premises)):
            return f"execution-tree step {expected} has duplicate premises"
        if any(premise < 0 or premise >= expected for premise in premises):
            return f"execution-tree step {expected} must reference only earlier steps"
    return None


def parse_final_answer(text: Any) -> tuple[Any | None, str | None]:
    # Parse the single JSON value enclosed by the model's answer tags.
    if not isinstance(text, str):
        return None, "reasoning output is not text"
    blocks = _ANSWER_BLOCK.findall(text)
    if len(blocks) != 1:
        return None, f"expected exactly one <answer> block, found {len(blocks)}"
    try:
        return json.loads(blocks[0]), None
    except json.JSONDecodeError as error:
        return (
            None,
            f"invalid JSON in <answer>: {error.msg} at line {error.lineno} column {error.colno}",
        )


def _sample(
    config: dict[str, Any], prompt: str, response_schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    provider = config["reasoning_trace"]["provider"].lower()
    model = config["reasoning_trace"]["model"]
    error = None
    if provider == "claude-code":
        if response_schema is not None:
            raise exp.RunnerError(
                "Claude Code does not provide constrained JSON-schema decoding"
            )
        command = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--safe-mode",
            "--model",
            model,
        ]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise exp.RunnerError(
                f"Claude Code reasoning request failed: {error}"
            ) from error
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise exp.RunnerError(
                f"Claude Code reasoning response was not JSON: {completed.stdout[-2000:]}"
            ) from error
        output = raw.get("result", "")
        if completed.returncode != 0 or raw.get("is_error"):
            # Claude Code can print an unrelated telemetry warning on stderr while returning the actual provider failure (for…
            detail = (str(output) if output else completed.stderr).strip()
            raise exp.RunnerError(
                f"Claude Code reasoning request failed ({completed.returncode}): "
                f"{detail[-2000:]}"
            )
        elif not isinstance(output, str):
            error = "Claude Code reasoning response has no text result"
            output = None
    elif provider == "anthropic":
        key_name = config["reasoning_trace"].get("api_key_env", "ANTHROPIC_API_KEY")
        key = os.environ.get(key_name)
        if not key:
            raise exp.RunnerError(
                f"reasoning API key environment variable is missing: {key_name}"
            )
        request_body: dict[str, Any] = {
            "model": model,
            "max_tokens": config["reasoning_trace"].get("max_output_tokens", 4096),
            "messages": [{"role": "user", "content": prompt}],
        }
        if response_schema is not None:
            request_body["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": response_schema,
                }
            }
        payload = json.dumps(request_body).encode("utf-8")
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise exp.RunnerError(
                f"Anthropic request failed ({error.code}): {detail[-2000:]}"
            ) from error
        output = "".join(
            block.get("text", "")
            for block in raw.get("content", [])
            if block.get("type") == "text"
        )
    elif provider == "openai":
        from openai import OpenAI

        key_name = config["reasoning_trace"].get("api_key_env", "OPENAI_API_KEY")
        client = OpenAI(
            api_key=os.environ.get(key_name),
            base_url=config["reasoning_trace"].get("base_url"),
        )
        request: dict[str, Any] = {"model": model, "input": prompt}
        if response_schema is not None:
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "reasoning_execution_tree",
                    "strict": True,
                    "schema": response_schema,
                }
            }
        response = client.responses.create(**request)
        raw = response.model_dump(mode="json")
        output = response.output_text
    else:
        from openai import OpenAI

        base_url = config["reasoning_trace"].get("base_url")
        if not base_url:
            raise exp.RunnerError(
                f"reasoning provider {provider!r} requires reasoning_trace.base_url"
            )
        key_name = config["reasoning_trace"].get("api_key_env", "OPENAI_API_KEY")
        client = OpenAI(api_key=os.environ.get(key_name), base_url=base_url)
        request = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        if response_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "reasoning_execution_tree",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        response = client.chat.completions.create(**request)
        raw = response.model_dump(mode="json")
        output = response.choices[0].message.content or "" if response.choices else ""
    return {
        "raw_response": raw,
        "output_text": output,
        "request_id": raw.get("id") or raw.get("session_id"),
        "usage": raw.get("usage"),
        **({"error": error} if error else {}),
    }


def reason(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    iteration = exp.stage_directory(run_directory, state)
    root = iteration / "tests_bobcat_natural_language_results"
    root.mkdir(parents=True, exist_ok=True)
    statutes = _statutes(run_directory, config)
    dataset_name = config.get("dataset", {}).get("name")
    if dataset_name:
        statutes = statutes.replace(f"[{dataset_name}/", "[")
    formats = exp.load_json(
        iteration / "tests_bobcat_symbolic_results/input_formats.json"
    )
    schemas = {
        (item["compiler_file"], item["scope"]): item["output_schema"]
        for item in schema_scopes(formats)
    }
    dataset_source = Path(config.get("dataset", {}).get("source", ""))
    descriptions = requirement_descriptions(
        dataset_source.parent.parent / "catala_gold" / dataset_source.name
    )
    provisions = _allowed_provision_ids(statutes)
    execution_tree_schema = _execution_tree_schema(provisions)
    usage_context = {
        "run_id": config["run_id"],
        "iteration": state["iteration"],
        "stage": "reasoning",
        "framework": "api",
        "provider": config["reasoning_trace"]["provider"],
        "model": config["reasoning_trace"]["model"],
    }
    extraction_usage_context = {**usage_context, "stage": "reasoning-extraction"}

    def sample_case(case: dict[str, Any]) -> dict[str, Any]:
        destination = root / f"{case['id']}.json"
        schema = schemas.get((case["source"], case["target"]), {"type": "object"})
        if case.get("output_name"):
            schema = compiled_json.named_output_schema(schema, case["output_name"])
        requirement_id = case.get("requirement_id")
        prompt = _prompt(
            statutes,
            case,
            schema,
            dataset_name,
            descriptions.get(requirement_id) if requirement_id else None,
        )
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if destination.is_file():
            existing = exp.load_json(destination)
            if (
                existing.get("format") == REASONING_RESULT_FORMAT
                and existing.get("prompt_sha256") == prompt_sha256
            ):
                if not existing.get("error") and not existing.get(
                    "execution_tree_extraction_error"
                ):
                    usage_tracking.cached_response(
                        run_directory,
                        usage_context,
                        existing,
                        f"{case['id']}:{prompt_sha256}",
                    )
                    return existing
                # Failed responses are diagnostics, not reusable completions.
        prompt_file = root / f"{case['id']}.prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        started = time.monotonic()
        try:
            sampled = usage_tracking.api_call(
                run_directory,
                {**usage_context, "case_id": case["id"]},
                prompt_sha256,
                lambda: _sample(config, prompt),
            )
        except Exception as error:
            sampled = {
                "output_text": None,
                "error": f"{type(error).__name__}: {error}",
                "request_id": None,
                "usage": None,
            }
        extraction_prompt = None
        extraction_prompt_sha256 = None
        extracted_tree = None
        extraction_error = None
        extraction_sampled: dict[str, Any] = {}
        if not sampled.get("error") and isinstance(sampled.get("output_text"), str):
            extraction_prompt = _execution_tree_prompt(
                _reasoning_without_answer(sampled["output_text"]), provisions
            )
            extraction_prompt_sha256 = hashlib.sha256(
                extraction_prompt.encode("utf-8")
            ).hexdigest()
            extraction_prompt_file = root / f"{case['id']}.execution-tree.prompt.txt"
            extraction_prompt_file.write_text(extraction_prompt, encoding="utf-8")
            try:
                extraction_sampled = usage_tracking.api_call(
                    run_directory,
                    {**extraction_usage_context, "case_id": case["id"]},
                    extraction_prompt_sha256,
                    lambda: _sample(config, extraction_prompt, execution_tree_schema),
                )
                try:
                    extracted_tree = json.loads(
                        extraction_sampled.get("output_text") or ""
                    )
                except (TypeError, ValueError) as error:
                    extraction_error = f"invalid execution-tree JSON: {error}"
                if extraction_error is None:
                    extraction_error = _validate_execution_tree(
                        extracted_tree, set(provisions)
                    )
                    if extraction_error is not None:
                        extracted_tree = None
            except Exception as error:
                extraction_error = f"{type(error).__name__}: {error}"
        record = {
            "id": case["id"],
            "prompt_file": prompt_file.name,
            "execution_tree_prompt_file": (
                f"{case['id']}.execution-tree.prompt.txt"
                if extraction_prompt is not None
                else None
            ),
            "format": REASONING_RESULT_FORMAT,
            "prompt_sha256": prompt_sha256,
            "execution_tree_prompt_sha256": extraction_prompt_sha256,
            "model": config["reasoning_trace"]["model"],
            "provider": config["reasoning_trace"]["provider"],
            "elapsed_seconds": time.monotonic() - started,
            "execution_tree": extracted_tree,
            "execution_tree_extraction_error": extraction_error,
            "execution_tree_raw_response": extraction_sampled.get("raw_response"),
            "execution_tree_request_id": extraction_sampled.get("request_id"),
            "execution_tree_usage": extraction_sampled.get("usage"),
            **sampled,
        }
        exp.atomic_json(destination, record)
        if record.get("error"):
            raise exp.RunnerError(
                f"reasoning case {case['id']} failed: {record['error']}"
            )
        return record

    jobs = max(1, int(config["reasoning_trace"].get("jobs", 1)))
    if jobs == 1:
        return [sample_case(case) for case in cases]
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        return list(executor.map(sample_case, cases))


run = reason
