# Fresh SARA Catala formalization

This project is derived from the literate templates in `data/raw/sara` and
validated against the unmodified SARA programs in `data/prolog/sara`.  It is
intentionally independent of every earlier SARA-to-Catala implementation.

## Source discipline

The nine `Section*.catala_en` files preserve the nine statutory texts. Every
independently operative statutory span carries an RSA block ID, including
parent aggregation and substantive trailing text. Trailing anchors use the
explicit `:closing` suffix rather than the former `:flush` name. Bare headings
have no blocks. `Definitions.catala_en` owns the shared factual world and generic
queries, while `Api.catala_en` owns the single evaluator-facing composition.
Neither infrastructure file has RSA/XML block annotations.

## Input boundary

The formalization uses statutory module boundaries instead of inlining the
whole factual database into §1. `Section2.FilingStatusFor`,
`Section63.TaxableIncome`, and `Section3301.UnemploymentTax` consume a taxpayer,
tax period, and normalized factual world. Their generated Catala outputs are
the three scalar inputs of `Section1.TotalTax`: taxable income, filing status,
and unemployment tax. This is the same dependency direction as the provisions:
§1 selects a rate schedule after the other sections have supplied the legal
quantities they define.

The external `Definitions.World` contains five lists: `dependency_candidates`
(Entity), `financial_facts`, `relationship_facts`, `employment_facts`, and
`status_facts` (their respective fact structures). Empty lists represent absent
families; no numbered slots or padding records are required. Attribute values use
`Definitions.FactValue` (`Known` or `Named`), avoiding the OCaml runtime
module name `Value`. Shared helpers
flatten these lists into event views while preserving normalization and
consistency checks. Repeated interchangeable employment facts may still use
scalar multiplicity, preserving the per-employee wage cap.

`prolog_to_catala/sara_fresh.adapter` accepts this native shape and migrates
historical numbered-slot JSON. It checks aliases and removes inactive padding
without truncating active facts. `legacy_inputs.json` remains the versioned
historical fixture for the 97 protected cases; the exporter converts it into
list-based Catala tests while checking original Prolog source hashes, subjects,
years, and expected totals. Adding a new Prolog case still requires deriving
and reviewing its factual fixture.

BOBCat's `--bobcat-max-list-length=N` now bounds each symbolic input list
(default 5). This bounds generated worlds, not concrete GT inputs: existing
cases retain up to eight relationship facts. A smaller bound explores a smaller
world and may miss behavior requiring more records. Intermediate representation
capacity is a separate BOBCat setting; list inputs do not guarantee that every
scope's symbolic search will finish quickly.

No Prolog statute conclusion is used by the converter or composer. Generated
Catala derives filing status, dependents, deductions, taxable income,
employment, wages, and unemployment tax from the factual world. The evaluator
can pass the three typed statutory results to `Api.TotalTax`, whose scalar
input surface remains compatible with `Section1.TotalTax`. The native
`Api.TotalTaxFromWorld` entry point now performs consistency validation and this
composition directly from factual inputs.

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

## Canonical facts and legacy compatibility

Numbered `World` slots are accepted only by the Python migration adapter.
Native Catala consumes the five lists. `prolog_to_catala.sara_fresh.adapter`
validates both shapes and exposes a derived canonical view; the gold rules use
matching shared helpers in `Definitions.catala_en`:

| Representation | Merge rule |
| --- | --- |
| Birth and child-relationship dates | One explicit DOB per person; conflicting explicit DOBs fail. Relationship start dates remain separate (including adoption). An age helper may explicitly request SARA's relationship-date fallback; it prefers explicit DOBs and otherwise chooses the earliest available relationship date. Explicit-birth-only provisions keep that policy. |
| Son/Daughter and inverse Father/Mother | One oriented child-parent edge per effective interval; retain original kinds as provenance. |
| Brother/Sister/Sibling and reversed pairs | One unordered sibling edge per effective interval; retain original kinds. |
| Repeated fact rows | Identical event ID + kind collapses; conflicting payloads fail. Multiplicity remains unchanged. |
| Income and received Payment | The same transaction ID counts once in gross income if recipient, amount, multiplicity, and dates agree; disagreements fail. Different IDs remain distinct even when amounts match. |
| Institution labels in purpose/location | A shared classification query reads either location or purpose. The canonical JSON view exposes a unique classification set, while original physical-location and purpose facts remain available. |
| Explicit itemization and deduction evidence | One year-aware selection helper combines explicit election by subject with the original SARA dated-deduction convention; event identity is not taxpayer identity. |

`Api.TotalTaxFromWorld` validates factual consistency before composing the gold
sections. Existing scalar `Api.TotalTax` callers remain supported. Raw templates
share the normalized helpers and perform the same input assertions in their API;
normalization infrastructure is not added as a repairable raw scope.

`legacy_inputs.json` is a compact, versioned snapshot of the 97 previously
protected factual inputs. It is a compatibility fixture, not a second canonical
input channel and not a general Prolog parser. Source hashes, query subjects,
years, and expected amounts are checked against the original Prolog files before
regeneration; changing those sources requires reviewing the fixture. Conversion
never derives expected tax from the candidate model. Generated canonical JSON
under `.port/sara_normalization/final` is disposable.

```sh
python3 -m prolog_to_catala.sara_fresh.export_catala_tests
python3 -m prolog_to_catala.sara_fresh.export_catala_tests --check
python3 -m unittest prolog_to_catala.sara_fresh.tests.test_normalization
python3 -m prolog_to_catala.sara_fresh.check
```

The final check runs all 97 original expectations using native Catala, with
absolute money error strictly less than $1. Invalid-input probes separately
check rejection of contradictory DOBs, repeated event payloads, and transaction
aliases. No expected answer is changed by normalization.
