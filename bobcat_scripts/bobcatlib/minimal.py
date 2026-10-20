"""Greedy reduction of a generated suite to maximal branch-outcome cover."""
from __future__ import annotations

import heapq
import json
from collections import defaultdict
from datetime import datetime, timezone

from . import paths


def _coverage_records(port: str, target_names: list[str], meta: list):
    inventory = set()
    for target in target_names:
        source = paths.coverage(port) / f"{target}.jsonl"
        if not source.exists():
            continue
        with source.open() as f:
            for line in f:
                record = json.loads(line)
                if record.get("kind") == "branch_manifest":
                    inventory.update(record["branches"])
                elif record.get("kind") == "branch_path":
                    outcomes = set(record["branches"])
                    meta.append((target, record["path"], outcomes))
    ordered = sorted(inventory)
    index = {outcome: i for i, outcome in enumerate(ordered)}
    masks = []
    for _target, _path, outcomes in meta:
        mask = 0
        for outcome in outcomes:
            if outcome in index:
                mask |= 1 << index[outcome]
        masks.append(mask)
    return ordered, masks


def _greedy(masks: list[int]) -> tuple[list[tuple[int, int]], int]:
    """Lazy greedy maximum coverage; return (row index, marginal gain)."""
    coverable = 0
    heap = []
    for i, mask in enumerate(masks):
        coverable |= mask
        heap.append((-mask.bit_count(), i))
    heapq.heapify(heap)
    uncovered = coverable
    chosen = []
    while uncovered and heap:
        _bound, i = heapq.heappop(heap)
        gain = (masks[i] & uncovered).bit_count()
        next_bound = -heap[0][0] if heap else -1
        if gain < next_bound:
            heapq.heappush(heap, (-gain, i))
            continue
        if gain == 0:
            break
        chosen.append((i, gain))
        uncovered &= ~masks[i]
    return chosen, coverable.bit_count()


def _narrow(selected: list[int], masks: list[int]) \
        -> tuple[list[int], list[tuple[int, int, int]]]:
    """Swap selected rows for narrower rows without changing suite coverage.

    Greedy set cover optimizes the number of rows, but an early choice can be
    much broader than it needs to be once the later choices are present.  For
    each selected slot, the bits not covered by the other selected rows are
    the only ones its replacement must contain.  Repeatedly make the largest
    strict reduction in per-row branch positions until no one-for-one swap is
    possible.

    Return the refined row indexes and ``(slot, old index, new index)`` for
    every swap.  Strictly decreasing mask sizes make the search terminate.
    """
    selected = list(selected)
    if not selected:
        return selected, []

    suite_coverage = 0
    for i in selected:
        suite_coverage |= masks[i]
    ordered_candidates = sorted(range(len(masks)),
                                key=lambda i: (masks[i].bit_count(), i))
    swaps = []

    while True:
        # Prefix/suffix unions let every slot's "all other rows" union be
        # computed without rebuilding it for every candidate.
        prefix = [0]
        for i in selected:
            prefix.append(prefix[-1] | masks[i])
        suffix = [0] * (len(selected) + 1)
        for slot in range(len(selected) - 1, -1, -1):
            suffix[slot] = suffix[slot + 1] | masks[selected[slot]]

        selected_set = set(selected)
        best = None
        for slot, old in enumerate(selected):
            old_size = masks[old].bit_count()
            required = suite_coverage & ~(prefix[slot] | suffix[slot + 1])
            if not required:
                # A redundant row should be removed by a cardinality
                # minimizer, not exchanged for an arbitrary near-empty row.
                continue
            for new in ordered_candidates:
                new_size = masks[new].bit_count()
                if new_size >= old_size:
                    break
                if new in selected_set or required & ~masks[new]:
                    continue
                proposal = (old_size - new_size, -slot, -new, slot, old, new)
                if best is None or proposal[:3] > best[:3]:
                    best = proposal
                # Candidates are ordered by size then index, so this is the
                # best replacement for this slot.
                break

        if best is None:
            break
        _saving, _slot_key, _new_key, slot, old, new = best
        selected[slot] = new
        swaps.append((slot, old, new))

        refined_coverage = 0
        for i in selected:
            refined_coverage |= masks[i]
        assert refined_coverage == suite_coverage

    return selected, swaps


def _marginal_gains(selected: list[int], masks: list[int]) -> list[int]:
    """Return each row's new coverage in the given presentation order."""
    covered = 0
    gains = []
    for i in selected:
        gains.append((masks[i] & ~covered).bit_count())
        covered |= masks[i]
    return gains


