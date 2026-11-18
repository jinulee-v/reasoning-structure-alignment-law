"""Deterministic final-answer-only feedback for the paired baseline."""

from __future__ import annotations

from pathlib import Path

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment.provision_testing import (
    accepted_tests, target_slug,
)


def write_reports(root: Path, results: list[dict], summary: dict,
                  symbolic=None) -> dict:
    by_case = {test["case"]["id"]: {**test, "target": result["target"]}
               for result in results for test in accepted_tests(result)}
    feedback = root / "feedback"
    feedback.mkdir(parents=True, exist_ok=True)
    reports = []
    diagnostics = []
    for row in summary.get("cases", []):
        item = by_case[row["id"]]
        error = (row.get("code_execution_error") or row.get("llm_reasoning_error")
                 or row.get("final_answer_parse_error"))
        mismatch = row.get("final_answer_aligned") is False
        if not mismatch and not error:
            continue
        provision = item["target"]["provision_id"]
        destination = feedback / target_slug(provision) / target_slug(row["id"])
        destination.mkdir(parents=True, exist_ok=True)
        # Keep computation and provision alignment out of baseline feedback.
        comparison = {key: row.get(key) for key in (
            "id", "inputs", "catala_answer", "llm_final_answer",
            "final_answer_aligned", "code_execution_error", "llm_reasoning_error",
            "final_answer_parse_error", "code_execution_diagnostic",
            "llm_reasoning_diagnostic")}
        report = {"target_provision": provision, "target_blocks": item["target"]["blocks"],
                  "case": item["case"], "comparison": comparison,
                  "answer_misaligned": mismatch}
        exp.atomic_json(destination / "report.json", report)
        (destination / "llm_reasoning.txt").write_text(
            item["reasoning"].get("output_text") or "", encoding="utf-8")
        if symbolic is not None:
            replay = symbolic.get(row["id"], {}) if hasattr(symbolic, "get") else {}
            # The baseline may see the concrete Catala result, but no computation trace.
            exp.atomic_json(destination / "catala_replay.json", {
                key: replay.get(key) for key in ("id", "inputs", "output", "error")})
        report_path = str((destination / "report.json").relative_to(feedback))
        if mismatch:
            reports.append({"provision": provision, "case_id": row["id"],
                            "report": report_path, "linked_provisions": [provision]})
        if error:
            diagnostics.append({"case_id": row["id"], "target_provision": provision,
                                "report": report_path, "error": str(error)})
    index = {"reports": reports, "diagnostics": diagnostics,
             "generation_gaps": [{"provision": result["target"]["provision_id"],
                                  "status": result["status"], "attempts": result.get("attempts", [])}
                                 for result in results if result["status"] != "accepted"],
             "report_method": "final_answer_only_no_graph_feedback"}
    exp.atomic_json(feedback / "index.json", index)
    return index
