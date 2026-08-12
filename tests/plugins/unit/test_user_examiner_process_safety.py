"""Regression test: nw-user-examiner must never kill by name/pattern.

K4 incident: while examining a live app, nw-user-examiner ran
`killall -9 python`, which killed the parent orchestrator process (not a
process it started), losing the result payload and costing ~449s recovery.
This locks the fix — an explicit prohibition on process-wide/name-matching
kill commands plus a positive exact-owned-PID cleanup rule — into the public
agent spec, without weakening the source-blind (never-read-code) epistemology
the agent otherwise depends on.
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
    """Extract the single Critical-Rules bullet that governs kill safety.

    Bounded from its own anchor to the start of the next top-level bullet
    (a line beginning with "- **"), so assertions below are scoped to this
    rule rather than matching incidentally anywhere in the file.
    """
    match = re.search(
        r"- \*\*Never kill by process name or pattern.*?(?=\n- \*\*|\n## )",
        text,
        re.DOTALL,
    )
    assert match, "process-safety bullet not found in nw-user-examiner.md"
    return match.group(0)


class TestProcessKillProhibition:
    """Every dangerous kill family must be explicitly named as forbidden."""

    @pytest.mark.parametrize("dangerous_command", DANGEROUS_COMMAND_FAMILIES)
    def test_dangerous_command_family_named_forbidden(self, dangerous_command):
        bullet = _process_safety_bullet(_agent_text())
        assert dangerous_command in bullet, (
            f"'{dangerous_command}' must be explicitly named in the "
            "process-safety prohibition"
        )

    def test_prohibition_bullet_uses_forbidden_language(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "Forbidden" in bullet or "never" in bullet.lower()

    @pytest.mark.parametrize("dangerous_command", DANGEROUS_COMMAND_FAMILIES)
    def test_dangerous_command_family_not_sanctioned_elsewhere(self, dangerous_command):
        """The literal command must not appear outside the prohibition bullet
        (e.g. as a sanctioned example in some other section)."""
        text = _agent_text()
        bullet = _process_safety_bullet(text)
        remainder = text.replace(bullet, "", 1)
        assert dangerous_command not in remainder, (
            f"'{dangerous_command}' appears outside the prohibition bullet — "
            "it may be sanctioned elsewhere in the spec"
        )

    def test_incident_anchor_present(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "449s" in bullet or "K4" in bullet


class TestOwnedPidCleanupRule:
    """Positive rule: capture, re-verify, and kill only an exact owned PID."""

    def test_requires_capturing_exact_pid_at_creation(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "PID" in bullet
        assert "$!" in bullet or "ownership handle" in bullet

    def test_requires_reverification_before_signaling(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "re-verify" in bullet.lower()

    def test_requires_no_kill_when_no_owned_handle(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "kill nothing" in bullet.lower()

    def test_orphan_reported_as_observation_not_fixed(self):
        bullet = _process_safety_bullet(_agent_text())
        assert "report" in bullet.lower()
        assert "observation" in bullet.lower()


class TestSourceBlindEpistemologyPreserved:
    """The fix must not weaken the never-read-code / no-controller rules."""

    def test_never_read_code_principle_intact(self):
        text = _agent_text()
        assert "must never read code" in text

    def test_no_controller_or_ledger_language_introduced(self):
        bullet = _process_safety_bullet(_agent_text())
        for forbidden_term in ("controller", "ledger", "hook"):
            assert forbidden_term not in bullet.lower()

    def test_verdict_contract_unchanged(self):
        text = _agent_text()
        assert "PASS | FAIL | INDETERMINATE" in text


class TestPrinciple8ProvenanceAnchors:
    """Principle 8 must retain unique examples and provenance after compression."""

    def _extract_principle_8(self, text: str) -> str:
        """Extract Principle 8 from Core Principles section.

        Scoped from "8. **Absence ≠ incapacity.**" to the start of principle 9
        (or end of section if no principle 9), so tests verify this rule only.
        """
        match = re.search(
            r"8\. \*\*Absence ≠ incapacity\.\*\*.*?(?=\n9\. \*\*|\n## |\Z)",
            text,
            re.DOTALL,
        )
        assert match, "Principle 8 not found in Core Principles"
        return match.group(0)

    def test_provenance_date_anchor_present(self):
        text = _agent_text()
        principle_8 = self._extract_principle_8(text)
        assert "Ale 2026-07-12" in principle_8, (
            "Principle 8 must name the provenance anchor (Ale 2026-07-12)"
        )

    def test_enum_unknown_symbol_example_present(self):
        text = _agent_text()
        principle_8 = self._extract_principle_8(text)
        assert "unknown_symbol" in principle_8.lower(), (
            "Principle 8 must retain the enum unknown_symbol example"
        )

    def test_confidence_unread_tree_example_present(self):
        text = _agent_text()
        principle_8 = self._extract_principle_8(text)
        assert "confidence 1.0" in principle_8.lower() or (
            "confidence" in principle_8.lower() and "unread" in principle_8.lower()
        ), "Principle 8 must retain the confidence 1.0 / unread tree example"

    def test_complete_zero_legs_example_present(self):
        text = _agent_text()
        principle_8 = self._extract_principle_8(text)
        assert (
            "complete" in principle_8.lower() and "zero legs" in principle_8.lower()
        ), "Principle 8 must retain the Complete / zero legs example"

    def test_python_ast_phantom_example_present(self):
        text = _agent_text()
        principle_8 = self._extract_principle_8(text)
        assert "python" in principle_8.lower() and (
            "phantom" in principle_8 or "invented" in principle_8
        ), "Principle 8 must retain the Python-AST phantom/invented example"
