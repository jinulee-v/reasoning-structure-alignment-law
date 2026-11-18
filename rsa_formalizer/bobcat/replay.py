"""Compiled replay of generated BOBCat cases."""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rsa_formalizer.stages import utils as exp
from . import compiled_json
from .compact_trace import FORMAT as COMPACT_FORMAT, annotated_scopes
from .records import ReplayRecords
from .trace import (
    DYNAMIC_SLICE_DEPENDENCY_SEMANTICS,
    DYNAMIC_SLICE_METHOD,
    DYNAMIC_SLICE_SCHEMA_VERSION,
    dependency_edges,
    execution_tree,
    execution_tree_events,
    persist_execution_forests,
    schema_scopes,
    slice_execution_tree,
    traced_provision_path,
)


_CASE_METADATA = (
    "target_provision",
    "input_authority",
    "case_origin",
    "test_strategy",
    "test_rationale",
    "natural_language_facts",
    "natural_language_question",
    "generated_expected_answer",
    "generated_reasoning_tree",
    "generated_design_id",
    "mapped_provision_ids",
)


def _sync_case_metadata(result: dict[str, Any], case: dict[str, Any]) -> bool:
    changed = False
    for key in _CASE_METADATA:
        value = case.get(key)
        if result.get(key) != value:
            result[key] = value
            changed = True
    return changed


