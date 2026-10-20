# Deviations in SARA, and the port defects found chasing them

The port is **bug-compatible**: where SARA's Prolog departs from the statute it
encodes, the Catala port reproduces the Prolog. That is what keeps `376/376` a
clean acceptance number, and it is why this file exists.

Three kinds of entry, with different lifetimes:

- **Part I — deviations in SARA.** Permanent properties of the gold. These never
  "resolve": reproducing them *is* the contract. A reader of the port needs them
  to understand why a scope is written the way it is.
- **Part II — port and harness defects.** Bugs in this port, found by
  differential testing and fixed. Each is kept for one reason: **its minimal
  reproducer is the only copy in existence.** Nothing executable encodes them, so
  each entry is a regression test written in prose. The narrative around them has
  been dropped; the reproducer and the named fix have not.
- **Part III — latent.** Port narrowings nothing has yet reached. Not open
  questions: each is classified and has a stated reason it is unfixed.

**Numbers are stable ids.** D1–D73 keep the numbers they were found under; D1,
D4 and D6 are cited by number from the Catala sources. Nothing is renumbered or
reused, so a gap would mean a withdrawn entry — there are none.

**On the apparatus.** Entries written before 2026-08-31 named "the fuzzer",
"Tier 1/2/3", a `COVERAGE.md`, and per-campaign finding counts. All of it was
replaced by `generate_test_cases.py` and `run_test_cases.py`; the old tools,
archives and `COVERAGE.md` were deleted, and the methodology is in
[README.md](README.md). Those names are gone from this file, and the pending-work
lists `COVERAGE.md` used to hold are inlined into Part III instead.

Upstream is never edited. Two copies of the statutes are built from it:

| path | contents |
|---|---|
| `data/prolog/sara/statutes` | pristine upstream, byte-identical to `sara.tar.gz` |
| `.port/sara/build/statutes` | + D1, the only edit, applied by `saralib.coverage` |
| `.port/sara/build/prolog_covered` | + a branch point at every goal position, generated |

## Index

| group | entries |
|---|---|
| **I. SARA deviations** — live, reproduced deliberately | D1–D14, D16, D17, D38 |
| **II.1** unbound arguments make a goal a test of the world | D18, D23, D24, D33, D34, D50, D55, D70, D75 |
| **II.2** a shared variable has to stay shared | D19, D26, D35, D36, D44, D52, D63, D71, D80 |
| **II.3** an injection without `discontiguous` *replaces* | D22, D30, D45, D46, D48, D51, D57, D58, D62, D65, D66, D67, D69, D73, D78 |
| **II.4** a failing call is not a zero | D20, D39, D47, D49 |
| **II.5** `findall` counts solutions, not members | D40, D56, D72 |
| **II.6** dates and windows | D31, D37, D42, D53, D74 |
| **II.7** a grant is also a source of candidates | D21, D25, D28, D32, D60, D79 |
| **II.8** distinctness, symmetry, and kind | D41, D61, D68 |
| **II.9** §151/§152 wiring | D27, D43, D54, D59 |
| **II.10** harness, not port | D15, D29, D46, D64 |
| **II.11** known and **unfixed** | D76, D77 |
| **II.12** several clauses hold at once | D81 |
| **III. Latent** | narrowings no case has reached |

D39, D47 and D49 belong to both II.3 and II.4 — they are where the override
mechanism and the failure-is-not-zero mistake meet, and that is the point of
them. D46 is listed under both II.3 and II.10.

---

# Part I — Deviations in SARA

These are properties of the gold. The port reproduces each deliberately.

## D1 — `day_to_stamp/2` returns a float, breaking `rdiv/2` on SWI ≥ 8

**The one edit made to upstream.** Required to run at all.

`utils.pl` computes timestamps with `date_time_stamp/2`, which yields a float.
Seven sites then apply `rdiv/2` to a duration derived from it (`section2.pl:249`,
`section152.pl:134`, `section7703.pl:137`, …). SARA pins SWI-Prolog 7.2.3 (2015);
on SWI ≥ 8 `rdiv/2` rejects floats:

    ERROR: rdiv/2: Type error: `rational' expected, found `31449600.0' (a float)

**Patch** (`saralib.coverage.COMPAT_PATCH`, an exact before/after pair that
refuses to apply if upstream has changed): bind the stamp through `integer/1`.
Timestamps are taken at UTC offset 0 with all time fields zero, so the float is
always integral and the conversion is value-preserving.

**Evidence:** with the patch, the generator's self-check reports 374/374 (376
less D4's two inert cases). Without it, every case reaching an `rdiv` site errors.

## D2 — `s151_b_applies/2` is unconditionally true

`section151.pl:69` carries the clause and the authors' own comment: it is a
cycle-breaking device against (b) → (d) → (b).

```prolog
s151_b_applies(_,_).      % "allows to test whether a deduction ... is allowable
                          %  without going into an infinite loop"
```

So the guard in `s151_b(Taxp,Ea,Taxy) :- s151_b_applies(Taxp,Taxy), s151_d(...)`
is vacuous: the taxpayer's *own* personal exemption is never tested for
eligibility. The arity-3 clause — the **spouse** guard — is real and does test
the §7703 / §152 / gross-income conditions.

    s151_b_applies/2(nobody,1999)         = TRUE (vacuous)
    s151_b_applies/3(nobody,noone,1999)   = false (guard is real at arity 3)

**Port:** Layer 1 defines the taxpayer guard as constantly true. Under a future
`--strict-statute` variant this is the first thing to restore. See D22 and D49
for what happens when a case *replaces* this clause.

## D3 — two cuts in `s151_d_3_A/7`

`section151.pl:149-157` cuts after the two subgoals binding AGI and the §68(b)
applicable amount, committing to the first solution of `gross_income/3` and
`s68_b/3`. Both are nondeterministic in general. It is the only non-declarative
control in the statute files — `!` appears nowhere else.

**Port:** Catala is deterministic, so the natural encoding already matches the
cut behaviour. Recorded because the port is faithful to the *cut* semantics, not
to the uncut relational reading.

## D4 — `s3306_c_2_pos` and `s3306_c_2_neg` contain no executable test

**Effective suite size is 374, not 376.**

Both files end their `% Facts` section with a clause missing its period:

```prolog
s3306_b(3200,alice_pays,alice_employer,alice,bob,alice,bob,_)     % <- no '.'

% Test
:- \+ s3306_c_2(alice_employer,_,2017).
```

Prolog reads the two together as one clause, so the intended fact absorbs the
test directive as its body:

    RULE: s3306_b(3200,...) :- \+ s3306_c_2(alice_employer,_,2017)

Two consequences: there is **no directive left to run**, so a harness deciding
pass/fail by looking for `Goal (directive) failed` records a vacuous pass; and
the injected `s3306_b/8` conclusion is conditional rather than a fact, so the
world model is also not what was intended.

**Port:** both are marked `inert` and excluded from the acceptance count, which
is reported as `374 live + 2 inert`. Repaired copies (period restored) are kept
alongside so §3306(c)(2) is still exercised, reported separately.

## D5 — `tax_case_25` encodes Bob's parents under a misspelled predicate

`events.pl` declares both `patient_/2` and `patient/2`. No statute file ever
reads `patient/2`, so facts asserted under it are dead. Exactly one case does so
(`tax_case_25.pl:11-12`, `patient(bob_birth,charlie)` for `patient_`), while the
same file uses `patient_/2` correctly at lines 28, 33 and 38.

**Evidence:** repairing the typo leaves the verdict unchanged —
`tax(alice,2018,259487)` holds either way. Alice's liability does not depend on
Bob's parentage here.

**Port:** reproduced as-is. Recorded because the case's formal encoding and its
NL text ("Bob is Charlie and Dorothy's son") disagree, which matters for any work
treating the NL text as the source of truth.

## D6 — §63(f)(2) counts a blind spouse as 600 entitlements

§63(f) sums aged and blind entitlements and multiplies by the per-entitlement
amount, so each count is meant to be 0 or 1. The aged clause does that; the blind
clause substitutes the dollar figure (`section63.pl:356-358`):

```prolog
(s63_f_2_B(Taxp,_,Taxy) -> Count2 is 600; Count2 is 0),   % siblings all use 1
```

A taxpayer with a blind spouse accrues 600 entitlements rather than one, making
the additional standard deduction 600 × $600 = $360,000 instead of $600.

**Port:** reproduced, constant carried across, comment pointing here
(`Section63.catala_en:171`). Second thing a `--strict-statute` variant should
correct, after D2.

## D7 — §152(b)(1)'s eligibility check never runs

`section152.pl:2-7`, `section152.pl:38`. §152 calls §152(b)(1), which is §152
again, so the rule is directly recursive:

```prolog
s152(Dependent,Taxp,Taxy) :-
    \+ ( var(Dependent), var(Taxp) ),
    Dependent\==Taxp,
    \+ s152_b_1(Taxp,_,Taxy),      % "is the taxpayer themselves a dependent?"
    s152_a(Dependent,Taxp,Taxy,_,_), ...
```

