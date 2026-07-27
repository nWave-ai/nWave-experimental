"""Regression for techdebt.md: coverage-map-verify-cli-runtime-dup.

scripts/cli/verify_coverage_map.py used to redefine its own
``_MANDATORY_SECTIONS_IN_ORDER`` tuple, byte-for-byte identical to
``des.application.coverage_map_verify_service.MANDATORY_SECTIONS_IN_ORDER`` --
two representations of the same §5.1 section-order contract with nothing
holding them equal. The CLI now imports the tuple from the service instead of
repeating it, so the two literally cannot drift: this test pins that they are
the SAME object, not merely equal-by-value today.
"""

from __future__ import annotations

import scripts.cli.verify_coverage_map as verify_coverage_map_cli
from des.application.coverage_map_verify_service import MANDATORY_SECTIONS_IN_ORDER


def test_cli_mandatory_sections_is_the_same_object_as_the_service_core() -> None:
    """The CLI must import the tuple, not maintain its own copy."""
    assert verify_coverage_map_cli._MANDATORY_SECTIONS_IN_ORDER is (
        MANDATORY_SECTIONS_IN_ORDER
    )
