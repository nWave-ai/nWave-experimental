"""Build-tier test conftest -- CLI option registration.

Pytest discovers `pytest_addoption` only via conftest.py / plugins, not via
test modules. The build-tier arch tests (`test_no_per_feature_atdd_ledger_
writes.py`) need a `--src-roots` flag the AT-4 driver supplies via subprocess
invocation; this conftest registers it once.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI flags for the build-tier arch tests."""
    parser.addoption(
        "--src-roots",
        action="store",
        default=None,
        help=(
            "Comma-separated list of directory roots to scan in the "
            "per-feature ledger ban arch test. Default: src,scripts "
            "(relative to repo root). The AT-4 driver supplies a temporary "
            "source tree path here."
        ),
    )
