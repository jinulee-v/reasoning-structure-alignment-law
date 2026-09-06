"""Where airline worlds come from, and which ones become test cases.

Four methods, and one rule deciding which worlds are kept: **a world is kept
when it drives the oracle down a path no kept world has taken.**  The path is
measured, not guessed --- it is the set of branch points the instrumented
oracle reaches (`coverage.py`) --- and selection consults Prolog alone, which
is what keeps the suite honest: it describes the statute's behaviour, not the
places the port happens to agree with it.

| method | scope | what it is for |
|---|---|---|
| `seed` | the 300 corpus cases | the only inputs with a known right answer, so also the harness's self-check |
| `exhaustive` | every country pair the tables distinguish x every cabin x a fixed bag universe | a completed enumeration over the statute's own vocabulary, which is a stronger claim than any number of samples |
| `boundary` | every numeric literal in the statute and its two neighbours, in the weight and size positions | the fee tables are step functions, and a step function is wrong at its steps or nowhere |
| `mutation` | worlds bred from those already kept | reaches combinations the first three do not assemble |
| `complimentary` | every AAdvantage / oneworld tier x military ground x cardmember x flagship x cabin, over eight routes | the Complimentary Bags section, which no case can state and no reference program formalizes --- so nothing external can check it, and exhaustive generation is the most that can be done |
| `carryon` | every item kind the statute names x sizes around the garment-bag limit x child counts | likewise for the carry-on section's exempt kinds and the one-diaper-bag-per-child allowance |
"""
from __future__ import annotations

import itertools
import random
import subprocess
from pathlib import Path

from . import coverage, paths
from .corpus import CABINS, CABIN_ATOM, Item, Trip, city_atom

#: one city per country the fee tables distinguish.  The statute reasons about
#: countries, so this is exhaustive at that granularity.
COUNTRY_REPS = [
    "Chicago",          # United States
    "San Juan",         # Puerto Rico
    "Toronto",          # Canada
    "Mexico City",      # Mexico
    "Havana",           # Cuba
    "Port-au-Prince",   # Haiti
    "Panama City",      # Panama
    "Bogotá",           # Colombia
    "Quito",            # Ecuador
    "Lima",             # Peru
    "Buenos Aires",     # Argentina
    "Rio de Janeiro",   # Brazil
    "Paris",            # Europe
    "Jerusalem",        # Israel
    "Doha",             # Qatar
    "Mumbai",           # India
    "Shanghai",         # China
    "Tokyo",            # Japan
    "Seoul",            # South Korea
    "Hong Kong",        # Hong Kong
    "Sydney",           # Australia
    "Auckland",         # New Zealand
    # Rows with their own fee cell that no DeonticBench case reaches, its 73
    # cities naming no city in them.
    "Charlotte Amalie", # U.S. Virgin Islands
    "Tegucigalpa",      # Honduras
    "Georgetown",       # Guyana
    "Paramaribo",       # Suriname
]

#: the AAdvantage / oneworld ladder, and the two military grounds
STATUSES = ["no_status", "gold", "platinum", "platinum_pro", "executive_platinum"]
MILITARY = ["not_military", "on_orders", "personal_travel"]
#: every item kind the carry-on section names
ITEM_KINDS = ["ordinary_bag", "soft_sided_garment_bag", "diaper_bag",
              "breast_pump", "breast_milk_cooler", "child_safety_seat",
              "stroller", "medical_or_mobility_device"]

#: Every weight the statute names, and its two neighbours: the bands are closed
#: above (`W =< 53`), so those three values fall in three different cells.
WEIGHTS = sorted({w + d for w in (50, 53, 70, 100) for d in (-1, 0, 1)} | {5, 45})

#: The same for the size limits.  A triple is chosen to hit each sum exactly.
SIZES = sorted({s + d for s in (62, 65, 115) for d in (-1, 0, 1)} | {35})

#: The carry-on box, and one item just inside and just outside it.
CARRY_ON_IN = Item(22, 14, 9, 10)
CARRY_ON_OUT = Item(23, 14, 9, 10)


