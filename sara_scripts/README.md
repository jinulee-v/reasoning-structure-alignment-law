# SARA → Catala port

Translating the [SARA benchmark](https://github.com/SgfdDttt/sara)
(Holzenberger, Blair-Stanek & Van Durme 2020) — 9 sections of the US Internal
Revenue Code, hand-formalized in Prolog, with 376 cases — into Catala.

The port is validated *against* the Prolog rather than derived from it: the
Catala is written from the statute text, and the Prolog serves as a differential
oracle. Acceptance is agreement on a representative of **every execution path**
SARA's Prolog can be driven down, not merely on its 376 cases — see
[Testing](#testing-every-execution-path-not-every-case), which is the whole of
the apparatus and is two scripts.

## Status

| step | state |
|---|---|
| 1. Reproduce the Prolog baseline | **done** — 376/376 |
| 2. Ground all cases to JSON | **done** — 376/376, 18,892 facts |
| 2b. Branch instrumentation | **done** — 3,195 goal positions over 227 clauses |
| 3. Layer-0 world model | **done** — world, injections, income, filing status |
| 3b. Case emitter + differential runner | **done** — end to end, per case |
| 4. Layer-1 statute sections | **done** — all nine sections |
| 5. Green on all cases | **done** — 374/374 live cases agree, 0 unported |
| 6. Green on every execution path | **in progress** — see below |

Last full run (2026-08-31): a suite of **2,508 test cases**, one per distinct
execution path, covering **2,620/3,195 = 82.0%** of the Prolog's goal positions
and **87.4%** of the 2,998 that can be reached at all. **2,503 agree, 5
disagree, collapsing to 3 distinct causes** — all three invisible to SARA's own
376 cases, all three written out with both systems' reasoning in
[../sara_port/reports/DISCREPANCIES.md](../sara_port/reports/DISCREPANCIES.md). Generation took 235 s and
the run 113 s.

### Sections

| section | Prolog | cases | state |
|---|--:|--:|---|
| §1 Tax imposed | 214 | 60 | **done** — four rate schedules, twenty brackets |
| §68 Limitation on itemized deductions | 111 | 14 | **done** |
| §7703 Marital status | 218 | 10 | **done** — (a) and (b), all cases agree |
| §63 Taxable income | 391 | 42 | **done** — (a)–(d), (f) |
| §152 Dependent defined | 387 | 40 | **done** — (a)–(d), all 40 cases agree |
| §2 Definitions | 458 | 32 | **done** — (a) and (b) |
| §151 Personal exemptions | 193 | 16 | **done** — (a)–(d) |
| §3306 Definitions | 835 | 58 live | **done** — (a), (b), (c) |
| §3301 Unemployment tax | 56 | 2 | **done** |
| `tax/3` (full stack) | — | 100 | **done** — §1 + §3301, to the dollar |

Both stacks are closed. The income-tax side runs §1 → §63 → §68 and §151 →
§152 → §7703, with §2 supplying the two filing statuses §1 needs; the
employment-tax side runs §3301 → §3306(a)/(b)/(c); and `tax/3` adds the two.

Every one of the 374 live cases agrees with the Prolog, including all 100
numeric `tax/3` cases, which are the only ones that compare a dollar figure
rather than a verdict.

### Cutting the §151 → §68 → §63 → §151 cycle

At **§68(b)**. The applicable amount is a pure function of filing status with
no route back into §63, so §151(d)(3) can call it directly and the dependency
order becomes §68 → §151 → §63. That is the same shape as the §7703(a) cut:
a genuinely acyclic entry point, not an arbitrary break.

### The second cycle, and how it is cut

§68(b) → §2(b) → §151 → §68(b) is a second cycle, running through four
statutes:

| | |
|---|---|
| §68(b)(1)(B) | "$275,000 in the case of a **head of household** (as defined in section 2(b))" |
| §2(b)(1)(B) | head of household if he maintains a home for a parent "**for whom the taxpayer is entitled to a deduction under section 151**" |
| §151(c) | "an exemption of **the exemption amount** for each dependent" |
| §151(d)(3)(A) | that exemption amount is reduced once income exceeds "**the applicable amount in effect under section 68(b)**" |

— and §68(b) is where we came in. To know whether you are a head of household
you must know your exemption amount; to know your exemption amount you must
know whether you are a head of household.

The loop is **not** inherent in the statute. §2(b)(1)(B) only asks whether the
taxpayer is *entitled* to a §151 deduction, not what it is worth, and SARA has
a predicate for exactly that — `s151_c_applies/3`, introduced with the comment
"allows to test whether a deduction under this section is allowable without
going into an inf loop (c) -> (d) -> (c)". §2(a)(1)(B) uses it
(`section2.pl:93`). §2(b)(1)(B) instead calls `s151_c/4`, which binds the
amount (`section2.pl:309`) — and the loop-free version is sitting commented out
on the next line. One call site, one line.

SWI-Prolog never actually walks the loop on this corpus. Probing
`s2_b_1_B_pos` directly, three different short-circuits stop it: §151(d)(2)
zeroes the exemption for someone who is themselves a dependent; §151(d)(5)
zeroes it outright for 2018–2025; and §2(b)(1)(A) is tried before (B) and never
touches §151(d). Catala has no such luck — it rejects the dependency cycle
statically, whether or not any input would traverse it.

The port follows the commented-out line, and it costs nothing: `Deduction` is
unbound at both of `s2_b_1_B`'s call sites, and `s151_d/3` is **total** — it
yields 0 under (d)(2) or (d)(5) and 2,000 otherwise, never failing (checked
over 20 taxpayer/year pairs across five cases, including entities absent from
the case). With the amount unbound, the §151(d) half can only succeed and binds
a value nobody reads. Dropping it is behaviour-preserving, not a deviation.

`Section2` therefore no longer depends on `Section151`, `SaraStatus` imports
`Section2`, and §2(a)/§2(b) **derive**, with the case's grant as an overriding
exception. A case that describes a head of household in prose and injects
nothing now gets the right rate schedule: in `s2_b_1_B_pos`, which grants only
`s151_c_applies/3`, `FilingStatus` returns `HeadOfHousehold` where it used to
return `Unmarried`.

Layer 0 also now carries `SaraKinship` — `is_child_of`, `is_sibling_of`,
`is_descendent_of` (unrolled to depth 3), and the step/in-law family — plus
`latest`/`earliest` over optional dates.

Run `python3 sara_scripts/run_test_cases.py` for the live number.

**Agreement alone is not coverage.** A scope can be written, typecheck, and
never be reached by any case — in which case a 100% agreement figure says
nothing about it. That is what the branch-coverage apparatus below is for, and
it was learned the hard way: the first time coverage was measured behind a
100% agreement figure, 24 of 35 scopes turned out never to be reached, and
wiring the dormant ones immediately surfaced six real disagreements.

The same discipline caught a second one. §152's cases are the first to grant a
conclusion for one year and then be *asked* about another, and that exposed an
off-by-one in `SaraWorld.injection_matches`: `List.sequence of 1, n` stops
below `n`, so the loop checking argument positions never reached the last one —
the taxable year, almost every time. Every injected conclusion had been
matching in every year. It had been latent since the first injection landed and
no case had happened to discriminate on it. The fix is a `+ 1`; the lesson is
that a helper shared by every Layer-1 section is worth a direct test rather
than only end-to-end agreement.

One scope remains unexercised, and it is honestly unreachable rather than
untested: `Section68.ApplicableAmountHolds` (`s68_b/3`) is only ever *injected*
by a case, never queried.

A renderer can opt into a conjunctive test by declaring `"multi": True`. That
is how §152(d)(2)(D) and (G) — window-constrained queries — §68(a)(1), which
binds the applicable amount and gross income before using them, and
§3306(c)(10)(A) are answered. All six conjunctive goals are now handled.

The last three sections took two more measurements that agreement alone would
not have caught.

**§63 was reading the wrong gross income.** `utils.pl` has both
`gross_income/3` and `gross_income_individual/3`; the first adds the spouse's
income when a joint return covers the whole year, and §63(a)/(b), §68,
§151(d)(3) and §152(d)(1)(B) all read through it. The port had been calling the
individual form everywhere, which no case noticed until the first joint filer
with a dollar figure to match. Scope coverage had been saying so all
along — `SaraIncome.GrossIncome` sat unexercised, and the reason it was
unexercised was that nothing called it.

**§2(b) was quantifying over two dependants at once.**
`s2_b(Taxp,Dependent,Taxy)` binds `Dependent` in (b)(1) and then puts *that
person* through (b)(3); reporting (b)(1) as a bare boolean let one person
satisfy (b)(1) while another tripped (b)(3). `tax_case_90` is exactly that
shape — a widower whose only household member is an unrelated friend — and it
was the single case in the corpus that could tell the difference.

### §3306's two internal cycles

§3306 is the only section that closes a cycle **inside itself**, and it does so
twice. Subsection (c) excludes agricultural labor unless (a)(2) is satisfied,
and (a)(2) asks (c) which days were worked; it excludes domestic service unless
(a)(3) is satisfied, and (a)(3) asks (b) for wages, which asks (c).

Both were cut by measurement rather than by judgement. `sara_port/` grew a
temporary instrumented copy of `section3306.pl` that counts each edge, run over
all 376 cases:

| edge | traversals | nested |
|---|--:|--:|
| (c)(1)(A)(ii) → (a)(2)(B) → (c) | 30, in 6 cases | **0** |
| (c)(2) → (a)(3) → (b) → (c) | **0** | 0 |

The first is real but exactly one level deep, and SARA's own source says why:
`s3306_c_1_A` opens with `nonvar(Caly)`, and the generator inside (a)(2)(B)
calls `s3306_c` with the calendar year unbound. `Section3306.catala_en`
therefore has two employment scopes — `EmploymentLower` for the inner level,
`Employment` for the outer — and threads the (a)(2)(B) verdicts in as a table.

The second is never entered at all: (c)(2) also demands the service be located
in a private home or a college club, and no live case has a service that is
both. (The two cases that would test it are the corpus's two inert files.) With
the year unbound `s3306_a_3` raises an instantiation error rather than failing,
so there is nothing to reproduce; the port keeps (c)(2)'s guard, which is the
stricter reading.

## Decisions

Settled with the project owner; each shapes the code, not just the docs.

- **Bug-compatible.** Where SARA's Prolog departs from the statute, the port
  reproduces the Prolog so the acceptance number stays clean. Every departure is
  recorded in [DEVIATIONS.md](DEVIATIONS.md).
- **Coverage is more than the verdict.** Originally: the same sets at each of
  the 43 `findall/3` sites. Superseded (2026-08-31) by the stronger and cheaper
  form below — the same verdict on a representative of every *execution path*,
  which is 3,195 branch points rather than 43 sites, and which subsumes the
  `findall` check because a set that differs takes a different path. The
  `findall`-tracing build was retired with it.
- **Cycles broken by explicit stratification** in Layer 0, not by mirroring
  SARA's vacuous-guard hack and not by an out-of-Catala fixpoint.
- **Money is Catala's `money` type**, not integers mirroring Prolog.

## Effective suite size: 374 live + 2 inert

`s3306_c_2_pos` and `s3306_c_2_neg` contain no executable test — a missing
period makes their last fact absorb the test directive as its body, so both pass
vacuously under any harness that watches for `Goal (directive) failed`. See
[DEVIATIONS.md](DEVIATIONS.md) D4. `generate_test_cases.py` names them in
`INERT` and excludes them from its self-check; report the number as
`374 live + 2 inert`, not `376`.

## Testing: every execution path, not every case

SARA's 376 cases were written to illustrate the statutes, not to exercise them:
they leave a quarter of the Prolog's goal positions untaken, and agreement on
the paths they do take says nothing about the rest. The acceptance criterion is
therefore not "the same verdict on 376 cases" but

> the same verdict on a representative of **every execution path** SARA's
> Prolog can be driven down.

A path is necessary but not sufficient. A case also has to *ask something
sharp*: see "The expected value comes from SARA" below, without which most
generated cases degrade into a `false` that proves almost nothing.

Two scripts, and one directory of test cases between them.

### 1. `sara_scripts/generate_test_cases.py` — build the suite

Writes `sara_port/test_cases/<id>/`, three files per case:

```
prolog.pl           the world as facts + the query, runnable on its own:
                        swipl -q -f prolog.pl -g main -t halt   ->  VERDICT true
catala.catala_en    the same world and the same query, as a standalone Catala
                    program against the port:
                        catala interpret catala.catala_en -s Run -I sara_catala \
                            --stdlib sara_catala/_build/libcatala --bin sara_catala/_build
meta.json           the world model, the query, where the case came from, and
                    the execution path it takes
```

Worlds come from four methods, and one rule decides which become test cases:
**a world is kept when it drives the statutes down a path no kept world has
taken.**

| method | scope | what it is for |
|---|---|---|
| `seed` | SARA's 376 cases | the only inputs with a known right answer, so also the harness's self-check |
| `exhaustive` | each predicate's *reachable* input signature (the call graph says which event predicates it can read — the median is 11 of 57), over a two-person two-event universe, asked every way round | a completed enumeration, which is a stronger claim than any number of samples |
| `arguments` | the 26 predicates that read no event facts at all — the §1 rate brackets, §63(c)(7), §151(d), §68(f) | there is no world to enumerate, so Prolog is asked to *generate* the relation — bind one argument from the boundary domain (every numeric literal in the statutes and its two neighbours), leave the rest free — and every solution plus its one-off neighbours is checked. So the port is not merely checked for agreeing on some tax figure; it is checked against the figure Prolog computes, at every bracket edge and on both sides of it |
| `mutation` | everything, especially §3306 and `tax/3` | reaches the sections whose signature is far too large to enumerate |

The path is measured, not guessed. `sara_port/build/prolog_covered/` is the
statutes with every body goal position rewritten as

```prolog
cov('section1.pl:68:0:c'), ( Taxinc =< 36900 *-> true ; cov('...:0:f'), fail )
```

so a position is fully covered only when the goal has been seen both
succeeding *and* failing — branch coverage, 3,195 points over 227 clauses. The
soft cut is what makes the rewrite transparent: `( G *-> true ; fail )` has
exactly `G`'s solutions in exactly `G`'s order, where `->` would have committed
to the first. The set of points a world reaches is its path, and two worlds
with the same path cannot distinguish the two systems.

Selection consults **Prolog alone**. Catala is not run until the second script,
which is what keeps the suite honest: it describes SARA's behaviour, not the
places the port happens to agree with it.

### 2. `sara_scripts/run_test_cases.py` — run them and report

Runs both programs for every case, compares the verdicts, and writes
`sara_port/reports/DISCREPANCIES.md` and `report.json`.

The report is **grouped, not enumerated**. A raw list is mostly repetition —
one defect in a shared helper shows up in every world that reaches it — so each
discrepancy is first shrunk by delta debugging (drop a fact, keep the drop if
the two systems still disagree) and then grouped by what is left: the predicate
asked, the direction, and the shape of the minimal world. One worked example is
written out per group, in full:

* **the input** — the minimal world as Prolog facts, and the query;
* **Prolog's reasoning** — which clause of which section was entered, what it
  tried, and which goal failed, reconstructed from the ordered branch-point
  trace and read back to the statute source;
* **Catala's reasoning** — which scope was entered, under which article of the
  statute, and what it concluded, from `catala interpret --trace`. Tracing runs
  the interpreter with `-W` so that the port's modules are re-read rather than
  linked; a linked module executes as one opaque step and its articles never
  appear.

### Reading the coverage number, and pushing it up

Two numbers get reported and only the first is a measurement:

* **`n/3195`** — the goal positions the suite reached. This is the number.
* **an upper bound** — the same count over a smaller denominator, excluding
  `f` points on deterministic builtins that no run has ever been seen to fail.

Nothing in the 3,195 is unreachable. Every one exists in the source and a good
enough input reaches it; what differs is how much is known. The audit therefore
splits the residual by *evidence*:

* **reachable** — the goal guarding this point has been observed failing at
  some other position, so nothing about the goal itself is in the way. This is
  a plain gap in the suite.
* **unproven** — an `f` point on a goal no run has ever seen fail. Probably it
  has none: `sum_list(L, Total)` with `Total` unbound succeeds or throws. But
  probably is not certainly, and the hypothesis has already been wrong here —
  `findall/3` and `sum_list/2` were on the "cannot fail" list until the suite
  caught them failing at four positions, which is what they do the moment the
  output argument is *bound*, as every numeric case binds it. So a functor
  observed failing anywhere is never counted as unfailable anywhere.

The report ends with the residual broken down by goal. Diagnosing the 427
reachable points the default run misses, by *why* each was missed:

| points | why |
|--:|---|
| 209 | in a predicate whose signature is too large to enumerate, so only mutation reaches it |
| 184 | in a clause with no query of its own — `s1_a_1`, `s3306_c_5_B`, `total_wages_employer` — entered only as a sub-goal of something else |
| 33 | in a predicate already enumerated exhaustively, so the gap is the *universe*, not the reach |
| 1 | in a predicate never targeted at all |

To close them:

| the gap | the lever |
|---|---|
| a predicate whose reachable input signature is larger than `--max-inputs`, so only mutation reaches it | raise `--max-inputs`. Worlds are addressed by index rather than materialised, so a 12-input predicate with 10 million worlds costs nothing to sample; but total enumeration work is predicates × `--cap`, so lower `--cap` as you raise it. Measured: `--max-inputs 12 --cap 8000` gives **83.8%** against 82.0%, for 6,621 test cases instead of 2,508 and 45 minutes instead of 4 |
| a predicate already enumerated exhaustively at the current signature | the universe, not the reach: two people, two events, four dates, four amounts. Widen the domains in `saralib.generate` |
| a clause with no query of its own — `s1_a_1`, `total_wages_employer`, `s3306_c_5_A` — reached only as a sub-goal | give it a Catala renderer so it can be asked directly. `--frontier-bias` breeds preferentially from worlds already inside a clause that still has uncovered points, but it is off by default: it measured *slower and no better*, because the worlds touching the most clauses are also the largest |
| a guard needing four conditions at once | past a certain depth mutation does not assemble four conditions. Build the world by hand; §1(a)(1)'s nonresident-alien bar was reached that way and no other |

### Do the two systems follow the same trail?

`run_test_cases.py --compare-trails` asks a stronger question than the verdict:
(it samples 150 cases by default — tracing needs whole-program mode, which
recompiles the port's module chain per case and costs 20–60 s where a plain
verdict costs 0.3 s)
did both systems consult the *same statute provisions*? Two systems can reach
the same answer through different provisions, and one of them is then right by
accident.

Neither side was built to answer, and both can. SARA names its predicates after
the statute — `s7703_a_1` is §7703(a)(1) — and the port's Catala carries
`law_headings` that spell the subdivision out, so a provision id is derivable
from each mechanically, with no hand-written correspondence table. (A
hand-written table is exactly the thing that gets edited until the comparison
passes.)

Two corrections are needed before subtracting anything, and both were found by
the numbers looking wrong:

* **align the vocabularies.** SARA's predicate names distinguish 185
  provisions; the port's headings distinguish 60. Compared at full depth, every
  case looks divergent because SARA has a predicate per §152(c)(2)(A) where the
  port has one scope under §152(c)(2). Each provision is reduced to the deepest
  prefix *both* vocabularies contain — 52 of them.
* **close under prefixes.** Consulting §152(c)(1) is consulting §152(c). Without
  this, one system annotating at the subsection and the other at the paragraph
  reads as a disagreement about the statute.

It is reported as a measurement, not a test, because one difference is
structural rather than a defect: a Catala scope computes *all* of its outputs,
so the port evaluates §7703(a)(2) even where (a)(1) already settled the question
and Prolog short-circuited. Set equality would fail on every such case and mean
nothing. On a 233-case sample the trails are identical on 41%, Prolog's set is
contained in the port's on 63%, and the mean overlap is 0.713.

The half worth reading is the other direction — **a provision SARA consults and
the port never opens is a rule the port may not be reading at all**, and that
one is invisible to verdict testing: `tax_case_74` agrees on the verdict while
the port never opens three of the provisions SARA used to reach it.

But a third correction is needed before that list means anything, and it is the
one that caught me out. **Only scope variables leave trace events.** A provision
the port implements as a top-level `declaration ... equals` — §151(d)(1)'s
`exemption_base equals $2,000`, §68(b)'s `applicable_amount depends on status`,
§152(c)(1)(A)'s `first_death` — is evaluated perfectly well and produces no
trace at all. Of the 60 provisions the port annotates, only 47 can ever appear.
Counting the other 13 as unread manufactures findings, and it manufactured the
four largest: §152(c)(1)(A) (38 cases), §7703(a)(1) (30), §68(b) (28),
§151(d)(1) (20) — none of them a defect. `catala_observable` now separates
them, which takes the containment gap from 60 cases in 141 to **41**.

What is left is a genuine lead list, headed by §151(b) (26 cases), §68 (8),
§152(a) (8), §7703(b)(1) (6). Each still needs reading against the statute
before it is called a deviation, because Prolog also backtracks *into*
provisions it then abandons, and consulting a rule is not the same as needing
it.

### The expected value comes from SARA

A mutant inherits its goal from the seed it was bred from. Mutate the world and
a bound output — `tax(alice,2018,259487)` — goes stale, so the case answers
`false`. That is a much weaker test than it looks: **two systems agreeing on
`false` agree only that each differs from that literal**, and they may differ
from it, and from each other, by any amount. Before this was fixed, 1,582 of
2,541 cases answered `false`, and 66 of them bound a value the world determines.

So the last pass of generation asks SARA for the value it actually derives and
binds *that*:

```
tax(alice,2015,81487)   ->  tax(alice,2015,186242)
s63_d_2(x,[1200],2017)  ->  s63_d_2(x,[2000],2017)
```

The case then answers `true` by construction, and a `true` verdict on a bound
output **is an exact value assertion on both sides** — the port has to compute
186,242, not merely something that isn't 81,487.

Which arguments are outputs is not declared anywhere; it is measured. Free an
argument and ask SARA:

| freeing it | means |
|---|---|
| yields values | an output the world determines — rebind to the first |
| **raises** | an input. An unbound year reaches `first_day_year/2`, which is `atom_string/2`, and that is an instantiation error rather than a failure (DEVIATIONS.md D12) |
| yields nothing | the predicate genuinely fails; there is no value to bind |

`saralib/pl/values_harness.pl` runs the probe, reusing the ordinary case
rendering so injections and `discontiguous` declarations keep their meaning.
Rebinding changes the execution path, so the verdict and the path signature are
re-measured afterwards and the new points join the coverage union. Skip the pass
with `--no-strengthen` to see the weaker suite it replaces.

### Running them

```bash
# toolchain, once (userspace, no root; ~1 h, nearly all of it OCaml 4.14.2)
bash sara_scripts/install_toolchain.sh
cd sara_catala && clerk start && clerk build && cd ..

python3 sara_scripts/generate_test_cases.py     # -> sara_port/test_cases/
python3 sara_scripts/run_test_cases.py          # -> sara_port/reports/

# useful variants
python3 sara_scripts/generate_test_cases.py --quick        # small suite, ~1 min
python3 sara_scripts/generate_test_cases.py --build        # rebuild build/ first
python3 sara_scripts/generate_test_cases.py --only s7703   # one section
python3 sara_scripts/run_test_cases.py --only s7703
python3 sara_scripts/run_test_cases.py --no-minimise       # faster, noisier
python3 sara_scripts/generate_test_cases.py --no-strengthen  # leave gold stale
python3 sara_scripts/generate_test_cases.py --mutants 40000  # push coverage
python3 sara_scripts/generate_test_cases.py --max-inputs 12 --cap 8000
python3 sara_scripts/run_test_cases.py --compare-trails      # same provisions?
python3 sara_scripts/run_test_cases.py --compare-trails --trail-sample 0  # all
```

`--mutants` is the main lever on coverage; everything else in the default run
is exhaustive already and does not improve with a larger budget.

Generation ends by re-running written cases *from disk* and checking each still
gives the verdict it was selected on. That pass exists because it caught a real
bug: a wrapped query in the header comment left its continuation line
uncommented, which swallowed the `ensure_loaded` with it, and six cases ran
against no statutes at all while still producing a verdict.

**`sara_port/` is generated in its entirety** — `rm -rf sara_port` is always
safe, and the next run rebuilds it from the pristine corpus in
`data/_raw/sara/` and from the port itself. Two things used to stop that being
true, and both are now rebuilt rather than stored:

* **the oracle's statutes.** The only edit anyone makes to SARA's Prolog is the
  SWI >= 8 integer-timestamp fix (D1); `saralib.coverage.COMPAT_PATCH` applies
  it from an exact before/after pair that refuses to run if upstream has
  changed, instead of a second hand-edited copy that could drift.
* **the interned key space.** Catala 1.2 has no string type, so the port's
  Layer-1 modules were compiled against integers named in
  `sara_catala/SaraPredicates.catala_en` — which means the module that *depends*
  on those keys is also enough to reconstruct them, and
  `saralib.catala.recover_symbols` does. Everything else in the table is
  allocated per rendered program and only has to be consistent within it.

## Layout

```
data/_raw/sara/                pristine upstream (tracked; never edit)
  statutes/{prolog,source}     Prolog gold + NL statute text
  cases/                       376 cases
  splits/{train,test}          256 / 120
  PROVENANCE.txt               source URL, sha256, fetch date

sara_scripts/                  the whole apparatus, and the two documents
  README.md                    this file
  DEVIATIONS.md                SARA's defects, the port's, and what is open
  generate_test_cases.py       build the suite            <- entry point
  run_test_cases.py            run it, report             <- entry point
  saralib/                     everything they share
    paths.py                   locations and toolchains
    grounding.py               SARA's cases -> world models
    value_types.py             the atom/string reading of every value
    prolog.py                  world -> Prolog; run it; collect coverage
    catala.py                  world -> Catala; run it
    catala_emit.py             the renderer, one per statute predicate
    coverage.py                instrument the statutes; point -> statute source
    generate.py                the four generation methods
    traces.py                  both systems' reasoning, rendered for a reader
    provisions.py              which statute provision each system consulted
    pl/                        cover_transform.pl, cov_runtime.pl, harness.pl,
                               signature.pl

sara_port/                     generated, in its entirety.  `rm -rf` it and
                               the next run rebuilds every part.
  test_cases/<id>/             prolog.pl, catala.catala_en, meta.json
  reports/                     DISCREPANCIES.md, report.json
  build/                       statutes (upstream + the D1 patch), the
                               instrumented copy, grounded cases, call graph,
                               value types, symbol table

sara_catala/
  clerk.toml                   Catala project (run `clerk start` once)
  SaraWorld.catala_en          Layer 0: types, injections, key spaces
  SaraIncome.catala_en         Layer 0: gross_income/3
  SaraStatus.catala_en         Layer 0: filing status (the cycle meeting point)
  SaraPredicates.catala_en     interned predicate keys (generated)
  SaraPattern.catala_en        the three Layer-1 encoding patterns
  SaraSmoke.catala_en          runtime proof on real case data
  SaraKinship.catala_en        Layer 0: kinship, step and in-law relations
  Section1.catala_en           §1, including `s1/4` as a value for tax/3
  Section2.catala_en           §2
  Section63.catala_en          §63
  Section68.catala_en          §68
  Section151.catala_en         §151
  Section152.catala_en         §152
  Section3306.catala_en        §3306 and §3301
  Section7703.catala_en        §7703
  SaraTax.catala_en            tax/3 — §1 plus §3301
```

## What the measurements forced

Layer 0's shape is not a design preference; each choice was forced by something
measured over all 376 grounded cases.

| finding | consequence |
|---|---|
| 154/376 cases (41%) inject statute conclusions; 213 injections over 30 predicates, 255 rows with don't-care args | every Layer-1 scope takes an `optional` injection input, overriding via a default-logic `exception` |
| role fan-out per event: `agent_` 2, `patient_` 2, `location_` 4, `amount_` 2, `start_` **101** | all roles are `list of`, never single values |
| `utils.pl` reads unbound vars as "no constraint" (`var`/`nonvar`, 25 uses) | absence is `optional`, never a sentinel date |
| Catala 1.2 has no string type; 1,154 distinct atoms but ~12 per case | identifiers interned to `integer` by the harness |
| statutes compare against exactly 22 string literals, 20 semantic | closed enumerations (`Purpose`, `Place`, `Medium`). `Medium` and `type_/2` also have to carry an *entity*, because §3306(b)(2) reads a plan out of `means_/2` and §3306(b)(7) compares two `type_` values |
| `s3306_c_7` uses `atom_prefix(E,"state of ")`, `s3306_c_11` a `' government'` suffix, `s3306_c_6` an equality | three precomputed tags on `Entity`; Catala cannot take a substring |
| `s3306_a_1_A_pos` injects `s3306_b(3200,_,bob_works,...)` — the remuneration **unbound** | `start_(Remuneration,Time)` then generates over every start date in the world, and the wage is counted once per date. `starts_for` reproduces that; treating the row's remuneration as one event halves the total |
| SARA's week key is `format_time`'s `%W` with no year attached | week 5 of one year and week 5 of the next collide in `list_to_set`; the port collides them too |
| the sums in §3301 are `sum_list` over `findall`, which counts **solutions** | every generator in §3306 is a list whose length is the Prolog's solution count, replicated by an explicit multiplier where a goal can match several facts |
| longest ancestor chain across all cases is **2** | `is_descendent_of` unrolls to depth 3, provably covering the suite |
| 63 cases have zero event facts | pure statute arithmetic; driven entirely by injections |
| §151→§68→§63→§151 and §152⇄§7703 are real cycles; Catala rejects cyclic definitions | explicit stratification at documented cycle-entry points |
| §7703(a) reads only events — no §152 dependency | the §152⇄§7703 cycle is cut there: §7703(a) → §152 → §7703(b) → §7703, four levels, documented in `Section7703.catala_en` |
| §7703(b)(3) scans 184 days for household membership | equivalent closed form: the residence interval meets [2 Jul, 1 Jan]. Same predicate, no duration arithmetic |
| 6 of the 376 test goals are conjunctions whose conjuncts share variables (`s68_a_1_pos` binds `Applicable_amount` in one and uses it in the next) | the emitter refuses to dispatch on the first goal alone; multi-goal cases stay `unported` until handled explicitly |

## Toolchain notes

No root on this machine, and no system gmp/ninja, so everything is userspace
under `.toolchain/` (gitignored):

- **SWI-Prolog 10.0.0** via micromamba. SARA pins 7.2.3 (2015); the only
  incompatibility is D1 in [DEVIATIONS.md](DEVIATIONS.md).
- **Catala 1.2.1** via opam on conda-forge OCaml 4.14.2. `saralib.paths.catala_env`
  is the environment the scripts run it in; to use `catala` by hand, set
  `OPAMROOT=.toolchain/opam` and put `.toolchain/opam/catala/bin` and
  `.toolchain/envs/catala/bin` on `PATH`.
- **Moving this tree.** Everything here is root-relative --- `paths.ROOT` is
  `saralib/`'s grandparent, `install_toolchain.sh` derives its own --- with one
  exception: **opam switches are not relocatable.** `catala` and `clerk` are
  native binaries with the switch prefix compiled in, so a moved switch keeps
  asking for its libraries where it was built (*"Required OCaml library not
  found at .../lib/ocaml/zarith"*), and no amount of rewriting the text configs
  under `.toolchain/` reaches that. Two ways out, and the tree has used both:
  rerun `install_toolchain.sh`, which rebuilds the switch in place and is the
  clean answer; or set `OCAMLLIB`, `OCAMLPATH` and `CAML_LD_LIBRARY_PATH` from
  the new root, which `catala_env` does unconditionally and which makes a move
  work without the hour.
- **Catala 1.2.1 has no proof backend at all.** This was checked rather than
  assumed: `opam install z3` succeeds (z3 4.16.0 builds from source once a C++
  compiler is on PATH — conda's env shadows the system one, so `gxx` has to be
  installed into it), Catala rebuilds against it, and there is still no `proof`
  subcommand. The installed plugins are `explain`, `lazy_interpreter` and
  `python` only. The `Verification.Z3backend` module documented for Catala 0.8
  is not shipped in 1.2.x, so the Z3-based equivalence work would need Catala
  pinned to 0.8, or its own encoding built on `catala dcalc` output. Nothing in
  this port depends on it: the differential runner uses `interpret`, so
  `install_toolchain.sh` no longer installs z3 and the switch no longer carries
  it.

## Next

The port itself is complete: all nine sections, all live cases, and a suite
that takes a representative of every execution path the generators found.
What is left:

1. **The residual branch points.** The largest bucket, 184 of them, is clauses
   with no query of their own — `s1_a_1`, `s3306_c_5_B`, `total_wages_employer`
   — which can only be entered as a sub-goal, so no test case can aim at them.
   Giving the most-missed of them a Catala renderer would make them directly
   askable and is the single highest-value change available.
2. **Directed generation.** The frontier bias breeds from worlds already inside
   a clause with uncovered points, which helps, but nothing yet aims at a
   *named* point. Reaching §1(a)(1)'s nonresident-alien bar needs a joint return
   spanning the year, a §7703 marriage, §63 taxable income *and* an event of a
   particular name, all at once; mutation does not assemble four conditions and
   a solver or a hand-built world is what closes it.
3. **The trail comparison as an acceptance test.** `--compare-trails` measures
   it today. Turning the measurement into a criterion needs the structural
   differences classified first — eager scope evaluation, the two cut cycles —
   so that what remains is signal. The `Prolog consults it, the port does not`
   direction is the half already worth reading.
4. **The one unexercised scope.** `Section68.ApplicableAmountHolds` is
   unreachable because `s68_b/3` is only ever injected by a case, never queried.
   Either find a case that queries it or delete it; an unexercised scope is an
   unverified one — and §68(b) heading the trail comparison's Prolog-only list
   is the same fact, arrived at independently.
5. **Use it.** The port is the ground-truth set it was built to be: nine
   sections of the IRC, formalized twice.
