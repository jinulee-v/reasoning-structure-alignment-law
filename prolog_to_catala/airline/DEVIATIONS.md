# Deviations

Three kinds of thing are recorded here, kept apart because they carry different
weight:

* **A. Where the corpus's Prolog departs from the statute text.** The port
  follows the Prolog, per the bug-compatible decision, so each of these is a
  place where the Catala is deliberately *not* the statute.
* **B. Where the statute does not determine an answer** and the port had to
  choose. The oracle and the Catala encode the same choice, so the differential
  test cannot see these; only reading can.
* **C. Where the corpus cannot reach a rule at all**, so no amount of testing
  says anything about it.

Every entry says how it was established. Nothing here is inferred from reading
alone unless it says so.

---

## A1. The carry-on is read as a property of a bag, not as an allowance of one

The statute says "You're allowed **1** carry-on bag and **1** personal item in
all cabins", and gives two boxes: 22 x 14 x 9 in for the carry-on, 18 x 14 x 8
in for the personal item. That is an allowance of two specific items.

The corpus's Prolog reads it as a test on each bag independently:

```prolog
checked_bag_number(Id,N) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), Bs),
    nth1(N,Bs,Id).
```

`\+ carry_on(B)` excludes *every* item inside the carry-on box, however many
there are --- an allowance of one has become a property of each bag.

An earlier version of this entry said the personal item "is never modelled at
all". That was wrong, and `check_shipped_rules.py` catches it: **19 files state
the 18 x 14 x 8 box**, and some use it, `..._cases_31` properly:

```prolog
personal_item(B):- bag(B,L,W,H,_), L=<18, W=<14, H=<8.
carry_on(B)    :- bag(B,L,W,H,_), L=<22, W=<14, H=<9, \+ personal_item(B).
checked(B)     :- bag(B,_,_,_,_), \+ personal_item(B), \+ carry_on(B).
```

It makes no difference, and the reason is worth stating rather than measuring:
the personal-item box is **contained** in the carry-on box (18<=22, 14<=14,
8<=9), so any bag that fits the first fits the second, and
`\+ personal_item(B), \+ carry_on(B)` is just `\+ carry_on(B)`. Modelling the
personal item cannot change which bags are checked in *any* world, fuzzed or
otherwise --- not merely in the 300. Every file that states either box states
the same one; none states a different limit.

**Measured**: over all 300 cases, exactly **one** item fits the carry-on box in
each. The 45 items that also fit the personal-item box are that same item every
time. So no case in the corpus can tell the two readings apart, and the choice
is unforced by the data.

**The port follows the Prolog** --- `Airline.catala_en`, `carry_on_fits`, and
`Trip.checked` filters on it --- because the Prolog is the oracle and a fuzzed
world *can* tell the two apart. `airline_oracle.pl` encodes the same reading, so
the two systems agree on fuzzed worlds with several small items by
construction, not by accident.

## A2. Premium Economy's "---" cells are read as $0

Several rows of the First and Second Bag tables print "---" in the Premium
Economy column, which means the cabin is not offered on that route rather than
that the bag is free. The port reads them as $0.

**Measured**: no case in the corpus is a Premium Economy passenger on any of
those routes, so the reading is unforced. A fuzzed world does reach them, and
both systems read them the same way.

The alternative --- treating the itinerary as impossible --- would need a third
verdict alongside `total_cost` and `accepted`, and nothing in the corpus asks
for one.

## A3. "Not accepted" is a verdict, not a fee, and the corpus never reaches it

Three cells of the Overweight table read "Not accepted" rather than a figure:
Europe / Israel / Qatar and Australia / New Zealand, in the 70--100 lb band.
The tables also simply stop --- there is no cell for a bag over 100 lbs, or
over 115 in.

**Measured**: across the corpus's 2,372 items, weights run 5--100 lbs and sizes
35--115 in, and **no** Europe or Australasia case has a bag over 70 lbs. So
every one of these cells is unreached by any *case*.

The programs' *rules*, though, do say something, and they do not agree with one
another. Recovered by `check_shipped_rules.py` and grouped by region, the
answers past the last row of each table are:

| input | what the shipped rules answer |
|---|---|
| oversize, 116 in, US/Canada | 90 files have no clause; 11 say $200; 3 say $0; one says `na`, one `not_accepted`, one `99999` |
| overweight, 101 lbs, US/Canada | 63 have no clause; 7 say $200; 3 say $0; one `na`, one `not_accepted`, two `99999` |
| overweight, 71--100 lbs, Europe | 20 have no clause; 2 say $0; one says `na` |

That is not a merge conflict to resolve by picking a winner. It is the statute
being silent and the corpus's own authors disagreeing about what to do, which
is the strongest form this entry could take: **the ambiguity is in the
benchmark, not only in this port's reading of it.**

