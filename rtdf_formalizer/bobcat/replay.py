"""Compiled replay of generated BOBCat cases."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rtdf_formalizer.stages import utils as exp
from . import compiled_json
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
) -> list[dict[str, Any]]:
    iteration = exp.stage_directory(run_directory, state)
    root = iteration / "tests_bobcat_symbolic_results"
    root.mkdir(parents=True, exist_ok=True)
    cached = [(root / f"{case['id']}.json") for case in cases]
    dependency_cache = root / "dependency_graphs.json"
    dependency_error_cache = root / "dependency_errors.json"
    if (
        cases
        and dependency_cache.is_file()
        and dependency_error_cache.is_file()
        and all(
            path.is_file()
            and exp.load_json(path).get("execution_tree") is not None
            and exp.load_json(path).get("dynamic_slice_tree") is not None
            and not exp.load_json(path).get("dynamic_slice_error")
            and exp.load_json(path).get("dynamic_slice_schema_version")
            == DYNAMIC_SLICE_SCHEMA_VERSION
            and exp.load_json(path).get("dependency_semantics")
            == DYNAMIC_SLICE_DEPENDENCY_SEMANTICS
            for path in cached
        )
    ):
        outputs = []
        for case, path in zip(cases, cached):
            output = exp.load_json(path)
            if output.get("source") != case["source"]:
                output["source"] = case["source"]
                exp.atomic_json(path, output)
            outputs.append(output)
        persist_execution_forests(root, outputs)
        return outputs
    project = root / "project"
    if not project.is_dir():
        exp.copy_project(iteration / "snapshot", project)
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
    outputs = []
    for case in cases:
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
        ):
            if cached_result.get("source") != case["source"]:
                cached_result["source"] = case["source"]
                exp.atomic_json(destination, cached_result)
            outputs.append(cached_result)
            continue
        executable = compiled_json.compiled_path(
            project, case["source"], case["target"]
        )
        result = {
            "id": case["id"],
            "source": case["source"],
            "target": case["target"],
            "inputs": case["inputs"],
            "branches": case["branches"],
            "statute_ids": case["statute_ids"],
            "output": None,
            "error": None,
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
                            iteration / "snapshot",
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
        exp.atomic_json(destination, result)
        outputs.append(result)
    persist_execution_forests(root, outputs)
    return outputs


run = replay_compiled
