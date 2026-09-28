"""Public oracle for the standing right to request wave detail directly.

The driving port is the read-only ``des wave-entry`` process.  It observes the
one product-owned instruction which a conversation host receives for every
resolved preference.  It does not simulate or claim to observe the host's later
substantive reply; that residual obligation belongs to the conversation host.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ON_REQUEST = "WAVE-END-OFFER-INTERNAL-ON-REQUEST: "
MODE_HOMES = {
    "always-skip": Path(__file__).parent / "nwave_home_always_skip",
    "ask": Path(__file__).parent / "nwave_home_ask",
    "always-expand": Path(__file__).parent / "nwave_home_always_expand",
    "smart": Path(__file__).parent / "nwave_home_smart",
    "ask-intelligent": Path(__file__).parent / "nwave_home_ask_intelligent",
}


def _run_wave_entry(home: Path) -> subprocess.CompletedProcess[str]:
    """Drive the real entry point with one fixture-owned preference."""
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


def _terminal(home: Path) -> str:
    """Return the real terminal only after the public command succeeds."""
    outcome = _run_wave_entry(home)
    terminal = outcome.stdout + outcome.stderr
    assert outcome.returncode == 0, (
        "WHAT: wave entry failed for a legal expansion preference; WHY: the "
        "standing direct-request obligation must be available before the wave "
        "begins; HOW: resolve the preference and emit its public instruction "
        f"rows (terminal={terminal!r})."
    )
    return terminal


def _on_request_rows(terminal: str) -> list[str]:
    """Read the one non-relayable standing obligation from shipped stdout."""
    return [line for line in terminal.splitlines() if line.startswith(ON_REQUEST)]


@pytest.mark.parametrize("mode", tuple(MODE_HOMES), ids=tuple(MODE_HOMES))
def test_direct_request_for_wave_detail_is_owed_under_every_preference(
    mode: str,
) -> None:
    """A user request is answered; preference controls proactive raising only."""
    terminal = _terminal(MODE_HOMES[mode])
    rows = _on_request_rows(terminal)

    assert len(rows) == 1, (
        "WHAT: wave entry did not emit exactly one answer-on-request rule; WHY: "
        "every resolved preference, including always-skip, must carry the same "
        "standing user right without competing owners; HOW: emit one INTERNAL-"
        f"ON-REQUEST row in every resolved branch (mode={mode!r}, rows={rows!r})."
    )
    rule = rows[0].lower()
    for phrase in (
        "direct request",
        "answer",
        "own initiative",
        "always-skip",
    ):
        assert phrase in rule, (
            f"WHAT: the direct-request rule omits {phrase!r}; WHY: it must oblige "
            "an immediate substantive reply while confining preference and scope "
            "rules to proactive offers; HOW: state this required boundary in the "
            f"one ON-REQUEST row (mode={mode!r}, row={rows[0]!r})."
        )


def test_always_skip_remains_proactively_silent_without_a_canned_direct_reply() -> None:
    """The standing obligation adds neither a relayable sentence nor a DES action."""
    terminal = _terminal(MODE_HOMES["always-skip"])

    assert "WAVE-END-OFFER: none" in terminal, (
        "WHAT: always-skip no longer renders proactive silence; WHY: the direct "
        "request right must not turn into an unsolicited offer; HOW: retain the "
        "Silent behaviour's none row."
    )
    assert "WAVE-END-OFFER-CHAT" not in terminal, (
        "WHAT: always-skip supplied a relayable chat payload; WHY: DES must not "
        "provide a canned sentence for a direct request; HOW: keep the standing "
        "rule INTERNAL and emit no CHAT or CHAT-IF row."
    )
    assert "not constrained here" not in terminal.lower(), (
        "WHAT: always-skip merely permits a direct reply; WHY: the user is owed "
        "an answer at any moment, not an optional exception to silence; HOW: "
        "remove the permissive Silent NOTE clause and use ON-REQUEST instead."
    )
    assert (
        "des wave-end" not in terminal.lower() and "des expand" not in terminal.lower()
    ), (
        "WHAT: the direct-request rule supplied a further DES command; WHY: the "
        "answer is conversation-host behaviour from the wave's actual result; HOW: "
        "supply no command in the emitted obligation."
    )
    assert "NEXT: no step is owed" in terminal, (
        "WHAT: wave entry says a later step is owed; WHY: a direct request needs "
        "no acceptance or DES action; HOW: retain the read-only no-step outcome."
    )
