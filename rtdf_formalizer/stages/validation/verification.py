"""Verify candidates with protected, Prolog-derived Catala test scopes."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..utils import (
    VERIFICATION_SCHEMA_VERSION,
    RunnerError,
    atomic_json,
    copy_project,
    extract_input_formats,
    load_json,
    publish_stage_snapshot,
    stage_directory,
    toolchain_environment,
    tree_hash,
    utc_now,
    validate_requirement_scope_outputs,
)

TEST_SCOPE = re.compile(r"(?m)^#\[test\]\s*\ndeclaration scope (\w+):")


def validate_verification_result(path: Path) -> dict[str, Any]:
    result = load_json(path)
    cases, summary = result.get("cases"), result.get("summary")
    if result.get("schema_version") != VERIFICATION_SCHEMA_VERSION:
        raise RunnerError(f"unsupported verification result schema in {path}")
    if not isinstance(cases, list) or not isinstance(summary, dict):
        raise RunnerError(f"malformed verification result in {path}")
    statuses = ("pass", "fail", "error", "skipped")
    if any(
        not isinstance(case, dict)
        or not isinstance(case.get("id"), str)
        or case.get("source") != "original"
        or case.get("status") not in statuses
        for case in cases
    ):
        raise RunnerError(f"malformed verification case in {path}")
    identifiers = [case["id"] for case in cases]
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(identifiers):
        raise RunnerError(f"verification case IDs are not unique and sorted in {path}")
    counts = {status: sum(case["status"] == status for case in cases) for status in statuses}
    expected = {
        "total": len(cases), "passed": counts["pass"], "failed": counts["fail"],
        "errors": counts["error"], "skipped": counts["skipped"],
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise RunnerError(f"verification summary counts disagree with cases in {path}")
    denominator = expected["passed"] + expected["failed"]
    if summary.get("accuracy") != (expected["passed"] / denominator if denominator else None):
        raise RunnerError(f"verification accuracy disagrees with cases in {path}")
    return result


def verification_fingerprint(snapshot: Path, tests: Path) -> dict[str, Any]:
    return {
        "runner": "native-catala-v1",
        "workspace": tree_hash(snapshot),
        "catala_tests": tree_hash(tests),
    }


def commit_verification_result(run_directory: Path, state: dict[str, Any], result: dict[str, Any]) -> None:
    for stage in ("validation", "verification"):
        if stage not in state["completed_stages"]:
            state["completed_stages"].append(stage)
    state.update(
        next_stage="reasoning_trace_diff_fuzzing",
        status="verified",
        verification_summary=result["summary"],
        updated_at=utc_now(),
    )
    atomic_json(run_directory / "state.json", state)


def _declared_tests(files: list[Path]) -> dict[tuple[str, str], str]:
    expected: dict[tuple[str, str], str] = {}
    for path in files:
        for scope in TEST_SCOPE.findall(path.read_text(encoding="utf-8")):
            key = (path.name, scope)
            if key in expected:
                raise RunnerError(f"duplicate Catala test scope: {path.name}::{scope}")
            expected[key] = f"original:{path.name}::{scope}"
    if not expected:
        raise RunnerError("Catala test suite contains no #[test] scopes")
    return expected


def _json_report(output: str) -> dict[str, Any] | None:
    marker = '{"test-results"'
    start = output.find(marker)
    if start < 0:
        return None
    try:
        report, _ = json.JSONDecoder().raw_decode(output[start:])
    except json.JSONDecodeError:
        return None
    return report if isinstance(report, dict) else None


def _test_records(
    report: dict[str, Any] | None,
    expected: dict[tuple[str, str], str],
    diagnostic: str,
) -> list[dict[str, Any]]:
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for file_result in (report or {}).get("test-results", []):
        name = Path(file_result.get("file", "")).name
        for test in file_result.get("tests", {}).get("scopes", []):
            key = (name, test.get("scope_name"))
            if key in expected:
                errors = test.get("errors") or []
                observed[key] = {
                    "status": "pass" if test.get("success") else "fail",
                    "detail": "; ".join(str(item.get("message", item)) for item in errors) or None,
                }
    return [
        {
            "id": identifier,
            "source": "original",
            "status": observed.get(key, {}).get("status", "error"),
            "detail": observed.get(key, {}).get("detail")
                if key in observed else diagnostic[-4000:] or "Catala test was not run",
        }
        for key, identifier in sorted(expected.items(), key=lambda item: item[1])
    ]


def run_verification_stage(
    run_directory: Path, config: dict[str, Any], state: dict[str, Any]
) -> bool:
    source = Path(config["dataset"]["source"]).resolve()
    tests = source / "tests_catala"
    files = sorted(tests.glob("*.catala_*")) if tests.is_dir() else []
    if not files:
        raise RunnerError(f"dataset has no Catala test cases: {tests}")
    expected = _declared_tests(files)
    stage_root = stage_directory(run_directory, state)
    snapshot = publish_stage_snapshot(run_directory, state)
    validation = stage_root / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    result_path = validation / "results.json"
    cache_path = validation / "cache.json"
    fingerprint = verification_fingerprint(snapshot, tests)
    if cache_path.is_file() and result_path.is_file():
        if load_json(cache_path).get("fingerprint") == fingerprint:
            commit_verification_result(
                run_directory, state, validate_verification_result(result_path)
            )
            return True

    environment = toolchain_environment(config)
    timeout = int(config.get("runtime", {}).get("timeout_seconds", 7200))
    with tempfile.TemporaryDirectory(prefix="rtdf-catala-verification-") as name:
        candidate = Path(name) / "candidate"
        copy_project(snapshot, candidate)
        candidate_format = extract_input_formats(
            candidate, environment=environment, timeout=timeout
        )
        requirement_outputs = validate_requirement_scope_outputs(
            candidate, candidate_format
        )
        atomic_json(validation / "input_formats.json", {
            "reference": None, "candidate": candidate_format,
        })
        if requirement_outputs is not None:
            atomic_json(validation / "requirement_outputs.json", requirement_outputs)
        for path in files:
            destination = candidate / path.name
            if destination.exists():
                raise RunnerError(f"Catala test collides with candidate file: {path.name}")
            shutil.copy2(path, destination)
        command = ["clerk", "test", *[path.name for path in files], "--json", "--color=never"]
        try:
            completed = subprocess.run(
                command, cwd=candidate, env=environment, text=True,
                capture_output=True, timeout=timeout,
            )
            diagnostic = (completed.stdout + "\n" + completed.stderr).strip()
            report = _json_report(completed.stdout)
        except (OSError, subprocess.TimeoutExpired) as error:
            diagnostic = str(error)
            report = None
        records = _test_records(report, expected, diagnostic)
        atomic_json(validation / "catala_report.json", report or {
            "error": diagnostic[-4000:]
        })
    counts = {status: sum(row["status"] == status for row in records)
              for status in ("pass", "fail", "error", "skipped")}
    denominator = counts["pass"] + counts["fail"]
    result = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "cases": records,
        "summary": {
            "total": len(records), "passed": counts["pass"],
            "failed": counts["fail"], "errors": counts["error"],
            "skipped": counts["skipped"],
            "accuracy": counts["pass"] / denominator if denominator else None,
        },
    }
    atomic_json(result_path, result)
    validate_verification_result(result_path)
    atomic_json(cache_path, {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "created_at": utc_now(),
    })
    commit_verification_result(run_directory, state, result)
    return True


def run(run_directory: Path, config: dict[str, Any], state: dict[str, Any]) -> bool:
    from ..formalization import commit_agent_result_if_complete

    commit_agent_result_if_complete(run_directory, state)
    return run_verification_stage(run_directory, config, state)
