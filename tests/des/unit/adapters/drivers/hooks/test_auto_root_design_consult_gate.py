"""K4 architecture-readiness gate: Auto-root PO/ATD first-dispatch header.

Prevents PO/ATD launch before architecture readiness: a confirmed Auto-root
dispatch to the exact `nw-product-owner` / `nw-acceptance-designer` role must
carry a well-formed `ARCHITECTURE-COVERED:` or `ARCHITECTURE-NO-IMPACT:`
`<repo-relative-permanent-path>.md#<anchor>` reference as the prompt's first
bytes, mirroring the harness shape of `test_auto_root_crafter_thin_header_gate.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


_VALID_PATH = "docs/product/architecture/adr-ssot-document-model.md"
_VALID_ANCHOR = "decision"
_VALID_COVERED = f"ARCHITECTURE-COVERED: {_VALID_PATH}#{_VALID_ANCHOR}"
_VALID_NO_IMPACT = f"ARCHITECTURE-NO-IMPACT: {_VALID_PATH}#{_VALID_ANCHOR}"

_DESIGN_CONSULT_GATE_SIGNATURE = "Auto-root design-consult header malformed"

_PO = "nw-product-owner"
_ATD = "nw-acceptance-designer"


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


class TestValidArchitectureHeaderPassesGateForBothRoles:
    @pytest.mark.parametrize("role", [_PO, _ATD])
    @pytest.mark.parametrize("header", [_VALID_COVERED, _VALID_NO_IMPACT])
    def test_valid_header_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path, role, header
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": header, "subagent_type": role},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _DESIGN_CONSULT_GATE_SIGNATURE not in payload.get("reason", "")


class TestMalformedArchitectureHeaderBlocksBeforeDownstreamActivation:
    @pytest.mark.parametrize("role", [_PO, _ATD])
    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            ("prose_prefix", "Please read this context first.\n" + _VALID_COVERED),
            ("no_header", "Do the work"),
            (
                "absolute_path",
                "ARCHITECTURE-COVERED: /etc/passwd.md#decision",
            ),
            (
                "dotdot_path",
                "ARCHITECTURE-COVERED: ../secret.md#decision",
            ),
            (
                "non_md_suffix",
                "ARCHITECTURE-COVERED: docs/product/vision.txt#decision",
            ),
            (
                "no_anchor",
                "ARCHITECTURE-COVERED: docs/product/vision.md",
            ),
            (
                "empty_anchor",
                "ARCHITECTURE-COVERED: docs/product/vision.md#",
            ),
            (
                "bad_anchor_uppercase",
                "ARCHITECTURE-COVERED: docs/product/vision.md#Decision",
            ),
            (
                "missing_blank_line_before_context",
                _VALID_COVERED + "\nextra context immediately",
            ),
            (
                "duplicate_header",
                _VALID_COVERED
                + "\n\nARCHITECTURE-COVERED: "
                + _VALID_PATH
                + "#"
                + _VALID_ANCHOR,
            ),
        ],
    )
    def test_malformed_header_blocks_before_service_creation(
        self, monkeypatch, capsys, audit_events, tmp_path, role, case_id, prompt
    ) -> None:
        def _boom(*args, **kwargs):
            raise AssertionError(
                f"downstream service must not be created on a blocked "
                f"design-consult dispatch ({case_id})"
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
                tool_input={"prompt": prompt, "subagent_type": role},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _DESIGN_CONSULT_GATE_SIGNATURE in payload["reason"], case_id


class TestScopeExclusionsPassThisSpecificGate:
    @pytest.mark.parametrize(
        "case_id,auto_observed,role,identity",
        [
            ("no_auto_observed", False, _PO, {}),
            ("subagent_identity_agent_id", True, _PO, {"agent_id": "sub-1"}),
            (
                "subagent_identity_agent_type",
                True,
                _ATD,
                {"agent_type": "nw-crafter"},
            ),
            ("non_exact_role_reviewer", True, "nw-product-owner-reviewer", {}),
            ("other_nw_role", True, "nw-software-crafter", {}),
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
            assert _DESIGN_CONSULT_GATE_SIGNATURE not in payload.get("reason", ""), (
                case_id
            )
