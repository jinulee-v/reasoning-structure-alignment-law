"""Review a provision repair candidate against frozen generated cases."""

from __future__ import annotations

import shutil
from pathlib import Path

from rsa_formalizer.bobcat import compiled_json
from rsa_formalizer.bobcat.replay import replay_compiled
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.validation import submissions
from . import comparison
from rsa_formalizer.stages.reasoning_structure_alignment import provision_testing, case_diagnoses


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
                and (base / 'feedback/replays' / prior_stage.name / 'index.json').is_file()
                and 'remaining_case_ids' in exp.load_json(previous)):
            shutil.rmtree(stage)
            report = exp.load_json(previous)
            case_diagnoses.publish_replay(base / "feedback", prior_stage, report)
            return report
    state = {"_stage_directory": str(stage)}
    results = exp.load_json(base / "executable_tests.json")["results"]
    retained = [test for result in results for test in provision_testing.accepted_tests(result)]
    cases = [test["case"] for test in retained]
    natural = [test["reasoning"] for test in retained]
    symbolic = replay_compiled(run, config, state, cases, bridge_timeout_seconds=90)
    build_errors = exp.load_json(stage / "tests_bobcat_symbolic_results" / "build_errors.json")
    if build_errors:
        raise exp.RunnerError(f"candidate replay bridge build failed: {build_errors}")
    candidate = comparison.compare(run, state, symbolic, natural)
    exp.atomic_json(stage / "comparison.json", candidate)

    before = exp.load_json(base / "before.json")
    baseline = {item["id"]: item for item in before["cases"]}
    changes = []
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
            })
    report = {
        "reviewed_cases": len(cases),
        "before_final_answers_aligned": before["final_answers_aligned"],
        "candidate_final_answers_aligned": candidate["final_answers_aligned"],
        "changed_outputs": len(changes),
        "new_llm_disagreements": worsened,
        "resolved_llm_disagreements": improved,
        "changes": changes,
        "note": "LLM final answers are evidence, not ground truth; inspect changed cases.",
    }
    destination = base / "feedback/replays" / stage.name
    rows = []
    by_id = {row['id']: row for row in candidate['cases']}
    for test in retained:
        identifier = test['case']['id']
        if Path(identifier).name != identifier or identifier in {'.', '..'}:
            raise exp.RunnerError(f'unsafe replay case ID: {identifier!r}')
        folder = destination / identifier
        folder.mkdir(parents=True, exist_ok=True)
        # Final answers and supplied inputs only: no computation traces or graphs.
        exp.atomic_json(folder / 'report.json', {
            'case': test['case'], 'comparison': by_id[identifier],
            'candidate_snapshot_sha256': candidate_hash,
        })
        (folder / 'llm_reasoning.txt').write_text(
            test['reasoning'].get('output_text') or '', encoding='utf-8')
        rows.append({'case_id': identifier, 'report': f'{identifier}/report.json'})
    remaining = case_diagnoses.remaining_cases(candidate)
    exp.atomic_json(destination / 'index.json', {
        'candidate_snapshot_sha256': candidate_hash,
        'reports': rows, 'remaining_case_ids': remaining,
    })
    report.update(remaining_case_ids=remaining,
                  evidence_index=f'/rsa/feedback/replays/{stage.name}/index.json',
                  evidence_cases=len(rows))
    exp.atomic_json(stage / "review.json", report)
    case_diagnoses.publish_replay(base / "feedback", stage, report)
    return report
