"""Every `# HANDOFF: <id> ...` code comment must have a matching row in
`HANDOFFS.md` -- a cross-wave instruction left as a bare comment is not an
executable constraint (no gate reads prose), which is exactly how D70
slice-02's `ledger_root` wiring stayed unread through DELIVER: the DESIGN
comment named the fix precisely, DELIVER graduated the scaffold it was
attached to, and nothing ever checked the comment got honored -- caught only
by Vera driving the real CLI, not by any of the 34 green unit-level ATs.

THE INVARIANT. Every `# HANDOFF: <id>` marker anywhere under `src/`,
`scripts/`, `tests/` must have a row in `HANDOFFS.md` keyed by the same
`<id>`. This does NOT verify the handoff was actually performed (that stays
a human/reviewer judgment, named explicitly in `HANDOFFS.md`'s own header) --
it only guarantees the marker can never be invisible: an unregistered marker
fails the build loudly, at authoring time, instead of surviving silently
until the next examine happens to walk that exact code path.

No allowlist: the convention ships with zero pre-existing usage (verified
2026-08-02, `grep -rn '# HANDOFF:' src/ scripts/ tests/` -> no hits), so
there is no legacy population to grandfather. Every marker from here on is
NEW and must be registered from the moment it is written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERIMETER = ("src", "scripts", "tests")
HANDOFFS_FILE = PROJECT_ROOT / "HANDOFFS.md"

# `# HANDOFF: <id> <free text>` -- id is the same kebab-case-ish token shape
# used elsewhere in this repo's piles (defects.md/techdebt.md item ids).
_MARKER_RE = re.compile(r"#\s*HANDOFF:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\b")

# `- [ ] <id>: ...` / `- [x] <id>: ...` row grammar, mirrors defects.md/techdebt.md.
_REGISTRY_ROW_RE = re.compile(r"^- \[[ x]\] ([A-Za-z0-9][A-Za-z0-9_-]*):", re.MULTILINE)


def _markers_in_tree() -> dict[str, list[str]]:
    """Map marker id -> list of ``file:line`` sites it was found at."""
    found: dict[str, list[str]] = {}
    for root_name in PERIMETER:
        root = PROJECT_ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                match = _MARKER_RE.search(line)
                if match is None:
                    continue
                rel = path.relative_to(PROJECT_ROOT)
                found.setdefault(match.group(1), []).append(f"{rel}:{line_no}")
    return found


def _registered_ids() -> set[str]:
    if not HANDOFFS_FILE.is_file():
        return set()
    text = HANDOFFS_FILE.read_text(encoding="utf-8")
    return set(_REGISTRY_ROW_RE.findall(text))


@pytest.mark.fast_gate
def test_every_handoff_marker_has_a_registry_row() -> None:
    markers = _markers_in_tree()
    registered = _registered_ids()
    unregistered = {
        mid: sites for mid, sites in markers.items() if mid not in registered
    }
    assert not unregistered, (
        "the following `# HANDOFF:` markers have no matching row in "
        f"{HANDOFFS_FILE.relative_to(PROJECT_ROOT)} -- a cross-wave "
        "instruction left as a bare comment is invisible to every gate "
        "(this IS the D70 slice-02 defect class): "
        f"{unregistered}. Add a row per HANDOFFS.md's own grammar for each "
        "id, or remove the marker if the handoff was already completed."
    )


@pytest.mark.fast_gate
def test_handoffs_file_exists_and_documents_the_row_grammar() -> None:
    """A registry nobody can find is as invisible as no registry at all."""
    assert HANDOFFS_FILE.is_file(), f"{HANDOFFS_FILE} must exist at repo root"
    text = HANDOFFS_FILE.read_text(encoding="utf-8")
    assert "Row grammar" in text
    assert "opened_by=" in text
