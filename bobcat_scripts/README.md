# BOBCat

BOBCat is **Branch-objective backward testing**. It is a separate
Catala compiler fork for bounded, goal-directed branch testing. CUTECat's
concrete-seed execution, path-prefix DFS, constraint flipping, mutation, and
coverage-priority scheduler are not part of BOBCat's execution algorithm.

For each distinct `(file, scope)` named by a benchmark's
`REQUIREMENT_OUTPUTS.json`, BOBCat:

1. keeps the DCalc definition graph shared and enters only definitions called
   by the selected scope;
2. assigns a stable `(decision_id, outcome_id)` to every source branch outcome;
3. compiles a demand-driven slice at the configured maximum input-list bound;
   intermediate storage has a separate, explicit bound;
4. reuses value relations, parameterized first-order functions, and activated definition
   bodies rather than copying guarded expressions at each reference;
5. uses a persistent solver for each goal and validates every candidate by
   concrete replay of the complete scope;
6. learns guarded assertion/failure obligations at the location rejected by
   replay. Unsupported refinements remain `UNKNOWN`; the engine does not guess
   dataset-specific preconditions.

The semantic design and its limits are described in [SEMANTICS.md](SEMANTICS.md).
An appendix-style account of the algorithm, ranked optimizations, and evaluation
is available in [BOBCAT_REPORT.md](BOBCAT_REPORT.md).

The solver supports scalar and nested conditionals, lazily resolved function
calls, options, matches, ordered defaults, recursive bounded-list inputs,
`map`/`filter`/`find`/`fold`/`reduce` composition, calendar-aware date and
duration operations, stable period sorting, and bounded month/year period
splitting. Unsupported symbolic operations are reported as `UNKNOWN`; BOBCat
never falls back to concolic path exploration. Concrete replay remains the
authority when symbolic and runtime behavior disagree.

`--bobcat-output=FIELD` roots the branch manifest and backward symbolic slice
at one top-level entry-scope output. Branches used only by other eagerly
materialized output fields are excluded from that target's coverage universe.

## Separate compiler repository