**Above 100 lbs the port now follows RuleArena, not silence.** The corpus's
upstream, RuleArena, carries the top overweight band upward rather than
stopping at 100 lbs --- $450 to or from Asia, $200 otherwise --- and it is the
only implementation of this statute that speaks there at all. A cross-check of
the fuzzed suite against it (`check_rulearena.py`) agreed on 1,048 worlds and
differed on exactly 2, both a 101 lb bag; the port was capping the band and
answering a flat $200. It no longer does. `bag_accepted` still returns false
above 100 lbs, so the statutory reading is unchanged --- only the figure that
accompanies it, which is now the upstream's rather than an invention.

One file resolves it the way the port does.
`airline_cases_complexity_0_airline_cases_69` writes
`overweight_fee(W,na) :- W > 70.` with the comment *"not accepted (irrelevant
here)"*, and propagates `na` through `max_fee/3` so the bag is rejected rather
than priced. That is exactly `bag_accepted`. So the port's reading is not
unforced after all --- it has one witness in the corpus, against two files that
answer $0.

The port answers with a second output rather than a fee. `accepted` is false
exactly when the policy will not carry some bag, and the oracle carries the
same predicate, so fuzzed worlds reach it in both systems.

Being precise about what the total then means: `overweight_fee` still returns
$200 in those cells, because it must return something, and `total_cost` adds
it. **That figure is not a claim.** The statute says the bag is refused; it
does not say what the trip costs instead, and neither system pretends to know.
A reader who sees `accepted = false` should ignore the total. The differential
test still exercises the band, because both systems compute the same
placeholder --- it checks that they agree about the *refusal*, which is the
part the statute determines.

## A4. The complimentary-bag allocation is a minimisation the statute does not state

"For First / Business, weight is 70 lbs for complimentary bags and 50 lbs for
excess charged bags." Which bags are the complimentary ones is the passenger's
to say, and the statute gives no rule.

The corpus's Prolog resolves it by **enumerating the allocations and taking the
cheapest** --- `airline_cases_complexity_0_airline_cases_14` does it explicitly:

```prolog
compute_total(MinTotal) :-
       findall(T, ( choose_two(L,F1,F2), cost_for_choice(F1,F2,T) ), Totals),
       min_list(Totals,MinTotal).
```

**The port follows it**, and this is one of the two places the Catala is not a
transcription of the statute at all but of a reading of it. The port does not
search: the base fees do not depend on the allocation, and each bag's saving is
independent of the others, so taking the largest savings is optimal and a rank
suffices. That equivalence is an argument, not a measurement --- but the
differential test does check it against the Prolog's actual search on the 26
cases whose reference program performs one.

## A5. Main Plus's allowance is derived from the tables, not stated

"^Main Plus includes 1 extra free checked bag in addition to the Main Cabin
allowance (max of 2)." The Main Cabin allowance is never given as a number. The
port reads it off the tables --- the number of leading positions the Main Cabin
column already prices at $0 --- which is 0 domestically and 1 on every route
where the Main Cabin first bag is free, so Main Plus gets 1 and 2 respectively,
and the footnote's cap binds exactly where it is written.

**Measured**: 41 cases are Main Plus, spread across domestic and international
routes, and all 41 agree. Before this reading, an earlier one that gave Main
Plus a flat single free bag failed 24 of them.

## A6. A free bag does not renumber the bags behind it

`airline_cases_complexity_0_airline_cases_12` is a Main Plus passenger with
four checked bags on a domestic route, and pays **$0 + $45 + $150 + $200**, not
$0 + $40 + $45 + $150. The free bag consumes position 1; the second bag is
still the second bag.

Established from that case, and it is the single case in the corpus that can
distinguish the two --- a passenger with a free allowance, on a route where the
first- and second-bag fees differ, with enough bags to reach the third tier.

## A7. One reference program collapses the weight allowance into the fee

`airline_cases_complexity_0_airline_cases_49` writes

```prolog
overweight_fee(W,0)    :- W =< 70.
overweight_fee(W,200)  :- W  > 70.
```

charging nothing below 70 lbs. Its case is First Class, and First Class
*complimentary* bags do carry a 70 lb allowance (A4 and the Weight and Size
section) --- so the file has folded the allowance into the fee function, losing
the distinction between complimentary and charged bags that the statute draws.

**Measured**: 147 other files, including six other First Class cases and eleven
Business ones, keep the two apart and write the 50 lb form. The file reproduces
its own label, so nothing in the corpus can see the difference; its own bags
are 60 and 68 lbs, which are free under either reading once the allowance is
applied.

The port keeps them apart, with the plurality. Recorded here because a reader
comparing the port to that one file will find a real difference and should know
it is the file, not the port.

## B1. Region rows are matched in the order the statute prints them

Several itineraries match more than one row --- a Havana to Paris trip is both
a Cuba row and a Europe row. The tables are printed in an order and the port
takes the first match, which is the ordinary reading of a rate table.

**Measured**: no case in the corpus matches two rows, so this is unforced by
the data. Both systems encode the same order (`first_bag_fee` in
`Airline.catala_en` and in `airline_oracle.pl`), so fuzzed worlds that do match
two rows agree by construction.

## C1. Statute rules no case can state, and no program formalizes

