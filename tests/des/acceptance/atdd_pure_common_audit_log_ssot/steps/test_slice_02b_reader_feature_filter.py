"""pytest-bdd binding for slice-02b-reader-feature-filter.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here -- every step routes through ``common_steps.py`` and ultimately
``composition.py`` service methods.

The slice-02b scenarios exercise the post-migration reader API surface that
slice-02 cascades into: the three aggregate readers (`verified_slices`,
`feature_end_events`, `environmental_e2e_events`) gain an optional
`feature_id=` keyword-only parameter so that singleton-shape callers can
preserve feature-scoped isolation. The CLI regression-pin (AT-3) closes the
F-DELIVER-INTEGRITY-LEDGER-TARGETING class at the operator-facing surface.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-02b-reader-feature-filter.feature")
