"""A single global repair session from provision-indexed immutable evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.bobcat import comparison
from rsa_formalizer.bobcat.replay import replay_compiled
from rsa_formalizer.bobcat.records import ReplayRecords
from . import provision_testing as tests
from . import computation_alignment


AGENT_PROMPT = """Repair the existing Catala formalization using /rsa/feedback/index.json.
This is ONE nonrecursive repair pass across the project. Each report names the
target statutory provision and its annotated Catala blocks. Read report.json,
llm_reasoning.txt, and catala_replay.json: these contain the concrete inputs,
outputs, extracted LLM structure, and concrete branch/dependency trace. Reports
are assembled mechanically; no other LLM has diagnosed or summarized mismatches.
When present, computation_graph_alignment gives provision-associated values,
quoted reasoning evidence, public input contexts, and earliest comparable
mismatches. Inspect these before downstream output differences. Attribution
differences require review; missing or ambiguous counterparts do not prove a
defect.
The repair index includes final-answer failures and intermediate value
divergences, including value divergences when final answers match. Attribution-only
differences do not independently request repair. All executable frozen cases are
retained by default: computation_graph_selection records target reachability as
diagnostic evidence. An absent or disconnected target in an extracted LLM graph
does not invalidate the input or prove that the program is correct. When graph
extraction is unavailable, diagnose final-answer failures from the structured
inputs, source provisions, and concrete execution trace.

Determine whether each discrepancy comes from Catala, test grounding, or the
reasoning oracle. A model answer is evidence, not ground truth. Do not change
correct Catala to match an incomplete or mistaken reasoning trace. For every
rejected final-answer mismatch, identify its case ID and first divergent
quantity, calculate both values from the input facts, and name the precise
incorrect step in the LLM reasoning. Distinguish per-entity values from
aggregate values; do not infer a reasoning
error from a label alone. Repair actual defects in
linked blocks, with only minimal dependency/helper edits when needed. Preserve
statute prose, annotations, declarations, API contracts, and every Markdown
code fence, including empty fenced blocks. Only change code inside existing
writable code fences; do not merge, remove, or relocate fences. Do not invent facts
or domain assertions to hide failures. Generation gaps and execution errors are
separate from semantic misalignments.

Before rejecting any final-answer or intermediate-value discrepancy as an oracle
error, record its case ID; the earliest divergent quantity with its taxpayer,
employer, worker and tax-period context; exact structured JSON input paths and
values establishing the relevant facts; the program value and independently
calculated expected value with arithmetic or Boolean conditions; the governing
source provision; and the precise quoted incorrect reasoning step. Check the
upstream predicates and explain how they lead to the output difference. Use the
structured inputs as authoritative when narrative rationale or reasoning differs.
Follow the input contract's rules for missing values and defaults. Do not add
evidence-presence requirements solely because facts are absent.
Do not infer a different employer, recipient, jurisdiction, service link, or
aggregate from a name or label. If the input contract or entity mapping cannot
resolve the discrepancy, classify it as unresolved_grounding or
unresolved_mapping, state what evidence is missing, and retain it in the final
unresolved list. Do not count an unsupported rejection as resolved or alter
correct logic merely to increase agreement with the oracle.

Produce a JSON list of ONLY the reports that remain non-aligned after your
repairs and replay review, including remaining intermediate-value mismatches
when final answers match, and any newly disagreeing cases found by replay.
Use /rsa/feedback/latest_replay.json and the evidence_index it names as the
authority for the final report, NOT the original /rsa/feedback/index.json or
baseline comparisons. Explain the CURRENT values and reasoning for every ID in
the latest replay's remaining_case_ids, including newly introduced discrepancies.
Exclude cases that are now aligned. Do not require a diagnosis file before replay.
Save the final artifact to /rsa/submission-check/case_diagnoses.json (outside
/workspace). Each dictionary must contain exactly these three fields:
  {"case_id": "<exact case ID>",
   "diagnosis": "<one sentence explaining the remaining discrepancy>",
   "classification": "Catala wrong | LLM wrong | Both wrong | Unresolved"}