A DeonticBench airline case says a name, a cabin, an origin, a destination, a
numbered list of boxes with weights, and a ticket price. Nothing else. So a
whole part of the statute is unreachable --- there is no way to write "the
passenger holds AAdvantage Platinum", "is travelling on military orders", "has
a stroller", or "carries a soft-sided garment bag".

**Measured** by `check_shipped_rules.py`, over all 300 programs:

| statute rule | programs formalizing it |
|---|--:|
| Soft-sided garment bag, 51 in | **0** |
| Diaper bags, breast pump, strollers, mobility devices ("these don't count") | **0** |
| Complimentary Bags: AAdvantage / oneworld status tiers | **0** |
| Complimentary Bags: active U.S. military, 1st--5th bags free | **0** |
| Complimentary Bags: the free-first-bag destination list | **0** |
| Honduras's own second-bag row | **0** |
| 45-day refund claim; taxes not shown | **0** |

The region rows in the same position --- Honduras's own second-bag row, and
Guyana/Suriname's rows in both tables --- are now carried too, with four cities
added to reach them (Charlotte Amalie, Tegucigalpa, Georgetown, Paramaribo).
The U.S. Virgin Islands, which the tables name alongside Puerto Rico
throughout, is now a country of its own rather than silently folded in.

This is a gap between the *corpus* and the statute, not between the port and
the corpus.

**The port now implements them anyway**, on the project owner's instruction and
with the ground-truth problem accepted going in. What that changes, and what it
does not:

* `Airline.catala_en` gains a **Complimentary Bags** section --- the AAdvantage
  and oneworld ladder, military on orders and on personal travel, cardmembers,
  Flagship, the free-first-bag destination list --- and the carry-on section
  gains the exempt kinds, the soft-sided garment bag's 51 in limit, and the
  one-diaper-bag-per-child allowance. `airline_oracle.pl` gains the same.
* The generator gains two methods, `complimentary` and `carryon`, which
  enumerate these grounds exhaustively over their own vocabulary. That is the
  most that can be done: there is nothing to compare against.
* **So these rules are checked for consistency between the two systems and for
  nothing else.** Every other rule in this port is answerable to something ---
  the 300 reference programs, the rules recovered from them, RuleArena. These
  are answerable to a reading, mine, recorded below. A reader who disagrees
  with the reading will find the port wrong and every test still green.

Two readings had to be chosen and the statute settles both, which is the most
that can be said for them:

* **The grounds do not stack.** "If you qualify for complimentary bags based on
  your AAdvantage or oneworld status, the benefits are based on your
  **highest** status level" --- so a passenger who is Executive Platinum and on
  military orders gets the better of 3 and 5, not 8. The allowance is a
  maximum over the grounds.
* **Ticketing and check-in resolve to the higher.** The statute gives two
  bullets for when they differ --- higher at ticketing, show the receipt;
  lower at ticketing, current benefits apply --- and both come to the same
  thing, so the port carries both and takes the better.

One thing fell out of writing it that is worth recording: the "Confirmed
Domestic First / Business / Premium Economy customers get the 1st and 2nd"
rule, and the whole free-first-bag **destination list**, are *redundant* with
the fee tables for every route the port can express. The tables already price
those cabins' first two bags at $0, and already give Main Cabin a free first
bag to every country on the list. The rules are encoded because the statute
states them separately and a reader should find them, not because any world
turns on them.

The region rows go the same way. The tables name Guyana, Suriname, Honduras and
the U.S. Virgin Islands as distinct from their neighbours; the corpus's 73
cities include none of the first three, and no city distinguishes USVI from
Puerto Rico. The port carries only the countries the corpus reaches
(`AirlineWorld.Country`), and the dropped rows are named in the comments of
`Airline.catala_en`. Eight programs do carry a Guyana/Suriname clause copied
from the statute, which no case of theirs can reach.

## C2. `main/0` in the oracle is never entered by the suite

The enumerator asks `total_cost/1` and `accepted/0` directly, so the oracle's
`main/0` --- 11 of the 483 branch points --- is outside the suite by
construction. It exists so that a generated `prolog.pl` runs on its own, and
`run_test_cases.py` does enter it, once per case.

---

## Not a deviation: the corpus is self-consistent

Worth recording because it was not obvious in advance and it is what made a
single port possible at all. The 300 reference programs were written
independently, one per case, and each restates the rules it needs. They could
easily have disagreed with one another.

**Measured**: a single reading of the statute reproduces the reference answer
on **300/300** cases, and the shared oracle built from that reading agrees with
all 300 programs.

Stronger, and measured separately by `check_shipped_rules.py`: the programs'
*rules* --- not merely their answers --- agree with one another region by
region on every input the statute's tables define, once abstention (a rule
abridged to its case) is distinguished from dissent. Two files dissent inside a
table, both recorded above as A7 and A3, and both are single files against
147 and 20. Everything else the corpus disputes lies past the tables' last
rows, where the statute stops.

The same measurement on DeonticBench's `uscis-aao` domain came out the other
way, which is why it is not in this tree: mean pairwise Jaccard overlap of the
242 programs' predicate vocabularies is **0.021**, and **94.4%** of the 6,080
predicates they use appear in exactly one case. There is no shared statute
there to write once and test against.
