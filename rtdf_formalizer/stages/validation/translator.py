"""Generate and exercise adapters between reference and candidate tests."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from rtdf_formalizer.stages.utils.guidance import semantic_guidance

from ..utils import (
    TRANSLATOR_MODEL,
    RunnerError,
    atomic_copy,
    extract_usage,
    load_json,
    sha256_file,
)


def translator_prompt(dataset_name: str | None = None) -> str:
    guidance = semantic_guidance(dataset_name) if dataset_name else None
    semantic_contract = (
        "\n\nThe candidate was given this semantic interface guidance:\n\n"
        f"{guidance}\n\nUse this guidance when implementing "
        "`reference_to_candidate` in `translate_test_cases.py`.\n"
        if guidance
        else ""
    )
    return (
        """Write `translate_test_cases.py` in the current directory.

You are comparing two independently supplied Catala 1.2 programs. The neutral
directory names are intentional; do not inspect paths outside this temporary
directory and do not use git, the network, or author metadata. `reference_program/`
is the ground-truth implementation and `candidate_program/` is the implementation
under evaluation. Their compiler-extracted scope JSON schemas are in
`reference_format.json` and `candidate_format.json`.

The schemas describe JSON-callable boundaries, not the programs' semantics.
Inspect both Catala sources when scopes have been split, combined, or expose
different levels of abstraction. In particular, an original-test `target` can
be a corpus label rather than a Catala scope name; select its reference scope
from its input/output shape and the source. A single reference call may require
an equivalent candidate scope at a different conceptual level. A candidate
scope with `schema_error` is not directly JSON-executable; do not pretend that
it can be tested through the JSON runner.

Inspect Catala-native types in both source declarations and extracted schemas
before coding conversions. JSON may encode a payload-free enum constructor as
a string and a payload-bearing constructor as a one-key object. A date payload
is a `year`/`month`/`day` object, not part of the constructor's string name.
Likewise, check the declared JSON shapes of durations, exact money/decimals,
options, records, lists, and nested variants; preserve their payloads and
numeric meaning. Decode the constructor first, then map it and its payload.
Never use the entire one-key object as a dictionary lookup key, drop a date
payload, or fabricate a date to satisfy the candidate schema.

Your goal is the broadest *faithful* adapter the candidate's public inputs and
outputs permit. Audit every reference test shape and enum constructor against
both programs before marking a case unsupported. Differently named constructors,
records, and predicates are not evidence of missing behavior. Translate enum
payloads field by field, including entity identifiers encoded elsewhere in a
candidate record, and preserve links between related facts. Check whether a
reference predicate assertion can be represented as a candidate input fact,
whether a query can be projected from a broader output, and whether several
candidate calls can together establish the queried result. Use a comparison
marker for a multi-call composition only if the host trial tool already supports
it, and validate each component call. Never infer inputs from an expected
answer or reimplement statutory rules in Python.

For each apparent gap, inspect concrete worlds as well as type declarations:
record which reference fields/constructors are used, where each maps in the
candidate schema, and which relationships or dates would be lost. Reject only
the cases whose needed facts or queried result truly cannot be represented.
Run the trial on the full original and BOBCat corpora, inspect skipped and
errored case diagnostics, and revise avoidable conversion failures before
finishing. A skipped case is not a model failure and must carry a precise
structural reason; a candidate execution error must be checked for an adapter
schema error before being attributed to the candidate.

Before rejecting a reference value because its fields differ, inspect which
facts are relevant for this concrete test's known inputs. A reference may
carry separate ordinary and Mayotte residency flags while the candidate has
one regular-stay flag. If residence selects one reference flag, map the active
flag and ignore the inactive one; do not require them to be equal. Only reject
when no semantics-preserving contextual projection can be justified from the
reference and candidate sources. Do not infer a legal outcome from expected
outputs to choose the mapping.

Implement a deterministic (no model calls, randomness, time-dependent decisions,
or network access) Python 3 program with one operation:

  python3 translate_test_cases.py --reference-test 'SINGLE_JSON_OBJECT'

`--reference-test` maps one ground-truth test to one candidate test. Parse that
one test and print exactly one translated test as JSON to stdout. Do not iterate
over test directories, execute Catala, compare results, write result files, or
print commentary. The host runner owns those operations and starts fresh
translator subprocesses.

Both input and output use BOBCat's exact six-field test format: `target`, `path`,
`inputs`, `outputs`, `error`, and `exact`. The input is a reference-program test.
The output is its equivalent concrete candidate-program test:

* `target`: an exact candidate scope name;
* `path`: that scope's candidate `compiler_file`, relative to
  `candidate_program/`;
* `inputs`: JSON accepted by that candidate scope;
* `outputs`: the expected candidate output, or a nested field projection when
  the reference test covers one result exposed inside a broader candidate scope;
