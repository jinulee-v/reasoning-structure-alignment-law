# Fresh SARA Catala formalization

This project is derived from the literate templates in `data/raw/sara` and
validated against the unmodified SARA programs in `data/prolog/sara`.  It is
intentionally independent of every earlier SARA-to-Catala implementation.

## Source discipline

The nine `Section*.catala_en` files preserve the nine statutory texts. Every
independently operative statutory span carries an RTDF block ID, including
parent aggregation and substantive trailing text. Trailing anchors use the
explicit `:closing` suffix rather than the former `:flush` name. Bare headings
have no blocks. `Definitions.catala_en` owns the shared factual world and generic
queries, while `Api.catala_en` owns the single evaluator-facing composition.
Neither infrastructure file has RTDF/XML block annotations.

## Input boundary

The formalization uses statutory module boundaries instead of inlining the
whole factual database into §1. `Section2.FilingStatusFor`,
`Section63.TaxableIncome`, and `Section3301.UnemploymentTax` consume a taxpayer,
tax period, and normalized factual world. Their generated Catala outputs are
the three scalar inputs of `Section1.TotalTax`: taxable income, filing status,
and unemployment tax. This is the same dependency direction as the provisions:
§1 selects a rate schedule after the other sections have supplied the legal
quantities they define.

The external `Definitions.World` has no optionals and no list-valued fields. It separates
financial, relationship/return, employment/institution, and personal-status
facts into bounded fixed-shape positions. Each family has its own closed kind;
unused positions use an explicit no-fact constructor, and scalar sentinels are
removed before provisions observe role or date collections. Catala provides a common internal event view only where
a provision genuinely quantifies across families. The converter filters
annual generator facts to the queried year and groups interchangeable
employees only after totaling each employee's wages, preserving the
per-employee wage cap through scalar multiplicity.

The deterministic Prolog-to-Catala mapping was implemented only after those
declarations typechecked.  It lives in `prolog_to_catala/sara_fresh`: the
grounder evaluates only case-local fact and generator clauses, and the adapter
maps their ground extension to the final `World`, `Entity`, and `TaxPeriod`
declarations. Generated Catala then evaluates the three upstream statutory
scopes; the Python composer performs only typed field and enum-constructor
conversion into `Section1.TotalTax`. Atom/string distinctions, linked country values,
point-event intervals, duplicate solutions, and stable entity identifiers are
all handled explicitly.  `INPUT_VARIABLE_DESCRIPTION.json` documents the
resulting boundary.

No Prolog statute conclusion is used by the converter or composer. Generated
Catala derives filing status, dependents, deductions, taxable income,
employment, wages, and unemployment tax from the factual world. The evaluator
then passes the three typed statutory results to `Api.TotalTax`, whose public
input surface remains the same small type-specific boundary as
`Section1.TotalTax`.

## Acceptance gates

From the repository root, run:

```sh
python3 -m prolog_to_catala.sara_fresh.check
```

The checks require:

1. all nine Catala modules typecheck;
2. all 97 original end-to-end `tax/3` programs agree exactly with Catala;
3. all 1,164 deterministic fuzzed Prolog cases agree: twelve monetary-fact
   mutations of each of the 97 end-to-end cases are evaluated independently by
   the Prolog statutes, translated through the final Catala input declarations,
   and replayed through compiled Catala;
4. generated cases contain multiple distinct positive tax results,
   rather than only `$0` cases.

Differential reports are written below `.port/sara_fresh`. Source files are
never generated from or synchronized with another Catala formalization.

The acceptance check also rejects every provision block containing only Catala
comments.  Passing typechecking is insufficient: executable declarations,
definitions, rules, or exceptions must occur in the block corresponding to the
provision they implement.

`run_fuzz_cases.py` remains a fast 33-case tax-schedule smoke check and is not
an acceptance gate.  The acceptance suite is `run_fuzzed_prolog_cases.py`; its
full per-case report is `.port/sara_fresh/fuzzed_prolog_report.json`.
After a full independent-oracle run has produced that report,
`--reuse-oracle-report` provides a faster regression pass: it re-grounds every
base case, applies the same twelve source-level amount mutations to the
extensional facts, and evaluates all 1,164 current Catala inputs in parallel.

The factual input contract uses bounded fixed-shape positions, and
interchangeable repeated employment facts are represented by a scalar
multiplicity.
