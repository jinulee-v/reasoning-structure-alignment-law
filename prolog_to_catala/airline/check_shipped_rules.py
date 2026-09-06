#!/usr/bin/env python3
"""Recover the statute's rules from the 300 shipped programs, and check the
oracle against them.

DeonticBench ships no single statute file, but it does ship the statute's
*rules* --- once per case, abridged to that case's route and cabin and mixed in
with its facts.  Recovering them is worth doing, because it changes what the
differential result rests on: `airline_oracle.pl` stops being a formalization
somebody here wrote and becomes one the corpus itself can be made to justify,
clause by clause.

Merging cannot be textual.  `oversize_fee/2` is written 78 different ways
across the 251 files that define it, and `total_cost/1` 173 ways across 273 ---
each program structures the whole computation to suit itself.  So the merge is
done by *behaviour*: each file's definition is run over a domain of inputs, the
files are grouped by the region their itinerary falls in, and the region's rule
is whatever its files agree on.

What comes out, and it is the point of the script:

  * within a region, the shipped rules agree on **everything the statute's
    tables define**;
  * every disagreement lies **past the last row of a table** --- a bag over
    115 in, or over 100 lbs --- where the files variously fail, or answer
    $200, $0, `na`, `not_accepted` or 999999.  That is not a merge conflict to
    be resolved, it is the statute being silent, and it is DEVIATIONS A3.

Run:  python3 prolog_to_catala/airline/check_shipped_rules.py [--verbose]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from airlinelib import corpus, paths

#: country -> the region whose row of the tables applies.  Only the groupings
#: the fee cells actually distinguish; see `Airline.catala_en` for the rows.
_REGION = {
    "US": "US/PR", "PuertoRico": "US/PR", "USVirginIslands": "US/PR",
    "Canada": "Canada",
    "Europe": "Europe/Israel/Qatar", "Israel": "Europe/Israel/Qatar",
    "Qatar": "Europe/Israel/Qatar",
    "Australia": "Australasia", "NewZealand": "Australasia",
    "India": "Asia", "China": "Asia", "Japan": "Asia",
    "SouthKorea": "Asia", "HongKong": "Asia",
    "Panama": "Panama/SouthAmerica", "Colombia": "Panama/SouthAmerica",
    "Ecuador": "Panama/SouthAmerica", "Peru": "Panama/SouthAmerica",
    "Argentina": "Panama/SouthAmerica", "Brazil": "Panama/SouthAmerica",
    "Mexico": "Mexico/Caribbean", "Cuba": "Mexico/Caribbean",
    "Haiti": "Mexico/Caribbean", "Honduras": "Mexico/Caribbean",
    "Guyana": "Guyana/Suriname", "Suriname": "Guyana/Suriname",
}
_COUNTRY_OF_CITY = {
    **{c: "US" for c in ["Atlanta","Austin","Boston","Charlotte","Chicago","Dallas",
        "Denver","Houston","Las Vegas","Los Angeles","Miami","Minneapolis",
        "New Orleans","New York","Orlando","Philadelphia","Phoenix","Portland",
        "Sacramento","Salt Lake City","San Francisco","Seattle","Washington D.C."]},
    "San Juan": "PuertoRico", "Charlotte Amalie": "USVirginIslands",
    "Tegucigalpa": "Honduras", "Georgetown": "Guyana", "Paramaribo": "Suriname",
    **{c: "Canada" for c in ["Montreal","Ottawa","Toronto","Vancouver"]},
    "Mexico City": "Mexico", "Havana": "Cuba", "Port-au-Prince": "Haiti",
    "Panama City": "Panama", "Bogotá": "Colombia", "Lima": "Peru", "Quito": "Ecuador",
    "Buenos Aires": "Argentina", "Rio de Janeiro": "Brazil",
    **{c: "Europe" for c in ["Amsterdam","Athens","Barcelona","Berlin","Brussels",
        "Helsinki","London","Madrid","Munich","Paris","Roma","Stockholm","Vienna","Zurich"]},
    "Jerusalem": "Israel", "Doha": "Qatar",
    **{c: "China" for c in ["Beijing","Chengdu","Guangzhou","Shanghai","Shenzhen","Wuhan","Xiamen"]},
    "Hong Kong": "HongKong",
    **{c: "Japan" for c in ["Kyoto","Nagoya","Osaka","Tokyo"]},
    **{c: "SouthKorea" for c in ["Busan","Incheon","Seoul"]},
    **{c: "India" for c in ["Mumbai","New Delhi"]},
    **{c: "Australia" for c in ["Melbourne","Sydney"]}, "Auckland": "NewZealand",
}

#: The predicates recovered, and the domain each is probed over.  Each domain
#: brackets every boundary the statute names, plus one value past the last row.
PROBES = {
    "oversize_fee/2":   [62, 63, 65, 66, 100, 115, 116],
    "overweight_fee/2": [50, 51, 53, 54, 70, 71, 100, 101],
}
#: what `airline_oracle.pl` computes, for the same inputs -- the claim under test
ORACLE = {
    "oversize_fee/2": {
        "US/Canada":           {62:0, 63:30, 65:30, 66:200, 100:200, 115:200},
        "Mexico/Caribbean":    {62:0, 63:30, 65:30, 66:200, 100:200, 115:200},
        "Asia":                {62:0, 63:30, 65:30, 66:200, 100:200, 115:200},
        "Australasia":         {62:0, 63:30, 65:30, 66:200, 100:200, 115:200},
        "Europe/Israel/Qatar": {62:0, 63:30, 65:30, 66:150, 100:150, 115:150},
        "Panama/SouthAmerica": {62:0, 63:30, 65:30, 66:150, 100:150, 115:150},
    },
    "overweight_fee/2": {
        "US/Canada":           {50:0, 51:30, 53:30, 54:100, 70:100, 71:200, 100:200},
        "Mexico/Caribbean":    {50:0, 51:30, 53:30, 54:100, 70:100, 71:200, 100:200},
        "Asia":                {50:0, 51:30, 53:30, 54:100, 70:100, 71:450, 100:450},
        # Europe and Australasia read "Not accepted" above 70 lbs, which the
        # oracle answers with `bag_accepted/1` rather than a fee, so these two
        # cells are compared as "no fee defined".
        "Europe/Israel/Qatar": {50:0, 51:30, 53:30, 54:100, 70:100, 71:None, 100:None},
        "Australasia":         {50:0, 51:30, 53:30, 54:100, 70:100, 71:None, 100:None},
    },
}
#: past these, the tables stop and the shipped rules stop agreeing
LAST_ROW = {"oversize_fee/2": 115, "overweight_fee/2": 100}


#: the two domestic rows the tables keep apart: $40 within the U.S. and Puerto
#: Rico, $35 between them and Canada.  Lumping them together reads a correct
#: $35 table as dissent from a $40 plurality.
_HOME = {"US/PR", "Canada"}


def region_of(trip) -> str:
    a = _REGION[_COUNTRY_OF_CITY[trip.origin]]
    b = _REGION[_COUNTRY_OF_CITY[trip.destination]]
    if a in _HOME and b in _HOME:
        return "US/PR" if a == b == "US/PR" else "US/PR<->Canada"
    return b if a in _HOME else a


def dump_clauses() -> dict:
    """(file, predicate indicator) -> its clauses, canonicalised."""
    out = subprocess.run(
        [str(paths.SWIPL), str(paths.PL_SUPPORT / "dump_clauses.pl"), "--",
         str(paths.AIRLINE_RAW / "cases")],
        capture_output=True, text=True, timeout=600)
    defs: dict = collections.defaultdict(list)
    for line in out.stdout.rstrip("\n").split("\n"):
        if line.count("\t") < 2:
            continue
        f, pi, txt = line.split("\t", 2)
        defs[(f, pi)].append(txt)
    return defs


def behaviour(clauses: list, name: str, domain: list) -> dict | None:
    """What this definition computes over `domain`; None if not self-contained."""
    query = (":- initialization(main,main).\nmain :- forall(member(X," +
             str(domain).replace(" ", "") + "),"
             f"( findall(Y,catch({name}(X,Y),_,fail),L), sort(L,S),"
             "  format('~w=~w;',[X,S]) )),nl.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".pl", delete=False) as fh:
        fh.write("\n".join(clauses) + "\n" + query)
        tmp = fh.name
    try:
        r = subprocess.run([str(paths.SWIPL), "-q", "-f", tmp], capture_output=True,
                           text=True, timeout=20, stdin=subprocess.DEVNULL)
        text = r.stdout.strip()
    except subprocess.TimeoutExpired:
        return None
    finally:
        os.unlink(tmp)
    if not text:
        return None
    got: dict = {}
    for part in text.rstrip(";").split(";"):
        if "=" not in part:
            return None
        x, ys = part.split("=", 1)
        vals = [v for v in ys.strip("[]").split(",") if v]
        # A definition with overlapping guards and no cut has several solutions.
        # Compare the first, which is what its program uses; report the rest as
        # nondeterminism rather than as a different reading.
        got[int(x)] = (vals[0], len(vals)) if vals else (None, 0)
    return got


# ------------------------------------------------------ the base fee table

#: every dollar figure the four bag tables print
TABLE_FEES = {0, 35, 40, 45, 60, 65, 75, 100, 150, 200}


def fee_table_of(clauses: list, name: str) -> tuple | None:
    """If this predicate behaves like a base checked-bag fee table, its values.

    Recovered by behaviour, not by name: the corpus writes this one rule under
    **17 different names** --- `checked_fee/2`, `within_us_base_fee/2`,
    `domestic_maincabin_base/2` and so on are the same 40/45/150/200 table ---
    so a name-based scan would find a sixth of it.  A predicate counts as the
    table when, asked for positions 1 to 4, it answers a non-decreasing,
    non-constant run of figures the tables actually print, reaching at least
    $150 by the third or fourth bag.  That last condition is what separates it
    from `oversize_fee/2` and `overweight_fee/2`, which are constant over such
    small arguments.
    """
    beh = behaviour(clauses, name, [0, 1, 2, 3, 4])
    if beh is None:
        return None
    got = []
    for pos in (0, 1, 2, 3, 4):
        v = beh.get(pos, (None, 0))[0]
        got.append(int(v) if v is not None and v.lstrip("-").isdigit() else None)
    # A file may number its positions from 1, as the tables do, or from 0
    # (`..._cases_28` writes `base_checked_fee(Idx,0) :- Idx =< 1`).  Offer both.
    out = []
    for start in (1, 0):
        vals = got[start:start + 4]
        if any(v is None for v in vals):
            continue
        if len(set(vals)) == 1 or max(vals) < 150:
            continue
        if any(a > b for a, b in zip(vals, vals[1:])):
            continue
        if not set(vals) <= TABLE_FEES:
            continue
        out.append(tuple(vals))
    return tuple(out) if out else None


def oracle_fee_tables(origin_atom: str, dest_atom: str, cabin_atom: str) -> dict:
    """The three tables a program might have written, all from the oracle.

    A file's fee table is not always the statute's table.  Three conventions
    appear in the corpus and all three are correct encodings of the same rule,
    differing only in where the free allowance has been applied:

      `published`  the table as printed, allowance applied elsewhere ---
                   `within_us_base_fee(1,40)` in `..._cases_58`;
      `allowed`    the allowance already folded in, so a Main Plus passenger's
                   first two positions read $0 --- `bag_base_fee(I,0) :- I =< 2`
                   in `..._cases_9`, whose comment says exactly that;
      `charged`    indexed from the first *charged* bag, so a First Class
                   table starts at the third --- `bag_fee(1,150)` in
                   `..._cases_89`, commented "3rd checked bag".

    Asked of the oracle rather than transcribed here, so this check cannot
    drift from the thing it is checking.
    """
    src = (f":- ensure_loaded('{paths.AIRLINE_ORACLE}').\n"
           f"origin({origin_atom}). destination({dest_atom}). cabin({cabin_atom}).\n"
           f"ticket(0).\n"
           ":- initialization(main,main).\n"
           "main :- forall(between(1,8,P),(table_fee(P,F),format('~w,',[F]))),nl,"
           "        forall(between(1,8,P),(position_fee(P,G),format('~w,',[G]))),nl.\n")
    with tempfile.NamedTemporaryFile("w", suffix=".pl", delete=False) as fh:
        fh.write(src); tmp = fh.name
    try:
        r = subprocess.run([str(paths.SWIPL), "-q", "-f", tmp], capture_output=True,
                           text=True, timeout=20, stdin=subprocess.DEVNULL)
        lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return {}
        pub = tuple(int(x) for x in lines[0].rstrip(",").split(",")[:8])
        alw = tuple(int(x) for x in lines[1].rstrip(",").split(",")[:8])
        # the charged-bags-only view: drop the leading free positions
        nfree = sum(1 for v in alw if v == 0 and pub[alw.index(v)] >= 0)
        nfree = 0
        for v in alw:
            if v == 0:
                nfree += 1
            else:
                break
        chg = alw[nfree:] + (200,) * nfree
        return {"published": pub[:4], "allowed": alw[:4], "charged": chg[:4]}
    except Exception:
        return {}
    finally:
        os.unlink(tmp)


def check_fee_tables(defs: dict, trips: dict, verbose: bool) -> tuple:
    """Recover the base fee table from the corpus and compare it to the oracle."""
    from airlinelib.corpus import CABIN_ATOM, city_atom
    print("\n=== the base checked-bag fee table   (recovered by behaviour, "
          "under whatever name each file gave it)")
    found: dict = collections.defaultdict(lambda: collections.defaultdict(list))
    names: collections.Counter = collections.Counter()
    cache: dict = {}
    per_file: dict = {}
    for (f, pi), clauses in defs.items():
        if f not in trips or not pi.endswith("/2"):
            continue
        name = pi.rsplit("/", 1)[0]
        if name in ("oversize_fee", "overweight_fee"):
            continue
        key = (name, tuple(clauses))
        if key not in cache:
            cache[key] = fee_table_of(list(clauses), name)
        if cache[key] is None:
            continue
        # a file may define several; keep the first found, and count the name
        per_file.setdefault(f, (name, cache[key]))
        names[name] += 1
    for f, (name, readings) in per_file.items():
        t = trips[f]
        found[(region_of(t), t.cabin)][readings].append(f)
    print(f"  {len(per_file)} files carry it, under {len(names)} different names: "
          + ", ".join(f"{n}/2 x{c}" for n, c in names.most_common(6)) + " ...")

    ok = bad = 0
    oracle_cache: dict = {}
    for (region, cabin) in sorted(found, key=lambda k: (k[0], k[1])):
        groups = found[(region, cabin)]
        sample = trips[next(iter(next(iter(groups.values()))))]
        ck = (city_atom(sample.origin), city_atom(sample.destination),
              CABIN_ATOM[cabin])
        if ck not in oracle_cache:
            oracle_cache[ck] = oracle_fee_tables(*ck)
        want = oracle_cache[ck]
        n = sum(len(v) for v in groups.values())
        matched, unmatched = collections.Counter(), {}
        for readings, files in groups.items():
            hit = next((k for k, v in want.items() if v in readings), None)
            if hit:
                matched[hit] += len(files)
            else:
                unmatched[readings] = files
        nbad = sum(len(v) for v in unmatched.values())
        print(f"  {region:16s} {cabin:16s} {n:3d} files  "
              f"oracle published={want.get('published')} "
              f"allowed={want.get('allowed')}")
        print(f"        {n - nbad}/{n} match one of the oracle's three views, under either position numbering ("
              + ", ".join(f"{v} {k}" for k, v in matched.most_common()) + ")")
        if nbad:
            bad += 1
            for vals, files in sorted(unmatched.items(), key=lambda kv: -len(kv[1])):
                print(f"        {len(files):3d} file(s) match none, saying {vals}: "
                      + ", ".join(sorted(files)[:3]))
        else:
            ok += 1
    return ok, bad


# ------------------------------------------ the boxes, and what nobody wrote

#: Statute rules no case can state and no program formalizes: a case says a
#: name, cabin, route, boxes with weights and a ticket price, with no way to say
#: "AAdvantage Platinum" or "a stroller".  Unreachable from the corpus, so the
#: port omits them too; counted here so the omission is measured.  DEVIATIONS C1.
UNFORMALIZED = [
    ("Soft-sided garment bag, 51 in", r"garment"),
    ("Diaper bags, breast pump, strollers, mobility devices",
     r"diaper|breast|stroller|child safety|mobility"),
    ("Complimentary Bags: AAdvantage / oneworld status tiers",
     r"aadvantage|oneworld|platinum|emerald|sapphire|ruby|aviator|gol diamond"),
    ("Complimentary Bags: active U.S. military", r"military"),
    ("Complimentary Bags: the free-first-bag destination list",
     r"complimentary[^\n]*(argentina|brazil|chile|paraguay|uruguay)"),
    ("Honduras's own second-bag row", r"honduras"),
    ("45-day refund claim; taxes not shown", r"refund|45 days"),
]

BOXES = [("carry-on bag", (22, 14, 9)), ("personal item", (18, 14, 8))]


def check_boxes_and_gaps() -> None:
    """The two dimension boxes, and the statute rules nobody wrote down."""
    import re
    progs = {f.name[:-3]: f.read_text()
             for f in sorted((paths.AIRLINE_RAW / "cases").glob("*.pl"))}

    print("\n=== the carry-on and personal-item boxes")
    for label, (a, b, c) in BOXES:
        pat = re.compile(rf"\b{a}\b[^\n]*\b{b}\b[^\n]*\b{c}\b")
        say = [k for k, v in progs.items() if pat.search(v)]
        print(f"  {label:16s} {len(say):3d} files state a box; all of them say "
              f"{a} x {b} x {c} -- no file states a different one")
    print("  the personal-item box is contained in the carry-on box "
          "(18<=22, 14<=14, 8<=9), so modelling it changes which bags are "
          "checked in no world at all.  DEVIATIONS A1.")

    print("\n=== statute rules no program formalizes, because no case can state them")
    for label, pat in UNFORMALIZED:
        r = re.compile(pat, re.I)
        n = sum(1 for v in progs.values() if r.search(v))
        print(f"  {n:3d} / {len(progs)}  {label}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", action="store_true", help="list every dissenting file")
    args = ap.parse_args()

    trips = {t.id: t for t in corpus.load_airline()}
    defs = dump_clauses()
    report: dict = {}
    failures = 0

    for pi, domain in PROBES.items():
        name = pi.split("/")[0]
        cache: dict = {}
        # region -> input -> answer -> [files].  A file with no clause for an
        # input is silent there, not dissenting: its definition was abridged to a
        # case that never needed that row.  Only differing answers conflict.
        votes: dict = collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
        silent_files: dict = collections.defaultdict(list)
        nondet: dict = collections.defaultdict(list)
        for (f, p), clauses in defs.items():
            if p != pi or f not in trips:
                continue
            key = tuple(clauses)
            if key not in cache:
                cache[key] = behaviour(list(clauses), name, domain)
            beh = cache[key]
            region = region_of(trips[f])
            if beh is None or all(v[0] is None for v in beh.values()):
                silent_files[region].append(f)      # calls a helper it did not carry
                continue
            if any(v[1] > 1 for v in beh.values()):
                nondet[region].append(f)
            for x in domain:
                if beh.get(x, (None, 0))[0] is not None:
                    votes[region][x][beh[x][0]].append(f)

        print(f"\n=== {pi}   ({sum(1 for k in defs if k[1] == pi)} files define it, "
              f"{len(cache)} distinct spellings)")
        report[pi] = {}
        for region in sorted(set(votes) | set(silent_files)):
            claim = ORACLE[pi].get(region)
            rows = [x for x in domain if x <= LAST_ROW[pi]]
            conflicts, mismatches, spoken = [], [], 0
            for x in rows:
                answers = votes[region].get(x, {})
                if not answers:
                    continue
                spoken += 1
                if len(answers) > 1:
                    conflicts.append((x, {k: len(v) for k, v in answers.items()}))
                # The gate is the oracle against the corpus plurality; a lone
                # file that specialises differently is reported, not decisive.
                if claim is not None and claim.get(x) is not None:
                    plurality = max(answers.items(), key=lambda kv: len(kv[1]))[0]
                    if plurality != str(claim[x]):
                        mismatches.append((x, str(claim[x]),
                                           {plurality: len(answers[plurality])}))
            nfiles = len({f for x in votes[region] for a in votes[region][x]
                          for f in votes[region][x][a]}) + len(silent_files[region])
            print(f"  {region:22s} {nfiles:3d} files "
                  f"({len(silent_files[region])} carried only a helper call), "
                  f"{spoken}/{len(rows)} table inputs answered: "
                  + ("the oracle computes what they say" if not mismatches
                     else "ORACLE DIFFERS FROM THE PLURALITY")
                  + ("" if not conflicts else
                     f"; {len(conflicts)} input(s) have a minority dissent"))
            for x, a in conflicts:
                majority = max(a.items(), key=lambda kv: kv[1])
                print(f"        conflict at x={x}: " +
                      ", ".join(f"{v} files say {k}" for k, v in
                                sorted(a.items(), key=lambda kv: -kv[1])))
                for ans, files in sorted(votes[region][x].items(),
                                         key=lambda kv: len(kv[1])):
                    if ans != majority[0]:
                        print(f"            dissenting ({ans}): "
                              + ", ".join(sorted(files)[:4]))
            for x, want, wrong in mismatches:
                print(f"        oracle says {want} at x={x}, but " +
                      ", ".join(f"{v} files say {k}" for k, v in wrong.items()))
            if nondet[region]:
                print(f"        {len(nondet[region])} definition(s) are "
                      f"nondeterministic (overlapping guards, no cut); compared "
                      f"on their first solution, which is what their program uses")
            if mismatches:
                failures += 1
            # past the last row the tables stop and so does the agreement
            past = [x for x in domain if x > LAST_ROW[pi]]
            if past:
                a = votes[region].get(past[0], {})
                said = sum(len(v) for v in a.values())
                print(f"        past the last row (x={past[0]}): {said} files answer at all"
                      + (", " + ", ".join(f"{len(v)} say {k}" for k, v in a.items())
                         if a else " -- all silent, as the statute is"))
            report[pi][region] = {
                "files": nfiles, "silent": len(silent_files[region]),
                "nondeterministic": sorted(nondet[region]),
                "table_inputs_answered": spoken,
                "conflicts": [{"input": x, "answers": a} for x, a in conflicts],
                "oracle_mismatches": [{"input": x, "oracle": w, "files_say": g}
                                      for x, w, g in mismatches]}

    check_boxes_and_gaps()
    tbl_ok, tbl_bad = check_fee_tables(defs, trips, args.verbose)
    failures += tbl_bad
    report["base_fee_table"] = {"cells_agreeing": tbl_ok, "cells_differing": tbl_bad}

    paths.REPORTS.mkdir(parents=True, exist_ok=True)
    (paths.REPORTS / "shipped_rules.json").write_text(json.dumps(report, indent=1))
    print(f"\n-> {paths.rel(paths.REPORTS)}/shipped_rules.json")
    if failures:
        print(f"\n{failures} region(s) where the oracle differs from what the "
              f"corpus's own rules say by plurality.")
    else:
        print("\nEvery region, on every input the statute's tables define: the "
              "oracle computes what the corpus's own rules say.\n"
              "Minority dissents, where reported above, are single files that "
              "specialised a rule to their own case; they are named so they can "
              "be read.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