def _triple(total: int) -> tuple:
    """Three dimensions summing to `total`, none of them carry-on sized."""
    a = max(23, total - 2 * (total // 3))
    b = (total - a) // 2
    return a, b, total - a - b


def _item(size: int, weight: int) -> Item:
    l, w, h = _triple(size)
    return Item(l, w, h, weight)


def seed_worlds(trips: list) -> list:
    return list(trips)


def exhaustive_worlds(bag_universe: list | None = None) -> list:
    """Every ordered country pair x every cabin x a fixed set of bag lists."""
    if bag_universe is None:
        bag_universe = [
            [],
            [CARRY_ON_IN],
            [_item(60, 40)],
            [CARRY_ON_IN, _item(60, 40)],
            [_item(60, 40), _item(64, 52), _item(70, 60)],
            [_item(60, 40)] * 4,
            [_item(120, 40)],                       # over 115 in
            [_item(60, 101)],                       # over 100 lbs
            [_item(60, 80)],                        # the 70--100 lb band
            [CARRY_ON_IN] + [_item(63, 51), _item(66, 55), _item(60, 71),
                             _item(64, 90), _item(70, 45)],
        ]
    out = []
    n = 0
    for o, d in itertools.product(COUNTRY_REPS, repeat=2):
        for cabin in CABINS:
            for items in bag_universe:
                n += 1
                out.append(Trip(id=f"x{n:06d}", origin=o, destination=d, cabin=cabin,
                                ticket=100, items=list(items), method="exhaustive"))
    return out


def boundary_worlds() -> list:
    """Every statute literal and its neighbours, in the weight and size slots.

    Crossed against the routes whose *cells* differ --- domestic, Cuba, Europe,
    Asia and Australasia are the five that carry a non-standard overweight or
    oversize figure --- and against every cabin, because the complimentary
    weight allowance is cabin-dependent.
    """
    routes = [("Chicago", "New York"), ("Chicago", "Havana"), ("Havana", "Chicago"),
              ("Chicago", "Paris"), ("Chicago", "Tokyo"), ("Chicago", "Sydney"),
              ("Chicago", "Lima"), ("Chicago", "Panama City"),
              ("Chicago", "Port-au-Prince"), ("Chicago", "Mexico City"),
              ("Chicago", "Toronto"), ("Chicago", "Rio de Janeiro")]
    out = []
    n = 0
    for (o, d) in routes:
        for cabin in CABINS:
            for size in SIZES:
                for weight in WEIGHTS:
                    n += 1
                    # one bag at the boundary, plus enough plain bags to reach
                    # each of the four fee positions
                    for k in (1, 2, 3, 4):
                        out.append(Trip(
                            id=f"b{n:06d}_{k}", origin=o, destination=d, cabin=cabin,
                            ticket=100,
                            items=[_item(60, 40)] * (k - 1) + [_item(size, weight)],
                            method="boundary"))
    return out


def complimentary_worlds() -> list:
    """Every ground the Complimentary Bags section grants an allowance on.

    This section is the one part of the statute with no oracle behind it: no
    case can state a status tier or military orders, and no reference program
    formalizes them (0 of 300).  So these worlds cannot be checked against
    anything external --- they check only that the two systems here read the
    section the same way.  They are generated exhaustively anyway, because
    that is the most that can be done, and because a rule nothing exercises is
    a rule nobody has read.
    """
    out, n = [], 0
    routes = [("Chicago", "New York"), ("Chicago", "Tokyo"), ("Chicago", "Paris"),
              ("Chicago", "Havana"), ("Chicago", "Toronto"),
              ("Chicago", "Tegucigalpa"), ("Chicago", "Georgetown"),
              ("Charlotte Amalie", "New York")]
    bags = [_item(60, 40)] * 6
    for (o, d) in routes:
        for cabin in CABINS:
            for status in STATUSES:
                for mil in MILITARY:
                    for card in (False, True):
                        for flag in (False, True):
                            n += 1
                            out.append(Trip(
                                id=f"c{n:06d}", origin=o, destination=d, cabin=cabin,
                                ticket=0, items=list(bags), method="complimentary",
                                status_at_checkin=status, military=mil,
                                cardmember=card, flagship=flag))
    # the two-status rule: ticketing and check-in resolve to the higher
    for a in STATUSES:
        for b in STATUSES:
            n += 1
            out.append(Trip(id=f"c{n:06d}", origin="Chicago", destination="New York",
                            cabin="Main Cabin", ticket=0, items=list(bags),
                            method="complimentary",
                            status_at_ticketing=a, status_at_checkin=b))
    return out


def carry_on_worlds() -> list:
    """The carry-on section's kinds: exempt items, the garment bag, diaper bags."""
    out, n = [], 0
    ordinary = [_item(60, 40)] * 3
    for kind in ITEM_KINDS:
        for size in (40, 50, 51, 52, 60):
            for children in (0, 1, 2):
                n += 1
                head = Item(*_triple(size), 20)
                head.kind = kind
                out.append(Trip(id=f"k{n:06d}", origin="Chicago", destination="New York",
                                cabin="Main Cabin", ticket=0,
                                items=[head] + ordinary, method="carryon",
                                children=children))
                n += 1
                out.append(Trip(id=f"k{n:06d}", origin="Chicago", destination="New York",
                                cabin="Main Cabin", ticket=0,
                                items=[head, head] + ordinary, method="carryon",
                                children=children))
    return out


def mutate(trip: Trip, rng: random.Random, cities: list) -> Trip:
    """One random edit to a kept world."""
    t = Trip(id="", origin=trip.origin, destination=trip.destination, cabin=trip.cabin,
             ticket=trip.ticket,
             items=[Item(i.length, i.width, i.height, i.weight, i.kind)
                    for i in trip.items], method="mutation",
             status_at_ticketing=trip.status_at_ticketing,
             status_at_checkin=trip.status_at_checkin, cardmember=trip.cardmember,
             military=trip.military, flagship=trip.flagship, children=trip.children)
    op = rng.randrange(12)
    if op == 0:
        t.origin = rng.choice(cities)
    elif op == 1:
        t.destination = rng.choice(cities)
    elif op == 2:
        t.cabin = rng.choice(CABINS)
    elif op == 3:
        t.ticket = rng.choice([0, 1, 100, 550, 9999])
    elif op == 4 and t.items:
        i = rng.randrange(len(t.items))
        t.items[i].weight = rng.choice(WEIGHTS)
    elif op == 5 and t.items:
        i = rng.randrange(len(t.items))
        l, w, h = _triple(rng.choice(SIZES))
        t.items[i].length, t.items[i].width, t.items[i].height = l, w, h
    elif op == 6:
        t.status_at_checkin = rng.choice(STATUSES)
    elif op == 7:
        t.status_at_ticketing = rng.choice(STATUSES)
    elif op == 8:
        t.military = rng.choice(MILITARY)
    elif op == 9:
        t.cardmember = not t.cardmember
        t.flagship = rng.random() < 0.5
    elif op == 10 and t.items:
        t.items[rng.randrange(len(t.items))].kind = rng.choice(ITEM_KINDS)
        t.children = rng.choice([0, 1, 2])
    elif t.items and rng.random() < 0.4:
        del t.items[rng.randrange(len(t.items))]
    else:
        t.items.append(_item(rng.choice(SIZES), rng.choice(WEIGHTS)))
    return t


# ------------------------------------------------------- running the oracle

def render_worlds(trips: list) -> str:
    out = []
    for t in trips:
        items = ", ".join(
            f"item({i},{it.kind},{it.length},{it.width},{it.height},{it.weight})"
            for i, it in enumerate(t.items, 1))
        out.append(
            f"world('{t.id}', {city_atom(t.origin)}, {city_atom(t.destination)}, "
            f"{CABIN_ATOM[t.cabin]}, {t.ticket}, [{items}], "
            f"{t.status_at_ticketing}, {t.status_at_checkin}, "
            f"{'yes' if t.cardmember else 'no'}, {t.military}, "
            f"{'yes' if t.flagship else 'no'}, {t.children}).")
    return "\n".join(out) + "\n"


#: filled in by `probe` with the union of points the last batch reached
LAST_COVERAGE: set = set()


def probe(trips: list, tag: str = "probe") -> dict:
    """Run worlds against the instrumented oracle; return id -> (total, accepted, signature).

    Also records, in `LAST_COVERAGE`, the union of branch points the batch
    reached --- the coverage figure the report quotes.
    """
    if not trips:
        return {}
    paths.SCRATCH.mkdir(parents=True, exist_ok=True)
    wfile = paths.SCRATCH / f"{tag}_worlds.pl"
    ofile = paths.SCRATCH / f"{tag}_out.txt"
    wfile.write_text(render_worlds(trips))
    r = subprocess.run(
        [str(paths.SWIPL), str(paths.PL_SUPPORT / "airline_enum.pl"), "--",
         str(coverage.COVERED), str(wfile), str(ofile)],
        capture_output=True, text=True, cwd=paths.BUILD, timeout=3600)
    if not ofile.exists():
        raise RuntimeError(f"enumeration failed:\n{r.stdout}\n{r.stderr}")
    cov = ofile.with_suffix(ofile.suffix + ".cov")
    LAST_COVERAGE.clear()
    if cov.exists():
        LAST_COVERAGE.update(p for p in cov.read_text().split("\n") if p.strip())
    res = {}
    for line in ofile.read_text().split("\n"):
        if not line.strip():
            continue
        cid, total, acc, sig = line.split("\t")
        res[cid] = (None if total == "error" else int(total),
                    None if acc == "error" else acc == "true", sig)
    return res


def select(trips: list, seen: set, tag: str) -> tuple:
    """Keep the worlds whose path signature is new, in order.

    Returns `(kept, seed_mismatches)`.

    A generated world has no known right answer, so the oracle's own figure is
    recorded as its expected value --- which makes the differential test a
    consistency check between the two systems and nothing more.  A **seed**
    world does have one, the reference program's answer, and that figure is
    left alone.  Overwriting it would turn the suite's only self-check into a
    tautology: the oracle would be checked against itself, and a wrong oracle
    would report a clean run.

    Seeds whose oracle answer differs from the reference program's are returned
    rather than silently kept: that is the step-1 validation failing, and
    nothing downstream is worth reading until it is fixed.
    """
    res = probe(trips, tag)
    kept, mismatches = [], []
    for t in trips:
        r = res.get(t.id)
        if r is None:
            continue
        total, acc, sig = r
        if t.method == "seed" and t.label is not None and total != t.label:
            mismatches.append({"id": t.id, "reference": t.label, "oracle": total})
        # Seeds are kept whether or not their path is new: they are the only
        # cases whose answer does not come from the oracle.
        if sig in seen and t.method != "seed":
            continue
        seen.add(sig)
        if t.method != "seed":
            t.label = total
        kept.append(t)
    return kept, mismatches
