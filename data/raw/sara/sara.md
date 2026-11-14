# Required task

Formalize the supplied Internal Revenue Code provisions as needed to calculate
a taxpayer's final tax liability.

Use the supplied source layout. `Definitions.catala_en` is the pre-completed
home for factual records, shared enumerations and structures, and genuinely
provision-neutral helpers used by multiple sections. It must not own statutory
rules, required outputs, or cross-section orchestration. Each
`Section[N].catala_en` module contains RSA fences for independently operative
statutory spans: leaf rules, substantive parent aggregation, and trailing
`:closing` text. Bare headings have no blocks. Do not add preamble or synthetic
block annotations. `Api.catala_en` is also unannotated and is the sole
evaluator-facing integration layer. Its protected prose records the requirement
ID, scope, and output contract, and its metadata fence already declares the
required `TotalTax.total_tax` output. Keep that scope and output unchanged. Add
internal variables and section subscopes to the declaration; keep the
predeclared `world`, `taxpayer`, and `period` inputs as the complete public
input contract. Implement cross-section composition in its Catala fence. Do not duplicate
statutory rules in `Api`, and do not add XML block annotations to
`Definitions` or `Api`.
Do not edit `Definitions.catala_en`; it is the fixed shared input contract.

`Api.catala_en` contains the following requirement:

- `TotalTax.total_tax`: calculate the final total tax liability of the person or
  entity whose tax the case asks for. Return the result as a non-optional
  monetary amount; `total_tax` itself must never be `Absent`.

Inputs must describe facts stated by a case. Do not require a caller to supply
a tax, eligibility decision, filing status, employment classification, or
other conclusion that these provisions are supposed to derive, except when a
case explicitly supplies a statutory premise.

Define an input default only when the statute itself supplies that exact default;
otherwise use `optional` and preserve the distinction between an absent fact and
a present value. This restriction applies to input representation, not to
control flow: an `Absent` match branch must still continue without the missing
value and produce the required final result.

Encode the intrinsic domain of factual inputs with Catala assertions. Constrain
shares to 0% through 100%, and ages, durations, counts, or amounts to be
nonnegative when negative values are meaningless. Also assert structural or
chronological invariants inherent in a fact's definition. Do not add constraints
merely to suppress difficult tests, and describe every asserted domain in
the corresponding Catala declarations.
