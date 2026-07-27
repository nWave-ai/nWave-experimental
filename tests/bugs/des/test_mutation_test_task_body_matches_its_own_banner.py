"""Regression: nWave/tasks/nw/mutation-test.md's BODY must match its own
FR-1 deprecation banner, and must not hand off to a nonexistent develop.md.

OBSERVED (2026-07-26): the file carries a correct FR-1 deprecation banner at
the top (mutation_enabled=false, opt-in only, not a default step) but the
body was never updated to match. Quality Gate section: 'Python projects
require mutation testing; all skips need documented justification' -- the
pre-FR-1 mandatory framing, directly contradicting the banner. Next Wave
section: 'Handoff To: Phase 8 - Finalize (orchestrator continues develop.md
workflow)' -- develop.md does not exist anywhere in the repo (grepped, zero
hits), and the phase number is also wrong against the current SSOT
(nWave/tasks/nw/deliver.md: Phase 7 = Finalize, Phase 8 = Retrospective,
Phase 5 = Mutation Testing).
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_TASK_PATH = _REPO_ROOT / "nWave" / "tasks" / "nw" / "mutation-test.md"


def test_develop_md_still_does_not_exist_fixture_sanity() -> None:
    assert not list(_REPO_ROOT.rglob("develop.md"))


def test_quality_gate_no_longer_states_mutation_is_mandatory() -> None:
    text = _TASK_PATH.read_text(encoding="utf-8")
    assert "require mutation testing" not in text


def test_next_wave_section_does_not_hand_off_to_develop_md() -> None:
    text = _TASK_PATH.read_text(encoding="utf-8")
    assert "continues develop.md workflow" not in text
    assert "Handoff To" not in text
    assert "Phase 8 - Finalize" not in text


def test_body_and_banner_agree_mutation_is_opt_in_only() -> None:
    text = _TASK_PATH.read_text(encoding="utf-8")
    assert "DEPRECATED" in text
    assert "skipped by default" in text.lower() or "skip conditions" in text.lower()
