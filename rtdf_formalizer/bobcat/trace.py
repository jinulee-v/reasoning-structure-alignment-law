"""Shared schemas, execution-tree slicing, and statute mapping."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from bobcat_scripts.bobcatlib import run as bobcat_run
from rtdf_formalizer.stages import utils as exp

DEFAULTS = {
    "bobcat_timeout_seconds": 1800,
    "bobcat_positive_hundred_money_inputs": False,
    "bobcat_max_list_length": None,
    "bobcat_representation_capacity": bobcat_run.DEFAULT_REPRESENTATION_CAPACITY,
    "bobcat_solver_timeout_ms": None,
    "bobcat_solver_timeout_max_ms": None,
    "bobcat_objective_timeout_ms": None,
    "statute_source": "gold",
}
_SITE = re.compile(r"@([^@:=>/]+\.catala_[A-Za-z]+):(\d+):")
_BLOCK_DETAILS = re.compile(r"<!-- rtdf-block-id: ([^;]+);[^>]*provision-id: ([^;]+);")
_DOCUMENT_ID = re.compile(r"<!--\s*rtdf-document-id:\s*([^\s>]+)\s*-->")
_HTML_COMMENT = re.compile(r"<!--[\s\S]*?-->")
_FENCE = re.compile(r"^```(?:catala[^\n]*)?$", re.MULTILINE)
_ANSWER_BLOCK = re.compile(r"<answer>\s*([\s\S]*?)\s*</answer>", re.IGNORECASE)
DYNAMIC_SLICE_SCHEMA_VERSION = 12
DYNAMIC_SLICE_DEPENDENCY_SEMANTICS = (
    "runtime_reads_branch_outcomes_call_returns_scope_inputs_v5"
)
DYNAMIC_SLICE_METHOD = "runtime_definition_dependency_closure"
REQUIREMENT_DESCRIPTIONS_FILE = "REQUIREMENT_DESCRIPTIONS.json"

_LABELED_PROVISION = re.compile(r"^\[([^\]\n]+)\]", re.MULTILINE)
REASONING_RESULT_FORMAT = "reasoning_with_json_answer_and_execution_tree"


def effective_options(config: dict[str, Any]) -> dict[str, Any]:
    options = {
        **DEFAULTS,
        **config.get("reasoning_trace_diff_fuzzing", config.get("post_validation", {})),
    }
    if options["statute_source"] != "gold":
        raise exp.RunnerError("only gold statute context is implemented")
    options.pop("output_format", None)
    if int(options["bobcat_timeout_seconds"]) <= 0:
        raise exp.RunnerError("BOBCat timeout must be positive")
    if (
        options["bobcat_max_list_length"] is not None
        and int(options["bobcat_max_list_length"]) < 0
    ):
        raise exp.RunnerError("BOBCat maximum list length must be nonnegative")
    if int(options["bobcat_representation_capacity"]) < max(
        1, int(options["bobcat_max_list_length"] or 0)
    ):
        raise exp.RunnerError(
            "BOBCat representation capacity must cover the input-list bound"
        )
    for key in (
        "bobcat_solver_timeout_ms",
        "bobcat_solver_timeout_max_ms",
        "bobcat_objective_timeout_ms",
    ):
        if options[key] is not None and int(options[key]) <= 0:
            raise exp.RunnerError(f"{key} must be positive")
    if (
        options["bobcat_solver_timeout_ms"] is not None
        and options["bobcat_solver_timeout_max_ms"] is not None
        and int(options["bobcat_solver_timeout_max_ms"])
        < int(options["bobcat_solver_timeout_ms"])
    ):
        raise exp.RunnerError(
            "BOBCat maximum solver timeout must cover its initial timeout"
        )
    return options


def backfill_options(run_directory: Path, config: dict[str, Any]) -> dict[str, Any]:
    # Persist newly introduced options for old and new runs alike.
    options = effective_options(config)
    changed = (
        config.get("reasoning_trace_diff_fuzzing") != options
        or "post_validation" in config
    )
    if "provider" not in config.get("reasoning_trace", {}):
        config["reasoning_trace"]["provider"] = config.get("agent", {}).get(
            "provider", "openai"
        )
        changed = True
    if changed:
        config["reasoning_trace_diff_fuzzing"] = options
        config.pop("post_validation", None)
        exp.atomic_json(run_directory / "config.json", config)
    return options


def scope_records(formats: dict[str, Any]) -> list[dict[str, Any]]:
    return list(formats["scopes"])


def _root_object_properties(schema: Any) -> dict[str, Any] | None:
    # Return the fields of a root object schema, following local references.
    if not isinstance(schema, dict):
        return None
    root = schema
    node: Any = schema
    visited: set[str] = set()
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        reference = node["$ref"]
        if not reference.startswith("#/") or reference in visited:
            return None
        visited.add(reference)
        node = root
        for component in reference[2:].split("/"):
            if not isinstance(node, dict):
                return None
            component = component.replace("~1", "/").replace("~0", "~")
            node = node.get(component)
    if not isinstance(node, dict) or node.get("type") != "object":
        return None
    properties = node.get("properties", {})
    return properties if isinstance(properties, dict) else None


def scope_has_nonempty_input_and_output(scope: dict[str, Any]) -> bool:
    # Whether a scope represents a testable mapping between nonempty records.
    return bool(_root_object_properties(scope.get("input_schema"))) and bool(
        _root_object_properties(scope.get("output_schema"))
    )


def schema_scopes(formats: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        scope
        for scope in scope_records(formats)
        if scope_has_nonempty_input_and_output(scope)
    ]


def requirement_descriptions(snapshot: Path) -> dict[str, str]:
    # Load optional structured task descriptions used in reasoning prompts.
    path = snapshot / REQUIREMENT_DESCRIPTIONS_FILE
    if not path.is_file():
        return {}
    value = exp.load_json(path)
    if value.get("schema_version") != 1 or not isinstance(
        value.get("requirements"), list
    ):
        raise exp.RunnerError(f"invalid {REQUIREMENT_DESCRIPTIONS_FILE}")
    descriptions: dict[str, str] = {}
    for index, entry in enumerate(value["requirements"]):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"requirement_id", "description"}
            or not all(
                isinstance(entry[key], str) and entry[key].strip() for key in entry
            )
        ):
            raise exp.RunnerError(
                f"invalid {REQUIREMENT_DESCRIPTIONS_FILE}.requirements[{index}]"
            )
        if entry["requirement_id"] in descriptions:
            raise exp.RunnerError(
                f"duplicate requirement description: {entry['requirement_id']}"
            )
        descriptions[entry["requirement_id"]] = entry["description"].strip()
    return descriptions


def scope_statute_anchor(snapshot: Path, source: str, scope: str) -> str:
    # Find the broadest provision containing this scope's executable definitions.
    path = snapshot / source
    if not path.is_file():
        raise exp.RunnerError(f"scope source is missing: {path}")
    source_text = path.read_text(encoding="utf-8")
    document_match = _DOCUMENT_ID.search(source_text)
    document_id = (
        document_match.group(1) if document_match else source.rsplit(".catala_", 1)[0]
    )
    heading = re.compile(
        r"^\s*(?:declaration\s+)?scope\s+" + re.escape(scope) + r"\s*:"
    )
    marker = None
    in_code = False
    provisions = []
    for line in source_text.splitlines():
        found = _BLOCK_DETAILS.search(line)
        if found:
            marker = found.group(2)
        if line.startswith("```catala"):
            in_code = True
        elif line == "```":
            in_code = False
        elif in_code and marker and marker != "none" and heading.match(line):
            if marker not in provisions:
                provisions.append(marker)
    if not provisions:
        return document_id
    # Hierarchical IDs such as section1(a)(i) have an identifiable parent.
    for candidate in provisions:
        parent = candidate.removesuffix(":flush")
        if all(
            other == candidate
            or other.startswith(parent + "(")
            or other.startswith(parent + ":")
            for other in provisions
        ):
            return parent
    # A scope implemented across sibling or otherwise unrelated provisions is governed by the source document.
    if not document_match:
        inferred_documents = {
            re.split(r"[(:]", provision, maxsplit=1)[0] for provision in provisions
        }
        if len(inferred_documents) == 1:
            return next(iter(inferred_documents))
    return document_id


def target_name(source: str, scope: str, output: str | None = None) -> str:
    identity = f"{source}:{scope}" + (f":{output}" if output else "")
    label = f"{Path(source).stem}_{scope}" + (f"_{output}" if output else "")
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", label)
    digest = hashlib.sha256(identity.encode()).hexdigest()[:10]
    return f"{safe.strip('_') or 'scope'}_{digest}"


def first_statute_visits(statute_ids: list[str]) -> list[str]:
    # Keep each provision once, at its first concrete or reported visit.
    return list(dict.fromkeys(statute_ids))


def provision_ids_overlap(left: str, right: str) -> bool:
    # Return whether two IDs denote the same or nested statutory text.
    left_local = left.rsplit("/", 1)[-1]
    right_local = right.rsplit("/", 1)[-1]
    if left_local == right_local:
        return True

    def is_ancestor(ancestor: str, descendant: str) -> bool:
        if not descendant.startswith(ancestor):
            return False
        suffix = descendant[len(ancestor) :]
        return suffix.startswith("(") or suffix.startswith(":")

    return is_ancestor(left_local, right_local) or is_ancestor(right_local, left_local)


def compare_provision_ids(catala_ids: list[str], llm_ids: list[str]) -> dict[str, Any]:
    # Compare most-specific visits while accepting ancestor refinement.
    def frontier(values: list[str]) -> list[str]:
        unique = first_statute_visits(values)
        return [
            provision
            for provision in unique
            if not any(
                other != provision
                and provision_ids_overlap(provision, other)
                and len(other.rsplit("/", 1)[-1]) > len(provision.rsplit("/", 1)[-1])
                for other in unique
            )
        ]

    catala = frontier(catala_ids)
    llm = frontier(llm_ids)
    overlaps = [
        {"catala": catala_id, "llm": llm_id}
        for catala_id in catala
        for llm_id in llm
        if provision_ids_overlap(catala_id, llm_id)
    ]
    return {
        "overlaps": overlaps,
        "catala_only": [
            provision
            for provision in catala
            if not any(provision_ids_overlap(provision, other) for other in llm)
        ],
        "llm_only": [
            provision
            for provision in llm
            if not any(provision_ids_overlap(provision, other) for other in catala)
        ],
    }


def _execution_node_key(node: dict[str, Any]) -> str:
    # Identity of one executed construct below a single tree parent.
    stable = {key: node.get(key) for key in ("kind", "name", "pos", "io")}
    return json.dumps(stable, ensure_ascii=False, sort_keys=True)


def _merge_execution_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Make repeated list-function visits explicit without creating a graph.
    merged: list[dict[str, Any]] = []
    indexes: dict[str, int] = {}
    for original in nodes:
        node = {**original}
        node["children"] = _merge_execution_nodes(list(node.get("children", [])))
        key = _execution_node_key(node)
        if key not in indexes:
            indexes[key] = len(merged)
            node["occurrences"] = int(node.get("occurrences", 1))
            merged.append(node)
            continue
        former = merged[indexes[key]]
        former["occurrences"] = int(former.get("occurrences", 1)) + int(
            node.get("occurrences", 1)
        )
        former["children"] = _merge_execution_nodes(
            [*former.get("children", []), *node.get("children", [])]
        )
        values = former.setdefault("observed_values", [])
        for value in (former.get("value"), node.get("value")):
            if value is not None and value not in values:
                values.append(value)
        former.pop("value", None)
    return merged


def execution_tree(
    events: list[dict[str, Any]], *, deduplicate: bool = True
) -> list[dict[str, Any]]:
    # Turn Catala's raw begin/end stream into a deduplicated call tree.
    roots: list[dict[str, Any]] = []
    stack: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []

    def children() -> list[dict[str, Any]]:
        return stack[-1][1] if stack else roots

    for event in events:
        kind = event.get("event")
        if kind == "BeginCall":
            node = {"kind": "call", "name": event.get("name"), "children": []}
            children().append(node)
            stack.append((node, node["children"]))
        elif kind == "EndCall":
            if stack:
                stack.pop()
        elif kind == "VariableDefinition":
            variable = {
                "kind": "variable",
                "name": event.get("name"),
                "io": event.get("io"),
                "value": event.get("value"),
                "children": [],
            }
            if isinstance(event.get("definition_id"), int):
                variable["definition_id"] = event["definition_id"]
                variable["reads"] = event.get("reads")
            children().append(variable)
        elif kind == "DecisionTaken":
            children().append(
                {"kind": "decision", "pos": event.get("pos"), "children": []}
            )
        elif kind == "BranchTaken":
            children().append(
                {
                    "kind": "branch",
                    "pos": event.get("pos"),
                    "outcome": event.get("outcome"),
                    "children": [],
                }
            )
    return _merge_execution_nodes(roots) if deduplicate else roots


def dependency_edges(payload: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    # Decode Catala's dependency graph as dependent -> direct dependencies.
    result: dict[str, dict[str, set[str]]] = {}
    intra = payload.get("intra_scopes", {})
    if not isinstance(intra, dict):
        return result
    for scope, graph in intra.items():
        if not isinstance(graph, dict):
            continue
        nodes = graph.get("nodes", {})
        names = {str(identifier): str(name) for identifier, name in nodes.items()}
        dependencies = {name: set() for name in names.values()}
        for edge in graph.get("edges", []):
            if not isinstance(edge, dict):
                continue
            source = names.get(str(edge.get("from")))
            target = names.get(str(edge.get("to")))
            if source is not None and target is not None:
                dependencies.setdefault(target, set()).add(source)
        result[str(scope)] = dependencies
    return result


def slice_execution_tree(
    tree: list[dict[str, Any]],
    entry_scope: str,
    output: str | None,
    graphs: dict[str, dict[str, set[str]]] | None = None,
) -> list[dict[str, Any]]:
    # Least runtime-definition dependency closure of the entry output record.
    definitions: dict[int, dict[str, Any]] = {}
    targets: list[int] = []

    def index(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if node.get("occurrences", 1) != 1:
                raise ValueError("merged runtime occurrences; use unmerged execution")
            if node.get("kind") == "variable":
                identifier = node.get("definition_id")
                if type(identifier) is not int or not isinstance(
                    node.get("reads"), list
                ):
                    raise ValueError(
                        "runtime dependency metadata missing; replay required"
                    )
                if identifier in definitions:
                    raise ValueError(
                        "duplicate runtime definition ID; use unmerged execution"
                    )
                definitions[identifier] = node
                io = node.get("io")
                is_entry_output = (
                    node.get("name", "").startswith(f"{entry_scope}.")
                    and isinstance(io, dict)
                    and io.get("io_output") is True
                )
                if (output and node.get("name") == f"{entry_scope}.{output}") or (
                    not output and is_entry_output
                ):
                    targets.append(identifier)
            index(node.get("children", []))

    index(tree)
    if not targets or (output and len(targets) != 1):
        expected = (
            f"one entry output {entry_scope}.{output}"
            if output
            else (f"one or more output fields of entry scope {entry_scope}")
        )
        raise ValueError(f"expected {expected}, found {len(targets)} occurrences")
    live = set(targets)
    pending = list(targets)
    while pending:
        identifier = pending.pop()
        for read in definitions[identifier]["reads"]:
            if not isinstance(read, dict) or type(read.get("definition_id")) is not int:
                raise ValueError(f"invalid runtime read for {identifier}: {read!r}")
            dependency = read.get("definition_id")
            if dependency not in definitions or dependency >= identifier:
                raise ValueError(
                    f"invalid reaching definition {dependency} for {identifier}"
                )
            if dependency not in live:
                live.add(dependency)
                pending.append(dependency)

    def prune(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for offset, node in enumerate(nodes):
            kind = node.get("kind")
            if kind in {"decision", "branch", "call"}:
                pending.append(node)
            elif kind == "variable":
                if node["definition_id"] in live:
                    # Calls and decisions occur while the following definition is being evaluated: runtime logs the definition only after…
                    for candidate in pending:
                        if candidate.get("kind") == "call":
                            selected.append(
                                {
                                    **candidate,
                                    "children": prune(candidate.get("children", [])),
                                }
                            )
                        else:
                            selected.append(candidate)
                    selected.append(node)
                else:
                    # A nested scope can contain a definition reached through an explicit runtime dependency even when its enclosing caller…
                    for candidate in pending:
                        if candidate.get("kind") != "call":
                            continue
                        children = prune(candidate.get("children", []))
                        if children:
                            selected.append({**candidate, "children": children})
                pending = []
        # Root/enclosing calls are not owned by a following sibling variable.
        for candidate in pending:
            if candidate.get("kind") != "call":
                continue
            children = prune(candidate.get("children", []))
            if children:
                selected.append({**candidate, "children": children})
        return selected

    return prune(tree)


def execution_tree_events(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Preorder compatibility view used only by the provision mapper.
    events: list[dict[str, Any]] = []
    for node in tree:
        kind = node.get("kind")
        if kind == "call":
            events.append({"event": "BeginCall", "name": node.get("name")})
            events.extend(execution_tree_events(node.get("children", [])))
            events.append({"event": "EndCall", "name": node.get("name")})
        elif kind == "variable":
            events.append(
                {
                    "event": "VariableDefinition",
                    "name": node.get("name"),
                    "io": node.get("io"),
                    "value": node.get("value"),
                }
            )
        elif kind == "decision":
            events.append({"event": "DecisionTaken", "pos": node.get("pos")})
        elif kind == "branch":
            events.append(
                {
                    "event": "BranchTaken",
                    "pos": node.get("pos"),
                    "outcome": node.get("outcome"),
                }
            )
    return events


def _source_span(snapshot: Path, position: Any) -> str | None:
    if not isinstance(position, dict):
        return None
    filename = position.get("filename")
    start_line = position.get("start_line")
    end_line = position.get("end_line")
    if not isinstance(filename, str) or not isinstance(start_line, int):
        return None
    source = snapshot / Path(filename).name
    if not source.is_file():
        return None
    lines = source.read_text(encoding="utf-8").splitlines()
    end_line = end_line if isinstance(end_line, int) else start_line
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        return None
    selected = lines[start_line - 1 : end_line]
    start_column = position.get("start_column")
    end_column = position.get("end_column")
    if isinstance(end_column, int) and selected:
        selected[-1] = selected[-1][: max(0, end_column - 1)]
    if isinstance(start_column, int) and selected:
        selected[0] = selected[0][max(0, start_column - 1) :]
    text = " ".join(line.strip() for line in selected).strip()
    return re.sub(r"\s+", " ", text) or None


def causal_execution_trace(
    snapshot: Path, tree: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    # Flatten a sliced execution and attach direct and inherited branch guards.
    nodes: list[dict[str, Any]] = []

    def guard(branch: dict[str, Any], relation: str) -> dict[str, Any]:
        position = branch.get("pos") or {}
        filename = position.get("filename")
        line = position.get("start_line")
        outcome = branch.get("outcome")
        return {
            "condition": _source_span(snapshot, position),
            "outcome": outcome,
            "selected_arm": (
                "then" if outcome is True else "else" if outcome is False else None
            ),
            "source": (
                f"{Path(filename).name}:{line}"
                if isinstance(filename, str) and isinstance(line, int)
                else None
            ),
            "relation": relation,
        }

    def visit(items: list[dict[str, Any]]) -> None:
        pending: list[dict[str, Any]] = []
        for item in items:
            if item.get("kind") == "branch":
                pending.append(guard(item, "direct"))
            if item.get("kind") == "variable":
                nodes.append(
                    {
                        "id": item.get("definition_id"),
                        "concept": item.get("name"),
                        "value": item.get("value"),
                        "depends_on": [
                            read.get("definition_id")
                            for read in item.get("reads", [])
                            if isinstance(read, dict)
                        ],
                        "branch_guards": list(pending),
                    }
                )
                pending.clear()
            visit(item.get("children", []))

    visit(tree)
    by_id = {
        node["id"]: node for node in nodes if isinstance(node.get("id"), int)
    }
    for node in nodes:
        inherited = []
        for dependency in node["depends_on"]:
            for original in by_id.get(dependency, {}).get("branch_guards", []):
                candidate = {**original, "relation": "inherited"}
                identity = {k: v for k, v in candidate.items() if k != "relation"}
                existing = [*node["branch_guards"], *inherited]
                if not any(
                    {k: v for k, v in former.items() if k != "relation"}
                    == identity
                    for former in existing
                ):
                    inherited.append(candidate)
        node["branch_guards"].extend(inherited)
    return nodes


def execution_tree_size(tree: list[dict[str, Any]]) -> int:
    # Count concrete nodes in an execution tree.
    return sum(1 + execution_tree_size(node.get("children", [])) for node in tree)


def persist_execution_forests(root: Path, results: list[dict[str, Any]]) -> None:
    # Store full coverage and dependency-sliced execution-tree forests.
    for field, filename in (
        ("execution_tree", "execution_tree.json"),
        ("dynamic_slice_tree", "dynamic_slice_tree.json"),
    ):
        nodes = [
            {**node, "case_id": result.get("id")}
            for result in results
            for node in result.get(field, [])
        ]
        exp.atomic_json(
            root / filename,
            {
                "schema_version": 2,
                "roots": nodes,
            },
        )


def provision_path(snapshot: Path, branches: list[str]) -> list[str]:
    # Map concrete branch events to first visits of provision IDs.
    result: list[str] = []
    provisions = _block_provisions(snapshot)
    for branch in branches:
        for filename, line in _SITE.findall(branch):
            block = _block_at_position(snapshot / filename, int(line))
            if block:
                provision = provisions.get(block)
                if provision:
                    result.append(provision)
    return first_statute_visits(result)


@lru_cache(maxsize=64)
def _block_provisions(snapshot: Path) -> dict[str, str]:
    result = {}
    for source in snapshot.glob("*.catala_*"):
        for block, provision in _BLOCK_DETAILS.findall(
            source.read_text(encoding="utf-8")
        ):
            if provision != "none":
                result[block] = provision
    return result


@lru_cache(maxsize=256)
def _code_blocks(source: Path) -> tuple[tuple[int, int, str], ...]:
    if not source.is_file():
        return ()
    blocks = []
    marker = None
    start = None
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        found = _BLOCK_DETAILS.search(line)
        if found:
            marker = found.group(1) if found.group(2) != "none" else None
        if line.startswith("```catala"):
            start = number + 1
        elif line == "```" and start is not None:
            if marker:
                blocks.append((start, number - 1, marker))
            start = None
    return tuple(blocks)


def _block_at_position(source: Path, line: int) -> str | None:
    return next(
        (block for start, end, block in _code_blocks(source) if start <= line <= end),
        None,
    )


@lru_cache(maxsize=64)
def _definition_blocks(snapshot: Path) -> dict[tuple[str, str], tuple[str, ...]]:
    found: dict[tuple[str, str], list[str]] = {}
    scope_pattern = re.compile(r"^\s*scope\s+(\w+)\s*:")
    definition_pattern = re.compile(r"^\s*definition\s+(\w+)\b")
    for source in snapshot.glob("*.catala_*"):
        scope = None
        in_code = False
        for number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            if line.startswith("```catala"):
                in_code = True
                scope = None
                continue
            if line == "```":
                in_code = False
                scope = None
                continue
            if not in_code:
                continue
            declared = scope_pattern.match(line)
            if declared:
                scope = declared.group(1)
            definition = definition_pattern.match(line)
            if definition and scope:
                block = _block_at_position(source, number)
                if block:
                    key = (scope, definition.group(1))
                    if block not in found.setdefault(key, []):
                        found[key].append(block)
    return {key: tuple(blocks) for key, blocks in found.items()}


@lru_cache(maxsize=64)
def _declaration_blocks(snapshot: Path) -> dict[tuple[str, str], tuple[str, ...]]:
    # Map generated helper-call names back to annotated Catala declarations.
    found: dict[tuple[str, str], list[str]] = {}
    declaration = re.compile(
        r"^\s*declaration\s+(?:(?:scope|structure|enumeration)\s+)?(\w+)\b"
    )
    for source in snapshot.glob("*.catala_*"):
        in_code = False
        for number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), 1
        ):
            if line.startswith("```catala"):
                in_code = True
                continue
            if line == "```":
                in_code = False
                continue
            if not in_code:
                continue
            matched = declaration.match(line)
            if not matched:
                continue
            block = _block_at_position(source, number)
            if block:
                key = (source.name, matched.group(1))
                if block not in found.setdefault(key, []):
                    found[key].append(block)
    return {key: tuple(blocks) for key, blocks in found.items()}


def _call_block(snapshot: Path, name: Any) -> str | None:
    if not isinstance(name, str) or "::" not in name:
        return None
    filename, declaration = name.split("::", 1)
    candidates = _declaration_blocks(snapshot).get(
        (Path(filename).name, declaration), ()
    )
    return candidates[0] if len(candidates) == 1 else None


def traced_provision_path(
    snapshot: Path,
    events: list[dict[str, Any]],
    entry_scope: str | None = None,
    entry_source: str | None = None,
) -> list[str]:
    # Map concrete events to each provision's first visit in execution order.
    result = []
    definitions = _definition_blocks(snapshot)
    previous_block = None
    for event in events:
        block = None
        if event.get("event") == "BeginCall":
            block = _call_block(snapshot, event.get("name"))
        if event.get("event") in {"BeginCall", "EndCall"}:
            previous_block = None
        if event.get("event") in {"DecisionTaken", "BranchTaken"}:
            position = event.get("pos") or {}
            filename, line = position.get("filename"), position.get("start_line")
            if isinstance(filename, str) and isinstance(line, int):
                block = _block_at_position(snapshot / Path(filename).name, line)
        elif event.get("event") == "VariableDefinition":
            name = event.get("name", "")
            if isinstance(name, str) and "." in name:
                candidates = definitions.get(tuple(name.split(".", 1)), ())
                if len(candidates) == 1:
                    block = candidates[0]
        # A decision is a concrete visit even when the same rule fires twice.
        if block and (
            event.get("event") in {"BeginCall", "DecisionTaken", "BranchTaken"}
            or block != previous_block
        ):
            result.append(block)
        if block:
            previous_block = block
    provisions = _block_provisions(snapshot)
    return first_statute_visits(
        [provisions[block] for block in result if block in provisions]
    )


def _collapse_adjacent_statute_leaves(nodes: list[Any]) -> list[Any]:
    # Collapse runs of equal string leaves without crossing another node.
    compact = []
    for node in nodes:
        if isinstance(node, str) and compact and compact[-1] == node:
            continue
        compact.append(node)
    return compact


def execution_statute_tree(snapshot: Path, tree: list[dict[str, Any]]) -> list[Any]:
    # Project execution to provision IDs and collapse adjacent equal leaves.
    definitions = _definition_blocks(snapshot)
    provisions = _block_provisions(snapshot)

    def provision(node: dict[str, Any]) -> str | None:
        block = None
        if node.get("kind") == "call":
            block = _call_block(snapshot, node.get("name"))
        elif node.get("kind") in {"decision", "branch"}:
            position = node.get("pos") or {}
            filename, line = position.get("filename"), position.get("start_line")
            if isinstance(filename, str) and isinstance(line, int):
                block = _block_at_position(snapshot / Path(filename).name, line)
        elif node.get("kind") == "variable":
            name = node.get("name", "")
            if isinstance(name, str) and "." in name:
                candidates = definitions.get(tuple(name.split(".", 1)), ())
                if len(candidates) == 1:
                    block = candidates[0]
        return provisions.get(block) if block else None

    result = []
    for node in tree:
        children = execution_statute_tree(snapshot, node.get("children", []))
        statute_id = provision(node)
        if statute_id or children:
            if statute_id and not children:
                result.append(statute_id)
                continue
            simplified = {}
            if statute_id:
                simplified["statute_id"] = statute_id
            if children:
                simplified["children"] = children
            result.append(simplified)
    return _collapse_adjacent_statute_leaves(result)


def statute_tree_ids(tree: list[Any]) -> list[str]:
    # Return provision IDs from a projected Catala tree in traversal order.
    result: list[str] = []
    for node in tree:
        if isinstance(node, str):
            result.append(node)
        elif isinstance(node, dict):
            statute_id = node.get("statute_id")
            if isinstance(statute_id, str):
                result.append(statute_id)
            children = node.get("children")
            if isinstance(children, list):
                result.extend(statute_tree_ids(children))
    return result


def reasoning_tree_provision_ids(tree: Any) -> list[str]:
    # Return provision IDs from an extracted LLM tree in step order.
    if not isinstance(tree, dict) or not isinstance(tree.get("steps"), list):
        return []
    return [
        step["provision"]
        for step in tree["steps"]
        if isinstance(step, dict) and isinstance(step.get("provision"), str)
    ]


def execution_blocks(snapshot: Path, tree: list[dict[str, Any]]) -> list[str]:
    # Return first visits of annotated source blocks in execution order.
    definitions = _definition_blocks(snapshot)
    result: list[str] = []
    seen: set[str] = set()

    def visit(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            block = None
            if node.get("kind") == "call":
                block = _call_block(snapshot, node.get("name"))
            elif node.get("kind") == "decision":
                position = node.get("pos") or {}
                filename, line = position.get("filename"), position.get("start_line")
                if isinstance(filename, str) and isinstance(line, int):
                    block = _block_at_position(snapshot / Path(filename).name, line)
            elif node.get("kind") == "variable":
                name = node.get("name", "")
                if isinstance(name, str) and "." in name:
                    candidates = definitions.get(tuple(name.split(".", 1)), ())
                    if len(candidates) == 1:
                        block = candidates[0]
            if block and block not in seen:
                seen.add(block)
                result.append(block)
            visit(node.get("children", []))

    visit(tree)
    return result
