"""K4 architecture gap: Auto-root ATD dispatch body envelope.

The checked-in `nw-auto` (ADR-SSOT-002 Section 4c) requires an Auto-root ATD
dispatch to carry the architecture authority line, one blank line, and the
twelve named non-empty facts below -- in this exact order -- so ATD never
infers or defaults an upstream fact. Drives the real handler end-to-end
(stdin -> stdout JSON / exit code), the same harness shape as
`test_auto_root_bash_lockdown.py`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler
from des.application.ordinary_request import compute_delivery_id, contract_locator_for


_REPO_ROOT = Path(__file__).resolve().parents[6]
_NW_AUTO_SKILL_MD = _REPO_ROOT / "nWave" / "skills" / "nw-auto" / "SKILL.md"
_ATD_AGENT_MD = _REPO_ROOT / "nWave" / "agents" / "nw-acceptance-designer.md"


_ATD = "nw-acceptance-designer"
_ATD_BODY_GATE_SIGNATURE = "Auto-root ATD dispatch body malformed"

_VALID_PATH = "docs/product/architecture/adr-ssot-document-model.md"
_VALID_ANCHOR = "decision"
_VALID_HEADER = f"ARCHITECTURE-COVERED: {_VALID_PATH}#{_VALID_ANCHOR}"

# OUTCOME and VALUE-SEED are the SAME immutable value seed text, compiled by
# `des prepare-ordinary-request` as compact JSON string literals
# (`json.dumps(text, ensure_ascii=False)`), so DELIVERY-ID/CONTRACT-LOCATOR
# below are the real recomputed projection, never a hand-picked constant.
_VALID_SEED_TEXT = "Ship the widget end to end."
_VALID_SEED_JSON = json.dumps(_VALID_SEED_TEXT, ensure_ascii=False)
_VALID_DELIVERY_ID_VALUE = compute_delivery_id(_VALID_SEED_TEXT)

_VALID_CONTRACT_LOCATOR = (
    f"CONTRACT-LOCATOR: {contract_locator_for(_VALID_DELIVERY_ID_VALUE)}"
)
_VALID_CONTRACT_SCHEMA = (
    "CONTRACT-SCHEMA: /home/user/.claude/lib/nWave/schemas/"
    "thin-delivery-contract.schema.json"
)
_VALID_DELIVERY_ID = f"DELIVERY-ID: {_VALID_DELIVERY_ID_VALUE}"
_VALID_OUTCOME = f"OUTCOME: {_VALID_SEED_JSON}"
_VALID_ROOT = "ROOT: /abs/repo/root"
_VALID_BASE_REVISION = "BASE-REVISION: git-sha1:" + "a" * 40
_VALID_ROUTE = "DELIVERY-ROUTE: RED_TO_GREEN"
_VALID_EXAMINE = "EXAMINE: true"
_VALID_INDEPENDENT_REVIEW = "INDEPENDENT-REVIEW: false"
_VALID_BUDGET_TOKEN_LIMIT = "BUDGET-TOKEN-LIMIT: 2000000"
_VALID_BUDGET_WALL_CLOCK_MINUTES = "BUDGET-WALL-CLOCK-MINUTES: 30"
_VALID_VALUE_SEED = f"VALUE-SEED: {_VALID_SEED_JSON}"


def _atd_body(
    *,
    header: str = _VALID_HEADER,
    blank_line: str = "",
    contract_locator_line: str = _VALID_CONTRACT_LOCATOR,
    contract_schema_line: str = _VALID_CONTRACT_SCHEMA,
    delivery_id_line: str = _VALID_DELIVERY_ID,
    outcome_line: str = _VALID_OUTCOME,
    root_line: str = _VALID_ROOT,
    base_revision_line: str = _VALID_BASE_REVISION,
    route_line: str = _VALID_ROUTE,
    examine_line: str = _VALID_EXAMINE,
    independent_review_line: str = _VALID_INDEPENDENT_REVIEW,
    budget_token_limit_line: str = _VALID_BUDGET_TOKEN_LIMIT,
    budget_wall_clock_minutes_line: str = _VALID_BUDGET_WALL_CLOCK_MINUTES,
    value_seed_line: str = _VALID_VALUE_SEED,
) -> str:
    return "\n".join(
        [
            header,
            blank_line,
            contract_locator_line,
            contract_schema_line,
            delivery_id_line,
            outcome_line,
            root_line,
            base_revision_line,
            route_line,
            examine_line,
            independent_review_line,
            budget_token_limit_line,
            budget_wall_clock_minutes_line,
            value_seed_line,
        ]
    )


_VALID_ATD_BODY = _atd_body()


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


class TestAtdAcceptsOnlyTheCompiledFourteenLineBody:
    @pytest.mark.parametrize(
        "prompt",
        [
            _VALID_ATD_BODY,
            _atd_body(route_line="DELIVERY-ROUTE: GREEN_TO_GREEN"),
            _atd_body(root_line=r"ROOT: C:\repo\root"),
            _atd_body(
                contract_schema_line=r"CONTRACT-SCHEMA: C:\lib\thin-delivery-contract.schema.json"
            ),
            _atd_body(base_revision_line="BASE-REVISION: git-sha256:" + "b" * 64),
            _atd_body(examine_line="EXAMINE: false"),
            _atd_body(independent_review_line="INDEPENDENT-REVIEW: true"),
            _atd_body(
                header=f"ARCHITECTURE-COVERED: {_VALID_PATH}#maintenance_windows"
            ),
        ],
        ids=[
            "canonical",
            "green_to_green",
            "windows_root",
            "windows_schema",
            "sha256_revision",
            "examine_false",
            "independent_review_true",
            "underscore_anchor",
        ],
    )
    def test_valid_body_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path, prompt
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


class TestAtdRejectsMissingInferredReorderedOrInvalidFacts:
    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            (
                "five_line_legacy_body",
                "\n".join(
                    [_VALID_HEADER, "", _VALID_ROOT, _VALID_VALUE_SEED, _VALID_ROUTE]
                ),
            ),
            ("missing_blank_line", _atd_body(blank_line="not blank")),
            ("missing_one_line", "\n".join(_VALID_ATD_BODY.splitlines()[:-1])),
            ("extra_trailing_line", _VALID_ATD_BODY + "\nEXTRA: context"),
            (
                "reordered_facts",
                _atd_body(
                    contract_locator_line=_VALID_CONTRACT_SCHEMA,
                    contract_schema_line=_VALID_CONTRACT_LOCATOR,
                ),
            ),
            (
                "duplicate_root_line_displaces_base_revision",
                _atd_body(base_revision_line=_VALID_ROOT),
            ),
            (
                "duplicate_architecture_header_in_body",
                _atd_body(value_seed_line=_VALID_HEADER),
            ),
            (
                "retired_no_impact_header",
                _atd_body(
                    header=f"ARCHITECTURE-NO-IMPACT: {_VALID_PATH}#{_VALID_ANCHOR}"
                ),
            ),
            (
                "relative_contract_locator_missing",
                _atd_body(contract_locator_line="CONTRACT-LOCATOR: "),
            ),
            (
                "absolute_contract_locator",
                _atd_body(
                    contract_locator_line="CONTRACT-LOCATOR: /docs/delivery-contracts/x.json"
                ),
            ),
            (
                "contract_locator_traversal",
                _atd_body(contract_locator_line="CONTRACT-LOCATOR: ../x.json"),
            ),
            (
                "contract_locator_wrong_suffix",
                _atd_body(
                    contract_locator_line="CONTRACT-LOCATOR: docs/delivery-contracts/x.txt"
                ),
            ),
            (
                "relative_contract_schema",
                _atd_body(contract_schema_line="CONTRACT-SCHEMA: relative/schema.json"),
            ),
            (
                "contract_schema_wrong_suffix",
                _atd_body(contract_schema_line="CONTRACT-SCHEMA: /abs/schema.txt"),
            ),
            ("empty_delivery_id", _atd_body(delivery_id_line="DELIVERY-ID: ")),
            (
                "delivery_id_uppercase",
                _atd_body(delivery_id_line="DELIVERY-ID: Auto-0123"),
            ),
            (
                "delivery_id_underscore",
                _atd_body(delivery_id_line="DELIVERY-ID: auto_0123"),
            ),
            (
                "delivery_id_dot",
                _atd_body(delivery_id_line="DELIVERY-ID: auto.0123"),
            ),
            (
                "delivery_id_slash",
                _atd_body(delivery_id_line="DELIVERY-ID: auto/0123"),
            ),
            (
                "delivery_id_whitespace",
                _atd_body(delivery_id_line="DELIVERY-ID: auto 0123"),
            ),
            (
                "delivery_id_leading_hyphen",
                _atd_body(delivery_id_line="DELIVERY-ID: -auto0123"),
            ),
            ("empty_outcome", _atd_body(outcome_line="OUTCOME: ")),
            ("relative_root", _atd_body(root_line="ROOT: relative/root")),
            (
                "base_revision_short_hex",
                _atd_body(base_revision_line="BASE-REVISION: git-sha1:abc123"),
            ),
            (
                "base_revision_uppercase_hex",
                _atd_body(base_revision_line="BASE-REVISION: git-sha1:" + "A" * 40),
            ),
            (
                "base_revision_unknown_tag",
                _atd_body(base_revision_line="BASE-REVISION: svn-rev:12345"),
            ),
            ("unknown_route", _atd_body(route_line="DELIVERY-ROUTE: UNKNOWN")),
            ("examine_not_bool", _atd_body(examine_line="EXAMINE: yes")),
            (
                "independent_review_not_bool",
                _atd_body(independent_review_line="INDEPENDENT-REVIEW: maybe"),
            ),
            (
                "budget_token_limit_zero",
                _atd_body(budget_token_limit_line="BUDGET-TOKEN-LIMIT: 0"),
            ),
            (
                "budget_token_limit_negative",
                _atd_body(budget_token_limit_line="BUDGET-TOKEN-LIMIT: -5"),
            ),
            (
                "budget_token_limit_leading_zero",
                _atd_body(budget_token_limit_line="BUDGET-TOKEN-LIMIT: 007"),
            ),
            (
                "budget_token_limit_non_digit",
                _atd_body(budget_token_limit_line="BUDGET-TOKEN-LIMIT: many"),
            ),
            (
                "budget_wall_clock_minutes_zero",
                _atd_body(
                    budget_wall_clock_minutes_line="BUDGET-WALL-CLOCK-MINUTES: 0"
                ),
            ),
            ("empty_value_seed", _atd_body(value_seed_line="VALUE-SEED: ")),
        ],
    )
    def test_malformed_body_blocks_with_this_gates_signature(
        self, monkeypatch, capsys, audit_events, tmp_path, case_id, prompt
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
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _ATD_BODY_GATE_SIGNATURE in payload["reason"], case_id


_VALID_REVISE_LOCATOR_VALUE = contract_locator_for(_VALID_DELIVERY_ID_VALUE)
_VALID_REVISE_LOCATOR_LINE = f"REVISE-CONTRACT: {_VALID_REVISE_LOCATOR_VALUE}"
_VALID_REVISE_ROUND_LINE = "REVISE-ROUND: 1/3"
_VALID_CITATION_TEXT = "The crafter cited an invented import that does not exist."
_VALID_CITATION_LINE = (
    f"CITATION: {json.dumps(_VALID_CITATION_TEXT, ensure_ascii=False)}"
)


def _atd_revision_body(
    *,
    locator_line: str = _VALID_REVISE_LOCATOR_LINE,
    round_line: str = _VALID_REVISE_ROUND_LINE,
    citation_line: str = _VALID_CITATION_LINE,
) -> str:
    return "\n".join([locator_line, round_line, citation_line])


class TestAtdAcceptsTheContractRevisionBody:
    """Run 4 evidence / ADR-SSOT-002 Section 4c/4d: a crafter INDETERMINATE
    citing the contract/oracle routes back to ATD with this alternate
    three-line body (stable-design report 2026-08-19 §1.2 added
    REVISE-ROUND, emitted only by `des revise-contract-round`) on the SAME
    already-produced DeliveryId -- never a fresh fourteen-line envelope
    from a second `prepare-ordinary-request` run."""

    def test_valid_revision_body_is_not_blocked_by_this_gate(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": _atd_revision_body(), "subagent_type": _ATD},
                transcript_path=_transcript(tmp_path, auto=True),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ATD_BODY_GATE_SIGNATURE not in payload.get("reason", "")

    @pytest.mark.parametrize(
        "case_id,prompt",
        [
            (
                "missing_citation_line",
                _VALID_REVISE_LOCATOR_LINE,
            ),
            (
                "extra_trailing_line",
                _atd_revision_body() + "\nEXTRA: context",
            ),
            (
                "wrong_first_line_prefix",
                _atd_revision_body(
                    locator_line=f"CONTRACT-LOCATOR: {_VALID_REVISE_LOCATOR_VALUE}"
                ),
            ),
            (
                "locator_wrong_directory",
                _atd_revision_body(
                    locator_line=f"REVISE-CONTRACT: docs/other/{_VALID_DELIVERY_ID_VALUE}.json"
                ),
            ),
            (
                "locator_wrong_suffix",
                _atd_revision_body(
                    locator_line=f"REVISE-CONTRACT: docs/delivery-contracts/{_VALID_DELIVERY_ID_VALUE}.txt"
                ),
            ),
            (
                "locator_absolute",
                _atd_revision_body(
                    locator_line=f"REVISE-CONTRACT: /docs/delivery-contracts/{_VALID_DELIVERY_ID_VALUE}.json"
                ),
            ),
            (
                "locator_traversal",
                _atd_revision_body(
                    locator_line="REVISE-CONTRACT: docs/delivery-contracts/../x.json"
                ),
            ),
            (
                "locator_missing_auto_prefix",
                _atd_revision_body(
                    locator_line="REVISE-CONTRACT: docs/delivery-contracts/0123456789abcdef.json"
                ),
            ),
            (
                "locator_short_hex",
                _atd_revision_body(
                    locator_line="REVISE-CONTRACT: docs/delivery-contracts/auto-0123.json"
                ),
            ),
            (
                "locator_uppercase_hex",
                _atd_revision_body(
                    locator_line="REVISE-CONTRACT: docs/delivery-contracts/auto-"
                    + "A" * 16
                    + ".json"
                ),
            ),
            (
                "citation_missing_prefix",
                _atd_revision_body(citation_line='"a bare unlabeled citation"'),
            ),
            (
                "citation_empty_string",
                _atd_revision_body(citation_line='CITATION: ""'),
            ),
            (
                "citation_whitespace_only",
                _atd_revision_body(citation_line='CITATION: "   "'),
            ),
            (
                "citation_not_json_string",
                _atd_revision_body(citation_line="CITATION: a bare unquoted citation"),
            ),
            (
                "citation_json_number_not_string",
                _atd_revision_body(citation_line="CITATION: 42"),
            ),
            (
                "round_missing_prefix",
                _atd_revision_body(round_line="1/3"),
            ),
            (
                "round_not_a_fraction",
                _atd_revision_body(round_line="REVISE-ROUND: one"),
            ),
            (
                "round_exceeds_its_own_bound",
                _atd_revision_body(round_line="REVISE-ROUND: 4/3"),
            ),
            (
                "round_zero",
                _atd_revision_body(round_line="REVISE-ROUND: 0/3"),
            ),
            (
                "round_negative",
                _atd_revision_body(round_line="REVISE-ROUND: -1/3"),
            ),
            (
                "round_leading_zero",
                _atd_revision_body(round_line="REVISE-ROUND: 01/3"),
            ),
            (
                "round_missing_denominator",
                _atd_revision_body(round_line="REVISE-ROUND: 1/"),
            ),
            (
                "two_line_body_missing_round_entirely",
                "\n".join([_VALID_REVISE_LOCATOR_LINE, _VALID_CITATION_LINE]),
            ),
        ],
    )
    def test_malformed_revision_body_blocks_with_this_gates_signature(
        self, monkeypatch, capsys, audit_events, tmp_path, case_id, prompt
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
        assert exit_code == 2, case_id
        assert payload["decision"] == "block", case_id
        assert _ATD_BODY_GATE_SIGNATURE in payload["reason"], case_id


class TestScopeExclusionsPassThisSpecificGate:
    @pytest.mark.parametrize(
        "case_id,auto_observed,role,identity",
        [
            ("no_auto_observed", False, _ATD, {}),
            ("subagent_identity_agent_id", True, _ATD, {"agent_id": "sub-1"}),
            ("subagent_identity_agent_type", True, _ATD, {"agent_type": "nw-crafter"}),
            ("non_exact_role", True, "nw-acceptance-designer-reviewer", {}),
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
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Agent",
                tool_input={"prompt": "Do the work", "subagent_type": role},
                transcript_path=_transcript(tmp_path, auto=auto_observed),
                **identity,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert _ATD_BODY_GATE_SIGNATURE not in payload.get("reason", ""), case_id


class TestRevisionGrammarDoesNotDriftAcrossAuthoringSurfaces:
    """The two-line `REVISE-CONTRACT:`/`CITATION:` shape is documented in
    TWO prose surfaces (root's routing skill, ATD's own agent spec) but
    enforced by a THIRD (this hook). A prefix changed in only one of the
    three would desync root's routing prose from what the hook actually
    admits -- pin the exact hook constants as literal substrings of both
    documents so that drift fails a test, not a live redispatch loop."""

    def test_revise_contract_and_citation_prefixes_appear_in_both_documents(
        self,
    ) -> None:
        skill_text = _NW_AUTO_SKILL_MD.read_text(encoding="utf-8")
        agent_text = _ATD_AGENT_MD.read_text(encoding="utf-8")
        for prefix in (
            pre_tool_use_handler._ATD_REVISE_CONTRACT_LINE_PREFIX.rstrip(),
            pre_tool_use_handler._ATD_REVISE_ROUND_LINE_PREFIX.rstrip(),
            pre_tool_use_handler._ATD_CITATION_LINE_PREFIX.rstrip(),
        ):
            assert prefix in skill_text, f"{prefix!r} missing from nw-auto/SKILL.md"
            assert prefix in agent_text, (
                f"{prefix!r} missing from nw-acceptance-designer.md"
            )

    def test_skill_names_the_revision_route_never_a_fresh_producer_run(self) -> None:
        skill_text = _NW_AUTO_SKILL_MD.read_text(encoding="utf-8")
        assert "INDETERMINATE" in skill_text
        assert "never a fresh `des prepare-ordinary-request` run" in skill_text