It terminates only because of argument order: the negated call is reached before
`s152_a` has bound `Taxp`, so on the recursive descent both arguments are unbound
and the first guard fails. §152(b)(1) therefore fails, its negation succeeds, and
the taxpayer's own eligibility is never tested.

**Evidence:** `s152_b_1_pos` grants `s152_c_1(bob,alice,2015)` and
`s152_c_1(charlie,bob,2015)`. Bob is Alice's dependent, so under the statute Bob
should have no dependents and `s152(charlie,bob,2015)` should fail. The Prolog
accepts it. The gold label only asks about Bob, so the corpus never exposes it.

**§152 is really two predicates wearing one name** — with the taxpayer bound the
guard applies, with it unbound the guard is skipped. D23, D24 and D33 all turn on
this.

**Port:** reproduced. `Section152.Ineligible` does not consult §152(b)(1) for the
candidate taxpayer, which is also what makes the port expressible — Catala
rejects the cycle the faithful reading would need.

## D8 — `s2_a_2_B`'s nonresident-alien test fires on *anybody*

`section2.pl:116-143`. Both corpus cases ask it as `s2_a_2_B(bob,_,2014)` with
the spouse unbound, so inside the negation `agent_(Someone_is_nra,Spouse)`
unifies with *any* agent of *any* NRA event. The paragraph asks "was anyone at
all a nonresident alien?" rather than "was the taxpayer or their spouse one?".

Right answer for the wrong reason here: `s2_a_2_B_neg`'s only NRA event is
Alice, who *is* Bob's late spouse. An unrelated nonresident alien would come out
wrong. **Port:** reproduced; `Section2.JointReturnPossible` reads an absent
spouse as "every agent matches".

## D9 — `s68_b/3` injected with its arguments transposed

`s151_d_3_B_pos` and `s151_d_3_B_neg` write `s68_b(alice,2015,250000)` where the
statute is `s68_b(Taxp,Aa,Taxy)` — the year in the amount's place. `s151_d_3_A`
calls `s68_b(Taxp,Aa,2015)`, which does not unify, so the grant is dead and the
figure comes from §68(b)'s own table. It happens to be $250,000 for an unmarried
taxpayer, so both cases still pass.

**Port:** reproduced without special-casing; the fixed-shape lookup constrains
argument 1 to `Taxp` and argument 3 to `num_key(Taxy)`. The transposed row fails
that lookup for the same reason and falls through to `Section68.applicable_amount`.

## D10 — two more inert injections

- `s151_d_2_neg` declares `s151_d/4` and asserts `s151_d(alice,bob,_,2015)`. The
  statute defines `s151_d/3`; there is no `s151_d/4`, so the clause is never
  called. The case passes anyway.
- `s2_b_1_A_ii`'s second conjunct is
  `s151_b_applies(Taxp,Dep,Taxy) ; s151_c_applies(Taxp,Dep,Taxy)`, and
  `s151_c_applies/3` is *defined* as `s152(Dep,Taxp,Taxy)` — the conjunct
  immediately before it. The disjunction can never fail, so those grants change
  nothing. (D33 revises this: it can fail, in the *bound* mode.)

Recorded so a reader does not wonder why the corresponding Catala is unreachable.

## D11 / D38 — §68(b)(1)(A) asks whether *anyone* is a surviving spouse

`section68.pl:22-35`. `s68_b` passes `_` for the third argument, so
`Surviving_spouse` reaches `s2_a/3` unbound and the disjunct reads "is *anybody*
a surviving spouse this year", not "is the taxpayer one". Same family as D8.

    s2_a(alice,_,2016).
    ?- s68_b_1_A(carol,_,_,_,2016).                           % true, port false

Every `s2_a/3` grant in the corpus names the case's own taxpayer, so SARA's own
cases never exercise the difference.

**History:** D11 recorded this and left the port deliberately *narrower*, arguing
that reproducing it would mean threading an "anyone at all" query through a scope
with no reason to take the world. That was true of `SaraStatus.FilingStatus` and
false of `Section68.SubparagraphHolds`, where the query actually lives. D38
reproduced it: (A) now also holds when some other person is a surviving spouse.
(B), (C) and (D) are untouched — SARA's unbound argument is in (A) alone.

`s68_b/3` inherits the quirk through its own disjunction but renders through
`ApplicableAmountHolds`, which takes no world; extending it would be a signature
change and no finding has reached it. Listed in Part III.

## D12 — §3306(b)(2) and (b)(10) call `s152/3` with the taxable year unbound

`section3306.pl:311` and `:365`. `s152/3` reaches `first_day_year/2`, which is
`atom_string(Year,Year_s)` — with `Year` unbound that is an instantiation error,
not a failure. So (b)(2)'s §152 alternative **throws** whenever reached.

**Evidence:** on `s3306_b_pos`, `s152(bob,alice,_)` gives
`error(instantiation_error, context(system:atom_string/2, _))`; the enclosing
`s3306_b_2/6` returns `no` because earlier conjuncts fail first. No live case
reaches it.

(b)(10) is different: its `Employee` is bound to the caller's `Payee`, so
`Employee==Payee` is *always true* and the §152 branch is dead code regardless.

**Port:** (b)(2)'s §152 alternative is `false`; (b)(10)'s is written out in full
since it is well-moded there. Both unreachable on this corpus.

## D13 — the `%W` week number depends on the machine's timezone

§3306(a)(1)(B) and (a)(2)(B) want ten days "each being in a different calendar
week". `day_to_stamp/2` builds the stamp from the day **plus one** at UTC
midnight; `format_time/3` then renders it in *local* time. West of UTC the two
shifts cancel; east of UTC they do not, and every date lands a day late.

**Evidence:** probed on this machine (TZ = CDT, UTC−5) over twelve dates spanning
leap years and both year boundaries. `2016-12-31` → week 52, `2018-12-31` → week
53, `2017-01-01` → week 00.

**Port:** `Section3306.week_of` computes `%W` of the day itself and matches all
twelve probes. The gold was produced west of UTC; **a machine east of UTC would
produce a different Prolog baseline**, and the port would then be the correct one.

Note the week key carries **no year**: week 5 of one year and week 5 of the next
collide inside `list_to_set/2`, and the ten-week test spans two calendar years.
The port collides them too.

## D14 — `s3306_c_1_A_i`'s third and fourth arguments are `findall` lists

`Employee` and `Service` are unified with *lists*, so a case naming a bare atom
there can never succeed. The corpus contains both forms: `s3306_c_1_A_i_pos` asks
for `[bob]` and holds; `s3306_c_1_A_i_neg` asks for `bob` and fails for this
reason alone, not because the wages test failed.

**Port:** reproduced — compares against the reported list where the case gives
one, renders `false` where the case gives an atom.

## D16 — two provisions let a variable bind to the individual it is contrasted with

§7703(a)(1) guards its spouse with `Taxp\==Spouse`. §2(b)(2)(B) does not, so on a
marriage naming a single agent the taxpayer is their own nonresident-alien spouse:

    marriage_(v1). agent_(v1,p2). nonresident_alien_(v2). agent_(v2,p2).
    ?- s2_b_2_B(p2,_,2015).                                   % true

§152(c)(1)(B) is the same shape one level down: `Residence_individual` and
`Residence_taxpayer` are separate variables over the same fact base, so one
residence event can satisfy both halves of the shared-abode test.

**Port:** `Section2.SpouseNonresidentAlien` carried an `sp.id != taxpayer.id`
guard SARA does not have; removed. See D41 for §2(b)(2)(C), the loose end.

## D17 — §7703(a)(1) fails outright on an undated death

In the branch where the marriage has no end date, `->` commits once a death event
is found, so the clause must then produce a date for it. A death carrying no date
does not fall through to `true`: `start_/2` fails and the whole of (a)(1) fails —
the taxpayer is not married, rather than married with an unknown end.

    death_(v1). agent_(v1,p2).
    marriage_(v2). agent_(v2,p1). agent_(v2,p2).
    ?- s7703_a_1(p1,_,_,_,2015).                              % false

**Port:** had collected the death *dates* and asked whether that list was empty,
which answers a different question. `Section7703.MarriageStatus` now tests the
first death *event*, matching the commit.

---

# Part II — Port and harness defects

Each entry: what was wrong, the minimal reproducer, and the fix. All are
resolved except D76, which is marked; the named scopes and fields were verified
present in `data/catala_gold/sara/`, and the suite runs 2541/2541 agreeing.

## II.1 — an unbound argument makes a goal a test of the world

SARA calls many predicates with arguments the caller leaves free. Prolog then
either re-binds on backtracking or leaves the variable free, and the goal asks a
question about the *world* rather than about a person. The port had approximated
each as a test of a particular individual. D7 is the root: §152 is two predicates
wearing one name.

