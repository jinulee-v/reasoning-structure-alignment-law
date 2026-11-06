"""Repair configuration and recursive scope-refinement operations."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

for _package_root in [Path("/rtdf/python"), *Path(__file__).resolve().parents]:
    if (_package_root / "rtdf_formalizer").is_dir():
        sys.path.insert(0, str(_package_root))
        break

from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.utils.common import RunnerError, atomic_json, load_json


class RepairMode(str, Enum):
    NO_TESTING = "no-testing"
    ANSWER_ONLY = "answer-only"
    RECURSIVE = "recursive"


DEFAULT_MAX_ITERATION = 2

REPLAY_SCRIPT = "replay_cases.py"

ARTIFACT_MANIFEST = "repair_artifacts.json"


def mode(config: dict[str, Any]) -> RepairMode | None:
    # Old runs remain opt-in; all new runs explicitly store their mode.
    from rtdf_formalizer.stages import utils as exp

    if "repair" not in config:
        return None
    try:
        selected = RepairMode(config["repair"]["mode"])
    except (ValueError, KeyError, TypeError) as error:
        raise exp.RunnerError(
            "repair.mode must be no-testing, answer-only, or recursive"
        ) from error
    return selected


def max_iteration(config: dict[str, Any]) -> int:
    # Return the inclusive repair-iteration cap persisted in a run config.
    value = config.get("repair", {}).get("max_iteration", DEFAULT_MAX_ITERATION)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        from rtdf_formalizer.stages import utils as exp

        raise exp.RunnerError("repair.max_iteration must be a non-negative integer")
    return value


def report_name(iteration: int) -> str:
    return f"iter{iteration}_testing_report.json"


def install_artifact(run: Path, name: str, source: Path) -> None:
    manifest_path = run / ARTIFACT_MANIFEST
    manifest = exp.load_json(manifest_path) if manifest_path.is_file() else {}
    manifest[name] = exp.sha256_file(source)
    # Write the allowlist first: interruption before copying is recoverable.
    exp.atomic_json(manifest_path, manifest)
    exp.atomic_copy(source, run / "workspace" / name)


def checked_artifacts(workspace: Path, run: Path | None = None) -> set[str]:
    # Exclude only runner-installed, unmodified files from submission checks.
    manifest_path = (run if run is not None else workspace.parent) / ARTIFACT_MANIFEST
    if run is None and workspace.name != "workspace":
        return set()
    if not manifest_path.is_file():
        return set()
    manifest = exp.load_json(manifest_path)
    for name, digest in manifest.items():
        if name != REPLAY_SCRIPT and not re.fullmatch(
            r"iter\d+_testing_report\.json", name
        ):
            raise exp.RunnerError(f"invalid managed repair artifact: {name}")
        path = workspace / name
        if path.is_symlink() or not path.is_file() or exp.sha256_file(path) != digest:
            raise exp.RunnerError(
                f"runner-managed repair artifact changed or missing: {name}"
            )
    return set(manifest)


def publish_report(run: Path, state: dict[str, Any], summary: dict[str, Any]) -> Path:
    iteration = int(state["iteration"])
    config_path = run / "config.json"
    selected = (
        mode(exp.load_json(config_path))
        if config_path.is_file()
        else RepairMode.ANSWER_ONLY
    )
    rows = []
    for row in summary["cases"]:
        if selected is RepairMode.ANSWER_ONLY and (
            not row.get("requirement_id") or not row.get("output_name")
        ):
            raise exp.RunnerError(
                "answer-only reports require a requirement/output mapping for every case"
            )
        trace = row.get("llm_reasoning_trace") or ""
        # Remove only the final answer block; the existing explanation is not summarized.
        blocks = list(
            re.finditer(r"<answer>[\s\S]*?</answer>", trace, flags=re.IGNORECASE)
        )
        if blocks:
            final = blocks[-1]
            trace = trace[: final.start()] + trace[final.end() :]
        trace = trace.strip()
        rows.append(
            {
                "requirement_id": row.get("requirement_id"),
                "source": row.get("source"),
                "scope": row.get("target"),
                "output_name": row.get("output_name"),
                "input": row["inputs"],
                "code_execution_output": row["catala_answer"],
                "llm_reasoning_trace": trace,
                "llm_answer": row["llm_final_answer"],
                "code_execution_error": bool(row.get("code_execution_error")),
                "code_execution_diagnostic": row.get("code_execution_diagnostic"),
                "llm_reasoning_error": bool(row.get("llm_reasoning_error")),
                "llm_reasoning_diagnostic": row.get("llm_reasoning_diagnostic"),
            }
        )
    destination = (
        run / "iterations" / f"{iteration:03d}" / "feedback" / report_name(iteration)
    )
    exp.atomic_json(destination, rows)
    install_artifact(run, destination.name, destination)
    return destination


def prepare_agent(run: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    if mode(config) is not RepairMode.ANSWER_ONLY or int(state["iteration"]) == 0:
        return
    previous = int(state["iteration"]) - 1
    report = run / "iterations" / f"{previous:03d}" / "feedback" / report_name(previous)
    if not report.is_file():
        raise exp.RunnerError(f"missing repair feedback: {report}")
    install_artifact(run, report.name, report)
    install_artifact(run, REPLAY_SCRIPT, Path(__file__))


def advance(
    run: Path, state: dict[str, Any], maximum: int = DEFAULT_MAX_ITERATION
) -> bool:
    # Archive completed iteration state before moving to the next code version.
    iteration = int(state["iteration"])
    exp.atomic_json(run / "iterations" / f"{iteration:03d}" / "state.json", state)
    if iteration >= maximum:
        state.update(
            next_stage="finished", status="completed", updated_at=exp.utc_now()
        )
        state.pop("reasoning_authorized_iteration", None)
        exp.atomic_json(run / "state.json", state)
        return False
    for key in (
        "comparison_summary",
        "verification_summary",
        "reasoning_authorized_iteration",
    ):
        state.pop(key, None)
    state.update(
        iteration=iteration + 1,
        next_stage="agent",
        status="running",
        completed_stages=["initialized"],
        active_attempt=None,
        updated_at=exp.utc_now(),
    )
    exp.atomic_json(run / "state.json", state)
    return True


def prompt(
    initial_prompt: str,
    selected: RepairMode,
    iteration: int,
    focus: dict[str, Any] | None = None,
) -> str:
    if iteration == 0 and not (selected is RepairMode.RECURSIVE and focus):
        return initial_prompt
    initial_instruction = (
        "You must formalize the entire dataset in a single run; don't stop until "
        "you achieve the best possible draft.\n"
    )
    if selected is RepairMode.NO_TESTING:
        instruction = (
            "Review the existing Catala implementation against the supplied statutes and "
            "requirements. Identify and fix any discrepancies you find.\n"
        )
    else:
        focus_instruction = ""
        if selected is RepairMode.RECURSIVE:
            if not focus:
                raise ValueError("recursive repair requires a current scope")
            focus_instruction = (
                f"This session refines scope {focus['scope']} in {focus['source']}. "
                "Read the scope-local evidence mounted at /rtdf/feedback. Compare each "
                "Catala result with the raw LLM reasoning and both execution trees. Start "
                "with catala_causal_trace.yaml, whose branch_guards record the concrete "
                "condition outcomes controlling each Catala value; use the raw Catala tree "
                "only when the compact trace is insufficient. You may "
                "edit this scope, descendant scopes, and shared helpers. Keep changes minimal "
                "and localized to the target scope. Edit a descendant scope or shared helper "
                "only when the evidence shows that the target cannot be corrected within the "
                "target scope itself, and make only the smallest necessary external change. "
                "Do not perform opportunistic refactoring or unrelated fixes. Replays use cached "
                "inputs and traces unless the runner detects an incompatible interface. "
                "If a generated test assigns values outside the scope's meaningful input "
                "domain, making sound natural-language reasoning impossible, encode the "
                "admissible domain as Catala assertions over the scope's input context "
                "variables, such as numeric bounds or structural invariants. Add only "
                "genuine domain preconditions, not constraints introduced merely to "
                "eliminate a disagreement. "
                "After a semantic or domain fix invalidates the current evidence, run "
                "python3 /rtdf/regenerate_scope_analysis.py to generate fresh BOBCat "
                "cases, Catala executions, LLM traces, and execution trees for this "
                "scope. The refreshed evidence replaces /rtdf/feedback/cases and its "
                "LLM usage is recorded by the runner. Use this after a relevant fix, "
                "not merely to seek a more favorable LLM answer. "
                "To replay every cached input against the current workspace, run "
                "python3 /rtdf/python/rtdf_formalizer/stages/reasoning_trace_diff_fuzzing/repair.py "
                "/rtdf/feedback --workspace /workspace. "
            )
        instruction = (
            ""
            if selected is RepairMode.RECURSIVE
            else (
                f"Read /workspace/{report_name(iteration - 1)}. It contains all tested inputs "
                "and their LLM and Catala answers, including matches and failures. Compare only "
                "the named requirement output. Money differences strictly below one currency "
                "unit count as equal; a difference of exactly one does not. Decide whether the "
                "Catala implementation, the LLM reasoning/answer, or both are wrong. Do not "
                "assume the LLM answer is authoritative. Fix the code where necessary.\n"
                f"To check current code, run: python3 /workspace/{REPLAY_SCRIPT} "
                f"/workspace/{report_name(iteration - 1)}\n"
                "This returns current answers in report order. Keep the report and helper unchanged.\n"
            )
        )
        instruction = focus_instruction + instruction
    return instruction + initial_prompt.replace(initial_instruction, "", 1)


def scope_id(source: str, scope: str) -> str:
    return f"{source}::{scope}"


def scope_slug(record: dict[str, Any]) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", record["id"]).strip("-")
    digest = hashlib.sha256(record["id"].encode()).hexdigest()[:12]
    return f"{value[:100] or 'scope'}-{digest}"


def scope_revision_root(run: Path, state: dict[str, Any]) -> Path:
    active = current_scope(state)
    if active is None:
        raise ValueError("recursive refinement has no active scope")
    revision = int(state.get("recursive_revision", 0))
    return run / "refinement" / scope_slug(active) / "revisions" / f"{revision:03d}"


def revision_directory(run: Path, state: dict[str, Any]) -> Path:
    step = state.get("recursive_step", "analysis")
    return scope_revision_root(run, state) / step


def topological_scope_order(
    scopes: Iterable[dict[str, Any]],
    dependencies: dict[str, set[str]],
    dependency_order: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    # Traverse entry scopes in execution order while placing every callee first.
    unique: dict[str, dict[str, Any]] = {}
    for record in scopes:
        source = record.get("compiler_file") or record.get("file")
        identifier = scope_id(source, record["scope"])
        unique.setdefault(
            identifier,
            {
                "id": identifier,
                "source": source,
                "file": record.get("file", source),
                "scope": record["scope"],
                "input_schema": record.get("input_schema"),
                "output_schema": record.get("output_schema"),
                "schema_error": record.get("schema_error"),
            },
        )
    identifiers = set(unique)
    ordered_dependencies: dict[str, list[str]] = {}
    for identifier in unique:
        needed = set(dependencies.get(identifier, set())) & identifiers
        preferred = (dependency_order or {}).get(identifier, [])
        ordered_dependencies[identifier] = [
            dependency for dependency in preferred if dependency in needed
        ]
        ordered_dependencies[identifier].extend(
            sorted(needed - set(ordered_dependencies[identifier]))
        )
    called = {
        dependency
        for values in ordered_dependencies.values()
        for dependency in values
    }
    roots = [identifier for identifier in unique if identifier not in called]
    ordered: list[dict[str, Any]] = []
    visited: set[str] = set()
    visiting: list[str] = []

    def visit(identifier: str) -> None:
        if identifier in visited:
            return
        if identifier in visiting:
            cycle = visiting[visiting.index(identifier) :] + [identifier]
            raise ValueError(
                "scope dependency graph contains a cycle: " + ", ".join(cycle)
            )
        visiting.append(identifier)
        for dependency in ordered_dependencies[identifier]:
            visit(dependency)
        visiting.pop()
        visited.add(identifier)
        record = dict(unique[identifier])
        record["dependencies"] = ordered_dependencies[identifier]
        ordered.append(record)

    for identifier in [*roots, *unique]:
        visit(identifier)
    return ordered


def _declared_dependency_order(
    project: Path,
    scopes: list[dict[str, Any]],
    dependencies: dict[str, set[str]],
) -> dict[str, list[str]]:
    by_id = {
        scope_id(record.get("compiler_file") or record.get("file"), record["scope"]): record
        for record in scopes
    }
    result: dict[str, list[str]] = {}
    for caller, needed in dependencies.items():
        record = by_id.get(caller)
        if record is None:
            continue
        source = project / record.get("file", record.get("compiler_file"))
        try:
            text = source.read_text(encoding="utf-8")
        except OSError:
            continue
        declaration = re.search(
            r"(?m)^declaration[ \t]+scope[ \t]+"
            + re.escape(record["scope"])
            + r"[ \t]*:",
            text,
        )
        start = declaration.start() if declaration else 0
        positions = {}
        for dependency in needed:
            target = by_id.get(dependency)
            position = text.find(target["scope"], start) if target else -1
            positions[dependency] = position if position >= 0 else len(text)
        result[caller] = sorted(
            needed,
            key=lambda dependency: (positions[dependency], dependency),
        )
    return result


def _graph_scope_mapping(
    scopes: list[dict[str, Any]], names: set[str]
) -> dict[str, str]:
    by_short: dict[str, list[str]] = {}
    for record in scopes:
        source = record.get("compiler_file") or record.get("file")
        by_short.setdefault(record["scope"], []).append(
            scope_id(source, record["scope"])
        )
    result: dict[str, str] = {}
    for name in names:
        candidates = sorted(set(by_short.get(name.rsplit(".", 1)[-1], [])))
        if len(candidates) == 1:
            result[name] = candidates[0]
            continue
        module = name.rsplit(".", 1)[0].rsplit(".", 1)[-1].casefold()
        qualified = [
            candidate
            for candidate in candidates
            if Path(candidate.split("::", 1)[0]).stem.casefold() == module
        ]
        if len(qualified) == 1:
            result[name] = qualified[0]
    return result


def discover_scope_order(
    project: Path,
    scopes: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    # Read Catala's static scope-call graph while retaining non-JSON scopes.
    from rtdf_formalizer.stages import utils as exp

    environment = exp.toolchain_environment(config)
    catala = shutil.which("catala", path=environment.get("PATH"))
    if not catala:
        raise exp.RunnerError("Catala is required to order scopes for recursive repair")
    timeout = int(config.get("runtime", {}).get("timeout_seconds", 7200))
    graph_dependencies: dict[str, set[str]] = {}
    for source in sorted(
        {record.get("compiler_file") or record.get("file") for record in scopes}
    ):
        completed = exp.run_checked(
            [
                catala,
                "dependency-graph",
                source,
                "--stdlib",
                "_build/libcatala",
                "--include",
                ".",
                "--whole-program",
                "--color=never",
            ],
            cwd=project,
            environment=environment,
            timeout=timeout,
        )
        try:
            _, inter = exp._dependency_graph_edges(json.loads(completed.stdout))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise exp.RunnerError(
                f"invalid Catala dependency graph for {source}: {error}"
            ) from error
        for caller, callees in inter.items():
            graph_dependencies.setdefault(caller, set()).update(callees)
    names = set(graph_dependencies)
    names.update(name for values in graph_dependencies.values() for name in values)
    mapping = _graph_scope_mapping(scopes, names)
    dependencies: dict[str, set[str]] = {}
    for caller, callees in graph_dependencies.items():
        if caller in mapping:
            dependencies.setdefault(mapping[caller], set()).update(
                mapping[callee] for callee in callees if callee in mapping
            )
    execution_order = _declared_dependency_order(project, scopes, dependencies)
    return topological_scope_order(scopes, dependencies, execution_order)


def install_plan(state: dict[str, Any], plan: list[dict[str, Any]]) -> None:
    state["recursive_repair_plan"] = plan
    state["recursive_repair_queue"] = [record["id"] for record in plan]
    state["recursive_order_version"] = 2
    state.setdefault("recursive_processed", {})
    state.setdefault("recursive_revisions", {})


def migrate_scope_order(run: Path, state: dict[str, Any]) -> bool:
    if int(state.get("recursive_order_version", 1)) >= 2:
        return False
    formats = json.loads(
        (run / "initial/validation/input_formats.json").read_text(encoding="utf-8")
    )["candidate"]["scopes"]
    previous = state["recursive_repair_plan"]
    dependencies = {
        record["id"]: set(record.get("dependencies", [])) for record in previous
    }
    execution_order = _declared_dependency_order(
        run / "initial/snapshot", formats, dependencies
    )
    plan = topological_scope_order(formats, dependencies, execution_order)
    processed = state.setdefault("recursive_processed", {})
    completed_prefix: list[str] = []
    for record in plan:
        if record["id"] not in processed:
            break
        completed_prefix.append(record["id"])
    keep = set(completed_prefix)
    state["recursive_processed"] = {
        identifier: value
        for identifier, value in processed.items()
        if identifier in keep
    }
    state["recursive_repair_plan"] = plan
    state["recursive_repair_queue"] = [
        record["id"] for record in plan if record["id"] not in keep
    ]
    state["recursive_order_version"] = 2
    state["recursive_invalidation_reason"] = (
        "scope traversal changed to dependency-first execution order"
    )
    state.pop("recursive_active_scope", None)
    state.pop("recursive_before_schema_fingerprint", None)
    activate_next(state)
    state.update(next_stage="scope_analysis", recursive_step="analysis", status="running")
    return True


def current_scope(state: dict[str, Any]) -> dict[str, Any] | None:
    identifier = state.get("recursive_active_scope")
    return next(
        (
            record
            for record in state.get("recursive_repair_plan", [])
            if record["id"] == identifier
        ),
        None,
    )


def activate_next(state: dict[str, Any]) -> dict[str, Any] | None:
    queue = state.setdefault("recursive_repair_queue", [])
    if not queue:
        state.pop("recursive_active_scope", None)
        return None
    identifier = queue.pop(0)
    state["recursive_active_scope"] = identifier
    revisions = state.setdefault("recursive_revisions", {})
    state["recursive_revision"] = int(revisions.get(identifier, 0))
    revisions[identifier] = state["recursive_revision"] + 1
    return current_scope(state)


def reverse_dependencies(plan: list[dict[str, Any]]) -> dict[str, set[str]]:
    result = {record["id"]: set() for record in plan}
    for record in plan:
        for dependency in record.get("dependencies", []):
            result.setdefault(dependency, set()).add(record["id"])
    return result


def dependent_closure(plan: list[dict[str, Any]], changed: set[str]) -> set[str]:
    reverse = reverse_dependencies(plan)
    result, pending = set(changed), list(changed)
    while pending:
        for dependent in reverse.get(pending.pop(), set()):
            if dependent not in result:
                result.add(dependent)
                pending.append(dependent)
    return result


def enqueue(state: dict[str, Any], identifiers: Iterable[str]) -> None:
    order = {
        record["id"]: index
        for index, record in enumerate(state["recursive_repair_plan"])
    }
    queue = state.setdefault("recursive_repair_queue", [])
    active = state.get("recursive_active_scope")
    pending = set(queue)
    pending.update(identifier for identifier in identifiers if identifier != active)
    queue[:] = sorted(
        pending, key=lambda identifier: (order.get(identifier, 10**9), identifier)
    )


def _scope_fragments(text: str, name: str) -> list[str]:
    heading = re.compile(
        r"(?m)^[ \t]*(?:declaration[ \t]+)?scope[ \t]+" + re.escape(name) + r"[ \t]*:"
    )
    boundaries = list(
        re.finditer(
            r"(?m)^[ \t]*(?:(?:declaration[ \t]+)?scope[ \t]+[^\s:]+[ \t]*:|```)", text
        )
    )
    fragments = []
    for match in heading.finditer(text):
        end = next(
            (item.start() for item in boundaries if item.start() > match.start()),
            len(text),
        )
        fragments.append(text[match.start() : end].strip())
    return fragments


def scope_fingerprint(workspace: Path, record: dict[str, Any]) -> str:
    source = workspace / record.get("file", record["source"])
    if not source.is_file():
        return "missing"
    fragments = _scope_fragments(source.read_text(encoding="utf-8"), record["scope"])
    payload = json.dumps(fragments, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def scope_fingerprints(workspace: Path, plan: list[dict[str, Any]]) -> dict[str, str]:
    return {record["id"]: scope_fingerprint(workspace, record) for record in plan}


def helper_inventory(workspace: Path) -> dict[str, dict[str, str]]:
    # Index top-level Catala values and functions separately from scopes.
    inventory: dict[str, dict[str, str]] = {}
    heading = re.compile(
        r"(?m)^[ \t]*declaration[ \t]+(?!scope\b)"
        r"(?:(?:structure|enumeration)[ \t]+)?([^\s:]+)[^\n]*$"
    )
    boundary = re.compile(
        r"(?m)^[ \t]*(?:declaration[ \t]+|(?:declaration[ \t]+)?scope[ \t]+|```)"
    )
    for source in sorted(workspace.rglob("*.catala_*")):
        text = source.read_text(encoding="utf-8")
        relative = source.relative_to(workspace).as_posix()
        boundaries = list(boundary.finditer(text))
        for match in heading.finditer(text):
            end = next(
                (item.start() for item in boundaries if item.start() > match.start()),
                len(text),
            )
            key = f"{relative}::{match.group(1)}"
            inventory[key] = {
                "name": match.group(1),
                "source": relative,
                "text": text[match.start() : end].strip(),
            }
    return inventory


def helper_graph(
    workspace: Path, plan: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, set[str]]]:
    # Compute conservative static helper-to-scope dependencies from authored source references.
    inventory = helper_inventory(workspace)
    fingerprints = {
        key: hashlib.sha256(value["text"].encode()).hexdigest()
        for key, value in inventory.items()
    }
    direct_helpers: dict[str, set[str]] = {key: set() for key in inventory}
    for key, value in inventory.items():
        for candidate, target in inventory.items():
            if candidate != key and re.search(
                r"\b" + re.escape(target["name"]) + r"\b", value["text"]
            ):
                direct_helpers[key].add(candidate)
    affected: dict[str, set[str]] = {key: set() for key in inventory}
    for record in plan:
        source = workspace / record.get("file", record["source"])
        text = "\n".join(
            _scope_fragments(
                source.read_text(encoding="utf-8") if source.is_file() else "",
                record["scope"],
            )
        )
        pending = [
            key
            for key, value in inventory.items()
            if re.search(r"\b" + re.escape(value["name"]) + r"\b", text)
        ]
        seen = set(pending)
        while pending:
            for dependency in direct_helpers.get(pending.pop(), set()):
                if dependency not in seen:
                    seen.add(dependency)
                    pending.append(dependency)
        for helper in seen:
            affected.setdefault(helper, set()).add(record["id"])
    return fingerprints, affected


def changed_helpers(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {
        identifier
        for identifier in set(before) | set(after)
        if before.get(identifier) != after.get(identifier)
    }


def helper_affected_scopes(
    changed: set[str], affected: dict[str, set[str]]
) -> set[str]:
    return {scope for helper in changed for scope in affected.get(helper, set())}


def schema_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "input": record.get("input_schema"),
        "output": record.get("output_schema"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def changed_scopes(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {
        identifier
        for identifier in set(before) | set(after)
        if before.get(identifier) != after.get(identifier)
    }


def record_processed(
    state: dict[str, Any],
    fingerprints: dict[str, str],
    changed: set[str],
) -> set[str]:
    # Accept the session, then requeue changed descendants and later-invalidated callers.
    active = state["recursive_active_scope"]
    processed = state.setdefault("recursive_processed", {})
    processed[active] = {
        "fingerprint": fingerprints.get(active),
        "revision": int(state.get("recursive_revision", 0)),
    }
    invalidated = dependent_closure(state["recursive_repair_plan"], changed) & set(
        processed
    )
    for identifier in invalidated:
        if identifier != active:
            processed.pop(identifier, None)
    targets = set(changed)
    targets.discard(active)
    targets.update(identifier for identifier in invalidated if identifier != active)
    enqueue(state, targets)
    return targets


def _node_scope(node: dict[str, Any], plan: list[dict[str, Any]]) -> str | None:
    name = node.get("scope") or node.get("name")
    if not isinstance(name, str):
        return None
    candidates = [
        record["id"]
        for record in plan
        if name == record["scope"] or name.endswith("." + record["scope"])
    ]
    if len(candidates) == 1:
        return candidates[0]
    if "." not in name:
        return None
    module = name.rsplit(".", 1)[0].rsplit(".", 1)[-1].casefold()
    qualified = [
        record["id"]
        for record in plan
        if record["id"] in candidates
        and Path(record.get("source", "")).stem.casefold() == module
    ]
    return qualified[0] if len(qualified) == 1 else None


def prune_execution_tree(tree: Any, state: dict[str, Any]) -> Any:
    # Collapse processed descendants without copying their potentially large concrete inputs.
    processed = set(state.get("recursive_processed", {}))
    active = state.get("recursive_active_scope")
    plan = state.get("recursive_repair_plan", [])
    if isinstance(tree, list):
        return [prune_execution_tree(item, state) for item in tree]
    if not isinstance(tree, dict):
        return tree
    identifier = _node_scope(tree, plan)
    if identifier in processed and identifier != active:
        encoded = json.dumps(tree.get("inputs"), sort_keys=True, default=str).encode()
        return {
            "kind": "processed_scope",
            "scope": identifier,
            "input_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
            "output": tree.get("output"),
        }
    return {key: prune_execution_tree(value, state) for key, value in tree.items()}


def write_scope_bundle(
    root: Path,
    state: dict[str, Any],
    cases: list[dict[str, Any]],
    symbolic: list[dict[str, Any]],
    natural: list[dict[str, Any]],
    previous_summary: dict[str, Any] | None = None,
) -> Path:
    # Give the repair agent scope-local evidence without comparison metadata.
    import yaml

    from rtdf_formalizer.bobcat.trace import causal_execution_trace
    from rtdf_formalizer.stages import utils as exp
    from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline

    bundle = root / "scope_task"
    bundle.mkdir(parents=True, exist_ok=True)
    active = current_scope(state)
    exp.atomic_json(
        bundle / "task.json",
        {
            "scope": active,
            "case_ids": [case["id"] for case in cases],
            "previous_summary": previous_summary,
            "invalidation_reason": state.get("recursive_invalidation_reason"),
        },
    )
    symbolic_by_id = {record["id"]: record for record in symbolic}
    natural_by_id = {record["id"]: record for record in natural}
    for case in cases:
        destination = bundle / "cases" / re.sub(r"[^A-Za-z0-9_.-]+", "_", case["id"])
        destination.mkdir(parents=True, exist_ok=True)
        formal = symbolic_by_id.get(case["id"], {})
        reasoning = natural_by_id.get(case["id"], {})
        llm_answer, parse_error = pipeline.parse_final_answer(
            reasoning.get("output_text")
        )
        exp.atomic_json(
            destination / "case.json",
            {
                "case_id": case["id"],
                "input": case.get("inputs"),
                "catala_output": formal.get("output"),
                "catala_error": formal.get("error"),
                "llm_answer": llm_answer,
                "llm_error": reasoning.get("error")
                or parse_error
                or reasoning.get("execution_tree_extraction_error"),
            },
        )
        sliced_tree = prune_execution_tree(
            formal.get("dynamic_slice_tree", formal.get("execution_tree", [])), state
        )
        exp.atomic_json(destination / "catala_execution_tree.json", sliced_tree)
        causal = causal_execution_trace(root / "snapshot", sliced_tree)
        (destination / "catala_causal_trace.yaml").write_text(
            yaml.safe_dump(causal, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        exp.atomic_json(
            destination / "llm_execution_tree.json", reasoning.get("execution_tree")
        )
        cot = pipeline._reasoning_without_answer(reasoning.get("output_text") or "")
        (destination / "llm_cot.txt").write_text(cot, encoding="utf-8")
    return bundle


def source_diff(before: Path, after: Path) -> str:
    left = before.read_text(encoding="utf-8").splitlines() if before.is_file() else []
    right = after.read_text(encoding="utf-8").splitlines() if after.is_file() else []
    return "\n".join(
        difflib.unified_diff(left, right, fromfile="before", tofile="after")
    )


def workspace_diff(before: Path, after: Path) -> str:
    paths = {path.relative_to(before) for path in before.rglob("*.catala_*")}
    paths.update(path.relative_to(after) for path in after.rglob("*.catala_*"))
    chunks = [source_diff(before / path, after / path) for path in sorted(paths)]
    return "\n".join(chunk for chunk in chunks if chunk)


def validate_summary(value: Any, scope: str, case_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("scope") != scope:
        raise ValueError("scope summary identifies the wrong scope")
    if not isinstance(value.get("change_summary"), list) or not all(
        isinstance(item, str) and item.strip() for item in value["change_summary"]
    ):
        raise ValueError("scope summary has an invalid change_summary")
    rows = value.get("remaining_disagreements")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict)
        or set(row) != {"case_id", "rationale"}
        or not isinstance(row["case_id"], str)
        or not isinstance(row["rationale"], str)
        or not row["rationale"].strip()
        for row in rows
    ):
        raise ValueError("scope summary has invalid disagreement rationales")
    summarized = [row["case_id"] for row in rows]
    if len(summarized) != len(set(summarized)) or set(summarized) != case_ids:
        raise ValueError("scope summary case IDs do not match remaining disagreements")
    return value


def initialize(run: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    # Build the work queue once from the validated initial formalization.
    from rtdf_formalizer.stages import utils as exp

    initial = run / "initial"
    formats_path = initial / "validation/input_formats.json"
    snapshot = initial / "snapshot"
    if not formats_path.is_file() or not snapshot.is_dir():
        raise exp.RunnerError(
            "recursive refinement requires validated initial artifacts"
        )
    formats = exp.load_json(formats_path)["candidate"]
    scopes = list(formats.get("scopes", []))
    project = initial / "dependency_project"
    if not project.is_dir():
        exp.copy_project(snapshot, project)
        gold = exp.resolve_gold_dataset(config["dataset"]["name"])
        if gold is not None:
            exp.stage_reference_dependencies(gold, project)
        exp.extract_input_formats(
            project,
            environment=exp.toolchain_environment(config),
            timeout=int(config.get("runtime", {}).get("timeout_seconds", 7200)),
        )
    plan = discover_scope_order(project, scopes, config)
    install_plan(state, plan)
    state["recursive_initial_fingerprints"] = scope_fingerprints(
        run / "workspace", plan
    )
    helper_hashes, helper_users = helper_graph(run / "workspace", plan)
    state["recursive_helper_fingerprints"] = helper_hashes
    state["recursive_helper_users"] = {
        key: sorted(value) for key, value in helper_users.items()
    }
    state["recursive_phase"] = "scope"
    if int(config.get("repair", {}).get("max_iteration", 2)) == 0:
        state["recursive_exhausted"] = list(state["recursive_repair_queue"])
        state["recursive_repair_queue"] = []
        state.update(next_stage="finished", status="completed")
    elif activate_next(state) is None:
        state.update(next_stage="finished", status="completed")
    else:
        state.update(
            next_stage="scope_analysis", status="running", recursive_step="analysis"
        )
    state["updated_at"] = exp.utc_now()
    exp.atomic_json(run / "state.json", state)


def _copy_cache(source: Path, destination: Path) -> None:
    for name in ("tests_bobcat", "tests_bobcat_natural_language_results"):
        candidate = source / name
        target = destination / name
        if candidate.is_dir() and not target.exists():
            shutil.copytree(candidate, target)


def _latest_summary(run: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    latest = run / "refinement" / scope_slug(record) / "latest.json"
    if not latest.is_file():
        return None
    pointer = json.loads(latest.read_text(encoding="utf-8"))
    summary = run / pointer["summary"]
    return (
        json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else None
    )


def _refresh_active_schema(
    run: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    root: Path,
) -> str:
    from rtdf_formalizer.stages import utils as exp

    active = current_scope(state)
    snapshot = exp.publish_stage_snapshot(run, state)
    project = root / "schema_project"
    if not project.is_dir():
        exp.copy_project(snapshot, project)
        gold = exp.resolve_gold_dataset(config["dataset"]["name"])
        if gold is not None:
            exp.stage_reference_dependencies(gold, project)
    formats = exp.extract_input_formats(
        project,
        environment=exp.toolchain_environment(config),
        timeout=int(config.get("runtime", {}).get("timeout_seconds", 7200)),
    )
    match = next(
        (
            record
            for record in formats.get("scopes", [])
            if record.get("scope") == active["scope"]
            and (record.get("compiler_file") or record.get("file")) == active["source"]
        ),
        None,
    )
    if match is None:
        active.update(
            input_schema=None,
            output_schema=None,
            schema_error="scope is absent from the current compiler interface",
        )
    else:
        active.update(
            input_schema=match.get("input_schema"),
            output_schema=match.get("output_schema"),
            schema_error=match.get("schema_error"),
        )
    return schema_fingerprint(active)


def analyze_scope(
    run: Path, config: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    # Analyze only the active scope and reuse its cases and LLM traces when schemas remain stable.
    from rtdf_formalizer.stages import utils as exp
    from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline

    root = exp.stage_directory(run, state)
    root.mkdir(parents=True, exist_ok=True)
    active = current_scope(state)
    if active is None:
        raise exp.RunnerError("recursive analysis has no active scope")
    current_schema = _refresh_active_schema(run, config, state, root)
    processed = state.get("recursive_processed", {}).get(active["id"], {})
    if state.get("recursive_step") == "result":
        cached_path = scope_revision_root(run, state) / "analysis"
        cached_schema = state.get("recursive_before_schema_fingerprint")
    else:
        cached_path = (
            run / processed["analysis_path"] if processed.get("analysis_path") else None
        )
        cached_schema = processed.get("schema_fingerprint")
        state["recursive_before_schema_fingerprint"] = current_schema
    if cached_path and cached_schema == current_schema:
        _copy_cache(cached_path, root)
    options = pipeline.backfill_options(run, config)
    options = {**options, "_scope_record": active}
    cases = pipeline.generate_tests(run, config, state, options)
    if cases:
        symbolic = pipeline.replay_compiled(run, config, state, cases)
        natural = pipeline.reason(run, config, state, cases)
        summary = pipeline.compare(run, state, symbolic, natural)
    else:
        symbolic, natural = [], []
        summary = {"total": 0, "cases": []}
        exp.atomic_json(root / "tests_bobcat_comparison/summary.json", summary)
    previous = _latest_summary(run, active)
    bundle = write_scope_bundle(root, state, cases, symbolic, natural, previous)
    state["recursive_last_analysis"] = str(root.relative_to(run))
    state["recursive_scope_task"] = str(bundle.relative_to(run))
    state["recursive_last_summary"] = {
        key: value for key, value in summary.items() if key != "cases"
    }
    state["updated_at"] = exp.utc_now()
    exp.atomic_json(run / "state.json", state)
    return summary


def regenerate_active_scope(
    run: Path, config: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    # Rebuild scope-local evidence from the agent's edited workspace.
    from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline

    active = current_scope(state)
    if active is None or state.get("recursive_step") != "session":
        raise exp.RunnerError("analysis regeneration requires an active repair session")
    parent = scope_revision_root(run, state) / "agent_regeneration"
    indices = [int(path.name) for path in parent.glob("[0-9][0-9][0-9]")]
    root = parent / f"{max(indices, default=-1) + 1:03d}"
    regenerated_state = {
        **state,
        "_stage_directory": str(root),
        "_reasoning_cache_nonce": str(root.relative_to(run)),
        "_usage_stage": "repair-regeneration-reasoning",
    }
    root.mkdir(parents=True)
    current_schema = _refresh_active_schema(run, config, regenerated_state, root)
    options = {**pipeline.backfill_options(run, config), "_scope_record": active}
    cases = pipeline.generate_tests(run, config, regenerated_state, options)
    if cases:
        symbolic = pipeline.replay_compiled(run, config, regenerated_state, cases)
        natural = pipeline.reason(run, config, regenerated_state, cases)
        summary = pipeline.compare(run, regenerated_state, symbolic, natural)
    else:
        symbolic, natural = [], []
        summary = {"total": 0, "cases": []}
        exp.atomic_json(root / "tests_bobcat_comparison/summary.json", summary)
    refreshed = write_scope_bundle(
        root, regenerated_state, cases, symbolic, natural, _latest_summary(run, active)
    )
    mounted = run / state["recursive_scope_task"]
    shutil.rmtree(mounted / "cases", ignore_errors=True)
    shutil.copytree(refreshed, mounted, dirs_exist_ok=True)
    result = {
        "scope": active["id"],
        "schema_fingerprint": current_schema,
        "case_count": len(cases),
        "analysis_path": str(root.relative_to(run)),
        "usage_stage": "repair-regeneration-reasoning",
    }
    exp.atomic_json(root / "regeneration.json", result)
    return result


def _summary_schema(case_ids: set[str]) -> dict[str, Any]:
    case_id_schema: dict[str, Any] = {"type": "string"}
    if case_ids:
        case_id_schema["enum"] = sorted(case_ids)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["scope", "change_summary", "remaining_disagreements"],
        "properties": {
            "scope": {"type": "string"},
            "change_summary": {"type": "array", "items": {"type": "string"}},
            "remaining_disagreements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["case_id", "rationale"],
                    "properties": {
                        "case_id": case_id_schema,
                        "rationale": {"type": "string"},
                    },
                },
            },
        },
    }


def generate_summary(
    run: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    comparison: dict[str, Any],
    before: Path,
    after: Path,
) -> dict[str, Any]:
    # Ask the reasoning model to summarize accepted changes and every remaining disagreement.
    from rtdf_formalizer.stages import utils as exp
    from rtdf_formalizer.stages.utils import usage as usage_tracking
    from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline

    active = current_scope(state)
    unaligned = {
        row["id"]
        for row in comparison.get("cases", [])
        if row.get("final_answer_aligned") is not True
    }
    evidence = [
        {
            "case_id": row["id"],
            "catala": row.get("catala_answer"),
            "catala_error": row.get("code_execution_diagnostic"),
            "llm": row.get("llm_final_answer"),
            "llm_error": row.get("llm_reasoning_diagnostic"),
            "llm_reasoning": row.get("llm_reasoning_trace"),
        }
        for row in comparison.get("cases", [])
        if row["id"] in unaligned
    ]
    prompt = (
        "Summarize the accepted Catala repair session as JSON. Describe concrete code changes "
        "briefly. For every listed remaining disagreement, explain why the session left Catala "
        "unchanged, especially any error in the LLM reasoning. Do not invent an explanation; "
        "say that the evidence is insufficient when necessary.\n\n"
        f"Scope: {active['scope']}\n"
        f"Source diff:\n{workspace_diff(before, after)}\n\n"
        f"Remaining disagreements:\n{json.dumps(evidence, ensure_ascii=False)}"
    )
    schema = _summary_schema(unaligned)
    value = None
    for _ in range(2):
        try:
            prompt_sha256 = hashlib.sha256(prompt.encode()).hexdigest()
            sampled = usage_tracking.api_call(
                run,
                {
                    "run_id": config["run_id"],
                    "iteration": state.get("iteration", 0),
                    "stage": "recursive-summary",
                    "framework": "api",
                    "provider": config["reasoning_trace"]["provider"],
                    "model": config["reasoning_trace"]["model"],
                    "scope": active["id"],
                },
                prompt_sha256,
                lambda: pipeline._sample(config, prompt, schema),
            )
            value = json.loads(sampled.get("output_text") or "")
            value = validate_summary(value, active["scope"], unaligned)
            break
        except Exception as caught:
            prompt += f"\n\nThe previous response was invalid: {caught}. Return corrected JSON."
    if value is None:
        value = {
            "scope": active["scope"],
            "change_summary": [
                "The summary model failed; inspect the saved source diff."
            ],
            "remaining_disagreements": [
                {
                    "case_id": identifier,
                    "rationale": "The available evidence did not establish why this disagreement remained.",
                }
                for identifier in sorted(unaligned)
            ],
        }
    destination = scope_revision_root(run, state) / "summary.json"
    exp.atomic_json(destination, value)
    exp.atomic_json(
        run / "refinement" / scope_slug(active) / "latest.json",
        {
            "revision": int(state.get("recursive_revision", 0)),
            "summary": str(destination.relative_to(run)),
            "fingerprint": scope_fingerprint(after, active),
        },
    )
    return value


def finalize_scope(run: Path, config: dict[str, Any], state: dict[str, Any]) -> None:
    # Accept the valid session, summarize it, and update the dependency work queue.
    from rtdf_formalizer.stages import utils as exp

    root = scope_revision_root(run, state)
    before = root / "analysis/snapshot"
    after = root / "result/snapshot"
    comparison_path = root / "result/tests_bobcat_comparison/summary.json"
    comparison = (
        exp.load_json(comparison_path) if comparison_path.is_file() else {"cases": []}
    )
    summary = generate_summary(run, config, state, comparison, before, after)
    plan = state["recursive_repair_plan"]
    before_scopes = state.get(
        "recursive_before_fingerprints", scope_fingerprints(before, plan)
    )
    after_scopes = scope_fingerprints(after, plan)
    changed = changed_scopes(before_scopes, after_scopes)
    before_helpers = state.get("recursive_before_helper_fingerprints", {})
    after_helpers, after_users = helper_graph(after, plan)
    helper_changes = changed_helpers(before_helpers, after_helpers)
    users = {
        key: set(value)
        for key, value in state.get("recursive_helper_users", {}).items()
    }
    for key, value in after_users.items():
        users.setdefault(key, set()).update(value)
    changed.update(helper_affected_scopes(helper_changes, users))
    requeued = record_processed(state, after_scopes, changed)
    active = state["recursive_active_scope"]
    state["recursive_processed"][active].update(
        {
            "analysis_path": str((root / "result").relative_to(run)),
            "schema_fingerprint": schema_fingerprint(current_scope(state)),
            "summary": str((root / "summary.json").relative_to(run)),
        }
    )
    state["recursive_helper_fingerprints"] = after_helpers
    state["recursive_helper_users"] = {
        key: sorted(value) for key, value in after_users.items()
    }
    state["recursive_last_change_summary"] = summary
    state["recursive_last_requeued"] = sorted(requeued)
    state.pop("recursive_invalidation_reason", None)
    state["recursive_active_scope"] = None
    maximum = int(config.get("repair", {}).get("max_iteration", 2))
    next_scope = activate_next(state)
    while next_scope is not None and int(state["recursive_revision"]) >= maximum:
        state.setdefault("recursive_exhausted", []).append(next_scope["id"])
        state["recursive_active_scope"] = None
        next_scope = activate_next(state)
    if next_scope is None:
        state.update(next_stage="finished", status="completed")
    else:
        state.update(
            next_stage="scope_analysis",
            recursive_step="analysis",
            status="running",
            completed_stages=["initialized"],
        )
        if next_scope["id"] in requeued:
            state["recursive_invalidation_reason"] = (
                "A later scope session changed this scope or a static dependency."
            )
    state["updated_at"] = exp.utc_now()
    exp.atomic_json(run / "state.json", state)


def bundle_report(bundle: Path) -> list[dict[str, Any]]:
    task = json.loads((bundle / "task.json").read_text(encoding="utf-8"))
    scope = task["scope"]
    rows = []
    for identifier in task.get("case_ids", []):
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier)
        case = json.loads(
            (bundle / "cases" / slug / "case.json").read_text(encoding="utf-8")
        )
        rows.append(
            {
                "source": scope["source"],
                "scope": scope["scope"],
                "input": case["input"],
                "output_name": None,
            }
        )
    return rows


def replay(
    report: Path, workspace: Path, *, timeout: int = 600
) -> list[dict[str, Any]]:
    from rtdf_formalizer.stages import utils as exp
    from rtdf_formalizer.bobcat import compiled_json

    rows = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("testing report must be a JSON array")
    if not rows:
        return []
    mappings = exp.load_requirement_outputs(workspace, require_resolved=True)
    by_requirement = {
        entry["requirement_id"]: entry
        for entry in (mappings or {}).get("requirements", [])
    }
    config_file = workspace.parent / "config.json"
    environment = (
        exp.toolchain_environment(exp.load_json(config_file))
        if config_file.is_file()
        else dict(os.environ)
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="rtdf-report-replay-") as temporary:
        project = Path(temporary) / "project"
        exp.copy_project(workspace, project)
        shutil.rmtree(project / ".compiled_scopes", ignore_errors=True)
        try:
            formats = exp.extract_input_formats(
                project, environment=environment, timeout=timeout
            )
            scopes = {(item["file"], item["scope"]): item for item in formats["scopes"]}
            scopes.update(
                {
                    (item["compiler_file"], item["scope"]): item
                    for item in formats["scopes"]
                }
            )
            selected = {
                (row.get("source"), row.get("scope"))
                for row in rows
                if row.get("source") and row.get("scope")
            }
            selected.update(
                (entry["file"], entry["scope"]) for entry in by_requirement.values()
            )
            build_errors = compiled_json.build_bridges(
                project,
                formats,
                environment=environment,
                timeout=timeout,
                selected=selected,
            )
            setup_error = None
        except (
            exp.RunnerError,
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ) as error:
            scopes, build_errors = {}, {}
            setup_error = str(error)
        for index, row in enumerate(rows):
            result = {
                "case_index": index,
                "requirement_id": row.get("requirement_id"),
                "source": row.get("source"),
                "scope": row.get("scope"),
                "input": row["input"],
                "code_execution_output": None,
                "code_execution_error": False,
                "code_execution_diagnostic": None,
            }
            try:
                if setup_error:
                    raise ValueError(setup_error)
                entry = by_requirement.get(row.get("requirement_id"))
                source = entry["file"] if entry else row["source"]
                scope_name = entry["scope"] if entry else row["scope"]
                output_name = entry["output"] if entry else row.get("output_name")
                scope = scopes[(source, scope_name)]
                executable = compiled_json.compiled_path(
                    project, scope["compiler_file"], scope_name
                )
                if not executable.is_file():
                    raise ValueError(
                        build_errors.get(
                            scope["compiler_file"],
                            build_errors.get(
                                f"{scope['compiler_file']}:{scope_name}",
                                "compiled bridge unavailable",
                            ),
                        )
                    )
                completed = subprocess.run(
                    [str(executable), scope_name],
                    cwd=project,
                    env=environment,
                    input=json.dumps(row["input"]) + "\n",
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                )
                if completed.returncode:
                    raise ValueError(
                        f"execution exited {completed.returncode}: {completed.stderr.strip()}"
                    )
                answer = json.loads(completed.stdout)
                if isinstance(answer, dict) and "__bridge_error__" in answer:
                    raise ValueError(str(answer["__bridge_error__"]))
                schema = (
                    compiled_json.named_output_schema(
                        scope["output_schema"], output_name
                    )
                    if output_name
                    else scope["output_schema"]
                )
                projected = (
                    compiled_json.named_answer(answer, output_name)
                    if output_name
                    else answer
                )
                result["code_execution_output"] = compiled_json.project_output_json(
                    projected, schema
                )
                if any(
                    name not in result["code_execution_output"]
                    for name in schema.get("required", [])
                ):
                    raise ValueError(
                        f"execution did not return {output_name or scope_name}"
                    )
            except (
                KeyError,
                TypeError,
                ValueError,
                OSError,
                subprocess.TimeoutExpired,
            ) as error:
                result.update(
                    code_execution_output=None,
                    code_execution_error=True,
                    code_execution_diagnostic=f"{type(error).__name__}: {error}",
                )
            results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--workspace", type=Path, default=Path(__file__).resolve().parent
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        report = args.report.resolve()
        if report.is_dir():
            with tempfile.TemporaryDirectory(prefix="rtdf-scope-replay-") as temporary:
                generated = Path(temporary) / "report.json"
                generated.write_text(
                    json.dumps(bundle_report(report)), encoding="utf-8"
                )
                values = replay(
                    generated, args.workspace.resolve(), timeout=args.timeout
                )
        else:
            values = replay(report, args.workspace.resolve(), timeout=args.timeout)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(values, ensure_ascii=False, indent=2))
    return 0


recursive = sys.modules[__name__]
recursive_repair = recursive


def _resume_controller(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    selected_mode: RepairMode,
    *,
    continue_reasoning: bool,
) -> dict[str, Any]:
    from rtdf_formalizer.stages import formalization, validation
    from rtdf_formalizer.stages import reasoning_trace_diff_fuzzing as pipeline

    if selected_mode is RepairMode.RECURSIVE:
        return _resume_recursive_run(run_directory, config, state)

    if continue_reasoning:
        if selected_mode is not RepairMode.ANSWER_ONLY:
            raise RunnerError("--continue-reasoning requires answer-only repair mode")
        if state["next_stage"] != "reasoning":
            raise RunnerError(
                "--continue-reasoning requires a run paused before reasoning"
            )
        state["reasoning_authorized_iteration"] = int(state["iteration"])
        atomic_json(run_directory / "state.json", state)
    maximum = max_iteration(config)
    while True:
        if not 0 <= int(state["iteration"]) <= maximum:
            raise RunnerError(
                f"repair iteration must be in iter0 through iter{maximum}"
            )
        stage = state["next_stage"]
        if stage == "finished" and state.get("status") == "completed":
            return state
        if stage == "agent":
            formalization.run(run_directory, config, state)
        elif stage == "validation":
            if not validation.run(run_directory, config, state):
                raise RunnerError(
                    "repair requires a dataset with validation/scoring support"
                )
        elif stage in (
            "reasoning_trace_diff_fuzzing",
            "bobcat",
            "compiled_replay",
            "reasoning",
            "comparison",
            "finished",
        ):
            if selected_mode is RepairMode.NO_TESTING:
                if "verification" not in state["completed_stages"]:
                    raise RunnerError(
                        "no-testing repair cannot advance without a validation score"
                    )
                if not advance(run_directory, state, maximum):
                    return state
            elif "comparison" in state["completed_stages"]:
                summary = load_json(
                    run_directory
                    / "iterations"
                    / f"{state['iteration']:03d}"
                    / "tests_bobcat_comparison/summary.json"
                )
                if any(
                    "code_execution_diagnostic" not in row for row in summary["cases"]
                ):
                    summary = pipeline.refresh_completed_comparison(
                        run_directory, state
                    )
                    state["comparison_summary"] = {
                        key: value for key, value in summary.items() if key != "cases"
                    }
                publish_report(run_directory, state, summary)
                if not advance(run_directory, state, maximum):
                    return state
            else:
                pipeline.run(run_directory, config, state)
                if state.get("status") == "awaiting_reasoning":
                    return state
        else:
            raise RunnerError(f"unsupported repair stage: {stage}")
        state = load_json(run_directory / "state.json")


def _resume_recursive_run(
    run_directory: Path, config: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    from rtdf_formalizer.stages import formalization, validation

    # Run one initial formalization followed by scope-local sessions from a dynamic work queue.

    if state.get("recursive_phase") == "scope" and migrate_scope_order(
        run_directory, state
    ):
        atomic_json(run_directory / "state.json", state)

    while True:
        stage = state["next_stage"]
        phase = state.get("recursive_phase", "initial")
        if stage == "finished":
            return state
        if phase == "initial":
            if stage == "agent":
                formalization.run(run_directory, config, state)
            elif stage == "validation":
                if not validation.run(run_directory, config, state):
                    raise RunnerError("recursive repair requires validation support")
            elif stage == "reasoning_trace_diff_fuzzing":
                recursive_repair.initialize(run_directory, config, state)
            else:
                raise RunnerError(f"unsupported initial recursive stage: {stage}")
        elif stage == "scope_analysis":
            plan = state["recursive_repair_plan"]
            state["recursive_before_fingerprints"] = (
                recursive_repair.scope_fingerprints(run_directory / "workspace", plan)
            )
            helper_hashes, helper_users = recursive_repair.helper_graph(
                run_directory / "workspace", plan
            )
            state["recursive_before_helper_fingerprints"] = helper_hashes
            state["recursive_helper_users"] = {
                key: sorted(value) for key, value in helper_users.items()
            }
            state["recursive_step"] = "analysis"
            atomic_json(run_directory / "state.json", state)
            recursive_repair.analyze_scope(run_directory, config, state)
            state.update(
                next_stage="agent",
                recursive_step="session",
                completed_stages=["initialized"],
                status="running",
            )
            atomic_json(run_directory / "state.json", state)
        elif stage == "agent":
            formalization.run(run_directory, config, state)
        elif stage == "validation":
            formalization.commit_agent_result_if_complete(run_directory, state)
            state.update(
                next_stage="scope_result",
                recursive_step="result",
                completed_stages=["initialized", "agent"],
            )
            atomic_json(run_directory / "state.json", state)
        elif stage == "scope_result":
            recursive_repair.analyze_scope(run_directory, config, state)
            state.update(next_stage="scope_finalize", status="analyzed")
            atomic_json(run_directory / "state.json", state)
        elif stage == "scope_finalize":
            recursive_repair.finalize_scope(run_directory, config, state)
        else:
            raise RunnerError(f"unsupported recursive stage: {stage}")
        state = load_json(run_directory / "state.json")


def resume(run_directory, config, state, selected_mode, *, continue_reasoning=False):
    step = state.pop("reasoning_trace_diff_fuzzing_step", None)
    if step is not None:
        state["next_stage"] = step
    result = _resume_controller(
        run_directory,
        config,
        state,
        selected_mode,
        continue_reasoning=continue_reasoning,
    )
    stage = result.get("next_stage")
    if stage not in ("formalization", "validation", "finished"):
        result["reasoning_trace_diff_fuzzing_step"] = stage
        result["next_stage"] = "reasoning_trace_diff_fuzzing"
        atomic_json(run_directory / "state.json", result)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
