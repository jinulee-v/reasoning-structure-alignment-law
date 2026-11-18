"""Review a provision repair candidate against frozen generated cases."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from rsa_formalizer.bobcat import comparison, compiled_json
from rsa_formalizer.bobcat.replay import replay_compiled
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.validation import submissions
from . import provision_testing, case_diagnoses


def _mismatches(case: dict) -> dict[str, dict]:
    graph = case.get("computation_graph_alignment") or {}
    return {item["quantity"]: item for item in graph.get("value_mismatches", [])
            if item.get("quantity")}


def _first_mismatch(case: dict) -> dict | None:
    graph = case.get("computation_graph_alignment") or {}
    rows = graph.get("earliest_comparable_mismatches") or []
    if not rows:
        return None
    item = rows[0]
    return {key: item.get(key) for key in
            ("quantity", "catala_value", "llm_value", "catala_provisions",
             "llm_provision", "evidence")}


def _publish_evidence(base: Path, stage: Path, retained: list[dict],
                      natural: list[dict], symbolic, candidate: dict,
                      baseline: dict, candidate_hash: str) -> dict:
    """Publish every replayed case through the agent's existing read-only mount."""
    destination = base / "feedback" / "replays" / stage.name
    destination.mkdir(parents=True, exist_ok=True)
    cases = {test["case"]["id"]: test for test in retained}
    reasoning = {item["id"]: item for item in natural}
    compared = {item["id"]: item for item in candidate["cases"]}
    rows = []
    remaining = []
    for trace in symbolic:
        identifier = trace["id"]
        # Generated IDs are also filenames in ReplayRecords, but validate the
        # boundary before publishing anything into the feedback tree.
        if Path(identifier).name != identifier or identifier in {".", ".."}:
            raise exp.RunnerError(f"unsafe replay case ID: {identifier!r}")
        folder = destination / identifier
        folder.mkdir(exist_ok=True)
        current = compared[identifier]
        graph = current.get("computation_graph_alignment") or {}
        reasons = (["final_answer_failure"] if current.get("final_answer_aligned") is False else [])
        if current.get("final_answer_aligned") is None:
            reasons.append("execution_or_reasoning_error")
        if graph.get("value_mismatches"):
            reasons.append("intermediate_value_divergence")
        if reasons:
            remaining.append(identifier)
        test = cases[identifier]
        report = {
            "case": test["case"],
            "comparison": current,
            "baseline_comparison": baseline[identifier],
            "candidate_snapshot_sha256": candidate_hash,
            "answer_misaligned": current.get("final_answer_aligned") is False,
            "structure_misaligned": bool(graph.get("value_mismatches")),
            "report_reasons": reasons,
            "earliest_comparable_mismatches": graph.get("earliest_comparable_mismatches", []),
            "computation_graph_selection": test.get("computation_graph_selection"),
        }
        exp.atomic_json(folder / "report.json", report)
        (folder / "llm_reasoning.txt").write_text(
            reasoning[identifier].get("output_text", ""), encoding="utf-8")
        exp.atomic_json(folder / "llm_computation_graph.json",
                        reasoning[identifier].get("computation_graph"))
        exp.atomic_json(folder / "computation_graph_alignment.json", graph)
        trace_path = folder / "catala_replay.json"
        source = getattr(symbolic, "paths_by_id", {}).get(identifier)
        if source is not None:
            trace_path.unlink(missing_ok=True)
            try:
                os.link(source, trace_path)
            except OSError:
                shutil.copy2(source, trace_path)
        else:
            exp.atomic_json(trace_path, trace)
        rows.append({"case_id": identifier,
                     "report": f"{identifier}/report.json",
                     "report_reasons": reasons})
    index = {"candidate_snapshot_sha256": candidate_hash,
             "reports": rows, "remaining_case_ids": remaining,
             "note": "All frozen replay cases, including cases outside the original feedback index."}
    exp.atomic_json(destination / "index.json", index)
    return {"evidence_index": f"/rsa/feedback/replays/{stage.name}/index.json",
            "evidence_cases": len(rows), "remaining_case_ids": remaining}