**D18 — §152(b)(1)'s "other taxpayer" was drawn from too small a universe.**
`s152_b_1(Taxp,Otaxp,Taxy)` leaves `Otaxp` free, so Prolog searches every person
the fact base names. `Section152.Ineligible` enumerated
`child_of ++ sibling_of ++ stepsibling_of` — the right set for §152(c)(2), the
wrong one for §152(d)(2), which reaches in both directions: (C) makes a person the
dependent of their own *descendant*, and (D) and (G) route through `stepparent_of`
and the in-law relations.

    agent_(e,charlie). patient_(e,bob). son_(e).
    ?- s152_b_1(bob,_,2019).                                  % true, via (d)(2)(C)
    ?- s2_b_1_A_ii(_,charlie,2019).                           % false

Because the guard is negated the error inverted — the port said *true* where SARA
says false. `Ineligible` now takes `DependantsOf`'s universe: everyone the event
base names in a role. `AnyQualifyingChildTaxpayer` keeps the three-relation list;
it stands for §152(c)(2) only.

**D23 — §2(b)(1)(A)(ii) ran the wrong §152 mode, over the wrong candidates.**
Two halves, both specific to the taxpayer-unbound mode every corpus case uses.
The port called `IsDependent`, which always applies D7's guard, and so denied a
taxpayer SARA allows; and its candidate set was D18's mistake one level up.

    agent_(e,charlie). brother_(e). patient_(e,bob).
    s151_c_applies(bob,charlie,2019).        % discontiguous declared
    ?- s2_b_1_A_ii(_,charlie,2019).                           % true, port false

`IsDependent` now exposes both readings — `holds` with the guard,
`holds_any_taxpayer` without — and the clause picks by whether the goal bound the
taxpayer. Candidates now come from `DependantsOf`.

**D24 — §152(d)(2)(H) is a checker, not a generator.** A consequence of D18:
widening the universe let the port reach (H) in a mode SARA never reaches it in.
(H) is the one subparagraph that is not a kinship relation, so it has no relation
to enumerate a taxpayer from. Two ordering artifacts stack — the disequality
`Dependent \== Taxp` is spent while `Taxp` is still fresh, and the spouse
parenthetical then *binds* `Taxp` from the agents of a marriage the dependant is in.

    s152_d_2_H(bob,charlie,2016,_,_,_)   -> true          (taxpayer bound)
    s152_d_2_H(bob,Otaxp,2016,_,_,_)     -> no solutions
    s152_a(bob,charlie,2016,_,_)         -> true
    s152_a(bob,Otaxp,2016,_,_)           -> no solutions

`MemberOfHousehold` now takes `taxpayer_generated`, threaded through
`QualifyingRelative`, `Dependent` and `IsDependent`. In the generated mode the
exclusion drops its `ev.agents contains taxpayer` conjunct.

**D33 — "the conjunct just proved" was a different question.**
`s2_b_1_A_ii` proves `s152(Dependent,Taxp,Taxy)` and then
`s151_c_applies(Taxp,Dependent,Taxy)`, which expands to the same goal — so the
port wrote it `true` and said so in a comment. It can fail: the first call runs
in the taxpayer-unbound mode where D7's guard is skipped; by the second, `Taxp`
is bound and the guard applies.

    son_(e). agent_(e,charlie). patient_(e,bob).
    ?- s152(bob,T,2017).             % T = charlie
    ?- s152(bob,charlie,2017).       % false
    ?- s2_b_1_A_ii(_,bob,2017).      % false, port true

The second conjunct is now evaluated in the bound mode.

**D34 — `gross_income/3` with the person unbound sums the whole world.**
§2(b)(3)(B) reaches `s152_d_1_B(Dependent,Taxy)` several conjuncts before (H)
binds the dependant. An unbound `Person` is re-bound on every solution of the
`findall`, so the call collects *everyone's* amounts. In that mode §152(d)(1)(B)
is a statement about the world, and one person's income defeats it for everybody.

    income_(e). agent_(e,bob). amount_(e,300000). start_(e,"2018-01-01").
    s152_d_2_H(charlie,bob,2018,_,"2018-01-01","2018-12-31").
    ?- gross_income(charlie,2018,G).      % G = 0
    ?- gross_income(D,2018,G).            % G = 300000, D still unbound
    ?- s152_d_1_B(charlie,2018).          % true
    ?- s152_d_1_B(_,2018).                % false
    ?- s2_b_3_B(bob,_,2018).              % false, port true

`NoIncome` now takes `dependant_unbound` and compares `Inc.everyone_income`
against zero in that mode. The joint-return branch of `gross_income/3` keeps its
bound reading; see Part III.

**D50 — §152(d)(2)(H) with the *dependant* unbound excludes everybody.** Mirror
of D24. §2(b)(3)(B) reaches (H) with `Dependent` still fresh — (H) is where SARA
binds it — so the spouse parenthetical collapses into "does the taxpayer have
*any* marriage running into the taxable year", because the taxpayer is himself an
agent of it. One marriage makes (H) false for every candidate at once.

    marriage_(alice_and_bob). agent_(alice_and_bob,bob). start_(...,1992-02-03).
    residence_(charlie_and_bob_residence). agent_(...,bob). agent_(...,charlie).
    ?- s2_b_3_B(bob,_,2018).                                 % false, port true

`MemberOfHousehold` now takes `dependant_generated` beside D24's
`taxpayer_generated`. Both weaken the guard in the direction that makes (H)
*harder* to satisfy.

**D55 — enumerating a taxpayer's dependants runs (H) unbound too.** D50 reaching
the place it matters most: `s152(Dependent,Taxp,Taxy)` with the dependant unbound
is how §151(c) finds who to allow an exemption for.

    marriage_(alice_and_bob). start_(alice_and_bob,2017-02-03).
    residence_(alice_residence). agent_(...,alice). patient_(...,alice_and_bob_home).
    residence_(bob_residence).   agent_(...,alice_and_bob_home).
                                 patient_(...,alice_and_bob_home).
    ?- tax(alice,2017,4938).                                 % true, port $4,378

The port made `alice_and_bob_home` — the house — a (H) dependant of alice's and
gave her a third $2,000 exemption. `dependant_generated` is now threaded through
`IsDependent` → `Dependent` → `QualifyingRelative` → `MemberOfHousehold`, and
`DependantsOf` passes `true`.

What does *not* change: §152(d)(1)'s income test. Under §2(b)(3)(B) SARA calls
`s152_d_1_B` with the dependant unbound (D34), but `s152_d_1` calls `s152_d_1_A`
first, and that binds the dependant through the relationship — so inside §152 the
income test is a test of a person. The same predicate, read two ways, one line
apart in the call graph.

**D70 — a granted §7703 with the spouse left unbound.** `s151_b_applies` never
binds `Spouse` itself; `s7703(Taxp,Spouse,_,Taxy)` does. A case granting §7703
with that argument left as a variable leaves it one, so the three goals after it
read as world-wide tests.

    :- discontiguous s7703/4.
    s7703(alice,_,_,2016).                    % the whole world
    ?- s63_d_2(alice,[2000],2016).            % false, port true

§151(b) yields *two* exemptions — alice's own and one for a spouse nobody names.
`Individual.unnamed_spouse_exemption` reproduces that.

**D75 — a person can be their own dependant.** `s152_b_1(Taxp,Otaxp,Taxy)` is
only ever called with `Otaxp` unbound, so §152's own `Dependent\==Taxp` compares
a bound term with a fresh variable and succeeds. §152(d)(2)(H) then binds the
taxpayer — and it can bind it to the dependant themselves, since (H) needs only a
residence whose household is somebody else.

    residence_(v1). agent_(v1,p1). patient_(v1,p2). start_(v1,"2015-09-27").
    ?- s63_d_2(p1,[2000],2017).                              % false, port true

SARA derives `s152_d_2_H(p1,p1,2017,p2,2015-09-27,_)` — p1 is p1's own
household-member dependant — so §151(d)(2) zeroes p1's own exemption and the
list is `[0]`, not `[2000]`. The port excluded the person from their own
candidate taxpayers twice over, in `Ineligible.candidates` and again in
`Ineligible.holds`; both filters are gone. `MemberOfHousehold`'s guard now reads
`dependant_generated or taxpayer_generated or dependant.id != taxpayer.id`,
since **either** side being generated spends the disequality — D50 is the
dependant, this is the taxpayer.

## II.2 — a shared variable has to stay shared

One Prolog variable used in several goals. The port asked each goal independently
against the query's own (usually unbound) argument, weakening a conjunction into
"somebody satisfies each half".

**D19 — §152(b)(2) dropped the spouse and never checked the joint return named
them.** `Section152.MarriedDependent` asked "is the dependant married to anyone"
and then whether some joint return listed the dependant; both of the Prolog's
spouse conjuncts were missing.

    marriage_(m). agent_(m,alice). agent_(m,bob).
    joint_return_(j). agent_(j,alice).
    start_(j,"2015-01-01"). end_(j,"2015-12-31").
    ?- s152_b_2(alice,_,_,2015).                              % false

Worth noting for what it says about the harness: the corpus binds the spouse
argument about as often as it leaves it free, so the port had been answering a
*weaker question than it was asked* on the acceptance suite itself, and agreed
there anyway. The renderer now threads the argument through as an `optional`,
`Absent` being the unbound mode. `S21`, the joint return event, stays dropped —
the scope quantifies over it and no case binds it.

