"""Public oracle for refusing an illegal wave-entry expansion preference.

The only driving port is the real ``des wave-entry`` CLI.  The fixture supplies
an invalid configured choice through the same NWaveLocations-owned home that an
operator configures; the oracle observes the terminal a user receives.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INVALID_HOME = Path(__file__).parent / "nwave_home_invalid"
ACCEPTED_EXPANSION_PROMPTS = (
    "ask",
    "always-skip",
    "always-expand",
    "smart",
    "ask-intelligent",
)


def _run_wave_entry_with_invalid_preference() -> subprocess.CompletedProcess[str]:
    """Drive the shipped CLI against the fixture-owned global configuration."""
    environment = os.environ.copy()
    environment["NWAVE_AGENTS_HOME"] = str(INVALID_HOME.resolve())
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


def test_invalid_expansion_prompt_is_refused_before_the_design_wave_begins() -> None:
    """An illegal closed-set preference stops the wave with a repairable refusal."""
    outcome = _run_wave_entry_with_invalid_preference()
    terminal = outcome.stdout + outcome.stderr

    assert outcome.returncode != 0, (
        "WHAT: an illegal documentation.expansion_prompt succeeded; WHY: a wave "
        "cannot use a preference outside its closed legal set; HOW: stop the "
        "wave-entry command with a refusal before constructing an offer."
    )
    assert "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: the illegal expansion preference was not an explicit refusal; WHY: "
        "the software already knows the invalid configured choice and can tell the "
        "operator how to repair it; HOW: classify an illegal closed-set choice as "
        f"Refusal (terminal={terminal!r})."
    )
    assert "verbose" in terminal, (
        "WHAT: the refusal does not name the supplied invalid value; WHY: the "
        "operator cannot identify which configuration must change; HOW: include "
        f"the offending expansion_prompt value in WHAT/WHY/HOW (terminal={terminal!r})."
    )
    assert "documentation.expansion_prompt" in terminal, (
        "WHAT: the refusal does not name the invalid configuration field; WHY: "
        "the operator must know where the illegal choice was configured; HOW: "
        "identify documentation.expansion_prompt in WHAT/WHY/HOW "
        f"(terminal={terminal!r})."
    )
    missing_choices = [
        choice for choice in ACCEPTED_EXPANSION_PROMPTS if choice not in terminal
    ]
    assert not missing_choices, (
        "WHAT: the refusal omits accepted expansion-prompt values; WHY: a closed "
        "set refusal must let the operator repair the configuration without guessing; "
        "HOW: list every accepted value from ExpansionPromptMode "
        f"(missing={missing_choices!r}, terminal={terminal!r})."
    )
    assert "WAVE-END-OFFER-CHAT:" not in terminal, (
        "WHAT: wave entry built a chat offer from an illegal preference; WHY: the "
        "design wave must not begin when its entry preference is refused; HOW: return "
        f"the refusal before offer construction (terminal={terminal!r})."
    )
    assert "WAVE-END-OFFER-INTERNAL-" not in terminal, (
        "WHAT: wave entry emitted internal offer instructions after refusing its "
        "preference; WHY: the assistant must not begin wave work from an invalid "
        "choice; HOW: emit no offer rows on this refusal "
        f"(terminal={terminal!r})."
    )
    lower_terminal = terminal.lower()
    wave_stop_phrases = (
        "do not begin the wave",
        "do not start the wave",
        "wave does not begin",
        "wave does not start",
        "wave must not begin",
        "wave must not start",
    )
    assert any(phrase in lower_terminal for phrase in wave_stop_phrases), (
        "WHAT: the refusal never says that the wave does not begin; WHY: the "
        "operator needs the visible stop condition, not only a configuration error; "
        "HOW: state in WHAT/WHY/HOW that this refusal stops wave work "
        f"(terminal={terminal!r})."
    )
