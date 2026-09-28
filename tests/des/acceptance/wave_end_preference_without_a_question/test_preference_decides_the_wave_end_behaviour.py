"""Public oracle for wave-end preferences that do not ask a question.

The only driving port is the installed ``des wave-entry`` CLI.  These finite,
configured preference cases verify the artefact that the assistant receives at
wave entry; a separate installed-host conversational smoke remains necessary to
observe an assistant carrying out an unprompted explanation in chat.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ALWAYS_SKIP_HOME = Path(__file__).parent / "nwave_home_always_skip"
ALWAYS_EXPAND_HOME = Path(__file__).parent / "nwave_home_always_expand"


def _run_wave_entry(home: Path) -> subprocess.CompletedProcess[str]:
    """Drive the real CLI with one fixture-owned global configuration."""
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


def _successful_terminal(outcome: subprocess.CompletedProcess[str]) -> str:
    """Return the shipped terminal only after its public command succeeded."""
    terminal = outcome.stdout + outcome.stderr
    assert outcome.returncode == 0, (
        "WHAT: wave entry failed for a legal expansion preference; WHY: the "
        "assistant needs a resolved wave-end behaviour before the design wave "
        "runs; HOW: resolve the legal preference and emit its public terminal "
        f"rows (terminal={terminal!r})."
    )
    return terminal


def _rows(terminal: str, marker: str) -> list[str]:
    """Read only the shipped protocol rows belonging to one behaviour marker."""
    return [line for line in terminal.splitlines() if line.startswith(marker)]


def test_preference_decides_the_wave_end_behaviour_without_a_question() -> None:
    """Skip is proactive silence; expand directs a pertinent, ungated explanation."""
    skip_terminal = _successful_terminal(_run_wave_entry(ALWAYS_SKIP_HOME))
    expand_terminal = _successful_terminal(_run_wave_entry(ALWAYS_EXPAND_HOME))

    assert "WAVE-END-OFFER: none" in skip_terminal, (
        "WHAT: always-skip did not produce the no-offer behaviour; WHY: this "
        "preference promises proactive silence at wave end; HOW: render the "
        "existing WAVE-END-OFFER label as none for always-skip."
    )
    assert "WAVE-END-OFFER-CHAT:" not in skip_terminal, (
        "WHAT: always-skip emitted a chat offer; WHY: proactive silence means "
        "the user is never asked about expansion; HOW: emit no CHAT row for the "
        f"Silent behaviour (terminal={skip_terminal!r})."
    )
    assert "WAVE-END-OFFER-INTERNAL-ACCEPTANCE" not in skip_terminal, (
        "WHAT: always-skip emitted an acceptance policy; WHY: no offer exists "
        "to accept when the resolved preference is Silent; HOW: keep INTERNAL-"
        f"ACCEPTANCE exclusive to Question (terminal={skip_terminal!r})."
    )
    assert "WAVE-END-OFFER: unprompted" in expand_terminal, (
        "WHAT: always-expand did not produce the unprompted behaviour; WHY: "
        "this preference promises an explanation without an offer first; HOW: "
        "render the existing WAVE-END-OFFER label as unprompted."
    )
    expand_rows = _rows(expand_terminal, "WAVE-END-OFFER-INTERNAL-EXPAND:")
    assert len(expand_rows) == 1, (
        "WHAT: always-expand has no internal expansion directive; WHY: the "
        "assistant needs an instruction to explain rather than ask; HOW: emit "
        f"one INTERNAL-EXPAND row (rows={expand_rows!r})."
    )
    assert "design" in expand_rows[0].lower(), (
        "WHAT: the unprompted directive is not pertinent to the completed design "
        "wave; WHY: the explanation must describe the wave that just completed; "
        f"HOW: name design in INTERNAL-EXPAND (row={expand_rows[0]!r})."
    )
    assert "WAVE-END-OFFER-CHAT:" not in expand_terminal, (
        "WHAT: always-expand emitted a chat offer; WHY: an unprompted explanation "
        "must not wait for the user to accept it; HOW: build no CHAT row for "
        f"Unprompted (terminal={expand_terminal!r})."
    )
    assert "WAVE-END-OFFER-INTERNAL-ACCEPTANCE" not in expand_terminal, (
        "WHAT: always-expand emitted an acceptance policy; WHY: an unprompted "
        "explanation is not gated on acceptance; HOW: keep INTERNAL-ACCEPTANCE "
        f"exclusive to Question (terminal={expand_terminal!r})."
    )
    assert skip_terminal != expand_terminal, (
        "WHAT: always-skip and always-expand have identical terminals; WHY: the "
        "preference must decide behaviour, not merely echo a configured value; "
        "HOW: emit the distinct Silent and Unprompted behaviour rows."
    )
