"""pytest-bdd binding for slice-02c-A-gate-event-affinity.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here -- every step routes through ``common_steps.py`` and ultimately
``composition.py`` service methods.

The slice-02c-A scenarios exercise the gate-event affinity bundle per M51
amendment (commit ``b5e647e1b``) + M56 amendment cycle 2 (commit
``fbdebd371``): six production callsites in three files migrated atomically
with their 16-row fixture-fanout (per M51 H1 verified empirically 2026-05-25).

Two BDD scenarios are bound here (AT-A1 parametrize Outline over 6 callsites
+ AT-A2 multi-feature filter forward-pin). AT-A3 (cross-feature isolation
property) is a layer-1 PBT in the sibling module
``test_slice_02c_A_cross_feature_isolation_property.py`` (per Mandate 9
layer-dependent PBT mode: PBT-full machinery only at layer 1-2).

RED-cadence (per ADR-025 + conftest._RED_SCAFFOLD_SLICES): scenarios tagged
``@slice-02c-A`` are author-ahead RED scaffolds, marked xfail strict=False
until the DELIVER A_GREEN_ATS crafter ships the 6-production-callsite +
16-fixture-fanout atomic bundle. Pre-DELIVER each AT-A1 row reds with
``AssertionError: per-feature legacy substrate unexpectedly created at ...``
(MISSING_FUNCTIONALITY -- the production source still references the legacy
per-feature path at most callsites). Post-A_GREEN every row passes
organically.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-02c-A-gate-event-affinity.feature")
