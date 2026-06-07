"""slice-01 (T-B) — mode-aware PreToolUse dispatch-prompt validation.

Epic F-DES-ATDD-PURE-DISPATCH-LIFECYCLE. Transformation T-B (F-08 / G-2):
make the DES ``PreToolUse`` dispatch-prompt validator mode-aware.

Before T-B, ``pre_tool_use_service.validate`` ran the classic 9-section
mandatory schema for *every* non-orchestrator DES task regardless of
``workflow.mode``. An ``atdd_pure`` dispatch — which carries the A→G phase
block and the AT-completion-ledger contract, NOT ``TDD_PHASES`` /
``OUTCOME_RECORDING`` / ``RECORDING_INTEGRITY`` execution-log sections — was
wrongly rejected ``MISSING: Mandatory section ...``.

T-B routes by ``classify_atdd_pure_dispatch``:
  * an ``atdd_pure`` dispatch with the correct ``atdd_pure`` section set is
    ALLOWED (validated against the ``atdd_pure`` schema);
  * an ``atdd_pure`` dispatch missing an ``atdd_pure``-required section, or
    carrying a defective marker set, is BLOCKED;
  * a classic dispatch still validates against the classic mandatory-section
    schema unchanged (no regression).

Port-to-port: the test enters through the ``PreToolUsePort`` driving port
(``PreToolUseService.validate``) and asserts on the ``HookDecision`` returned
at the port boundary. Driven ports (audit writer, time provider) are
in-memory doubles.

Three ATs, slice ≤ 3 — AT-1 is parametrized over the allowed-atdd_pure /
blocked-defective / allowed-classic universe (one ``Scenario Outline`` per the
ATs-max-PBT density mandate); AT-2 / AT-3 pin the two structural invariants.
"""

from __future__ import annotations

import pytest

from des.adapters.drivers.hooks.service_factory import create_pre_tool_use_service
from des.domain.des_marker_parser import DesMarkerParser
from des.ports.driven_ports.audit_log_writer import AuditLogWriter
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


# ---------------------------------------------------------------------------
# In-memory driven-port doubles (port boundary only)
# ---------------------------------------------------------------------------


class _RecordingAuditWriter(AuditLogWriter):
    """In-memory AuditLogWriter double — records every event for inspection."""

    def __init__(self) -> None:
        self.events: list = []

    def log_event(self, event) -> None:
        self.events.append(event)


# ---------------------------------------------------------------------------
# atdd_pure dispatch prompt — the canonical T-A template section set, rendered
# ---------------------------------------------------------------------------


_ATDD_PURE_SECTIONS = (
    "DES_METADATA",
    "AGENT_IDENTITY",
    "SKILL_LOADING",
    "TASK_CONTEXT",
    "DESIGN_CONTEXT",
    "ATDD_PURE_PHASES",
    "QUALITY_GATES",
    "AT_COMPLETION_LEDGER",
    "RECORDING_INTEGRITY",
    "BOUNDARY_RULES",
    "TERMINATING_RUN",
    "TIMEOUT_INSTRUCTION",
)


def _atdd_pure_prompt(*, omit: str | None = None) -> str:
    """Render an atdd_pure dispatch prompt with the T-A template section set.

    Args:
        omit: when given, the named atdd_pure-required section is left out —
            producing a structurally-defective atdd_pure dispatch.
    """
    header = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : atdd-pure-dispatch-lifecycle -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
    )
    # DESIGN_CONTEXT must carry a real architecture citation — the slice-01
    # content gate (crafter-design-adherence-enforcement) refuses a citation-free
    # body. This test's intent is mode-routing, so the citation is incidental;
    # a real dispatch carries a filled DESIGN_CONTEXT (slice-02 auto-injects it).
    section_bodies = {
        "DESIGN_CONTEXT": "Per ADR-028 / DDD-1 the mode-aware validator routes "
        "by workflow mode; see feature-delta.md DESIGN section.",
    }
    body = "\n".join(
        f"# {section}\n{section_bodies.get(section, f'Content for {section}.')}\n"
        for section in _ATDD_PURE_SECTIONS
        if section != omit
    )
    return header + "\n" + body


def _atdd_pure_prompt_defective_markers() -> str:
    """An atdd_pure dispatch whose marker set is defective (DES-PHASE missing).

    The atdd_pure section set is complete, but DES-PHASE is absent — so
    ``classify_atdd_pure_dispatch`` returns 'defective'. Must be BLOCKED.
    """
    header = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : atdd-pure-dispatch-lifecycle -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
    )
    body = "\n".join(
        f"# {section}\nContent for {section}.\n" for section in _ATDD_PURE_SECTIONS
    )
    return header + "\n" + body


_CLASSIC_SECTIONS = (
    "DES_METADATA",
    "AGENT_IDENTITY",
    "TASK_CONTEXT",
    "TDD_PHASES",
    "QUALITY_GATES",
    "OUTCOME_RECORDING",
    "RECORDING_INTEGRITY",
    "BOUNDARY_RULES",
    "TIMEOUT_INSTRUCTION",
)


