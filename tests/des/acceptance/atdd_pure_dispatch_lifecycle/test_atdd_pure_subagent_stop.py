"""slice-02 (T-C) — mode-aware SubagentStop return validation acceptance tests.

Epic F-DES-ATDD-PURE-DISPATCH-LIFECYCLE. Transformation T-C: make the DES
`SubagentStop` return-validator mode-aware (F-08 / G-3 + G-4).

Today `SubagentStopService.validate` reads `project_id` via `ExecutionLogReader`
and blocks `LOG_FILE_NOT_FOUND` when no `execution-log.json` exists. An
`atdd_pure` dispatch is roadmap-free / execution-log-free by design, so a
legitimate `atdd_pure` sub-agent return is wrongly rejected. T-C adds a mode
branch: when the resolved context is `atdd_pure`, the SubagentStop validator
allows the return WITHOUT demanding an `execution-log.json`. The classic path
is unchanged.

G-4 rides here: `extract_des_context_from_transcript` returns on the FIRST
`DES-VALIDATION` message — unsafe once an `atdd_pure` transcript can carry
marker-shaped text more than once. T-C adds a `DES-MODE:atdd_pure` last-match
scan: the LAST atdd_pure marker block in the transcript wins.

ATs (slice ≤ 3):
  * AT-1 — an `atdd_pure` SubagentStop return is ALLOWED with no
    `execution-log.json` on disk anywhere (the `ExecutionLogReader` is never
    consulted). Driving port: `SubagentStopService.validate`.
  * AT-2 — a classic SubagentStop return STILL requires its `execution-log.json`
    — a classic return with a missing log is blocked `LOG_FILE_NOT_FOUND`
    (no regression of the classic contract).
  * AT-3 — a transcript carrying two `DES-MODE:atdd_pure` marker blocks
    resolves to the LAST block (G-4 last-match scan); a classic transcript
    keeps the first-match return.

Layer note (Mandate 9 / 11): AT-1/AT-2 exercise the application driving port
with in-memory driven doubles (layer 2 — example-based, the failure surface is
a single allow/block decision). AT-3 exercises the transcript-extraction
adapter logic with a real JSONL file on `tmp_path` (layer 3 — example-based per
Mandate 11).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from des.adapters.drivers.hooks.subagent_stop_handler import (
    _AtddPureResolvedContext,
    _resolve_des_context,
    extract_des_context_from_transcript,
)
from des.application.subagent_stop_service import SubagentStopService
from des.domain.step_completion_validator import StepCompletionValidator
from des.domain.tdd_schema import TDDSchemaLoader
from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driven_ports.execution_log_reader import (
    ExecutionLogReader,
    LogFileNotFound,
)
from des.ports.driven_ports.scope_checker import ScopeChecker, ScopeCheckResult
from des.ports.driven_ports.time_provider_port import TimeProvider
from des.ports.driver_ports.subagent_stop_port import SubagentStopContext


# ---------------------------------------------------------------------------
# Test doubles (driven port implementations — port-boundary doubles only)
# ---------------------------------------------------------------------------


class SpyAuditWriter(AuditLogWriter):
    """Spy capturing all logged audit events for assertion."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)


class StubTimeProvider(TimeProvider):
    """Stub returning a fixed timestamp for deterministic testing."""

    def now_utc(self) -> datetime:
        return datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


class StubScopeChecker(ScopeChecker):
    """Stub returning no scope violations."""

    def check_scope(
        self, project_root: Path, allowed_patterns: list[str]
    ) -> ScopeCheckResult:
        return ScopeCheckResult(has_violations=False, out_of_scope_files=[])


class MissingLogReader(ExecutionLogReader):
    """ExecutionLogReader that always reports the log is missing.

    Models the atdd_pure substrate: there is NO execution-log.json on disk.
    If the atdd_pure SubagentStop path ever consults this reader, the test
    surfaces it (the read raises LogFileNotFound, which the classic path
    converts to a block).
    """

    consulted: bool

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


