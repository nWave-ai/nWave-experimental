"""Regression: nw-distill-red-scaffolding SKILL.md must cite a real module.

OBSERVED (2026-07-26): the skill stated 'Red Gate Snapshot
(`src/des/application/red_gate_snapshot.py`) classifies failures by error
type', but neither that file nor a ``RedGateSnapshot`` class exists anywhere
in ``src/`` -- confirmed by both a direct path check and a repo-wide grep for
the class name, zero hits outside the skill itself. The RED-vs-BROKEN
classification the skill describes (AssertionError is RED, NotImplementedError
/ ImportError is BROKEN) is real and lives in
``src/des/cli/verify_red_green.py`` -- CLAUDE.md itself names that file as
'the canonical done-right example' for GDP-8 -- under a different module name
and without a ``RedGateSnapshot`` class. An agent reading the skill and going
to inspect or extend the cited module hit a bare file-not-found.

This test pins the fix: the skill cites the real classifier file, and the
fabricated path is gone.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_PATH = (
    _REPO_ROOT / "nWave" / "skills" / "nw-distill-red-scaffolding" / "SKILL.md"
)
_REAL_CLASSIFIER = _REPO_ROOT / "src" / "des" / "cli" / "verify_red_green.py"
_FABRICATED_MODULE = _REPO_ROOT / "src" / "des" / "application" / "red_gate_snapshot.py"


def test_the_fabricated_module_still_does_not_exist_fixture_sanity() -> None:
    """Fixture sanity: the module the skill used to cite is genuinely absent."""
    assert not _FABRICATED_MODULE.exists()


def test_skill_no_longer_cites_the_fabricated_module() -> None:
    text = _SKILL_PATH.read_text(encoding="utf-8")
    assert "red_gate_snapshot.py" not in text
    assert "Red Gate Snapshot" not in text


def test_skill_cites_the_real_classifier_that_exists_on_disk() -> None:
    assert _REAL_CLASSIFIER.is_file(), (
        "fixture sanity: the real classifier module must exist for the "
        "citation to be true"
    )
    text = _SKILL_PATH.read_text(encoding="utf-8")
    assert "src/des/cli/verify_red_green.py" in text