The compiler is tracked as a Git submodule published at
[`jinulee-v/bobcat`](https://github.com/jinulee-v/bobcat). The implementations
are deliberately isolated:

| path | purpose |
|---|---|
| `.toolchain/src/catala-cutecat` | existing CUTECat checkout; unchanged by BOBCat |
| `.toolchain/src/catala-bobcat` | pinned `jinulee-v/bobcat` submodule containing the compiler fork and `compiler/bobcat/` |
| `bobcat_scripts/patches/` | the active Z3 model-construction cache patch and historical compiler patch exports |
| `.toolchain/src/catala-bobcat/_build/default/compiler/catala.exe` | binary used by every BOBCat script |
| `.port/<port>_bobcat/` | BOBCat-only projects, solver results, datasets, and reports |

Build the separate compiler and its isolated Z3 runtime (requires CMake, a C++ compiler, and `patch`):

```sh
python3 bobcat_scripts/build.py
```

If `.toolchain/src/catala-bobcat` is absent, the build script initializes the
repository-pinned submodule (or clones the BOBCat repository directly when
run outside a superproject). It reuses the CUTECat opam switch only as an
OCaml/Z3 dependency environment; it does not invoke the CUTECat compiler
binary. The build also installs a pinned Z3 4.13.3 with a model-construction
memoization fix under `.toolchain/bobcat-z3/`; it leaves the shared Z3 intact.

## Running the engine

The native command is:

```sh
LD_LIBRARY_PATH="$PWD/.toolchain/bobcat-z3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
.toolchain/src/catala-bobcat/_build/default/compiler/catala.exe \
  bobcat program.catala_en -s Scope --bobcat-max-list-length=5 \
  --bobcat-max-representation-capacity=64 \
  --bobcat-timings
```

Pass `--bobcat-positive-hundred-money-inputs` to add hard input-domain
assumptions requiring every present `money` input, including nested list and
record fields, to be strictly positive and an exact multiple of 100 currency
units. The option is off by default so signed-money programs retain Catala's
ordinary input domain.

Its machine-readable result stream includes:

```text
BOBCAT_BRANCH_MANIFEST ["decision/outcome", ...]
BOBCAT_REPLAY {"objectives":[...],"input":{...},"branches":[...]}
BOBCAT_REFINEMENT {"input":{...},"predicted":[...],"observed":[...],...}
BOBCAT_TIMING {"phase":"shared_compilation","objectives":[...],"cpu_ms":12.3}
BOBCAT_TIMING {"phase":"z3_check_and_decode","objectives":[...],"cpu_ms":4.2,"list_bound":1}
BOBCAT_OBJECTIVE {"objective":"decision/outcome","status":"sat",...}
BOBCAT_OBJECTIVE {"objective":"decision/outcome","status":"unsat"}
BOBCAT_OBJECTIVE {"objective":"decision/outcome","status":"unknown",...}
BOBCAT_DONE 3
```

When the entered scope contains no branch outcomes, the manifest remains
empty and BOBCat emits one concretely validated input using CUTECat's default
values instead of inventing a branch objective:

```text
BOBCAT_BRANCH_MANIFEST []
BOBCAT_REPLAY {"kind":"branchless_default","objectives":[],"input":{...},"outputs":{...},"branches":[]}
BOBCAT_DONE 0
```

This is an entry-scope exception that ensures every target has a test case.
It does not change the branch-coverage numerator or denominator. The defaults
match CUTECat: true, numeric zero, 2010-01-01, a ten-day duration, the first
enumeration constructor, None, and an empty list.

A scope with no inputs has exactly one possible execution. BOBCat emits that
case as `fixed_input`, marks its visited manifest outcomes reachable, and marks
the remaining outcomes unreachable without asking Z3 to rediscover that the
input space is a singleton.

The campaign entry point reads all five `REQUIREMENT_OUTPUTS.json` files,
groups repeated output mappings by `(file, scope)`, resolves declarations in
the native source modules (including French `Inclusion` fragments), and
invokes only `catala bobcat`. Targets intentionally enter the whole scope:
that gives BOBCat and path-oriented CUTECat-list the same branch universe,
while each target's note preserves the requirement IDs and output names:

```sh
python3 bobcat_scripts/generate_dataset.py --list
python3 bobcat_scripts/generate_dataset.py --port airline \
  --bobcat-max-list-length 5 \
  --bobcat-max-representation-capacity 64 \
  --solver-timeout-ms 2000 --solver-timeout-max-ms 60000
```

The campaign driver launches each BOBCat process with a 256 MiB native stack.
This accommodates deeply nested, recursion-free DCalc produced by large Catala
modules; it does not change list bounds or solver semantics.

The campaign default is 1,800 seconds (30 minutes) per target. `--timeout`
overrides that outer process budget; the separate solver timeout options keep
one difficult Z3 query from monopolizing it.

Objective classifications are written under `.port/<port>_bobcat/goals/`.
Every successfully decoded input that completes concrete replay is written to
the dataset, including a replay whose observed path differs from its symbolic
prediction. Coverage is credited only from the outcomes concrete replay
actually observes. The dataset is not reduced with a coverage-based set-cover
pass: every validated example from every public wrapper scope is retained and
published.

The default strategy is `--bobcat-strategy demand`; `eager` is available for
controlled comparisons. The configured list bound applies only to symbolic
inputs. Structural analysis derives the capacity required by grounded and
intermediate lists, while `--bobcat-max-representation-capacity` limits the
materialized Z3 list datatype to 64 slots by default. If the derived capacity
is larger, BOBCat marks the encoding incomplete: replay-validated witnesses
remain sound, but unresolved objectives are not classified as unreachable.
Objective ordering defaults to `--bobcat-objective-order=depth`, visiting
outcomes by their minimum branch nesting depth through the shared DCalc
definition graph. The prior source-file and branch-kind ranking remains
available as `--bobcat-objective-order=legacy`. The five-dataset comparison is
recorded in [OBJECTIVE_ORDER_EXPERIMENT.md](OBJECTIVE_ORDER_EXPERIMENT.md);
the full 1,800-second run covered slightly fewer validated outcomes with depth
ordering, so the default expresses the chosen traversal policy rather than an
empirical coverage advantage.
The manifest is emitted before formula construction and retains the coverage
denominator even when compilation or solving times out.

A rejected replay activates the matching guarded semantic obligations for all
compiled instances at that runtime source location. The engine retries when it
learns an obligation; a failure without a new supported obligation remains
`UNKNOWN`. Infeasibility is reported only with a complete
encoding, and includes `list_bound` in the native objective record.

Use `--bobcat-timings` on the campaign driver to record capacity,
summary counts, compilation, solving, replay, and failure-refinement costs.

## Tests

```sh
PYTHONPATH=bobcat_scripts python3 -m pytest bobcat_scripts/tests -q
```

The direct-engine regressions include intentionally infeasible nested arms,
including one whose outer condition is a separately defined predicate. BOBCat
proves the contradictory outcome UNSAT without enumerating paths.

An isolated campaign can set `BOBCAT_CAMPAIGN_ROOT` to a separate output directory.
Source datasets and shared build tools are unchanged by that setting. Use the
same environment variable for generation, coverage measurement, and comparison.

BOBCat uses ordinary first-model SAT queries. It has no MaxSAT or coverage
optimization mode; concrete replay already credits every incidentally observed
outcome from a successful test.

## Measured demand-driven campaign

The earlier retained implementation was tested on 23 public-wrapper targets
with a 1,800-second timeout per target. See the
[coverage and runtime comparison](../.port/bobcat_experiments/demand/COMPARISON.md)
for the supplied original baseline, previous recovery run, validated coverage,
and remaining timeouts/resource failures.
