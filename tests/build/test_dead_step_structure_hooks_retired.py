"""Regression -- the dead 14-phase step-structure TDD hooks stay retired.

Hook-audit fix 2026-07-29 (Difetto B). `scripts/hooks/nwave-step-structure-
validator.py` and `scripts/hooks/nwave-tdd-validator.py` enforced a 14-phase
TDD contract (PREPARE, RED_ACCEPTANCE, RED_UNIT, ..., REFACTOR_L1..L4, ...)
superseded TWICE by the current canon (5-phase legacy, then the 3-phase
RED/GREEN/COMMIT of ADR-025). Zero `steps/NN-NN.json` files were tracked
anywhere in the repo -- the data model they validated had no producer -- and
their remediation message pointed at `/nw-split`, a command that does not
exist. Deleted rather than realigned: nothing produces their input today.

This guards against silent reintroduction: a future edit re-adding the files
or their `.pre-commit-config.yaml` wiring without also fixing (or dropping)
the `/nw-split` pointer would resurrect an actively-wrong remediation.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_RETIRED_SCRIPTS = (
    "scripts/hooks/nwave-step-structure-validator.py",
    "scripts/hooks/nwave-tdd-validator.py",
)

_RETIRED_HOOK_IDS = (
    "nwave-step-structure-validation",
    "nwave-tdd-phase-validation",
)


def test_retired_scripts_are_absent_from_disk() -> None:
    """The two dead 14-phase validator scripts must not be resurrected."""
    present = [p for p in _RETIRED_SCRIPTS if (PROJECT_ROOT / p).exists()]
    assert not present, (
        "WHAT: a retired 14-phase step-structure hook script is back on disk.\n"
        "WHY: it validates steps/NN-NN.json, a data model with zero producers "
        "in this repo (git ls-files finds none), and its remediation pointed "
        "at the nonexistent /nw-split command.\n"
        "HOW: if step-file validation is genuinely needed again, author it "
        "fresh against the CURRENT 3-phase RED/GREEN/COMMIT canon (ADR-025) "
        "and a real remediation command -- do not resurrect the old file.\n"
        f"    {present}"
    )


def test_precommit_config_no_longer_wires_the_retired_hooks() -> None:
    """`.pre-commit-config.yaml` must not re-wire either retired hook id."""
    config_text = (PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    wired = [
        hook_id for hook_id in _RETIRED_HOOK_IDS if f"id: {hook_id}" in config_text
    ]
    assert not wired, (
        "WHAT: .pre-commit-config.yaml re-wires a retired 14-phase hook id.\n"
        "WHY/HOW: see test_retired_scripts_are_absent_from_disk.\n"
        f"    {wired}"
    )


def test_no_active_hook_points_operators_at_nonexistent_nw_split() -> None:
    """No live hook script (git or Claude-Code lifecycle) may cite `/nw-split`.

    Scoped to the two live hook surfaces only (`scripts/hooks/`,
    `src/des/adapters/drivers/hooks/`) -- historical/archived/analysis docs are
    allowed to mention a command that once existed; a live remediation message
    pointing at a command that does not exist is the actual defect.
    """
    live_hook_dirs = (
        PROJECT_ROOT / "scripts" / "hooks",
        PROJECT_ROOT / "src" / "des" / "adapters" / "drivers" / "hooks",
    )
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for hook_dir in live_hook_dirs
        for path in hook_dir.rglob("*.py")
        if "/nw-split" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "WHAT: a live hook script's message cites the nonexistent /nw-split "
        "command.\n"
        "WHY: pointing an operator at a command that does not exist is an "
        "actively wrong HOW, worse than no HOW at all.\n"
        "HOW: point at a real command, or drop the reference.\n"
        f"    {offenders}"
    )
