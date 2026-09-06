"""Where candidate worlds come from, and which of them become test cases.

The goal is a suite that takes *every* execution path through SARA's Prolog,
not one that takes many paths many times.  So generation and selection are
separate concerns:

  **generation** proposes worlds, by four complementary methods --

    `seeds`       SARA's own 376 cases.  They are the only inputs with a known
                  right answer, so they are also the harness's self-check.
    `exhaustive`  for each query predicate, every world that can be built from
                  the event predicates *reachable* from it (the call graph in
                  `signature.json` says which), over a two-person two-event
                  universe, asked every way round.  Small enough to enumerate
                  completely for most predicates, which is a stronger claim
                  than any number of samples.
    `arguments`   for the 26 predicates that read no event facts at all --- the
                  rate brackets, the exemption amounts --- there is no world to
                  enumerate, so Prolog is asked to generate the relation
                  instead and every solution and its neighbours is checked.
    `mutation`    coverage-guided mutation of whatever has been kept so far,
                  for the predicates whose reachable signature is too large to
                  enumerate --- §3306 and `tax/3`, mostly.

  **selection** keeps a world only when it does something new.  Every candidate
  is run through the instrumented statutes, which return the *set* of branch
  points it reached; a world is kept when that set is one no kept world has
  produced (a new execution path) or when it reaches a point nothing has
  reached (new coverage).  Two worlds that drove the statutes down the same
  path cannot distinguish the two systems, so keeping both would only make the
  suite slower to run and harder to read.

Selection runs against Prolog alone.  Catala is not consulted until
`run_test_cases.py`, which is what keeps generation honest: the suite is a
description of SARA's behaviour, not of where the port happens to agree.
"""
from __future__ import annotations

import collections
import copy
import datetime
import itertools
import json
import math
import random
import re
import subprocess

from . import catala_emit as emit
from .paths import COVERED, PL_SUPPORT, SCRATCH, SIGNATURE, STATUTES, SWIPL
from .prolog import DATE_RE, load_seeds
from .grounding import input_predicates

PORTED = emit.PORTED


# ------------------------------------------------------- the input signature

def signature() -> dict:
    """The call graph and literal dictionary, read out of the statutes."""
    if not SIGNATURE.exists():
        SIGNATURE.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [str(SWIPL), str(PL_SUPPORT / "signature.pl"), "--",
             str(STATUTES), str(SIGNATURE)],
            capture_output=True, text=True)
        if not SIGNATURE.exists():
            raise RuntimeError(proc.stdout + proc.stderr)
    return json.loads(SIGNATURE.read_text())


def reachable_inputs() -> dict:
    """query predicate -> the event predicates it can actually read.

    The median is 11 of 57, and 26 predicates reach none at all.  Mutating a
    whole thirty-fact world to test a predicate that reads five of them is
    almost all wasted motion; this is what lets the exhaustive method have a
    small enough space to finish.
    """
    sig = signature()
    inputs = {f"{n}/{a}" for n, a in input_predicates()}
    graph = collections.defaultdict(set)
    for e in sig["edges"]:
        graph[e["from"]].add(e["to"])

    def reach(q):
        seen, stack = set(), [q]
        while stack:
            for y in graph.get(stack.pop(), ()):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen

    return {q: sorted(reach(q) & inputs) for q in sorted(PORTED)}


def statute_atoms() -> list:
    """Names the statutes mention outright.

    Three are in none of SARA's 376 cases and cannot appear in a generated
    world unless they are put there: `decree of divorce` and `decree of
    separate maintenance`, which §7703(b) matches by name, and
    `someone_is_nra`, which §1(a)(1) uses as the *subject* of its
    nonresident-alien bar --- a lower-case atom where SARA meant a variable,
    so the bar fires only for an event literally so named.
    """
    out = set()
    for lit in signature()["literals"]:
        v = lit["value"]
        if isinstance(v, str) and 1 < len(v) < 60 and not v.startswith("%"):
            out.add(v)
    return sorted(out)


