"""Delta debugging: shrink a disagreeing world to the smallest one that still
disagrees.

A defect in a shared rule --- one fee cell, one boundary --- shows up in every
world that reaches it, and those worlds differ in everything else.  Reporting
them as a list is reporting the same finding hundreds of times.  Shrinking
first, and grouping on what survives, is what makes the report readable, and it
is the same discipline `prolog_to_catala/sara/run_test_cases.py` applies.

Each move drops or simplifies one part of the world and is kept only if the two
systems still disagree afterwards.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import airline
from .corpus import CABINS, Item, Trip


def _disagrees(trip: Trip) -> bool:
    with tempfile.TemporaryDirectory() as d:
        r = airline.run_both(trip, Path(d))
    return not (r["prolog"]["total"] is not None
                and r["prolog"]["total"] == r["catala"]["total"]
                and r["prolog"]["accepted"] == r["catala"]["accepted"])


def _copy(t: Trip) -> Trip:
    return Trip(id=t.id, origin=t.origin, destination=t.destination, cabin=t.cabin,
                ticket=t.ticket, items=[Item(i.length, i.width, i.height, i.weight)
                                        for i in t.items],
                label=t.label, method=t.method)


def shrink(trip: Trip, rounds: int = 4) -> dict:
    """The smallest world reachable by these moves that still disagrees."""
    best = _copy(trip)
    for _ in range(rounds):
        changed = False

        # drop one item at a time, greedily
        i = 0
        while i < len(best.items):
            cand = _copy(best)
            del cand.items[i]
            if _disagrees(cand):
                best = cand
                changed = True
            else:
                i += 1

        # flatten the ticket, which never interacts with any rule
        if best.ticket != 0:
            cand = _copy(best)
            cand.ticket = 0
            if _disagrees(cand):
                best, changed = cand, True

        # simplify each remaining item towards the smallest, lightest bag that
        # still shows the disagreement
        for i in range(len(best.items)):
            for field, floor in (("weight", 1), ("length", 23), ("width", 1), ("height", 1)):
                cand = _copy(best)
                setattr(cand.items[i], field, floor)
                if _disagrees(cand):
                    best, changed = cand, True

        # try a cabin that is simpler to reason about
        for cabin in CABINS:
            if cabin == best.cabin:
                continue
            cand = _copy(best)
            cand.cabin = cabin
            if _disagrees(cand):
                best, changed = cand, True
                break

        if not changed:
            break
    return best.to_json()
