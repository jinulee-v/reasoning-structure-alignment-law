# DeonticBench *airline* → Catala port

Translating DeonticBench's [airline](https://huggingface.co/datasets/gydou/DeonticBench)
domain (Dou et al. 2026) — the published American Airlines checked-bag policy,
with 300 cases — into Catala, and validating it differentially against the
benchmark's own Prolog.

The port is validated *against* the Prolog rather than derived from it: the
Catala is written from the statute text, and the Prolog serves as a differential
oracle. Acceptance is agreement on a representative of **every execution path**
the statute can be driven down, not merely on the 300 cases.

This is the same apparatus as [`../sara/`](../sara/README.md),
and reuses its coverage transform unchanged so the two ports' numbers are
comparable. One thing about the corpus forces a structural difference, and it
is the first thing to understand about this tree.

## DeonticBench ships no shared formalization

SARA has one Prolog formalization of nine IRC sections and 376 case files
against it. DeonticBench has **no shared statute at all**: each of the 300
airline cases carries a self-contained Prolog program with the rules and that
case's facts together, and the rules are re-derived, abridged to the case, in
each one. Two consequences:

1. **A fuzzed world has nothing to run on.** A per-case program's facts are
   baked into it, and its rules are specialised to that case's route and cabin
   — `airline_cases_complexity_0_airline_cases_26` hardcodes the Premium
   Economy domestic fee table and nothing else. You cannot ask it about a
   different world.
2. **The oracle has to be assembled, and then earned.** So this tree adds the
   file the benchmark does not ship: `airlinelib/pl/airline_oracle.pl`, one
   generic formalization of the statute over a world given as facts.

