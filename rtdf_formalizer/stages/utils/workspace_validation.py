"""Candidate integrity, dependency, schema, and requirement validation."""

from __future__ import annotations

import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .catala import (
    catala_sources,
    copy_project,
    included_files,
    run_checked,
    toolchain_environment,
    write_verification_clerk_config,
)
from .common import (
    FENCE_START,
    SCOPE_DECLARATION,
    RunnerError,
    load_json,
    normalize_protected_whitespace,
    parse_fenced_document,
    relative_files,
    sha256_file,
)

REQUIREMENT_OUTPUTS_FILE = "REQUIREMENT_OUTPUTS.json"
INPUT_VARIABLE_DESCRIPTION_FILE = "INPUT_VARIABLE_DESCRIPTION.json"
REQUIREMENT_ID = re.compile(r"(?m)^-[ \t]+`([A-Z0-9][A-Z0-9-]*)`:")
API_REQUIREMENT = re.compile(
    r"(?m)^-[ \t]+Requirement ID[ \t]+`([A-Z0-9][A-Z0-9-]*)`:"
    r"[ \t]+scope[ \t]+`([^`]+)`,[ \t]+output[ \t]+`([^`]+)`\.\s*$"
)
MIN_VALID_CATALA_BLOCK_RATIO = 0.9
MIN_VALID_CATALA_BLOCK_LINES = 2

SCOPE_DEFINITION_START = re.compile(
    r"^[ \t]*(?:scope|champ[ \t]+d'application)[ \t]+([^\W\d]\w*)[ \t]*:",
    re.MULTILINE,
)
VARIABLE_DEFINITION = re.compile(
    r"^[ \t]*(?:definition|définition)[ \t]+([^\s.:[\](){}]+)",
    re.MULTILINE,
)
SCOPE_OUTPUT = re.compile(
    r"^[ \t]*(?:output|résultat)[ \t]+([^\s.:[\](){}]+)[ \t]+"
    r"(?:content|contenu)\b",
    re.MULTILINE,
)
RTDF_BLOCK_ID = re.compile(rb"<!--[ \t]*rtdf-block-id:[ \t]*([^;>]+)[ \t]*;")


def valid_catala_block(block: bytes) -> bool:
    # Require at least two nonblank, non-comment lines of Catala.
    code_lines = sum(
        1
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith(b"#")
    )
    return code_lines >= MIN_VALID_CATALA_BLOCK_LINES


def catala_block_symbols(block: bytes) -> tuple[set[str], set[tuple[str, str]]]:
    # Return declared scopes and scope variables defined by one fence body.
    text = block.decode("utf-8", errors="replace")
    declared = set(SCOPE_DECLARATION.findall(text))
    definitions: set[tuple[str, str]] = set()
    current_scope: str | None = None
    for line in text.splitlines():
        scope = SCOPE_DEFINITION_START.match(line)
        if scope:
            current_scope = scope.group(1)
            continue
        if SCOPE_DECLARATION.match(line):
            current_scope = None
            continue
        definition = VARIABLE_DEFINITION.match(line)
        if current_scope is not None and definition:
            definitions.add((current_scope, definition.group(1)))
    return declared, definitions


def declared_scope_outputs(source: Path) -> dict[str, set[str]]:
    # Read output declarations from the Catala metadata fences in a source.
    outputs: dict[str, set[str]] = {}
    for block in parse_fenced_document(source).blocks:
        text = block.decode("utf-8", errors="replace")
        current_scope: str | None = None
        for line in text.splitlines():
            declaration = SCOPE_DECLARATION.match(line)
            if declaration:
                current_scope = declaration.group(1)
                outputs.setdefault(current_scope, set())
                continue
            if SCOPE_DEFINITION_START.match(line):
                current_scope = None
                continue
            output = SCOPE_OUTPUT.match(line)
            if current_scope is not None and output:
                outputs[current_scope].add(output.group(1))
    return outputs


