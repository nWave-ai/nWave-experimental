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
_VALID_COVERED_UNDERSCORE = f"ARCHITECTURE-COVERED: {_VALID_PATH}#maintenance_windows"
_VALID_COVERED_UNICODE = f"ARCHITECTURE-COVERED: {_VALID_PATH}#decisione-è-valida"

_DESIGN_CONSULT_GATE_SIGNATURE = "Auto-root design-consult header malformed"
_ATD_BODY_GATE_SIGNATURE = "Auto-root ATD dispatch body malformed"
_ARCHITECT_ENVELOPE_GATE_SIGNATURE = "Auto-root architect envelope malformed"

_PO = "nw-product-owner"
_ATD = "nw-acceptance-designer"
_ARCHITECT = "nw-solution-architect"

_VALID_ROOT = "/abs/repo/root"
_VALID_VALUE_SEED_LINE = "VALUE-SEED: Implement the widget end to end."
_VALID_ROUTE_RED_LINE = "DELIVERY-ROUTE: RED_TO_GREEN"
_VALID_ROUTE_GREEN_LINE = "DELIVERY-ROUTE: GREEN_TO_GREEN"


def _atd_body(
    *,
    header: str = _VALID_COVERED,
    root_line: str = f"ROOT: {_VALID_ROOT}",
    value_seed_line: str = _VALID_VALUE_SEED_LINE,
    route_line: str = _VALID_ROUTE_RED_LINE,
    blank_line: str = "",
) -> str:
    return "\n".join([header, blank_line, root_line, value_seed_line, route_line])


_VALID_ATD_BODY_RED = _atd_body()
_VALID_ATD_BODY_GREEN = _atd_body(route_line=_VALID_ROUTE_GREEN_LINE)
_VALID_ATD_BODY_WINDOWS = _atd_body(root_line=r"ROOT: C:\repo\root")


def _architect_envelope(
    *,
    consult_line: str = "AUTO-ARCHITECTURE-CONSULT: bounded subject",
    root_line: str = f"AUTO-ARCHITECTURE-ROOT: {_VALID_ROOT}",
    route_line: str = "AUTO-DELIVERY-ROUTE: RED_TO_GREEN",
) -> str:
    return "\n".join([consult_line, root_line, route_line])


_VALID_ARCHITECT_ENVELOPE_RED = _architect_envelope()
_VALID_ARCHITECT_ENVELOPE_GREEN = _architect_envelope(
    route_line="AUTO-DELIVERY-ROUTE: GREEN_TO_GREEN"
)
_VALID_ARCHITECT_ENVELOPE_WINDOWS = _architect_envelope(
    root_line=r"AUTO-ARCHITECTURE-ROOT: C:\repo\root"
)


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


class TestValidArchitectureHeaderPassesGateForProductOwner:
    @pytest.mark.parametrize("role", [_PO])
    @pytest.mark.parametrize(
        "header",
        [
            _VALID_COVERED,
            _VALID_NO_IMPACT,
            _VALID_COVERED_UNDERSCORE,
            _VALID_COVERED_UNICODE,
        ],
    )
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
    @pytest.mark.parametrize("role", [_PO])
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
                "bad_anchor_punctuation",
                "ARCHITECTURE-COVERED: docs/product/vision.md#decision?",
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


@pytest.mark.parametrize(
    "prompt",
    [
        _VALID_ATD_BODY_RED,
        _VALID_ATD_BODY_GREEN,
        _VALID_ATD_BODY_WINDOWS,
        _atd_body(header=_VALID_COVERED_UNDERSCORE),
        _atd_body(header=_VALID_COVERED_UNICODE),
    ],
)
def test_atd_accepts_only_the_compiled_five_line_body(
    monkeypatch, capsys, audit_events, tmp_path, prompt
) -> None:
    _exit_code, payload = _run(
        monkeypatch,
        capsys,
        _stdin(
            tool_name="Agent",
            tool_input={"prompt": prompt, "subagent_type": _ATD},
            transcript_path=_transcript(tmp_path, auto=True),
        ),
    )
    if payload is not None and payload.get("decision") == "block":
        assert _ATD_BODY_GATE_SIGNATURE not in payload.get("reason", "")


@pytest.mark.parametrize(
    "prompt",
    [
        _VALID_COVERED,
        _atd_body(blank_line="not blank"),
        _atd_body(root_line="ROOT: relative"),
        _atd_body(value_seed_line="VALUE-SEED: "),
        _atd_body(route_line="DELIVERY-ROUTE: UNKNOWN"),
        _VALID_ATD_BODY_RED + "\nextra",
    ],
)
def test_atd_rejects_missing_inferred_or_extra_context(
    monkeypatch, capsys, audit_events, tmp_path, prompt
) -> None:
    exit_code, payload = _run(
        monkeypatch,
        capsys,
        _stdin(
            tool_name="Agent",
            tool_input={"prompt": prompt, "subagent_type": _ATD},
            transcript_path=_transcript(tmp_path, auto=True),
        ),
    )
    assert exit_code == 2
    assert _ATD_BODY_GATE_SIGNATURE in payload["reason"]


@pytest.mark.parametrize(
    "prompt",
    [
        _VALID_ARCHITECT_ENVELOPE_RED,
        _VALID_ARCHITECT_ENVELOPE_GREEN,
        _VALID_ARCHITECT_ENVELOPE_WINDOWS,
    ],
)
def test_architect_accepts_only_the_upstream_route_envelope(
    monkeypatch, capsys, audit_events, tmp_path, prompt
) -> None:
    _exit_code, payload = _run(
        monkeypatch,
        capsys,
        _stdin(
            tool_name="Agent",
            tool_input={"prompt": prompt, "subagent_type": _ARCHITECT},
            transcript_path=_transcript(tmp_path, auto=True),
        ),
    )
    if payload is not None and payload.get("decision") == "block":
        assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", "")


@pytest.mark.parametrize(
    "prompt",
    [
        "\n".join(_VALID_ARCHITECT_ENVELOPE_RED.splitlines()[:2]),
        _architect_envelope(consult_line="AUTO-ARCHITECTURE-CONSULT: "),
        _architect_envelope(root_line="AUTO-ARCHITECTURE-ROOT: relative"),
        _architect_envelope(route_line="AUTO-DELIVERY-ROUTE: UNKNOWN"),
        _VALID_ARCHITECT_ENVELOPE_RED + "\nextra",
    ],
)
def test_architect_rejects_missing_inferred_or_extra_context(
    monkeypatch, capsys, audit_events, tmp_path, prompt
) -> None:
    exit_code, payload = _run(
        monkeypatch,
        capsys,
        _stdin(
            tool_name="Agent",
            tool_input={"prompt": prompt, "subagent_type": _ARCHITECT},
            transcript_path=_transcript(tmp_path, auto=True),
        ),
    )
    assert exit_code == 2
    assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE in payload["reason"]