The rules themselves, though, **are** shipped — inside each `reference_prolog`,
abridged to that case and mixed in with its facts — and the oracle is checked
against them, not merely written alongside them. That is
`check_shipped_rules.py`, and it is the third validation step; see
[Recovering the statute's rules from the corpus](#recovering-the-statutes-rules-from-the-corpus).

Validation is therefore in **two steps** rather than one:

| step | what is checked | result |
|---|---|---|
| 1 | the shared oracle against all 300 per-case reference programs, each on its own world | **300/300** |
| 1b | the oracle's fee functions and fee table against the *rules* those programs carry, region by region | **every region and cell agrees** |
| 1c | the port against **RuleArena**, the independently written upstream reference, on every fuzzed world it can express | **agrees** (and found the >100 lb difference) |
| 2 | the Catala port against the shared oracle, on the 300 seed worlds and on every generated world | **23,906/23,906** |

Step 1 is a gate, not a footnote: `generate_test_cases.py` runs it first and
says so, and the seed cases keep the reference program's answer as their
expected value rather than the oracle's --- otherwise the only check with an
external ground truth would be the oracle checked against itself.

Last full run (2026-09-05, after the move to `prolog_to_catala/`): a suite of
**23,906 test cases**, one per distinct execution path, covering **489/632 =
77.4%** of the oracle's goal positions. **All 23,906 agree**, the 300 seed
cases agree *and* reproduce the reference programs' own answers, and
DeonticBench's `hard` subset is **80/80**. Generation took 310 s and the run
328 s.

Step 1 is what makes step 2 mean anything. Without it the oracle would be a
second guess at the statute rather than a stand-in for the corpus.

## Status

| step | state |
|---|---|
| 1. Reproduce the reference programs' answers | **done** — 300/300 |
| 2. Pin the statute's semantics | **done** — one reading reproduces all 300 labels |
| 3. Shared Prolog oracle | **done** — 300/300 against the per-case programs |
| 4. Catala port of the statute | **done** — `data/catala_gold/airline/Airline.catala_en` |
| 5. Branch instrumentation | **done** — 483 goal positions over 152 clauses |
| 6. Green on every generated execution path | **done** — 23,906/23,906 |

### That the corpus is self-consistent is a result, not an assumption

The 300 programs were written independently and each restates the rules it
needs, so they could easily have disagreed with one another — in which case no
single Catala could agree with all of them and the whole exercise would be
ill-posed. It was measured before anything was written: a single reading of the
statute reproduces the reference answer on **300/300** cases.

The same measurement on DeonticBench's `uscis-aao` domain came out the other
way, and that domain is deliberately **not** in this tree. Its 242 reference
programs share no formalization: the mean pairwise Jaccard overlap of their
predicate vocabularies is **0.021**, and **94.4%** of the 6,080 predicates they
use appear in exactly one case — they are case-specific paraphrases of each
record (`indian_court_order_jan21_1984_authorized_adoption_and_permission_to_export`),
and 65 of the 242 hardcode the outcome with a `fail`-bodied predicate. There is
no statute there to write once and test against, only 242 unrelated programs;
a "port" would be 242 unrelated transliterations, and agreement on them would
measure a transliterator, not a formalization.

## What the measurements forced

Each of these changed the port, and each was measured over all 300 cases rather
than chosen a priori. The full list, with what is still undetermined, is in
[DEVIATIONS.md](DEVIATIONS.md).

| finding | consequence |
|---|---|
| exactly **one** item fits the carry-on box in each of the 300 cases; the 45 that also fit the personal-item box are that same item | the statute's "1 carry-on **and** 1 personal item" allowance and the Prolog's "every bag inside the box" test cannot be told apart by any case. The port follows the Prolog (DEVIATIONS A1) |
| `airline_cases_complexity_0_airline_cases_14` enumerates all pairs of complimentary bags and takes `min_list` | which bags take the 70 lb allowance is a **minimisation**, not a rule. The port ranks rather than searches, which is equivalent because the base fees do not depend on the allocation |
| Main Plus fails 24 of 41 cases under a flat one-free-bag reading | the Main Cabin allowance is read off the tables — the leading positions already priced at $0 — so Main Plus is 1 domestically and 2 internationally, exactly where the footnote's "(max of 2)" binds |
| a free bag in `..._cases_12` is followed by a **$45**, not a $40 | the allowance waives a position's fee; it does not renumber the bags behind it |
| `..._cases_46` (First, to Japan) is $70 short under a two-complimentary-bag reading | "complimentary" means *priced at $0*, which on that route is three positions, not the two of the explicit allowance. Unifies First/Business, Australasia and the free-first-bag routes under one rule |
| Rio de Janeiro is $15 dearer than Lima for a Basic Economy first bag | South America splits: Colombia/Ecuador/Peru at $45, the rest at $60. The coarse region tags that got 283/300 had to become the statute's own row structure |
| weights run 5–100 lbs and sizes 35–115 in, and no Europe or Australasia case has a bag over 70 lbs | every "Not accepted" cell is unreached. The port returns a second output, `accepted`, rather than inventing a fee (DEVIATIONS A3) |
| the oracle's `table_fee(3,0)` succeeded where `table_fee(3,F)` gives 150 | calling a fee predicate with its output **bound** skips the earlier clauses' guards by head unification. Cost two of the 300; the oracle now always binds a fresh variable and tests it. The same defect class SARA's `findall/3` and `sum_list/2` positions have |
| a world with **no items** threw in a standalone `prolog.pl` but computed inside the enumerator | the enumerator asserts into `item/5` and so declares it dynamic; a generated file with no items left it with no clauses at all, and calling an undefined predicate is an existence_error in SWI rather than a failure. The oracle now declares the four world predicates dynamic, so "no such fact" means false in both settings. The suite covers this --- the empty bag list is in `exhaustive_worlds`, and the runner executes the standalone `prolog.pl` --- but a manual probe of eight adversarial worlds reached it first, while the differential run was still going |
| 562 cases returned no Catala value at all | the emitter spelled Rio de Janeiro's enumeration case `RiodeJaneiro` where the port declares `RioDeJaneiro` --- the default "drop spaces and hyphens" rule is right for twenty of the twenty-one multi-word cities and wrong for the one with a particle. `corpus.check_gazetteer` now reads the port's own `City` declaration and refuses to emit anything if a corpus city does not name a case of it |

## Testing: every execution path, not every case

The 300 cases were written to illustrate the policy, not to exercise it. The
acceptance criterion is therefore not "the same answer on 300 cases" but

> the same answer on a representative of **every execution path** the statute
> can be driven down.

Two scripts, and one directory of test cases between them.

### 1. `generate_test_cases.py` — build the suite

Writes `.port/airline/test_cases/<id>/`, three files per case:

```
prolog.pl           the world as facts + the query, runnable on its own:
                        swipl -q -f prolog.pl        ->  total_cost(N).  accepted(B).
catala.catala_en    the same world, as a standalone Catala program against the port:
                        catala interpret catala.catala_en -s Run -I data/catala_gold/airline \
                            --stdlib data/catala_gold/airline/_build/libcatala --bin data/catala_gold/airline/_build
meta.json           the world model, where it came from, and its path signature
```

Worlds come from four methods, and one rule decides which become test cases:
**a world is kept when it drives the oracle down a path no kept world has
taken.**

| method | scope | what it is for |
|---|---|---|
| `seed` | the 300 corpus cases | the only inputs with a known right answer, so also the harness's self-check |
| `complimentary` | every status tier x military ground x cardmember x flagship x cabin, over eight routes | the Complimentary Bags section, which nothing external can check |
| `carryon` | every item kind x sizes around the 51 in garment-bag limit x child counts | likewise for the exempt kinds and the diaper-bag allowance |
| `exhaustive` | every ordered pair of the 22 countries the tables distinguish × every cabin × a fixed bag universe | a completed enumeration over the statute's own vocabulary, which is a stronger claim than any number of samples. The statute reasons about countries, so this is exhaustive at the granularity anything can depend on |
| `boundary` | every numeric literal in the statute and its two neighbours, in the weight and size slots, over the twelve routes whose cells differ | the fee tables are step functions, and a step function is wrong at its steps or nowhere |
| `mutation` | worlds bred from those already kept | reaches combinations the first three do not assemble |

#### How the methods differ from `prolog_to_catala/sara`

The apparatus is the same shape and shares the coverage transform, but three of
the four methods are not the same, and the seeds differ most.

| | SARA | airline |
|---|---|---|
| **seeds** | 376 case files of Prolog *facts*, loaded against the one shared statute. `grounding.py` runs them and reads the world model out of the Prolog | 300 whole programs, with no shared statute to load them against. The world model is parsed from the **English case text** instead --- all 300 parse one grammar --- and is then validated by requiring the oracle to reproduce the label from it |
| **exhaustive** | each predicate's *reachable input signature*, which the call graph computes (the median predicate reads 11 of 57 event predicates), over a two-person two-event universe | the statute's own vocabulary: all 22 x 22 country pairs x 6 cabins x a fixed bag universe. The statute reasons about countries, so this is exhaustive at the granularity anything can depend on |
| **third method** | `arguments`: for the 26 predicates that read no event facts, ask **Prolog to generate the relation** --- bind one argument from a boundary domain, leave the rest free, check every solution | `boundary`: every numeric literal in the statute and its two neighbours, in the weight and size slots. There is no predicate here whose relation Prolog could enumerate --- every fee is a total function of the world --- so generation has nothing to do and the step functions' steps are what matter |
| **mutation** | same | same |
| **strengthening** | "the expected value comes from SARA": a mutated world makes a bound goal like `tax(alice,2018,259487)` go stale, so the case degrades into a `false` that proves little; the last pass asks SARA for the value it derives and rebinds it | not needed. The query is always `total_cost(T)` with `T` unbound, so there is no bound goal to go stale and every case is already an exact value assertion |
| **trail comparison** | `--compare-trails` asks whether both systems consulted the same statute provisions | not implemented |

One thing is *not* a method in either tree and should not be read as one: the
eight adversarial worlds probed by hand that turned up the empty-world defect.
That was a manual check run while a background job finished, it is in no
script, and the suite covers the same ground --- see the defect table above.

The path is measured, not guessed. `.port/airline/build/airline_oracle_covered.pl`
is the oracle with every body goal position rewritten as

```prolog
cov('airline_oracle.pl:118:0:c'), ( Dim =< 62 *-> true ; cov('...:0:f'), fail )
```

so a position is fully covered only when the goal has been seen both succeeding
*and* failing — branch coverage, **483 points over 152 clauses**. The transform
is `prolog_to_catala/sara/saralib/pl/cover_transform.pl`, reused rather than
reimplemented. The soft cut is what makes the rewrite transparent:
`( G *-> true ; fail )` has exactly `G`'s solutions in exactly `G`'s order,
where `->` would have committed to the first.

Selection consults **Prolog alone**. Catala is not run until the second script,
which is what keeps the suite honest: it describes the statute's behaviour, not
the places the port happens to agree with it.

### 2. `run_test_cases.py` — run them and report

Runs both programs for every case, compares both outputs — the dollar total
*and* the `accepted` verdict — and writes `.port/airline/reports/DISCREPANCIES.md`
and `report.json`.

The report is **grouped, not enumerated**. One defect in a shared rule shows up
in every world that reaches it, so each discrepancy is first shrunk by delta
debugging (`airlinelib/minimise.py` — drop an item, flatten the ticket, shrink a
dimension, simplify the cabin; keep the move if the two systems still disagree)
and then grouped by what is left.

The seed cases are reported separately, and to a stricter standard: they must
not merely agree with each other but match **the reference program's own
answer**, which is the corpus's gold label. Agreement between two things that
are both wrong is the failure mode a self-check exists to catch.

### What the 23,906 does and does not establish

Worth stating plainly, because the headline number invites a stronger reading
than it deserves.

**The Catala and the oracle are siblings.** SARA's port can say that its Catala
was written from the statute and checked against a Prolog *somebody else
wrote*. Here there is no such single Prolog, so the oracle file is mine, and
both it and the Catala descend from one reading of the statute that was fitted
to the 300 labels (a Python sketch, iterated 0/300 -> 91 -> 259 -> 283 -> 300)
before either was written.

What repairs this in part is step 1b. The rules *are* shipped, once per case,
and `check_shipped_rules.py` recovers them and checks the oracle's fee
functions against them --- so on the fee tables the oracle is no longer only
mine: it computes what the corpus's own rules say, region by region, on every
input those tables define. That is a check the 300/300 does not give, because a
program's rules define fees its own bags never had.

The recovery covers three of the statute's rule families and the two dimension
boxes:

| rule | files carrying it | names it is written under | result |
|---|--:|--:|---|
| `oversize_fee` | 251 | 1 | one behaviour per region; oracle agrees |
| `overweight_fee` | 167 | 1 | one behaviour per region; oracle agrees |
| the base checked-bag fee table | 245 | **20** | all 245 match the oracle, in all 30 (region, cabin) cells |
| carry-on box | 92 | --- | unanimously 22 x 14 x 9 |
| personal-item box | 19 | --- | unanimously 18 x 14 x 8 |

What is still **not** recovered, and is therefore checked only by whole-program
agreement (the 300/300) rather than rule by rule:

* the **complimentary-bag minimisation** --- `choose_two/3` with `min_list/2`,
  in 54 files. Every file that performs it structures the search differently,
  and comparing searches needs more than probing a function over a domain;
* the **free-allowance count** for Main Plus, which most files fold into their
  fee table rather than state (which is why the table has three indexings);
* `total_cost/1` itself --- 273 files, **173 spellings**, because that is where
  each program's own structure lives.

So:

* **What the 23,906 shows** is transcription fidelity between two genuinely
  different encodings of that reading --- Catala's functional style with
  default logic against Prolog's clause order with cuts. That is not a
  triviality: all three defects the run found were real, and the fee tables
  are ordered-row structures where an off-by-one row is easy to make and
  invisible until something exercises it. It also shows the reading is
  *internally consistent* over a much larger space than the corpus.
* **What it does not show** is that the reading is right off the corpus. Where
  a shared misreading would live, both systems would agree and the run would
  stay green.

How much space that is, measured: the corpus reaches **40 of the 484** country
pairs the tables distinguish, and **111 of the 2,904** (pair, cabin)
combinations --- **4%**. Its items never exceed 100 lbs or 115 in, and no
Europe or Australasia case has a bag over 70 lbs. Everything outside that is
checked by agreement alone.

External ground truth exists in exactly one place and it is checked there: the
300 seed worlds, where the reference programs supply an answer neither of my
two systems produced. That is step 1, it is 300/300, and it gates the run.

The places where a shared misreading is most likely are not a mystery either
--- they are the entries in [DEVIATIONS.md](DEVIATIONS.md) marked **B** and
**C**, which are precisely the readings the corpus cannot force: the row order
of the fee tables (B1), Premium Economy's "---" cells (A2), and the "Not
accepted" band (A3). Reading those against the statute is the work that
remains; no amount of fuzzing will do it.

### Recovering the statute's rules from the corpus

`python3 prolog_to_catala/airline/check_shipped_rules.py`

Merging the 300 programs into one file cannot be done textually: `oversize_fee/2`
is written **78 different ways** across the 251 files that define it, and
`total_cost/1` **173 ways** across 273, because each program structures the whole
computation to suit itself. So the merge is done by *behaviour*. Each file's
definition is run over a domain that brackets every boundary the statute names,
the files are grouped by the region their itinerary falls in, and the region's
rule is what its files say.

Two things make the result readable, and both were wrong in the first version
of this script:

* **Silence is not dissent.** A definition with no clause for an input was
  abridged to a case that never needed that row. It abstains; it does not
  disagree. Counting abstention as a conflicting reading made 11 regions look
  broken.
* **Nondeterminism is not dissent either.** A definition with overlapping
  guards and no cut has several solutions; its program uses the first, so that
  is what is compared.

What comes out:

| | |
|---|---|
| `oversize_fee/2` | 251 files, 78 spellings, **17 behaviours** --- and one per region: $200 above 65 in for US/Canada, Mexico/Caribbean, Asia and Australasia; $150 for Europe/Israel/Qatar and Panama/South America |
| `overweight_fee/2` | 167 files, 73 spellings --- $30 to 53 lbs, $100 to 70, then $200, except $450 for Asia, and *no clause at all* for Europe and Australasia |
| the base fee table | 245 files under **20 different names** --- `checked_fee/2`, `within_us_base_fee/2` and `domestic_maincabin_base/2` are the same 40/45/150/200 table --- recovered by behaviour and matching the oracle in all 30 (region, cabin) cells |
| the oracle | computes what they say, in every region, on every input the tables define |
| disagreement | lies almost entirely **past the last row** --- a bag over 115 in or over 100 lbs --- where files variously fail, or answer $200, $0, `na`, `not_accepted` or 999999 |

Recovering the fee table needed one more distinction than the fee functions
did, and getting it wrong made four correct files look like dissenters. A
file's table is not always the statute's table: it may have the free allowance
already folded in (`bag_base_fee(I,0) :- I =< 2`, whose comment says so), or be
indexed from the first *charged* bag (`bag_fee(1,150)`, commented "3rd checked
bag"), or count positions from **0** (`base_checked_fee(Idx,0) :- Idx =< 1`,
commented "Idx 0 or 1 -> 1st / 2nd checked"). All four are correct encodings of
one rule. The check asks the oracle for all three views and accepts a file that
matches any, under either numbering --- and then 245 of 245 match.

That last row is the finding worth having. It is not a merge conflict to be
resolved by picking a winner: it is the statute being silent, and the corpus's
own authors disagreeing about what to do about it. It is DEVIATIONS A3,
independently confirmed.

Two files dissent *inside* a table, and the script names them:

* `..._cases_49` writes `overweight_fee(W,0) :- W =< 70`, charging nothing
  below 70 lbs. It is a First Class case, and First Class complimentary bags do
  carry a 70 lb allowance --- so the file has collapsed the allowance into the
  fee function. 147 other files, including six other First Class cases and
  eleven Business, keep them apart. It reproduces its own label, so nothing in
  the corpus can see it.
* `..._cases_69` answers the atom `na` above 70 lbs on a Europe route and
  propagates it through `max_fee/3` so the bag is rejected. That is not a fee
  and not a conflict --- it is the same reading the port takes with
  `bag_accepted`, and it is corroboration rather than dissent. Two other files
  answer $0 there instead.

### RuleArena, the corpus's upstream, and the one independent oracle

DeonticBench's airline domain descends from **RuleArena** (Zhou et al., ACL
2025, <https://github.com/skyriver-2000/rulearena>): same policy, same six
cabins, same three complexity tiers --- `airline_cases_complexity_0/1/2` are
its `comp_0/1/2` --- and its `airline/compute_answer.py` reproduces **all 300**
of DeonticBench's labels. Found by looking, after the claim that no
independent implementation existed turned out to be worth checking.

Two things follow, and they pull in opposite directions.

**It closes the "siblings" gap, partly.** `check_rulearena.py` runs RuleArena's
Python over this suite's worlds and compares. It is the only oracle in this
tree that nobody here wrote, so on the worlds it can express it is evidence
about the *reading*, not just about transcription.

It cannot express all of them, and the script reports how many it skipped:

* RuleArena models a route as **the U.S. and one other region**, so a
  foreign-to-foreign itinerary is outside it. So is every DeonticBench case ---
  all 300 are U.S. <-> X --- but the fuzzer generates them freely, and roughly
  **half the suite** is foreign-to-foreign. There the port rests on its own
  reading of the tables' row order, checked by nothing (DEVIATIONS B1).
* RuleArena drops the carry-on **positionally**, always `bag_list[0]`, where
  this port drops every item inside the 22 x 14 x 9 box. The two coincide when
  the first item is in the box and no other is --- true of all 300 cases,
  because RuleArena's generator built them that way, and false for many fuzzed
  worlds. Which also explains DEVIATIONS A1's measurement: exactly one item
  fits the box in every case *by construction upstream*, not by coincidence.

**It found a real difference.** On the comparable fuzzed worlds the two agreed
1,048 times and differed twice, both on a **101 lb bag**. The statute's
overweight table stops at 100 lbs; this port stopped with it and answered a
flat $200 above, calling the figure a placeholder. RuleArena carries the top
band upward instead --- $450 to or from Asia, $200 otherwise. The port now does
the same, because RuleArena is the only implementation that speaks where the
statute is silent, and `bag_accepted` already carries the statutory meaning.
See DEVIATIONS A3.

**It does not supply the missing rules.** RuleArena names its scope explicitly,
as a `rule_list` of ten:

```python
rule_list = [
    "1 base check price matching", "2 base check price matching",
    "3 base check price matching", "4+ base check price matching",
    "oversize fee matching", "overweight fee matching",
    "complementary overweight", "maximum violation fee",
    "main plus extra complementary", "overall fee aggregation",
]
```

That is the same ten this port implements. AAdvantage and oneworld status,
military orders, garment bags, strollers and Honduras are absent from
RuleArena too --- the benchmark family scoped them out, and neither its
generator nor its answer key can express them.

#### Rules the corpus never formalizes at all, and what became of them

The other half of the question is what the *statute* has that no program
implements. Measured over all 300:

| statute rule | programs formalizing it |
|---|--:|
| Soft-sided garment bag, 51 in | **0** |
| Diaper bags, breast pump, strollers, mobility devices | **0** |
| Complimentary Bags: AAdvantage / oneworld status tiers | **0** |
| Complimentary Bags: active U.S. military | **0** |
| Complimentary Bags: the free-first-bag destination list | **0** |
| Honduras's own second-bag row | **0** |
| 45-day refund claim; taxes not shown | **0** |

None is reachable from a case, which says only a name, a cabin, a route, a list
of boxes with weights, and a ticket price. There is no way to state a status
tier, military orders, a stroller or a garment bag.

**They are implemented anyway**, and the honest label for them is different
from everything else in this tree. `AirlineWorld` grew `EliteStatus`,
`MilitaryStatus` and `ItemKind`, and six fields on `Itinerary`; `Airline` grew
a Complimentary Bags section and a fuller carry-on section; the oracle grew
the same; and the generator grew `complimentary` and `carryon`, which
enumerate the new grounds exhaustively over their own vocabulary.

Every new field defaults to *nothing*, which is what keeps the rest honest:
a world that does not mention a status tier renders exactly the `prolog.pl` it
rendered before the section existed, and the 300 cases are untouched --- the
oracle still reproduces all 300 reference answers, which is the regression
test that matters.

But **these rules are checked for agreement between the two systems and for
nothing else.** No case states them, no reference program formalizes them, and
RuleArena scoped them out. Where the rest of the port is answerable to the
corpus, these are answerable only to a reading, which is written out in
DEVIATIONS C1 along with the two choices it turns on --- that the grounds take
a maximum rather than stacking, and that ticketing and check-in resolve to the
higher.

Writing them turned up one thing worth knowing: the "Confirmed Domestic First
/ Business / Premium Economy" rule and the whole free-first-bag **destination
list** are *redundant* with the fee tables over every route the port can
express. The tables already price those cabins' first two bags at $0 and
already give Main Cabin a free first bag to every country on the list. They
are encoded because the statute states them separately, not because any world
turns on them.

The gate is the oracle against the **plurality** reading. A lone file that
specialised a rule to its own case is reported and named, but it does not get
to decide what the statute says.

### Reading the coverage number

Two numbers get reported and only the first is a measurement:

* **371/483 = 76.8%** — the goal positions the suite reached. This is the
  number.
* the residual, 112 points, split by *evidence* rather than counted as one
  lump. Written to `.port/airline/reports/coverage_audit.json`:

  | bucket | points | what it means |
  |---|--:|---|
  | harness | 11 | in `main/0`, which the enumerator never calls |
  | unproven | 89 | an `f` point on a goal no run has been seen to fail |
  | **reachable** | **12** | a genuine gap in the suite |

  So the honest statement is not "76.8% covered" but **12 of 483 positions are
  untested and could be tested**. The definitions:

  * **harness** — in the oracle's `main/0`, which the enumerator never calls: it
    asks `total_cost/1` and `accepted/0` directly. Outside the suite by
    construction rather than missed.
  * **unproven** — an `f` point on a goal no run has ever been seen to fail.
    Probably it has none: `sum_list(L, Total)` with `Total` unbound succeeds or
    throws, and 35 of the 89 are unifications like `Fee = 45` that bind a fresh
    output variable to a constant. Probably is not certainly, and the
    hypothesis has already been wrong in this tree — see the `table_fee(3,0)`
    row above. So a functor observed failing anywhere is never counted as
    unfailable anywhere, and `=` is kept apart from `=\=`, `=:=` and `=<`,
    which fail readily and are reported as `(comparison)`.
  * **reachable** — the goal has been observed failing at some other position,
    so nothing about the goal itself is in the way. A plain gap in the suite.

## Running it

```bash
# toolchain, once -- shared with prolog_to_catala/sara, and already built if that tree ran
bash install_toolchain.sh

# `generate_test_cases.py` runs `clerk start` and compiles the port's two
# modules itself, so a fresh clone needs nothing else.
python3 prolog_to_catala/airline/generate_test_cases.py     # -> .port/airline/test_cases/
python3 prolog_to_catala/airline/run_test_cases.py          # -> .port/airline/reports/

# useful variants
python3 prolog_to_catala/airline/generate_test_cases.py --quick        # seeds only, ~1 min
python3 prolog_to_catala/airline/generate_test_cases.py --mutants 20000 # push coverage
python3 prolog_to_catala/airline/run_test_cases.py --only complexity_2
python3 prolog_to_catala/airline/run_test_cases.py --no-minimise       # faster, noisier
```

**`.port/airline/` is generated in its entirety** — `rm -rf .port/airline` is
always safe, and the next run rebuilds it from the pristine corpus in
`data/prolog/airline/` and from the port itself.

## Layout

```
data/prolog/airline/        pristine upstream (tracked; never edit)
  airline/cases/               the 300 per-case reference Prolog programs
  airline/meta/                text, question, label, hard flag
  airline/statutes/            section1_non_textual, shared by all 300
  PROVENANCE.txt               source URLs, revision, sha256, fetch date

prolog_to_catala/airline/               the whole apparatus, and the two documents
  README.md                    this file
  DEVIATIONS.md                where the Prolog departs from the statute, and
                               where the statute does not determine an answer
  generate_test_cases.py       build the suite            <- entry point
  run_test_cases.py            run it, report             <- entry point
  airlinelib/
    paths.py                   locations and the Catala toolchain
    corpus.py                  the raw cases -> world models
    airline.py                 world -> Prolog, world -> Catala, run both
    generate.py                the four generation methods, and selection
    coverage.py                instrument the oracle; point -> statute source
    minimise.py                delta debugging for the report
    pl/airline_oracle.pl       the shared statute formalization -- the oracle
    pl/airline_enum.pl         many worlds in one SWI process, with signatures

data/catala_gold/airline/
  clerk.toml                   Catala project (run `clerk start` once)
  AirlineWorld.catala_en       Layer 0: cabins, countries, the city gazetteer,
                               items, itineraries
  Airline.catala_en            the statute: carry-on, the four fee tables,
                               complimentary bags, weight and size

.port/airline/                  generated, in its entirety
  test_cases/<id>/             prolog.pl, catala.catala_en, meta.json
  build/                       the instrumented oracle, points, scratch
  reports/                     DISCREPANCIES.md, report.json, generation.json,
                               coverage_audit.json
```
