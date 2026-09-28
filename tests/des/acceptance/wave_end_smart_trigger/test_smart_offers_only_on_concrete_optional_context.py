"""Public oracle for the smart, conditionally relayable wave-end offer.

The driving port is the installed ``des wave-entry`` CLI.  This oracle observes
the product-owned terminal policy, not an assistant's later semantic judgment:
whether the completed wave actually produced optional context is decided in the
conversation host.  The terminal must nevertheless make both branches, its
closed trigger vocabulary, and the fail-safe relay marker observable.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SMART_HOME = Path(__file__).parent / "nwave_home_smart"
ASK_HOME = Path(__file__).parent / "nwave_home_ask"
CONDITION_MARKER = "WAVE-END-OFFER-INTERNAL-CONDITION: "
TRIGGER_MARKER = "WAVE-END-OFFER-INTERNAL-TRIGGER: "
GATED_CHAT_MARKER = "WAVE-END-OFFER-CHAT-IF: "


def _run_wave_entry(home: Path) -> subprocess.CompletedProcess[str]:
    """Drive the shipped command with a fixture-owned resolved preference."""
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


def _terminal(outcome: subprocess.CompletedProcess[str]) -> str:
    """Return the shipped terminal only after the public command succeeds."""
    terminal = outcome.stdout + outcome.stderr
    assert outcome.returncode == 0, (
        "WHAT: wave entry failed for the legal smart preference; WHY: the "
        "assistant needs the resolved gated policy before the wave begins; HOW: "
        f"resolve smart and emit its terminal rows (terminal={terminal!r})."
    )
    return terminal


def _rows(terminal: str, marker: str) -> list[str]:
    """Read product-shipped rows from one unambiguous terminal marker."""
    return [line for line in terminal.splitlines() if line.startswith(marker)]


@pytest.mark.negative_at
def test_smart_offers_only_on_concrete_optional_context() -> None:
    """Smart supplies a gated sentence and explicit silence, never an ungated offer."""
    smart_terminal = _terminal(_run_wave_entry(SMART_HOME))
    ask_terminal = _terminal(_run_wave_entry(ASK_HOME))

    assert "WAVE-END-OFFER: conditional" in smart_terminal, (
        "WHAT: smart did not produce a conditional offer; WHY: an optional "
        "explanation is permitted only when the completed wave produced concrete "
        "optional context; HOW: render smart as the conditional behaviour."
    )
    gated_rows = _rows(smart_terminal, GATED_CHAT_MARKER)
    assert len(gated_rows) == 1 and gated_rows[0][len(GATED_CHAT_MARKER) :], (
        "WHAT: smart has no product-owned gated chat sentence; WHY: the assistant "
        "must relay a sentence authored by DES only after the condition holds; HOW: "
        f"emit exactly one non-empty {GATED_CHAT_MARKER!r} row (rows={gated_rows!r})."
    )
    assert not _rows(smart_terminal, "WAVE-END-OFFER-CHAT: "), (
        "WHAT: smart emitted an ungated relayable sentence; WHY: an unaware "
        "consumer would offer detail even when context is absent; HOW: use only "
        "the distinct CHAT-IF marker for smart."
    )

    ask_rows = _rows(ask_terminal, "WAVE-END-OFFER-CHAT: ")
    assert (
        len(ask_rows) == 1
        and gated_rows[0][len(GATED_CHAT_MARKER) :]
        == ask_rows[0][len("WAVE-END-OFFER-CHAT: ") :]
    ), (
        "WHAT: smart changed the ask sentence; WHY: this value changes whether the "
        "offer is said, not what topic it names; HOW: build both payloads through "
        "the existing product-owned chat sentence."
    )

    conditions = _rows(smart_terminal, CONDITION_MARKER)
    assert len(conditions) == 1, (
        "WHAT: smart does not state its one condition; WHY: the assistant cannot "
        "apply the gate safely without both branches; HOW: emit one INTERNAL-"
        f"CONDITION row (rows={conditions!r})."
    )
    condition = conditions[0].lower()
    for phrase in (
        "concrete optional context",
        "only if",
        "say nothing about expansion",
        "do not invent",
    ):
        assert phrase in condition, (
            f"WHAT: the smart condition omits {phrase!r}; WHY: it must permit an "
            "offer only for real optional context and otherwise preserve silence; "
            "HOW: state the positive gate, silence branch, and no-invention rule."
        )

    trigger_rows = _rows(smart_terminal, TRIGGER_MARKER)
    expected_kinds = ("alternative", "trade-off", "risk", "constraint", "consequence")
    assert len(trigger_rows) == len(expected_kinds), (
        "WHAT: smart did not enumerate its closed population of optional-context "
        "kinds; WHY: the gate must distinguish optional context from the primary "
        "wave result; HOW: emit each of the five declared trigger rows "
        f"(rows={trigger_rows!r})."
    )
    trigger_text = "\n".join(trigger_rows).lower()
    for kind in expected_kinds:
        assert kind in trigger_text, (
            f"WHAT: smart omits the {kind!r} trigger kind; WHY: the closed "
            "vocabulary prevents the primary result alone from justifying an offer; "
            "HOW: emit the declared trigger row for that kind."
        )

    assert _rows(smart_terminal, "WAVE-END-OFFER-INTERNAL-ACCEPTANCE: "), (
        "WHAT: smart has no acceptance policy; WHY: a gated offer still needs a "
        "natural-language way to accept it when it is made; HOW: retain the "
        "existing INTERNAL-ACCEPTANCE policy."
    )
    assert "WAVE-END-OFFER: conditional" not in ask_terminal and not _rows(
        ask_terminal, GATED_CHAT_MARKER
    ), (
        "WHAT: ask became conditional; WHY: its existing preference remains an "
        "unconditional optional question; HOW: keep the smart gate exclusive to "
        "the smart branch."
    )
    assert "des wave-end" not in smart_terminal, (
        "WHAT: smart directs a second DES step at wave end; WHY: preference is "
        "resolved once at entry and the end must not reread it; HOW: emit no "
        "wave-end command."
    )
    assert "NEXT: no step is owed" in smart_terminal, (
        "WHAT: wave entry says a further step is owed; WHY: the end of the wave "
        "must consume the retained directive only; HOW: keep the no-step terminal "
        "outcome."
    )
