"""Public CLI oracle for the ask-intelligent wave-end expansion offer.

The installed ``des wave-entry`` command is the sole driving port. At entry it
cannot know what a wave will later produce, so this oracle observes only the
terminal policy it ships. Whether an installed conversational host later names
at most two relevant topics requires an independent installed-host conversation
smoke; it is not a claim this CLI observation can establish.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ASK_INTELLIGENT_HOME = Path(__file__).parent / "nwave_home_ask_intelligent"
SMART_HOME = Path(__file__).parent / "nwave_home_smart"
NAMING_MARKER = "WAVE-END-OFFER-INTERNAL-NAMING: "
TRIGGER_MARKER = "WAVE-END-OFFER-INTERNAL-TRIGGER: "
CONDITION_MARKER = "WAVE-END-OFFER-INTERNAL-CONDITION: "


def _run_wave_entry(home: Path) -> subprocess.CompletedProcess[str]:
    """Drive the shipped entry command with a fixture-owned preference."""
    environment = os.environ.copy()
    environment["NWAVE_AGENTS_HOME"] = str(home.resolve())
    return subprocess.run(
        [
            "uv",
            "run",
            "des",
            "wave-entry",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--wave",
            "design",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _terminal(outcome: subprocess.CompletedProcess[str], mode: str) -> str:
    terminal = outcome.stdout + outcome.stderr
    assert outcome.returncode == 0, (
        f"WHAT: wave entry failed for legal {mode!r}; WHY: the host needs the "
        "resolved wave-end policy before the wave starts; HOW: resolve that "
        f"legal preference and emit its terminal rows (terminal={terminal!r})."
    )
    return terminal


def _rows(terminal: str, marker: str) -> list[str]:
    """Read rows emitted by the product, never test-authored equivalents."""
    return [line for line in terminal.splitlines() if line.startswith(marker)]


@pytest.mark.negative_at
def test_ask_intelligent_emits_named_offer_policy_with_smarts_gate() -> None:
    """Named policy reuses smart's gate and leaves result-derived names to the host."""
    named_terminal = _terminal(_run_wave_entry(ASK_INTELLIGENT_HOME), "ask-intelligent")
    smart_terminal = _terminal(_run_wave_entry(SMART_HOME), "smart")

    assert "WAVE-END-OFFER: named" in named_terminal, (
        "WHAT: ask-intelligent has no named-topic behaviour; WHY: users who chose "
        "it need an optional, result-specific expansion offer; HOW: render the "
        "named member of the closed wave-end behaviour sum."
    )
    naming_rows = _rows(named_terminal, NAMING_MARKER)
    assert len(naming_rows) == 1, (
        "WHAT: the named offer does not state exactly one naming rule; WHY: the "
        "host needs one unambiguous policy for result-derived topics; HOW: emit "
        f"one {NAMING_MARKER!r} row (rows={naming_rows!r})."
    )
    assert not _rows(named_terminal, "WAVE-END-OFFER-CHAT: ") and not _rows(
        named_terminal, "WAVE-END-OFFER-CHAT-IF: "
    ), (
        "WHAT: named emitted a fixed relayable sentence; WHY: a sentence made at "
        "entry cannot explicitly name a later result topic; HOW: keep named topic "
        "selection in the host-facing internal rule."
    )
    offer_rows = _rows(named_terminal, "WAVE-END-OFFER")
    assert not any("<" in row or "{" in row or "..." in row for row in offer_rows), (
        "WHAT: a placeholder stands in for a topic; WHY: a placeholder can hide an "
        "invented topic; HOW: emit no topic token until the host has a real result."
    )

    named_triggers = sorted(_rows(named_terminal, TRIGGER_MARKER))
    smart_triggers = sorted(_rows(smart_terminal, TRIGGER_MARKER))
    assert named_triggers and named_triggers == smart_triggers, (
        "WHAT: ask-intelligent does not reuse smart's closed trigger population; "
        "WHY: both preferences must offer only for the same optional context; HOW: "
        "reuse the shared condition and trigger-row constructor."
    )
    named_conditions = _rows(named_terminal, CONDITION_MARKER)
    smart_conditions = _rows(smart_terminal, CONDITION_MARKER)
    assert named_conditions and named_conditions == smart_conditions, (
        "WHAT: named does not retain smart's conditional gate; WHY: result "
        "specificity must not broaden when an offer is made; HOW: emit the shared "
        "conditional policy."
    )
    assert _rows(named_terminal, "WAVE-END-OFFER-INTERNAL-ACCEPTANCE: "), (
        "WHAT: named lacks an acceptance policy; WHY: its explanation remains "
        "optional; HOW: reuse the natural-language acceptance row."
    )
    assert "WAVE-END-OFFER: conditional" not in named_terminal, (
        "WHAT: named is rendered as smart; WHY: the host needs distinct named "
        "behaviour while retaining the same gate; HOW: emit the named label."
    )
    next_rows = _rows(named_terminal, "NEXT: ")
    assert next_rows and not any("des " in row.lower() for row in next_rows), (
        "WHAT: named requires a follow-up command; WHY: preference resolves once at "
        "entry and result naming requires no DES step; HOW: retain a no-command outcome."
    )
