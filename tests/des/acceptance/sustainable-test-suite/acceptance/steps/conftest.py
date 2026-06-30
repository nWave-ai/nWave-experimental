"""Shared fixtures for the slice-01 two-layer authored business-language ATs.

A conftest.py in the steps directory makes its fixtures + step definitions visible
to every scenario collected under this directory (the pytest-bdd idiomatic share).

The `driver` fixture is the ONE shared L2 concrete driver (`SlicePlanGateDriver`)
behind the `GatewayDriver` interface (DDD-3C). The L1 business-language step
definitions depend only on the interface; the fixture binds the per-language
(Python subprocess) concrete. The SAME driver instance serves both features in the
reuse scenario — authored reuse without re-authoring (DDD-2C, scenario 5).
"""

from __future__ import annotations

import pytest

from .composition import SlicePlanGateDriver


@pytest.fixture
def driver() -> SlicePlanGateDriver:
    return SlicePlanGateDriver()
