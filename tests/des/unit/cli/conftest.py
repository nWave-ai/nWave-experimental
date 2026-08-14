"""Shared fixtures and constants for charter_scaffold and dispatch CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest


#: The real `nWave/templates/expectation-charter.md` "Template" skeleton
#: (byte-faithful). Shared across all seed-mode tests to ensure consistency.
#: A single source of truth for the charter template that scaffold emits.
EXPECTATION_CHARTER_TEMPLATE = """# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


@pytest.fixture
def charter_template_seeded_repo(tmp_path: Path) -> Path:
    """Seed a temp repo with the standard expectation-charter template.

    Every `charter_scaffold` seed-mode test reads this template from
    `nWave/templates/expectation-charter.md` (repo-root-relative). This
    fixture sets up the one common asset all tests require.

    Returns the repo root (same as `tmp_path`).
    """
    template_dir = tmp_path / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        EXPECTATION_CHARTER_TEMPLATE, encoding="utf-8"
    )
    return tmp_path