def statute_constants() -> list:
    """Every integer literal in the statutes, and its two neighbours.

    The thresholds are where the branches are: $20,000 of agricultural wages,
    20 days of service, the §1 bracket edges.  A value one dollar either side
    of one takes a branch a random amount essentially never will.
    """
    out = set()
    for path in STATUTES.glob("section*.pl"):
        for m in re.finditer(r"(?<![\w.])(\d{2,})(?![\w.])", path.read_text()):
            n = int(m.group(1))
            out |= {n - 1, n, n + 1}
    return sorted(x for x in out if 0 <= x <= 10_000_000)


def goal_templates(seeds: list) -> dict:
    """pred/arity -> the argument patterns SARA's own cases query it with."""
    out: dict[str, list] = {}
    for rec in seeds:
        test = rec["test"]
        if len(test["goals"]) != 1:
            continue
        g = test["goals"][0]
        key = f"{g['predicate']}/{len(g['args'])}"
        if key in PORTED:
            out.setdefault(key, []).append(list(g["args"]))
    return out


# ------------------------------------------------------ method 2: exhaustive

# Two people and two events is the smallest universe satisfying the statutes'
# relational tests (a marriage has two agents; a payment a payer and a payee),
# and one more of each multiplies the enumeration cost.
PEOPLE = ["p1", "p2"]
EVENTS = ["v1", "v2"]
DATES = ['"2015-01-01"', '"2015-06-15"', '"2015-12-31"', '"2016-01-01"']
AMOUNTS = ["0", "1", "5000", "20000"]
YEAR = 2015
MULTI_ROLES = {"agent_", "patient_"}   # a marriage names both spouses
GOAL_VARIANTS = 16


def role_domain(pred: str) -> list:
    field = emit.ROLE_FIELDS.get(pred)
    if pred in ("start_", "end_"):
        return DATES
    if pred == "amount_":
        return AMOUNTS
    if field in ("purposes", "types"):
        return [f'"{p}"' for p in sorted(emit.PURPOSES)][:2] + EVENTS[:1]
    if field in ("places", "destinations"):
        return [f'"{p}"' for p in sorted(emit.PLACES)][:3]
    if field == "media":
        return [f'"{m}"' for m in sorted(emit.MEDIA)]
    if field == "countries":
        return ['"usa"', '"france"']
    if pred == "agent_":
        return PEOPLE + ['"decree of divorce"']   # §7703(b) tests it by name
    return PEOPLE


def _role_options(binary: list) -> list:
    """For each binary role, the values one event may carry in it."""
    out = []
    for b in binary:
        dom = role_domain(b)
        opts = [()] + [(v,) for v in dom]
        if b in MULTI_ROLES and len(dom) >= 2:
            opts += [tuple(c) for c in itertools.combinations(dom[:2], 2)]
        out.append((b, opts))
    return out


class ShapeSpace:
    """Every way one event can be built from a predicate's input signature,
    addressed by index rather than materialised.

    The space is a mixed-radix product: one digit for the event's kind (none,
    or any of the unary predicates), then one per binary role.  Eleven relevant
    inputs is a few hundred thousand shapes and their *pairs* are then 10^10 --
    building either as a list is what used to cap `--max-inputs` at 5.  Decoding
    an index costs nothing, so the enumeration is exhaustive where it is small
    and a reproducible sample where it is not.
    """

    def __init__(self, unary: list, binary: list) -> None:
        self.kinds = [()] + [(u,) for u in unary]
        self.roles = _role_options(binary)
        self.size = len(self.kinds)
        for _b, opts in self.roles:
            self.size *= len(opts)

    def at(self, i: int) -> list:
        shape = []
        for b, opts in reversed(self.roles):
            i, d = divmod(i, len(opts))
            if opts[d]:
                shape.append((b, opts[d]))
        shape.reverse()
        return [("kind", k) for k in self.kinds[i % len(self.kinds)]] + shape


