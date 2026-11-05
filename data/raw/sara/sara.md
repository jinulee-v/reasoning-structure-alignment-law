# Required task

Formalize the supplied Internal Revenue Code provisions as needed to calculate
a taxpayer's final tax liability.

The code may be given these input facts: taxpayer income, deductions, tax year,
filing election, marital and household circumstances, family relationships,
ages, residency, support, employment, remuneration, payroll, and any other
relevant facts stated by a case.

Some facts may be absent. Preserve that absence using Catala `optional` values:
JSON `null` corresponds to Catala `Absent`. Do not substitute fabricated values
such as zero, false, an arbitrary date, or an arbitrary enumeration case.
Explicitly handle both `Absent` and `Present` before using every optional value
so omitted or inapplicable facts cannot cause evaluation errors. In the
`Absent` branch, proceed through the baseline, default, or inapplicable branch
that does not require that value; do not automatically propagate `Absent` to
the enclosing calculation. Check whether a rule applies before inspecting
optional facts used only by that rule.

Use the supplied source layout. `Definitions.catala_en` is the unannotated
home for factual records, shared enumerations and structures, and genuinely
provision-neutral helpers used by multiple sections. It must not own statutory
rules, required outputs, or cross-section orchestration. Each
`Section[N].catala_en` module contains RTDF fences for independently operative
statutory spans: leaf rules, substantive parent aggregation, and trailing
`:closing` text. Bare headings have no blocks. Do not add preamble or synthetic
block annotations. `Api.catala_en` is also unannotated and is the sole
evaluator-facing integration layer. Its protected prose records the requirement
ID, scope, and output contract, and its metadata fence already declares the
required `TotalTax.total_tax` output. Keep that scope and output unchanged. Add
factual inputs, internal variables, and section subscopes to the declaration,
then implement cross-section composition in its Catala fence. Do not duplicate
statutory rules in `Api`, and do not add XML block annotations to
`Definitions` or `Api`.

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

## Input variable descriptions

After the Catala scopes typecheck, run `/rtdf/extract_input_requirements.sh`.
The helper reads the protected contract in `Api.catala_en`, calls
`clerk json-schema` for its declared scope, then writes one global `fields`, `enums`, or
`structs` description for each unique entry to `INPUT_VARIABLE_DESCRIPTION.json`.
Each field records the `FILE::SCOPE` identifier that requests it. The evaluator
derives relevant keys from the selected scope. Fill each entry with a precise
natural-language description. State the person or entity, time period, units,
relationship direction, aggregation semantics, inclusions and exclusions, and
the meaning of `null`/`Absent` or of any legally justified default. Rerun the
helper after changing an input declaration. The run is incomplete while any
description is blank.
