"""Public oracle for the one completed-wave boundary of expansion offers.

The sole driving port is the installed ``des wave-entry`` process. It observes
the stdout grammar retained at a wave's entry and the state command an
orchestrator runs after a terminal. It does not claim to observe an installed
conversational host following wave instructions.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ASK_HOME = Path(__file__).parent / "nwave_home_ask"
MODE_HOMES = {
    "ask": ASK_HOME,
    "always-skip": REPOSITORY_ROOT
    / "tests/des/acceptance/wave_end_preference_without_a_question/nwave_home_always_skip",
    "always-expand": REPOSITORY_ROOT
    / "tests/des/acceptance/wave_end_preference_without_a_question/nwave_home_always_expand",
    "smart": REPOSITORY_ROOT
    / "tests/des/acceptance/wave_end_smart_trigger/nwave_home_smart",
    "ask-intelligent": REPOSITORY_ROOT
    / "tests/des/acceptance/wave_end_named_topics/nwave_home_ask_intelligent",
}
WHEN = "WAVE-END-OFFER-INTERNAL-WHEN: "
NOT_NOW = "WAVE-END-OFFER-INTERNAL-NOT-NOW: "
RESOLVED_ONCE = "WAVE-END-OFFER-INTERNAL-RESOLVED-ONCE: "


def _run(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Drive a public DES command with a fixture-owned global preference."""
    environment = os.environ.copy()
    environment["NWAVE_AGENTS_HOME"] = str(home.resolve())
    return subprocess.run(
        ["uv", "run", "des", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _terminal(home: Path, wave: str = "deliver") -> str:
    outcome = _run(
        home, "wave-entry", "--repo-root", str(REPOSITORY_ROOT), "--wave", wave
    )
    terminal = outcome.stdout + outcome.stderr
    assert outcome.returncode == 0, (
        "WHAT: a declared wave could not resolve its entry-time offer policy; WHY: "
        "the preference must be resolved once before a completed wave can decide "
        f"whether to say anything; HOW: accept {wave!r} and print its public rows "
        f"(terminal={terminal!r})."
    )
    return terminal


def _rows(terminal: str, prefix: str) -> list[str]:
    return [line for line in terminal.splitlines() if line.startswith(prefix)]


@pytest.mark.parametrize(
    ("mode", "expects_when"),
    (
        ("ask", True),
        ("always-expand", True),
        ("smart", True),
        ("ask-intelligent", True),
        ("always-skip", False),
    ),
)
def test_the_scope_and_one_time_preference_lifecycle_are_explicit_for_every_mode(
    mode: str, expects_when: bool
) -> None:
    """Every preference outcome retains one entry decision, even silent mode."""
    terminal = _terminal(MODE_HOMES[mode])
    when_rows = _rows(terminal, WHEN)
    resolved_rows = _rows(terminal, RESOLVED_ONCE)

    assert len(when_rows) == int(expects_when), (
        "WHAT: the completed-wave scope row is absent, duplicated, or appears for "
        "silent preference; WHY: an offer is speakable only in a final response of "
        "a wave that really completed, while silence has no message consumer; HOW: "
        f"emit exactly one WHEN row only for an uttering mode (mode={mode!r}, rows={when_rows!r})."
    )
    if expects_when:
        scope = when_rows[0].lower()
        assert "final response" in scope and "complet" in scope, (
            "WHAT: the WHEN row does not confine an offer to the final response of "
            "a completed wave; WHY: a lone DES terminal must never prompt the user; "
            f"HOW: name both limits in the WHEN row (row={when_rows[0]!r})."
        )
    assert len(resolved_rows) == 1, (
        "WHAT: the entry terminal does not declare exactly one preference resolution; "
        "WHY: a wave must not reread configuration or decide differently at its end; "
        f"HOW: emit one RESOLVED-ONCE row in every mode (mode={mode!r}, rows={resolved_rows!r})."
    )
    lifecycle = resolved_rows[0].lower()
    assert (
        "once" in lifecycle
        and "global-config" in lifecycle
        and "do not read" in lifecycle
    ), (
        "WHAT: the resolution row does not identify its one-time global-config "
        "lifecycle; WHY: the existing cascade has one entry-time owner; HOW: say it "
        f"was resolved once from GLOBAL-CONFIG and is not read again (row={resolved_rows[0]!r})."
    )
    assert "wave-end step" in lifecycle, (
        "WHAT: the resolution row leaves a later wave-end operation possible; WHY: "
        "there is no DES wave-end step after a terminal; HOW: explicitly forbid a "
        f"wave-end step (row={resolved_rows[0]!r})."
    )


def test_the_completed_wave_terminal_enumerates_every_non_completion_situation() -> (
    None
):
    """The six exclusions make absence distinguishable from an omitted policy."""
    terminal = _terminal(ASK_HOME)
    rows = _rows(terminal, NOT_NOW)

    assert len(rows) == 6, (
        "WHAT: non-completion situations are not a closed population of six; WHY: "
        "a boolean completion flag leaves the no-offer branch without a producer; "
        f"HOW: emit six NOT-NOW rows (rows={rows!r})."
    )
    joined = "\n".join(rows)
    for outcome in ("Success", "Refusal", "Retry", "Indeterminate"):
        assert re.search(rf"\b{outcome}\b", joined), (
            "WHAT: a lone DES step terminal is not explicitly excluded from an offer; "
            "WHY: a terminal outcome is not a completed wave; HOW: name the quoted "
            f"outcome word {outcome!r} in a NOT-NOW row (rows={rows!r})."
        )
    lower = joined.lower()
    assert (
        "craft" in lower
        and "before your final response" in lower
        and "without completing" in lower
    ), (
        "WHAT: the exclusion population misses a successful craft, an earlier turn, "
        "or a stopped wave; WHY: none completes the named wave; HOW: name all three "
        f"situations in NOT-NOW rows (rows={rows!r})."
    )
    assert "DELIVERY-OUTCOME:" not in joined, (
        "WHAT: an internal instruction uses the DELIVERY-OUTCOME line prefix; WHY: "
        "a terminal-row consumer could treat it as a second outcome; HOW: quote only "
        f"the outcome words in NOT-NOW rows (rows={rows!r})."
    )


def test_lone_terminals_never_construct_or_carry_a_wave_end_offer() -> None:
    """A refusal and the after-terminal state query are different from wave completion."""
    refusal = _run(
        ASK_HOME,
        "wave-entry",
        "--repo-root",
        str(REPOSITORY_ROOT),
        "--wave",
        "nonsense",
    )
    state = _run(ASK_HOME, "state", "--repo-root", str(REPOSITORY_ROOT))
    refused_terminal = refusal.stdout + refusal.stderr
    state_terminal = state.stdout + state.stderr

    assert "DELIVERY-OUTCOME: Refusal" in refused_terminal, (
        "WHAT: an uninstalled wave did not refuse; WHY: a model-invented wave cannot "
        "complete and receive an offer; HOW: return the public Refusal terminal."
    )
    assert (
        "WAVE-END-OFFER" not in refused_terminal
        and "WAVE-END-OFFER" not in state_terminal
    ), (
        "WHAT: a lone terminal emitted a wave-end offer; WHY: only a named wave's "
        "final response may say it; HOW: construct offer rows only at wave entry, "
        f"never for refusal or state (refusal={refused_terminal!r}, state={state_terminal!r})."
    )
