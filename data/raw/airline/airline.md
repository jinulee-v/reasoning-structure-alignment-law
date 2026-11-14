# Required task

Formalize the supplied airline policy as needed to calculate the total cost of
a concrete passenger itinerary.

Use the supplied source layout. `Definitions.catala_en` is the pre-completed home
for itinerary facts, shared enumerations and structures, and genuinely
provision-neutral helpers used by the policy and API. It must not own policy
rules, required outputs, or evaluator orchestration.
`airlinepolicy.catala_en` contains RSA fences for the independently
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
Do not edit `Definitions.catala_en`; it is the fixed shared input contract.

`Api.catala_en` contains the following requirement:

- `TotalCost.total_cost`: calculate the total cost of a concrete passenger
  itinerary, including the ticket price, checked-bag charges, excess-size and
  excess-weight charges, special-item charges, and all applicable waivers and
  allowances. Return a non-optional monetary amount; `total_cost` itself must
  never be `Absent`.

Inputs must describe facts stated by a case, and it is already completed for you. Do not require a caller to supply
a carry-on/checked-bag classification, fee classification, allowance decision,
or other conclusion that the policy is supposed to derive, except when a case
explicitly supplies a policy premise.

Encode the intrinsic domain of factual inputs with Catala assertions. Constrain
shares to 0% through 100%, and ages, durations, counts, or amounts to be
nonnegative when negative values are meaningless. Also assert structural or
chronological invariants inherent in a fact's definition.
