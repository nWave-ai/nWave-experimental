"""Regression test: nw-user-examiner must never kill by name/pattern.

K4 incident: while examining a live app, nw-user-examiner ran
`killall -9 python`, which killed the parent orchestrator process (not a
process it started), losing the result payload and costing ~449s recovery.
This locks the fix -- an explicit prohibition on process-wide/name-matching
kill commands plus a positive exact-owned-PID cleanup rule -- into the public
agent spec's Constraints section, without weakening the source-blind
(never-read-code) epistemology the agent otherwise depends on.
"""

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENT_PATH = PROJECT_ROOT / "nWave" / "agents" / "nw-user-examiner.md"

DANGEROUS_COMMAND_FAMILIES = [
    "killall",
    "pkill",
    "pgrep",
    "kill $(",
]


def _agent_text() -> str:
    return AGENT_PATH.read_text(encoding="utf-8")


def _process_safety_bullet(text: str) -> str:
    """Extract the single Constraints bullet governing kill safety.

    Bounded from the "if a supplied public start recipe" anchor to the next
    top-level bullet (a line beginning with "- "), so assertions below are
    scoped to this rule rather than matching incidentally elsewhere.
    """
    match = re.search(
        r"- If a supplied public start recipe starts a process.*?(?=\n- |\Z)",
        text,
        re.DOTALL,
    )
    assert match, "process-safety bullet not found in nw-user-examiner.md"
    return match.group(0)


@pytest.mark.parametrize("dangerous_command", DANGEROUS_COMMAND_FAMILIES)
def test_dangerous_kill_families_are_forbidden_and_scoped(dangerous_command):
    """Every dangerous kill family is named forbidden inside the bullet, and
    does not appear sanctioned anywhere else in the agent spec."""
    text = _agent_text()
    bullet = _process_safety_bullet(text)
    assert dangerous_command in bullet, (
        f"'{dangerous_command}' must be explicitly named forbidden in the "
        "process-safety Constraints bullet"
    )
    assert "forbidden" in bullet.lower()

    remainder = text.replace(bullet, "", 1)
    assert dangerous_command not in remainder, (
        f"'{dangerous_command}' appears outside the prohibition bullet -- "
        "it may be sanctioned elsewhere in the spec"
    )


def test_owned_pid_capture_reverify_and_no_kill_without_handle():
    """Positive rule: capture exact PID/ownership at creation, re-verify
    ownership before signaling, kill nothing without a reverified owned
    handle, and report an orphan as a concrete observation."""
    bullet = _process_safety_bullet(_agent_text())
    assert "PID" in bullet
    assert "ownership handle" in bullet
    assert "at creation" in bullet
    assert "re-verif" in bullet.lower()
    assert "kill nothing" in bullet.lower()
    assert "report" in bullet.lower() and "orphan" in bullet.lower()


def test_source_blindness_and_verdict_contract_preserved_no_new_controller():
    """The fix must not weaken source-blindness, must not introduce a
    controller/ledger/hook/registry, and must preserve the terminal
    PASS/FAIL/INDETERMINATE verdict contract."""
    text = _agent_text()
    bullet = _process_safety_bullet(text)

    assert "Source blind" in text
    assert "PASS | FAIL | INDETERMINATE" in text

    for forbidden_term in ("controller", "ledger", "hook", "registry"):
        assert forbidden_term not in bullet.lower(), (
            f"'{forbidden_term}' must not appear in the process-safety bullet"
        )
