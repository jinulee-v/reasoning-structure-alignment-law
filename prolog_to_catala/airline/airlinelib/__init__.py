"""The DeonticBench *airline* -> Catala port apparatus.

Two entry points, `generate_test_cases.py` and `run_test_cases.py`, and this
package between them.  The layout mirrors `prolog_to_catala/sara/saralib`, but the
corpus forces one structural difference: DeonticBench ships no shared statute
formalization, only a self-contained Prolog program per case, so the oracle the
port is measured against has to be written and then validated against all 300
of them.  See `prolog_to_catala/airline/README.md`.
"""
