"""Paths in, dataset out.

One JSONL file per target, one row per replay-validated solver model:

    {"target": "airline_one_item", "path": 0,
     "inputs":  {"cabin": {"cons": "MainCabin"}, "weight1": 40, ...},
     "outputs": {"total": "50.00", "accepted": true},
     "error": null, "exact": true}

Values are JSON, with two conventions.  Money and decimals are **strings**, not
floats: a fee is a number of cents and `50.00` must not come back as
`50.000000000000007`.  An enumeration is `{"cons": "MainCabin"}`, or
`{"cons": "Present", "payload": ...}` when the constructor carries one, because
a bare `"MainCabin"` would be indistinguishable from a string field.

The rows are a *reading* of what BOBCat printed, and each port's `raw/`
keeps what it actually printed, byte for byte.  Anything this pipeline cannot
read is counted in `INDEX.json` under `unparsed` rather than dropped quietly,
so a schema change in the compiler's printer shows up as a number and not as a
silently smaller dataset.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone

from . import paths
from .parse import Path as ConcPath, Run


def _row(target_name: str, p: ConcPath) -> dict:
    return {
        "target": target_name,
        "path": p.index,
        "inputs": {k: v.as_json() for k, v in p.inputs.items()},
        "outputs": {k: v.as_json() for k, v in p.outputs.items()},
        "error": p.error,
        "exact": p.exact,
    }


def _key(row: dict) -> str:
    """A row's inputs, canonically, for spotting repeats."""
    return json.dumps(row["inputs"], sort_keys=True)


def schema_of(run: Run) -> dict:
    """Field -> Catala kind, and the fields that were not the same kind twice.

    A field whose kind varies between paths is a signal worth keeping: it means
    either an optional that is sometimes absent, or that this module misread
    one of the two.
    """
    def kinds(which: str) -> dict:
        seen: dict = {}
        for p in run.paths:
            for name, v in getattr(p, which).items():
                seen.setdefault(name, set()).add(v.kind)
        return {n: (ks.pop() if len(ks) == 1 else sorted(ks))
                for n, ks in sorted(seen.items())}
    return {"inputs": kinds("inputs"), "outputs": kinds("outputs")}