**D26 — a joint return signed by one spouse counted as joint.**
`SaraStatus.JointReturn.filed` quoted the Prolog in its docstring, including
`agent_(Joint_return,Spouse)`, and then tested only `agent_(Joint_return,Taxp)`.

    joint_return_(j). agent_(j,alice).
    start_(j,"2017-01-01"). end_(j,"2017-12-31").
    s7703(alice,spouse,_,2017).
    ?- s63_c_2_A_i(alice,_,2017).                             % false, port true

Needed a second change: `Spouse` is bound by the preceding `s7703`, and a case can
grant that marriage without the event base naming one, so `FilingStatus.spouse`
now takes the identity from the same grant. Without it a corpus case regressed.

**D35 — §152(c)(1)(E) forgot which joint return.** `NoJointReturn` took a
boolean — *is* the dependant married — which cannot express `agent_(J,Spouse)`.

    marriage_(m). agent_(m,bob). agent_(m,charlie).
    joint_return_(j). agent_(j,bob).
    start_(j,"2019-01-01"). end_(j,"2019-12-31").
    ?- s152_c_1_E(bob,_,2019).                                % true, port false

The scope now takes the §7703 spouses in full and requires one on the return; an
empty list is the unmarried case, where (E) holds outright.

**D36 — §3306(b)(15) let the employer and the employee stop co-referring.**
`s3306_c(_,Employer,Employee,_,_)` binds both and later goals reuse them.
`ExcludedSurvivorPayment` asked `EmploymentLower` whether *some* employment
exists, then separately whether some agent of the remuneration fit the query's
employer — unbound, so any agent at all.

    s3306_c(alice_employer,alice,bob,_,_).      % employer alice, employee bob
    death_(p). agent_(p,charlie). patient_(p,charlie).
    start_(p,"2020-01-20"). start_(p,"2019-11-25").
    marriage_(m). agent_(m,bob).
    ?- s3306_b_15(p,_,_,_,_).                                 % false, port true

The scope now iterates `EmploymentLower(...).solutions` and uses one row's pair
throughout.

**D44 — §152(c)(3) shares one birth event between its two halves.**
`Individual_is_born` and `Individual_dob` are the *same* variables in both halves
of the disjunction. Down the first they are already bound to a `birth_` event, so
the age test must accept that event's date; the `son_`/`daughter_` alternatives
are reachable only down the second. The port evaluated `younger` and `under_25`
as independent existentials.

    birth_(b1). agent_(b1,alice). start_(b1,"1992-01-10").
    birth_(b2). agent_(b2,bob).   start_(b2,"1992-12-31").
    son_(s).    agent_(s,bob).    start_(s,"2018-03-04").
    ?- s152_c_3(bob,alice,2019).                              % false, port true

bob is younger than alice, but his own birth puts him at 27 at the close of 2019,
and the `son_` event's 2018 date is not available to him.

Note the second disjunct's `\+`: `section152.pl:207` states
`agent_(Someone_is_born,Dependent)` **twice**, the second presumably meant to name
the taxpayer. Writing the taxpayer in — the reading the statute suggests — broke
`tax_case_36`, which is how the duplication came to light.

**D52 — §3306(b)(7) weighed one employment's business against another's service.**
Same shape as D36.

    service_(alice_employer). agent_(alice_employer,bob). patient_(...,bob).
    business_(alice_runs_a_factory_c25). agent_(...,alice).
    ?- s3306_b_7(alice_pays_bob,_,_,_,_,_).                  % false, port true

`s3306_c` binds `Employer` to bob — (c)(A) takes the employer from the service's
*patient* — and bob runs no business. `ExcludedNonCashOutsideBusiness` now
iterates `EmploymentLower(...).solutions` and reads `emp.employer`, `emp.service`.

**D63 — §3306(b)(15)'s payee is one person, not two.**
`patient_(Remuneration,Payee)` binds the payee and `agent_(Emar,Payee)` reuses
it: the benefit is excluded only where the person *paid* is the one the dead
employee was married to.

    agent_(alice_pays,alice). patient_(alice_pays,cash).
    death_(bob_dies). agent_(bob_dies,bob).
    marriage_(bob_and_charlie). agent_(bob_and_charlie,bob).
    ?- s3306_b_15(alice_pays,_,_,_,_).                       % false, port true

The payee here is `cash`. D36 bound the employer and employee from one `s3306_c`
row and left the payee free; this binds it once in the remuneration and reads it
back in the marriage.

**D71 — §63(c)(6)(A) took the first spouse, not each of them.**
`s7703(Taxp,Spouse,_,Taxy)` is a generator and every goal after it backtracks over
it. The port passed `MaritalStatusA.spouse` — `List.first_element`.

    marriage_(alice_and_bob). agent_(...,alice). agent_(...,bob_itemized_deduction).
    marriage_(alice_and_bob_c85). agent_(...,alice). agent_(...,bob).
    deduction_(bob_itemized_deduction). agent_(bob_itemized_deduction,bob).
    ?- s63_c_6_A(alice,_,_,2017).                            % true, port false

`NotEligible` now takes `spouses` and quantifies.

**D80 — §63(f)(1)(B) read "over 65" and "§151(b) allows it" off different
spouses.** One `Spouse` runs the length of the clause: the person who has
attained 65 is the person §151(b) allows the additional exemption for. The port
tested the birth date against `FilingStatus.spouse` and the §151(b) allowance
against *any* spouse, so a couple filing jointly collected a $600 entitlement
SARA does not grant them.

    marriage_(m). agent_(m,alice). agent_(m,bob). agent_(m,j).
    joint_return_(j). agent_(j,alice). agent_(j,bob).
    start_(j,"2019-01-01"). end_(j,"2019-12-31").
    birth_(b). agent_(b,alice). start_(b,"1950-03-02").
    ?- s63_c_3(bob,0,2019).                                  % true, port $600

`s151_b_applies(bob,alice,2019)` fails on the joint return, so alice — who *is*
over 65 — is not an exempt spouse. `agent_(m,j)`, the mutation's own quirk, makes
the joint return event a second §7703 "spouse" of bob, and it is not on any joint
return of its own, so §151(b) allows it and the port read the two halves off the
two different spouses. `AgedOrBlind` now takes `exempt_spouses` — a list — and
quantifies both halves over the same person; `AgedBlindClauseHolds` and
`AdditionalDeductionHolds` take it too, in place of `spouse` and
`spouse_exemption_allowed`.

## II.3 — an injection without `discontiguous` *replaces* the predicate

**D22 established the semantics by experiment**, and it is the single largest
family. A case injects a statute conclusion by asserting clauses in its own file,
loaded before the statutes. Whether that *adds* a clause or *replaces* the
predicate depends on one declaration:

```prolog
:- discontiguous s151_b_applies/2.    % present -> the row is appended
s151_b_applies(alice,2018).           % absent  -> SWI: "Redefined static
                                      %            procedure", statute gone
```

Every corpus case that injects a *statute* predicate declares it, so the port
treated injections as purely additive and agreed on all 374. The other half is
not a corner: it decides whether a derivation runs at all.

**The mechanism.** Each real injected conclusion carries a
`replaces_statute` flag.  Thus an override does not require a synthetic marker
row or a ghost argument, and a scope can ask
`W.pred_overridden of injections, P.pred_x` without another input.
`W.pred_available of injections, pred, matching_injections` is
"the derivation is still there, or a row answers this query". Consumers that must
distinguish "no value" from "the value zero" pair it with an `applies` output of
their own (see II.4).

**D22 — the first consumer.** `s151_b_applies/2` is D2's cycle-breaking clause,
true of everyone. A case injecting `s151_b_applies(alice,2018)` without the
declaration revokes D2 for every taxpayer but alice.

    s151_b_applies(alice,2018).
    ?- s63_d_2(carol,[2000],2017).                            % false, port true

**D30 — a replaced §152(d)(2)(H) still fell back on the event base.**
`MemberOfHousehold.windows` used injected windows when there were any and derived
ones otherwise — right for a grant that *added*, wrong for one that replaced.

    s152_d_2_H(charlie,bob,2019,_,"2019-01-01","2019-12-31").   % no discontiguous
    ?- s2_b_1_A(bob,_,_,2018).                                % false, port true

The grant names 2019 and the query asks 2018, so the injected set is empty and
the port fell back on residences while SARA has nothing to fall back on. The
exception now fires on the override as well as on a non-empty match.

**D45 — the gate, generalised.** The consumers, with the chain measured rather
than assumed:

    s63_c(venezuela," government",54267).      % replaces the clause
    ?- s63(bob,2012,TI).      % fails
    ?- s1(bob,2012,_,I).      % fails
    ?- tax(bob,2012,T).       % T = 0

- `Section63.TaxableIncome.applies` — §63 needs `s63/3`, and its
  standard-deduction branch needs `s63_c/3`, `s63_c_2/3`, `s63_c_3/3` (and
  `s63_c_1/3`, added by D58). Losing (c) kills (b) and, with nothing itemized,
  §63 with it.
