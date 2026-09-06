"""What to run CUTECat on, and why each one is on the list.

Two kinds of target.

A **port target** points straight at a file of one of the two Catala ports and
names a scope in it.  Nothing is written for these: the SARA port already
contains scopes whose inputs are money, integers, booleans and enumerations,
which is exactly what CUTECat can encode, so the statute is explored as it
stands.  This is the honest case --- the dataset is of the port, not of a
paraphrase of it.

A **harness target** points at a file under the port's own `harnesses/`. The focused airline
harnesses keep individual fee rules small even though the complete itinerary
structure, including its item list, is now directly enterable. The SARA list
harness similarly exposes existing top-level helpers through a compact scope.
Each harness says in its own header which rule it exposes and what it does not.

The one rule about adding a target: a harness may *call* the port and may
restate a two-line rule when the port's version demands an itinerary, but it
must never contain a rule the port does not.  A dataset generated from a
statute nobody wrote is worth nothing.
"""
from __future__ import annotations

from . import entrypoints, paths
from .run import Target


def _siblings(directory, exclude):
    """Every module in a port, except the one being run."""
    return sorted(p for p in directory.glob("*.catala_en") if p != exclude)


def _sara(name, file, scope, note, **kw) -> Target:
    f = paths.SARA_CATALA / file
    return Target(name=name, port="sara", harness=f, scope=scope,
                  modules=_siblings(paths.SARA_CATALA, f), note=note, **kw)


def _airline(name, harness, scope, note, **kw) -> Target:
    f = paths.harnesses("airline") / harness
    return Target(name=name, port="airline", harness=f, scope=scope,
                  modules=_siblings(paths.AIRLINE_CATALA, f), note=note, **kw)


def _sara_harness(name, harness, scope, note, **kw) -> Target:
    f = paths.harnesses("sara") / harness
    return Target(name=name, port="sara", harness=f, scope=scope,
                  modules=sorted(paths.SARA_CATALA.glob("*.catala_en")),
                  note=note, **kw)


def all_targets() -> list:
    return [
        # ---- SARA: the port's own scopes, unmodified ---------------------
        _sara("sara_section68", "Section68.catala_en", "Section68",
              "§68's overall limitation on itemized deductions: the "
              "applicable amount by filing status, the 3%/80% pair, and the "
              "2018--2025 suspension. Pure arithmetic over money and a year, "
              "which is the shape CUTECat is best at."),
        _sara("sara_basic_standard_deduction", "Section63.catala_en",
              "BasicStandardDeduction",
              "§63(c)(2)'s basic standard deduction by filing status, and "
              "(c)(7)'s doubling for 2018--2025."),
        _sara("sara_section68_reduction_one", "Section68.catala_en",
              "ReductionOneHolds",
              "§68(a)(1) as the cases query it: 3 percent of the excess of "
              "AGI over the applicable amount."),
        _sara_harness(
            "sara_role_count", "SaraRoleCount.catala_en", "RoleCount",
            "SaraIncome.role_count over a bounded symbolic list of entities. "
            "The same harness calls Section152.dates_or over a bounded list "
            "of dates to exercise its empty/non-empty branch."),
        # ---- airline: harnesses ------------------------------------------
        _airline("airline_carry_on", "AirlineCarryOn.catala_en", "CarryOn",
                 "The carry-on box, the garment-bag sum and the exempt kinds, "
                 "over one `W.Item` --- the largest part of the airline world "
                 "model that holds no list."),
        _airline("airline_allowance", "AirlineAllowance.catala_en",
                 "Allowance",
                 "The elite-status and military ladders of the Complimentary "
                 "Bags section, both functions of one enumeration."),
        _airline("airline_trip", "AirlineTrip.catala_en", "FullTrip",
                 "The whole fee computation over a one-item itinerary. The "
                 "harness builds the item list from scalar symbolic inputs, "
                 "so bounded concolic list execution can now explore it.",
                 timeout=300),
    ]


# ---- the enumerated entry points -----------------------------------------
# `all_targets()` is the hand-picked list of scopes worth a dataset; these are
# its exhaustive complement --- every remaining entry point whose inputs CUTECat
# can encode --- generated rather than curated, to answer how much of the port
# is reachable.  A port scope is named directly; a top-level function goes
# through a wrapper `entrypoints.write_harnesses` writes into the port's own
# `harnesses/generated/`.
def _port_name(directory) -> str:
    return "sara" if directory == paths.SARA_CATALA else "airline"


def enumerated_targets(refresh: bool = True) -> list:
    """One target per enterable entry point not already in `all_targets()`."""
    taken = {(t.harness.name, t.scope) for t in all_targets()}
    out = []
    for directory in (paths.SARA_CATALA, paths.AIRLINE_CATALA):
        port = entrypoints.scan(directory)
        prefix = _port_name(directory)
        siblings = sorted(directory.glob("*.catala_en"))

        # Scopes the port already has: no wrapper, run the file as it stands.
        for sig in port.entries:
            if sig.kind != "scope" or not entrypoints.enterable(sig, port.types):
                continue
            if (sig.file, sig.name) in taken:
                continue
            f = directory / sig.file
            out.append(Target(
                name=f"{prefix}_scope_{sig.file.replace('.catala_en', '')}"
                     f"_{sig.name}",
                port=prefix, harness=f, scope=sig.name,
                modules=[m for m in siblings if m != f],
                project=f"{prefix}_port_{sig.file.replace('.catala_en', '')}",
                note=f"{sig.module}.{sig.name}, a scope of the port "
                     f"({sig.file}:{sig.line})."))

        # Top-level functions: one wrapper file per source.
        written = (entrypoints.write_harnesses(port, paths.generated(prefix))
                   if refresh else _existing(port, prefix))
        for path, sigs in sorted(written.items()):
            for sig in sigs:
                out.append(Target(
                    name=f"{prefix}_fn_{sig.name}",
                    port=prefix,
                    harness=path,
                    scope=entrypoints.scope_name(sig.name),
                    modules=siblings,
                    project=f"{prefix}_wrap_{path.stem}",
                    note=f"{sig.module}.{sig.name}, a top-level function of "
                         f"the port ({sig.file}:{sig.line}), behind a "
                         f"generated wrapper scope."))
    return out


def _existing(port, prefix: str) -> dict:
    """The wrapper files already on disk, without rewriting them."""
    out = {}
    for sig in port.entries:
        if sig.kind == "function" and entrypoints.enterable(sig, port.types):
            stem = sig.file.replace(".catala_en", "")
            out.setdefault(paths.generated(prefix) / f"{stem}Wrappers.catala_en",
                           []).append(sig)
    return {k: v for k, v in out.items() if k.exists()}


def by_port(ts: list) -> dict:
    """The targets grouped by the port they belong to, ports in a fixed order.

    Every output tree is per port, so almost everything downstream wants the
    targets this way round rather than as one flat list.
    """
    out = {p: [] for p in paths.PORTS}
    for t in ts:
        out[t.port].append(t)
    return {p: v for p, v in out.items() if v}


def by_name(names: list, enumerated: bool = False) -> list:
    """Select targets by name, refusing a name that is not one."""
    ts = all_targets() + (enumerated_targets() if enumerated else [])
    if not names:
        return ts
    index = {t.name: t for t in ts}
    missing = [n for n in names if n not in index]
    if missing:
        raise SystemExit(
            f"no such target: {', '.join(missing)}\n"
            f"  known targets: {', '.join(sorted(index))}")
    return [index[n] for n in names]
