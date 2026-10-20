# Demand-driven bounded branch testing

## Contract

An input-list bound `k` restricts every input list, including nested lists, to
length at most `k`. A branch goal is a source decision/outcome pair, shared
across dynamic calls. The query starts at the selected public scope's entry.
Only a **successful replay of the complete scope** supplies a coverage witness;
all observed source outcomes are credited, including incidental outcomes.
Partial executions and symbolic predictions supply no coverage.

The default strategy is `--bobcat-strategy=demand`. It compiles the selected
goal's dependency slice and suspends computations whose definitions are not yet
needed. Eager compilation remains available as `--bobcat-strategy=eager` for
comparison. Both query the configured maximum input bound directly.

## Bounds and completeness

Input length and intermediate storage capacity are distinct. Concatenating two
length-one inputs can produce a length-two result. Literal lists retain their
full source length. A structural size analysis tracks list lengths separately
from element shapes, propagates record/tuple/function shapes, and iterates folds
over the outer list bound. It memoizes abstract applications.

The compiler always uses this analysis. To prevent a conservative whole-program
estimate from materializing an impractically large Z3 datatype, representation
capacity is capped at 64 slots by default and can be changed with
`--bobcat-max-representation-capacity`. Exceeding that storage capacity marks
the encoding incomplete, so it cannot certify unresolved objectives as
unreachable. Replay-validated witnesses remain valid for the original program
regardless of that limitation.

## Shared, suspended relations

Whether a named type contains a function is computed once as the least fixed
point over the type declaration graph. Reverse dependency edges propagate
positive facts; subsequent queries are lookups instead of repeated unfolding.
This handles shared and cyclic type graphs without path-dependent memoization.

Symbolic environments use structurally interned DAG identities. Definition keys
retain lexical identity, captured environments, arguments, and representation
sorts. Conditional side conditions keep their guards. Field projection resolves
the requested field before constructing an entire record.

A suspended value introduces result `r` and validity `v`. Refinement adds:

```
v = validity_of_body
v => r = value_of_body
```

Children may remain suspended. Semantic refinement follows dependencies among
abstract symbols from the current query and learned failure conditions; sharing
an ordinary input variable alone does not make two computations dependent.

A suspended call can also have a reachability relation for the selected goal.
Each call-site guard implies an activation symbol. Expansion equates the
reachability flag to the goal's guarded occurrences in the body, retaining the
caller's guard and captured environment. Demand compilation does not close
activation to the currently known callers: additional callers may be discovered
later. Reachability caches belong to the current slice, so a newly learned
failure location cannot reuse a slice that omitted that location.

The eager strategy instead instantiates shared value/validity templates by
substitution. It does not rely on recursive-function unfolding in Z3.

## Failure-directed refinement

Assertions, fatal leaves, and missing-rule errors register suspended obligations
with their guards, environments, and source locations. A rejected replay selects
obligations at its failure location. An assertion adds `guard => predicate`; a
fatal leaf excludes its guard; a required default adds definedness and absence
of conflict. Each dynamic instance retains its own substitutions.

If the failure is outside the current slice, the engine enlarges the slice with
that location and replaces the old goal formula. Learned failure locations
accumulate monotonically. It does not preserve the old formula as an alternative
that could bypass the new obligation.

A goal continues through semantic refinements until it has a witness, becomes
infeasible under a complete encoding, or cannot make supported progress. There
is no retry count or concrete-input blacklist standing in for semantic learning.
Each goal has its own solver session; definitions remain shared within that
session. Solver timeouts queue larger-budget retries. Replay uses a cooperative CPU
budget checked at interpreter expression callbacks; it cannot preempt an
individual long primitive between callbacks. Replay timeouts first expand remaining semantic dependencies; when none remain,
they queue larger-budget replay retries.
Unresolved classifications remain pending so later successful replays can still
credit their outcomes.

For a complete bounded encoding, the intended abstraction invariant is:

```
successful execution reaching goal b within bound k => current query for b
```

Refinement adds necessary semantic conditions. SAT still requires native
validation. UNSAT is reported only when completeness is established.

## Calendar encoding

Dates use serial days. Calendar selectors are introduced on demand, with ground
constraints relating year/month/day to the serial value through the Gregorian
calendar. Symbolic input years range from 0 through 9999. Decoding uses the
concrete inverse calendar conversion of the solved serial value, including when
no calendar selector was needed by the query.

## Z3 model-construction memoization

BOBCat uses an isolated, patched Z3 4.13.3 library. The patch memoizes
`include_func_interp(f)` within one `model_generator::mk_func_interps` call.
The original loop visits each application of `f`; datatype eligibility scans
all applications of `f`. For `m_f` applications this repeats roughly `m_f²`
work. The cache reduces those repeated eligibility scans to roughly `m_f`.
This does not make the entire solver or model generator linear-time.

The eligibility predicate reads the fixed model-construction context. Its result
is identical for all applications of the same declaration during that phase.
The cache is discarded after each model-construction call, including across
solver push/pop and subsequent models. No solver constraints, domain bounds,
or model choices are changed by the memoization.

`build_z3.py` verifies a pinned source archive checksum, applies
[the patch](patches/z3-model-function-inclusion-cache.patch), and builds a Release
shared library under `.toolchain/bobcat-z3/`. Build metadata records source,
patch, and library hashes. BOBCat's Python launcher selects this library;
the shared opam/CUTECat installation is not modified.

## Verification and measurement

Regression tests cover bounded concatenation, nested lists, captured closures,
guarded assertions, failures outside the target slice, missing rules, unused
date inputs, list equality, native coverage, and model-cache lifetime. Timing
records separate capacity analysis, compilation, semantic/failure refinement,
solver/model decoding, and concrete replay. The branch manifest is emitted
before formula construction, preserving the denominator after timeouts.

Benchmark improvement must be measured from the union of successful native
replay outcomes at equal wrapper budgets. Microbenchmark improvements alone do
not establish end-to-end coverage improvement.