- `SaraStatus.FilingStatus` — a replaced `s2_a/3` or `s2_b/3` leaves only its rows.
- `Section151.Individual.aa` — likewise for `s68_b/3`.

Not every replacement propagates: `s63_f_1_A/2` sits inside
`( ... -> Count1 is 1 ; Count1 is 0 )`, where failing changes a count rather than
availability. D57 revises what that implies.

**D48 — a replaced `s151_b_applies/3` supplies §151(b)'s spouses itself.**

    s151_b_applies(alice,2015,2015).
    ?- s151_a(alice,4000,2015).                              % true, port false

Two exemptions of $2,000: alice's own, and one for "2015" — that argument is a
*number*, and SARA does not care, since it is a Prolog term that `list_to_set`
keeps. `entity_of_key` gives `Absent` for a numeric key, the unnamed person
`Exemption` already carried. `Individual.spouse_entries` is now the derived list
when the guard stands, plus a row-derived entry either way.

**D51 — a replaced §7703 removes §152(b)(2)'s marriage.**

    s7703(alice_and_bob_joint_return,'-01-01',35,441).       % no `discontiguous`
    ?- s152_b_2(alice,_,_,2015).                             % false, port true

The row is nonsense, and that is the point: what matters is that it *replaced*
§7703. `MarriedDependent` now builds `candidate_spouses` the standard way.

**D57 — a replaced §63(f)(1)(A) revokes the birth-date derivation.**

    s63_f_1_A(4439,373181).                        % no `discontiguous`
    birth_(alice_is_born). start_(alice_is_born,1950-03-02).
    ?- tax(alice,2017,10018).                      % false, port true

This is the case D45 had set aside as *not* wanting the `applies` treatment, and
that reading holds up — failing here is an ordinary outcome, turned into a count
of zero, so there is nothing for an `applies` companion to carry. What it needs is
the plain gate, `pred_overridden` on the derivation alone. (f)(1)(B) takes the same.

**D58 — a replaced `s63_c_1/3` takes the standard deduction with it.** The one
predicate missing from D45's availability chain; it sits between `s63_c_2/3` and
`s63_c_3/3` and was not asked about.

    s63_c_1(bob_maintains_household_2018,2014,2014).   % no `discontiguous`
    ?- tax(bob,2015,4509).                             % false, port true

**D62 — the §151(d)(3) query surfaces needed the availability test too.** D45
gave `ExemptionAmount.phased_out` the test, but `PhaseoutHolds` — the surface the
`s151_d_3_A/7` and `s151_d_3_B/5` cases go through — asked neither.

    s68_b(alice,2015,250000).                % no `discontiguous`
    ?- s151_d_3_B(22,alice,_,2015,_).                        % false, port true

**D65 — §7703's own grant, and its replacement, belong in `MaritalStatus`.**
Three callers unioned the granted spouse in for themselves (D26, D32) and the
rest did not; none asked whether the grant had *replaced* §7703.

    s7703(alice_and_bob_joint_return,'-01-01',35,441).   % no `discontiguous`
    ?- s151_b(alice,bob,_,2015).                         % false, port true

`MaritalStatus` now reports `derived_spouses`, `granted_spouses`, and `spouses` as
the union — empty of the first under a replacement. The per-caller unioning in
`Section151.Individual` is gone with it, removing a double count. `living_apart`
is `s7703_b/3` and still reads `derived_spouses`: a grant of `s7703/4` says
nothing about whether (b) took a spouse back out.

**D66 — `s152_c/3` and `s152_c_1/3` are different predicates.**
`s152_c(Dep,Taxp,Taxy) :- s152_c_1(Dep,Taxp,Taxy)` is one clause, and replacing
it makes (c)(1) unreachable however that paragraph was itself granted.

    :- discontiguous s152_c_1/3.
    s152_c_1(bob,alice,2015).                  % added
    s152_c("domestic service",fz_21,2015).     % *replaced*
    ?- s152_a(bob,alice,2015,_,_).                           % false, port true

`QualifyingChild.holds_c` now requires `s152_c/3` to be available as well.

**D67 — a replaced `s151_c_applies/3` supplies §151(c)'s dependants itself.**
D48's twin.

    s151_c_applies(0,79,alice_income).         % no `discontiguous`
    ?- tax(alice,2017,2384).                                 % false, port true

`Individual.dependant_entries` is built the way `spouse_entries` is.

**D69 — §3306(b) and (c) replaced, not added to.** `Wages.rows` and
`Employment.solutions` were both derived ++ injected.

    s3306_b(2017,2014,17545,0,127,maryland,usa,spouse).   % no `discontiguous`
    ?- tax(alice,2017,21635).                             % false, port true

    s3306_c('make provisions...',fz_33,10644,'domestic service',358316).
    ?- tax(alice,2017,72344).                             % false, port true

`Wages` now reports `rows_available` and drops derived rows under a replacement;
`Employment` and `EmploymentLower` gate the same way. The eight cases that inject
`s3306_c/5` all declare it, so the additive reading still holds where the corpus
uses it.

**D73 — a replaced §3306(a) leaves nobody an employer.** `s3306_a/2` has three
clauses — (1) employment generally, (2) agricultural labor, (3) domestic service
— and an undeclared grant replaces all three.

    s3306_a(bob,alice_pays).                  % no `discontiguous`
    ?- tax(alice,2017,21635).                 % false, port true

With the paragraphs gone, alice is not an employer, `s3301/6` fails, and `tax/3`
takes its `\+ s3301(...)` branch. `Employer.holds` now requires the predicate not
to have been replaced, with the grant still an exception above it.

**D78 — a replaced `s151_c/4` leaves §151(c) no clause to reach dependants
through.** The port honoured a replaced `s151_c_applies/3` and read injected
`s151_c/4` rows, but not the third case: replacing `s151_c/4` itself removes the
clause `s151_individual/5`'s `findall` calls, so the derived dependants and any
`s151_c_applies/3` grant go with it.

    income_(inc). agent_(inc,alice). amount_(inc,9560). start_(inc,"2017-12-31").
    son_(k). agent_(k,charlie). patient_(k,alice).
    s151_c(house,2012,"club",199427).         % no `discontiguous`
    ?- s151_a(alice,2000,2017).               % true, port false ($4,000)

Charlie is alice's son and worth a second $2,000 exemption; the injected row
answers for nobody, and the replacement is why. `dependant_entries` is now empty
whenever `P.pred_s151_c_4` is overridden, leaving `set_c` the rows alone.

## II.4 — a failing call is not a zero

Money cannot express the difference between "no value" and "the value zero", and
in SARA a failing call propagates up the chain while a zero does not. Four
entries, three of them where this meets II.3.

**D20 — §68(a)(2) read a missing §63(d) as a deduction total of zero.** Minimal
reproducer is an *empty* world:

    ?- s68_a_2(alice,_,0,2016).                              % false

`section63.pl:292` guards §63(d) with `L>0`, so a taxpayer with no itemized
deduction makes §63(d) *fail*, and §68(a)(2) fails with it. The renderer read a
missing grant as `$0`, which satisfied `round(80 * 0 / 100) = 0` — and it ignored
deductions the event base does hold, consulting only the case's grant.
`ReductionTwoHolds` now takes the predicate separately as `itemizes`, which
carries the `L>0` guard exactly.

**D39 — a replaced §151 has to make §63 and §1 *fail*, not total zero.**
For a taxpayer no row names, `s151(Taxp,_,_,Ded,Taxy)` simply fails, §63 fails
with it, §1 with that, and `tax/3` falls into its own
`( s1(...) ; ( \+ s1(...), Income_tax is 0 ) )` branch. The port carried the grant
as an *exception* on `Personal.total` and left the derivation in place, so a
replaced §151 quietly went on computing exemptions for everybody it did not name.
`Personal` now carries `applies` beside `total`, `Section63.TaxableIncome` passes
it on, and `Section1.Tax.subsection` is `Absent` when it is false. The same gate
went on `ExemptionListHolds`.

**D47 — a replaced §68(b) makes the phaseout unreachable, not zero.** The
correction to a first attempt at D45, which had set the applicable amount to `$0`
when the predicate was overridden. That is worse than doing nothing: an
applicable amount of zero makes the phaseout apply to the whole of AGI, the
*opposite* of not applying. `Individual` now reports `aa_available` beside `aa`,
and `ExemptionAmount.phased_out` requires it.

**D49 — a replaced `s151_b/3` makes §151 fail, not total zero.**
`s151_individual/5` opens with `s151_b(Taxp,Ea,Taxy)`; every exemption list and
every total is downstream of that one call.

    s151_b(fz_33,alice_and_bob_divorce,2010).
    ?- tax(alice,2017,174).                                  % false, port true

D22 had fixed the sibling case by dropping the taxpayer's entry from `set_b`.
That got the right answer, because an empty list is not `[2000]` either, but it
modelled a failing call as an empty result. `Individual` now reports
`self_exemption_available` — D2's guard *and* the availability of `s151_b/3` —
and `Personal.applies` requires it of the taxpayer and of a joint-filing spouse
alike, since the joint branch calls `s151_individual` twice.

