"""Run and cache candidate verification against reference test cases."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from rtdf_formalizer.stages.utils.guidance import semantic_guidance

from ..utils import (
    INPUT_VARIABLE_DESCRIPTION_FILE,
    VERIFICATION_SCHEMA_VERSION,
    RunnerError,
    append_jsonl,
    atomic_copy,
    atomic_json,
    copy_project,
    corpus_test_files,
    extract_input_formats,
    load_json,
    publish_stage_snapshot,
    resolve_gold_dataset,
    run_checked,
    sha256_bytes,
    sha256_file,
    stage_directory,
    stage_endpoint_tests,
    stage_reference_dependencies,
    toolchain_environment,
    tree_hash,
    utc_now,
    validate_input_variable_descriptions,
    validate_requirement_scope_outputs,
    verification_test_directories,
)
from .translator import (
    TRANSLATOR_MODEL,
    generate_translator,
    stage_translator_trial_tool,
)


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
        or case.get("source") not in ("original", "bobcat")
        or case.get("status") not in statuses
        for case in cases
    ):
        raise RunnerError(f"malformed verification case in {path}")
    identifiers = [case["id"] for case in cases]
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(identifiers):
        raise RunnerError(f"verification case IDs are not unique and sorted in {path}")
    counts = {
        status: sum(case["status"] == status for case in cases) for status in statuses
    }
    expected = {
        "total": len(cases),
        "passed": counts["pass"],
        "failed": counts["fail"],
        "errors": counts["error"],
        "skipped": counts["skipped"],
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise RunnerError(f"verification summary counts disagree with cases in {path}")
    denominator = expected["passed"] + expected["failed"]
    expected_accuracy = expected["passed"] / denominator if denominator else None
    if summary.get("accuracy") != expected_accuracy:
        raise RunnerError(f"verification accuracy disagrees with cases in {path}")
    return result


def verification_fingerprint(
    candidate_snapshot: Path,
    gold: Path,
    tests: dict[str, Path | None],
    translator: Path,
    dataset_name: str,
) -> dict[str, Any]:
    guidance = semantic_guidance(dataset_name) or ""
    contract_hash = sha256_bytes(guidance.encode("utf-8"))
    return {
        # Retain the historical field name for version-1 cache compatibility.
        "workspace": tree_hash(candidate_snapshot),
        "reference": tree_hash(gold),
        "original_tests": tree_hash(tests["original"]),
        "bobcat_tests": tree_hash(tests["bobcat"]),
        "translator": sha256_file(translator),
        "semantic_guidance": contract_hash,
        "endpoint_test_files": {
            corpus: list(
                corpus_test_files(dataset_name, tests[corpus], corpus=corpus)
                if tests[corpus] is not None
                else ()
            )
            for corpus in ("original", "bobcat")
        },
    }


def commit_verification_result(
    run_directory: Path,
    state: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if "validation" not in state["completed_stages"]:
        state["completed_stages"].append("validation")
    if "verification" not in state["completed_stages"]:
        state["completed_stages"].append("verification")
    summary = result["summary"]
    state.update(
        next_stage="reasoning_trace_diff_fuzzing",
        status="verified",
        verification_summary=summary,
        active_attempt=None,
        updated_at=utc_now(),
    )
    atomic_json(run_directory / "state.json", state)


def run_verification_stage(
    run_directory: Path,
    config: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    # Typecheck, extract interfaces, translate tests, and compare outputs.
    gold = resolve_gold_dataset(config["dataset"]["name"])
    if gold is None:
        return False
    tests = verification_test_directories(gold)
    if "information_extraction" in config:
        # The free-form-interface experiment is intentionally grounded only in human-authored original cases.
        tests["bobcat"] = None
        if tests["original"] is None or tests["original"].name != "tests_nl":
            raise RunnerError(
                "information extraction requires the conventional tests_nl suite"
            )
    elif tests["original"] is not None and tests["original"].name == "tests_nl":
        raise RunnerError("a tests_nl suite requires information extraction")
    iteration = stage_directory(run_directory, state)
    snapshot = publish_stage_snapshot(run_directory, state)
    validation = iteration / "validation"
    validation.mkdir(parents=True, exist_ok=True)
    translator = run_directory / "translate_test_cases.py"
    result_path = validation / "results.json"
    cache_path = validation / "cache.json"

    if translator.is_file() and result_path.is_file() and cache_path.is_file():
        cached = load_json(cache_path)
        fingerprint = verification_fingerprint(
            snapshot, gold, tests, translator, config["dataset"]["name"]
        )
        if cached.get("fingerprint") == fingerprint:
            result = validate_verification_result(result_path)
            commit_verification_result(run_directory, state, result)
            return True

    environment = toolchain_environment(config)
    timeout = int(config.get("runtime", {}).get("timeout_seconds", 7200))
    with tempfile.TemporaryDirectory(prefix="rtdf-verification-") as temporary_name:
        temporary = Path(temporary_name)
        reference = temporary / "reference_program"
        candidate = temporary / "candidate_program"
        copy_project(gold, reference)
        stage_reference_dependencies(gold, reference)
        copy_project(snapshot, candidate)

        original_tests = temporary / "test_cases/original"
        if tests["original"] is not None:
            if tests["original"].parent == gold:
                original_tests = reference / tests["original"].name
            else:
                stage_endpoint_tests(
                    tests["original"],
                    original_tests,
                    dataset_name=config["dataset"]["name"],
                    corpus="original",
                )
        bobcat_tests = temporary / "test_cases/bobcat"
        if tests["bobcat"] is not None:
            stage_endpoint_tests(
                tests["bobcat"],
                bobcat_tests,
                dataset_name=config["dataset"]["name"],
                corpus="bobcat",
            )

        case_timeout = max(
            1, int(os.environ.get("BENCHMARK_CASE_TIMEOUT_SECONDS", "600"))
        )
        case_count = sum(
            sum(
                1
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if path.suffix == ".jsonl"
            else 1
            for corpus in (original_tests, bobcat_tests)
            if corpus.is_dir()
            for path in (*corpus.rglob("*.json"), *corpus.rglob("*.jsonl"))
        )
        verification_timeout = max(timeout, case_count * (2 * case_timeout) + 1800)

        reference_format = extract_input_formats(
            reference, environment=environment, timeout=timeout
        )
        candidate_format = extract_input_formats(
            candidate, environment=environment, timeout=timeout
        )
        requirement_outputs = validate_requirement_scope_outputs(
            candidate, candidate_format
        )
        input_variable_descriptions = None
        if (candidate / INPUT_VARIABLE_DESCRIPTION_FILE).is_file():
            input_variable_descriptions = validate_input_variable_descriptions(
                candidate, candidate_format, requirement_outputs
            )
        atomic_json(temporary / "reference_format.json", reference_format)
        atomic_json(temporary / "candidate_format.json", candidate_format)
        trial_tool = stage_translator_trial_tool(temporary)
        atomic_json(
            validation / "input_formats.json",
            {"reference": reference_format, "candidate": candidate_format},
        )
        if requirement_outputs is not None:
            atomic_json(validation / "requirement_outputs.json", requirement_outputs)
        if input_variable_descriptions is not None:
            atomic_json(
                validation / "input_variable_descriptions.json",
                input_variable_descriptions,
            )

        if "information_extraction" in config:
            from . import information_extraction

            if not original_tests.is_dir() or not any(original_tests.glob("*.json")):
                raise RunnerError(
                    f"no NL test cases found for {config['dataset']['name']}"
                )
            records = information_extraction.extract(
                run_directory,
                config,
                state,
                candidate,
                candidate_format,
                original_tests,
                validation,
                requirement_outputs=requirement_outputs,
                input_variable_descriptions=input_variable_descriptions,
            )
            result = information_extraction.evaluate(
                records,
                candidate,
                candidate_format,
                environment=environment,
                timeout=case_timeout,
            )
            atomic_json(result_path, result)
            validate_verification_result(result_path)
            for stage in ("validation", "information_extraction", "verification"):
                if stage not in state["completed_stages"]:
                    state["completed_stages"].append(stage)
            state.update(
                next_stage="reasoning_trace_diff_fuzzing",
                status="verified",
                verification_summary=result["summary"],
                active_attempt=None,
                updated_at=utc_now(),
            )
            atomic_json(run_directory / "state.json", state)
            return True

        neutral_input_hashes = (
            tree_hash(reference),
            tree_hash(candidate),
            tree_hash(original_tests if original_tests.is_dir() else None),
            tree_hash(bobcat_tests if bobcat_tests.is_dir() else None),
            sha256_file(temporary / "reference_format.json"),
            sha256_file(temporary / "candidate_format.json"),
            sha256_file(trial_tool),
        )
        translator_metadata_path = validation / "translator.json"
        translator_metadata = (
            load_json(translator_metadata_path)
            if translator_metadata_path.is_file()
            else {}
        )
        guidance = semantic_guidance(config["dataset"]["name"]) or ""
        semantic_guidance_hash = sha256_bytes(guidance.encode("utf-8"))
        test_contract_hash = sha256_bytes(
            (
                f"original={tree_hash(original_tests if original_tests.is_dir() else None)}\n"
                f"bobcat={tree_hash(bobcat_tests if bobcat_tests.is_dir() else None)}\n"
            ).encode("utf-8")
        )
        if (
            not translator.is_file()
            or translator_metadata.get("semantic_guidance") != semantic_guidance_hash
            or translator_metadata.get("test_contract") != test_contract_hash
        ):
            metadata = generate_translator(
                temporary,
                translator,
                timeout=verification_timeout,
                artifact_directory=validation,
                environment=environment,
                dataset_name=config["dataset"]["name"],
            )
            metadata["semantic_guidance"] = semantic_guidance_hash
            metadata["test_contract"] = test_contract_hash
            atomic_json(translator_metadata_path, metadata)
            usage_record = {
                "run_id": config["run_id"],
                "iteration": state["iteration"],
                "stage": "test-translation",
                "framework": "codex",
                "provider": "openai",
                "model": TRANSLATOR_MODEL,
                "request_id": None,
                "elapsed_seconds": metadata["elapsed_seconds"],
                **metadata["usage"],
                "recorded_at": utc_now(),
            }
            append_jsonl(run_directory / "usage.jsonl", usage_record)
            if not (temporary / "translate_test_cases.py").is_file():
                shutil.copy2(translator, temporary / "translate_test_cases.py")
        else:
            shutil.copy2(translator, temporary / "translate_test_cases.py")
            try:
                compile(translator.read_text(encoding="utf-8"), translator.name, "exec")
            except (OSError, SyntaxError) as error:
                raise RunnerError(
                    f"cached test translator is invalid: {error}"
                ) from error
        if neutral_input_hashes != (
            tree_hash(reference),
            tree_hash(candidate),
            tree_hash(original_tests if original_tests.is_dir() else None),
            tree_hash(bobcat_tests if bobcat_tests.is_dir() else None),
            sha256_file(temporary / "reference_format.json"),
            sha256_file(temporary / "candidate_format.json"),
            sha256_file(trial_tool),
        ):
            raise RunnerError(
                "translator-generation agent modified a verification input"
            )

        # Build typed JSON decoders from the candidate schema for compiled OCaml scopes.
        from rtdf_formalizer.bobcat.compiled_json import (
            build_bridges,
            translated_scope_pairs,
        )

        selected_scopes = translated_scope_pairs(
            temporary / "translate_test_cases.py",
            [original_tests, bobcat_tests],
            environment=environment,
            timeout=case_timeout,
        )
        bridge_errors = build_bridges(
            candidate,
            candidate_format,
            environment=environment,
            timeout=case_timeout,
            selected=selected_scopes,
        )
        atomic_json(
            validation / "compiled_bridges.json",
            {
                "errors": bridge_errors,
                "selected_endpoints": len(selected_scopes),
                "built": sum(
                    1
                    for path in (candidate / ".compiled_scopes").rglob("*")
                    if path.is_symlink()
                )
                if (candidate / ".compiled_scopes").is_dir()
                else 0,
            },
        )

        temporary_result = temporary / "results.json"
        run_checked(
            [
                sys.executable,
                str(trial_tool),
                "--output",
                str(temporary_result),
            ],
            cwd=temporary,
            environment=environment,
            timeout=verification_timeout,
        )
        result = validate_verification_result(temporary_result)
        atomic_copy(temporary_result, result_path)

    fingerprint = verification_fingerprint(
        snapshot, gold, tests, translator, config["dataset"]["name"]
    )
    atomic_json(
        cache_path,
        {
            "schema_version": VERIFICATION_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            "created_at": utc_now(),
        },
    )
    commit_verification_result(run_directory, state, result)
    return True


def run(run_directory: Path, config: dict[str, Any], state: dict[str, Any]) -> bool:
    from ..formalization import commit_agent_result_if_complete

    commit_agent_result_if_complete(run_directory, state)
    return run_verification_stage(run_directory, config, state)
