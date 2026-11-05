# Required tasks

Formalize the supplied community-gaming rules so that callers can determine,
from the factual details of a proposed activity, whether each covered form is
authorized:

- `NSW-ART-UNION`: an art union;
- `NSW-CHARITY-HOUSIE`: charity housie;
- `NSW-CLUB-BINGO`: club bingo;
- `NSW-DRAW-LOTTERY`: a draw lottery;
- `NSW-NO-DRAW-LOTTERY`: a no-draw lottery;
- `NSW-PROGRESSIVE-LOTTERY`: a progressive lottery; and
- `NSW-SOCIAL-HOUSIE`: social housie.

Expose machine-callable scopes for those authorization decisions. Choose your
own data structures and internal decomposition. Inputs must be case facts, not
the authorization conclusions the rules are supposed to derive.

Every requirement ID above must have a corresponding entry in
`REQUIREMENT_OUTPUTS.json`, naming the Catala source file, a machine-callable
scope in that file, and one top-level output variable that provides the
requested authorization decision.

For input values that have realistic default values, please include their
default values in the code.

## Input variable descriptions

After the Catala scopes typecheck, run `/rtdf/extract_input_requirements.sh`.
The helper calls `clerk json-schema` for every distinct file and scope selected
in `REQUIREMENT_OUTPUTS.json`, then writes one global `fields`, `enums`, or
`structs` description for each unique entry to `INPUT_VARIABLE_DESCRIPTION.json`.
Each field records the `FILE::SCOPE` identifiers that request it. The evaluator derives relevant keys from the selected scope. Shared entries appear only once. Fill each entry
with a precise natural-language description, including
ownership, time period, units, relationship direction, aggregation, inclusions
and exclusions, and default semantics. Rerun the helper after changing an input
declaration. No description may remain blank.