## II.5 — `findall` counts solutions, not members

SARA's money sums are `findall`s, and the number of solutions is the product of
the matches in *every* position of the goal. A fact stated twice contributes
twice; a goal that cannot be satisfied at all contributes nothing.

**D40 — a fact stated twice counts twice.** The port modelled the `amount_` and
`start_` factors but tested the role with `ev.patients contains person`, a boolean.

    payment_(p). amount_(p,113209). start_(p,"2018-12-31").
    patient_(p,alice). patient_(p,alice).            % stated twice
    ?- tax(alice,2018,28292).                        % false, port true

Whether a duplicated fact *should* count twice is a question about SARA, not the
statute; the port's job is to agree. `role_count` supplies the missing factor for
`income` and `payments`.

**D56 — a deduction stated twice is deducted twice.** D40 one section over.

    agent_(itemized_deduction_3,alice).      % stated twice
    agent_(itemized_deduction_3,alice).
    amount_(itemized_deduction_3,1993).
    ?- tax(alice,2010,3274).                                 % false, port true

SARA's deductions come to $11,575 and the port's to $9,582 — the difference is
exactly the repeated $1,993. `ItemizedDeductions.total` now multiplies by
`Inc.role_count of ev.agents, taxpayer`.

**D72 — a deduction with no amount is not an itemized deduction.** Every goal in
the `findall` has to succeed for there to be a solution, `amount_(D,Amount)`
included. The port's `itemizes` asked for the event, the agent and a date, but
not the amount.

    deduction_(alice_employer). agent_(alice_employer,bob).
    start_(alice_employer,2012-02-01).        % no amount_
    ?- tax(bob,2012,986).                                    % true, port $1,436

An amountless deduction routed the taxpayer to §63(a), where the itemized total
is $0, instead of §63(b), where the standard deduction is $3,000.

## II.6 — dates and windows

**D31 — `SameAbode` read only the first of several recorded dates.**
§152(c)(1)(B) gets each residence's span from
`( \+ start_(R,_) -> first_day_year(Taxy,S) ; start_(R,S) )`. The `->` commits on
its *condition*, and the condition is the negation, so the else branch is an
ordinary goal that backtracks over every recorded date.

    residence_(r). agent_(r,alice). agent_(r,bob). patient_(r,home).
    start_(r,"2015-09-01"). start_(r,"2008-01-01").
    ?- s152_c_1_B(bob,_,alice,_,_,2015).                      % true, port false

The port took `List.first_element`, the right reading of the *other* shape in
this file — `( end_(R,End) -> ... ; \+ end_(R,_) )`, where the commit really does
pick one end. All four date lists in §152 are now enumerated, and §7703 with
them (D74).

**D37 — §152(d)(2)(D)'s marriage must be dated, and only its.**
`is_stepparent_of` requires the marriage to carry a start; its four siblings
(`is_stepsibling_of`, `is_child_in_law_of`, `is_parent_in_law_of`,
`is_sibling_in_law_of`) all write `( \+ start_(M,_) ; start_(M,S) )` instead.
Only `utils.pl:262` omits the fallback.

    marriage_(m). agent_(m,alice). agent_(m,charlie).     % no start_
    father_(f). agent_(f,charlie). patient_(f,bob). start_(f,"1995-04-15").
    ?- is_stepparent_of(alice,bob,S,E).                       % no solutions

`SaraKinship.stepparent_of` now filters to `dated_marriages_of`; the other four
are left as they are.

**D42 — the in-law relations dropped the marriage's own window.** Each runs only
while *both* the kinship and the marriage do. `SaraKinship` built
`parent_in_law_of` and `sibling_in_law_of` from the kinship window alone, and
`child_in_law_of` from `cy.window` written three times.

    marriage_(m). agent_(m,alice). agent_(m,bob). end_(m,"2014-05-16").
    father_(f). agent_(f,charlie). patient_(f,bob). start_(f,"2014-04-15").
    ?- s152_d_2_G(alice,charlie,S,E), var(E).                 % false, port true

The marriage had ended, so SARA's `earliest` binds `End_relationship` and
`var(E)` fails. All three now join the marriage event's own window. Note the
marriage here carries an end but no start — exactly what `dated_marriages_of`
filters out, right for D37 and wrong here — so these three take the window from
the marriage event directly.

**D53 — §3301's wages are the calendar year's, not the employer test's window.**
§3306(a)(1)(A) asks about "the calendar year **or the preceding calendar year**",
so `dates_in_window` spans two years. `total_wages_employer/6` asks a different
question with the same shape: one year, the one being taxed.

    payment_(alice_pays_bob_c85). start_(alice_pays_bob_c85,2017-01-01).
    amount_(alice_pays_bob_c85,45252).
    ?- tax(alice,2018,0).                                   % true, port $420

alice is an employer in 2018 on the strength of the 2017 payment — SARA agrees —
but her 2018 wages are $0. The port now has `dates_in_year` beside
`dates_in_window`; the three §3306(a) call sites keep the two-year span.

**D74 — §7703(a)(1) read only the first of several marriage starts.** D31 one
section over, in the place its fix was not applied. SARA writes the default as a
*disjunction*, `( \+ start_(M,_), S = First_day_year ; start_(M,S) )`, so it
backtracks over every recorded start.

    marriage_(v1). agent_(v1,p1). agent_(v1,p2).
    start_(v1,"2016-01-01"). start_(v1,"2005-04-18").
    ?- s7703_a_1(p1,_,_,_,2015).                             % true, port false

`is_before(2016-01-01, 2015-12-31)` fails, Prolog retries on `2005-04-18` and
succeeds; the Prolog trace shows the retry explicitly (`✗ is_before(J,F)` then
`✓ is_before(J,F)`). `MarriageStatus.started_on` was
`List.first_element of marriage.starts`; it is now `start_candidates`, the
recorded starts or `[first_day_year]` when there are none, and `holds_a_1`
quantifies over it.

## II.7 — a grant is also a source of candidates

SARA accepts a case's injected conclusion as one more solution of the goal. Where
the port derived a candidate list from the event base, a world whose entire
content is the grant produced an empty list.

**D21 — §63(f)'s spouse exemption was read from injections only.** The inverse
error. `s63_f_1_B` and `s63_f_2_B` end in `s151_b_applies(Taxp,Spouse,Taxy)`,
which SARA both accepts as a grant and derives itself; the renderer's helper
looked only at `injections`. Every corpus case that reaches §63(f) grants the
conclusion, so this agreed on all 374.

    marriage_(m). agent_(m,alice). agent_(m,bob).
    blindness_(b). agent_(b,alice). start_(b,"2013-10-04").
    ?- s63_f_2_B(bob,_,2017).                                 % true, port false

`Section151.Individual` already derived the set as `exempt_spouses`; the guard now
reads the grant *or* that set. The test is membership, not non-emptiness: with two
spouses the exemption belongs to a particular one.

**D25 — §151(b)'s grant was matched in either argument position.**
`s151_b_applies(Taxp,Spouse,Taxy)` names the taxpayer first; the §63(f) helper
looked for the taxpayer in *either* of the first two positions, so
`s151_b_applies(alice,bob,2017)` also handed *bob* an exemption for alice. All
six corpus cases put the query's taxpayer first, so nothing needed the second
lookup — defensive over-matching. The helper now also respects D22.

**D28 — a granted §152(d)(2)(H) offered no candidate dependant.** `s2_b_3_B` is
asked with the dependant unbound and SARA binds it at the *last* conjunct, so a
grant is the only thing that can supply one.

    s152_d_2_H(charlie,bob,2018,_,"2018-01-01","2018-12-31").
    ?- s2_b_3_B(bob,_,2018).                                  % true, port false

`HouseholdMemberOnly.candidates` drew from the event base alone. Injected rows now
feed the candidate list alongside derived ones.

**D32 — a *granted* marriage bought no spouse exemption.** The §151 half of D26.
`SaraStatus.married` honoured a granted `s7703/4`; §151 did not, on either step —
`Individual.all_spouses` came from `MaritalStatus.spouses`, and
`SpouseExemptionApplies.married` re-tested the same way.

    s7703(alice,spouse,_,2017).        % granted; no marriage event
    ?- s63_d_2(alice,[2000],2017).                            % false, port true

SARA returns `[2000,2000]`. Fixing only the first changed nothing — the filter
removed what the list had gained — which is worth recording: **a fix that
measures as inert is usually a fix that is half done**, not one that was
unnecessary. (Superseded in placement by D65, which moved this into
`MaritalStatus`.)

**D60 — a granted dependant nobody names in a role.** D28 in the other §152
consumer.

    :- discontiguous s152_c_1/3.
    s152_c_1(bob,alice,2015).                % the whole world
    ?- s151_a(alice,4000,2015).              % true, port $2,000