Choose exactly one classification, referring to the CURRENT repaired Catala
and frozen LLM reasoning. Include oracle errors and unresolved grounding or
mapping issues whenever a discrepancy remains; rejecting the oracle does not
make a case aligned. Include each remaining case once. Use a nonempty single-line
diagnosis of at most 600 characters. An empty list is valid only if no reports
remain non-aligned. Any source edit after replay requires another successful
replay before writing the final report and submitting. If replay fails, fix the
failure and retry. The final submission check rejects stale source snapshots,
missing remaining cases, and reports for cases that are now aligned. It checks
coverage and JSON format, not the legal correctness of your diagnoses.

Definitions.catala_en is intentionally mounted read-only. Other Catala source
files in /workspace are writable; put any necessary local helper correction in
those files. A write failure on Definitions.catala_en does not make the whole
workspace read-only.

Preserve the submitted file set throughout the repair: do not create, delete,
or rename project files under /workspace. Edit existing writable Catala files
for source changes. Put all scratch scripts, notes, logs, captured tool responses,
and other temporary files under /tmp, not /workspace. The only new workspace
files allowed are compiler-generated artifacts under _build/ and _targets/
from the required Clerk commands; the runner removes those before integrity
checks. Do not use those directories to store your own temporary files.

Tests and oracles are fixed. Do not regenerate analysis, call
/rsa/regenerate_scope_analysis.py, or change test inputs. Do not recurse through
scopes or invoke a separate LLM summarizer. Work from all reports together.
Run `clerk start`, then `clerk typecheck .` before and after edits. Keep the
project typechecking. Review all reports and use
`python3 /rsa/replay_candidate.py` to evaluate your repairs. After inspecting the
results, correct demonstrated defects and replay the updated source as needed.
There is no limit on replay calls or repair iterations; do not minimize testing
because a call takes a long time. Verify the final source with replay before
submission so that your remaining-case report describes the submitted code.
It replays all frozen generated cases against a snapshot of your workspace and
shows every changed final answer, including newly disagreeing cases. The response's
evidence_index points to /rsa/feedback/replays/attempt-N/index.json. This read-only
index covers EVERY replayed frozen case, including cases absent from the original
feedback index, and lists remaining_case_ids. Each case directory contains
report.json with full structured inputs, current and baseline comparisons,
llm_reasoning.txt with the full frozen reasoning, llm_computation_graph.json,
computation_graph_alignment.json, and catala_replay.json with the current concrete
execution trace. Read those files to investigate new disagreements; absence from
the original feedback index does not mean the input evidence is unavailable.
Use remaining_case_ids as the EXACT list for the final remaining-case JSON.
Replay again after any later source edit before finalizing that list.

A replay may produce no partial output while the validator works. A silent or sleeping client waiting on the validator socket is
not evidence of a stall. Allow the existing call to finish; use the tool's wait
or poll mechanism for a running call. Do not terminate, restart, or submit a
duplicate call merely because it is slow, silent, or you discover another issue.
Continue useful work while waiting, including reviewing evidence, editing
existing writable Catala files, and running local typechecks. This overlaps
repair work with replay latency. The returned results describe the snapshot
submitted when the call started, not any edits made afterward; keep track of
those later changes and do not claim that the replay checked them. Capture the
full response under /tmp so terminal truncation does not require another replay.

