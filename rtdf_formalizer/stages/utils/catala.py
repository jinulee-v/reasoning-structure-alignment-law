"""Catala project discovery, execution, schemas, and test staging."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rtdf_formalizer.stages.utils.guidance import endpoint_test_files
from .common import (
    ROOT,
    SCOPE_DECLARATION,
    VERIFICATION_SCHEMA_VERSION,
    RunnerError,
    relative_files,
)


def toolchain_environment(config: dict[str, Any]) -> dict[str, str]:
    # Return the host environment needed by the frozen Catala toolchain.
    environment = os.environ.copy()
    configured = config.get("runtime", {}).get("host_toolchain")
    toolchain = Path(configured) if configured else ROOT / ".toolchain"
    prefixes = [
        toolchain / "opam/catala/bin",
        toolchain / "envs/catala/bin",
    ]
    environment["PATH"] = os.pathsep.join(
        [str(path) for path in prefixes if path.is_dir()]
        + [environment.get("PATH", "")]
    )
    library = toolchain / "envs/catala/lib"
    if library.is_dir():
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            (str(library), environment.get("LD_LIBRARY_PATH", ""))
        )
    return environment


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise RunnerError(f"verification executable not found: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RunnerError(
            f"verification command timed out after {timeout}s: {' '.join(command)}"
        ) from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RunnerError(
            f"verification command failed ({result.returncode}): "
            f"{' '.join(command)}\n{detail[-4000:]}"
        )
    return result


def catala_sources(project: Path) -> list[Path]:
    # Return program modules, excluding generated builds and test fixtures.
    sources = list(
        path
        for path in project.glob("*.catala_*")
        if path.is_file() and not path.is_symlink()
    )
    wrappers = project / "verification_wrappers"
    if wrappers.is_dir():
        sources.extend(
            path
            for path in wrappers.glob("*.catala_*")
            if path.is_file() and not path.is_symlink()
        )
    return sorted(sources)


def declared_scopes(source: Path) -> list[str]:
    return SCOPE_DECLARATION.findall(
        source.read_text(encoding="utf-8", errors="replace")
    )


def included_files(source: Path) -> set[str]:
    return set(
        re.findall(
            r"^[ \t]*>[ \t]*(?:Inclusion|Include)[ \t]*:[ \t]*([^\r\n]+)",
            source.read_text(encoding="utf-8", errors="replace"),
            re.MULTILINE,
        )
    )


def stage_reference_dependencies(gold: Path, reference: Path) -> None:
    # Copy known upstream modules needed by the French example projects.
    if gold.name not in ("aides_logement", "allocations_familiales"):
        return
    # Clerk deliberately ignores underscore-prefixed source directories.
    external = reference / "verification_includes"
    examples = ROOT / ".port/catala_examples_source"
    for name in (
        "base_mensuelle_allocations_familiales",
        "smic",
        "prologue_france",
        "prestations_familiales",
    ):
        source = examples / name
        if not source.is_dir():
            raise RunnerError(f"missing reference dependency: {source}")
        copy_project(source, external / name)
    if gold.name == "aides_logement":
        source = ROOT / "data/catala_gold/allocations_familiales"
        if not source.is_dir():
            raise RunnerError(f"missing reference dependency: {source}")
        copy_project(source, external / "allocations_familiales")


def project_include_directories(project: Path) -> list[Path]:
    external = project / "verification_includes"
    return [project] + (
        sorted(path for path in external.iterdir() if path.is_dir())
        if external.is_dir()
        else []
    )


def write_verification_clerk_config(project: Path) -> None:
    relative_includes = [
        path.relative_to(project).as_posix()
        for path in project_include_directories(project)
    ]
    rendered = ", ".join(json.dumps(path) for path in relative_includes)
    (project / "clerk.toml").write_text(
        "# Generated in an isolated verification copy.\n"
        "[project]\n"
        'build_dir = "_build"\n'
        'target_dir = "_targets"\n'
        f"include_dirs = [{rendered}]\n",
        encoding="utf-8",
    )


def extract_json_value(output: str) -> Any:
    # Read the JSON value even if Clerk printed build progress before it.
    decoder = json.JSONDecoder()
    for index, character in enumerate(output):
        if character not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if not output[index + end :].strip():
            return value
    raise RunnerError("Catala json-schema produced no parseable JSON value")


def extract_input_formats(
    project: Path,
    *,
    environment: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    # Ask Catala for the exact JSON input/output schema of every root scope.
    sources = catala_sources(project)
    if not sources:
        raise RunnerError(f"Catala project has no root source modules: {project}")
    clerk = shutil.which("clerk", path=environment.get("PATH"))
    catala = shutil.which("catala", path=environment.get("PATH"))
    if not clerk or not catala:
        raise RunnerError("the validation toolchain must provide both clerk and catala")

    write_verification_clerk_config(project)
    included = {name for source in sources for name in included_files(source)}
    masters = [source for source in sources if source.name not in included]
    includes = project_include_directories(project)
    clerk_include_args = [
        value for path in includes for value in ("--include", str(path))
    ]

    run_checked(
        [clerk, "start", "--color=never"],
        cwd=project,
        environment=environment,
        timeout=timeout,
    )
    run_checked(
        [
            clerk,
            "typecheck",
            *[path.relative_to(project).as_posix() for path in masters],
            *clerk_include_args,
            "--color=never",
        ],
        cwd=project,
        environment=environment,
        timeout=timeout,
    )
    scopes: list[dict[str, Any]] = []
    for source in sources:
        compiler_source = source
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
            compiler_source = owners[0]
        for scope in declared_scopes(source):
            entry: dict[str, Any] = {
                "file": source.relative_to(project).as_posix(),
                "compiler_file": compiler_source.relative_to(project).as_posix(),
                "scope": scope,
            }
            try:
                result = run_checked(
                    [
                        clerk,
                        "json-schema",
                        compiler_source.relative_to(project).as_posix(),
                        "--scope",
                        scope,
                        *clerk_include_args,
                        "--whole-program",
                        "--color=never",
                    ],
                    cwd=project,
                    environment=environment,
                    timeout=timeout,
                )
                schemas = extract_json_value(result.stdout)
                if not isinstance(schemas, list) or len(schemas) != 2:
                    raise RunnerError(
                        f"unexpected json-schema result for {source.name}:{scope}"
                    )
                entry.update(input_schema=schemas[0], output_schema=schemas[1])
            except RunnerError as error:
                # Catala intentionally refuses JSON schemas for scopes with higher-order values.
                entry.update(
                    input_schema=None, output_schema=None, schema_error=str(error)
                )
            scopes.append(entry)
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "project_files": [path.relative_to(project).as_posix() for path in sources],
        "scopes": scopes,
    }


def resolve_gold_dataset(dataset_name: str) -> Path | None:
    root = ROOT / "data/catala_gold"
    direct = root / dataset_name
    if direct.is_dir():
        return direct
    normalized = dataset_name.casefold().replace("-", "_")
    matches = (
        [
            path
            for path in root.iterdir()
            if path.is_dir() and path.name.casefold().replace("-", "_") == normalized
        ]
        if root.is_dir()
        else []
    )
    return matches[0] if len(matches) == 1 else None


def verification_test_directories(gold: Path) -> dict[str, Path | None]:
    # Locate pre-existing tests only; BOBCat generation is deliberately elsewhere.
    conventional = [gold / name for name in ("tests_nl", "tests_catala")]
    available = [path for path in conventional if path.is_dir()]
    if len(available) > 1:
        raise RunnerError(
            f"dataset has multiple primary test suites: {', '.join(map(str, available))}"
        )
    # Never consume `.port/<dataset>/test_cases` here: those directories also contain fuzzing/mutation outputs.
    original = available[0] if available else None
    bobcat = gold / "tests_bobcat"
    return {
        "original": original,
        "bobcat": bobcat if bobcat.is_dir() else None,
    }


def copy_project(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("_build", "_targets", ".git", "__pycache__"),
    )


def corpus_test_files(
    dataset_name: str, source: Path, *, corpus: str
) -> tuple[str, ...]:
    # Select complete original corpora and public-endpoint BOBCat corpora.
    if corpus == "original":
        return tuple(
            path.name
            for pattern in ("*.json", "*.jsonl")
            for path in sorted(source.glob(pattern))
        )
    if corpus == "bobcat":
        return endpoint_test_files(dataset_name, source)
    raise RunnerError(f"unknown verification corpus: {corpus}")


def stage_endpoint_tests(
    source: Path,
    destination: Path,
    *,
    dataset_name: str,
    corpus: str,
) -> None:
    # Copy the selected files for one frozen verification corpus.
    selected = corpus_test_files(dataset_name, source, corpus=corpus)
    destination.mkdir(parents=True)
    for filename in selected:
        candidate = source / filename
        if not candidate.is_file():
            raise RunnerError(
                f"endpoint test selection names a missing {corpus} file: {candidate}"
            )
        shutil.copy2(candidate, destination / filename)


def tree_hash(directory: Path | None) -> str | None:
    if directory is None:
        return None
    digest = hashlib.sha256()
    ignored = {"_build", "_targets", ".git", "__pycache__"}
    for relative, path in sorted(relative_files(directory).items()):
        if any(part in ignored for part in Path(relative).parts):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