`QualifyingChild.holds_c` reads the grant back correctly — it was never asked,
because bob was not a candidate. `DependantsOf.candidates` now unions in the
entities the case names as this taxpayer's dependant, across `s152_c_1/3`,
`s152_c/3`, `s152_c_3/3`, `s152_c_2/4` and `s152_d_2_H/6`.

**D79 — a granted §7703 names a spouse's *taxpayer*, and §151(b) needs it.**
`s151_b_applies(S,Taxp,Taxy)` opens with `s7703(S,Taxp,_,Taxy)` and `S` free, so
the other taxpayer is whoever §7703 pairs this one with. `Individual.marriage_partners`
enumerated marriage *events* only, and a grant that names the pair without one
left the set empty.

    s7703(alice,spouse,_,2017).               % the whole world
    ?- s63_c_1(spouse,2017,500).              % true, port $3,000

`s151_b_applies(alice,spouse,2017)` holds, so §63(c)(5) caps the spouse's basic
standard deduction at $500. `marriage_partners` now unions in the first argument
of each matching `s7703/4` grant, and drops the event-derived half when the
predicate was replaced.

## II.8 — distinctness, symmetry, and kind

**D41 — §2(b)(2)(C) also lets the taxpayer be their own spouse.** The loose end
D16 left, which had said (C) "is reached only with a bound, distinct spouse".

    marriage_(m). agent_(m,alice).
    death_(d). agent_(d,alice). start_(d,"2014-07-09").
    ?- s2_b_2_C(alice,_,_,2014).                              % true, port false

`SpouseDiedInYear` no longer requires the two to differ.

**D61 — §7703 is not symmetric, and §151(d)(2) asks it the other way round.**
`s151_d_2` generates the other taxpayer through `s151_b_applies(Otaxp,Taxp,Taxy)`,
whose first goal is `s7703(Otaxp,Taxp,_,Taxy)` — the roles reversed. The port took
candidates from the taxpayer's own §7703 spouses, the same set only while §7703 is
symmetric, and it is not: (a)(1)'s death branch reads the *spouse's* death (D17).

    marriage_(alice_and_bob_c32).           % no start, no end
    agent_(alice_and_bob_c32,alice). agent_(alice_and_bob_c32,bob).
    death_(bob_dies). agent_(bob_dies,bob). % no date
    ?- s63_c_5(alice,_,_,2014,500).                          % true, port false

`s7703(bob,alice,_,2014)` holds; `s7703(alice,bob,_,2014)` fails. `Individual` now
reports `marriage_partners` and §151(d)(2) enumerates over that.

**D68 — `usa` the atom is not `"usa"` the string.** Which `EntityTag` a value
earns depends on how SARA tests for it, and the two kinds of test disagree:
`==` distinguishes atom from string, while `atom_prefix/2` and `sub_atom/5`
convert either kind.

    service_(alice_employer). location_(alice_employer,usa).   % atom
    ?- tax(alice,2017,21635).                                  % false, port true

`entity_tag` gave every value spelled `usa` the `UsaEntity` tag whatever its kind.
The equality-based tags — `usa`, `united states government`, the two decrees — are
now string-only; prefix and suffix tags still apply to either kind.

## II.9 — §151/§152 wiring

**D27 — §7703(b)(1) accepted any child, not a qualifying child.** §7703(b)(1)
ends with `s152_a_1(Dependent,Taxp,Taxy)`, which is §152(c) in full. The renderer
supplied every child of the taxpayer with none of the tests applied.

    son_(b). agent_(b,charlie). patient_(b,alice).      % no birth date
    residence_(rc). agent_(rc,charlie). patient_(rc,alice_s_house).
    start_(rc,"2017-09-16").
    residence_(ra). agent_(ra,alice). patient_(ra,alice_s_house).
    ?- s7703_b_1(alice,_,_,2086).                             % false, port true

`Section152` already exports the right set — "§152(a)(1) children, for
§7703(b)(1)" — and the renderer now calls it.

**D43 — §151(d)(2)'s two readings had drifted apart.** Being somebody's *exempt
spouse* under (b) disallows the exemption exactly as being their dependent under
(c) does. `Individual.disallowed` had both routes; `DisallowedHolds`, the query
surface for the same subsection, had only the §152 one.

    marriage_(m). agent_(m,alice). agent_(m,bob).
    ?- s151_d_2(bob,_,0,2015).                                % true, port false

`DisallowedHolds` now calls `Individual.disallowed` rather than restating it.
**Two identical statements of one subsection is how this happened**; one was
updated and the other was not.

**D54 — §151(b)'s "spouse has no gross income" is the joint figure.**
`gross_income/3` is joint-aware: when the person filed a joint return covering the
year it is the *sum* of both individual incomes. The port asked
`GrossIncomeIndividual`.

    marriage_(alice_and_bob). marriage_(bob_and_charlie).
    joint_return_(bob_and_charlie_joint_return).  % 2015-01-01 .. 2015-12-31
    income_(charlie_income). agent_(charlie_income,charlie). amount_(...,4439).
    ?- tax(bob,2015,0).                                      % true, port $291

bob has two spouses; alice may claim an exemption for bob only if bob has no gross
income, and bob filed jointly with charlie. `SpouseExemptionApplies` now takes
`spouse_gross_income` as an input rather than computing it — §7703(b)(1) needs the
kinship lists to decide whether the couple lived apart, and this scope does not
carry them.

**D59 — §1's subsection query read only the granted taxable income.**
`s1_c(Taxp,Taxy,Taxinc,Tax)` reaches its rate schedule through `s63/3`, and every
corpus case that asks it also grants §63.

    % no facts at all
    ?- s1_c(alice,2017,_,0).                                 % true, port false

An empty world gives alice a taxable income of $0 and a §1(c) tax of $0. The grant
and the derivation are two solutions of the same goal, so `SubsectionHolds` now
takes both — `derived_income` with its own `derived_applies`, since a *replaced*
`s63/3` leaves only the rows.

## II.10 — harness, not port

**D15 — one case's role predicates were lost in grounding.** `tax_case_33`
defines its event base as rules over a generated workforce, using
`split_string/4`. `saralib.grounding` enumerated each event predicate with
`findall/3` over all-unbound arguments; `split_string/4` on an unbound first
argument raises an instantiation error, `findall/3` aborts, and the grounder's
`catch/3` recorded the whole predicate as empty — dropping the rule's extension
*and* the case's plain facts alongside it. The grounder now binds the first
argument to each identifier the unary case predicates name. Re-grounding all 376
cases changes exactly one file, which gains 1,420 facts.

**D29 — trimming a value's own whitespace split it in two.** `unquote` and
`entity_lit` both trimmed the token before interning, which is right for Prolog
source text and wrong for a value arriving already exact from the fact base.

    agent_(e,"state of "). income_(e). amount_(e,2312). start_(e,"2015-01-01").
    ?- s152_d_1_B("state of ",2015).                          % false, port true

One value in the corpus makes the difference: `"state of "`, §3306(c)(7)'s prefix
*including* its trailing space. Whitespace *around* the quotes is still trimmed;
whitespace inside the value is kept, and a typed value is not trimmed at all.

**D46 — the override marker was emitted for cases that declared the predicate.**
Introduced by D22 and latent until D45. `emit_case` read the record's
`discontiguous` field, which a generated record carries (an empty list included)
and a grounded corpus record does not, so `rec.get("discontiguous", ())` read the
absent field as "declared nothing". **Every corpus injection was marked as a
replacement — 154 of the 376 cases.** It cost nothing while the only consumers
were predicates whose corpus cases happen not to inject them, and broke
`s151_d_3_B_pos` the moment D45 gated `aa` on `s68_b/3`, which that case injects
*and declares*. The emitter now falls back to `.port/sara/discontiguous.json`,
built from the raw case files; markers fell from 154 cases to 3.

A default argument silently made 154 cases mean something they do not say, and
the acceptance suite did not notice until a fix depended on it. `discontiguous`
is not a flag with a sensible default — absent and empty are different claims.

**D64 — an archive that asked the two systems different questions.** The
generator once wrote the goal in two spellings: the raw text Prolog runs kept the
quotes SARA's template had, while the parsed arguments the Catala emitter reads
held the bare token. `entity_lit` picks the atom or the string key space by
exactly that quoting — as SWI's `==` does — so `"state of maryland"` and
`state of maryland` interned as two different entities, and every such query was
reported as a disagreement.

    ?- s63_c_6_D("state of maryland",2015).    % agrees once both are asked it
    ?- tax("johns hopkins university",2017,0). % likewise

The generator was fixed when this was found; the *archives* were not, and a stale
record is not a stale count — it is a permanent false finding no work on the port
can clear. **A differential harness is software under test, and an archived
finding carries its harness's defects with it.** This is why the current apparatus
regenerates cases rather than keeping an archive, and why `run_test_cases.py`
derives the question from the one spelling both systems share.

---

## II.11 — known and unfixed

**D76 — §3306(c)(2)'s call to `s3306_a_3` is dropped.** A deliberate port
narrowing, and the one place the stratification costs something. §3306(c)(2)
ends with a negated conjunct the port does not carry:

```prolog
s3306_c_2(Service,Location,Caly) :-
    ( type_(Service,"domestic service") ; purpose_(Service,"domestic service") ),
    patient_(Service,Person), location_(Service,Location),
    ( Location=="private home" ; ... ),
    \+ s3306_a_3(Person,_,_,Caly).        % <- dropped
```

Dropping a `\+` conjunct makes the port's (c)(2) **broader**: it excludes a
service from "employment" that SARA would keep.

**Why it is not fixed.** `s3306_a_3` → `s3306_a_3_is_wages` → `s3306_b`, and
`s3306_b` requires `s3306_c(Employment,_,_,_,Year)` — so restoring the conjunct
reintroduces the (c)(2) → (a)(3) → (b) → (c) cycle, which Catala rejects
outright. SARA terminates through it only by mode: with the year unbound
`s3306_a_3` raises an instantiation error rather than failing.

**Correction to the earlier record.** This was filed as unreachable, on a
measurement over SARA's 376 cases that traversed the edge zero times. **That is
no longer true.** Under the 2,541-case generated suite the edge is entered and
returns: `section3306.pl:591:8:c` and `:8:f` are both covered, and the clause's
exit point `591:9:e` with them. So the reason it is unfixed is the cycle, not
unreachability.

No case has yet *distinguished* the two systems here, and the cycle is why
building one is hard: a world that makes `s3306_a_3` succeed must first make
`s3306_c` hold for the same service.

**D77 — SARA's predicates are relations; the port computes a function.** Where a
case injects a conclusion *additively* (D22's `discontiguous` reading), the
statute's own derivation survives beside the injected row, so the predicate has
several answers at once. The port computes one.

    :- discontiguous s63_c_2/3.
    :- discontiguous s63_c_3/3.
    s63_c_2(alice,2017,2000).                  % beside the statute's own 3000
    s63_c_3(alice,3000,2017).                  % beside the statute's own 0
    ?- findall(V, s63_c_1(alice,2017,V), Vs).  % Vs = [3000,6000,2000,5000]

Each basic amount against each additional one: `s63_c_1_A` yields `[3000,2000]`
and `s63_c_1_B` yields `[0,3000]`. The port's `Section63` produces a single
standard deduction.

**Why the corpus never showed it.** SARA's own case asks
`\+ s63_c_1(alice,2017,4000)`, and 4,000 is in neither system's answers — they
agree, for unrelated reasons. A *bound* value asks SARA "is V among my
solutions" and asks the port "is V equal to my value", and those questions differ
only when SARA is non-deterministic and the corpus never binds a member that
separates them.

**Consequence for the suite.** The goal-strengthening pass (README, "The expected
value comes from SARA") rebinds a stale expected value to the one SARA derives —
but only where SARA derives exactly **one**. Binding a non-deterministic goal to
an arbitrary member would assert something the port may legitimately not compute,
and report a discrepancy that is an artefact of which member was picked; a first
implementation did exactly that, on ten cases across `s63_b`, `s63_c_1` and
`s3301`. Such goals are now left alone, which is why this entry exists rather
than a set of findings.

**Why it is not fixed.** Reporting a solution *set* rather than a value is a
signature change to every scope in the chain, and `verdict content boolean` at
the query surface cannot express it. D81 is the same gap reached from the other
side — several §1 clauses holding at once — and shows what the port can do about
it short of a set: pick the solution SARA reaches first, rather than refuse.

The honest statement of what the suite checks is therefore: **for a deterministic
goal, both systems compute the same value; for a non-deterministic one, both
agree on membership of the value the case happens to name.**

## II.12 — several clauses hold at once and the port refused to answer

**D81 — §1's four clauses are a disjunction; a single `status` is not.**
`s1/4` is `s1_a ; s1_b ; s1_c ; s1_d` and SARA backtracks over every clause that
holds, so a taxpayer can have two taxes and `tax/3` accepts either. The port
computes one `FilingStatus.status`, and its three exceptions to the `Unmarried`
default were unlabelled siblings — when two of their conditions held, Catala
refused the program outright rather than answering it.

```
"There is a conflict between multiple valid consequences for assigning the
 same variable."  SaraStatus.catala_en:223.24-54
```

    marriage_(m). agent_(m,alice). agent_(m,bob). start_(m,"2013-02-03").
    nonresident_alien_(nra). agent_(nra,alice).
    father_(f). agent_(f,bob). patient_(f,charlie).
    residence_(r). agent_(r,bob). agent_(r,charlie). patient_(r,house).
    start_(r,"2004-01-01"). end_(r,"2019-12-31").
    payment_(pay). agent_(pay,bob). amount_(pay,1). purpose_(pay,house).
    start_(pay,"2015-01-01"). end_(pay,"2015-12-31").
    income_(i). agent_(i,bob). amount_(i,700000). start_(i,"2015-12-31").
    ?- findall(T, tax(bob,2015,T), Ts).       % Ts = [253943, 263722]

Bob is married under §7703(a) — the marriage is dated, unended, and neither
spouse has died — and *also* a head of household, because §2(b)(1)'s
"not married" test is defeated by §2(b)(2)(B) once alice is a nonresident alien.
So §1(b) and §1(d) both apply: $253,943 through the head-of-household schedule,
$263,722 through married-filing-separately.

The three exceptions are now an explicit chain, in §1's own clause order — (a)
before (b) before (c) and (d) — which is the solution SARA reaches first, and the
one a gold amount records. `Unmarried` stays the base, since §1(c) demands
`\+ s7703(Taxp,_,_,Taxy)` and cannot hold beside (d) anyway.

**What this does not fix.** Choosing SARA's *first* solution is not the same as
having all of them: a case naming the second — here `tax(bob,2015,263722)`, which
SARA accepts — still separates the two systems. That is D77, and it is unfixed
for the reason recorded there.

---

# Part III — Latent

Port narrowings nothing has reached. Each is Part II in kind — a place the port
is knowingly not SARA — and each is one or two scopes of work. Listed here rather
than as numbered entries because no case has separated the two systems, so there
is no reproducer to record. (This is what `COVERAGE.md` used to hold.)

- **`s68_b/3` and the D11/D38 quirk.** It renders through `ApplicableAmountHolds`,
  which takes a status and a claimed amount and no world, so reproducing the
  unbound-argument reading would be a signature change.
- **Override `applies` companions still to add** (D45's pattern): `s151_b/3`
  beyond D49's use, `s63_c/3`, `s63_c_2/3`, `s63_c_3/3`, `s63/3`, `s2_b/3` —
  one `applies` output each.
- **§2(b)(3)(B)'s remaining unbound conjuncts.** `\+ s152_b(D,Taxp,Taxy)`,
  `\+ s152_a_1(D,Taxp,Taxy)`, `s152_d_1_D(D,Taxy)` and the (A)–(G) block all run
  with the dependant unbound too; only `s152_d_1_B` (D34) and (H) (D50, D75) are
  carried across. The port still asks the rest per-candidate.
- **`gross_income/3`'s joint-return branch with the person unbound** (D34's tail)
  — a third reading of that predicate, unreached.

## Adjudicated: not deviations

Three items sat here as open questions. Each is now settled as a **formalization
decision that preserves behaviour**, so none is a deviation and none belongs in
this file; all three are described in [README.md](README.md). Recorded here only
so they are not re-opened.

- **Cycle stratification.** §151 → §68 → §63 → §151, §152 ⇄ §7703,
  §68(b) → §2(b) → §151(c) → §151(d)(3) → §68(b), and §3306's two internal cycles
  are real, and Catala rejects cyclic definitions. The port breaks each at a
  genuinely acyclic entry point (§68(b), §7703(a), `s151_c_applies/3`, and
  §3306's `nonvar(Caly)` guard). **Behaviour-preserving everywhere except
  §3306(c)(2)**, which is D76 — that is the one stratification with a cost, and
  it now has its own entry rather than hiding inside this one.

- **`s151_c/4` → `s151_c_applies/3` at `section2.pl:309`.** §2(b)(1)(B) needs
  only *entitlement* to a §151 deduction and calls `s151_c/4` with `Deduction`
  unbound at both call sites. `s151_c/4` is `s151_c_applies/3` then `s151_d/3`,
  so the substitution is behaviour-preserving exactly if `s151_d/3` is total with
  its amount unbound. **It is** — structurally every path binds `Ea` (0 under
  (d)(2) or (d)(5); otherwise (d)(1)'s 2,000, reduced by (d)(3) or not), and
  empirically 24 of 24 probes across six taxpayers and four years succeed with no
  failure and no error. The port calls the applicability test alone, which is
  what breaks the third cycle and what SARA's own author left commented out on
  the next line.

- **`latest/2` and `earliest/2` leave their output unbound on an empty list**
  (`utils.pl:26`, `utils.pl:58`), which callers read as "no constraint". This is
  the `var`/`nonvar` idiom, not a defect, and it is modelled by the optional-date
  encoding in Layer 0. Load-bearing and easy to get wrong, which is why it is
  worth stating — but it is an encoding note, not a departure.
