#!/usr/bin/env python3
"""Compare BOBCat objective orders on every public scope in all five ports.

Runs share the same compiler, project, bounds, and per-scope time budget. Raw
output is retained separately from the published test datasets.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

from bobcatlib import parse, paths, run, targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--reverse", action="store_true",
                        help="reverse which mode runs first within each pair")
    parser.add_argument("--output", type=Path,
                        default=paths.PORT_ROOT / "bobcat_order_experiment")
    args = parser.parse_args()
    if args.timeout <= 0 or args.jobs <= 0:
        parser.error("--timeout and --jobs must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    scope_targets = targets.enumerated_targets()
    projects = {}
    for target in scope_targets:
        key = target.port, target.project_dir
        if key not in projects:
            projects[key] = run.prepare_project(target)

    def execute(index_target):
        index, target = index_target
        target.timeout = args.timeout
        target.strategy = "demand"
        target.max_list_length = 5
        target.solver_timeout_ms = 2000
        target.solver_timeout_max_ms = 60000
        records = []
        # Alternate run order to reduce systematic warm-cache advantage.
        modes = ("legacy", "depth") if (index % 2 == int(args.reverse)) else ("depth", "legacy")
        for mode in modes:
            target.objective_order = mode
            result = run.run_bobcat(target, projects[target.port, target.project_dir])
            parsed = parse.parse_run(result.stdout, result.stderr)
            (args.output / f"{target.name}.{mode}.stdout").write_text(result.stdout)
            (args.output / f"{target.name}.{mode}.stderr").write_text(result.stderr)
            manifest = set(parsed.branch_manifest or [])
            covered = set().union(*(set(p.branches) for p in parsed.paths)) if parsed.paths else set()
            records.append({
                "port": target.port, "target": target.name, "mode": mode,
                "seconds": result.seconds, "timed_out": result.timed_out,
                "returncode": result.returncode, "finished": parsed.finished,
                "manifest_count": len(manifest), "covered_count": len(covered & manifest),
                "sat_count": sum(o.status == "sat" for o in parsed.objectives),
                "unknown_count": sum(o.status == "unknown" for o in parsed.objectives),
                "validated_inputs": len(parsed.paths),
                "manifest": sorted(manifest), "covered": sorted(covered & manifest),
                "command": result.command,
            })
        return records

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for pair in concurrent.futures.as_completed(
                [pool.submit(execute, item) for item in enumerate(scope_targets)]):
            rows = pair.result()
            records.extend(rows)
            print(rows[0]["target"], " ".join(
                f'{r["mode"]}:{r["covered_count"]}/{r["manifest_count"]}'
                f'@{r["seconds"]:.0f}s' for r in rows), flush=True)
            (args.output / "results.json").write_text(
                json.dumps(records, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
