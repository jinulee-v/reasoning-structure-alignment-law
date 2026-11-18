"""Prune reproducible replay data after a provision repair has finished.

The frozen cases, input schemas, Catala snapshots, reasoning oracles, reports,
review verdicts, and held-out results remain in the run. `restore` reruns the
same public cases against a retained snapshot when a trace is needed again.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rsa_formalizer.bobcat.replay import replay_compiled
from rsa_formalizer.stages import utils as exp
from . import provision_testing


def _stages(run: Path) -> list[Path]:
    base = run / "provision_repair"
    stages = [base / "analysis", base / "evaluation"]
    reviews = base / "session" / "candidate_reviews"
    if reviews.is_dir():
        stages.extend(sorted(p for p in reviews.glob("attempt-*") if p.is_dir()))
    return [p for p in stages if (p / "snapshot").is_dir()]


def prune_completed(run: Path) -> dict:
    """Delete only replay artifacts that can be recreated from frozen inputs."""
    run = run.resolve()
    state = exp.load_json(run / "state.json")
    if state.get("status") != "completed" or state.get("provision_phase") != "finished":
        raise exp.RunnerError("replay artifacts may be pruned only after a completed run")
    base = run / "provision_repair"
    if not (base / "summary.json").is_file():
        raise exp.RunnerError("missing completed provision summary")
    for name in ("executable_tests.json", "computation_oracles.json"):
        if not (base / name).is_file():
            raise exp.RunnerError(f"cannot reproduce replay without {name}")

    stages = _stages(run)
    manifest_path = base / "artifact_retention.json"
    prior = exp.load_json(manifest_path) if manifest_path.is_file() else None
    manifest = {
        "schema_version": 1,
        "method": "replay_compiled from retained Catala snapshots and executable_tests.json",
        "recorded_at": prior["recorded_at"] if prior else exp.utc_now(),
        "last_pruned_at": exp.utc_now(),
        "config_sha256": exp.sha256_file(run / "config.json"),
        "cases_sha256": exp.sha256_file(base / "executable_tests.json"),
        "oracles_sha256": exp.sha256_file(base / "computation_oracles.json"),
        "stages": {},
        "removed_files": prior["removed_files"] if prior else 0,
        "removed_bytes": prior["removed_bytes"] if prior else 0,
        "last_removed_files": 0,
        "last_removed_bytes": 0,
    }
    for stage in stages:
        key = str(stage.relative_to(run))
        manifest["stages"][key] = {"snapshot_sha256": exp.tree_hash(stage / "snapshot")}
    if prior:
        for key in ("config_sha256", "cases_sha256", "oracles_sha256", "stages"):
            if prior[key] != manifest[key]:
                raise exp.RunnerError(f"cannot prune changed recovery input: {key}")
    # Write the recovery recipe before removing anything. A retry is safe.
    exp.atomic_json(manifest_path, manifest)

    def remove_file(path: Path) -> None:
        if path.is_file():
            manifest["removed_files"] += 1
            manifest["removed_bytes"] += path.stat().st_size
            manifest["last_removed_files"] += 1
            manifest["last_removed_bytes"] += path.stat().st_size
            path.unlink()

    def remove_tree(path: Path) -> None:
        if path.is_dir():
            files = [item for item in path.rglob("*") if item.is_file()]
            size = sum(item.stat().st_size for item in files)
            manifest["removed_bytes"] += size
            manifest["removed_files"] += len(files)
            manifest["last_removed_bytes"] += size
            manifest["last_removed_files"] += len(files)
            shutil.rmtree(path)

    for stage in stages:
        replay = stage / "tests_bobcat_symbolic_results"
        if replay.is_dir():
            for path in replay.glob("*.json"):
                if path.name not in {"input_formats.json", "build_errors.json",
                                     "dependency_graphs.json", "dependency_errors.json"}:
                    remove_file(path)
            remove_tree(replay / "project")
        for name in ("tests_bobcat_comparison", "tests_final_answer_comparison"):
            remove_tree(stage / name)
        if stage.parent.name == "candidate_reviews":
            remove_file(stage / "comparison.json")

    for feedback in (base / "feedback", base / "evaluation" / "feedback"):
        if feedback.is_dir():
            for path in feedback.rglob("catala_replay.json"):
                remove_file(path)
    exp.atomic_json(manifest_path, manifest)
    return manifest


def restore(run: Path, stage_name: str) -> dict:
    """Regenerate one pruned stage and its feedback copies, when applicable."""
    run = run.resolve()
    base = run / "provision_repair"
    manifest = exp.load_json(base / "artifact_retention.json")
    if exp.sha256_file(run / "config.json") != manifest["config_sha256"]:
        raise exp.RunnerError("run config changed since artifact pruning")
    cases_path = base / "executable_tests.json"
    if exp.sha256_file(cases_path) != manifest["cases_sha256"]:
        raise exp.RunnerError("frozen executable tests changed since artifact pruning")
    if exp.sha256_file(base / "computation_oracles.json") != manifest["oracles_sha256"]:
        raise exp.RunnerError("frozen computation oracles changed since artifact pruning")
    if stage_name in {"analysis", "evaluation"}:
        stage = base / stage_name
    elif stage_name.startswith("attempt-") and stage_name.removeprefix("attempt-").isdigit():
        stage = base / "session" / "candidate_reviews" / stage_name
    else:
        raise exp.RunnerError(f"unknown replay stage: {stage_name}")
    key = str(stage.relative_to(run))
    expected = manifest["stages"].get(key)
    if not expected or exp.tree_hash(stage / "snapshot") != expected["snapshot_sha256"]:
        raise exp.RunnerError("Catala snapshot missing or changed since artifact pruning")

    config = exp.load_json(run / "config.json")
    results = exp.load_json(cases_path)["results"]
    retained = [test for result in results for test in provision_testing.accepted_tests(result)]
    cases = [test["case"] for test in retained]
    symbolic = replay_compiled(run, config, {"_stage_directory": str(stage)}, cases)
    final_only = config["repair"]["mode"] == "baseline_final_answer_only"
    if final_only:
        from rsa_formalizer.stages.baselines.final_answer_only import comparison
        natural = [test["reasoning"] for test in retained]
    else:
        from rsa_formalizer.bobcat import comparison
        oracles = exp.load_json(base / "computation_oracles.json")["cases"]
        natural = [{**test["reasoning"], "computation_graph": oracles[test["case"]["id"]]}
                   for test in retained]
    summary = comparison.compare(run, {"_stage_directory": str(stage)}, symbolic, natural)
    if stage_name == "analysis":
        saved = exp.load_json(base / "before.json")
        expected_aligned = saved["final_answers_aligned"]
    elif stage_name == "evaluation":
        saved = exp.load_json(base / "after.json")
        expected_aligned = saved["final_answers_aligned"]
    else:
        saved = exp.load_json(stage / "review.json")
        expected_aligned = saved["candidate_final_answers_aligned"]
    if summary["final_answers_aligned"] != expected_aligned:
        raise exp.RunnerError(
            f"restored {stage_name} has {summary['final_answers_aligned']} aligned answers; "
            f"saved review had {expected_aligned}"
        )
    if stage_name.startswith("attempt-"):
        exp.atomic_json(stage / "comparison.json", summary)
    else:
        feedback = base / "feedback" if stage_name == "analysis" else stage / "feedback"
        for report_path in feedback.rglob("report.json") if feedback.is_dir() else ():
            case_id = exp.load_json(report_path)["case"]["id"]
            replay = symbolic.get(case_id, {})
            if final_only:
                replay = {key: replay.get(key) for key in ("id", "inputs", "output", "error")}
            exp.atomic_json(report_path.parent / "catala_replay.json", replay)
    return {"stage": stage_name, "cases": len(cases), "final_answers_aligned": summary["final_answers_aligned"]}
