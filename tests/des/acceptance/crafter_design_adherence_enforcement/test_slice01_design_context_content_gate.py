"""slice-01 (@walking-skeleton) — DESIGN_CONTEXT content-presence gate.

Feature ``crafter-design-adherence-enforcement`` — closes backlog #63 INPUT-b
(DDD-1). The load-bearing enforcement: a crafter dispatch whose
``# DESIGN_CONTEXT`` section body carries NO architecture citation (empty,
whitespace, a template placeholder, the "no design artifacts" sentinel, or
citation-free prose) is REFUSED before the crafter can run. A dispatch whose
DESIGN_CONTEXT carries a real design citation (a DDD / ADR / SYS id, a
feature-delta.md path, brief.md, or a ``## Wave: DESIGN`` reference) is ALLOWED.

The pain (Ale-diagnosed root of architectural drift): "ai crafter non arriva il
brief sul design da seguire, quindi fanno passare gli ATs ma non seguono
l'architettura → duplicano e driftano." The ``# DESIGN_CONTEXT`` slot exists but
is cosmetic — today the validator checks only that the HEADER is present, not
its CONTENT. slice-01 turns the cosmetic slot into a hard gate.

Driving port (Mandate-13 — Layer 3 composition): the SUT is driven through the
production composition root ``create_pre_tool_use_service()`` →
``PreToolUseService.validate(PreToolUseInput(prompt=...))``. The observable
outcome is the ``HookDecision`` returned at the port boundary
(``action`` ∈ {"allow", "block"} + ``reason``). The validator's content rule
extends ``AtddPurePromptValidator`` (the ``ValidatorPort`` the service drives) —
the test NEVER imports the validator or the domain predicate directly; it asserts
the verdict on the real validation surface. Driven ports (audit writer, time
provider) are in-memory doubles per the Architecture of Reference.

Meta-caveat (DESIGN_CONTEXT-of-the-AT-itself): the fixture dispatch prompts
below assert on the DESIGN_CONTEXT *content of a test-fixture dispatch string* —
they are TEST DATA (strings), NOT real dispatches. The SUT is the validator; the
fixture prompts are its input.

Three ATs, slice ≤ 3:
  * AT-1 (@walking-skeleton) — the load-bearing REFUSE: an atdd_pure dispatch
    whose DESIGN_CONTEXT body is empty / whitespace / a placeholder / the
    no-artifacts sentinel / citation-free prose is BLOCKED. Parametrized over
    the placeholder/citation-free space (the unbounded-input domain OQ-2 flags),
    driven through the real composition root.
  * AT-2 — the don't-over-reject: an atdd_pure dispatch whose DESIGN_CONTEXT
    carries a real architecture citation (DDD-N / ADR-* / SYS-N / feature-delta
    path / brief.md / ## Wave: DESIGN) is ALLOWED. Parametrized over the
    citation-token shapes.
  * AT-3 (boundary discriminator) — header-present-but-body-empty. This is the
    case that PASSES today (the header-only check `f"# DESIGN_CONTEXT" in prompt`
    is satisfied) and MUST be RED under slice-01: the body after the heading is
    empty, so the content gate must REFUSE.

PBT note (Mandate 9 v2): the composition root here wires all in-memory driven
doubles (RecordingAuditWriter + deterministic SystemTimeProvider), and the
placeholder/citation negative-match space is a pure string-predicate domain — so
parametrized example density over the materially-distinct placeholder/citation
shapes is the paradigm match at this in-process composition layer. PBT-friendly,
example-anchored.
"""

from __future__ import annotations

import pytest

from des.adapters.drivers.hooks.service_factory import create_pre_tool_use_service
from des.ports.driven_ports.audit_log_writer import AuditLogWriter
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


# ---------------------------------------------------------------------------
# In-memory driven-port double (port boundary only)
# ---------------------------------------------------------------------------


class _RecordingAuditWriter(AuditLogWriter):
    """In-memory AuditLogWriter double — records every event for inspection."""

    def __init__(self) -> None:
        self.events: list = []

    def log_event(self, event) -> None:
        self.events.append(event)


# ---------------------------------------------------------------------------
# Fixture dispatch-prompt rendering (TEST DATA — not a real dispatch)
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

# The literal template placeholder shipped in nw-execute/SKILL.md:226-231 — a
# dispatch that forgot to fill DESIGN_CONTEXT carries this verbatim.
_TEMPLATE_PLACEHOLDER = (
    "{Summary of architectural decisions relevant to this slice, extracted from\n"
    "docs/feature/{feature-id}/feature-delta.md DESIGN section. Include component\n"
    "structure, dependency boundaries, technology choices, design constraints. If\n"
    'no design artifacts exist, write "No design artifacts available — use project\n'
    'conventions."}'
)

_NO_ARTIFACTS_SENTINEL = "No design artifacts available — use project conventions."


def _render_atdd_pure_dispatch(*, design_context_body: str) -> str:
    """Render a well-formed atdd_pure dispatch with a chosen DESIGN_CONTEXT body.

    Every mandatory atdd_pure section is present (so the existing header-only
    checks all pass); only the DESIGN_CONTEXT *body* varies. This isolates the
    content-presence gate as the single thing under test.

    Args:
        design_context_body: the text placed under the ``# DESIGN_CONTEXT``
            heading. Empty/whitespace/placeholder/sentinel/prose vs a real
            citation is the discriminator.
    """
    header = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-PROJECT-ID : crafter-design-adherence-enforcement -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
    )
    blocks = []
    for section in _ATDD_PURE_SECTIONS:
        body = (
            design_context_body
            if section == "DESIGN_CONTEXT"
            else f"Content for {section}."
        )
        blocks.append(f"# {section}\n{body}\n")
    return header + "\n" + "\n".join(blocks)


