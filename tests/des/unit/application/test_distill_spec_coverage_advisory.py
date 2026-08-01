"""P3.1/P3.2 — the DISTILL gate-out spec-coverage ADVISORY dispatch.

Planted-defect done-currency for wiring the (already-built, pinned)
`verify_spec_coverage` gate into the DISTILL gate-out as ADVISORY: it must
FIRE on the feature's checklist + AT corpus, surface uncovered rows LOUD
(naming the mandatory categories), and NEVER veto (always exit 0) — an
armed gate that could block a mandatory wave is out of scope; the whole
point is a non-blocking signal that no requirement is silently uncovered.

Hermetic: a temp project tree with a requirement-checklist + an AT dir; the
three transitions the smoke-proof established (uncovered -> advisory naming
the security row; covered -> silent pass; no checklist -> advisory-skip).
"""

from __future__ import annotations

import json
from pathlib import Path

from des.application.subagent_stop_service import spec_coverage_gate_stdout


_FID = "demo-feature"


def _feature(tmp_path: Path) -> tuple[Path, Path, Path]:
    dist = tmp_path / "docs" / "feature" / _FID / "distill"
    dist.mkdir(parents=True)
    checklist = dist / "requirement-checklist.md"
    checklist.write_text(
        "| ID | Requirement | Category |\n|----|----|----|\n"
        "| R1 | core booking works | functional |\n"
        "| R2 | client identity rejected server-side | security |\n",
        encoding="utf-8",
    )
    at = dist / "test_demo.py"
    return tmp_path, checklist, at


def _run(root: Path) -> tuple[int, dict]:
    code, out = spec_coverage_gate_stdout(root, _FID)
    return code, json.loads(out)


def _write_at(at: Path, body: str) -> None:
    """Head-tag the fixture AT with '@feature-{_FID}' -- fix-coverage-claim-
    names-a-feature: attribution requires the file to self-identify (a
    '# @feature-<id>' comment), never a bare marker anywhere on disk."""
    at.write_text(f"# @feature-{_FID}\n{body}", encoding="utf-8")


def test_uncovered_security_row_is_surfaced_advisory_not_veto(tmp_path: Path) -> None:
    root, _checklist, at = _feature(tmp_path)
    _write_at(at, "def test_b():\n    assert True\n")  # covers nothing
    code, verdict = _run(root)
    assert code == 0, "advisory NEVER vetoes a mandatory wave"
    assert verdict["verdict"] == "advisory"
    blob = json.dumps(verdict)
    assert (
        "R2" in blob and "security" in blob.lower()
    )  # the eval's silent-absence class
    assert "security" in verdict["mandatory_categories_uncovered"]


def test_full_coverage_is_a_silent_pass(tmp_path: Path) -> None:
    root, _checklist, at = _feature(tmp_path)
    # markers INSIDE the test body (the gate's convention)
    _write_at(
        at, "def test_b():\n    # covers: R1\n    # covers: R2\n    assert True\n"
    )
    code, verdict = _run(root)
    assert code == 0
    assert verdict["verdict"] == "pass"


def test_no_checklist_is_advisory_skip_composition_proceeds(tmp_path: Path) -> None:
    root, checklist, at = _feature(tmp_path)
    _write_at(at, "def test_b():\n    assert True\n")
    checklist.unlink()  # unarmed — no checklist authored yet
    code, verdict = _run(root)
    assert code == 0, "no checklist -> advisory-skip, the composition does NOT halt"
    assert verdict["verdict"] == "advisory"
    assert "not yet armed" in verdict["reason"]
