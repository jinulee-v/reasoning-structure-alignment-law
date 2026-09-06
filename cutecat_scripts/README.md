# Concolic execution → a dataset of inputs and outputs

[CUTECat](https://github.com/CatalaLang/catala/tree/cutecat-rebase) is a
concolic interpreter for Catala: it runs a scope on a concrete input while
recording the branch conditions symbolically, hands the negation of one of them
to Z3, and runs again on whatever Z3 returns — until no unexplored branch is
left. What it prints is one input/output pair per path.

This tree turns that stream into a dataset. For every target it runs the
engine, reads back what it printed, and writes one JSON row per path:

```json
{"target": "sara_section68", "path": 7,
 "inputs":  {"agi_in": "300000.00", "itemized_deductions_in": "40000.00",
             "status_in": {"cons": "MarriedFilingJointly"}, "taxable_year_in": 2009},
 "outputs": {"applies": true, "aa": "166800.00", "reduction": "3996.00",
             "deductions_out": "36004.00"},
 "error": null, "exact": true}
```

The rows are of the ports that already live in this repository — the SARA
port's nine IRC sections and the DeonticBench *airline* port — so the dataset
is of a statute somebody formalized and validated, not of a toy.

## The pipeline

```
python3 cutecat_scripts/generate_dataset.py --list   # what the targets are
python3 cutecat_scripts/generate_dataset.py          # run them all
python3 cutecat_scripts/generate_dataset.py sara_section68 --timeout 60
python3 cutecat_scripts/generate_dataset.py --timeout 300 --jobs 8
```

Every run opens with the **census**: both ports are scanned for their entry
points --- every `declaration scope` and every top-level `declaration f ...
depends on ...` --- and one wrapper scope is written per enterable top-level
function, into that port's `harnesses/generated/`. The wrappers are what make those
functions targets at all, so this is not a step to remember separately; it
costs a sub-second scan and it writes each port's `ENTRY_POINTS.md`.

Then three steps per target, all in `cutecatlib/`:

| step | what happens | where |
|---|---|---|
| 1 | a private clerk project is assembled — the file under test, the port modules it uses, and a standard library built by *this* compiler | `run.prepare_project` |
| 2 | `catala concolic -W -s SCOPE --message-format=gnu` is run in it, with a timeout | `run.run_concolic` |
| 3 | the `[RESULT]` stream is parsed into paths and written as JSONL | `parse.py`, `values.py`, `dataset.py` |

Output, all of it regenerable:

```
.port/<port>_cutecat/        one tree per port: sara_cutecat, airline_cutecat
  build/<target>/            the clerk project, kept so a run can be reproduced
  raw/<target>.stdout        what CUTECat printed, byte for byte
  dataset/<target>.jsonl     one row per path
  dataset/INDEX.json         per target: the command, the counts, the schema
  reports/DATASET.md         the same, readable
  reports/ENTRY_POINTS.md    the census: every way into this port
.port/cutecat_tools/         the two OCaml tools, built against the compiler
```

The trees are separate all the way down, so a run over one port neither reads
nor rewrites anything belonging to the other, and each port's `INDEX.json` and
reports describe that port alone.

Three flags in step 2 are load-bearing and none of them is obvious.

**`-W`** (whole program). Without it a `> Using Section151 as S151` is a
*linked* module: the compiler resolves it to a compiled OCaml object and the
interpreter calls into it, so the section executes as one opaque step and
contributes no path constraints at all. The run finishes in a second having
found one path. `-W` inlines the module sources instead, which is what makes
the port's own branches visible to Z3.

**`--message-format=gnu`**. CUTECat has no machine-readable output; the default
message format renders each result in a Unicode box wrapped to the terminal
width, so a struct comes back across several lines with `│` down the left. GNU
format is one line per message with newlines flattened to spaces, which is what
makes `parse.py` possible at all.

**The private project directory.** CUTECat is built from a branch, not from the
1.2.1 release, so it must not be pointed at `data/catala_gold/sara/_build` — that
standard library was laid down by the other compiler. Each target gets its own.

## How much of the port a suite executes, and how well

```
python3 cutecat_scripts/measure_coverage.py --per-target
python3 cutecat_scripts/measure_coverage.py --uncovered   # every outcome missed
```

One script, two measurements, always both: **statement** coverage --- was an
expression evaluated --- and **branch** coverage --- did every decision come
out every way it can. They are read off the same union of coverage maps, so
the second costs nothing beyond the first, and reporting only the first would
flatter every suite.

Path counts say what the engine did, not what the statute got. Dataset
generation passes `--conc-code-coverage`: the engine records the program's
reachable positions once, initialization once, and reached positions for every
generated path under `.port/<port>_cutecat/coverage/`. The command above unions
those maps without rerunning the examples and writes, per port,
`reports/COVERAGE.md` and `dataset/COVERAGE.json`. A row from an
older dataset with no native map is replayed automatically as a compatibility
fallback.

A **rule** is one item of Catala source — a top-level `declaration`, a `scope`
header, a `definition` / `rule` / `exception` inside a scope. A **branch** is
one recorded expression position inside a rule. Two artifacts have to be
subtracted before the numbers mean anything, and both are visible in the raw
map:

- whole-program mode builds a closure for every top-level definition in every
  module it links, marking exactly one position — the definition's own name.
  `SaraKinship` comes back with fifteen "reached" positions from a suite that
  never calls it, so a rule counts as exercised only at **two** reached
  positions or more;
- a **constant** — a top-level declaration with no `depends on`, such as
  `Airline`'s ten country lists — is computed once at load, so it is always
  fully covered. Constants are held out of the ratio and counted apart.

The union of the coverage maps happens in OCaml
([coverage_tool/catala_coverage.ml](coverage_tool/catala_coverage.ml)): the
`--code-coverage` dump is a marshalled OCaml value, not a format, so nothing
outside the compiler can read it. The tool is built against the libraries the
CUTECat switch installs and deliberately lives outside the pinned checkout.

### Which branches a suite takes

Statement coverage cannot tell an `if` taken both ways from one taken only on
the `then` side, and for comparing an execution path against a reasoning trace
that is the whole question. The branch half of the report joins two things
that come out of the same dcalc program:

- an **inventory** of decision outcomes, from a Catala plugin in
  [branch_tool/](branch_tool/): for every `if`, `match` and default group, the
  source position that is reached exactly when that outcome is taken;
- the **coverage map** CUTECat records during the concolic evaluation.

Both sides call `Driver.Passes.dcalc` with the same options, so the positions
are the same values and the join is exact rather than a guess about source
text. It checks out: of the 186 inventory positions in the files
`sara_section68` touches, 0 fail to appear as a key in the coverage map.

A **decision** is a point where control can go more than one way. A **default
group** is one only once it has an alternative --- a `definition` with at least
one `exception`. An unconditional `definition` compiles to a default group with
a single alternative and is held out, because a rule with no choice in it does
not belong in a branch-coverage denominator.

Getting that right needs the dcalc shape rather than the source. `definition
reduction equals $0` with one `exception ... under condition applies` becomes
four nested `EDefault`s, of which two are scaffolding:

```
D0 ⟨ D1 | true ⊢ D2 ⟩          the group root
D1 ⟨ D3 | false ⊢ ∅ ⟩          the exception-group wrapper
D2 ⟨      true ⊢ ⟨$0⟩ ⟩        the base alternative
D3 ⟨   applies ⊢ ⟨min …⟩ ⟩     the exception
```

Only the leaves carry law. D1's consequence is `∅` and is never evaluated; a
first version of the tool counted it and reported phantom outcomes at variable
declarations.

The standard library is inlined by `-W` like any other module, so `if`s inside
`Money.min` land in the inventory. They come out again: the coverage side
already drops them, and they are not statute.

## Reading a row

Values are read back from the compiler's own expression printer
(`compiler/shared_ast/print.ml`), so `values.py` is a parser for that printer,
and the conventions in the JSON follow from what it prints:

| Catala | printed | JSON |
|---|---|---|
| boolean | `true` | `true` |
| integer | `-12` | `-12` |
| money | `¤42.00` | `"42.00"` |
| decimal | `1.25`, `1.333…` | `"1.25"`, `"1.333"` with `"exact": false` |
| date | `\|2024-01-01\|` | `"2024-01-01"` |
| duration | `[0 years, 0 months, 3 days]` | `{"years": 0, "months": 0, "days": 3}` |
| enumeration | `MainCabin`, `Present x` | `{"cons": "MainCabin"}`, `{"cons": "Present", "payload": …}` |
| structure | `{ Item kind = …; }` | `{"struct": "Item", "fields": {…}}` |
| list | `[a; b]` | `[…]` |

Money and decimals are **strings**. A fee is a number of cents and JSON's
number is a float: `50.00` must not come back as `50.000000000000007`.

An input is named as the compiler names it — the scope's field with `_in`
appended, so `agi` appears as `agi_in`. That is the name in the output being
read back, and renaming it here would be this pipeline's invention rather than
the engine's report.

`"exact": false` marks a row containing a decimal that was printed truncated
(with `…`) at `--max-prec-digits`, so its number is not the number that was
computed. `"error"` is set instead of the outputs when the path ended in a
Catala error — a conflict between exceptions, an empty default — which is a
finding about the statute rather than a defect in the run.

Nothing that fails to parse is dropped quietly: `INDEX.json` counts it under
`unparsed`, so a change to the compiler's printer shows up as a number rather
than as a silently smaller dataset. And `raw/` keeps what was actually printed,
so the reading can always be checked against it.

## What can be explored, and what cannot

CUTECat encodes booleans, integers, decimals, money, dates, durations,
structures, enumerations, and—through the local concolic-lists patch—bounded
lists. List inputs use a symbolic length and predeclared symbolic elements;
operations over the concrete list are unrolled while retaining their symbolic
results and path constraints. The length bound is configured with
`--conc-max-list-length` and defaults to 3.

Lists may also be nested in structures or in other lists. Their symbolic
lengths and elements are registered recursively and materialised only when the
enclosing input is reconstructed. Options and sorting retain their upstream
limitations.

**SARA is reachable where the engine's arithmetic is implemented.** Its world
model is list-heavy, but §68's overall limitation and §63's standard deduction
take money, a year, a filing status and booleans. Those scopes are in the port
already, so the targets that point at them add no Catala whatsoever: the
dataset is of the statute as it is written. The local patches also implement
rational-to-integer conversion and list filtering. §1's schedule remains
excluded because selecting a tax bracket actively constructs an option.

**The airline port is now directly enterable.** Its world model is one
structure, `W.Itinerary`, whose `items` field is a list. Recursive bounded-list
inputs make that structure and all functions depending on it available to the
all-entry-points run; the smaller hand-written harnesses remain useful focused
targets.

A harness may call the port and may restate a two-line rule when the port's
version demands an itinerary; it must never contain a rule the port does not.
A dataset generated from a statute nobody wrote is worth nothing. Each harness
says in its own header which rule it exposes and what it leaves out.

## Toolchain

CUTECat needs Z3, and it is a different Catala from the one the ports are
validated against, so it gets its own opam switch. Both are built by the one
installer:

```bash
bash install_toolchain.sh cutecat     # just this part
bash install_toolchain.sh             # the whole toolchain
```

| | |
|---|---|
| `.toolchain/opam/catala` | Catala 1.2.1, the release. `catala interpret`. The ports' verdicts come from here and nowhere else. |
| `.toolchain/opam/cutecat` | the `cutecat-rebase` branch at `e9e8628`, plus Z3 4.13.3. `catala concolic`. |
| `.toolchain/src/catala-cutecat` | the checkout the second switch is pinned to |
| `.toolchain/envs/cutecat` | a conda-forge python, because Z3's build driver is `python3 scripts/mk_make.py` |

The two must not be confused. What the second one produces is a dataset, not a
judgement: it is not the compiler either port was measured with.

The installer applies the compatibility patches in `cutecat_scripts/patches/`,
including `concolic-lists.patch`, to that commit. Upstream
aborts while creating a Z3 sort for any `optional` field, even when the field
belongs to an imported declaration the selected scope never reads. The patch
treats that field as opaque, just as upstream already treats list fields.
Options are still not encoded: a scope that actively reads one remains outside
the supported target set. `INDEX.json` records the patch alongside the commit.

One wrinkle is worth knowing about, because its symptom is misleading. Z3 is
built by the *system* C++ compiler, and `.toolchain/envs/catala/bin` carries
conda's binutils — `ld`, `as`, `gcc`. A `/usr/bin/g++` that finds conda's `ld`
first links against conda's sysroot glibc and fails with `libdl.so.2:
undefined reference to '_dl_vsym@GLIBC_PRIVATE'`, which reaches Z3's build
script as the much less helpful *"C++ compiler was not found"*. The installer
therefore runs that one `opam install` with the system PATH in front and with
`CPATH`, `LIBRARY_PATH` and `LD_LIBRARY_PATH` unset.

## Files

| | |
|---|---|
| [generate_dataset.py](generate_dataset.py) | the entry point |
| [measure_coverage.py](measure_coverage.py) | how much of the port a suite executes, and which of its decisions it takes every way |
| [cutecatlib/branches.py](cutecatlib/branches.py) | the inventory, and the join against coverage |
| [branch_tool/](branch_tool/) | the Catala plugin that enumerates decision outcomes |
| [cutecatlib/coverage.py](cutecatlib/coverage.py) | native-map loading, fallback replay, union, and rule/branch accounting |
| [coverage_tool/](coverage_tool/) | the OCaml that unions the compiler's coverage dumps |
| [cutecatlib/targets.py](cutecatlib/targets.py) | what to run on, and why each one is on the list |
| [cutecatlib/run.py](cutecatlib/run.py) | the clerk project and the invocation |
| [cutecatlib/parse.py](cutecatlib/parse.py) | the `[RESULT]` stream → paths |
| [cutecatlib/values.py](cutecatlib/values.py) | one printed Catala value → JSON |
| [cutecatlib/dataset.py](cutecatlib/dataset.py) | paths → JSONL, `INDEX.json`, the report |
| [cutecatlib/paths.py](cutecatlib/paths.py) | every path, per port, and the second switch's environment |
| [cutecatlib/entrypoints.py](cutecatlib/entrypoints.py) | the census, and the wrapper scopes it writes |
| `data/catala_gold/<port>/harnesses/` | thin entry scopes into that port — the hand-written ones for the airline rules and SARA's list helpers, and `generated/` for the wrappers the census writes. They live with the port because a harness is Catala against one port and nothing else. |
| [patches/unused-option-sort.patch](patches/unused-option-sort.patch) | lets unused option-bearing declarations coexist with otherwise supported scopes |
| [patches/concolic-lists.patch](patches/concolic-lists.patch) | bounded symbolic list inputs and concolic list combinators; default maximum length 3 |
| [patches/concolic-list-stdlib.patch](patches/concolic-list-stdlib.patch) | preserves symbolic information through standard-library list helpers, `find`, and indexing |
| [patches/concolic-nested-lists.patch](patches/concolic-nested-lists.patch) | recursively materialises list fields and list-of-list inputs, with per-execution length-demand memoisation |
| [patches/concolic-coverage.patch](patches/concolic-coverage.patch) | records reachable positions once and reached positions for every generated concolic path |
| [patches/concolic-options.patch](patches/concolic-options.patch) | monomorphises polymorphic optionals into Z3 sum types and materialises `Absent` / `Present payload` inputs |
| [patches/concolic-representation-fixes.patch](patches/concolic-representation-fixes.patch) | preserves symbolic list identity and tuple/option payloads, models `sequence` and `nth_element`, and validates negated branch sites |
| [patches/unicode-identifiers.patch](patches/unicode-identifiers.patch) | accepts Unicode XID identifiers, including CJK names, in the CUTECat compiler lexer |
