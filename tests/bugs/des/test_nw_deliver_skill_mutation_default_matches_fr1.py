"""Regression: nw-deliver/SKILL.md must not bake mutation testing in as a
default per-feature phase, contradicting CLAUDE.md's FR-1 deprecation.

OBSERVED (2026-07-26): CLAUDE.md § 'Mutation Testing Strategy' (STANDING,
FR-1, 2026-07-04) states mutation testing is DEPRECATED, REMOVED from the
velocity-v2 methodology, that `.nwave/des-config.json` keeps
`mutation_enabled=false`, and that mutmut is NOT part of any per-feature or
nightly gate -- do not run it as a default step. Yet nw-deliver/SKILL.md's
Tier-1 MANDATORY output template listed 'mutation' as an always-emitted
per-phase quality gate alongside refactor/review/integrity, and its Rigor
Profile Integration table read '`mutation_enabled` | If false, skip Phase 5
regardless of mutation strategy in CLAUDE.md' -- i.e. the skill's default
assumption was that Phase 5 (mutation) RUNS unless explicitly toggled off,
the inverse of the standing default (off unless explicitly opted in).
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILL_PATH = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"


def _tier1_quality_gates_line(text: str) -> str:
    for line in text.splitlines():
        if "Quality gates" in line and "refactor" in line:
            return line
    raise AssertionError("Tier-1 'Quality gates' bullet not found in nw-deliver skill")


def _mutation_enabled_row(text: str) -> str:
    for line in text.splitlines():
        if "`mutation_enabled`" in line:
            return line
    raise AssertionError("mutation_enabled rigor-table row not found")


def test_tier1_quality_gates_does_not_list_mutation_as_unconditional() -> None:
    line = _tier1_quality_gates_line(_SKILL_PATH.read_text(encoding="utf-8"))
    assert "mutation, integrity)" not in line, (
        "mutation must not be listed as an unconditional Tier-1 quality "
        "gate alongside refactor/review/integrity -- it is opt-in only "
        "per CLAUDE.md FR-1"
    )


def test_mutation_enabled_row_states_default_is_skip() -> None:
    row = _mutation_enabled_row(_SKILL_PATH.read_text(encoding="utf-8"))
    assert "deprecated" in row.lower()
    assert "default is `false`" in row or "config default is `false`" in row


def test_claude_md_still_declares_mutation_deprecated_fixture_sanity() -> None:
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Mutation Testing Strategy" in claude_md
    assert "DEPRECATED" in claude_md