def review(run: Path, config: dict, *, agent_home: Path | None = None) -> dict:
    """Replay public cases; separately archive private held-out measurements."""
    base = run / "provision_repair"
    # Clerk writes build artifacts into the agent workspace during typecheck.
    # They are generated files, not changes to the formalization.
    exp.cleanup_clerk_artifacts(run / "workspace")
    exp.validate_workspace(run / "input", run / "workspace")
    reviews = base / "session" / "candidate_reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    number = 1
    while (reviews / f"attempt-{number}").exists():
        number += 1
    stage = reviews / f"attempt-{number}"
    stage.mkdir()
    exp.copy_project(run / "workspace", stage / "snapshot")
    candidate_hash = exp.tree_hash(stage / "snapshot")
    case_diagnoses.begin_replay(base / "feedback", candidate_hash)
    submissions.record(run, config, stage / "snapshot", trigger="replay",
                       label=stage.name, agent_home=agent_home)
    for previous in sorted(reviews.glob("attempt-*/review.json")):
        prior_stage = previous.parent
        errors_path = prior_stage / "tests_bobcat_symbolic_results" / "build_errors.json"
        if (errors_path.is_file() and not exp.load_json(errors_path)
                and exp.tree_hash(prior_stage / "snapshot") == candidate_hash
                and (base / "feedback/replays" / prior_stage.name / "index.json").is_file()):
            shutil.rmtree(stage)
            report = exp.load_json(previous)
            case_diagnoses.publish_replay(base / "feedback", prior_stage, report)
            return report
    state = {"_stage_directory": str(stage)}
    results = exp.load_json(base / "executable_tests.json")["results"]
    retained = [test for result in results for test in provision_testing.accepted_tests(result)]
    cases = [test["case"] for test in retained]
    oracles = exp.load_json(base / "computation_oracles.json")["cases"]
    natural = [{**test["reasoning"], "computation_graph": oracles[test["case"]["id"]]}
               for test in retained]
    symbolic = replay_compiled(run, config, state, cases, bridge_timeout_seconds=90)
    build_errors = exp.load_json(stage / "tests_bobcat_symbolic_results" / "build_errors.json")
    if build_errors:
        raise exp.RunnerError(f"candidate replay bridge build failed: {build_errors}")
    candidate = comparison.compare(run, state, symbolic, natural)
    exp.atomic_json(stage / "comparison.json", candidate)

    before = exp.load_json(base / "before.json")
    baseline = {item["id"]: item for item in before["cases"]}
    changes = []
    computation_changes = []
    improved = worsened = 0
    for current in candidate["cases"]:
        original = baseline[current["id"]]
        old = original.get("catala_answer")
        new = current.get("catala_answer")
        if ((old is None) != (new is None)
                or (old is not None and new is not None
                    and not compiled_json.json_equivalent(old, new))):
            prior = original.get("final_answer_aligned")
            aligned = current.get("final_answer_aligned")
            if prior is False and aligned is True:
                improved += 1
            elif prior is True and aligned is False:
                worsened += 1
            changes.append({
                "id": current["id"], "before": old, "candidate": new,
                "llm_answer": current.get("llm_final_answer"),
                "before_aligned": prior, "candidate_aligned": aligned,
                "before_first_mismatch": _first_mismatch(original),
                "candidate_first_mismatch": _first_mismatch(current),
            })
        old_mismatches = _mismatches(original)
        new_mismatches = _mismatches(current)
        newly_disagreeing = sorted(set(new_mismatches) - set(old_mismatches))
        resolved = sorted(set(old_mismatches) - set(new_mismatches))
        if newly_disagreeing or resolved:
            computation_changes.append({
                "id": current["id"],
                "newly_disagreeing_quantities": [
                    {key: new_mismatches[q].get(key) for key in
                     ("quantity", "catala_value", "llm_value", "evidence")}
                    for q in newly_disagreeing],
                "resolved_quantities": resolved,
            })
    report = {
        "reviewed_cases": len(cases),
        "before_final_answers_aligned": before["final_answers_aligned"],
        "candidate_final_answers_aligned": candidate["final_answers_aligned"],
        "before_value_mismatch_cases": before["computation_value_mismatch_cases"],
        "candidate_value_mismatch_cases": candidate["computation_value_mismatch_cases"],
        "changed_outputs": len(changes),
        "new_llm_disagreements": worsened,
        "resolved_llm_disagreements": improved,
        "changes": changes,
        "computation_changes": computation_changes,
        "note": "LLM answers and computation graphs are evidence, not ground truth; inspect changed cases.",
    }
    report.update(_publish_evidence(
        base, stage, retained, natural, symbolic, candidate, baseline, candidate_hash))
    exp.atomic_json(stage / "review.json", report)
    case_diagnoses.publish_replay(base / "feedback", stage, report)
    return report
