"""Retired documentation preferences cannot make an installed runtime unhealthy."""

from __future__ import annotations

import json
from pathlib import Path

from nwave_ai.doctor.checks.density import DensityCheck
from nwave_ai.doctor.context import DoctorContext


def test_invalid_legacy_preference_is_nonblocking_but_visible(tmp_path: Path) -> None:
    global_dir = tmp_path / ".nwave"
    global_dir.mkdir()
    (global_dir / "config.json").write_text(
        json.dumps({"documentation": {"expansion_prompt": "unsupported"}})
    )

    result = DensityCheck().run(DoctorContext(home_dir=tmp_path))

    assert result.passed is True
    assert "ignored" in result.message
    assert "diagnostic-only" in result.message
    assert "unsupported" in result.message
