"""Rendering an airline world to each system, and running it.

Both renderings describe the *same* world, and each is runnable on its own:

    swipl -q -f prolog.pl                    -> total_cost(N).  accepted(B).
    catala interpret catala.catala_en -s Run -> total = $N   accepted = B
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import paths
from .corpus import (Trip, CABIN_ATOM, CABIN_CATALA, ITEM_KINDS, MILITARY,
                     STATUSES, city_atom, city_catala)


# ------------------------------------------------------------------ Prolog

def render_prolog(trip: Trip, oracle: Path | None = None) -> str:
    oracle = oracle or paths.AIRLINE_ORACLE
    lines = [
        f"% {trip.id} ({trip.method})",
        "%   swipl -q -f prolog.pl",
        "",
        f":- ensure_loaded('{oracle}').",
        "",
        f"origin({city_atom(trip.origin)}).",
        f"destination({city_atom(trip.destination)}).",
        f"cabin({CABIN_ATOM[trip.cabin]}).",
        f"ticket({trip.ticket}).",
        "",
    ]
    for i, it in enumerate(trip.items, 1):
        lines.append(f"item({i},{it.kind},{it.length},{it.width},"
                     f"{it.height},{it.weight}).")
    # Stated only when not the default, so an ordinary world's `prolog.pl`
    # reads as it did before the Complimentary Bags section existed.
    comp = []
    if trip.status_at_ticketing != "no_status":
        comp.append(f"status_at_ticketing({trip.status_at_ticketing}).")
    if trip.status_at_checkin != "no_status":
        comp.append(f"status_at_checkin({trip.status_at_checkin}).")
    if trip.cardmember:
        comp.append("cardmember.")
    if trip.military != "not_military":
        comp.append(f"military({trip.military}).")
    if trip.flagship:
        comp.append("flagship.")
    if trip.children:
        comp.append(f"children({trip.children}).")
    if comp:
        lines += ["", "% Complimentary Bags attributes"] + comp
    lines += ["", ":- initialization(main, main).", ""]
    return "\n".join(lines)


_TOTAL_RE = re.compile(r"total_cost\((-?\d+)\)")
_ACC_RE = re.compile(r"accepted\((\w+)\)")


def run_prolog(source: Path, timeout: int = 60) -> dict:
    r = subprocess.run([str(paths.SWIPL), "-q", "-f", str(source)],
                       capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    m, a = _TOTAL_RE.search(r.stdout), _ACC_RE.search(r.stdout)
    return {"total": int(m.group(1)) if m else None,
            "accepted": (a.group(1) == "true") if a else None,
            "stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode}


# ------------------------------------------------------------------ Catala

def _items_catala(trip: Trip, indent: str) -> str:
    rows = [f"W.Item {{ -- kind: W.ItemKind.{ITEM_KINDS[it.kind]} "
            f"-- length: {it.length} -- width: {it.width} "
            f"-- height: {it.height} -- weight: {it.weight} }}" for it in trip.items]
    if not rows:
        return "[]"
    sep = ";\n" + indent
    return "[" + sep.join(rows) + "]"


def render_catala(trip: Trip) -> str:
    itin = (
        f"W.Itinerary {{\n"
        f"            -- origin: W.City.{city_catala(trip.origin)}\n"
        f"            -- destination: W.City.{city_catala(trip.destination)}\n"
        f"            -- cabin: W.Cabin.{CABIN_CATALA[trip.cabin]}\n"
        f"            -- ticket: ${trip.ticket}\n"
        f"            -- items:\n"
        f"                 {_items_catala(trip, '                 ')}\n"
        f"            -- status_at_ticketing: "
        f"W.EliteStatus.{STATUSES[trip.status_at_ticketing]}\n"
        f"            -- status_at_checkin: "
        f"W.EliteStatus.{STATUSES[trip.status_at_checkin]}\n"
        f"            -- cardmember: {str(trip.cardmember).lower()}\n"
        f"            -- military: W.MilitaryStatus.{MILITARY[trip.military]}\n"
        f"            -- flagship: {str(trip.flagship).lower()}\n"
        f"            -- children: {trip.children}\n"
        f"          }}")
    return f"""# {trip.id} ({trip.method})

> Using AirlineWorld as W
> Using Airline as A

The same world as `prolog.pl`, against the port.

```catala-metadata
declaration scope Run:
  internal trip content A.Trip
  output total content money
  output accepted content boolean
```

```catala
scope Run:
  definition trip equals
    output of A.Trip with {{ -- itinerary: {itin} }}
  definition total equals trip.total_cost
  definition accepted equals trip.accepted
```
"""


_CAT_TOTAL = re.compile(r"total\s*=\s*\$([\d,]+)(?:\.(\d+))?")
_CAT_ACC = re.compile(r"accepted\s*=\s*(\w+)")


def run_catala(source: Path, timeout: int = 300) -> dict:
    r = subprocess.run(paths.catala_cmd(source), capture_output=True, text=True,
                       timeout=timeout, env=paths.catala_env())
    out = r.stdout + r.stderr
    m, a = _CAT_TOTAL.search(out), _CAT_ACC.search(out)
    total = None
    if m:
        total = int(m.group(1).replace(",", ""))
        if m.group(2) and int(m.group(2)) != 0:
            total = None            # a fractional dollar is a real difference
    return {"total": total, "accepted": (a.group(1) == "true") if a else None,
            "stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode}


def run_both(trip: Trip, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    p = workdir / "prolog.pl"; c = workdir / "catala.catala_en"
    p.write_text(render_prolog(trip)); c.write_text(render_catala(trip))
    return {"prolog": run_prolog(p), "catala": run_catala(c)}
