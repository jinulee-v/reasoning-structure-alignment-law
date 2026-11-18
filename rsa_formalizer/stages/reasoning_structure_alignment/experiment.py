"""Create a shared provision-generation checkpoint and independent repair forks."""

from __future__ import annotations

import copy
import os
import re
import shlex
import shutil
import uuid
from pathlib import Path

from rsa_formalizer.stages import utils as exp
from .provision_testing import FORMAT, discover_targets
from rsa_formalizer.utils.run_names import repair_name


MODES = ("reasoning_structure_alignment", "baseline_final_answer_only")


def _write_shell(run: Path) -> None:
    config = exp.load_json(run / "config.json")
    module = "main_initial" if config.get("repair", {}).get("mode", "initial_validation") in {"initial_validation", "provision_shared"} else "main_repair"
    command = ("#!/usr/bin/env bash\nset -euo pipefail\n"
               f"cd {shlex.quote(str(exp.ROOT))}\n"
               f"exec .venv/bin/python -m rsa_formalizer.{module} resume {shlex.quote(str(run))}\n")
    script = run / "run.sh"
    script.write_text(command, encoding="utf-8")
    os.chmod(script, 0o755)


def _run_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise exp.RunnerError("invalid run ID")
    return exp.RUNS / name


def prepare_initial(run: Path) -> None:
    """Continue a validated initial run into shared test generation in place."""
    run = run.resolve()
    initial = run / "initial/snapshot"
    if not initial.is_dir() or not (run / "initial/validation/results.json").is_file():
        raise exp.RunnerError("initial validation and snapshot must be complete before test generation")
    config = exp.load_json(run / "config.json")
    if config.get("repair", {}).get("mode") not in {"initial_validation", "provision_shared"}:
        raise exp.RunnerError("initial run has already entered test generation")
    gold = exp.resolve_gold_dataset(config["dataset"]["name"])
    suite = gold / "tests_catala" if gold is not None else None
    if suite is None or not suite.is_dir():
        raise exp.RunnerError("protected Catala tests must be in data/catala_gold/<dataset>/tests_catala")
    base = run / "provision_repair"
    analysis = base / "analysis"
    if not (analysis / "snapshot").exists():
        exp.copy_project(initial, analysis / "snapshot")
    formats = exp.load_json(run / "initial/validation/input_formats.json")["candidate"]
    targets = discover_targets(analysis / "snapshot",
                              exp.load_json(run / "input/RSA_MANIFEST.json"), formats)
    if not targets:
        raise exp.RunnerError("initial formalization has no XML-annotated provision blocks")
    generation = config.get("test_generation", {})
    jobs = generation.get("jobs", 4)
    config.update(shared_generation=True, validation_suite_sha256=exp.tree_hash(suite))
    config.setdefault("prompt_cache", {"enabled": True, "ttl": "30m", "diagnostics": True})
    config["repair"] = {"mode": "provision_shared", "max_attempts_per_provision": 3,
                        "generation_jobs": jobs, "generation_format": FORMAT,
                        "computation_graph_alignment": {"enabled": True,
                            "jobs": generation.get("graph_extraction_jobs", jobs),
                            "max_extraction_attempts": generation.get("max_extraction_attempts", 2)}}
    exp.atomic_json(base / "formats.json", formats)
    exp.atomic_json(analysis / "tests_bobcat_symbolic_results/input_formats.json", formats)
    exp.atomic_json(base / "plan.json", {"targets": targets, "baseline": str(initial),
                    "generation_format": FORMAT, "baseline_sha256": exp.tree_hash(initial)})
    # The state and config are separate durable writes. Resuming a partial transition
    # must enter generation, never repeat initial formalization or validation.
    state = exp.load_json(run / "state.json")
    state.update(status="ready", next_stage="provision_repair", provision_phase="generate",
                 provision_total=len(targets), updated_at=exp.utc_now())
    exp.atomic_json(run / "config.json", config)
    exp.atomic_json(run / "state.json", state)
    _write_shell(run)


