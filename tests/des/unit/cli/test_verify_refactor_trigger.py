"""P1.3 signal-driven refactor trigger — the observed proofs, pinned.

These tests ARE the evolution-plan P1.3 done-currency, made permanent: the
gate was proven by execution against a planted defect of its target class
(the SSOT violation — the same seat-status Enum redeclared in two touched
modules, plus a duplicated multi-line block), a clean well-factored case,
and the degrade-LOUD no-arm case. Deleting the gate's logic turns these RED.

Arm assertions check the prefix only ("ast-fallback" / "none") so the pins
stay hermetic whether or not a ``tsunami`` executable happens to be on the
machine's PATH (the suffix honestly reports the probe either way).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_refactor_trigger import main


_PLANTED_TEMPLATE = """from enum import Enum


class SeatStatus(Enum):
    FREE = "free"
    HELD = "held"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


def {func}(seat_id: str) -> dict:
    if not seat_id:
        raise ValueError("seat_id required")
    record = {{"seat": seat_id}}
    record["status"] = SeatStatus.HELD.name
    record["retries"] = len(seat_id) % 3
    return record
"""


def _verdict(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return json.loads(capsys.readouterr().out.splitlines()[0])  # type: ignore[no-any-return]


def test_clean_module_is_clean_with_arm_declared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE proof: a well-factored module -> exit 0, arm declared."""
    (tmp_path / "pricing.py").write_text(
        '"""Well-factored small module."""\n'
        "\n"
        "TAX_RATE = 0.22\n"
        "\n"
        "\n"
        "def net_price(gross: float) -> float:\n"
        "    return gross / (1 + TAX_RATE)\n"
        "\n"
        "\n"
        "def tax_amount(gross: float) -> float:\n"
        "    return gross - net_price(gross)\n"
    )

    assert main(["--repo", str(tmp_path), "--files", "pricing.py"]) == 0
    verdict = _verdict(capsys)
    assert verdict["event"] == "RefactorTriggerClean"
    assert str(verdict["arm"]).startswith("ast-fallback")
    assert verdict["findings"] == []


def test_planted_ssot_violation_fires_naming_both_sites(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: seat-status Enum redeclared in two touched modules
    plus a duplicated block -> exit 1; findings name BOTH files with line."""
    (tmp_path / "booking.py").write_text(_PLANTED_TEMPLATE.format(func="reserve"))
    (tmp_path / "checkout.py").write_text(_PLANTED_TEMPLATE.format(func="confirm"))

    code = main(
        ["--repo", str(tmp_path), "--files", "booking.py", "--files", "checkout.py"]
    )

    assert code == 1
    verdict = _verdict(capsys)
    assert verdict["event"] == "RefactorTriggerFired"
    assert str(verdict["arm"]).startswith("ast-fallback")
    findings = verdict["findings"]
    assert isinstance(findings, list)
    classes = {f["class"] for f in findings}
    assert "parallel_enum_definitions" in classes
    assert "duplicated_code" in classes
    files_named = {(f["file"], f["class"]) for f in findings}
    booking = str(tmp_path / "booking.py")
    checkout = str(tmp_path / "checkout.py")
    assert (booking, "parallel_enum_definitions") in files_named
    assert (checkout, "parallel_enum_definitions") in files_named
    assert (booking, "duplicated_code") in files_named
    assert (checkout, "duplicated_code") in files_named
    assert all(isinstance(f["line"], int) and f["line"] > 0 for f in findings)


def test_parallel_enum_detected_without_textual_duplication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The parallel-enum detector specifically: 4/5 member overlap across
    textually DIFFERENT enums (no duplicated block) -> the only finding
    class is parallel_enum_definitions, at both definition sites."""
    (tmp_path / "seats_a.py").write_text(
        "from enum import Enum\n"
        "\n"
        "\n"
        "class SeatStatus(Enum):\n"
        '    FREE = "F"\n'
        '    HELD = "H"\n'
        '    BOOKED = "B"\n'
        '    CANCELLED = "C"\n'
        '    BLOCKED = "X"\n'
    )
    (tmp_path / "seats_b.py").write_text(
        "from enum import IntEnum\n"
        "\n"
        "\n"
        "class SeatState(IntEnum):\n"
        "    FREE = 11\n"
        "    HELD = 12\n"
        "    BOOKED = 13\n"
        "    CANCELLED = 14\n"
        "    EXPIRED = 15\n"
    )

    code = main(
        ["--repo", str(tmp_path), "--files", "seats_a.py", "--files", "seats_b.py"]
    )

    assert code == 1
    verdict = _verdict(capsys)
    findings = verdict["findings"]
    assert isinstance(findings, list)
    assert {f["class"] for f in findings} == {"parallel_enum_definitions"}
    assert {f["file"] for f in findings} == {
        str(tmp_path / "seats_a.py"),
        str(tmp_path / "seats_b.py"),
    }
    briefs = {str(f["brief"]) for f in findings}
    assert any("SeatStatus" in b and "SeatState" in b for b in briefs)
    assert all(f["line"] == 4 for f in findings)


def test_non_python_file_without_arm_degrades_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DEGRADE proof: a .ts file has no assessing arm -> exit 2 with
    what/why/how and the arm declared — NEVER a silent zero-findings."""
    (tmp_path / "app.ts").write_text('export const seatStatus = "free";\n')

    assert main(["--repo", str(tmp_path), "--files", "app.ts"]) == 2
    verdict = _verdict(capsys)
    assert verdict["event"] == "RefactorTriggerIndeterminate"
    assert all(k in verdict for k in ("what", "why", "how", "arm"))
    assert str(verdict["arm"]).startswith("none")


def test_no_input_degrades_loud_never_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Neither --files nor --diff-base -> exit 2 LOUD, what/why/how."""
    assert main(["--repo", str(tmp_path)]) == 2
    verdict = _verdict(capsys)
    assert verdict["event"] == "RefactorTriggerIndeterminate"
    assert all(k in verdict for k in ("what", "why", "how", "arm"))
