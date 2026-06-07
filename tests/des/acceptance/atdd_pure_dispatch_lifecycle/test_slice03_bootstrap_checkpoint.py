"""slice-03 (T-D) — bootstrap checkpoint: atdd_pure dispatch lifecycle e2e.

Epic F-DES-ATDD-PURE-DISPATCH-LIFECYCLE. Transformation T-D — the bootstrap
checkpoint. slice-00 (T-A, the atdd_pure dispatch template), slice-01 (T-B,
mode-aware ``PreToolUse`` validator) and slice-02 (T-C, mode-aware
``SubagentStop`` validator) are all delivered GREEN. T-D proves the dispatch
lifecycle works end-to-end: a real ``atdd_pure`` dispatch round-trips through
the now-mode-aware lifecycle without improvisation.

This is the proof that the F-08 dispatch-lifecycle gap is closed — "shipped"
means "demoable", not "prose-coherent" (US-4).

Genuine end-to-end composition, no fixture-folding:
  * the dispatch prompt is the REAL production ``nw-execute/SKILL.md``
    ``atdd_pure`` template extracted from disk (T-A);
  * it is validated by the REAL production ``PreToolUseService.validate`` via
    the ``PreToolUsePort`` driving port (T-B);
  * a simulated ``atdd_pure`` crafter return is validated by the REAL
    production ``SubagentStopService.validate`` via the ``SubagentStopPort``
    driving port (T-C);
  * at no point is an ``execution-log.json`` present on disk — T-D is the
    Earned-Trust probe for "atdd_pure produces no execution-log" (DESIGN
    §Earned Trust).

If the validators were stubbed out this test would still pass — that would be
fixture-folding and wrong. They are the production application services,
constructed via the production ``service_factory`` / real DI. The test fails
RED if either validator is mode-blind.

Layer note (Mandate 9 / 11): this is a layer-3+ ``@wiring_e2e`` checkpoint —
example-based, one representative round-trip, traditional assertions. Gates
stay prose-invoked at T-D by design (the epic proves the dispatch *lifecycle*,
not the hook-enforced gates — those are F-DES-ATDD-PURE-HOOK-GATES).

Two ATs (slice ≤ 2):
  * AT-1 (@wiring_e2e) — the full lifecycle round-trip: real T-A template →
    real PreToolUse validator (ALLOW) → real SubagentStop validator on an
    atdd_pure return (ALLOW, no execution-log demanded, ExecutionLogReader
    never consulted).
  * AT-2 — the ADR-028 amendment note recording the delivered dispatch
    lifecycle is present in the ADR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.service_factory import create_pre_tool_use_service
from des.application.subagent_stop_service import SubagentStopService
from des.domain.des_marker_parser import (
    DesMarkerParser,
    classify_atdd_pure_dispatch,
)
from des.domain.step_completion_validator import StepCompletionValidator
from des.domain.tdd_schema import TDDSchemaLoader
from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driven_ports.execution_log_reader import (
    ExecutionLogReader,
    LogFileNotFound,
)
from des.ports.driven_ports.scope_checker import ScopeChecker, ScopeCheckResult
from des.ports.driven_ports.time_provider_port import TimeProvider
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.subagent_stop_port import SubagentStopContext


# ---------------------------------------------------------------------------
# Production T-A template extraction (real skill file on disk)
# ---------------------------------------------------------------------------

_SKILL_PATH = Path("nWave/skills/nw-execute/SKILL.md")
_TEMPLATE_BEGIN = "<!-- ATDD-PURE-DISPATCH-TEMPLATE:BEGIN -->"
_TEMPLATE_END = "<!-- ATDD-PURE-DISPATCH-TEMPLATE:END -->"

_ADR_028_PATH = Path("docs/architecture/adrs/adr-028-atdd-pure-roadmap-free-spine.md")
_AMENDMENT_ANCHOR = "## Amendment — atdd_pure dispatch lifecycle delivered"

# The DESIGN_CONTEXT {Summary…} placeholder verbatim from the template, AFTER the
# {feature-id} substitution applied above. The slice-01 content gate
# (crafter-design-adherence-enforcement) refuses this unfilled placeholder, so a
# REAL dispatchable render must fill it.
_TEMPLATE_DESIGN_CONTEXT_PLACEHOLDER = (
    "{Summary of architectural decisions relevant to this slice, extracted from\n"
    "docs/feature/atdd-pure-dispatch-lifecycle/feature-delta.md DESIGN section. "
    "Include component\n"
    "structure, dependency boundaries, technology choices, design constraints. If\n"
    'no design artifacts exist, write "No design artifacts available — use project\n'
    'conventions."}'
)

# A real citation-bearing DESIGN_CONTEXT body — what the render-time auto-inject
# (slice-02) will produce. Cites ADR-028 + the feature-delta.md DESIGN path so the
# content gate's design-reference token regex matches.
_FILLED_DESIGN_CONTEXT = (
    "Per ADR-028 the atdd_pure spine is roadmap-free; this dispatch round-trips "
    "the mode-aware lifecycle. See "
    "docs/feature/atdd-pure-dispatch-lifecycle/feature-delta.md DESIGN section "
    "for the T-A/T-B/T-C decomposition."
)


def _render_atdd_pure_dispatch_prompt() -> str:
    """Extract and render the REAL production atdd_pure dispatch template.

    Mirrors what the /nw-execute dispatcher does at render time: extract the
    verbatim template block between the BEGIN/END anchors, fill the
    {placeholders} with concrete slice-03 values. No fixture — the input is
    the production skill file on disk.
    """
    content = _SKILL_PATH.read_text(encoding="utf-8")
    begin = content.find(_TEMPLATE_BEGIN)
    end = content.find(_TEMPLATE_END)
    assert begin != -1 and end > begin, (
        "atdd_pure dispatch template anchors missing from nw-execute/SKILL.md — "
        "slice-00 (T-A) must land before the slice-03 checkpoint"
    )
    template = content[begin + len(_TEMPLATE_BEGIN) : end]
    rendered = (
        template.replace("{feature-id}", "atdd-pure-dispatch-lifecycle")
        .replace("{slice-NN}", "slice-03")
        .replace("{slice-id}", "slice-03")
        .replace("{phase}", "G_COMMIT")
        .replace("{ATDDPurePhase}", "G_COMMIT")
        .replace("{agent}", "nw-software-crafter")
        .replace("{agent-name}", "nw-software-crafter")
    )
    # Fill the DESIGN_CONTEXT {Summary…} placeholder with a real citation-bearing
    # body — mirroring what the /nw-execute render-time auto-inject (slice-02 of
    # crafter-design-adherence-enforcement) will do. An UNFILLED template is not
    # a dispatchable prompt under the slice-01 content gate
    # (design_context_carries_architecture refuses the raw {Summary…}
    # placeholder). T-A intent is preserved: the input is still the real
    # production template extracted from disk — this only completes the render.
    return rendered.replace(
        _TEMPLATE_DESIGN_CONTEXT_PLACEHOLDER, _FILLED_DESIGN_CONTEXT
    )


# ---------------------------------------------------------------------------
# In-memory driven-port doubles (port boundary only)
# ---------------------------------------------------------------------------


class _RecordingAuditWriter(AuditLogWriter):
    """In-memory AuditLogWriter double — records every event for inspection."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)