When the call returns, inspect each changed case and correct any demonstrably
incorrect edit before final submission; a new LLM disagreement alone does not
prove a regression. Investigate using the full case evidence, fix demonstrated
regressions, and replay again to verify recovery. For build or execution errors,
diagnose the failure, fix it, and retry; do not treat it as semantic disagreement.
Run `/rsa/check_submission.sh` after the final edits and replay review as
the final submission check; it also validates the remaining-discrepancy JSON report.
If that check rejects source integrity or an invalid report, restore the exact
protected prose, annotations, and fences or correct the report, then resubmit rather than
claiming successful completion. Describe concrete
changes and unresolved case IDs in your final response. The runner will run
protected validation afterward; it will not request another repair pass.
"""


def _state(run: Path, state: dict, phase: str, root: Path) -> None:
    state.update(provision_phase=phase, next_stage="provision_repair",
                 _stage_directory=str(root), status="running", updated_at=exp.utc_now())
    exp.atomic_json(run / "state.json", state)


def retain_executable(base: Path, results: list[dict], symbolic: ReplayRecords) -> tuple[list[dict], ReplayRecords]:
    """Keep only cases for which the frozen Catala program actually executes."""
    excluded = {row["id"]: row.get("error") or "missing Catala output"
                for row in symbolic if row.get("error") or row.get("output") is None}
    retained = [{**result, "accepted_tests": [test for test in tests.accepted_tests(result)
                                        if test["case"]["id"] not in excluded]}
                for result in results]
    retained = [{**result, "status": "accepted" if result["accepted_tests"] else "execution_excluded"}
                for result in retained]
    exp.atomic_json(base / "execution_exclusions.json", excluded)
    exp.atomic_json(base / "executable_tests.json", {"results": retained})
    if hasattr(symbolic, "case_files"):
        paths = [path for path in symbolic.case_files if path.stem not in excluded]
        filtered = ReplayRecords(paths)
    else:
        filtered = [row for row in symbolic if row["id"] not in excluded]
    return retained, filtered


def run(run: Path, config: dict, state: dict) -> dict:
    from rsa_formalizer.stages import formalization, validation
    from .diff import workspace_diff

    base = run / "provision_repair"
    analysis = base / "analysis"
    phase = state.get("provision_phase", "generate")
    formats = exp.load_json(base / "formats.json")
    plan = exp.load_json(base / "plan.json")
    if plan.get("generation_format") != tests.FORMAT:
        raise exp.RunnerError("provision plan uses an incompatible generation format; create a new shared checkpoint")
    final_only = config["repair"]["mode"] == "baseline_final_answer_only"
    if not final_only and not computation_alignment.enabled(config):
        raise exp.RunnerError("provision graph selection requires repair.computation_graph_alignment.enabled")
    targets = plan["targets"]
    settings = config["repair"]
    if final_only:
        from rsa_formalizer.stages.baselines.final_answer_only import reports as baseline_reports
        from rsa_formalizer.stages.baselines.final_answer_only import comparison as baseline_comparison
        write_reports = baseline_reports.write_reports
        compare = baseline_comparison.compare
    else:
        write_reports = tests.write_reports
        compare = comparison.compare
    if phase == "generate":
        _state(run, state, "generate", analysis)
        def generate(target: dict) -> dict:
            print(f"Generating provision test: {target['provision_id']}", flush=True)
            result = tests.generate_target(run, config, target, analysis / "snapshot", formats,
                                           settings["max_attempts_per_provision"])
            print(f"Provision {target['provision_id']}: {result['status']} "
                  f"({len(tests.accepted_tests(result))} tests retained)", flush=True)
            return result
        with ThreadPoolExecutor(max_workers=settings["generation_jobs"]) as executor:
            results = list(executor.map(generate, targets))
        exp.atomic_json(base / "tests.json", {"results": results})
        graph_root = analysis / "computation_graph_results"
        oracles = {test["case"]["id"]: exp.load_json(
            graph_root / test["case"]["id"] / "result.json")
            for result in results for test in tests.accepted_tests(result)}
        exp.atomic_json(base / "computation_oracles.json", {"cases": oracles})
        if settings["mode"] == "provision_shared":
            exp.atomic_json(base / "checkpoint.json", {
                "snapshot_sha256": exp.tree_hash(analysis / "snapshot"),
                "tests_sha256": exp.sha256_file(base / "tests.json"),
                "computation_oracles_sha256": exp.sha256_file(base / "computation_oracles.json"),
                "validation_suite_sha256": config["validation_suite_sha256"],
            })
            state.update(provision_phase="fork_ready", next_stage="fork_ready",
                         status="fork_ready", updated_at=exp.utc_now())
            exp.atomic_json(run / "state.json", state)
            return state
        _state(run, state, "compare", analysis)
        return state
    results_path = base / "executable_tests.json"
    if not results_path.is_file():
        results_path = base / "selection.json"
    if not results_path.is_file():
        source_results = exp.load_json(base / "tests.json")["results"]
        oracles = exp.load_json(base / "computation_oracles.json")["cases"]
        filter_by_target = settings.get("filter_by_target_provision_reachability", False)
        selected = (source_results if final_only else
                    tests.select_by_computation_graph(source_results, oracles,
                                                     reject_unapplied=filter_by_target))
        exp.atomic_json(base / "selection.json", {"results": selected})
        results_path = base / "selection.json"
    results = exp.load_json(results_path)["results"]
    retained = [test for result in results for test in tests.accepted_tests(result)]
    cases = [test["case"] for test in retained]
    natural = [test["reasoning"] for test in retained]
    if phase == "compare":
        _state(run, state, "compare", analysis)
        if not cases:
            tests.write_reports(base, results, {"cases": []})
            raise exp.RunnerError("No full-input provision cases passed graph selection")
        symbolic = replay_compiled(run, config, state, cases)
        results, symbolic = retain_executable(base, results, symbolic)
        retained = [test for result in results for test in tests.accepted_tests(result)]
        cases = [test["case"] for test in retained]
        natural = [test["reasoning"] for test in retained]
        if not final_only:
            oracles = exp.load_json(base / "computation_oracles.json")["cases"]
            natural = [{**row, "computation_graph": oracles[row["id"]]} for row in natural]
        summary = compare(run, state, symbolic, natural)
        index = write_reports(base, results, summary, symbolic)
        exp.atomic_json(base / "before.json", summary)
        state.update(provision_feedback=str((base / "feedback").relative_to(run)),
                     provision_baseline=str(analysis / "snapshot"), provision_tests_accepted=len(cases),
                     provision_misaligned=len(index["reports"]))
        state["provision_agent_required"] = bool(index["reports"])
        _state(run, state, "agent" if state["provision_agent_required"] else "evaluate", base / "session")
        return state
    if phase == "agent":
        _state(run, state, "agent", base / "session")
        # One global session: no recursive scope, requeue, or summary call.
        formalization.run(run, config, state)
        state["completed_stages"] = ["initialized"]
        _state(run, state, "evaluate", base / "evaluation")
        return state
    if phase == "evaluate":
        if not final_only:
            # Frozen extraction from the baseline; never re-extract against repaired code.
            oracles = exp.load_json(base / "computation_oracles.json")["cases"]
            natural = [{**row, "computation_graph": oracles[row["id"]]} for row in natural]
        evaluation = base / "evaluation"
        _state(run, state, "evaluate", evaluation)
        exp.publish_stage_snapshot(run, state)
        symbolic = replay_compiled(run, config, state, cases)
        after = compare(run, state, symbolic, natural)
        exp.atomic_json(base / "after.json", after)
        write_reports(evaluation, results, after, symbolic)
        (base / "changes.diff").write_text(workspace_diff(analysis / "snapshot", run / "workspace"), encoding="utf-8")
        validation.run(run, config, state)
        before = exp.load_json(base / "before.json")
        exp.atomic_json(base / "summary.json", {
            "mode": settings["mode"], "target_provisions": len(targets),
            "accepted_cases": len(cases),
            "accepted_provisions": sum(bool(tests.accepted_tests(result)) for result in results),
            "generation_gaps": sum(not tests.accepted_tests(result) for result in results),
            "generation_attempts": sum(result.get("attempt_count",
                len(result.get("attempts", [])) + len(tests.accepted_tests(result))) for result in results),
            "repair_sessions": int(bool(state.get("provision_agent_required", state.get("provision_misaligned")))),
            "before": {k: v for k, v in before.items() if k != "cases"},
            "after": {k: v for k, v in after.items() if k != "cases"},
            "validation": state.get("verification_summary"), "summarizer_calls": 0,
        })
        state.update(provision_phase="finished", next_stage="finished", status="completed", updated_at=exp.utc_now())
        exp.atomic_json(run / "state.json", state)
        from .artifact_retention import prune_completed
        prune_completed(run)
    return state
