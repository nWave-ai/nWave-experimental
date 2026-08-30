"""F-ROOT-MODE-GATE-SCOPE-CAPTURE-AND-LATCH defect 1 -- the mode-select
nagging/trap machinery captured every root Bash/Write/Edit in every repo and
every task, with no nWave-adjacency condition at all.

CONFIRMED IN SOURCE 2026-08-24: the repo-level opt-in already exists
(``<repo>/.nwave/config.json`` -> ``enabled``, repo-over-global precedence
via ``des.domain.config_merge.declared_enabled``) and other surfaces already
honour it (``activation_gate.apply_gate``, ``commit_message_attribution.
attribution_is_due``) -- the mode gate simply never consulted it. A beta
user's prose-drafting session in a mostly-markdown, unconfigured repo was
forced through ``nw-mode-select``, classified ``auto M``, then told BY THE
GATE'S OWN ERROR TEXT to invoke ``Skill(nw-auto)`` -- an irreversible
latch. A second, independent occurrence hit this repo's own orchestrator
session on a first Bash that only READ a document.

The fix (``root_activation_context.root_mode_gate_repo_is_active``, reused
by both `pre_tool_use_handler.py` and `pre_write_handler.py`): the SAME
``DESConfig``/``resolve_activation`` chain `activation_gate.apply_gate`
already uses scopes the "Invoke nw-mode-select" nag and the AUTO_PENDING/
INVALID handoff trap to a repo that actually declared the opt-in.

The vincolo di merito, verified here too (never weakened): once
``Skill(nw-auto)`` was GENUINELY observed in the transcript, the AUTO_ENGAGED
lockdown (e.g. the SendMessage/non-nw-* Agent restriction) stays
unconditional -- it must still fire even in a repo that never declared the
opt-in, because real delivery machinery is genuinely in flight by then.

Every scenario drives the REAL handlers end-to-end (stdin -> stdout JSON /
exit code), the same harness shape as `test_auto_root_bash_lockdown.py` and
`test_k3a_additional_context_channel.py`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from des.adapters.drivers.hooks import pre_tool_use_handler, pre_write_handler


def _home_no_global_opinion(tmp_path: Path) -> Path:
    """A disposable HOME with no global config at all -- the ADR-AG-002
    fresh-install default (``opt-in``, no marker declared)."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    return home


def _repo(tmp_path: Path, *, activated: bool) -> Path:
    """A repo under a SEPARATE tmp_path branch (never under HOME, so the
    legacy marker walk-up never accidentally finds anything from HOME)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    if activated:
        marker_dir = repo / ".nwave"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "local-config.json").write_text(
            json.dumps({"enabled_for_repo": True}), encoding="utf-8"
        )
    return repo


def _bash_stdin(repo: Path, *, transcript_path: str | None = None) -> str:
    payload: dict[str, object] = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "cwd": str(repo),
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _write_stdin(repo: Path, *, transcript_path: str | None = None) -> str:
    payload: dict[str, object] = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(repo / "NOTES.md")},
        "cwd": str(repo),
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _agent_stdin(repo: Path, *, transcript_path: str | None, subagent_type: str) -> str:
    payload: dict[str, object] = {
        "tool_name": "Agent",
        "tool_input": {"prompt": "do the thing", "subagent_type": subagent_type},
        "cwd": str(repo),
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _send_message_stdin(repo: Path, *, transcript_path: str | None) -> str:
    payload: dict[str, object] = {
        "tool_name": "SendMessage",
        "tool_input": {"to": "somebody", "message": "hi"},
        "cwd": str(repo),
    }
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return json.dumps(payload)


def _mode_select_marker_transcript(tmp_path: Path, selection: str) -> str:
    transcript = tmp_path / "transcript.jsonl"
    entries = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "nw-mode-select"},
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": f"NW-MODE-SELECTED: {selection}"}]
            },
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return str(transcript)


def _nw_auto_engaged_transcript(tmp_path: Path) -> str:
    transcript = tmp_path / "transcript.jsonl"
    entries = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
                ]
            },
        },
    ]
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return str(transcript)


def _run_pre_tool_use(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    return exit_code, (json.loads(out) if out else None)


def _run_pre_write(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_write_handler.handle_pre_write()
    out = capsys.readouterr().out.strip()
    return exit_code, (json.loads(out) if out else None)


# --- 1. the FIRST-Bash nag (Site B), the exact scope-capture trigger --------


def test_first_bash_in_unactivated_repo_is_not_forced_through_mode_select(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """FALSIFIER: the exact reported symptom -- a first Bash call in a repo
    that never declared the nWave opt-in must NOT be blocked for lacking a
    mode-select marker."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=False)

    exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, _bash_stdin(repo))

    assert exit_code != 2 or (payload or {}).get("reason") != (
        "Invoke nw-mode-select before the first Bash/Write/Edit."
    ), (
        f"an unactivated repo's first Bash must never be forced through "
        f"nw-mode-select -- got exit={exit_code} payload={payload!r}"
    )