def _pair_at(k: int, S: int) -> tuple:
    """Decode index `k` into the `k`-th unordered pair (i <= j) of `S` shapes.

    Row `i` holds the pairs (i,i)..(i,S-1), so it starts at
    `i*S - i*(i-1)/2`; inverting that is a quadratic, done in integers so the
    answer is exact rather than nearly right at the row boundaries.
    """
    disc = (2 * S + 1) ** 2 - 8 * k
    i = ((2 * S + 1) - math.isqrt(disc)) // 2
    off = lambda n: n * S - n * (n - 1) // 2          # noqa: E731
    while off(i + 1) <= k:
        i += 1
    while i > 0 and off(i) > k:
        i -= 1
    return i, i + (k - off(i))


def _worlds_for(inputs: list, cap: int, seed: int = 0):
    """Worlds over `inputs` with one or two events; all of them, or `cap` of
    them drawn reproducibly.  Returns (worlds, exhaustive, total)."""
    unary = [p.split("/")[0] for p in inputs if p.endswith("/1")]
    binary = [p.split("/")[0] for p in inputs if p.endswith("/2")]
    space = ShapeSpace(unary, binary)
    S = space.size
    # Unordered pairs only: the two event identifiers are interchangeable, so
    # (A on v1, B on v2) and (B on v1, A on v2) are the same world renamed.
    total = S + S * (S + 1) // 2

    def build(index):
        if index < S:
            return [(EVENTS[0], space.at(index))]
        i, j = _pair_at(index - S, S)
        return [(EVENTS[0], space.at(i)), (EVENTS[1], space.at(j))]

    if total <= cap:
        return [build(k) for k in range(total)], True, total
    # Draw distinct indices rather than rejection-sampling pairs: as `cap`
    # approaches `total`, rejection sampling becomes a coupon-collector problem
    # and never finishes.  `random.sample` is O(cap) whatever the ratio.
    idx = random.Random(seed).sample(range(total), cap)
    idx.sort()
    return [build(k) for k in idx], False, total


def _goals_for(key: str, templates: dict) -> list:
    """The query, re-aimed at the small universe --- every way round.

    A bound argument in SARA's template may name a person (`alice`) or an event
    (`alice_pays`), and the two are not interchangeable: a query pinned to a
    person in an event position matches nothing, and every world in the scope
    then takes the same trivial path.  Rather than guess the role of each
    position, enumerate them over the whole small universe.
    """
    if key not in templates:
        return []
    pred = key.split("/")[0]
    fixed, slots = [], []
    for a in templates[key][0]:
        bare = re.sub(r"\s+", " ", str(a)).strip().strip("\"'")
        if emit.is_var(a):
            fixed.append("_")
        elif re.match(r"^-?\d+$", bare):
            fixed.append(str(YEAR) if abs(int(bare)) < 3000 else bare)
        elif DATE_RE.match(bare):
            fixed.append(DATES[1])
        else:
            fixed.append(None)
            slots.append(len(fixed) - 1)

    out = []
    for combo in itertools.product(PEOPLE + EVENTS, repeat=len(slots)):
        row = list(fixed)
        for pos, val in zip(slots, combo):
            row[pos] = val
        out.append(f"{pred}({','.join(row)})")
        if len(out) >= GOAL_VARIANTS:
            break
    return out or [f"{pred}({','.join(fixed)})"]


def _world_to_events(world) -> tuple[dict, dict]:
    """The enumerator's shape as a world model, with every value's reading.

    The atom/string kinds cannot be re-derived downstream: `"france"` is a
    legal bare atom but the enumerator wrote it quoted, and Prolog would then
    be answering about a string while Catala answered about an atom.  The
    generator knows, so it says.
    """
    out: dict[str, list] = {}
    kinds: dict[str, str] = {}
    for ev, shape in world:
        for slot, vals in shape:
            if slot == "kind":
                out.setdefault(vals, []).append([ev])
                kinds[f"{vals}\t0\t{ev}"] = "atom"
                continue
            kinds[f"{slot}\t0\t{ev}"] = "atom"
            for v in vals:
                quoted = v.startswith('"')
                raw = v.strip('"')
                if re.match(r"^-?\d+$", raw) and not quoted:
                    out.setdefault(slot, []).append([ev, int(raw)])
                else:
                    out.setdefault(slot, []).append([ev, raw])
                    kinds[f"{slot}\t1\t{raw}"] = "str" if quoted else "atom"
    return out, kinds


