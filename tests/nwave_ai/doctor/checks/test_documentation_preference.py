"""Doctor must not approve a preference that prevents wave entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from nwave_ai.doctor.checks.density import DensityCheck
from nwave_ai.doctor.context import DoctorContext


@pytest.mark.parametrize(
    ("document", "field"),
    [
        ({"documentation": {"density": "unsupported"}}, "density"),
        ({"documentation": {"expansion_prompt": "unsupported"}}, "expansion_prompt"),
        ({"rigor": {"profile": "unsupported"}}, "rigor.profile"),
        ({"rigor": {"profile": 3}}, "rigor.profile"),
        ({"rigor": []}, "rigor"),
        ({"documentation": []}, "documentation"),
    ],
)
def test_invalid_active_preference_fails_without_rewriting_config(
    tmp_path: Path, document: dict, field: str
) -> None:
    config = tmp_path / ".nwave" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps(document))
    original = config.read_bytes()

    result = DensityCheck().run(DoctorContext(home_dir=tmp_path))

    assert result.passed is False
    assert result.error_code is not None
    assert str(config) in result.remediation
    assert field in result.message
    assert config.read_bytes() == original


def test_valid_full_preference_can_be_repaired_after_a_failed_check(
    tmp_path: Path,
) -> None:
    config = tmp_path / ".nwave" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"documentation": {"density": "unsupported"}}))
    check = DensityCheck()
    context = DoctorContext(home_dir=tmp_path)
    assert check.run(context).passed is False

    config.write_text(json.dumps({"documentation": {"density": "full"}}))
    repaired = config.read_bytes()

    assert check.run(context).passed is True
    assert config.read_bytes() == repaired
