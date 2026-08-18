"""K4 Run 6 evidence: Auto-root PO dispatch envelope.

The root hand-authored the PO dispatch prompt, was rejected by the hook
twice (`WHAT: Auto-root design-consult header malformed -- ... first bytes
are not exactly one ARCHITECTURE-COVERED: <path>#<anchor> line`), then
forwarded the architecture anchor into PO's own context on the next retry
(`CHARTER-AUTHOR-DISQUALIFIED` -- a matrix row 10 regression, PO refuses to
author a charter the instant its context carries an architecture-authority
anchor), ~8 minutes lost across the thrash. The hook's own PO gate used to
REQUIRE that exact anchor as the prompt's first bytes -- directly
contradicting PO's own role-level refusal of it. `des resolve-charters`
now prints the exact four-line value-only envelope
(`des.application.ordinary_request.build_po_envelope`) on `AUTHOR`; this
gate accepts ONLY that shape, with no architecture anchor anywhere in it.
Drives the real handler end-to-end (stdin -> stdout JSON / exit code), the
same harness shape as `test_auto_root_atd_body_gate.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler
from des.application.ordinary_request import build_po_envelope, compute_delivery_id


_PO = "nw-product-owner"
_PO_ENVELOPE_GATE_SIGNATURE = "Auto-root PO dispatch envelope malformed"

_VALID_DELIVERY_ID = compute_delivery_id("Ship the widget end to end.")
_VALID_NAMESPACE = f"docs/product/expectations/{_VALID_DELIVERY_ID}"
_VALID_ROOT = "/abs/repo/root"
_VALID_SEED_TEXT = "Ship the widget end to end."

_VALID_ARCH_HEADER = "ARCHITECTURE-COVERED: docs/architecture/adrs/adr-1.md#decision"


def _po_envelope(
    *,
    delivery_id: str = _VALID_DELIVERY_ID,
    namespace: str = _VALID_NAMESPACE,
    root: str = _VALID_ROOT,
    value_seed: str = _VALID_SEED_TEXT,
) -> str:
    return build_po_envelope(
        delivery_id=delivery_id, namespace=namespace, root=root, value_seed=value_seed
    )


_VALID_PO_ENVELOPE = _po_envelope()


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


class TestPoEnvelopeAcceptsOnlyTheEmittedFourLineShape:
    @pytest.mark.parametrize(
        "prompt",
        [
            _VALID_PO_ENVELOPE,
            _po_envelope(root=r"ROOT: C:\repo\root".removeprefix("ROOT: ")),
            _po_envelope(value_seed='A seed with "quotes" and | pipes.'),
            _po_envelope(namespace="docs/product/expectations/auto-0123456789abcdef"),
        ],
        ids=["canonical", "windows_root", "seed_special_chars", "other_namespace"],
    )
    def test_valid_envelope_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path, prompt
    ) -> None:
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": prompt, "subagent_type": _PO},
                transcript_path=_transcript(tmp_path, auto=True),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _PO_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", "")


class TestPoEnvelopeRejectsMalformedOrContaminatedPrompts:
    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            (
                "hand_authored_with_architecture_anchor_prefix",
                f"{_VALID_ARCH_HEADER}\n\n{_VALID_PO_ENVELOPE}",
            ),
            (
                "hand_authored_bare_architecture_anchor_only",
                _VALID_ARCH_HEADER,
            ),
            (
                "architecture_anchor_inside_value_seed_field_only",
                _po_envelope(value_seed=_VALID_ARCH_HEADER),
            ),
            (
                "legacy_delivery_id_namespace_root_value_seed_no_json_encoding",
                "\n".join(
                    [
                        f"DELIVERY-ID: {_VALID_DELIVERY_ID}",
                        f"NAMESPACE: {_VALID_NAMESPACE}",
                        f"ROOT: {_VALID_ROOT}",
                        f"VALUE-SEED: {_VALID_SEED_TEXT}",
                    ]
                ),
            ),
            ("missing_one_line", "\n".join(_VALID_PO_ENVELOPE.splitlines()[:-1])),
            ("extra_trailing_line", _VALID_PO_ENVELOPE + "\nEXTRA: context"),
            (
                "reordered_facts",
                "\n".join(
                    [
                        f"NAMESPACE: {_VALID_NAMESPACE}",
                        f"DELIVERY-ID: {_VALID_DELIVERY_ID}",
                        f"ROOT: {_VALID_ROOT}",
                        f'VALUE-SEED: "{_VALID_SEED_TEXT}"',
                    ]
                ),
            ),
            ("empty_delivery_id", _po_envelope(delivery_id="")),
            ("empty_namespace", _po_envelope(namespace="")),
            ("empty_root", _po_envelope(root="")),
            ("only_whitespace_prompt", "   "),
            ("empty_prompt", ""),
        ],
    )
    def test_malformed_or_contaminated_prompt_blocks_with_this_gates_signature(
        self, monkeypatch, capsys, audit_events, tmp_path, case_id, prompt
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": prompt, "subagent_type": _PO},
                transcript_path=_transcript(tmp_path, auto=True),
            ),
        )
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _PO_ENVELOPE_GATE_SIGNATURE in payload["reason"], case_id


class TestExcludedDispatchIsNotBlockedByThisGate:
    @pytest.mark.parametrize(
        "case_id,auto_observed,role,identity",
        [
            ("no_auto_observed", False, _PO, {}),
            ("subagent_identity_agent_id", True, _PO, {"agent_id": "sub-1"}),
            ("subagent_identity_agent_type", True, _PO, {"agent_type": "nw-crafter"}),
            ("non_exact_role", True, "nw-product-owner-reviewer", {}),
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
            assert _PO_ENVELOPE_GATE_SIGNATURE not in payload.get("reason", ""), case_id


class TestSkillDocPointsAtTheProducingTool:
    """`nw-auto/SKILL.md` must route root to `resolve-charters`' printed
    envelope, never to hand-authoring one -- the exact Run 6 defect."""

    def test_skill_names_resolve_charters_envelope_never_hand_authored(self) -> None:
        from pathlib import Path

        skill_text = (
            Path(__file__).resolve().parents[6]
            / "nWave"
            / "skills"
            / "nw-auto"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        assert "des resolve-charters" in skill_text
        assert "verbatim" in skill_text
        assert (
            "never author" in skill_text.lower()
            or "never hand-author" in skill_text.lower()
        )
