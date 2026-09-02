"""Name the statute provision each system consulted, so the two can be compared.

Agreeing on the verdict is weak evidence: two systems can reach the same answer
through different provisions, and one of them is then right by accident.  The
stronger question is whether they *followed the same trail* --- whether the set
of statute provisions consulted on a given input is the same.

Both sides can be made to say, and neither was designed to:

* SARA names its Prolog predicates after the statute --- `s7703_a_1` is
  §7703(a)(1), `s152_c_1_B` is §152(c)(1)(B) --- so a clause in the coverage
  trace carries its provision in its name.
* the port's Catala carries `law_headings` on every decision, and the headings
  spell the subdivision out: `("(a)(1) Determination as of the close of the
  taxable year", "§7703. Determination of marital status")`.

So a provision id like `7703(a)(1)` is derivable from each, mechanically and
without a hand-written correspondence table --- which matters, because a
hand-written table is exactly the kind of thing that gets written until the
comparison passes.

What the comparison is *not*: an equality that ought to hold.  The two systems
are deliberately factored differently (Layer 0 has no statute of its own; the
port cuts two dependency cycles SARA leaves in place), and Prolog backtracks
into provisions it then abandons.  `compare` reports the two sets and their
difference and leaves the judgement to the caller; `depth` exists because
agreement at section level is a much weaker claim than agreement at
`(a)(1)(B)`, and the two are worth reporting apart.
"""
from __future__ import annotations

import re

# The nine sections SARA formalises.  Requiring the number to be one of these
# keeps `s151_individual` and `total_wages_employer` --- helpers, not
# provisions --- out of the comparison rather than inventing a §151_individual.
SECTIONS = {"1", "2", "63", "68", "151", "152", "3301", "3306", "7703"}

# A subdivision label: `(a)`, `(1)`, `(B)`, `(ii)`, `(I)`.  Anything else that
# follows the section number in a predicate name is a qualifier SARA added
# (`_applies`, `_individual`), not a level of the statute.
_LABEL = re.compile(r"^(?:[a-z]|[A-Z]|\d+|i{1,3}|iv|vi{0,3}|ix|x|"
                    r"I{1,3}|IV|VI{0,3}|IX|X)$")

_PRED = re.compile(r"^s(\d+)((?:_[A-Za-z0-9]+)*)$")
_SECTION_IN_HEADING = re.compile(r"§\s*(\d+)")
_LEADING_LABELS = re.compile(r"^((?:\([^()]+\))+)")


def of_prolog(predicate: str):
    """`s152_c_1_B` -> `152(c)(1)(B)`; a helper predicate -> None."""
    m = _PRED.match(predicate)
    if not m or m.group(1) not in SECTIONS:
        return None
    section, rest = m.group(1), m.group(2)
    labels = []
    for part in rest.split("_")[1:]:
        if not _LABEL.match(part):
            break            # `_applies`, `_individual`: stop, keep the prefix
        labels.append(part)
    return section + "".join("(%s)" % x for x in labels)


def of_catala(headings: list):
    """The provision a Catala law heading stack names, or None for Layer 0.

    Order-independent: the section is whichever heading carries a section sign,
    and the subdivision is the deepest heading opening with bracketed labels.
    """
    section = None
    for h in headings:
        m = _SECTION_IN_HEADING.search(h)
        if m and m.group(1) in SECTIONS:
            section = m.group(1)
            break
    if section is None:
        return None
    # `law_headings` runs innermost-first, and a nested heading may restate the
    # path (`(a)(2) Legal separation` under `§7703`) or only its own last step
    # (`(2) Legal separation` under `(a) General rule`).  Composing outwards-in
    # and treating a restatement as a replacement handles both; taking the
    # longest single heading, which is what this did first, silently turned
    # §7703(a)(2) into §7703(2) and made a third of the corpus look divergent.
    labels: list = []
    for h in reversed(headings):
        m = _LEADING_LABELS.match(h.strip())
        if not m:
            continue
        here = re.findall(r"\(([^()]*)\)", m.group(1))
        if len(here) > len(labels) and here[:len(labels)] == labels:
            labels = here              # a restatement of the path so far
        else:
            labels = labels + here     # this heading's own step
    return section + "".join("(%s)" % x for x in labels)


_SPLIT = re.compile(r"^(\d+)((?:\([^()]*\))*)$")


def split(provision: str):
    """`152(c)(1)(B)` -> ("152", ["c", "1", "B"])."""
    m = _SPLIT.match(provision)
    if not m:
        return provision, []
    return m.group(1), re.findall(r"\(([^()]*)\)", m.group(2))


def truncate(provision: str, depth: int) -> str:
    """`152(c)(1)(B)` at depth 2 -> `152(c)(1)`; at depth 0 -> `152`."""
    section, labels = split(provision)
    return section + "".join("(%s)" % x for x in labels[:depth])