def write(port: str, project) -> dict:
    """Build ``dataset_minimal`` from the port's current complete dataset."""
    source_dir = paths.dataset(port)
    source_index = json.loads((source_dir / "INDEX.json").read_text())
    target_names = [t["name"] for t in source_index["targets"]]

    meta = []
    outcomes, masks = _coverage_records(port, target_names, meta)
    greedy, covered = _greedy(masks)
    greedy_indexes = [i for i, _gain in greedy]
    selected_indexes, swaps = _narrow(greedy_indexes, masks)
    selected = list(zip(selected_indexes,
                        _marginal_gains(selected_indexes, masks)))

    out = paths.dataset_minimal(port)
    out.mkdir(parents=True, exist_ok=True)
    # Replace only files generated by this routine. The directory itself is
    # intentionally stable so a running visualizer does not lose its cwd.
    for old in out.glob("*.jsonl"):
        old.unlink()

    wanted = defaultdict(dict)
    examples = []
    for example_index, (row_index, gain) in enumerate(selected):
        target, path_index, covered_outcomes = meta[row_index]
        wanted[target][path_index] = (example_index, gain, covered_outcomes)
        examples.append({"index": example_index, "target": target,
                         "path": path_index, "branch_gain": gain,
                         "branch_outcomes": masks[row_index].bit_count()})

    swap_records = []
    for slot, old, new in swaps:
        old_target, old_path, _old_outcomes = meta[old]
        new_target, new_path, _new_outcomes = meta[new]
        swap_records.append({
            "slot": slot,
            "from": {"target": old_target, "path": old_path,
                     "branch_outcomes": masks[old].bit_count()},
            "to": {"target": new_target, "path": new_path,
                   "branch_outcomes": masks[new].bit_count()},
        })

    selected_rows = {}
    for target, by_path in wanted.items():
        rows = {}
        with (source_dir / f"{target}.jsonl").open() as f:
            for line in f:
                row = json.loads(line)
                if row["path"] in by_path:
                    rows[row["path"]] = row
        selected_rows[target] = rows
        with (out / f"{target}.jsonl").open("w") as f:
            for path_index, row in sorted(rows.items()):
                f.write(json.dumps(row, sort_keys=True) + "\n")

    with (out / "COVERAGE.jsonl").open("w") as f:
        for e in examples:
            _idx, _gain, covered_outcomes = wanted[e["target"]][e["path"]]
            f.write(json.dumps({"target": e["target"], "path": e["path"],
                                "branches": sorted(covered_outcomes)}) + "\n")

    target_index = {t["name"]: t for t in source_index["targets"]}
    targets = []
    for target in sorted(wanted):
        entry = dict(target_index[target])
        entry["file"] = f"{target}.jsonl"
        entry["paths"] = len(wanted[target])
        targets.append(entry)
    manifest = {
        "port": port,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("lazy greedy maximum coverage over exact source branch "
                   "outcome IDs, followed by coverage-preserving one-for-one "
                   "narrowing"),
        "source_dataset": paths.rel(source_dir),
        "branch_outcomes_coverable": covered,
        "branch_outcomes_in_manifest": len(outcomes),
        "narrowing": {
            "swaps": swap_records,
            "branch_outcomes_before": sum(masks[i].bit_count()
                                          for i in greedy_indexes),
            "branch_outcomes_after": sum(masks[i].bit_count()
                                         for i in selected_indexes),
        },
        "examples": examples,
        "targets": targets,
        "totals": {"examples": len(examples), "targets": len(targets)},
    }
    (out / "INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "README.md").write_text(
        "# Greedy maximal branch-cover suite\n\n"
        f"Selected **{len(examples)}** examples from "
        f"{source_index['totals']['paths']} generated paths. The suite covers "
        f"all **{covered}** exact branch-outcome IDs reached by any "
        "recorded input. It first chooses the input covering the largest "
        "number of exact outcomes not covered by earlier choices. It then makes "
        "coverage-preserving one-for-one swaps for tests that cover fewer "
        "branch outcomes; "
        f"**{len(swaps)}** swaps reduced the sum of per-test branch outcomes "
        f"from **{manifest['narrowing']['branch_outcomes_before']}** to "
        f"**{manifest['narrowing']['branch_outcomes_after']}**.\n")
    return manifest
