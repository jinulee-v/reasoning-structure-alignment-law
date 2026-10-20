#!/usr/bin/env python3
"""Compare a completed wrapper campaign with an explicitly supplied baseline.

Example:
  python3 bobcat_scripts/compare_results.py \
    --baseline .port/bobcat_experiments/semantic_bounds/baseline.json \
    --output .port/bobcat_experiments/semantic_bounds

Run measure_coverage.py first. Coverage is the existing native source-outcome
union; imported libraries and wrapper scaffolding use the measurement driver's
normal exclusions. Baseline values are data, not compiler configuration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from bobcatlib import paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    rows, scopes = [], []
    for port, (old_covered, old_total) in baseline["coverage"].items():
        coverage = json.loads((paths.dataset(port) / "COVERAGE.json").read_text())
        index = json.loads((paths.dataset(port) / "INDEX.json").read_text())
        current = coverage["branches"]["covered"]
        row = dict(port=port, previous_covered=old_covered, previous_total=old_total,
                   covered=current["outcomes_covered"], total=current["outcomes"],
                   targets=len(index["targets"]),
                   timed_out=sum(t["timed_out"] for t in index["targets"]),
                   paths=sum(t["paths"] for t in index["targets"]))
        row["delta_covered"] = row["covered"] - old_covered
        row["delta_percentage_points"] = 100 * (
            row["covered"] / row["total"] - old_covered / old_total)
        rows.append(row)
        for target in index["targets"]:
            phases, encodings, refinements = Counter(), [], []
            stdout = paths.raw(port) / (target["name"] + ".stdout")
            for line in stdout.read_text().splitlines():
                for tag in ("BOBCAT_TIMING", "BOBCAT_ENCODING", "BOBCAT_REFINEMENT"):
                    if tag + " " not in line:
                        continue
                    record = json.loads(line.split(tag + " ", 1)[1])
                    if tag == "BOBCAT_TIMING":
                        phases[record["phase"]] += record["cpu_ms"]
                    elif tag == "BOBCAT_ENCODING":
                        encodings.append(record)
                    else:
                        refinements.append(record)
            metrics = coverage["targets"][target["name"]]["branch_totals"]
            scopes.append(dict(
                port=port, scope=target["scope"], seconds=target["seconds"],
                timed_out=target["timed_out"], returncode=target["returncode"],
                finished=target["finished"], paths=target["paths"],
                covered=metrics["outcomes_covered"], total=metrics["outcomes"],
                phase_cpu_ms=dict(phases), encodings=encodings,
                rejected_inputs=len(refinements),
                learned_obligations=sum(r.get("learned_obligations", 0) for r in refinements),
                unrefined_failures=sum(not r.get("learned_obligations", 0) for r in refinements)))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "comparison.json").write_text(json.dumps(
        dict(baseline_source=baseline.get("source"), datasets=rows, scopes=scopes),
        indent=2) + "\n")
    lines = ["# BOBCat wrapper campaign comparison", "",
             "All public wrapper scopes; 1,800-second timeout per scope; maximum input-list length 5.",
             "BOBCat uses ordinary first-model SAT; it has no MaxSAT mode.",
             "Previous coverage is supplied by the user. This is a before/after comparison, not an ablation of the three changes.", "",
             "| Dataset | Previous | Current | Covered change | Percentage-point change | Timed out | Validated tests |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['port']} | {r['previous_covered']}/{r['previous_total']} | "
                     f"{r['covered']}/{r['total']} | {r['delta_covered']:+d} | "
                     f"{r['delta_percentage_points']:+.1f} | {r['timed_out']}/{r['targets']} | {r['paths']} |")
    if any(r["total"] != r["previous_total"] for r in rows):
        lines += ["", "**Inventory changed:** compare denominators as well as numerators; counts are not directly interchangeable."]
    lines += ["", "## Per wrapper scope", "",
              "| Dataset | Scope | Seconds | Covered | Tests | Rejections | Learned obligations | Result |",
              "|---|---|---:|---:|---:|---:|---:|---|"]
    for s in scopes:
        status = "timeout" if s["timed_out"] else ("completed" if s["finished"] else f"exit {s['returncode']}")
        lines.append(f"| {s['port']} | {s['scope']} | {s['seconds']:.1f} | "
                     f"{s['covered']}/{s['total']} | {s['paths']} | {s['rejected_inputs']} | "
                     f"{s['learned_obligations']} | {status} |")
    lines += ["", "## Interpretation", "",
              "Coverage counts only outcomes observed in successful complete-scope replay. A failed replay contributes no coverage. Per-scope coverage overlaps and must not be summed to obtain dataset coverage.", "",
              "Timings in comparison.json are CPU time for completed phases. A process killed during compilation cannot emit that phase's closing timing; missing time is not zero cost. Shared compilation excludes solving and replay in this implementation.", "",
              "The supplied baseline does not include matching per-scope timings or a recorded command, so this comparison cannot isolate the effects of a longer timeout or attribute gains to individual changes.", "",
              "Artifacts: [campaign configuration](campaign.json), [compiler patch](compiler.patch), [test log](tests.log), [machine-readable results](comparison.json).", ""]
    (args.output / "COMPARISON.md").write_text("\n".join(lines))
    print("\n".join(lines[:10]))


if __name__ == "__main__":
    main()
