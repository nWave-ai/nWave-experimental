"""K4 camp7 evidence, 2026-08-23: Auto-root architect repair-consult envelope.

`des compile-contract` correctly rejected the architect's own authored
target-declaration table, exhaustively, naming every offending row --
verified against the exact installed runtime camp7 used. But when root
re-dispatched the architect to repair it, the ONLY documented shape for an
`AUTO-ARCHITECTURE-CONSULT` prompt was three fixed header lines, declared
"the entire prompt" -- structurally unable to carry a multi-line rejection.
This gate's own OLD form enforced that literally: `len(lines) != 3` blocked
ANYTHING beyond the three header lines, so even a root that WANTED to
forward the rejection verbatim could not -- the correct form was
unrepresentable (GDP-0). Root hand-paraphrased instead, omitting the
Target-cell defect the paraphrase never mentioned; three dispatches (442.4s,
15.3% of the arm's wall) were needed to converge.

This gate now ALSO accepts an OPTIONAL fourth field, the SAME quoted-
heredoc discipline `_is_value_seed_stdin_heredoc` already enforces for
NW_SEED, carrying the producer's exact BLOCKED stdout verbatim:

    AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
    AUTO-ARCHITECTURE-ROOT: <absolute-root>
    AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>
    AUTO-ARCHITECTURE-REJECTION: <<'NW_REJECTION'
    <producer's exact BLOCKED stdout, byte-for-byte>
    NW_REJECTION

The base three-line shape is unchanged, byte-identical -- a fresh, non-
repair consult is unaffected. Drives the real handler end-to-end (stdin ->
stdout JSON / exit code), the same harness shape as
`test_auto_root_po_envelope_gate.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


_ARCHITECT = "nw-solution-architect"
_ARCHITECT_ENVELOPE_GATE_SIGNATURE = "Auto-root architect envelope malformed"

_VALID_CONSULT = (
    "AUTO-ARCHITECTURE-CONSULT: Repair docs/product/architecture/brief.md#widget"
)
_VALID_ROOT = "AUTO-ARCHITECTURE-ROOT: /abs/repo/root"
_VALID_ROUTE = "AUTO-DELIVERY-ROUTE: RED_TO_GREEN"

_VALID_BASE_ENVELOPE = "\n".join([_VALID_CONSULT, _VALID_ROOT, _VALID_ROUTE])

_REJECTION_HEADER = "AUTO-ARCHITECTURE-REJECTION: <<'NW_REJECTION'"
_REJECTION_BODY = (
    "BLOCKED: 7 problems found in one pass -- each is independent; fix them all, "
    "then re-run.\n"
    "(1/7) WHAT: target-declaration-table: target-declaration table row for "
    "'Storage of window schedule/duration' declares decision \"New Check."
    'maintenance_windows = ...", outside EXTEND|CREATE_NEW WHY: the Decision '
    "column is the targetPlan schema's closed vocabulary; transcription never "
    "widens or reinterprets it HOW: declare EXTEND or CREATE_NEW for the row"
)
_REJECTION_TERMINATOR = "NW_REJECTION"


def _repair_envelope(*, body: str = _REJECTION_BODY) -> str:
    return "\n".join(
        [_VALID_BASE_ENVELOPE, _REJECTION_HEADER, body, _REJECTION_TERMINATOR]
    )


_VALID_REPAIR_ENVELOPE = _repair_envelope()


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


def _dispatch(monkeypatch, capsys, tmp_path, prompt: str) -> tuple[int, dict | None]:
    return _run(
        monkeypatch,
        capsys,
        _stdin(
            tool_name="Agent",
            tool_input={"prompt": prompt, "subagent_type": _ARCHITECT},
            transcript_path=_transcript(tmp_path, auto=True),
        ),
    )


class TestBaseThreeLineConsultIsUnchanged:
    def test_fresh_consult_still_passes_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        _exit_code, payload = _dispatch(
            monkeypatch, capsys, tmp_path, _VALID_BASE_ENVELOPE
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", "")


class TestRepairConsultAcceptsAWellFormedVerbatimRejectionCarrier:
    def test_valid_repair_envelope_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        _exit_code, payload = _dispatch(
            monkeypatch, capsys, tmp_path, _VALID_REPAIR_ENVELOPE
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", "")

    def test_multiline_rejection_body_is_accepted(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        multiline_body = _REJECTION_BODY + "\n" + "(2/7) WHAT: a second row problem"
        _exit_code, payload = _dispatch(
            monkeypatch, capsys, tmp_path, _repair_envelope(body=multiline_body)
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", "")


class TestRepairConsultRejectsAnythingOtherThanTheWellFormedCarrier:
    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            (
                "hand_paraphrase_one_extra_line_no_heredoc",
                _VALID_BASE_ENVELOPE
                + "\ndes compile-contract rejected the table, fix the "
                "Decision column.",
            ),
            (
                "empty_rejection_carrier_header_then_terminator_only",
                "\n".join([_VALID_BASE_ENVELOPE, _REJECTION_HEADER, "NW_REJECTION"]),
            ),
            (
                "unquoted_heredoc_delimiter",
                "\n".join(
                    [
                        _VALID_BASE_ENVELOPE,
                        "AUTO-ARCHITECTURE-REJECTION: <<NW_REJECTION",
                        _REJECTION_BODY,
                        _REJECTION_TERMINATOR,
                    ]
                ),
            ),
            (
                "missing_terminator",
                "\n".join([_VALID_BASE_ENVELOPE, _REJECTION_HEADER, _REJECTION_BODY]),
            ),
            (
                "trailing_content_after_terminator",
                _VALID_REPAIR_ENVELOPE + "\nEXTRA: context",
            ),
            (
                "wrong_delimiter",
                "\n".join(
                    [
                        _VALID_BASE_ENVELOPE,
                        "AUTO-ARCHITECTURE-REJECTION: <<'WRONG_DELIM'",
                        _REJECTION_BODY,
                        "WRONG_DELIM",
                    ]
                ),
            ),
        ],
    )
    def test_malformed_repair_carrier_blocks_with_this_gates_signature(
        self, monkeypatch, capsys, audit_events, tmp_path, case_id, prompt
    ) -> None:
        exit_code, payload = _dispatch(monkeypatch, capsys, tmp_path, prompt)
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE in payload["reason"], case_id


class TestExcludedDispatchIsNotBlockedByThisGate:
    @pytest.mark.parametrize(
        "case_id,auto_observed,role,identity",
        [
            ("no_auto_observed", False, _ARCHITECT, {}),
            ("subagent_identity_agent_id", True, _ARCHITECT, {"agent_id": "sub-1"}),
            (
                "subagent_identity_agent_type",
                True,
                _ARCHITECT,
                {"agent_type": "nw-crafter"},
            ),
            ("other_nw_role", True, "nw-acceptance-designer", {}),
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
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={
                    "prompt": "hand-authored, not this gate's shape",
                    "subagent_type": role,
                },
                transcript_path=_transcript(tmp_path, auto=auto_observed),
                **identity,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ARCHITECT_ENVELOPE_GATE_SIGNATURE not in payload.get(
                "reason", ""
            ), case_id