def exhaustive_candidates(templates: dict, max_inputs: int, cap: int,
                          only: str = "", seed: int = 0) -> list:
    """World models covering every shape a small predicate can be asked in."""
    reach = reachable_inputs()
    out = []
    for key, ins in sorted(reach.items()):
        if not (0 < len(ins) <= max_inputs) or key not in templates:
            continue
        if only and only not in key:
            continue
        goals = [g for g in _goals_for(key, templates)
                 if re.match(r"^[a-zA-Z_0-9]+\(.*\)$", g, re.S)]
        if not goals:
            continue
        worlds, _exhaustive, _total = _worlds_for(
            ins, max(1, cap // len(goals)), seed)
        pred = key.split("/")[0]
        for wi, world in enumerate(worlds):
            events, kinds = _world_to_events(world)
            for gi, goal in enumerate(goals):
                args = [a.strip() for a in
                        re.match(r"^[a-zA-Z_0-9]+\((.*)\)$", goal, re.S)
                        .group(1).split(",")]
                out.append({
                    "id": f"{pred}_{len(args)}__x{wi:05d}_{gi}",
                    "origin": "exhaustive", "query": key,
                    "question": "", "events": events, "other": {},
                    "discontiguous": [], "value_kinds": kinds,
                    "test": {"task": "entailment", "negated": False,
                             "expected": None,
                             "goals": [{"predicate": pred, "args": args}],
                             "raw": goal, "gold_amount": None},
                })
    return out


# --------------------------------------- method 2b: exhaustive over arguments

_GENERATE_PL = """
:- ensure_loaded('{init}').
:- use_module(library(time)).
:- use_module(library(http/json)).
main :-
    findall(_{{pred: P, args: As}},
        ( member(P-N, {spec}),
          member(Pos, [0,1,2]),
          Pos < N,
          member(V, {dom}),
          functor(G, P, N),
          arg(Pos1, G, V), Pos1 is Pos + 1,
          catch(call_with_time_limit(5, G), _, fail),
          ground(G),
          G =.. [_|As] ),
        Rows0),
    sort(Rows0, Rows),
    json_write_dict(current_output, _{{rows: Rows}}), nl.
"""


def zero_input_predicates() -> list:
    """The predicates that read no event facts at all.

    26 of the 142: the §1 rate brackets, §63(c)(7)'s suspended amounts,
    §151(d)'s exemption, §68(f).  They are pure arithmetic over their own
    arguments, so there is no world to enumerate --- and enumerating worlds for
    them, which is what the method above would do, tests nothing.
    """
    reach = reachable_inputs()
    return [q for q, ins in sorted(reach.items()) if not ins]


def boundary_domain() -> list:
    """Every numeric literal the statutes mention, its two neighbours, and the
    calendar years the suspension rules turn on.

    Every one of these predicates is a threshold comparison (`Taxinc =< 36900`,
    `between(2018,2025,Taxy)`), and a threshold is exactly what a random
    generator steps over rather than lands on.
    """
    vals = {0, 1, -1} | set(range(2014, 2029))
    for lit in signature()["literals"]:
        v = lit["value"]
        if isinstance(v, int) and not isinstance(v, bool):
            vals |= {v - 1, v, v + 1}
    return sorted(v for v in vals if -1 <= v <= 10_000_000)


def _perturb(tuples: list) -> list:
    """Each solution plus its one-off neighbours.

    A bracket boundary is only tested by a pair of inputs straddling it, and
    the solution set alone lands on one side of every one.
    """
    out = set(tuples)
    for pred, args in tuples:
        for i, a in enumerate(args):
            if isinstance(a, int) and not isinstance(a, bool):
                for d in (-1, 1):
                    out.add((pred, tuple(list(args[:i]) + [a + d]
                                         + list(args[i + 1:]))))
    return sorted(out, key=lambda t: (t[0], [str(x) for x in t[1]]))


def argument_candidates(only: str = "", timeout: int = 900) -> list:
    """Ground tuples of each world-independent relation, found by Prolog itself.

    The method is functional rather than boolean.  Prolog is asked to
    *generate* the relation --- bind one argument from the boundary domain,
    leave the rest free, collect every solution --- and each solution plus its
    neighbours is then put to both systems.  So the port is not merely checked
    for agreeing on whether some tax figure is right; it is checked against the
    figure Prolog computes, at every bracket edge and on both sides of it.
    """
    preds = [q for q in zero_input_predicates()
             if not only or only in q]
    if not preds:
        return []
    spec = "[" + ",".join(f"{p.split('/')[0]}-{p.split('/')[1]}"
                          for p in preds) + "]"
    dom = "[" + ",".join(map(str, boundary_domain())) + "]"
    work = SCRATCH / "argexh"
    work.mkdir(parents=True, exist_ok=True)
    src = work / "generate.pl"
    src.write_text(_GENERATE_PL.format(init=COVERED / "init", spec=spec,
                                       dom=dom))
    proc = subprocess.run(
        [str(SWIPL), "-q", "-f", str(src), "-g", "main", "-t", "halt"],
        capture_output=True, text=True, timeout=timeout)
    src.unlink(missing_ok=True)
    start = proc.stdout.find("{")
    if start < 0:
        return []
    rows = json.loads(proc.stdout[start:])["rows"]
    tuples = _perturb([(r["pred"], tuple(r["args"])) for r in rows])

    out = []
    for n, (pred, args) in enumerate(tuples):
        toks = [quote_arg(a) for a in args]
        key = f"{pred}/{len(args)}"
        if key not in PORTED:
            continue
        out.append({
            "id": f"{pred}_{len(args)}__a{n:05d}",
            "origin": "arguments", "query": key,
            "question": "", "events": {}, "other": {},
            "discontiguous": [], "value_kinds": {},
            "test": {"task": "entailment", "negated": False, "expected": None,
                     "goals": [{"predicate": pred, "args": toks}],
                     "raw": f"{pred}(" + ",".join(toks) + ")",
                     "gold_amount": None},
        })
    return out


# -------------------------------------------------------- method 3: mutation

DATE_FIELDS = {"start_", "end_"}
INT_FIELDS = {"amount_"}
STRUCTURED = ["usa", "united states government", "state of maryland",
              "state of ohio", "france government",
              "international organization x"]


class Pools:
    """The values a mutation may draw on, read off the world it is mutating."""

    def __init__(self, rec: dict) -> None:
        ev = rec["events"]
        kinds = sorted(emit.EVENT_KINDS)
        self.event_ids = sorted({str(r[0]) for p in kinds for r in ev.get(p, [])})
        entities, self.dates, self.ints = set(), set(), set()
        for pred in sorted(emit.ROLE_FIELDS):
            for row in ev.get(pred, []):
                if len(row) != 2:
                    continue
                v = row[1]
                if isinstance(v, int) and not isinstance(v, bool):
                    self.ints.add(v)
                elif DATE_RE.match(str(v)):
                    self.dates.add(str(v))
                else:
                    entities.add(str(v))
        self.entities = sorted(entities | set(self.event_ids))
        self.dates = sorted(self.dates)
        self.ints = sorted(self.ints)
        self.years = sorted({int(d[:4]) for d in self.dates} or {2015})


class Mutator:
    """Random edits to a world model, biased at the statutes' thresholds."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.constants = statute_constants()
        self.entities = STRUCTURED + [a for a in statute_atoms()
                                      if a not in STRUCTURED]
        self.purposes = sorted(emit.PURPOSES)
        self.places = sorted(emit.PLACES)
        self.media = sorted(emit.MEDIA) + ["check", "goods"]
        self.kind_preds = sorted(emit.EVENT_KINDS)
        self.role_preds = sorted(emit.ROLE_FIELDS)

    # -- value generators --------------------------------------------------
    def a_date(self, pools: Pools) -> str:
        """Biased to year boundaries and one-day-off neighbours: the statutes
        compare against `first_day_year`/`last_day_year` constantly, and
        §3306's `%W` week number turns on which side of a Monday a day falls."""
        rng, r = self.rng, self.rng.random()
        year = rng.choice(pools.years + [rng.randint(2004, 2019)])
        if r < 0.30:
            return f"{year}-01-01"
        if r < 0.50:
            return f"{year}-12-31"
        if r < 0.75 and pools.dates:
            base = datetime.date.fromisoformat(rng.choice(pools.dates))
            return (base + datetime.timedelta(days=rng.choice(
                [-366, -31, -7, -1, 1, 7, 31, 366]))).isoformat()
        return datetime.date(year, rng.randint(1, 12),
                             rng.randint(1, 28)).isoformat()

    def an_int(self, pools: Pools) -> int:
        rng, r = self.rng, self.rng.random()
        if r < 0.45:
            return rng.choice(self.constants)
        if r < 0.75 and pools.ints:
            base = rng.choice(pools.ints)
            return max(0, base + rng.choice([-1, 1, -100, 100, -base, base]))
        return rng.randint(0, 400_000)

    def an_entity(self, pools: Pools) -> str:
        rng, r = self.rng, self.rng.random()
        if r < 0.65 and pools.entities:
            return rng.choice(pools.entities)
        if r < 0.85:
            return rng.choice(self.entities)
        return f"g_{rng.randint(0, 40)}"

    def a_role_value(self, pools: Pools, pred: str):
        rng = self.rng
        if pred in DATE_FIELDS:
            return self.a_date(pools)
        if pred in INT_FIELDS:
            return self.an_int(pools)
        field = emit.ROLE_FIELDS[pred]
        if field in ("purposes", "types") and rng.random() < 0.6:
            return rng.choice(self.purposes)
        if field in ("places", "destinations") and rng.random() < 0.7:
            return rng.choice(self.places)
        if field == "media" and rng.random() < 0.7:
            return rng.choice(self.media)
        return self.an_entity(pools)

    # -- edits -------------------------------------------------------------
    def add_fact(self, rec, pools):
        rng = self.rng
        if rng.random() < 0.35 or not pools.event_ids:
            pred = rng.choice(self.kind_preds)
            row = [self.an_entity(pools) if rng.random() < 0.4
                   else f"g_ev_{rng.randint(0, 30)}"]
        else:
            pred = rng.choice(self.role_preds)
            row = [rng.choice(pools.event_ids), self.a_role_value(pools, pred)]
        rows = rec["events"].setdefault(pred, [])
        if row not in rows:
            rows.append(row)

    def del_fact(self, rec, pools):
        preds = [p for p, rows in rec["events"].items() if rows]
        if not preds:
            return
        pred = self.rng.choice(preds)
        rec["events"][pred].pop(self.rng.randrange(len(rec["events"][pred])))
        if not rec["events"][pred]:
            del rec["events"][pred]

    def mutate_arg(self, rec, pools):
        rng = self.rng
        preds = [p for p, rows in rec["events"].items()
                 if rows and p in emit.ROLE_FIELDS]
        if not preds:
            return
        row = rng.choice(rec["events"][(pred := rng.choice(preds))])
        if len(row) != 2:
            return
        if rng.random() < 0.3:
            row[0] = rng.choice(pools.event_ids or [row[0]])
        else:
            row[1] = self.a_role_value(pools, pred)

    def clone_event(self, rec, pools):
        """Copy every fact about one event onto a fresh identifier.

        Multiplicity is semantics in §3306 --- `sum_list` over a `findall`
        counts solutions, not facts --- so duplicating an event is the edit
        most likely to separate a port that models sets from one that models
        multisets.
        """
        if not pools.event_ids:
            return
        src = self.rng.choice(pools.event_ids)
        dst = f"{src}_c{self.rng.randint(0, 99)}"
        for _pred, rows in list(rec["events"].items()):
            for row in list(rows):
                if str(row[0]) == src:
                    new = [dst] + list(row[1:])
                    if new not in rows:
                        rows.append(new)

    def retype_value(self, rec, pools):
        """Flip one value between the atom and string readings.

        SARA quotes `location_(e,usa)` in one case and `location_(e,"usa")` in
        another; `==` tells them apart and the port's symbol table does not.
        """
        cands = [(p, r) for p in ("location_", "reason_", "purpose_", "means_")
                 for r in rec["events"].get(p, [])
                 if len(r) == 2 and isinstance(r[1], str)
                 and not DATE_RE.match(str(r[1]))]
        if not cands:
            return
        pred, row = self.rng.choice(cands)
        key = f"{pred}\t1\t{row[1]}"
        kinds = rec.setdefault("value_kinds", {})
        kinds[key] = "atom" if kinds.get(key) == "str" else "str"

    def add_injection(self, rec, pools):
        """Assert a statute conclusion, the way 175 of the 376 cases do."""
        known = rec.get("_inject_pool") or []
        if not known:
            return
        rng = self.rng
        key = rng.choice(known)
        arity = int(key.split("/")[1])
        row = []
        for _ in range(arity):
            r = rng.random()
            row.append(self.an_entity(pools) if r < 0.5
                       else (rng.choice(pools.years) if r < 0.7
                             else self.an_int(pools)))
        rec["other"].setdefault(key, []).append(row)
        if rng.random() < 0.8 and key not in rec["discontiguous"]:
            rec["discontiguous"].append(key)

    def del_injection(self, rec, pools):
        keys = [k for k, v in rec["other"].items() if v]
        if not keys:
            return
        key = self.rng.choice(keys)
        rec["other"][key].pop(self.rng.randrange(len(rec["other"][key])))
        if not rec["other"][key]:
            del rec["other"][key]

    def toggle_discontiguous(self, rec, pools):
        """Declared, an injected row is an extra clause; undeclared, it
        replaces the statute's own definition.  Three of SARA's cases rely on
        the second reading, and the port models only the first."""
        keys = sorted(rec["other"])
        if not keys:
            return
        key = self.rng.choice(keys)
        if key in rec["discontiguous"]:
            rec["discontiguous"].remove(key)
        else:
            rec["discontiguous"].append(key)

    def retarget(self, rec, pools, templates):
        """Re-aim the query: same predicate as the parent most of the time, a
        different ported one now and then, with bound positions redrawn."""
        rng = self.rng
        g = rec["test"]["goals"][0]
        key = f"{g['predicate']}/{len(g['args'])}"
        if rng.random() < 0.25 or key not in templates:
            key = rng.choice(sorted(templates))
        args = list(rng.choice(templates[key]))
        for i, a in enumerate(args):
            if emit.is_var(a) or str(a).startswith("["):
                continue          # unbound stays a generator; a list stays a list
            if rng.random() < 0.45:
                continue
            # SARA writes a date argument quoted, so read the class off the
            # unquoted token; otherwise an entity lands in a date position and
            # the renderer emits `|alice|`.
            bare = str(a).strip('"\'')
            if re.match(r"^-?\d+$", bare):
                args[i] = str(rng.choice(pools.years)
                              if abs(int(bare)) < 3000 else self.an_int(pools))
            elif DATE_RE.match(bare):
                args[i] = '"' + self.a_date(pools) + '"'
            else:
                args[i] = self.an_entity(pools)
        set_goal(rec, key.split("/")[0], args)

    EDITS = [("add_fact", 5), ("mutate_arg", 5), ("del_fact", 3),
             ("clone_event", 3), ("retype_value", 2), ("add_injection", 2),
             ("del_injection", 1), ("toggle_discontiguous", 1)]

    def spawn(self, parent: dict, templates: dict, tag: str) -> dict:
        rec = copy.deepcopy(parent)
        rec["id"], rec["origin"] = tag, "mutation"
        rec.setdefault("other", {})
        rec.setdefault("discontiguous", [])
        pools = Pools(rec)
        choices = [n for n, w in self.EDITS for _ in range(w)]
        for _ in range(self.rng.randint(1, 4)):
            getattr(self, self.rng.choice(choices))(rec, pools)
        if self.rng.random() < 0.5:
            self.retarget(rec, Pools(rec), templates)
        rec["query"] = "%s/%d" % (rec["test"]["goals"][0]["predicate"],
                                  len(rec["test"]["goals"][0]["args"]))
        return rec


def quote_arg(a) -> str:
    """Write one goal argument back as Prolog.

    An argument SARA already quoted --- `s63_c_6_D("Walter Brown Family Trust
    II",1999)` --- passes through untouched.  Quoting it again asks about a
    different term, and the discrepancy that follows would be the harness's
    rather than the port's.
    """
    s = str(a)
    if (emit.is_var(s) or re.match(r"^-?\d+$", s) or s.startswith("[")
            or s[:1] in ('"', "'")):
        return s
    if re.match(r"^[a-z][a-zA-Z0-9_]*$", s):
        return s
    return '"' + s.replace('"', '\\"') + '"'


def set_goal(rec: dict, pred: str, args: list) -> None:
    """Write the query into the record, in *one* spelling.

    `raw` is what Prolog runs and `goals[].args` is what the Catala renderer
    reads, so the two have to agree down to the quoting: both pick the atom or
    the string key space by whether the token is quoted, exactly as SWI's `==`
    does.  Storing the bare value in one and the quoted token in the other
    asked the two systems about different terms and reported every such query
    as a discrepancy.
    """
    toks = [quote_arg(a) for a in args]
    rec["test"] = {
        "task": "numeric" if pred == "tax" else "entailment",
        "negated": False, "expected": None,
        "goals": [{"predicate": pred, "args": toks}],
        "raw": f"{pred}(" + ",".join(toks) + ")", "gold_amount": None,
    }


def seed_candidates() -> list:
    """SARA's 376 cases, as world models with their own goals."""
    injectable = sorted({k for rec in load_seeds() for k in rec["other"]})
    out = []
    for rec in load_seeds():
        g = rec["test"]["goals"][0]
        rec["origin"] = "seed"
        rec["query"] = f"{g['predicate']}/{len(g['args'])}"
        rec["_inject_pool"] = injectable
        out.append(rec)
    return out


def minimise(rec: dict, still_interesting, tag: str,
             budget: int = 2000) -> dict:
    """Greedy delta debugging: drop a fact, keep the drop if the property
    still holds.  A raw finding carries dozens of irrelevant facts; what makes
    it readable is the two-or-three-fact core.

    `budget` bounds the number of oracle calls.  Each call is a Prolog run and
    a Catala run, so an unbounded shrink of a hundred-fact world can outlast
    the entire suite it came from; stopping early gives a world that is smaller
    rather than smallest, which is enough to read.
    """
    cur, n = copy.deepcopy(rec), 0
    changed = True
    while changed and n < budget:
        changed = False
        for pred in sorted(cur["events"]):
            i = 0
            while i < len(cur["events"].get(pred, [])) and n < budget:
                n += 1
                cand = copy.deepcopy(cur)
                del cand["events"][pred][i]
                if not cand["events"][pred]:
                    del cand["events"][pred]
                if still_interesting(cand, f"{tag}_m{n}"):
                    cur, changed = cand, True
                else:
                    i += 1
        for key in sorted(cur.get("other", {})):
            i = 0
            while i < len(cur["other"].get(key, [])) and n < budget:
                n += 1
                cand = copy.deepcopy(cur)
                del cand["other"][key][i]
                if not cand["other"][key]:
                    del cand["other"][key]
                if still_interesting(cand, f"{tag}_m{n}"):
                    cur, changed = cand, True
                else:
                    i += 1
    return cur
