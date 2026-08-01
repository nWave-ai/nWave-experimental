"""An unregistered smoke target is rejected before a release lane starts.

Copilot is a supported installer platform and must never be used as a proxy for
an unknown target.  This layer-1 contract protects the actual failure mode: a
matrix typo or an unregistered future CLI must fail loudly, rather than create
a misleading green release-smoke lane.
"""

from __future__ import annotations

import pytest

from scripts.release.rc_smoke.contracts import UnsupportedToolError, tool_contract


def test_unregistered_smoke_target_is_rejected_with_a_readable_diagnostic() -> None:
    """A release engineer sees why an unknown target cannot start a lane."""
    with pytest.raises(UnsupportedToolError, match="unsupported tool.*unregistered-cli"):
        tool_contract("unregistered-cli")