def _decision(prompt: str):
    """Drive the PreToolUsePort: validate a dispatch, return the HookDecision."""
    service = create_pre_tool_use_service(audit_writer_factory=_RecordingAuditWriter)
    return service.validate(PreToolUseInput(prompt=prompt, subagent_type="agent"))


# ---------------------------------------------------------------------------
# AT-1 — load-bearing REFUSE: citation-free DESIGN_CONTEXT body is BLOCKED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "design_context_body",
    [
        pytest.param("", id="empty"),
        pytest.param("   \n  \t \n", id="whitespace-only"),
        pytest.param(_TEMPLATE_PLACEHOLDER, id="template-placeholder"),
        pytest.param(_NO_ARTIFACTS_SENTINEL, id="no-artifacts-sentinel"),
        pytest.param(
            "We will build a clean service that does things nicely with good code.",
            id="citation-free-prose",
        ),
    ],
)
def test_at1_dispatch_without_architecture_citation_is_refused(
    design_context_body: str,
) -> None:
    """Scenario: A dispatch whose DESIGN_CONTEXT carries no architecture is refused.

    Given a crafter dispatch whose DESIGN_CONTEXT body carries no architecture
          citation — it is empty, whitespace, the template placeholder, the
          "no design artifacts" sentinel, or citation-free prose,
    When the dispatch is validated through the PreToolUse driving port,
    Then the dispatch is REFUSED (task invocation blocked),
    And the refusal reason names the missing design content,
         so the operator can no longer dispatch a crafter without the design it
         must follow (#63 INPUT enforcement).
    """
    decision = _decision(
        _render_atdd_pure_dispatch(design_context_body=design_context_body)
    )

    assert decision.action == "block", (
        "a DESIGN_CONTEXT body with no architecture citation must be REFUSED — "
        f"got action={decision.action!r} (reason: {decision.reason!r})"
    )
    assert decision.reason is not None and "DESIGN_CONTEXT" in decision.reason, (
        "the refusal must name the DESIGN_CONTEXT content as the cause; "
        f"got reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# AT-2 — don't-over-reject: a real architecture citation is ALLOWED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "design_context_body",
    [
        pytest.param(
            "Per DDD-1 the validator extends AtddPurePromptValidator with a "
            "content-presence rule.",
            id="ddd-token",
        ),
        pytest.param(
            "Component structure follows ADR-CP-001; the gate is read-only.",
            id="adr-token",
        ),
        pytest.param(
            "Boundary contract is fixed by SYS-4 — driving port only.",
            id="sys-token",
        ),
        pytest.param(
            "See docs/feature/crafter-design-adherence-enforcement/feature-delta.md "
            "DESIGN section for the 3-surface decomposition.",
            id="feature-delta-path",
        ),
        pytest.param(
            "Architecture decisions are summarised in brief.md: hexagonal layering, "
            "domain predicate in the domain layer.",
            id="brief-md-token",
        ),
    ],
)
def test_at2_dispatch_with_architecture_citation_is_allowed(
    design_context_body: str,
) -> None:
    """Scenario: A dispatch whose DESIGN_CONTEXT cites real architecture passes.

    Given a crafter dispatch whose DESIGN_CONTEXT body carries a real design
          citation — a DDD / ADR / SYS id, a feature-delta.md path, or brief.md,
    When the dispatch is validated through the PreToolUse driving port,
    Then the dispatch is ALLOWED — the content gate does not over-reject a
         valid, architecture-bearing body.
    """
    decision = _decision(
        _render_atdd_pure_dispatch(design_context_body=design_context_body)
    )

    assert decision.action == "allow", (
        "a DESIGN_CONTEXT body carrying a real architecture citation must be "
        f"ALLOWED — got action={decision.action!r} (reason: {decision.reason!r})"
    )


# ---------------------------------------------------------------------------
# AT-3 — boundary discriminator: header present, body empty (RED today)
# ---------------------------------------------------------------------------


def test_at3_header_present_but_body_empty_is_refused() -> None:
    """Scenario: A DESIGN_CONTEXT heading with an empty body is refused.

    Given a crafter dispatch that DOES carry the ``# DESIGN_CONTEXT`` heading
          (so the legacy header-only check is satisfied) but leaves the section
          body empty,
    When the dispatch is validated through the PreToolUse driving port,
    Then the dispatch is REFUSED — header presence is not enough; the content
         gate refuses an empty body.

    This is the discriminator the slice exists for: today the header-only check
    ``"# DESIGN_CONTEXT" in prompt`` PASSES this dispatch (the heading is
    present), so it is the case that proves the content gate adds load-bearing
    enforcement beyond the cosmetic header.
    """
    dispatch = _render_atdd_pure_dispatch(design_context_body="")

    # The legacy header-only condition is satisfied — the discriminator premise.
    assert "# DESIGN_CONTEXT" in dispatch, (
        "fixture premise: the DESIGN_CONTEXT heading must be present so the test "
        "discriminates the content gate from the legacy header-only check"
    )

    decision = _decision(dispatch)

    assert decision.action == "block", (
        "a present DESIGN_CONTEXT heading with an empty body must still be "
        f"REFUSED by the content gate — got action={decision.action!r} "
        f"(reason: {decision.reason!r})"
    )
