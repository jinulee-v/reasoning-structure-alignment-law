# SARA original cases through the nine public APIs

The original JSONL suite contains 362 executable Catala ports of SARA's 376
Prolog cases. The saved model was asked to implement the nine scopes in
`data/raw/sara/sara.md`. `API_COVERAGE.json` lists all 362 cases, their query,
the gold scopes called by the verdict, and their translation status.

| Query | Cases | Validated public-API projection |
| --- | ---: | --- |
| `tax/3` | 98 | `TotalTax`: round income and unemployment tax separately, then sum |
| `s152_a/5` | 2 | `DependencyEligibility.is_dependent` |
| `s152_c_1/3` | 2 | Qualifying-child result; these cases have no relevant override |
| `s152_d_1_D/2` | 2 | Query `DependencyEligibility.is_qualifying_child` for every other person and check that none qualify; both compositions replayed on gold |
| `s3301/6` | 2 | `UnemploymentTax.is_employer` and claimed tax |
| `s63_a/5`, `s63_b/4` | 4 | `TaxableIncome.taxable_income` compared with the claim; all four replayed on gold |
| **Gold API observable** | **110** | |

The candidate adapter represents **108** of these. Both `s3301/6` worlds
inject a `total_wages_employer/6` amount. The candidate has no premise input
for that amount. Passing gold's numeric predicate ID unchanged silently
discards it, so those two candidate comparisons are skipped. The other ten
non-tax comparisons were executed against the saved candidate and all passed.

The remaining **252** original cases have no validated projection through the
nine APIs. They are not counted as model failures:

| Statutory family | Cases | Clause result missing from public outputs |
| --- | ---: | --- |
| §1 | 49 | Bracket selection and subsection claims; the nine subsection worlds also error through gold `IncomeTax` |
| §151 | 16 | Personal totals, spouse/dependent, phaseout, and suspension clauses |
| §152 | 34 | Relationship, abode, age, income, and household subclauses |
| §2 | 32 | Individual filing-status conditions rather than the final status |
| §3306 | 59 | Employer thresholds, wage exclusions, geography, and service clauses |
| §63 | 38 | Deduction and special-rule intermediates |
| §68 | 14 | Individual reduction formulas and thresholds rather than their combined result |
| §7703 | 10 | Marital and household conditions rather than final filing status |
| **Not validated** | **252** | |

The nearby cases were checked by execution, not by matching names. On both
`s151_a/3` worlds, gold `ExemptionAmount` returns $2,000 for the taxpayer
while the clause asks whether the personal total is $4,000. Querying every
world entity did not recover that total from the API amounts. All nine §1
subsection worlds errored through gold `IncomeTax`. The four §63(a)/(b) worlds
gave a taxable-income claim comparison matching the clause verdict. Both
§152(d)(1)(D) worlds gave the expected result from the dependency composition.

This is a verified comparison base. Additional multi-call constructions would
need case-level gold validation and an adapter implementation before entering
the scored base. The adapter does not reimplement statutory clauses or create
hypothetical worlds to probe the model.

## Entity-valued tax facts

All 98 tax cases translate to candidate JSON. Of them, 62 contain gold
sum-type payloads: `PurposeEntity` in 61 cases, `NamedPlace` in 15, and
`MediumEntity` in one; the groups overlap. The candidate schema has no
corresponding payload constructors. The adapter preserves the relationships
used by these tax queries through its other fields:

- A payment purpose naming a service becomes a `reasons` link to the same
  service ID. A purpose naming a home or residence event becomes
  `HouseholdMaintenance` with that home ID in `patients`.
- Country facts attached to a named place move to the referring service.
  Other named places become `OtherPlace`; a gold `usa` atom stays distinct
  from the string `"usa"`.
- `MediumEntity` becomes `Noncash`; class events for hospitals, educational
  institutions, penal institutions, and American employers become candidate
  entity tags. Opaque purpose values naming no world entity are omitted.
- A dated deduction with an amount supplies a one-day `ItemizeElection` fact,
  matching gold §63. In the four §63 clause cases, an untyped payment to the
  taxpayer receives the candidate's `GrossIncome` purpose.

The adapter also maps supported gold predicate IDs, argument order, year keys,
and numeric payload positions to the candidate representation. It rejects an
unmapped premise rather than scoring a program that never received it. These
checks validate the data projection; they do not assert the saved model's tax
answer. Two representative payload-bearing tax worlds executed through the
candidate's `UnemploymentTax` scope. A direct `TotalTax` run on one of them
exceeded 180 seconds, so it supplied no tax-correctness result.