def fork(shared: Path, mode: str) -> Path:
    """Copy frozen evidence into one independently resumable repair run."""
    if mode not in MODES:
        raise exp.RunnerError(f"unknown repair mode: {mode}")
    shared = shared.resolve()
    state = exp.load_json(shared / "state.json")
    if state.get("provision_phase") != "fork_ready":
        raise exp.RunnerError("shared generation has not reached the fork checkpoint")
    existing_forks = shared / "forks.json"
    if existing_forks.is_file() and mode in exp.load_json(existing_forks):
        raise exp.RunnerError(f"shared checkpoint already has a {mode} fork")
    source_base = shared / "provision_repair"
    source_config = exp.load_json(shared / "config.json")
    checkpoint_file = source_base / "checkpoint.json"
    if not checkpoint_file.is_file():
        exp.atomic_json(checkpoint_file, {
            "snapshot_sha256": exp.tree_hash(source_base / "analysis/snapshot"),
            "tests_sha256": exp.sha256_file(source_base / "tests.json"),
            "computation_oracles_sha256": exp.sha256_file(source_base / "computation_oracles.json"),
            "validation_suite_sha256": source_config["validation_suite_sha256"],
        })
    checkpoint = exp.load_json(checkpoint_file)
    if (checkpoint["snapshot_sha256"] != exp.tree_hash(source_base / "analysis/snapshot")
            or checkpoint["tests_sha256"] != exp.sha256_file(source_base / "tests.json")
            or checkpoint["computation_oracles_sha256"] != exp.sha256_file(source_base / "computation_oracles.json")):
        raise exp.RunnerError("shared checkpoint evidence changed after generation")
    name = repair_name(shared, mode)
    run = _run_path(name)
    if run.exists():
        raise exp.RunnerError(f"run already exists: {run}")
    staging = exp.RUNS / f".{name}.{uuid.uuid4().hex}.tmp"
    try:
        staging.mkdir(parents=True)
        for part in ("input", "workspace"):
            exp.copy_project(shared / part, staging / part)
        base = staging / "provision_repair"
        analysis = base / "analysis"
        exp.copy_project(source_base / "analysis/snapshot", analysis / "snapshot")
        for part in ("plan.json", "formats.json", "tests.json", "computation_oracles.json"):
            shutil.copy2(source_base / part, base / part)
        shutil.copy2(source_base / "checkpoint.json", base / "checkpoint.json")
        exp.atomic_json(analysis / "tests_bobcat_symbolic_results/input_formats.json",
                        exp.load_json(base / "formats.json"))
        config = copy.deepcopy(source_config)
        config.update(run_id=name, parent_run=str(shared), shared_parent=str(shared), shared_generation=False)
        config["shared_checkpoint"] = checkpoint
        config["repair"]["mode"] = mode
        config["repair"]["require_case_diagnoses"] = True
        config["repair"]["case_diagnoses_scope"] = "remaining"
        if mode == "baseline_final_answer_only":
            config["repair"]["computation_graph_alignment"]["enabled"] = False
        exp.atomic_json(staging / "config.json", config)
        exp.atomic_json(staging / "state.json", {
            "schema_version": exp.SCHEMA_VERSION, "run_id": name,
            "completed_stages": ["initialized"], "status": "ready",
            "recursive_phase": "initial", "next_stage": "provision_repair",
            "provision_phase": "compare", "provision_total": state["provision_total"],
            "shared_checkpoint_sha256": exp.tree_hash(source_base / "analysis/snapshot"),
            "updated_at": exp.utc_now(),
        })
        # Keep each repair inspectable even if its initial run is later archived.
        exp.copy_project(shared / "initial", staging / "initial")
        provenance = staging / "provenance/shared"
        for part in ("config.json", "state.json", "usage.jsonl", "run.log"):
            if (shared / part).is_file():
                provenance.mkdir(parents=True, exist_ok=True)
                shutil.copy2(shared / part, provenance / part)
        for part in ("usage.jsonl", "run.log"):
            if (shared / part).is_file():
                shutil.copy2(shared / part, staging / part)
        for part in ("api_calls", "usage_events"):
            if (shared / part).is_dir():
                shutil.copytree(shared / part, staging / part)
        staging.rename(run)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    forks_path = shared / "forks.json"
    forks = exp.load_json(forks_path) if forks_path.is_file() else {}
    forks[mode] = str(run)
    exp.atomic_json(forks_path, forks)
    if set(forks) == set(MODES):
        script = shared / "run_pair.sh"
        script.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            f"cd {shlex.quote(str(exp.ROOT))}\n"
            + "".join(f"{shlex.quote(forks[item])}/run.sh\n" for item in MODES)
            + f"exec .venv/bin/python -m rsa_formalizer.main_repair pair-summary {shlex.quote(str(shared))}\n",
            encoding="utf-8")
        os.chmod(script, 0o755)
    _write_shell(run)
    return run