class Alignment:
    """The depth at which the two systems actually distinguish a provision.

    SARA's predicate names distinguish 185 provisions; the port's law headings
    distinguish 60.  Comparing the two sets at full depth therefore measures
    annotation granularity, not behaviour: SARA has a predicate per
    §152(c)(2)(A) and (B) where the port has one scope under §152(c)(2), so
    every case looks divergent whatever either system does.

    An aligned comparison truncates each provision to the longest prefix that
    *both* vocabularies contain, so the question asked is only ever one both
    sides can answer.  The vocabularies are read off the two sources --- the
    statutes' predicate names and the port's headings --- not written by hand.
    """

    def __init__(self, prolog_vocab: set, catala_vocab: set) -> None:
        self.common = prolog_vocab & catala_vocab
        self._cache: dict = {}

    def __call__(self, provision: str) -> str:
        if provision in self._cache:
            return self._cache[provision]
        section, labels = split(provision)
        best = section
        for n in range(len(labels) + 1):
            cand = section + "".join("(%s)" % x for x in labels[:n])
            if cand in self.common:
                best = cand
        self._cache[provision] = best
        return best


def prolog_vocabulary(clause_index: dict) -> set:
    """Every provision SARA's predicate names distinguish."""
    out = set()
    for rows in clause_index.values():
        for _line, pred in rows:
            v = of_prolog(pred)
            if v:
                out.add(v)
    return out


_HEADING = re.compile(r"^(#+)\s*(.+)$")


_DEFINES = re.compile(r"^\s*(definition|rule|assertion)\s")


def catala_observable(sources) -> set:
    """The provisions a Catala trace can actually show the port consulting.

    Only *scope* variables produce trace events.  A provision the port
    implements as a top-level `declaration ... equals` --- a constant like
    §151(d)(1)'s `exemption_base equals $2,000`, or a pure function like
    §68(b)'s `applicable_amount depends on status` --- is evaluated perfectly
    well and leaves no trace at all.

    Counting those as "the port never consulted this rule" is how the trail
    comparison manufactures its own findings: the three provisions at the top
    of that list by volume were all of this kind, and none of them was a
    defect.  A provision is observable here iff some `definition`, `rule` or
    `assertion` sits under it.
    """
    out, stack = set(), []
    for src in sorted(sources):
        stack = []
        for line in src.read_text().splitlines():
            m = _HEADING.match(line)
            if m:
                stack = stack[:len(m.group(1)) - 1] + [m.group(2).strip()]
                continue
            if _DEFINES.match(line):
                v = of_catala(list(reversed(stack)))
                if v:
                    # A definition under `(c)(1)(A)` also evidences `(c)(1)`
                    # and `(c)`: entering the deeper one means entering those.
                    section, labels = split(v)
                    for n in range(len(labels) + 1):
                        out.add(section + "".join("(%s)" % x for x in labels[:n]))
    return out


def catala_vocabulary(sources) -> set:
    """Every provision the port's law headings distinguish."""
    out, stack = set(), []
    for src in sorted(sources):
        stack = []
        for line in src.read_text().splitlines():
            m = _HEADING.match(line)
            if not m:
                continue
            stack = stack[:len(m.group(1)) - 1] + [m.group(2).strip()]
            v = of_catala(list(reversed(stack)))
            if v:
                out.add(v)
    return out


def from_prolog_trace(points: list, describe) -> set:
    """Provisions named by the clauses a Prolog coverage trace entered."""
    out = set()
    for point in points:
        p = of_prolog(describe(point)["predicate"])
        if p:
            out.add(p)
    return out


def from_catala_trace(events: list) -> set:
    """Provisions named by the law headings of a Catala JSON trace."""
    out = set()
    for ev in events:
        if ev.get("event") != "DecisionTaken":
            continue
        p = of_catala(ev.get("pos", {}).get("law_headings") or [])
        if p:
            out.add(p)
    return out


def compare(prolog_set: set, catala_set: set, depth=None) -> dict:
    """The two sets, reduced to a common vocabulary, and their difference.

    `depth` is an int to truncate at a fixed level, or an `Alignment` to reduce
    each provision to the deepest level both systems distinguish.
    """
    reduce = ((lambda p: truncate(p, depth)) if isinstance(depth, int)
              else (depth or (lambda p: p)))
    a = {reduce(p) for p in prolog_set}
    b = {reduce(p) for p in catala_set}
    return {
        "depth": depth,
        "both": sorted(a & b),
        "prolog_only": sorted(a - b),
        "catala_only": sorted(b - a),
        "agree": a == b,
        "jaccard": (len(a & b) / len(a | b)) if (a | b) else 1.0,
    }
