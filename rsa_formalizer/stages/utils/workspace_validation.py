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
RSA_BLOCK_ID = re.compile(rb"<!--[ \t]*rsa-block-id:[ \t]*([^;>]+)[ \t]*;")
MODULE_DECLARATION = re.compile(
    r"(?m)^[ \t]*>[ \t]*Module[ \t]+([^\s]+)[ \t]*$"
)
CATALA_IMPORT = re.compile(
    rb">[ \t]*Using[ \t]+[A-Za-z_][A-Za-z_0-9]*[ \t]+as[ \t]+"
    rb"[A-Za-z_][A-Za-z_0-9]*[ \t]*"
)
DECLARATION_SYMBOL = re.compile(
    r"^[ \t]*(?:#[^\n]*\n[ \t]*)*(?:declaration|déclaration)[ \t]+"
    r"(?:(?:scope|structure|enumeration|champ[ \t]+d'application|"
    r"énumération)[ \t]+)?([^\W\d]\w*)",
    re.MULTILINE,
)


def valid_catala_block(block: bytes) -> bool:
    # Require at least two nonblank, non-comment lines of Catala.
    code_lines = sum(
        1
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith(b"#")
    )
    return code_lines >= MIN_VALID_CATALA_BLOCK_LINES


def catala_block_symbols(block: bytes) -> tuple[set[str], set[tuple[str, str]]]:
    # Return declared symbols and scope variables defined by one fence body.
    text = block.decode("utf-8", errors="replace")
    declared = set(DECLARATION_SYMBOL.findall(text))
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


def _module_name(source: Path) -> str | None:
    match = MODULE_DECLARATION.search(
        source.read_text(encoding="utf-8", errors="replace")
    )
    return match.group(1) if match else None


def _skeleton_without_added_imports(baseline: bytes, candidate: bytes) -> bytes:
    """Permit new Catala module imports in the header, preserving all law text."""
    header = baseline.split(b"```catala", 1)[0]
    original = {line.strip() for line in header.splitlines()
                if CATALA_IMPORT.fullmatch(line.strip())}
    lines = candidate.splitlines(keepends=True)
    before_fence = True
    retained = []
    for line in lines:
        if before_fence and line.startswith(b"```catala"):
            before_fence = False
        if (before_fence and CATALA_IMPORT.fullmatch(line.strip())
                and line.strip() not in original):
            continue
        retained.append(line)
    return b"".join(retained)


def _qualified_symbol_matches_module(
    qualified: str,
    module: str | None,
    symbol: str,
    *,
    allow_unqualified: bool = False,
) -> bool:
    """Whether a whole-program graph symbol belongs to one source module."""
    parts = qualified.split(".")
    if not parts or parts[-1] != symbol:
        return False
    return (allow_unqualified and qualified == symbol) or (
        module is not None and module in parts[:-1]
    )