def _make_service(log_reader: ExecutionLogReader) -> SubagentStopService:
    """Build a SubagentStopService with in-memory driven doubles."""
    return SubagentStopService(
        log_reader=log_reader,
        completion_validator=StepCompletionValidator(TDDSchemaLoader().load()),
        scope_checker=StubScopeChecker(),
        audit_writer=SpyAuditWriter(),
        time_provider=StubTimeProvider(),
    )


def _make_transcript(tmp_dir: Path, *prompts: str, name: str = "agent-test") -> str:
    """Write a JSONL transcript with one user message per prompt, in order."""
    transcript_path = tmp_dir / f"{name}.jsonl"
    with open(transcript_path, "w") as f:
        for idx, prompt in enumerate(prompts):
            entry = {
                "type": "user",
                "message": {"role": "user", "content": prompt},
                "uuid": f"test-uuid-{idx}",
                "timestamp": "2026-05-20T12:00:00Z",
            }
            f.write(json.dumps(entry) + "\n")
    return str(transcript_path)


_ATDD_PURE_PROMPT = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-PROJECT-ID : {feature} -->\n"
    "<!-- DES-MODE : atdd_pure -->\n"
    "<!-- DES-PHASE : {phase} -->\n"
    "<!-- DES-SLICE : {slice} -->\n"
)

_CLASSIC_PROMPT = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-PROJECT-ID : {feature} -->\n"
    "<!-- DES-STEP-ID : {step} -->\n"
)


# ---------------------------------------------------------------------------
# AT-1 — an atdd_pure SubagentStop return is ALLOWED with no execution-log
# ---------------------------------------------------------------------------


def test_at1_atdd_pure_return_allowed_without_execution_log():
    """Property: an atdd_pure crafter return needs no execution-log.json.

    Given a SubagentStop context resolved as atdd_pure (mode=atdd_pure,
          carrying a slice_id and phase, NO execution_log_path / step_id),
    And there is no execution-log.json anywhere on disk,
    When the DES SubagentStop validator validates the return,
    Then the decision is ALLOW — the validator does NOT demand an
         execution-log.json that atdd_pure never produces,
    And the ExecutionLogReader is never consulted.

    Before T-C this RED-fails: the classic step-1 read raises LogFileNotFound
    and the validator returns block(LOG_FILE_NOT_FOUND).
    """
    reader = MissingLogReader()
    service = _make_service(reader)

    context = SubagentStopContext(
        execution_log_path="",
        project_id="atdd-pure-dispatch-lifecycle",
        step_id="",
        mode="atdd_pure",
        slice_id="slice-02",
        atdd_pure_phase="G_COMMIT",
    )

    decision = service.validate(context)

    assert decision.action == "allow", (
        f"atdd_pure SubagentStop return was {decision.action!r} "
        f"(reason={decision.reason!r}); expected 'allow' — atdd_pure produces "
        "no execution-log.json and the validator must not demand one"
    )
    assert reader.consulted is False, (
        "the atdd_pure SubagentStop path consulted the ExecutionLogReader — "
        "it must skip ExecutionLogReader entirely (the whole point of T-C)"
    )


# ---------------------------------------------------------------------------
# AT-2 — a classic SubagentStop return STILL requires its execution-log
# ---------------------------------------------------------------------------