class _StubTimeProvider(TimeProvider):
    """Stub returning a fixed timestamp for deterministic testing."""

    def now_utc(self) -> datetime:
        return datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


class _StubScopeChecker(ScopeChecker):
    """Stub returning no scope violations."""

    def check_scope(
        self, project_root: Path, allowed_patterns: list[str]
    ) -> ScopeCheckResult:
        return ScopeCheckResult(has_violations=False, out_of_scope_files=[])


class _NoLogReader(ExecutionLogReader):
    """ExecutionLogReader that records consultation and reports the log missing.

    Models the atdd_pure substrate: there is NO execution-log.json on disk.
    If the atdd_pure SubagentStop path ever consults this reader, ``consulted``
    flips True and the round-trip fails — proving the lifecycle is genuinely
    mode-aware, not fixture-folded.
    """

    def __init__(self) -> None:
        self.consulted = False

    def read_project_id(self, execution_log_path: str) -> str:
        self.consulted = True
        raise LogFileNotFound(execution_log_path)

    def read_step_events(self, execution_log_path: str, step_id: str) -> list[str]:
        self.consulted = True
        raise LogFileNotFound(execution_log_path)

    def read_all_events(self, execution_log_path: str) -> list[str]:
        self.consulted = True
        raise LogFileNotFound(execution_log_path)


def _make_subagent_stop_service(reader: ExecutionLogReader) -> SubagentStopService:
    """Build the production SubagentStopService with in-memory driven doubles."""
    return SubagentStopService(
        log_reader=reader,
        completion_validator=StepCompletionValidator(TDDSchemaLoader().load()),
        scope_checker=_StubScopeChecker(),
        audit_writer=_RecordingAuditWriter(),
        time_provider=_StubTimeProvider(),
    )


# ---------------------------------------------------------------------------
# AT-1 — full lifecycle round-trip: real T-A template through T-B and T-C
# ---------------------------------------------------------------------------