def _named_dependency_edges(payload: Any) -> dict[str, set[str]]:
    """Decode one named graph payload as dependent-to-dependencies."""
    if not isinstance(payload, dict):
        return {}
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
    return dependencies


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
    with tempfile.TemporaryDirectory(prefix="rsa-dependency-check-") as temporary_name:
        temporary = Path(temporary_name) / "project"
        copy_project(workspace, temporary)
        write_verification_clerk_config(temporary)
        run_checked(
            [clerk, "start", "--color=never"],
            cwd=temporary,
            environment=environment,
            timeout=300,
        )
        graph_by_owner: dict[Path, dict[str, Any]] = {}

        def dependency_graph(owner: Path) -> dict[str, Any]:
            cached = graph_by_owner.get(owner)
            if cached is not None:
                return cached
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
            graph_by_owner[owner] = graph
            return graph

        # First compute whole-program reachability from every contracted output.
        # The graph uses module-qualified names for imported scopes and helpers.
        reachable_symbols: set[str] = set()
        selected_graph_by_owner: dict[Path, dict[str, set[str]]] = {}
        for owner, selected in selected_by_owner.items():
            graph = dependency_graph(owner)
            intra, inter = _dependency_graph_edges(graph)
            graph_scopes = set(inter)
            graph_scopes.update(key.split("\0", 1)[0] for key in intra)
            selected_graph: dict[str, set[str]] = {}
            for scope, outputs in selected.items():
                graph_scope = _matching_graph_scope(scope, graph_scopes)
                if graph_scope is None:
                    raise RunnerError(
                        f"mapped scope is absent or ambiguous in dependency graph: "
                        f"{owner.relative_to(workspace).as_posix()}::{scope}"
                    )
                selected_graph.setdefault(graph_scope, set()).update(outputs)

            reachable_scopes = _dependency_closure(inter, set(selected_graph))
            reachable_symbols.update(reachable_scopes)
            reachable_symbols.update(
                _dependency_closure(
                    _named_dependency_edges(graph.get("types", {})),
                    reachable_scopes,
                )
            )
            selected_graph_by_owner[owner] = selected_graph

            # Validate the contracted outputs against the root compilation unit.
            for graph_scope, targets in selected_graph.items():
                qualified_targets = {f"{graph_scope}\0{target}" for target in targets}
                existing_targets = qualified_targets & set(intra)
                if existing_targets != qualified_targets:
                    missing = sorted(
                        target.split("\0", 1)[1]
                        for target in qualified_targets - existing_targets
                    )
                    raise RunnerError(
                        f"mapped outputs are absent from dependency graph for "
                        f"{owner.relative_to(workspace).as_posix()}::"
                        f"{graph_scope.rsplit('.', 1)[-1]}: {missing}"
                    )

        # Catala emits intra-scope edges only for scopes authored by the file
        # passed to `dependency-graph`, even with --whole-program. Compile each
        # imported module separately, then attribute its local graph back to it.
        for owner in sorted(set(owner_by_file.values())):
            graph = dependency_graph(owner)
            intra, _ = _dependency_graph_edges(graph)
            module = _module_name(owner)
            authored_outputs = outputs_by_owner.get(owner, {})
            live_variables: set[tuple[str, str]] = set()
            live_symbols = {
                symbol.rsplit(".", 1)[-1]
                for symbol in reachable_symbols
                if _qualified_symbol_matches_module(
                    symbol,
                    module,
                    symbol.rsplit(".", 1)[-1],
                    allow_unqualified=owner in selected_by_owner,
                )
            }
            local_scopes = {key.split("\0", 1)[0] for key in intra}
            selected_graph = selected_graph_by_owner.get(owner, {})
            for local_scope in local_scopes:
                if not any(
                    _qualified_symbol_matches_module(
                        symbol,
                        module,
                        local_scope,
                        allow_unqualified=owner in selected_by_owner,
                    )
                    for symbol in reachable_symbols
                ):
                    continue
                targets = None
                for selected_scope, selected_targets in selected_graph.items():
                    if selected_scope.rsplit(".", 1)[-1] == local_scope:
                        targets = selected_targets
                        break
                if targets is None:
                    targets = authored_outputs.get(local_scope, set())
                qualified_targets = {f"{local_scope}\0{target}" for target in targets}
                existing_targets = qualified_targets & set(intra)
                live = _dependency_closure(intra, existing_targets)
                if existing_targets:
                    live_symbols.add(local_scope)
                live_variables.update(
                    (local_scope, item.split("\0", 1)[1])
                    for item in live
                    if item.startswith(f"{local_scope}\0")
                )
            live_by_owner[owner] = (live_symbols, live_variables)

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
    if declared & live_scopes or definitions & live_variables:
        return True
    # Catala's graph names stateful variables as `variable@state`, while the
    # authored definition line contains only the base variable name.
    if any(
        live_scope == scope and live_variable.startswith(f"{variable}@")
        for scope, variable in definitions
        for live_scope, live_variable in live_variables
    ):
        return True
    # Assertions have compiler-generated node names, so associate an
    # assertion-only fence with its reachable containing scope.
    text = block.decode("utf-8", errors="replace")
    block_scopes = set(SCOPE_DEFINITION_START.findall(text))
    has_assertion = bool(re.search(r"(?m)^[ \t]*assertion[ \t]+", text))
    return has_assertion and bool(block_scopes & live_scopes)


def catala_block_ids(source: Path) -> tuple[str, ...]:
    # Return each Catala fence's preceding RSA block ID in source order.
    identifiers: list[str] = []
    pending: str | None = None
    for line in source.read_bytes().splitlines(keepends=True):
        match = RSA_BLOCK_ID.search(line)
        if match:
            pending = match.group(1).decode("utf-8", errors="replace").strip()
        if FENCE_START.fullmatch(line.decode("utf-8", errors="surrogateescape")):
            identifiers.append(pending or f"unidentified-fence-{len(identifiers) + 1}")
            pending = None
    return tuple(identifiers)


def unreachable_catala_blocks(
    workspace: Path, requirement_outputs: dict[str, Any]
) -> list[str]:
    # List RSA blocks outside the union of mapped-output dependencies.
    live = dependency_live_definitions(workspace, requirement_outputs)
    unreachable: list[str] = []
    for source in catala_sources(workspace):
        relative = source.relative_to(workspace).as_posix()
        blocks = parse_fenced_document(source).blocks
        identifiers = catala_block_ids(source)
        if len(identifiers) != len(blocks):
            raise RunnerError(
                f"could not associate RSA block IDs with fences in {relative}"
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
    baseline_files = relative_files(input_directory)
    workspace_files = relative_files(workspace)
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
    fixed_definitions = any(
        (input_directory / f"{name}.md").is_file()
        for name in ("airline", "sara")
    )
    for relative, baseline_path in baseline_files.items():
        candidate_path = workspace_files[relative]
        if (
            fixed_definitions
            and relative.startswith(("Definition.catala_", "Definitions.catala_"))
            and baseline_path.read_bytes() != candidate_path.read_bytes()
        ):
            raise RunnerError(f"agent changed fixed shared input {relative}")
        if baseline_path.suffix.startswith(".catala_"):
            baseline = parse_fenced_document(baseline_path)
            candidate = parse_fenced_document(candidate_path)
            if normalize_protected_whitespace(
                baseline.skeleton
            ) != normalize_protected_whitespace(
                _skeleton_without_added_imports(baseline.skeleton, candidate.skeleton)
            ):
                raise RunnerError(
                    f"agent changed statute prose, RSA annotations, or fences in {relative}"
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