def _dependency_graph_edges(
    graph: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    # Decode compiler edges as dependent-to-dependencies and scope calls.
    intra: dict[str, set[str]] = {}
    for scope, payload in graph.get("intra_scopes", {}).items():
        if not isinstance(payload, dict):
            continue
        nodes = {
            str(identifier): str(name)
            for identifier, name in payload.get("nodes", {}).items()
        }
        dependencies = {name: set() for name in nodes.values()}
        for edge in payload.get("edges", []):
            source = nodes.get(str(edge.get("from")))
            target = nodes.get(str(edge.get("to")))
            if source is not None and target is not None:
                dependencies.setdefault(target, set()).add(source)
        for variable, values in dependencies.items():
            intra[f"{scope}\0{variable}"] = {f"{scope}\0{value}" for value in values}

    inter_payload = graph.get("inter_scopes", {})
    nodes = (
        {
            str(identifier): str(name)
            for identifier, name in inter_payload.get("nodes", {}).items()
        }
        if isinstance(inter_payload, dict)
        else {}
    )
    inter = {name: set() for name in nodes.values()}
    if isinstance(inter_payload, dict):
        for edge in inter_payload.get("edges", []):
            source = nodes.get(str(edge.get("from")))
            target = nodes.get(str(edge.get("to")))
            if source is not None and target is not None:
                inter.setdefault(target, set()).add(source)
    return intra, inter


def _dependency_closure(
    dependencies: dict[str, set[str]], targets: set[str]
) -> set[str]:
    closure = set(targets)
    pending = list(targets)
    while pending:
        target = pending.pop()
        for dependency in dependencies.get(target, set()):
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return closure


def _matching_graph_scope(scope: str, candidates: set[str]) -> str | None:
    # Match an authored scope name to its possibly module-qualified graph name.
    if scope in candidates:
        return scope
    matches = sorted(name for name in candidates if name.rsplit(".", 1)[-1] == scope)
    return matches[0] if len(matches) == 1 else None


def dependency_live_definitions(
    workspace: Path, requirement_outputs: dict[str, Any]
) -> dict[str, tuple[set[str], set[tuple[str, str]]]]:
    # Find scope definitions that feed outputs exposed by requirement mappings.
    sources = catala_sources(workspace)
    included = {name for source in sources for name in included_files(source)}
    masters = [source for source in sources if source.name not in included]
    owner_by_file: dict[str, Path] = {}
    for source in sources:
        owner = source
        if source.name in included:
            owners = [
                candidate
                for candidate in masters
                if source.name in included_files(candidate)
            ]
            if len(owners) != 1:
                raise RunnerError(
                    f"cannot identify master file for included {source.name}"
                )
            owner = owners[0]
        owner_by_file[source.relative_to(workspace).as_posix()] = owner

    selected_by_owner: dict[Path, dict[str, set[str]]] = {}
    for entry in requirement_outputs["requirements"]:
        owner = owner_by_file.get(entry["file"])
        if owner is None:
            raise RunnerError(f"mapped Catala file does not exist: {entry['file']}")
        selected_by_owner.setdefault(owner, {}).setdefault(entry["scope"], set()).add(
            entry["output"]
        )

    outputs_by_owner: dict[Path, dict[str, set[str]]] = {}
    for relative, owner in owner_by_file.items():
        source_outputs = declared_scope_outputs(workspace / relative)
        combined = outputs_by_owner.setdefault(owner, {})
        for scope, outputs in source_outputs.items():
            combined.setdefault(scope, set()).update(outputs)

    environment = toolchain_environment({})
    clerk = shutil.which("clerk", path=environment.get("PATH"))
    catala = shutil.which("catala", path=environment.get("PATH"))
    if not clerk or not catala:
        raise RunnerError("the submission dependency check requires clerk and catala")

    live_by_owner: dict[Path, tuple[set[str], set[tuple[str, str]]]] = {}
    with tempfile.TemporaryDirectory(prefix="rtdf-dependency-check-") as temporary_name:
        temporary = Path(temporary_name) / "project"
        copy_project(workspace, temporary)
        write_verification_clerk_config(temporary)
        run_checked(
            [clerk, "start", "--color=never"],
            cwd=temporary,
            environment=environment,
            timeout=300,
        )
        for owner, selected in selected_by_owner.items():
            relative_owner = owner.relative_to(workspace).as_posix()
            completed = run_checked(
                [
                    catala,
                    "dependency-graph",
                    relative_owner,
                    "--stdlib",
                    "_build/libcatala",
                    "--include",
                    ".",
                    "--whole-program",
                    "--color=never",
                ],
                cwd=temporary,
                environment=environment,
                timeout=300,
            )
            try:
                graph = json.loads(completed.stdout)
            except json.JSONDecodeError as error:
                raise RunnerError(
                    f"could not parse Catala dependency graph for {relative_owner}: {error}"
                ) from error
            intra, inter = _dependency_graph_edges(graph)
            graph_scopes = set(inter)
            graph_scopes.update(key.split("\0", 1)[0] for key in intra)
            selected_graph: dict[str, set[str]] = {}
            for scope, outputs in selected.items():
                graph_scope = _matching_graph_scope(scope, graph_scopes)
                if graph_scope is None:
                    raise RunnerError(
                        f"mapped scope is absent or ambiguous in dependency graph: "
                        f"{relative_owner}::{scope}"
                    )
                selected_graph.setdefault(graph_scope, set()).update(outputs)

            reachable_scopes = _dependency_closure(inter, set(selected_graph))
            authored_outputs = outputs_by_owner.get(owner, {})
            live_variables: set[tuple[str, str]] = set()
            live_scopes: set[str] = set()
            for graph_scope in reachable_scopes:
                short_scope = graph_scope.rsplit(".", 1)[-1]
                targets = selected_graph.get(graph_scope)
                if targets is None:
                    targets = authored_outputs.get(short_scope, set())
                qualified_targets = {f"{graph_scope}\0{target}" for target in targets}
                existing_targets = qualified_targets & set(intra)
                if (
                    graph_scope in selected_graph
                    and existing_targets != qualified_targets
                ):
                    missing = sorted(
                        target.split("\0", 1)[1]
                        for target in qualified_targets - existing_targets
                    )
                    raise RunnerError(
                        f"mapped outputs are absent from dependency graph for "
                        f"{relative_owner}::{short_scope}: {missing}"
                    )
                live = _dependency_closure(intra, existing_targets)
                if existing_targets:
                    live_scopes.add(short_scope)
                live_variables.update(
                    (short_scope, item.split("\0", 1)[1])
                    for item in live
                    if item.startswith(f"{graph_scope}\0")
                )
            live_by_owner[owner] = (live_scopes, live_variables)

    result: dict[str, tuple[set[str], set[tuple[str, str]]]] = {}
    for relative, owner in owner_by_file.items():
        result[relative] = live_by_owner.get(owner, (set(), set()))
    return result


def dependency_valid_catala_block(
    block: bytes,
    live_scopes: set[str],
    live_variables: set[tuple[str, str]],
) -> bool:
    # Require substantive code that declares or defines dependency-live symbols.
    if not valid_catala_block(block):
        return False
    declared, definitions = catala_block_symbols(block)
    return bool(declared & live_scopes or definitions & live_variables)


def catala_block_ids(source: Path) -> tuple[str, ...]:
    # Return each Catala fence's preceding RTDF block ID in source order.
    identifiers: list[str] = []
    pending: str | None = None
    for line in source.read_bytes().splitlines(keepends=True):
        match = RTDF_BLOCK_ID.search(line)
        if match:
            pending = match.group(1).decode("utf-8", errors="replace").strip()
        if FENCE_START.fullmatch(line.decode("utf-8", errors="surrogateescape")):
            identifiers.append(pending or f"unidentified-fence-{len(identifiers) + 1}")
            pending = None
    return tuple(identifiers)


def unreachable_catala_blocks(
    workspace: Path, requirement_outputs: dict[str, Any]
) -> list[str]:
    # List RTDF blocks outside the union of mapped-output dependencies.
    live = dependency_live_definitions(workspace, requirement_outputs)
    unreachable: list[str] = []
    for source in catala_sources(workspace):
        relative = source.relative_to(workspace).as_posix()
        blocks = parse_fenced_document(source).blocks
        identifiers = catala_block_ids(source)
        if len(identifiers) != len(blocks):
            raise RunnerError(
                f"could not associate RTDF block IDs with fences in {relative}"
            )
        live_scopes, live_variables = live.get(relative, (set(), set()))
        unreachable.extend(
            identifier
            for identifier, block in zip(identifiers, blocks)
            if not dependency_valid_catala_block(block, live_scopes, live_variables)
        )
    return sorted(unreachable)


def required_functionality_ids(dataset: Path) -> list[str]:
    # Read the stable requirement IDs from a dataset's task document.
    identifiers: list[str] = []
    for document in sorted(dataset.glob("*.md")):
        identifiers.extend(REQUIREMENT_ID.findall(document.read_text(encoding="utf-8")))
    if len(identifiers) != len(set(identifiers)):
        duplicates = sorted(
            {value for value in identifiers if identifiers.count(value) > 1}
        )
        raise RunnerError(f"duplicate requirement IDs in task documents: {duplicates}")
    return identifiers


def api_requirement_outputs(dataset: Path) -> dict[str, Any] | None:
    # Read protected requirement mappings embedded in an API document.
    api_sources = sorted(
        source
        for source in dataset.glob("*.catala_*")
        if source.name.split(".catala_", 1)[0].casefold() == "api"
    )
    mappings: list[dict[str, str]] = []
    for source in api_sources:
        relative = source.relative_to(dataset).as_posix()
        for requirement_id, scope, output in API_REQUIREMENT.findall(
            source.read_text(encoding="utf-8")
        ):
            mappings.append(
                {
                    "requirement_id": requirement_id,
                    "file": relative,
                    "scope": scope,
                    "output": output,
                }
            )
    if not mappings:
        return None
    identifiers = [entry["requirement_id"] for entry in mappings]
    if len(identifiers) != len(set(identifiers)):
        duplicates = sorted(
            {value for value in identifiers if identifiers.count(value) > 1}
        )
        raise RunnerError(f"duplicate API requirement contracts: {duplicates}")
    required = required_functionality_ids(dataset)
    by_id = {entry["requirement_id"]: entry for entry in mappings}
    if required:
        missing = sorted(set(required) - set(identifiers))
        extra = sorted(set(identifiers) - set(required))
        if missing or extra:
            raise RunnerError(
                f"API requirement contract mismatch (missing={missing}, extra={extra})"
            )
    else:
        required = identifiers
    return {
        "schema_version": 1,
        "requirements": [by_id[identifier] for identifier in required],
    }


def load_requirement_outputs(
    dataset: Path, *, require_resolved: bool
) -> dict[str, Any] | None:
    # Validate the agent-authored requirement-to-output mapping.
    path = dataset / REQUIREMENT_OUTPUTS_FILE
    identifiers = required_functionality_ids(dataset)
    if not path.is_file():
        api_contract = api_requirement_outputs(dataset)
        if api_contract is not None:
            return api_contract
        if identifiers:
            raise RunnerError(
                "dataset requirements have neither a protected Api.catala_* "
                f"contract nor {REQUIREMENT_OUTPUTS_FILE}"
            )
        return None
    value = load_json(path)
    if value.get("schema_version") != 1:
        raise RunnerError(f"{REQUIREMENT_OUTPUTS_FILE} must have schema_version 1")
    requirements = value.get("requirements")
    if not isinstance(requirements, list):
        raise RunnerError(f"{REQUIREMENT_OUTPUTS_FILE}.requirements must be a list")
    mapped: dict[str, dict[str, str]] = {}
    for index, entry in enumerate(requirements):
        if not isinstance(entry, dict) or set(entry) != {
            "requirement_id",
            "file",
            "scope",
            "output",
        }:
            raise RunnerError(
                f"{REQUIREMENT_OUTPUTS_FILE}.requirements[{index}] must contain only "
                "requirement_id, file, scope, and output"
            )
        if not all(isinstance(entry[key], str) for key in entry):
            raise RunnerError(
                f"{REQUIREMENT_OUTPUTS_FILE}.requirements[{index}] values must be strings"
            )
        identifier = entry["requirement_id"]
        if identifier in mapped:
            raise RunnerError(f"duplicate requirement mapping: {identifier}")
        if require_resolved and (
            not entry["file"].strip()
            or not entry["scope"].strip()
            or not entry["output"].strip()
        ):
            raise RunnerError(f"unresolved requirement mapping: {identifier}")
        mapped[identifier] = entry
    missing = sorted(set(identifiers) - mapped.keys())
    extra = sorted(mapped.keys() - set(identifiers))
    if missing or extra:
        raise RunnerError(
            f"requirement mapping mismatch (missing={missing}, extra={extra})"
        )
    return {
        "schema_version": 1,
        "requirements": [mapped[identifier] for identifier in identifiers],
    }


def _root_schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    node = schema
    reference = node.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/definitions/"):
        node = schema.get("definitions", {}).get(reference.rsplit("/", 1)[-1], {})
    properties = node.get("properties", {}) if isinstance(node, dict) else {}
    return properties if isinstance(properties, dict) else {}


def load_input_variable_descriptions(dataset: Path) -> dict[str, Any]:
    # Load the agent-authored natural-language contract for Catala inputs.
    path = dataset / INPUT_VARIABLE_DESCRIPTION_FILE
    if not path.is_file():
        raise RunnerError(f"dataset has no {INPUT_VARIABLE_DESCRIPTION_FILE}")
    value = load_json(path)
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "fields",
        "enums",
        "structs",
    }:
        raise RunnerError(
            f"{INPUT_VARIABLE_DESCRIPTION_FILE} must contain only schema_version, "
            "fields, enums, and structs"
        )
    if value.get("schema_version") != 3:
        raise RunnerError(
            f"{INPUT_VARIABLE_DESCRIPTION_FILE} must have schema_version 3"
        )
    fields = value["fields"]
    if not isinstance(fields, dict):
        raise RunnerError(f"{INPUT_VARIABLE_DESCRIPTION_FILE}.fields must be an object")
    for name, entry in fields.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(entry, dict)
            or set(entry) != {"scopes", "description"}
            or not isinstance(entry["scopes"], list)
            or not entry["scopes"]
            or len(entry["scopes"]) != len(set(entry["scopes"]))
            or not all(isinstance(scope, str) and scope for scope in entry["scopes"])
            or not isinstance(entry["description"], str)
            or not entry["description"].strip()
        ):
            raise RunnerError(
                f"{INPUT_VARIABLE_DESCRIPTION_FILE}.fields.{name} must contain "
                "unique non-empty scopes and a non-blank description"
            )
    for collection in ("enums", "structs"):
        entries = value[collection]
        if not isinstance(entries, dict) or not all(
            isinstance(name, str)
            and name
            and isinstance(description, str)
            and description.strip()
            for name, description in entries.items()
        ):
            raise RunnerError(
                f"{INPUT_VARIABLE_DESCRIPTION_FILE}.{collection} "
                "must map every non-empty name to a non-blank description"
            )
    return value


