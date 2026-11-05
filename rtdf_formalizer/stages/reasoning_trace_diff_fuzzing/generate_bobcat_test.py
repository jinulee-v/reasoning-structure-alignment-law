"""BOBCat case generation for Catala scopes."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from bobcat_scripts.bobcatlib import parse, paths as bobcat_paths, run as bobcat_run
from rtdf_formalizer.stages import utils as exp
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing import repair
from rtdf_formalizer.bobcat.trace import (
    _root_object_properties,
    provision_path,
    schema_scopes,
    scope_records,
    target_name,
)


def _all_scopes(
    run_directory: Path,
    snapshot: Path,
    iteration: Path,
    config: dict[str, Any],
    *,
    include_unusable: bool = False,
) -> list[dict[str, Any]]:
    cached = iteration / "validation/input_formats.json"
    if not cached.is_file() and repair.mode(config) is repair.RepairMode.RECURSIVE:
        cached = run_directory / "initial/validation/input_formats.json"
    if cached.is_file():
        formats = exp.load_json(cached)["candidate"]
        return scope_records(formats) if include_unusable else schema_scopes(formats)
    project = iteration / "tests_bobcat_symbolic_results/project"
    if not project.is_dir():
        exp.copy_project(snapshot, project)
        gold = exp.resolve_gold_dataset(config["dataset"]["name"])
        if gold is not None:
            exp.stage_reference_dependencies(gold, project)
    formats = exp.extract_input_formats(
        project,
        environment=exp.toolchain_environment(config),
        timeout=int(config["runtime"].get("timeout_seconds", 7200)),
    )
    exp.atomic_json(
        iteration / "tests_bobcat_symbolic_results/input_formats.json", formats
    )
    return scope_records(formats) if include_unusable else schema_scopes(formats)


def generate_tests(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
    options: dict[str, Any],
) -> list[dict[str, Any]]:
    iteration = exp.stage_directory(run_directory, state)
    snapshot = (
        exp.publish_stage_snapshot(run_directory, state)
        if state.get("recursive_phase")
        else exp.publish_iteration_snapshot(run_directory, int(state["iteration"]))
    )
    root = iteration / "tests_bobcat"
    root.mkdir(parents=True, exist_ok=True)
    requested = options.get("_scope_record")
    scopes = _all_scopes(
        run_directory,
        snapshot,
        iteration,
        config,
        include_unusable=requested is not None,
    )
    if requested is not None:
        scopes = [
            scope
            for scope in scopes
            if scope.get("scope") == requested["scope"]
            and (scope.get("compiler_file") or scope.get("file")) == requested["source"]
        ]
        if not scopes:
            scopes = [dict(requested, compiler_file=requested["source"])]
        else:
            scopes = [{**scopes[0], **requested, "compiler_file": requested["source"]}]
        scope = scopes[0]
        input_properties = _root_object_properties(scope.get("input_schema"))
        output_properties = _root_object_properties(scope.get("output_schema"))
        if input_properties is None or not output_properties:
            exp.atomic_json(
                root / "scopes.json",
                {
                    "scopes": scopes,
                    "snapshot_sha256": exp.tree_hash(snapshot),
                    "no_cases_reason": scope.get("schema_error")
                    or "scope has no observable JSON output",
                },
            )
            return []
    if not scopes:
        raise exp.RunnerError(
            f"model snapshot has no scopes with nonempty input and output records: {snapshot}"
        )
    exp.atomic_json(
        root / "scopes.json",
        {"scopes": scopes, "snapshot_sha256": exp.tree_hash(snapshot)},
    )
    port = (
        re.sub(r"[^A-Za-z0-9_-]", "_", config["dataset"]["name"]).strip("_")
        or "dataset"
    )
    previous_root = os.environ.get("BOBCAT_CAMPAIGN_ROOT")
    os.environ["BOBCAT_CAMPAIGN_ROOT"] = str(root)
    try:
        for scope in scopes:
            source = scope["compiler_file"]
            output = scope.get("output")
            name = target_name(source, scope["scope"], output)
            result_file = root / f"{name}.json"
            if result_file.is_file():
                continue
            harness = snapshot / source
            target = bobcat_run.Target(
                name=name,
                port=port,
                harness=harness,
                scope=scope["scope"],
                output=output,
                positive_hundred_money_inputs=bool(
                    options["bobcat_positive_hundred_money_inputs"]
                ),
                max_list_length=(
                    int(options["bobcat_max_list_length"])
                    if options["bobcat_max_list_length"] is not None
                    else None
                ),
                representation_capacity=int(options["bobcat_representation_capacity"]),
                solver_timeout_ms=(
                    int(options["bobcat_solver_timeout_ms"])
                    if options["bobcat_solver_timeout_ms"] is not None
                    else None
                ),
                solver_timeout_max_ms=(
                    int(options["bobcat_solver_timeout_max_ms"])
                    if options["bobcat_solver_timeout_max_ms"] is not None
                    else None
                ),
                objective_timeout_ms=(
                    int(options["bobcat_objective_timeout_ms"])
                    if options["bobcat_objective_timeout_ms"] is not None
                    else None
                ),
                modules=[
                    path for path in exp.catala_sources(snapshot) if path != harness
                ],
                include_dirs=bobcat_paths.extra_include_dirs(port),
                timeout=int(options["bobcat_timeout_seconds"]),
                project=name,
            )
            try:
                project = bobcat_run.prepare_project(target)
                outcome = bobcat_run.run_bobcat(target, project)
                parsed = parse.parse_run(outcome.stdout, outcome.stderr)
                rows = [
                    {
                        "id": f"{name}:{path.index}",
                        "target": scope["scope"],
                        **({"output_name": output} if output else {}),
                        **(
                            {"requirement_id": scope["requirement_id"]}
                            if scope.get("requirement_id")
                            else {}
                        ),
                        "source": source,
                        "inputs": {
                            key: value.as_json() for key, value in path.inputs.items()
                        },
                        "branches": path.branches,
                        "statute_ids": provision_path(snapshot, path.branches),
                        "exact": path.exact,
                        **({"kind": path.kind} if path.kind else {}),
                        **({"bobcat_error": path.error} if path.error else {}),
                    }
                    for path in parsed.paths
                ]
                record = {
                    "scope": scope,
                    "command": outcome.command,
                    "returncode": outcome.returncode,
                    "timed_out": outcome.timed_out,
                    "elapsed_seconds": outcome.seconds,
                    "finished": parsed.finished,
                    "incomplete": parsed.incomplete,
                    "branch_manifest": parsed.branch_manifest,
                    "objectives": [
                        {
                            "objective": objective.objective,
                            "status": objective.status,
                            **(
                                {"input": objective.input}
                                if objective.input is not None
                                else {}
                            ),
                            **(
                                {"validated": objective.validated}
                                if objective.validated is not None
                                else {}
                            ),
                            **(
                                {"reason": objective.reason}
                                if objective.reason is not None
                                else {}
                            ),
                        }
                        for objective in parsed.objectives
                    ],
                    "unparsed": parsed.unparsed,
                    "cases": rows,
                }
                capture = root / "raw"
                capture.mkdir(exist_ok=True)
                (capture / f"{name}.stdout").write_text(
                    outcome.stdout, encoding="utf-8"
                )
                (capture / f"{name}.stderr").write_text(
                    outcome.stderr, encoding="utf-8"
                )
            except Exception as error:
                record = {
                    "scope": scope,
                    "error": f"{type(error).__name__}: {error}",
                    "cases": [],
                }
            exp.atomic_json(result_file, record)
    finally:
        if previous_root is None:
            os.environ.pop("BOBCAT_CAMPAIGN_ROOT", None)
        else:
            os.environ["BOBCAT_CAMPAIGN_ROOT"] = previous_root
    result_files = [
        root
        / f"{target_name(scope['compiler_file'], scope['scope'], scope.get('output'))}.json"
        for scope in scopes
    ]
    cases = []
    for scope, path in zip(scopes, result_files):
        if not path.is_file():
            continue
        record = exp.load_json(path)
        for original in record.get("cases", []):
            case = dict(original)
            if scope.get("requirement_id"):
                case["requirement_id"] = scope["requirement_id"]
                case["output_name"] = scope["output"]
                # Two requirements may intentionally share a scope/output.
                if result_files.count(path) > 1:
                    suffix = hashlib.sha256(
                        scope["requirement_id"].encode()
                    ).hexdigest()[:12]
                    case["id"] = f"{original['id']}:req-{suffix}"
            cases.append(case)
    missing = []
    for scope, path in zip(scopes, result_files):
        record = exp.load_json(path) if path.is_file() else {}
        if not record.get("cases"):
            missing.append(
                f"{scope['compiler_file']}::{scope['scope']}"
                + (f" ({record['error']})" if record.get("error") else "")
            )
    if missing and requested is None:
        raise exp.RunnerError(
            "BOBCat did not generate a test case for every eligible scope: "
            + "; ".join(missing)
            + f"; inspect {root}"
        )
    return cases


run = generate_tests
