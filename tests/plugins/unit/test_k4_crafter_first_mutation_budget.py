"""K4 crafter first-mutation budget (2026-08-13).

Confirmed defect (exact installed K4): nw-software-crafter made 43 tool
calls before its first production Edit, re-researching cronsim, logging,
API versioning and migrations the validated DeliveryContract already
declared via `targets[].overlap`/`.justification`/`.declared-imports`/
`.boundary`. It exhausted maxTurns 45 with a partial models.py, no
views/migration/tests/receipt; hidden acceptance 0/6.

Tests verify, anchored on nw-software-crafter.md's Dispatch authority
section:
(a) maxTurns stays 45 -- this fix works inside the existing ceiling, it
    does not raise it
(b) the thin dispatch-authority branch states a hard <=15-tool-call bound
    on the first production mutation, counted from task entry, including
    Skill invocations
(c) contract-owned facts (`overlap`/`justification`/`declared-imports`/
    `boundary`) are declared authoritative and re-derivation via
    dependency/architecture/logging/migration surveys or generic greps is
    explicitly forbidden
(d) an unresolved/mismatched contract fact still fails loud via the
    existing AUTHORITY_REFUSED clause -- the new budget step does not
    replace it with a research detour
(e) the terminal verification receipt and the no-test-authoring/no-test-
    editing rules survive unweakened
(f) the pre-mutation validation steps (1-7) are batched under one closed
    budget, not left as unbounded, order-free research
"""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "nWave" / "agents"
CRAFTER_PATH = AGENTS_DIR / "nw-software-crafter.md"

DISPATCH_ANCHOR = "## Dispatch authority — applies before all later workflow text"
WORKFLOW_MODE_ANCHOR = "## Workflow Mode Dispatch"
AUTHORITY_REFUSED = "{AUTHORITY_REFUSED: true"


def _body() -> str:
    return CRAFTER_PATH.read_text(encoding="utf-8")


def _frontmatter(body: str) -> str:
    assert body.startswith("---\n"), "Agent file must open with YAML frontmatter"
    end = body.index("\n---\n", 4)
    return body[4:end]


def _dispatch_section(body: str) -> str:
    start = body.index(DISPATCH_ANCHOR)
    end = body.index(WORKFLOW_MODE_ANCHOR)
    return body[start:end]


def _normalized(text: str) -> str:
    return " ".join(text.split())


class TestMaxTurnsUnchanged:
    """(a) The fix must fit inside the existing ceiling, never raise it."""

    def test_max_turns_is_still_exactly_45(self):
        frontmatter = _frontmatter(_body())
        match = re.search(r"^maxTurns:\s*(\d+)\s*$", frontmatter, flags=re.MULTILINE)
        assert match is not None, "maxTurns field missing from frontmatter"
        assert match.group(1) == "45", (
            f"maxTurns must remain 45, found {match.group(1)}"
        )

    def test_no_retry_controller_ledger_or_receipt_artifact_language_added(self):
        section = _dispatch_section(_body()).lower()
        for forbidden in (
            "retry budget",
            "retry controller",
            "new ledger",
            "receipt artifact",
            "raise maxturns",
        ):
            assert forbidden not in section, f"Forbidden addition present: {forbidden}"


class TestFirstMutationBound:
    """(b) A hard <=15-tool-call bound on the first production mutation."""

    def test_dispatch_section_states_15_tool_call_first_mutation_bound(self):
        section = _normalized(_dispatch_section(_body()))
        assert "tool call 15 counted from task entry" in section
        assert "skill invocations count" in section.lower()
        assert "first production edit/write to a declared target" in section.lower()

    def test_budget_reserves_remainder_for_targets_command_and_receipt(self):
        section = _normalized(_dispatch_section(_body()))
        assert "reserve the remaining budget" in section
        for token in (
            "every declared target one at a time in the smallest bounded vertical",
            "the focused verification command",
            "the terminal receipt",
        ):
            assert token in section, f"Missing budget reservation clause: {token}"

    def test_validation_steps_are_batched_into_one_closed_budget(self):
        section = _normalized(_dispatch_section(_body()))
        assert "batch steps 1-7 into one closed pre-mutation budget" in section.lower()


class TestContractFactsAuthoritativeNoRediscovery:
    """(c) Contract-owned facts settle reuse/architecture/dependency/library
    questions; re-derivation is explicitly forbidden."""

    def test_contract_owned_fields_declared_authoritative(self):
        section = _normalized(_dispatch_section(_body()))
        for field in (
            "targets[].overlap",
            ".justification",
            ".declared-imports",
            ".boundary",
        ):
            assert field in section, f"Contract-owned field not named: {field}"
        assert "closed and authoritative" in section

    def test_rediscovery_of_contract_owned_facts_is_forbidden(self):
        section = _normalized(_dispatch_section(_body())).lower()
        assert "never re-derive them" in section
        assert "generic greps" in section or "research" in section, (
            "Contract-owned facts must prohibit generic greps/research"
        )


class TestUnresolvedFactStillFailsLoud:
    """(d) The budget step does not replace fail-loud with a research detour."""

    def test_authority_refused_clause_still_covers_unresolved_and_mismatched(self):
        body = _body()
        section = _dispatch_section(body)
        assert AUTHORITY_REFUSED in section
        refusal_sentence = section[
            section.index("Any missing, malformed") : section.index(AUTHORITY_REFUSED)
        ]
        assert "unresolved" in refusal_sentence
        assert "mismatched" in refusal_sentence


class TestQualityObligationsSurvive:
    """(e) Verification receipt and no-test-authoring/editing rules unweakened."""

    def test_terminal_verification_receipt_fields_present(self):
        body = _body()
        for field_token in ("outcome: PASS|FAIL", "argv:", "scope:", "exit_code:"):
            assert field_token in body, f"Receipt field missing: {field_token}"
        assert "never a paraphrase" in body
        assert "incomplete, not done" in body

    def test_no_test_authoring_or_editing_rules_intact(self):
        section = _normalized(_dispatch_section(_body()))
        assert "no test edits" in section.lower()
        assert (
            "neither obligation authorizes authoring or editing a test"
            in section.lower()
        )
        body = _body()
        assert "Crafter does NOT author the unit test under any budget" in body
        assert "No test authoring" in body


class TestAnchorsSoleOwner:
    """(f) These sections exist exactly once; deletion/duplication fails loud."""

    def test_dispatch_anchor_and_budget_step_appear_exactly_once(self):
        body = _body()
        assert body.count(DISPATCH_ANCHOR) == 1
        assert body.count("Batch Steps 1-7 into one closed pre-mutation budget") == 1
        assert body.index(DISPATCH_ANCHOR) < body.index(WORKFLOW_MODE_ANCHOR)