def _classic_prompt() -> str:
    """Render a well-formed classic DES dispatch prompt (9 mandatory sections)."""
    header = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : some-feature -->\n"
        "<!-- DES-STEP-ID : 01-01 -->\n"
    )
    body = "\n".join(
        f"# {section}\nContent for {section}.\n" for section in _CLASSIC_SECTIONS
    )
    # Classic schema also checks the 3 TDD phase names.
    phases = "\n1. RED\n2. GREEN\n3. COMMIT\n"
    return header + "\n" + body + phases


def _validate(prompt: str):
    """Drive the PreToolUsePort: render a dispatch, return the HookDecision."""
    service = create_pre_tool_use_service(audit_writer_factory=_RecordingAuditWriter)
    return service.validate(PreToolUseInput(prompt=prompt, subagent_type="agent"))


# ---------------------------------------------------------------------------
# AT-1 — mode-aware routing universe: allowed-atdd_pure / blocked-defective /
#         allowed-classic (parametrized Scenario Outline)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dispatch", "expected_action"),
    [
        pytest.param(_atdd_pure_prompt(), "allow", id="well-formed-atdd_pure"),
        pytest.param(
            _atdd_pure_prompt(omit="ATDD_PURE_PHASES"),
            "block",
            id="atdd_pure-missing-phase-block",
        ),
        pytest.param(
            _atdd_pure_prompt(omit="AT_COMPLETION_LEDGER"),
            "block",
            id="atdd_pure-missing-ledger-section",
        ),
        pytest.param(
            _atdd_pure_prompt_defective_markers(),
            "block",
            id="atdd_pure-defective-marker-set",
        ),
        pytest.param(_classic_prompt(), "allow", id="well-formed-classic"),
    ],
)
def test_at1_pre_tool_use_routes_validation_by_workflow_mode(
    dispatch: str, expected_action: str
) -> None:
    """Property: PreToolUse validation routes by the dispatch's workflow mode.

    Given a DES dispatch prompt,
    When PreToolUseService.validate is invoked through the PreToolUsePort,
    Then a well-formed atdd_pure dispatch is ALLOWED (validated against the
         atdd_pure section schema), a structurally-defective or
         defective-marker-set atdd_pure dispatch is BLOCKED, and a well-formed
         classic dispatch is still ALLOWED (classic schema, no regression).
    """
    decision = _validate(dispatch)

    assert decision.action == expected_action, (
        f"expected {expected_action!r}, got {decision.action!r} "
        f"(reason: {decision.reason!r})"
    )


# ---------------------------------------------------------------------------
# AT-2 — an atdd_pure dispatch is NOT rejected for missing classic-only sections
# ---------------------------------------------------------------------------


def test_at2_atdd_pure_dispatch_not_blocked_for_missing_classic_sections() -> None:
    """Regression guard for F-08 / G-2.

    Given a well-formed atdd_pure dispatch (no TDD_PHASES / OUTCOME_RECORDING),
    When it is validated through the PreToolUsePort,
    Then it is ALLOWED — the classic mandatory-section schema is NOT applied,
         so no 'MISSING: Mandatory section TDD_PHASES' style block occurs.
    """
    decision = _validate(_atdd_pure_prompt())

    assert decision.action == "allow", (
        f"atdd_pure dispatch wrongly blocked: {decision.reason!r}"
    )
    # The defining defect of F-08: classic-only sections demanded of atdd_pure.
    assert decision.reason is None or "TDD_PHASES" not in decision.reason
    assert decision.reason is None or "OUTCOME_RECORDING" not in decision.reason


# ---------------------------------------------------------------------------
# AT-3 — classic dispatch validation is unchanged (classic schema still applies)
# ---------------------------------------------------------------------------


def test_at3_classic_dispatch_still_validated_against_classic_schema() -> None:
    """The classic path is unregressed — classic schema still rejects gaps.

    Given a classic DES dispatch missing a classic mandatory section,
    When it is validated through the PreToolUsePort,
    Then it is BLOCKED against the classic mandatory-section schema — T-B's
         mode branch does not weaken classic-dispatch validation.
    """
    # Sanity: a parsed classic dispatch is classified 'absent' (not atdd_pure).
    from des.domain.des_marker_parser import classify_atdd_pure_dispatch

    classic = _classic_prompt()
    assert classify_atdd_pure_dispatch(DesMarkerParser().parse(classic)) == "absent"

    # A classic dispatch missing TDD_PHASES must still be blocked by the
    # classic schema.
    broken_classic = classic.replace("# TDD_PHASES", "# UNRELATED_HEADER")
    decision = _validate(broken_classic)

    assert decision.action == "block", (
        "classic dispatch missing a mandatory section must still be blocked "
        "by the classic schema"
    )
