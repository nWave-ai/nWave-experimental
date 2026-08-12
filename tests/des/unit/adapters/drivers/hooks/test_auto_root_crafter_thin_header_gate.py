"""K4 architecture gap: Auto-root crafter first-dispatch THIN header gate.

Empirically, real Auto root prefixed prose/duplicated JSON before the ATD-
authored THIN-DELIVERY-CONTRACT header, dispatched `nw-software-crafter`
anyway, and only got `AUTHORITY_REFUSED` back from the crafter itself --
after wave/service activation had already run. This gate makes the
first-bytes contract a deterministic PreToolUse/Agent boundary: a malformed
header on a confirmed Auto-root -> exact-crafter-role dispatch is blocked
BEFORE any downstream wave/service activation, mirroring the harness shape
of `test_auto_root_bash_lockdown.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


_VALID_LOCATOR = "docs/feature/thin/design/thin-delivery-contract.json"
_VALID_DIGEST = "sha256:" + "a" * 64
_VALID_HEADER = f"THIN-DELIVERY-CONTRACT: {_VALID_LOCATOR}\nTHIN-DELIVERY-CONTRACT-DIGEST: {_VALID_DIGEST}"

_CRAFTER_THIN_GATE_SIGNATURE = "Auto-root crafter thin authority malformed"


def _transcript(tmp_path, *, auto: bool) -> str:
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    if auto:
        lines.append(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
        )
    transcript.write_text(
        "\n".join(json.dumps(line) for line in lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    return str(transcript)


def _stdin(
    *,
    tool_name: str,
    tool_input: dict,
    transcript_path: str | None = None,
    **identity: str,
) -> str:
    payload: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestValidThinHeaderPassesGateForBothParadigms:
    @pytest.mark.parametrize(
        "role", ["nw-software-crafter", "nw-functional-software-crafter"]
    )
    def test_valid_header_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path, role
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": _VALID_HEADER, "subagent_type": role},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _CRAFTER_THIN_GATE_SIGNATURE not in payload.get("reason", "")


class TestMalformedThinHeaderBlocksBeforeDownstreamActivation:
    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            (
                "prose_prefix",
                "Please read this context first.\n" + _VALID_HEADER,
            ),
            (
                "bad_digest_length",
                "THIN-DELIVERY-CONTRACT: "
                + _VALID_LOCATOR
                + "\nTHIN-DELIVERY-CONTRACT-DIGEST: sha256:"
                + "a" * 10,
            ),
            (
                "uppercase_hex",
                "THIN-DELIVERY-CONTRACT: "
                + _VALID_LOCATOR
                + "\nTHIN-DELIVERY-CONTRACT-DIGEST: sha256:"
                + "A" * 64,
            ),
            (
                "missing_blank_line_before_context",
                _VALID_HEADER + "\nextra context immediately",
            ),
            (
                "duplicate_header",
                _VALID_HEADER + "\n\nTHIN-DELIVERY-CONTRACT: " + _VALID_LOCATOR,
            ),
            (
                "absolute_locator",
                "THIN-DELIVERY-CONTRACT: /etc/thin-delivery-contract.json\n"
                "THIN-DELIVERY-CONTRACT-DIGEST: " + _VALID_DIGEST,
            ),
            (
                "dotdot_locator",
                "THIN-DELIVERY-CONTRACT: ../thin-delivery-contract.json\n"
                "THIN-DELIVERY-CONTRACT-DIGEST: " + _VALID_DIGEST,
            ),
            ("missing_header", "Do the work"),
        ],
    )
    def test_malformed_header_blocks_before_service_creation(
        self, monkeypatch, capsys, audit_events, tmp_path, case_id, prompt
    ) -> None:
        def _boom(*args, **kwargs):
            raise AssertionError(
                f"downstream service must not be created on a blocked "
                f"crafter thin-header dispatch ({case_id})"
            )

        monkeypatch.setattr(
            pre_tool_use_handler.service_factory,
            "create_wave_activation_service",
            _boom,
        )
        monkeypatch.setattr(
            pre_tool_use_handler.service_factory,
            "create_pre_tool_use_service",
            _boom,
        )
        transcript_path = _transcript(tmp_path, auto=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={
                    "prompt": prompt,
                    "subagent_type": "nw-software-crafter",
                },
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _CRAFTER_THIN_GATE_SIGNATURE in payload["reason"], case_id


class TestScopeExclusionsPassThisSpecificGate:
    @pytest.mark.parametrize(
        "case_id,auto_observed,role,identity",
        [
            ("no_auto_observed", False, "nw-software-crafter", {}),
            (
                "subagent_identity_agent_id",
                True,
                "nw-software-crafter",
                {"agent_id": "sub-1"},
            ),
            (
                "subagent_identity_agent_type",
                True,
                "nw-software-crafter",
                {"agent_type": "nw-crafter"},
            ),
            ("non_exact_crafter_role", True, "nw-crafter", {}),
        ],
    )
    def test_excluded_dispatch_is_not_blocked_by_this_gate(
        self,
        monkeypatch,
        capsys,
        audit_events,
        tmp_path,
        case_id,
        auto_observed,
        role,
        identity,
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=auto_observed)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": "Do the work", "subagent_type": role},
                transcript_path=transcript_path,
                **identity,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _CRAFTER_THIN_GATE_SIGNATURE not in payload.get("reason", ""), (
                case_id
            )
