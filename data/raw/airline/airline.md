# Required task

Formalize the supplied airline policy as needed to calculate the total cost of
a concrete passenger itinerary.

The code may be given these input facts: ticket price, route, cabin, passenger
membership or benefit status, accompanying children, each presented item's
kind, dimensions and weight, and any other relevant facts stated by a case. The
user does not specify which items are intended as carry-on bags, checked bags,
or personal items; derive those classifications from the policy.

Some facts may be absent. Preserve that absence using Catala `optional` values:
JSON `null` corresponds to Catala `Absent`. Do not substitute fabricated values
such as zero, false, an arbitrary city, or an arbitrary enumeration case.
Explicitly handle both `Absent` and `Present` before using every optional value
so omitted or inapplicable facts cannot cause evaluation errors. In the
`Absent` branch, proceed through the baseline, default, or inapplicable branch
that does not require that value; do not automatically propagate `Absent` to
the enclosing calculation. Check whether a rule applies before inspecting
optional facts used only by that rule.

Use the supplied source layout. `Definitions.catala_en` is the unannotated home
for itinerary facts, shared enumerations and structures, and genuinely
provision-neutral helpers used by the policy and API. It must not own policy
rules, required outputs, or evaluator orchestration.
`section1_non_textual.catala_en` contains RTDF fences for the independently
operative policy spans and its existing neutral preamble slots. Do not add new
preamble or synthetic block annotations, and do not move policy rules away
from the spans they formalize. `Api.catala_en` is also unannotated and is the
sole evaluator-facing integration layer. Its protected prose records the
requirement ID, scope, and output contract, and its metadata fence already
declares the required `TotalCost.total_cost` output. Keep that scope and output
unchanged. Add factual inputs, internal variables, and policy subscopes to the
declaration, then implement policy composition in its Catala fence. Do not
duplicate policy rules in `Api`, and do not add XML block annotations to
`Definitions` or `Api`.

`Api.catala_en` contains the following requirement:

- `TotalCost.total_cost`: calculate the total cost of a concrete passenger
  itinerary, including the ticket price, checked-bag charges, excess-size and
  excess-weight charges, special-item charges, and all applicable waivers and
  allowances. Return a non-optional monetary amount; `total_cost` itself must
  never be `Absent`.

Inputs must describe facts stated by a case. Do not require a caller to supply
a carry-on/checked-bag classification, fee classification, allowance decision,
or other conclusion that the policy is supposed to derive, except when a case
explicitly supplies a policy premise.

Define an input default only when the policy itself supplies that exact
default; otherwise use `optional` and preserve the distinction between an
absent fact and a present value. This restriction applies to input
representation, not to control flow: an `Absent` match branch must still
continue without the missing value and produce the required final result.

Encode the intrinsic domain of factual inputs with Catala assertions. Constrain
shares to 0% through 100%, and ages, durations, counts, or amounts to be
nonnegative when negative values are meaningless. Also assert structural or
chronological invariants inherent in a fact's definition. Do not add constraints
merely to suppress difficult tests, and describe every asserted domain in
`INPUT_VARIABLE_DESCRIPTION.json`.

## Input variable descriptions

After the Catala scopes typecheck, run `/rtdf/extract_input_requirements.sh`.
The helper reads the protected contract in `Api.catala_en`, calls
`clerk json-schema` for its declared scope, then writes one global `fields`,
`enums`, or `structs` description for each unique entry to
`INPUT_VARIABLE_DESCRIPTION.json`. Each field records the `FILE::SCOPE`
identifier that requests it. The evaluator derives relevant keys from the
selected scope. Fill each entry with a precise natural-language description.
State the passenger or itinerary, units, ordering and aggregation semantics,
inclusions and exclusions, and the meaning of `null`/`Absent` or of any legally
justified default. Rerun the helper after changing an input declaration. The
run is incomplete while any description is blank.