def _input_description_inventory(
    schema: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    # Return nested paths and reachable named enums and structs for one scope.
    definitions = schema.get("definitions", {})
    root_reference = schema.get("$ref", "")
    root_name = root_reference.rsplit("/", 1)[-1] if root_reference else None
    fields: set[str] = set()
    enums: set[str] = set()
    structs: set[str] = set()
    primitive_names = {
        "money",
        "decimal",
        "date",
        "duration",
        "unit",
        "integer",
        "boolean",
        "string",
        "number",
    }

    def walk(node: Any, path: str, seen: frozenset[str]) -> None:
        if not isinstance(node, dict):
            return
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            name = reference.rsplit("/", 1)[-1]
            if name != root_name and name not in primitive_names:
                definition = definitions.get(name, {})
                if isinstance(definition.get("enum"), list):
                    enums.add(name)
                elif isinstance(definition.get("properties"), dict):
                    structs.add(name)
            if name in seen:
                return
            walk(definitions.get(name, {}), path, seen | {name})
            return
        if node.get("type") == "array":
            walk(node.get("items", {}), path + "[]", seen)
            return
        properties = node.get("properties", {})
        if isinstance(properties, dict):
            for name, child in properties.items():
                child_path = f"{path}.{name}" if path else name
                fields.add(child_path)
                walk(child, child_path, seen)

    walk(schema, "", frozenset())
    return sorted(fields), sorted(enums), sorted(structs)


def validate_input_variable_descriptions(
    candidate: Path,
    candidate_format: dict[str, Any],
    requirement_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Require the description inventory to exactly match callable Catala inputs.
    value = load_input_variable_descriptions(candidate)
    selected_scope_ids = (
        {
            f"{entry['file']}::{entry['scope']}"
            for entry in requirement_outputs["requirements"]
        }
        if requirement_outputs is not None
        else None
    )
    expected: dict[str, tuple[list[str], list[str], list[str]]] = {}
    for scope in candidate_format.get("scopes", []):
        schema = scope.get("input_schema")
        if not isinstance(schema, dict) or not _root_schema_properties(schema):
            continue
        if str(scope.get("scope", "")).casefold().startswith("test"):
            continue
        scope_id = f"{scope['file']}::{scope['scope']}"
        if selected_scope_ids is not None and scope_id not in selected_scope_ids:
            continue
        expected[scope_id] = _input_description_inventory(schema)
    expected_global = {
        "fields": sorted(
            {name for inventory in expected.values() for name in inventory[0]}
        ),
        "enums": sorted(
            {name for inventory in expected.values() for name in inventory[1]}
        ),
        "structs": sorted(
            {name for inventory in expected.values() for name in inventory[2]}
        ),
    }
    for collection, names in expected_global.items():
        actual_names = sorted(value[collection])
        if actual_names != names:
            raise RunnerError(
                f"stale global {collection} descriptions "
                f"(missing={sorted(set(names) - set(actual_names))}, "
                f"extra={sorted(set(actual_names) - set(names))})"
            )
    expected_field_scopes: dict[str, set[str]] = {}
    for scope_id, (fields, _, _) in expected.items():
        for name in fields:
            expected_field_scopes.setdefault(name, set()).add(scope_id)
    for name, scopes in expected_field_scopes.items():
        actual_scopes = set(value["fields"][name]["scopes"])
        if actual_scopes != scopes:
            raise RunnerError(
                f"stale scope references for field {name} "
                f"(missing={sorted(scopes - actual_scopes)}, "
                f"extra={sorted(actual_scopes - scopes)})"
            )
    return value


def validate_requirement_scope_outputs(
    candidate: Path, candidate_format: dict[str, Any]
) -> dict[str, Any] | None:
    # Resolve every declared requirement mapping against extracted Catala schemas.
    mapping = load_requirement_outputs(candidate, require_resolved=True)
    if mapping is None:
        return None
    by_location = {
        (str(scope.get("file", "")), str(scope.get("scope", ""))): scope
        for scope in candidate_format.get("scopes", [])
    }
    resolved = []
    for entry in mapping["requirements"]:
        location = (entry["file"], entry["scope"])
        scope = by_location.get(location)
        if scope is None:
            raise RunnerError(
                f"requirement {entry['requirement_id']} maps to missing scope "
                f"{entry['file']}::{entry['scope']}"
            )
        output_schema = scope.get("output_schema")
        if not isinstance(output_schema, dict):
            raise RunnerError(
                f"requirement {entry['requirement_id']} scope {entry['scope']!r} "
                "has no JSON-callable output schema"
            )
        properties = _root_schema_properties(output_schema)
        if entry["output"] not in properties:
            raise RunnerError(
                f"requirement {entry['requirement_id']} maps to missing output "
                f"{entry['scope']}.{entry['output']}"
            )
        resolved.append(
            {
                **entry,
                "output_schema": properties[entry["output"]],
            }
        )
    return {"schema_version": 1, "requirements": resolved}


def validate_workspace(input_directory: Path, workspace: Path) -> dict[str, Any]:
    # Validate protected inputs and reject insubstantial Catala submissions.
    from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair

    baseline_files = relative_files(input_directory)
    workspace_files = relative_files(workspace)
    # The live workspace and its immutable iteration snapshot both contain runner-managed repair inputs.
    for name in repair.checked_artifacts(workspace, input_directory.parent):
        workspace_files.pop(name, None)
    if baseline_files.keys() != workspace_files.keys():
        added = sorted(workspace_files.keys() - baseline_files.keys())
        removed = sorted(baseline_files.keys() - workspace_files.keys())
        raise RunnerError(
            f"agent changed the file set (added={added}, removed={removed})"
        )

    load_requirement_outputs(workspace, require_resolved=True)
    changed_blocks = 0
    nonempty_blocks = 0
    total_blocks = 0
    documents = 0
    candidate_blocks: dict[str, tuple[bytes, ...]] = {}
    file_hashes: dict[str, str] = {}
    for relative, baseline_path in baseline_files.items():
        candidate_path = workspace_files[relative]
        if baseline_path.suffix.startswith(".catala_"):
            baseline = parse_fenced_document(baseline_path)
            candidate = parse_fenced_document(candidate_path)
            if normalize_protected_whitespace(
                baseline.skeleton
            ) != normalize_protected_whitespace(candidate.skeleton):
                raise RunnerError(
                    f"agent changed statute prose, RTDF annotations, or fences in {relative}"
                )
            if len(baseline.blocks) != len(candidate.blocks):
                raise RunnerError(f"agent changed the Catala fence count in {relative}")
            documents += 1
            total_blocks += len(candidate.blocks)
            changed_blocks += sum(
                left != right for left, right in zip(baseline.blocks, candidate.blocks)
            )
            nonempty_blocks += sum(bool(block.strip()) for block in candidate.blocks)
            candidate_blocks[relative] = candidate.blocks
        elif relative == REQUIREMENT_OUTPUTS_FILE:
            pass
        elif relative == INPUT_VARIABLE_DESCRIPTION_FILE:
            load_input_variable_descriptions(workspace)
        elif baseline_path.read_bytes() != candidate_path.read_bytes():
            raise RunnerError(f"agent changed non-Catala input {relative}")
        file_hashes[relative] = sha256_file(candidate_path)

    if documents == 0:
        raise RunnerError("the dataset contains no .catala_* documents")
    if total_blocks == 0:
        raise RunnerError("the dataset contains no Catala fences")
    if changed_blocks == 0:
        raise RunnerError("the agent did not change any Catala fence body")
    # The integrity gate checks whether the statutory fences contain meaningful Catala.
    valid_code_blocks = sum(
        valid_catala_block(block)
        for blocks in candidate_blocks.values()
        for block in blocks
    )
    minimum_valid_blocks = math.ceil(total_blocks * MIN_VALID_CATALA_BLOCK_RATIO)
    if valid_code_blocks < minimum_valid_blocks:
        raise RunnerError("translation not happening for all provisions")
    return {
        "documents": documents,
        "changed_blocks": changed_blocks,
        "nonempty_blocks": nonempty_blocks,
        "total_blocks": total_blocks,
        "valid_code_blocks": valid_code_blocks,
        "files": file_hashes,
    }


def integrity_manifest_matches(
    recorded: dict[str, Any] | None, current: dict[str, Any]
) -> bool:
    # Compare integrity data while accepting manifests from before the code gate.
    if recorded == current:
        return True
    legacy_current = {
        key: value
        for key, value in current.items()
        if key not in {"total_blocks", "valid_code_blocks"}
    }
    return recorded == legacy_current


def workspace_fence_progress(input_directory: Path, workspace: Path) -> dict[str, int]:
    # Count live Catala fence bodies without enforcing final-run integrity.
    total = filled = changed = valid = 0
    for relative, baseline_path in relative_files(input_directory).items():
        if not baseline_path.suffix.startswith(".catala_"):
            continue
        candidate_path = workspace / relative
        baseline = parse_fenced_document(baseline_path)
        total += len(baseline.blocks)
        if not candidate_path.is_file():
            continue
        candidate = parse_fenced_document(candidate_path)
        filled += sum(bool(block.strip()) for block in candidate.blocks)
        valid += sum(valid_catala_block(block) for block in candidate.blocks)
        changed += sum(
            left != right for left, right in zip(baseline.blocks, candidate.blocks)
        )
    return {"filled": filled, "valid": valid, "changed": changed, "total": total}
