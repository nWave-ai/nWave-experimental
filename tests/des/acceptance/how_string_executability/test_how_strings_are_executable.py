"""Every command prescribed by a WHAT/WHY/HOW repair is executable."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
AUDITED_ROOTS = (REPO_ROOT / "src" / "des", REPO_ROOT / "scripts")
COMMAND_PATTERN = re.compile(r"\bdes\s+([a-z][a-z0-9-]*)")
SCRIPT_PATTERN = re.compile(r"\bpython(?:3)?\s+(scripts/[A-Za-z0-9_./-]+\.py)")


def _repair_strings() -> list[str]:
    strings: list[str] = []
    for root in AUDITED_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.keyword) or node.arg not in {
                    "how",
                    "remediation",
                }:
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, str
                ):
                    strings.append(node.value.value)
    return strings


def test_repair_commands_are_live_and_the_audit_is_not_vacuous() -> None:
    repairs = _repair_strings()
    subcommands = sorted(
        {match for text in repairs for match in COMMAND_PATTERN.findall(text)}
    )
    scripts = sorted(
        {match for text in repairs for match in SCRIPT_PATTERN.findall(text)}
    )

    assert subcommands or scripts, "no executable HOW/remediation was discovered"

    for subcommand in subcommands:
        completed = subprocess.run(
            [sys.executable, "-m", "des.cli", subcommand, "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        combined = completed.stdout + completed.stderr
        assert "invalid choice" not in combined, (
            f"repair prescribes removed des subcommand {subcommand!r}: {combined}"
        )

    for relative in scripts:
        assert (REPO_ROOT / relative).is_file(), (
            f"repair prescribes missing script {relative!r}"
        )
