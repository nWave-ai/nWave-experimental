"""pytest-bdd binding for slice-02-caller-migration.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here -- every step routes through ``common_steps.py`` and ultimately
``composition.py`` service methods.

The slice-02 scenarios exercise the eleven caller-migration paths via the
production driving ports (CLI subprocess or in-process composition-root
invocation, per caller), the in-tree per-feature-ledger ban arch test, and
the regression-pin on the legacy dual-shape contract.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-02-caller-migration.feature")