def write_target(target, run: Run, result, dedup: bool = False) -> dict:
    """Write one target's JSONL and raw capture; return its INDEX entry."""
    dataset_dir = paths.dataset(target.port)
    raw_dir = paths.raw(target.port)
    coverage_dir = paths.coverage(target.port)
    goals_dir = paths.goals(target.port)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    coverage_dir.mkdir(parents=True, exist_ok=True)
    goals_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / f"{target.name}.stdout").write_text(result.stdout)
    if result.stderr:
        (raw_dir / f"{target.name}.stderr").write_text(result.stderr)

    goal_records = [
        {"objective": goal.objective, "status": goal.status,
         **({"model": goal.model} if goal.model is not None else {}),
         **({"input": goal.input} if goal.input is not None else {}),
         **({"validated": goal.validated}
            if goal.validated is not None else {}),
         **({"reason": goal.reason} if goal.reason is not None else {})}
        for goal in run.objectives
    ]
    goals_out = goals_dir / f"{target.name}.jsonl"
    with goals_out.open("w") as file:
        for record in goal_records:
            file.write(json.dumps(record, sort_keys=True) + "\n")

    rows = [{**_row(target.name, p), **({"kind": p.kind} if p.kind else {})}
            for p in run.paths]
    seen: set = set()
    kept, repeats = [], 0
    for r in rows:
        k = _key(r)
        if k in seen:
            repeats += 1
            if dedup:
                continue
        seen.add(k)
        kept.append(r)

    out = dataset_dir / f"{target.name}.jsonl"
    with out.open("w") as f:
        for r in kept:
            f.write(json.dumps(r, sort_keys=True) + "\n")

    kept_indexes = {r["path"] for r in kept}
    coverage_out = coverage_dir / f"{target.name}.jsonl"
    coverage_records = []
    manifest_extended = 0
    branch_manifest = run.branch_manifest
    if branch_manifest is not None:
        # A compiler manifest should already contain every replay event. Keep
        # the report sound if instrumentation ever violates that invariant:
        # observed outcomes are evidence and must never be discarded merely
        # because the static census missed their identity.
        observed = {branch for path in run.paths for branch in path.branches}
        original = set(branch_manifest)
        branch_manifest = sorted(original | observed)
        manifest_extended = len(set(branch_manifest) - original)
        coverage_records.append({"kind": "branch_manifest",
                                 "branches": branch_manifest})
    cumulative_branches = set()
    for p in run.paths:
        if p.index in kept_indexes and branch_manifest is not None:
            cumulative_branches.update(p.branches)
            record = {"kind": "branch_path", "path": p.index,
                      "branches": p.branches}
            if p.coverage_seconds is not None:
                record["elapsed_cpu_seconds"] = p.coverage_seconds
                record["cumulative_covered"] = len(cumulative_branches)
                record["manifest_outcomes"] = len(branch_manifest)
            coverage_records.append(record)
    if coverage_records:
        with coverage_out.open("w") as f:
            for record in coverage_records:
                f.write(json.dumps(record, sort_keys=True) + "\n")
    elif coverage_out.exists():
        coverage_out.unlink()

    outputs = Counter(json.dumps(r["outputs"], sort_keys=True) for r in kept)
    return {
        "name": target.name,
        "port": target.port,
        "scope": target.scope,
        "harness": paths.rel(target.harness),
        "modules": [paths.rel(m) for m in target.modules],
        "note": target.note,
        "command": result.command,
        "file": out.name,
        "coverage_file": (coverage_out.name if coverage_records else None),
        "goals_file": goals_out.name,
        "objectives": len(goal_records),
        "objectives_sat": sum(r["status"] == "sat" for r in goal_records),
        "objectives_unsat": sum(r["status"] == "unsat" for r in goal_records),
        "objectives_unknown": sum(r["status"] == "unknown" for r in goal_records),
        "objectives_spurious": len(run.refinements),
        "manifest_extended_from_replay": manifest_extended,
        "coverage_paths": sum(r["kind"] == "branch_path"
                              for r in coverage_records),
        "paths": len(kept),
        "repeated_inputs": repeats,
        "distinct_outputs": len(outputs),
        "errors": sum(1 for r in kept if r["error"]),
        "inexact": sum(1 for r in kept if not r["exact"]),
        "unparsed": len(run.unparsed),
        "finished": run.finished,
        "incomplete": run.incomplete,
        "timed_out": result.timed_out,
        "returncode": result.returncode,
        "seconds": round(result.seconds, 1),
    }


def bobcat_version() -> dict:
    """What produced the dataset, so a stale one can be recognized as stale."""
    src = paths.SOURCE
    commit = None
    if (src / ".git").exists():
        r = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                           capture_output=True, text=True)
        commit = r.stdout.strip() or None
    version = None
    if paths.CATALA.exists():
        r = subprocess.run([str(paths.CATALA), "--version"],
                           env=paths.bobcat_env(), capture_output=True,
                           text=True)
        version = r.stdout.strip() or None
    return {"repository": paths.BOBCAT_REPOSITORY,
            "commit": commit, "version": version,
            "binary": paths.rel(paths.CATALA)}