def test_at2_classic_return_still_blocked_when_execution_log_missing():
    """Property: the classic SubagentStop contract is unregressed.

    Given a SubagentStop context resolved as classic (explicit mode="classic",
          carrying an execution_log_path + step_id),
    And the execution-log.json is missing,
    When the DES SubagentStop validator validates the return,
    Then the decision is BLOCK with a LOG_FILE_NOT_FOUND-shaped reason — the
         classic path still demands the execution-log,
    And the ExecutionLogReader IS consulted (the classic path reads it).
    """
    reader = MissingLogReader()
    service = _make_service(reader)

    context = SubagentStopContext(
        execution_log_path="/nonexistent/docs/feature/x/deliver/execution-log.json",
        project_id="some-classic-feature",
        step_id="01-01",
        mode="classic",
    )

    decision = service.validate(context)

    assert decision.action == "block", (
        "a classic SubagentStop return with a missing execution-log must be "
        f"blocked; got {decision.action!r}"
    )
    assert decision.reason is not None and "not found" in decision.reason.lower(), (
        f"expected a LOG_FILE_NOT_FOUND-shaped block reason, got {decision.reason!r}"
    )
    assert reader.consulted is True, (
        "the classic SubagentStop path must consult the ExecutionLogReader"
    )


# ---------------------------------------------------------------------------
# AT-3 — transcript extraction: last-match atdd_pure scan (G-4)
# ---------------------------------------------------------------------------


def test_at3_two_atdd_pure_marker_blocks_resolve_to_the_last(tmp_path):
    """Property: a transcript with two atdd_pure marker blocks → the LAST wins.

    Given an agent transcript carrying two DES-MODE:atdd_pure marker blocks
          (e.g. a re-dispatched slice — residue R7),
    When extract_des_context_from_transcript resolves the DES context,
    Then it resolves to the LAST atdd_pure block (the most recent dispatch),
         not the first — G-4 last-match scan,
    And the resolved context carries mode=atdd_pure and a slice_id, with NO
         step_id (atdd_pure carries no DES-STEP-ID).

    And (no regression): a classic transcript still uses the first-match return.
    """
    first = _ATDD_PURE_PROMPT.format(
        feature="atdd-pure-dispatch-lifecycle", phase="A_GREEN_ATS", slice="slice-01"
    )
    last = _ATDD_PURE_PROMPT.format(
        feature="atdd-pure-dispatch-lifecycle", phase="G_COMMIT", slice="slice-02"
    )
    transcript = _make_transcript(tmp_path, first, last)

    context = extract_des_context_from_transcript(transcript)

    assert context is not None, (
        "an atdd_pure transcript must resolve to a DES context, not None"
    )
    assert context.get("mode") == "atdd_pure", (
        f"expected mode=atdd_pure in the resolved context, got {context!r}"
    )
    assert context.get("slice_id") == "slice-02", (
        f"last-match scan must keep the LAST atdd_pure block (slice-02); "
        f"got slice_id={context.get('slice_id')!r} — first-match would yield slice-01"
    )
    assert context.get("step_id") is None, (
        "an atdd_pure transcript carries no DES-STEP-ID — the resolved context "
        f"must not carry a step_id; got {context.get('step_id')!r}"
    )

    # The handler's full DES-context resolution must propagate the atdd_pure
    # discriminant — a classic 5-tuple would route the return into the
    # execution-log-demanding classic path (G-3 regression).
    resolved = _resolve_des_context({"agent_transcript_path": transcript, "cwd": ""})
    assert isinstance(resolved, _AtddPureResolvedContext), (
        "an atdd_pure transcript must resolve to an _AtddPureResolvedContext — "
        f"got {type(resolved).__name__}; a classic tuple would demand an "
        "execution-log.json the atdd_pure dispatch never produces"
    )
    assert resolved.project_id == "atdd-pure-dispatch-lifecycle"
    assert resolved.slice_id == "slice-02"
    assert resolved.atdd_pure_phase == "G_COMMIT"

    # No regression — a classic transcript keeps the first-match return.
    classic_transcript = _make_transcript(
        tmp_path,
        _CLASSIC_PROMPT.format(feature="classic-feature", step="01-01"),
        name="classic-agent",
    )
    classic_context = extract_des_context_from_transcript(classic_transcript)
    assert classic_context is not None
    assert classic_context.get("project_id") == "classic-feature"
    assert classic_context.get("step_id") == "01-01"