* `error`: the expected candidate error, normally null; and
* `exact`: whether comparison must be exact.

Preserve the reference test's meaning and money/decimal exactness. Never obtain
the expected output by running the candidate. The fixed files
`reference_format.json`, `candidate_format.json`, `reference_program/`, and
`candidate_program/` are available beside the script for analysis. Load them
relative to `__file__`; they are not CLI arguments. If the candidate has no
concrete executable equivalent, exit nonzero with a precise diagnostic instead
of fabricating inputs or expected outputs. Candidate self-test/conformance scopes
such as zero-input `Test*` scopes are not equivalents of input-dependent
reference tests and must not be used as substitutes. Finish only after
syntax-checking the script and running `--help`. Implement the mapping as an
explicit `reference_to_candidate` function and have the CLI call it. The
mapping need not be invertible: do not add hidden provenance or perturb
semantic values to make it reversible.
After every substantive change, run:

  python3 .verification_tools/run_translator_trial.py

This host-owned test-execution tool invokes the current script once per reference
test, executes each translated test concretely against the candidate Catala
program, and compares its actual output with the translated expected output. It
returns the corpus summary and diagnostics (success/failure/error rates).
Use that feedback to fix avoidable mappings. Your final action must be a
successful trial of the final script. The tool owns its scratch result and trial
receipt. Apart from those tool-owned files, create or modify only
`translate_test_cases.py`.
"""
        + semantic_contract
    )


TRANSLATOR_TRIAL_TOOL = r'''#!/usr/bin/env python3
"""Translate tests one-by-one, execute candidate Catala, and compare outputs."""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parent.parent
TOOL_DIR = Path(__file__).resolve().parent
FIELDS = {"target", "path", "inputs", "outputs", "error", "exact"}
WORKER = threading.local()
CASE_TIMEOUT_SECONDS = max(1, int(os.environ.get("BENCHMARK_CASE_TIMEOUT_SECONDS", "600")))


def candidate_directory():
    if not hasattr(WORKER, "candidate"):
        source = ROOT / "candidate_program"
        destination = ROOT / ".verification_tools" / f"candidate_worker_{threading.get_ident()}"
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("_build"))
        WORKER.candidate = destination
    return WORKER.candidate


class UnsupportedReference(RuntimeError):
    """The candidate has no semantics-preserving JSON call for this case."""
    pass


def jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def normalize(value):
    if isinstance(value, dict):
        return tuple((key, normalize(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(normalize(item) for item in value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return ("number", Decimal(str(value)))
    if isinstance(value, str):
        try:
            if "/" in value:
                numerator, denominator = value.split("/", 1)
                return ("number", Decimal(numerator) / Decimal(denominator))
            return ("number", Decimal(value))
        except (InvalidOperation, ValueError, ZeroDivisionError):
            return value
    return value


def equivalent(left, right):
    if left == right:
        return True
    if (isinstance(left, tuple) and isinstance(right, tuple)
            and len(left) == len(right) == 2
            and left[0] == right[0] == "number"):
        # OCaml exact money may appear with a binary float tail such as 99.45999999999999.
        return abs(left[1] - right[1]) <= Decimal("0.000000000001")
    return (isinstance(left, tuple) and isinstance(right, tuple)
            and len(left) == len(right)
            and all(equivalent(a, b) for a, b in zip(left, right)))


def project_actual(actual, expected):
    if isinstance(expected, dict) and set(expected) == {"__claimed_taxable_income__"}:
        if not isinstance(actual, dict) or "taxable_income" not in actual:
            raise RuntimeError("candidate taxable income output is missing")
        claim = expected["__claimed_taxable_income__"]["claimed_amount"]
        return {"__claimed_taxable_income__": {
            "claimed_amount": claim,
            "verdict": Decimal(str(actual["taxable_income"])) == Decimal(str(claim)),
        }}
    if isinstance(expected, dict) and set(expected) == {"__s3301_verdict__"}:
        if not isinstance(actual, dict) or not {"is_employer", "tax"} <= set(actual):
            raise RuntimeError("candidate unemployment output lacks employer or tax")
        claim = expected["__s3301_verdict__"]["claimed_tax"]
        observed = Decimal(str(actual["tax"])).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return {"__s3301_verdict__": {
            "claimed_tax": claim,
            "verdict": bool(actual["is_employer"]) and observed == Decimal(str(claim)),
        }}
    if isinstance(expected, dict) and set(expected) == {"__rounded_tax_components__"}:
        if not isinstance(actual, dict) or not {"income_tax", "unemployment_tax"} <= set(actual):
            raise RuntimeError("candidate tax output lacks both tax components")
        whole = Decimal("1")
        total = sum(
            Decimal(str(actual[field])).quantize(whole, rounding=ROUND_HALF_UP)
            for field in ("income_tax", "unemployment_tax")
        )
        return {"__rounded_tax_components__": str(total)}
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise RuntimeError("candidate output is not an object required by projection")
        missing = sorted(set(expected) - set(actual))
        if missing:
            raise RuntimeError(f"candidate output lacks projected fields: {missing}")
        return {key: project_actual(actual[key], value) for key, value in expected.items()}
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            # Preserve list-shape mismatches for the comparator.
            return actual
        return [project_actual(item, wanted) for item, wanted in zip(actual, expected)]
    return actual


def parse_json(text):
    return json.loads(text, parse_float=Decimal)


def parse_process_json(text):
    try:
        return parse_json(text.strip())
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        try:
            return parse_json(line.strip())
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder(parse_float=Decimal)
    for offset, character in reversed(list(enumerate(text))):
        if character not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[offset:])
            if not text[offset + end:].strip():
                return value
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("no JSON value in process output", text, 0)


def rows():
    for source_name in ("original", "bobcat"):
        directory = ROOT / "test_cases" / source_name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.jsonl")):
            relative = path.relative_to(directory).as_posix()
            with path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    yield source_name, relative, line_number, parse_json(line)


def stable_id(source, relative, line_number, row):
    encoded = json.dumps(jsonable(row), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:12]
    return f"{source}:{relative}:{line_number}:{digest}"


def translate(translator, reference_test):
    encoded = json.dumps(jsonable(reference_test), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    completed = subprocess.run(
        [sys.executable, str(translator), "--reference-test", encoded],
        cwd=ROOT, text=True, capture_output=True, timeout=CASE_TIMEOUT_SECONDS
    )
    if completed.returncode == 3:
        raise UnsupportedReference((completed.stderr or completed.stdout).strip())
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"translator failed ({completed.returncode}): {detail[-2000:]}")
    try:
        translated = parse_json(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"translator stdout is not one JSON object: {error}") from error
    if not isinstance(translated, dict) or set(translated) != FIELDS:
        raise RuntimeError("translated test must contain exactly the six BOBCat fields")
    if not isinstance(translated["target"], str) or not translated["target"]:
        raise RuntimeError("translated target must be a non-empty candidate scope")
    if not isinstance(translated["path"], str) or not translated["path"]:
        raise RuntimeError("translated path must be a non-empty candidate source path")
    if reference_test.get("inputs") and not translated.get("inputs"):
        raise RuntimeError(
            "an input-dependent reference test cannot become a zero-input candidate test"
        )
    return translated


def execute_candidate(test, force_interpreter=False):
    if test["target"] == "__all_false_is_qualifying_child__":
        calls = test["inputs"].get("calls")
        if not isinstance(calls, list):
            raise RuntimeError("dependency composition requires a call list")
        observed = []
        for call in calls:
            result, _ = execute_candidate({
                **test, "target": "DependencyEligibility", "inputs": call,
                "outputs": {"is_qualifying_child": False},
            })
            if not isinstance(result, dict) or "is_qualifying_child" not in result:
                raise RuntimeError("dependency output lacks qualifying-child result")
            observed.append(bool(result["is_qualifying_child"]))
        return {"all_false": not any(observed)}, None
    relative = Path(test["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("translated path must stay within candidate_program")
    compiled = (ROOT / "candidate_program" / ".compiled_scopes"
                / relative.with_suffix("") / test["target"])
    if force_interpreter:
        compiled = ROOT / "candidate_program" / ".compiled_scopes" / "__disabled__"
    candidate = ROOT / "candidate_program" if compiled.is_file() else candidate_directory()
    source = candidate / relative
    if not source.is_file():
        raise RuntimeError(f"candidate source does not exist: {test['path']}")
    command = ([str(compiled), test["target"]] if compiled.is_file() else [
        "clerk", "run", relative.as_posix(), "--scope", test["target"],
        "--input", "-", "--output-format=json", "--color=never",
    ])
    process = subprocess.Popen(
        command, cwd=candidate, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=os.environ.copy(), start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            json.dumps(jsonable(test["inputs"]), ensure_ascii=False),
            timeout=CASE_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if completed.returncode:
        if compiled.is_file():
            return execute_candidate(test, force_interpreter=True)
        detail = (completed.stderr or completed.stdout).strip()
        if test["error"] is not None:
            return None, detail
        raise RuntimeError(f"candidate execution failed ({completed.returncode}): {detail[-2000:]}")
    if test["error"] is not None:
        raise RuntimeError("candidate succeeded but translated test expected an error")
    try:
        result = parse_process_json(completed.stdout)
        if isinstance(result, dict) and "__bridge_error__" in result:
            return execute_candidate(test, force_interpreter=True)
        return result, None
    except json.JSONDecodeError as error:
        raise RuntimeError(f"candidate stdout is not JSON: {error}") from error


def run_all():
    translator = ROOT / "translate_test_cases.py"
    if not translator.is_file():
        raise RuntimeError("translate_test_cases.py does not exist")
    def evaluate_one(row):
        source, relative, line_number, reference_test = row
        record = {
            "id": stable_id(source, relative, line_number, reference_test),
            "source": source,
            "status": "error",
            "reference_output": jsonable(reference_test.get("outputs")),
            "candidate_output": None,
            "detail": None,
        }
        try:
            if not isinstance(reference_test, dict) or set(reference_test) != FIELDS:
                raise RuntimeError("reference test does not have the six BOBCat fields")
            candidate_test = translate(translator, reference_test)
            record["reference_output"] = jsonable(candidate_test["outputs"])
            actual, actual_error = execute_candidate(candidate_test)
            record["candidate_output"] = jsonable(actual)
            if candidate_test["error"] is not None:
                record["status"] = "pass"
                record["detail"] = actual_error
            elif equivalent(
                normalize(project_actual(actual, candidate_test["outputs"])),
                normalize(candidate_test["outputs"]),
            ):
                record["status"] = "pass"
            else:
                record["status"] = "fail"
                record["detail"] = "candidate output differs from translated expected output"
        except UnsupportedReference as error:
            record["status"] = "skipped"
            record["detail"] = str(error)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            record["detail"] = f"{type(error).__name__}: {error}"
        return record

    # Bound concurrent Catala interpreters for small hosts.
    jobs = max(1, min(32, int(os.environ.get("TRANSLATOR_TRIAL_JOBS", "1"))))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(evaluate_one, rows()))
    cases.sort(key=lambda case: case["id"])
    counts = collections.Counter(case["status"] for case in cases)
    denominator = counts["pass"] + counts["fail"]
    return {
        "schema_version": 1,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "errors": counts["error"],
            "skipped": counts["skipped"],
            "accuracy": counts["pass"] / denominator if denominator else None,
        },
    }


def write_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = run_all()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.output:
        write_atomic(Path(args.output), result)
    diagnostics = collections.Counter(
        str(case["detail"]) for case in result["cases"]
        if case["status"] in ("error", "skipped")
    )
    feedback = {
        "expected_cases": result["summary"]["total"],
        "summary": result["summary"],
        "common_diagnostics": [
            {"count": count, "detail": detail[:1000]}
            for detail, count in diagnostics.most_common(10)
        ],
    }
    translator = ROOT / "translate_test_cases.py"
    receipt = {
        **feedback,
        "translator_sha256": hashlib.sha256(translator.read_bytes()).hexdigest(),
    }
    write_atomic(TOOL_DIR / "trial_receipt.json", receipt)
    print(json.dumps(feedback, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def stage_translator_trial_tool(temporary: Path) -> Path:
    tool = temporary / ".verification_tools/run_translator_trial.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(TRANSLATOR_TRIAL_TOOL, encoding="utf-8")
    tool.chmod(0o555)
    return tool


def generate_translator(
    temporary: Path,
    destination: Path,
    *,
    timeout: int,
    artifact_directory: Path,
    environment: dict[str, str] | None = None,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    # Generate one run-specific translator without exposing run provenance.
    codex = shutil.which("codex")
    if codex is None:
        raise RunnerError(
            "Codex executable is required to generate the test translator"
        )
    prompt = translator_prompt(dataset_name)
    stdout = artifact_directory / "translator_codex.jsonl"
    stderr = artifact_directory / "translator_codex.stderr.log"
    command = [
        codex,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--model",
        TRANSLATOR_MODEL,
        "--cd",
        str(temporary),
        "-",
    ]
    started = time.monotonic()
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            process = subprocess.run(
                command,
                input=prompt.encode("utf-8"),
                stdout=out,
                stderr=err,
                timeout=timeout,
                env=environment,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RunnerError(f"Codex translator generation failed: {error}") from error
    if process.returncode:
        raise RunnerError(
            f"Codex translator generation failed; see temporary log {stderr}"
        )
    generated = temporary / "translate_test_cases.py"
    if not generated.is_file():
        raise RunnerError("Codex completed without creating translate_test_cases.py")
    compile(generated.read_text(encoding="utf-8"), generated.name, "exec")
    receipt_path = temporary / ".verification_tools/trial_receipt.json"
    if not receipt_path.is_file():
        raise RunnerError(
            "Codex translator generation finished without a full-corpus trial"
        )
    receipt = load_json(receipt_path)
    if receipt.get("translator_sha256") != sha256_file(generated):
        raise RunnerError("Codex did not trial the final translator version")
    atomic_copy(generated, destination)
    usage = extract_usage(stdout, prompt)
    return {
        "model": TRANSLATOR_MODEL,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "sha256": sha256_file(destination),
        "usage": usage,
    }
