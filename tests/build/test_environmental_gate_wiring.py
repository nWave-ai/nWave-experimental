"""Arch test: the environmental e2e gate stays wired into the floor.

Slice-04 of fix-oss-environmental-e2e-gate. Residuality R3 (the
`verify_environmental_e2e` CLI not shipped = F-11 recursion) + R10 (the
feature-end cycle runs but its env-e2e sub-step is silently removed).

Statically asserts the gate is wired at TWO independent points:
  (a) Registered in `pyproject.toml` `[project.scripts]` (shipped command set).
  (b) Named within the bounded `## Feature-End Cycle` section of
      `nWave/skills/nw-deliver/SKILL.md` (the load-bearing skill-doc that
      prescribes the DELIVER feature-end orchestration step).

Both must pass; either failure means the gate has lost a wiring point and the
floor is at risk. The diagnostic names which point lost the gate so a
regression surfaces actionable repair guidance.

Grep is necessary-not-sufficient -- it cannot catch semantic reorder. The
behavioural layer is `_missing_feature_end_cycle_records` + the heartbeat
record (RES-2). This arch test is the static layer of the three-layer defense.
"""

from __future__ import annotations

from pathlib import Path

from des.install.environmental_gate_wiring import verify_environmental_gate_wiring


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"
_DELIVER_SKILL_PATH = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"


def test_environmental_gate_is_wired_into_floor() -> None:
    """Both wiring points hold: gate in shipped command set + in feature-end cycle."""
    result = verify_environmental_gate_wiring(_PYPROJECT_PATH, _DELIVER_SKILL_PATH)
    assert result.passed, result.diagnostic