def _compiler_dependencies(
    project: Path, source: str, environment: dict[str, str], timeout: int
) -> dict[str, dict[str, set[str]]]:
    catala = shutil.which("catala", path=environment.get("PATH"))
    if not catala:
        raise RuntimeError("catala unavailable for dependency extraction")
    completed = subprocess.run(
        [
            catala,
            "dependency-graph",
            source,
            "--stdlib",
            "_build/libcatala",
            "--color=never",
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError((completed.stdout + completed.stderr)[-3000:])
    return dependency_edges(json.loads(completed.stdout))


def replay_compiled(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    bridge_timeout_seconds: int = 600,
) -> list[dict[str, Any]]:
    jobs = config.get("execution", {}).get("replay_jobs", 4)
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError("execution.replay_jobs must be a positive integer")
    stage_root = exp.stage_directory(run_directory, state)
    root = stage_root / "tests_bobcat_symbolic_results"
    root.mkdir(parents=True, exist_ok=True)
    cached = [(root / f"{case['id']}.json") for case in cases]
    mode = config.get("execution", {}).get("replay_trace_mode", "xml_scopes")
    if mode not in {"xml_scopes", "full"}:
        raise ValueError(f"unknown replay trace mode: {mode}")
    trace_format = COMPACT_FORMAT if mode == "xml_scopes" else "full"
    trace_scopes = annotated_scopes(stage_root / "snapshot") if mode == "xml_scopes" else None
    dependency_cache = root / "dependency_graphs.json"
    dependency_error_cache = root / "dependency_errors.json"

    def complete_cached_case(path: Path) -> bool:
        if not path.is_file():
            return False
        result = exp.load_json(path)
        return (
            result.get("execution_tree") is not None
            and result.get("dynamic_slice_tree") is not None
            and not result.get("dynamic_slice_error")
            and result.get("dynamic_slice_schema_version") == DYNAMIC_SLICE_SCHEMA_VERSION
            and result.get("dependency_semantics") == DYNAMIC_SLICE_DEPENDENCY_SEMANTICS
            and result.get("replay_trace_format", "full") == trace_format
        )

    if (
        cases
        and dependency_cache.is_file()
        and dependency_error_cache.is_file()
        and all(complete_cached_case(path) for path in cached)
    ):
        for case, path in zip(cases, cached):
            output = exp.load_json(path)
            changed = _sync_case_metadata(output, case)
            if output.get("source") != case["source"]:
                output["source"] = case["source"]
                changed = True
            if changed:
                exp.atomic_json(path, output)
        outputs = ReplayRecords(cached)
        persist_execution_forests(root, outputs)
        return outputs
    project = root / "project"
    if not project.is_dir():
        exp.copy_project(stage_root / "snapshot", project)
        gold = exp.resolve_gold_dataset(config["dataset"]["name"])
        if gold is not None:
            exp.stage_reference_dependencies(gold, project)
    formats_file = root / "input_formats.json"
    if formats_file.is_file():
        formats = exp.load_json(formats_file)
    else:
        formats = exp.extract_input_formats(
            project,
            environment=exp.toolchain_environment(config),
            timeout=int(config["runtime"].get("timeout_seconds", 7200)),
        )
        exp.atomic_json(formats_file, formats)
    selected = {(case["source"], case["target"]) for case in cases}
    environment = exp.toolchain_environment(config)
    timeout = int(config["runtime"].get("timeout_seconds", 7200))
    errors = compiled_json.build_bridges(
        project,
        {**formats, "scopes": schema_scopes(formats)},
        environment=environment,
        selected=selected,
        trace_scopes=trace_scopes,
        timeout=bridge_timeout_seconds,
    )
    exp.atomic_json(root / "build_errors.json", errors)
    graphs: dict[str, dict[str, dict[str, set[str]]]] = {}
    dependency_errors: dict[str, str] = {}
    for source in sorted({case["source"] for case in cases}):
        try:
            graphs[source] = _compiler_dependencies(
                project, source, environment, timeout
            )
        except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as error:
            dependency_errors[source] = f"{type(error).__name__}: {error}"
    exp.atomic_json(
        root / "dependency_graphs.json",
        {
            source: {
                scope: {
                    variable: sorted(dependencies)
                    for variable, dependencies in variables.items()
                }
                for scope, variables in source_graph.items()
            }
            for source, source_graph in graphs.items()
        },
    )
    exp.atomic_json(root / "dependency_errors.json", dependency_errors)

    def replay_case(case: dict[str, Any]) -> None:
        # Bridges and dependency graphs are built once before workers start.
        # Each worker owns its subprocess, trace objects, and per-case JSON file.
        destination = root / f"{case['id']}.json"
        if destination.is_file():
            cached_result = exp.load_json(destination)
        else:
            cached_result = {}
        if (
            cached_result.get("execution_tree") is not None
            and cached_result.get("dynamic_slice_tree") is not None
            and not cached_result.get("dynamic_slice_error")
            and cached_result.get("dynamic_slice_schema_version")
            == DYNAMIC_SLICE_SCHEMA_VERSION
            and cached_result.get("dependency_semantics")
            == DYNAMIC_SLICE_DEPENDENCY_SEMANTICS
            and cached_result.get("replay_trace_format", "full") == trace_format
        ):
            changed = _sync_case_metadata(cached_result, case)
            if cached_result.get("source") != case["source"]:
                cached_result["source"] = case["source"]
                changed = True
            if changed:
                exp.atomic_json(destination, cached_result)
            return
        executable = compiled_json.compiled_path(
            project, case["source"], case["target"]
        )
        result = {
            "id": case["id"],
            "target_provision": case.get("target_provision"),
            "input_authority": case.get("input_authority"),
            "source": case["source"],
            "target": case["target"],
            "inputs": case["inputs"],
            "branches": case["branches"],
            "statute_ids": case["statute_ids"],
            "case_origin": case.get("case_origin", "bobcat"),
            "test_strategy": case.get("test_strategy"),
            "test_rationale": case.get("test_rationale"),
            "natural_language_facts": case.get("natural_language_facts"),
            "natural_language_question": case.get("natural_language_question"),
            "generated_expected_answer": case.get("generated_expected_answer"),
            "generated_reasoning_tree": case.get("generated_reasoning_tree"),
            "generated_design_id": case.get("generated_design_id"),
            "mapped_provision_ids": case.get("mapped_provision_ids"),
            "output": None,
            "error": None,
            "replay_trace_format": trace_format,
            "dynamic_slice_schema_version": DYNAMIC_SLICE_SCHEMA_VERSION,
            "dynamic_slice_method": DYNAMIC_SLICE_METHOD,
        }
        if case.get("output_name"):
            result["output_name"] = case["output_name"]
        if case.get("requirement_id"):
            result["requirement_id"] = case["requirement_id"]
        if not executable.is_file():
            result["error"] = "compiled OCaml bridge unavailable"
        else:
            try:
                completed = subprocess.run(
                    [str(executable), case["target"], "--trace"],
                    cwd=project,
                    input=json.dumps(case["inputs"], ensure_ascii=False) + "\n",
                    text=True,
                    capture_output=True,
                    timeout=600,
                    env=environment,
                )
                result["execution"] = {
                    "command": [str(executable), case["target"], "--trace"],
                    "returncode": completed.returncode,
                    "stderr": completed.stderr,
                }
                if completed.returncode:
                    result["error"] = (
                        f"compiled execution exited {completed.returncode}"
                    )
                else:
                    observed = json.loads(completed.stdout.strip())
                    if (
                        isinstance(observed, dict)
                        and "events" in observed
                        and "result" in observed
                    ):
                        result["output"] = observed["result"]
                        if (
                            observed.get("dependency_semantics")
                            != DYNAMIC_SLICE_DEPENDENCY_SEMANTICS
                        ):
                            raise ValueError(
                                "trace lacks complete condition/call instrumentation; rebuild bridge and replay"
                            )
                        result["dependency_semantics"] = observed[
                            "dependency_semantics"
                        ]
                        tree = execution_tree(observed["events"], deduplicate=False)
                        result["execution_tree"] = tree
                        result["dynamic_slice_tree"] = slice_execution_tree(
                            tree,
                            case["target"],
                            case.get("output_name"),
                            graphs.get(case["source"], {}),
                        )
                        result["statute_ids"] = traced_provision_path(
                            stage_root / "snapshot",
                            execution_tree_events(result["dynamic_slice_tree"]),
                            case["target"],
                            case["source"],
                        )
                    elif (
                        isinstance(observed, dict)
                        and "trace" in observed
                        and "result" in observed
                    ):
                        raise ValueError(
                            "legacy trace has incomplete dependencies; rebuild and replay"
                        )
                    else:
                        if (
                            isinstance(observed, dict)
                            and "__bridge_error__" in observed
                        ):
                            result["output"] = observed
                        else:
                            raise ValueError(
                                "compiled execution returned no dependency trace"
                            )
                    if (
                        isinstance(result["output"], dict)
                        and "__bridge_error__" in result["output"]
                    ):
                        result["error"] = result["output"]["__bridge_error__"]
                        result["output"] = None
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                result["error"] = f"{type(error).__name__}: {error}"
                result["dynamic_slice_error"] = result["error"]
        exp.atomic_json(destination, result, indent=None)
        # Do not retain case-sized traces in futures or the coordinator.
        del result, cached_result
        completed = observed = tree = None

    if jobs == 1:
        for number, case in enumerate(cases, 1):
            replay_case(case)
            print(f"Catala replay {number}/{len(cases)}: {case['id']}", flush=True)
    elif cases:
        with ThreadPoolExecutor(max_workers=min(jobs, len(cases))) as executor:
            futures = {executor.submit(replay_case, case): case["id"] for case in cases}
            for number, future in enumerate(as_completed(futures), 1):
                future.result()
                print(f"Catala replay {number}/{len(cases)}: {futures[future]}", flush=True)
    # Completion order may vary; disk-backed results retain the input case order.
    outputs = ReplayRecords(cached)
    persist_execution_forests(root, outputs)
    return outputs


run = replay_compiled
