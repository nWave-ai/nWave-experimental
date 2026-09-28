"""Public oracle for an optional, natural-language wave-end expansion offer.

The only behavioural driving port is the installed ``des wave-entry`` CLI.
It resolves the global documentation preference once at wave entry and emits
one CHAT payload and separate INTERNAL instruction rows.  Only the payload after
``WAVE-END-OFFER-CHAT:`` is relayable in chat; INTERNAL rows are for the
assistant only.
The test deliberately does not invoke a DES delivery step or accept either
choice: accepting an offer must leave the existing documents and DES execution
outside this feature's command untouched.

Scope limit: this oracle observes only the real CLI output and its read-only
state. It cannot observe an installed assistant retaining that block and
responding in chat. A real installed-host conversational smoke is required
before claiming that chat-facing value complete.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ASK_HOME = Path(__file__).parent / "nwave_home_ask"
ASK_EXPLICIT_HOME = Path(__file__).parent / "nwave_home_ask_explicit"
WAVES = ("discover", "diverge", "discuss", "design", "devops", "distill", "deliver")


def _run_wave_entry(home: Path, wave: str) -> subprocess.CompletedProcess[str]:
    """Drive the shipped CLI with an absolute, fixture-owned config location."""
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
            wave,
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _file_digests(root: Path) -> dict[str, str]:
    """Snapshot real files only; Python bytecode is not part of this contract."""
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(path for path in root.rglob("*") if path.is_file())
        if "__pycache__" not in path.parts
    }


def _git_porcelain() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _offer_lines(stdout: str) -> tuple[str, list[str]]:
    """Return the only relayable payload and its non-relayable instructions."""
    chat_prefix = "WAVE-END-OFFER-CHAT: "
    internal_prefix = "WAVE-END-OFFER-INTERNAL-"
    chat_lines = [line for line in stdout.splitlines() if line.startswith(chat_prefix)]
    internal_lines = [
        line for line in stdout.splitlines() if line.startswith(internal_prefix)
    ]

    assert len(chat_lines) == 1, (
        "WHAT: wave entry did not emit exactly one chat payload; WHY: a completed "
        "wave has one optional conversational offer, and multiple or absent payloads "
        "can make the assistant relay protocol text; HOW: print one "
        f"{chat_prefix!r} row (rows={chat_lines!r}, stdout={stdout!r})."
    )
    assert internal_lines, (
        "WHAT: wave entry emitted no separate internal instructions; WHY: DES must "
        "construct the assistant policy without exposing it as user chat; HOW: print "
        f"the required {internal_prefix!r} rows alongside the CHAT row."
    )
    return chat_lines[0][len(chat_prefix) :], internal_lines


@pytest.mark.parametrize("wave", WAVES, ids=WAVES)
def test_completed_wave_can_relay_a_plain_optional_expansion_offer(
    wave: str,
) -> None:
    """Every installed wave name can construct the one user-visible ask offer."""
    outcome = _run_wave_entry(ASK_HOME, wave)

    assert outcome.returncode == 0, (
        "WHAT: wave entry failed for a declared wave; WHY: a completed wave "
        "must be able to retain its optional expansion offer before its terminal "
        f"chat response; HOW: accept the closed wave name {wave!r} and emit its "
        f"offer (stdout={outcome.stdout!r}, stderr={outcome.stderr!r})."
    )
    assert "\x1b" not in outcome.stdout, (
        "WHAT: the offer contains an ANSI escape sequence; WHY: the chat offer "
        "must be accessible without colour or terminal control support; HOW: "
        "render the offer as plain text."
    )
    chat_text, internal_lines = _offer_lines(outcome.stdout)
    normalized = chat_text.lower()
    assert chat_text and chat_text.endswith("?"), (
        "WHAT: the relayable offer is not one natural-language question; WHY: "
        "the user must be able to understand and answer the optional choice in chat; "
        f"HOW: emit one concise question as CHAT text (chat_text={chat_text!r})."
    )
    assert wave in normalized, (
        "WHAT: the chat offer does not name the completed wave; WHY: the user needs "
        "to know which completed work the optional detail concerns; HOW: include the "
        f"completed wave name in the CHAT sentence (chat_text={chat_text!r})."
    )
    assert "optional" in normalized and "silence" in normalized, (
        "WHAT: the chat offer does not say that it is optional and silence changes "
        "nothing; WHY: declining must be possible without a command or reply; HOW: "
        f"state both facts in ordinary language (chat_text={chat_text!r})."
    )
    forbidden_chat_fragments = (
        "wave-end-offer",
        "provenance",
        "default",
        "explicit_override",
    )
    assert not any(fragment in normalized for fragment in forbidden_chat_fragments), (
        "WHAT: the user-visible offer leaks a protocol label or configuration metadata; "
        "WHY: only ordinary conversation may be relayed to chat; HOW: keep labels and "
        f"provenance in INTERNAL rows only (chat_text={chat_text!r})."
    )
    assert "reply " not in normalized, (
        "WHAT: the user-visible offer requires an exact reply token; WHY: affirmative "
        "natural-language replies and requests for detail must remain valid; HOW: ask "
        f"the question without a reply command (chat_text={chat_text!r})."
    )
    assert any(
        line.startswith("WAVE-END-OFFER-INTERNAL-MODE") for line in internal_lines
    ), (
        "WHAT: resolved-mode metadata is missing from INTERNAL output; WHY: the "
        "assistant must follow DES's entry-time decision without rereading config; HOW: "
        f"emit an INTERNAL-MODE row (internal_lines={internal_lines!r})."
    )
    assert any(
        line.startswith("WAVE-END-OFFER-INTERNAL-ACCEPTANCE") for line in internal_lines
    ), (
        "WHAT: natural-language acceptance policy is missing from INTERNAL output; WHY: "
        "the assistant needs the DES-built rule without exposing a command token; HOW: "
        f"emit an INTERNAL-ACCEPTANCE row (internal_lines={internal_lines!r})."
    )


def test_explicit_density_override_proves_wave_entry_read_the_preference() -> None:
    """Same ask outcome, different provenance: a constant block cannot pass."""
    default = _run_wave_entry(ASK_HOME, "design")
    explicit = _run_wave_entry(ASK_EXPLICIT_HOME, "design")

    assert default.returncode == explicit.returncode == 0, (
        "WHAT: a valid ask configuration failed at wave entry; WHY: the offer "
        "must resolve the existing global cascade once before the wave runs; HOW: "
        "read the selected global config through NWaveLocations and construct the "
        "offer without writing state."
    )
    default_chat, default_internal = _offer_lines(default.stdout)
    explicit_chat, explicit_internal = _offer_lines(explicit.stdout)
    assert default_chat and explicit_chat, (
        "WHAT: a configured ask mode did not construct an offer; WHY: the "
        "optional chat offer is promised only for that mode; HOW: emit the "
        "WAVE-END-OFFER-CHAT row for resolved ask."
    )
    assert any("default" in line.lower() for line in default_internal) and any(
        "explicit_override" in line.lower() for line in explicit_internal
    ), (
        "WHAT: the two configuration fixtures did not expose distinct cascade "
        "provenance; WHY: a hard-coded offer could otherwise masquerade as a "
        "preference read; HOW: echo resolver provenance in INTERNAL metadata, not "
        f"the chat payload (default={default_internal!r}, explicit={explicit_internal!r})."
    )


def test_unknown_wave_is_refused_without_constructing_an_offer() -> None:
    """The model cannot mint a wave designation and obtain a chat offer."""
    outcome = _run_wave_entry(ASK_HOME, "invented-wave")
    combined = outcome.stdout + outcome.stderr

    assert outcome.returncode != 0, (
        "WHAT: an unknown wave name succeeded; WHY: the assistant could create "
        "an offer for a wave that nWave never installed; HOW: refuse names outside "
        "the closed installed-wave set."
    )
    assert "WAVE-END-OFFER-CHAT:" not in combined, (
        "WHAT: an unknown wave emitted an offer; WHY: only a completed installed "
        "wave may cause a user-facing expansion prompt; HOW: return the refusal "
        "before offer construction."
    )
    missing = [wave for wave in WAVES if wave not in combined]
    assert not missing, (
        "WHAT: the refusal omits accepted wave names; WHY: the operator cannot "
        "repair the invalid input; HOW: list the closed installed-wave set in its "
        f"WHAT/WHY/HOW response (missing={missing!r}, output={combined!r})."
    )


def test_wave_entry_is_read_only_for_delivery_and_selected_config() -> None:
    """Constructing an offer changes neither DES state nor its input config."""
    before_status = _git_porcelain()
    before_des = _file_digests(REPOSITORY_ROOT / ".nwave" / "des")
    before_home = _file_digests(ASK_HOME)

    outcome = _run_wave_entry(ASK_HOME, "design")

    assert outcome.returncode == 0, (
        "WHAT: the read-only wave-entry query failed; WHY: completing a wave "
        "must not need to run a DES delivery step to obtain its chat offer; HOW: "
        f"keep wave-entry a read-only CLI projection (stderr={outcome.stderr!r})."
    )
    assert _git_porcelain() == before_status, (
        "WHAT: wave entry changed repository working state; WHY: accepting or "
        "ignoring the optional offer must leave documents and DES execution "
        "unchanged; HOW: do not write repository files while resolving the offer."
    )
    assert _file_digests(REPOSITORY_ROOT / ".nwave" / "des") == before_des, (
        "WHAT: wave entry changed .nwave/des state; WHY: it is outside the "
        "canonical delivery sequence; HOW: construct the offer in memory only."
    )
    assert _file_digests(ASK_HOME) == before_home, (
        "WHAT: wave entry changed the global config fixture; WHY: resolving a "
        "preference must never rewrite it; HOW: open the global config read-only."
    )