def test_first_bash_in_activated_repo_still_requires_mode_select(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """NEGATIVE CONTROL, the vincolo di merito: a repo that DID declare the
    opt-in keeps the existing, correct behaviour -- unchanged."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=True)

    exit_code, payload = _run_pre_tool_use(monkeypatch, capsys, _bash_stdin(repo))

    assert exit_code == 2
    assert payload is not None
    assert (
        payload.get("reason")
        == "Invoke nw-mode-select before the first Bash/Write/Edit."
    )


# --- 2. the FIRST-Write/Edit nag, the sibling trigger for mutations --------


def test_first_write_in_unactivated_repo_is_not_forced_through_mode_select(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """The Write/Edit sibling of the Bash trap (`pre_write_handler.py`) --
    `is_nwave_adjacent_write` filters by path shape only, never by repo
    activation, so it fired identically."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=False)

    exit_code, payload = _run_pre_write(monkeypatch, capsys, _write_stdin(repo))

    assert exit_code != 2 or (payload or {}).get("reason") != (
        "Invoke nw-mode-select before the first mutation."
    ), f"got exit={exit_code} payload={payload!r}"


def test_first_write_in_activated_repo_still_requires_mode_select(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """NEGATIVE CONTROL for the Write/Edit path."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=True)

    exit_code, payload = _run_pre_write(monkeypatch, capsys, _write_stdin(repo))

    assert exit_code == 2
    assert payload is not None
    assert payload.get("reason") == "Invoke nw-mode-select before the first mutation."


# --- 3. the AUTO_PENDING handoff trap (Site A) -- the beta user's exact text --


def test_auto_pending_handoff_trap_scoped_to_activated_repo(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """FALSIFIER: the SPECIFIC reported trap text -- 'Invoke Skill(nw-auto)
    as the next tool call' -- must never fire in an unactivated repo."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=False)
    transcript_path = _mode_select_marker_transcript(tmp_path, "auto M")

    exit_code, payload = _run_pre_tool_use(
        monkeypatch,
        capsys,
        _agent_stdin(repo, transcript_path=transcript_path, subagent_type="nw-crafter"),
    )

    assert exit_code != 2 or "Invoke Skill(nw-auto)" not in (payload or {}).get(
        "reason", ""
    ), f"got exit={exit_code} payload={payload!r}"


def test_auto_pending_handoff_trap_still_fires_in_activated_repo(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """NEGATIVE CONTROL: an activated repo keeps the existing trap
    unchanged -- this is what protects a REAL Auto M/L run."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=True)
    transcript_path = _mode_select_marker_transcript(tmp_path, "auto M")

    exit_code, payload = _run_pre_tool_use(
        monkeypatch,
        capsys,
        _agent_stdin(repo, transcript_path=transcript_path, subagent_type="nw-crafter"),
    )

    assert exit_code == 2
    assert "Invoke Skill(nw-auto)" in (payload or {}).get("reason", "")


# --- 4. the vincolo di merito: AUTO_ENGAGED lockdown stays unconditional --


def test_auto_engaged_lockdown_still_fires_regardless_of_repo_activation(
    monkeypatch, capsys, audit_events, tmp_path: Path
) -> None:
    """The AUTO_ENGAGED SendMessage lockdown must NOT be weakened by this
    fix -- once `nw-auto` was genuinely observed, real delivery machinery is
    in flight and the protection applies regardless of this repo's own
    config."""
    monkeypatch.setenv("HOME", str(_home_no_global_opinion(tmp_path)))
    repo = _repo(tmp_path, activated=False)
    transcript_path = _nw_auto_engaged_transcript(tmp_path)

    exit_code, payload = _run_pre_tool_use(
        monkeypatch,
        capsys,
        _send_message_stdin(repo, transcript_path=transcript_path),
    )

    assert exit_code == 2, (
        f"the AUTO_ENGAGED lockdown must stay unconditional even in an "
        f"unactivated repo -- got exit={exit_code} payload={payload!r}"
    )
    assert payload is not None
    assert payload.get("decision") == "block"
