"""Public nWave prose must use the installed ``des`` command boundary."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_NWAVE_ROOT = PROJECT_ROOT / "nWave"
INTERNAL_MODULE_INVOCATION = re.compile(r"\bpython3?\s+-m\s+des\.cli\b")


def test_public_markdown_never_invokes_internal_des_python_modules() -> None:
    """Shipped instructions call ``des`` rather than guessing an interpreter."""
    violations = [
        f"{path.relative_to(PROJECT_ROOT)}:{line_number}: {line.strip()}"
        for path in sorted(PUBLIC_NWAVE_ROOT.rglob("*.md"))
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if INTERNAL_MODULE_INVOCATION.search(line)
    ]

    assert not violations, (
        "Public nWave instructions bypass the installed `des` command boundary:\n"
        + "\n".join(violations)
    )
