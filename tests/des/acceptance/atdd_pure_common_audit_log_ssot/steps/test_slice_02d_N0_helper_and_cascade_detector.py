"""pytest-bdd binding for slice-02d-N0-helper-and-cascade-detector.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here -- every step routes through ``common_steps.py`` and ultimately
``composition.py`` service methods.

The slice-02d-N0 scenarios exercise the coordinated fixture migration helper
signature evolution per M40 architect design (commit ``8afa698df``):
``seed_required_feature_end_records`` gains a ``feature_id: str | None = None``
keyword-only parameter, dual-shape backward-compat preserved (legacy ledger-
bound writes unchanged when ``feature_id`` omitted; singleton-shape forward to
``ledger.append_*(feature_id=...)`` when supplied). Foreground binding
completion (M43 BG agent ran out of context mid-edit) -- AT-COMPLETENESS
contract requires executable scaffolding at DISTILL phase, not just .feature
+ composition stubs.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-02d-N0-helper-and-cascade-detector.feature")
