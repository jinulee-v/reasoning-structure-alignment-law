# formalization_rtf

The SARA → Catala port and its differential-testing apparatus, moved out of
`scaling_formalization_compute/` on 2026-09-01 so that the two lines of work no
longer share a tree.

| directory | what it is |
|---|---|
| [sara_scripts/](sara_scripts/) | the apparatus — two scripts and `saralib/`. **Start at [sara_scripts/README.md](sara_scripts/README.md).** |
| [sara_catala/](sara_catala/) | the port: nine IRC sections plus the world model, in Catala 1.2 |
| [data/_raw/sara/](data/_raw/sara/) | upstream SARA (Holzenberger, Blair-Stanek & Van Durme 2020), never edited |
| `sara_port/` | generated in its entirety by `generate_test_cases.py --build`, except [sara_port/reports/DISCREPANCIES.md](sara_port/reports/DISCREPANCIES.md) |
| `sara_catala_backup/` | earlier snapshots of the port |
| `.toolchain/` | userspace SWI-Prolog 10, OCaml 4.14.2 and Catala 1.2.1 |

The deviations SARA's Prolog shows against the statutes, and the port's against
the Prolog, are in [sara_scripts/DEVIATIONS.md](sara_scripts/DEVIATIONS.md).

## Running it

```bash
python3 sara_scripts/generate_test_cases.py      # build the suite
python3 sara_scripts/run_test_cases.py           # differential run -> sara_port/reports/
```

Every path is derived from this directory (`saralib.paths.ROOT` is
`saralib/`'s grandparent), so the tree can be moved again without editing
anything — see the *Moving this tree* note under
[Toolchain notes](sara_scripts/README.md#toolchain-notes) for the one thing
that is not automatic, an opam switch's compiled-in prefix.

## Rebuilding the toolchain from scratch

`.toolchain/` is gitignored. Rebuilding it is one pinned script — SWI-Prolog
10.0.0, OCaml 4.14.2, Catala 1.2.1 — and takes about an hour, nearly all of it
opam building the OCaml compiler:

```bash
bash sara_scripts/install_toolchain.sh
```
