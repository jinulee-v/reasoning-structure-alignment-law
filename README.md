# formalization_rtf

The SARA → Catala port and its differential-testing apparatus, moved out of
`scaling_formalization_compute/` on 2026-09-01 so that the two lines of work no
longer share a tree.

Two ports now live here, built with the same apparatus and sharing one
toolchain: **SARA** (nine sections of the US Internal Revenue Code) and
**DeonticBench *airline*** (the published American Airlines checked-bag policy).

Everything generated lives under `.port/`, which is gitignored in its entirety:
delete any of it and the scripts put it back.

| directory | what it is |
|---|---|
| [prolog_to_catala/sara/](prolog_to_catala/sara/) | SARA's apparatus — two scripts and `saralib/`. **Start at [prolog_to_catala/sara/README.md](prolog_to_catala/sara/README.md).** |
| [data/catala_gold/sara/](data/catala_gold/sara/) | the SARA port: nine IRC sections plus the world model, in Catala 1.2, and the `harnesses/` that enter it |
| [data/prolog/sara/](data/prolog/sara/) | upstream SARA's Prolog — statutes and 376 cases (Holzenberger, Blair-Stanek & Van Durme 2020), never edited |
| [data/raw/sara/](data/raw/sara/) | the statute prose, section by section: what a formalization is written against |
| `.port/sara/` | generated in its entirety by `generate_test_cases.py --build`, except [.port/sara/reports/DISCREPANCIES.md](.port/sara/reports/DISCREPANCIES.md) |
| [prolog_to_catala/airline/](prolog_to_catala/airline/) | the airline apparatus. **Start at [prolog_to_catala/airline/README.md](prolog_to_catala/airline/README.md).** |
| [data/catala_gold/airline/](data/catala_gold/airline/) | the airline port: the bag-fee policy plus its world model, and the `harnesses/` that enter it |
| [data/prolog/airline/](data/prolog/airline/) | upstream DeonticBench *airline* — 300 per-case programs (Dou et al. 2026), never edited |
| [data/raw/airline/](data/raw/airline/) | the published bag-fee rules, verbatim |
| [data/catala_gold/NSW_community_gaming/](data/catala_gold/NSW_community_gaming/) | Catala's NSW community-gaming examples and upstream tests |
| [data/raw/NSW_community_gaming/](data/raw/NSW_community_gaming/) | the governing NSW community-gaming prose extracted from the literate Catala sources |
| [data/catala_gold/aides_logement/](data/catala_gold/aides_logement/) | Catala's French housing-benefit formalization and upstream tests |
| [data/raw/aides_logement/](data/raw/aides_logement/) | the French housing-benefit source prose extracted from the literate Catala sources |
| [data/catala_gold/allocations_familiales/](data/catala_gold/allocations_familiales/) | Catala's French family-benefit formalization and upstream tests |
| [data/raw/allocations_familiales/](data/raw/allocations_familiales/) | the French family-benefit source prose extracted from the literate Catala sources |
| `.port/airline/` | generated in its entirety by `prolog_to_catala/airline/generate_test_cases.py` — last run 23,906/23,906 agree |
| [cutecat_scripts/](cutecat_scripts/) | the concolic pipeline: CUTECat's execution paths through either port, as a dataset of inputs and outputs. **Start at [cutecat_scripts/README.md](cutecat_scripts/README.md).** |
| `.port/sara_cutecat/`, `.port/airline_cutecat/` | generated in their entirety by `cutecat_scripts/generate_dataset.py`, one tree per port |
| `sara_catala_backup/` | earlier snapshots of the SARA port |
| `.toolchain/` | userspace SWI-Prolog 10, OCaml 4.14.2 and Catala 1.2.1, shared by both — plus a second switch carrying CUTECat |

The deviations each corpus's Prolog shows against its statute, and each port's
against that Prolog, are in
[prolog_to_catala/sara/DEVIATIONS.md](prolog_to_catala/sara/DEVIATIONS.md) and
[prolog_to_catala/airline/DEVIATIONS.md](prolog_to_catala/airline/DEVIATIONS.md).

The two corpora differ in one way that shapes the second tree. SARA ships a
single Prolog formalization of its statutes; DeonticBench ships **none** — each
of its 300 airline cases carries a self-contained program with the rules and
that case's facts together. So the airline port has to write the shared oracle
itself and then earn it, against all 300 per-case programs, before the Catala
can be measured against it. DeonticBench's `uscis-aao` domain was downloaded
and measured for the same treatment and dropped: its 242 programs share no
formalization at all (mean pairwise predicate-vocabulary overlap 0.021), so
there is nothing there to write once and test against.

## Running it

```bash
python3 prolog_to_catala/sara/generate_test_cases.py         # build the suite
python3 prolog_to_catala/sara/run_test_cases.py              # differential run -> .port/sara/reports/

python3 prolog_to_catala/airline/generate_test_cases.py      # the airline suite
python3 prolog_to_catala/airline/run_test_cases.py           # -> .port/airline/reports/

python3 cutecat_scripts/generate_dataset.py         # concolic paths -> .port/<port>_cutecat/
python3 cutecat_scripts/measure_coverage.py         # statement and branch coverage
```

Every path is derived from this directory (`saralib.paths.ROOT` and
`airlinelib.paths.ROOT` are each their package's third parent), so the tree can
be moved again without editing anything — see the *Moving this tree* note under
[Toolchain notes](prolog_to_catala/sara/README.md#toolchain-notes) for the one thing
that is not automatic, an opam switch's compiled-in prefix.

## Rebuilding the toolchain from scratch

`.toolchain/` is gitignored. Rebuilding it is one pinned script — SWI-Prolog
10.0.0, OCaml 4.14.2, Catala 1.2.1, and CUTECat with Z3 4.13.3 — and takes
about two hours, most of it opam building compilers:

```bash
bash install_toolchain.sh
```

It takes a comma-separated list of stages (`swipl`, `ocaml`, `catala`,
`cutecat`), so a piece of it can be rerun on its own:

```bash
bash install_toolchain.sh cutecat
```

The concolic engine lands on a **second** opam switch, `.toolchain/opam/cutecat`,
and not in the one the ports are validated against: it is a different Catala,
built from a branch. See
[cutecat_scripts/README.md](cutecat_scripts/README.md#toolchain).
