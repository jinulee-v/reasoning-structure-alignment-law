"""Support library for the two SARA differential-testing entry points.

    prolog_to_catala/sara/generate_test_cases.py   builds .port/sara/test_cases/
    prolog_to_catala/sara/run_test_cases.py        runs them and reports discrepancies

Nothing here is meant to be run directly.  The modules are:

    paths        every filesystem location and both toolchain environments
    grounding    SARA's 376 case files -> JSON world models
    value_types  the atom/string reading of every value, recovered per case
    prolog       render a world model as Prolog; run it; collect coverage
    catala_emit  render a world model as a standalone Catala program
    coverage     build the instrumented statutes; map a branch point to source
    generate     the three ways a test case is produced
    traces       both systems' execution traces, rendered for a human

Grouping and the markdown report live in `run_test_cases.py` itself, since
nothing else has any use for them.
"""