def write_index(port: str, entries: list,
                valid_names: set[str] | None = None) -> dict:
    """Fold this run's targets into `INDEX.json`, keeping the rest.

    A run of one target must not leave an index that describes one target: the
    JSONL files of the others are still on disk and still part of the dataset,
    so an index that forgot them would understate it and quietly invalidate any
    count taken from it.  Entries are therefore merged by name --- this run's
    win and earlier valid census targets survive. ``valid_names`` removes old
    curated targets that no longer belong to the automatic census.
    """
    dataset_dir = paths.dataset(port)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    merged = {}
    old = dataset_dir / "INDEX.json"
    if old.exists():
        for e in json.loads(old.read_text()).get("targets", []):
            # An entry whose rows have since been deleted is stale.
            if ((valid_names is None or e["name"] in valid_names)
                    and (dataset_dir / e.get("file", "")).exists()):
                merged[e["name"]] = e
    for e in entries:
        merged[e["name"]] = e
    entries = [merged[k] for k in sorted(merged)]

    index = {
        "port": port,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bobcat": bobcat_version(),
        "totals": {
            "targets": len(entries),
            "objectives": sum(e.get("objectives", 0) for e in entries),
            "objectives_sat": sum(e.get("objectives_sat", 0) for e in entries),
            "objectives_unsat": sum(e.get("objectives_unsat", 0) for e in entries),
            "objectives_unknown": sum(e.get("objectives_unknown", 0) for e in entries),
            "objectives_spurious": sum(e.get("objectives_spurious", 0) for e in entries),
            "paths": sum(e["paths"] for e in entries),
            "coverage_paths": sum(e.get("coverage_paths", 0)
                                  for e in entries),
            "unparsed": sum(e["unparsed"] for e in entries),
        },
        "targets": entries,
    }
    (dataset_dir / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


def write_report(port: str, index: dict, schemas: dict) -> None:
    """`.port/<port>_bobcat/reports/DATASET.md` --- what BOBCat produced."""
    reports_dir = paths.reports(port)
    reports_dir.mkdir(parents=True, exist_ok=True)
    L = []
    L.append(f"# The goal-directed branch dataset --- {port}\n")
    repository = index["bobcat"].get("repository", "unknown repository")
    L.append(f"Generated {index['generated']} by "
             f"`bobcat_scripts/generate_dataset.py`, from BOBCat "
             f"`{(index['bobcat']['commit'] or '?')[:12]}` "
             f"({index['bobcat']['version'] or 'unknown version'}) in "
             f"`{repository}`.\n")
    L.append("One row per satisfiable branch objective: the input Z3 chose, "
             "its concrete output, and every outcome that replay exercised. "
             f"The rows are in `{paths.rel(paths.dataset(port))}/`; what the "
             f"engine actually printed is in `{paths.rel(paths.raw(port))}/`. "
             f"Compiler-native exact branch traces captured during the same "
             f"evaluation "
             f"is in `{paths.rel(paths.coverage(port))}/`; the coverage "
             f"report consumes it without replaying those rows.\n")

    L.append("| target | scope | paths | distinct outputs | errors | s | note |")
    L.append("|---|---|--:|--:|--:|--:|---|")
    for e in index["targets"]:
        flags = []
        if e["timed_out"]:
            flags.append("timed out")
        if e["incomplete"]:
            flags.append("incomplete")
        if e["unparsed"]:
            flags.append(f"{e['unparsed']} unparsed")
        if e["inexact"]:
            flags.append(f"{e['inexact']} inexact")
        if e["repeated_inputs"]:
            flags.append(f"{e['repeated_inputs']} repeated")
        note = "; ".join(flags) or e["note"] or ""
        L.append(f"| `{e['name']}` | `{e['scope']}` | {e['paths']} | "
                 f"{e['distinct_outputs']} | {e['errors']} | "
                 f"{e['seconds']:.0f} | {note} |")
    L.append("")

    L.append("## What each target's rows look like\n")
    for e in index["targets"]:
        s = schemas.get(e["name"], {})
        L.append(f"### `{e['name']}`\n")
        if e["note"]:
            L.append(e["note"] + "\n")
        L.append(f"`{e['harness']}`, scope `{e['scope']}`.\n")
        for which in ("inputs", "outputs"):
            fields = s.get(which, {})
            if not fields:
                continue
            L.append(f"*{which}*: " + ", ".join(
                f"`{n}` ({k if isinstance(k, str) else '/'.join(k)})"
                for n, k in fields.items()) + "\n")
    L.append("")

    L.append("## Reading the values\n")
    L.append("- an input is named as the compiler names it, which is the "
             "scope's field with `_in` appended (`agi` is `agi_in`): that is "
             "the name in the output being read back, and renaming it here "
             "would be this pipeline's invention rather than the engine's "
             "report;\n"
             "- money and decimals are strings (`\"50.00\"`), because a fee is "
             "a number of cents and a float is not;\n"
             "- an enumeration is `{\"cons\": \"MainCabin\"}`, with a "
             "`\"payload\"` key when the constructor carries one;\n"
             "- a struct is `{\"struct\": \"Item\", \"fields\": {...}}`;\n"
             "- a date is `\"2024-01-01\"`, a duration "
             "`{\"years\": 0, \"months\": 0, \"days\": 3}`;\n"
             "- `\"exact\": false` marks a row containing a decimal that the "
             "compiler printed truncated (with `…`), so its number is not the "
             "number that was computed;\n"
             "- `\"error\"` is set instead of the outputs when the path ended "
             "in a Catala error --- a conflict between exceptions, say --- "
             "which is a finding rather than a defect in the run.\n")
    (reports_dir / "DATASET.md").write_text("\n".join(L))
