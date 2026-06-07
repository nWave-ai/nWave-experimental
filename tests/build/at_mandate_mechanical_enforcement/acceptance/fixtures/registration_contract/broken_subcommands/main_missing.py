"""GOLDEN FIXTURE leaf — a registered module that imports but exposes no ``main``.

This is the planted-violation corpus for the registration contract (the recall
half). The module imports cleanly, so a naive "can I import the module?" check
passes — but the dispatcher's contract is stronger: the row must ALSO expose a
callable ``main`` entry. This module deliberately has none, so a dropped or
half-wired registration cannot pass green.

A registration-contract gate that cannot catch this gap is itself
testing-theater (ADR-TEST-002 D-E golden-fixture-AT meta-rule).
"""

from __future__ import annotations


# GAP: no ``main`` callable defined — the planted registration breach.
SOMETHING_ELSE = "not the entry point"