@pytest.mark.wiring_e2e
def test_at1_atdd_pure_dispatch_round_trips_through_mode_aware_lifecycle():
    """Property: a real atdd_pure dispatch round-trips the mode-aware lifecycle.

    Given the REAL production nw-execute/SKILL.md atdd_pure dispatch template
          (T-A), rendered with concrete slice-03 values,
    And there is NO execution-log.json on disk at any point,
    When the dispatch prompt is validated by the REAL PreToolUseService
         (T-B) through the PreToolUsePort,
    And a simulated atdd_pure crafter return is validated by the REAL
         SubagentStopService (T-C) through the SubagentStopPort,
    Then the PreToolUse decision is ALLOW (the atdd_pure section schema is
         applied, not the classic 9-section schema),
    And the SubagentStop decision is ALLOW (no execution-log.json demanded),
    And the ExecutionLogReader is never consulted on the atdd_pure return.

    This is the F-08 closure proof. If either validator were mode-blind this
    test stays RED: T-B would block the dispatch MISSING classic sections,
    T-C would block the return LOG_FILE_NOT_FOUND.
    """
    # --- Stage 1: render the real production atdd_pure dispatch prompt (T-A).
    dispatch_prompt = _render_atdd_pure_dispatch_prompt()

    # Sanity: the rendered prompt is a genuine atdd_pure dispatch — the
    # production classifier recognises it. (If this is not 'valid' the e2e
    # claim is hollow.)
    markers = DesMarkerParser().parse(dispatch_prompt)
    assert classify_atdd_pure_dispatch(markers) == "valid", (
        "the rendered T-A template is not classified 'valid' by the production "
        "parser — the lifecycle checkpoint cannot proceed"
    )

    # --- Stage 2: validate the dispatch through the REAL PreToolUse port (T-B).
    pre_service = create_pre_tool_use_service(
        audit_writer_factory=_RecordingAuditWriter
    )
    pre_decision = pre_service.validate(
        PreToolUseInput(prompt=dispatch_prompt, subagent_type="agent")
    )
    assert pre_decision.action == "allow", (
        f"the atdd_pure dispatch was {pre_decision.action!r} by the PreToolUse "
        f"validator (reason={pre_decision.reason!r}); expected 'allow' — the "
        "mode-aware validator must route it to the atdd_pure section schema"
    )

    # --- Stage 3: validate a simulated atdd_pure crafter return through the
    #     REAL SubagentStop port (T-C) — with NO execution-log.json on disk.
    reader = _NoLogReader()
    stop_service = _make_subagent_stop_service(reader)
    stop_context = SubagentStopContext(
        execution_log_path="",
        project_id="atdd-pure-dispatch-lifecycle",
        step_id="",
        mode="atdd_pure",
        slice_id="slice-03",
        atdd_pure_phase="G_COMMIT",
    )
    stop_decision = stop_service.validate(stop_context)

    assert stop_decision.action == "allow", (
        f"the atdd_pure crafter return was {stop_decision.action!r} by the "
        f"SubagentStop validator (reason={stop_decision.reason!r}); expected "
        "'allow' — atdd_pure produces no execution-log.json and the validator "
        "must not demand one"
    )
    assert reader.consulted is False, (
        "the atdd_pure SubagentStop path consulted the ExecutionLogReader — "
        "the mode-aware lifecycle must skip it entirely for atdd_pure returns "
        "(this is exactly the F-08 / G-3 defect T-C closes)"
    )


# ---------------------------------------------------------------------------
# AT-2 — the ADR-028 amendment note recording the delivered lifecycle
# ---------------------------------------------------------------------------


def test_at2_adr_028_records_dispatch_lifecycle_amendment():
    """The ADR-028 amendment note recording the delivered lifecycle is present.

    Given ADR-028 (the roadmap-free spine ADR),
    When the atdd_pure dispatch lifecycle (template + mode-aware validators) is
         delivered,
    Then ADR-028 carries a one-paragraph amendment note recording that the
         dispatch lifecycle — the T-A template and the mode-aware T-B / T-C
         validators — is part of the roadmap-free spine's definition.
    """
    content = _ADR_028_PATH.read_text(encoding="utf-8")
    assert _AMENDMENT_ANCHOR in content, (
        f"ADR-028 missing the slice-03 amendment anchor {_AMENDMENT_ANCHOR!r} — "
        "the dispatch-lifecycle amendment note has not been appended"
    )
    # The amendment must name the three delivered transformations so the note
    # is substantive, not a placeholder heading.
    amendment = content[content.find(_AMENDMENT_ANCHOR) :]
    for token in ("atdd_pure", "PreToolUse", "SubagentStop"):
        assert token in amendment, (
            f"the ADR-028 amendment note does not mention {token!r} — it must "
            "record the delivered dispatch template + mode-aware validators"
        )
