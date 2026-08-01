"""SubagentStopService - application service for step completion validation.

Orchestrates domain logic (StepCompletionValidator) and driven ports
(ExecutionLogReader, ScopeChecker, AuditLogWriter, TimeProvider) to produce
allow/block decisions for step completion.

This service implements the SubagentStopPort driver port interface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from des.ports.driven_ports.audit_log_writer import AuditEvent, AuditLogWriter
from des.ports.driven_ports.execution_log_reader import (
    ExecutionLogReader,
    LogFileCorrupted,
    LogFileNotFound,
)
from des.ports.driver_ports.pre_tool_use_port import HookDecision
from des.ports.driver_ports.subagent_stop_port import (
    SubagentStopContext,
    SubagentStopPort,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from des.domain.log_integrity_validator import (
        CorrectableEntry,
        LogIntegrityValidator,
    )
    from des.domain.step_completion_validator import StepCompletionValidator
    from des.ports.driven_ports.commit_verifier import (
        CommitVerificationResult,
        CommitVerifier,
    )
    from des.ports.driven_ports.discuss_review_reader import DiscussReviewReader
    from des.ports.driven_ports.feature_delta_reader import FeatureDeltaReader
    from des.ports.driven_ports.scope_checker import ScopeChecker
    from des.ports.driven_ports.time_provider_port import TimeProvider
    from des.ports.driven_ports.wave_active_store import (
        WaveActiveReader,
        WaveActiveWriter,
    )


# f-design-devops-review-gate slice-02 (the literal-lift): the closed set of
# waves whose gate-out stack carries a review-verdict gate. The live SubagentStop
# gate-out dispatch keys on the ACTIVE wave being in this set (lifted from the
# hardcoded "discuss" literal). DISCUSS keeps its structural + PO-review pair;
# DESIGN / DEVOPS each carry a single review-verdict consumer row.
_REVIEW_GATE_OUT_WAVES: frozenset[str] = frozenset({"discuss", "design", "devops"})

# The wave-parametric review-verdict consumer gate-ids the gate-out invoker routes
# to the SAME generic ReviewVerdictGate.evaluate core (the SSOT-reuse proof). The
# DISCUSS PO-review (verify-discuss-review) keeps its dedicated DiscussReviewGate
# branch -- its stack also carries the structural validate-feature-delta row.
_REVIEW_VERDICT_GATE_IDS: frozenset[str] = frozenset(
    {"verify-design-review", "verify-devops-review"}
)

# --- DISTILL gate-out: verify-spec-coverage (evolution P3.1/P3.2, ADVISORY) --
#
# DISCOVERY (this wiring slice): the four rows already declared in
# ``nWave/waves/distill.yaml`` ``gate_stack.gate-out`` (check-slice-at-
# completeness, gate-design-at-coherence, self-attest, verify-test-runner) are
# NOT reached by ``_discuss_gate_out_declarative`` -- ``_REVIEW_GATE_OUT_WAVES``
# is ``{discuss, design, devops}`` and does NOT include ``"distill"``. The
# DISTILL registry stack is a resolution-only proof (the composition ATs read
# ``wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")`` directly);
# no live invoker dispatches it today. Adding ``"distill"`` to
# ``_REVIEW_GATE_OUT_WAVES`` would activate the WHOLE stack at once, including
# ``check-slice-at-completeness`` (``on_failure: block``) which
# ``_discuss_gate_out_invoker`` does not route -- an uncatalogued gate_id fails
# CLOSED (``unknown_gate_stdout`` -> exit 1) and, being first in the list with
# ``on_failure: block``, would BLOCK EVERY DISTILL RETURN. That is exactly the
# non-zero blast radius this wiring must avoid on a MANDATORY wave, so this
# slice deliberately does NOT touch ``_REVIEW_GATE_OUT_WAVES`` / the shared
# discuss/design/devops invoker. Instead ``verify-spec-coverage`` gets its OWN
# narrow, ADVISORY-ONLY dispatch (``_distill_gate_out_spec_coverage`` below)
# that never blocks by construction (it always returns exit 0), independent of
# the still-unwired sibling rows.
_DISTILL_WAVE = "distill"
_SPEC_COVERAGE_GATE_ID = "verify-spec-coverage"

# Conventional per-feature paths (P3.1 checklist extraction + AT corpus scope).
# No shipped feature has produced a requirement-checklist.md yet (P3.1/P3.2 are
# greenfield), so there is no existing sibling convention to mirror; this is
# the documented fallback the wiring brief names when the convention is
# unclear: the feature's own DISTILL folder plus the repo-wide ``tests/`` tree
# (covering both Gherkin ATs colocated with DISTILL output and pytest ATs
# anywhere under ``tests/``).
_CHECKLIST_RELATIVE_PATH = "requirement-checklist.md"


def _distill_checklist_path(project_root: Path, feature_id: str) -> Path:
    """The P3.1 requirement-checklist path for ``feature_id`` under ``project_root``."""
    return (
        project_root
        / "docs"
        / "feature"
        / feature_id
        / "distill"
        / _CHECKLIST_RELATIVE_PATH
    )


def _distill_spec_coverage_at_dirs(project_root: Path, feature_id: str) -> list[Path]:
    """The AT-corpus directories to scan for ``feature_id`` -- existing dirs only."""
    candidates = (
        project_root / "docs" / "feature" / feature_id / "distill",
        project_root / "tests",
    )
    return [candidate for candidate in candidates if candidate.is_dir()]


def spec_coverage_gate_stdout(project_root: Path, feature_id: str) -> tuple[int, str]:
    """Evaluate the P3.2 spec-coverage gate for ``feature_id`` -- ADVISORY ONLY.

    Wraps the ALREADY-BUILT, pinned pure-computation functions in
    ``des.cli.verify_spec_coverage`` (checklist parsing, AT-corpus discovery,
    coverage-marker scanning, category counting) -- this function is pure
    orchestration, it invents no new gate logic. Always returns exit 0 (never
    a veto -- P3.1/P3.2 enforcement is advisory at DISTILL gate-out):

      * no checklist on disk / no AT-corpus directory / a malformed checklist
        -> an ``advisory`` verdict naming the arming gap, never silently
        passing (a silent pass on an unarmed gate is the eval's disease this
        gate exists to close).
      * every checklist row covered by >=1 AT -> a clean ``pass`` (silent).
      * >=1 uncovered row -> an ``advisory`` verdict naming each uncovered row
        + the mandatory categories among them (ui/e2e/nfr/security/
        validation/build), loud but non-blocking.

    ``verify_spec_coverage``'s pure helpers print human-readable lines on
    their OWN error/indeterminate branches (designed for standalone CLI use);
    called in-process from a hook path, that stdout would otherwise leak into
    the hook's own stdout protocol. Every call into that module is wrapped in
    ``redirect_stdout`` so this function is silent on the real stdout by
    construction, regardless of which branch fires.
    """
    import io
    from contextlib import redirect_stdout

    from des.application import spec_coverage_attribution as attribution
    from des.application import wave_gate_stack_dispatch as wgs
    from des.application.feature_at_files import (
        feature_tag_files,
        feature_tagged_test_files,
    )
    from des.cli import verify_spec_coverage as spec_coverage_cli

    def _best_effort_ids(path: Path) -> set[str]:
        # An unparseable AT file never blocks the advisory -- best effort:
        # skip its (unknowable) contribution to coverage.
        ids_or_exit = spec_coverage_cli._covered_ids_in_file(path)
        return ids_or_exit if isinstance(ids_or_exit, set) else set()

    checklist_path = _distill_checklist_path(project_root, feature_id)
    if not checklist_path.is_file():
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason=(
                f"no requirement-checklist.md -- spec-coverage not yet armed "
                f"for this feature (expected at {checklist_path})"
            ),
            advice=[
                "extract the requirement checklist at DISTILL-open (P3.1) to "
                f"{checklist_path} to arm the spec-coverage gate for this "
                "feature.",
            ],
        )

    if attribution.checklist_mentions_undeclared_decoy(checklist_path, feature_id):
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason=(
                f"the requirement checklist at {checklist_path} mentions "
                f"'@feature-{feature_id}' without a valid line-anchored, "
                "own-line declaration -- a decoy occurrence (e.g. inside a "
                "requirement's prose) must not be mistaken for a genuine "
                "self-declaration."
            ),
            advice=[
                f"add a dedicated line '@feature-{feature_id}' to the "
                "checklist's head to properly self-declare its identity.",
            ],
        )

    at_dirs = _distill_spec_coverage_at_dirs(project_root, feature_id)
    if not at_dirs:
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason=(
                "no AT-corpus directory found for this feature (checked "
                f"{checklist_path.parent} and {project_root / 'tests'})"
            ),
            advice=[
                "author ATs under tests/ (or the feature's distill/ folder) "
                "so the spec-coverage gate has a corpus to scan.",
            ],
        )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        requirements_or_exit = spec_coverage_cli._parse_checklist(checklist_path)
        if isinstance(requirements_or_exit, int):
            return wgs.advisory_stdout(
                _SPEC_COVERAGE_GATE_ID,
                reason=(
                    "the requirement checklist is malformed or unreadable -- "
                    "degraded to advisory-indeterminate rather than a silent "
                    f"pass ({buffer.getvalue().strip() or 'see checklist file'})"
                ),
                advice=[
                    "fix the checklist grammar (one '| R<n> | text | category |'"
                    " or '- R<n> [category] text' row per requirement) and "
                    "re-run.",
                ],
            )
        requirements = requirements_or_exit

        scanned_files = sorted(
            {path for at_dir in at_dirs for path in spec_coverage_cli._discover(at_dir)}
        )

    attributed_files = tuple(
        sorted(
            p
            for p in set(feature_tag_files(project_root, feature_id))
            | set(feature_tagged_test_files(project_root, feature_id))
            if spec_coverage_cli.is_at_file(p)
        )
    )
    outcome = attribution.resolve_attribution(
        feature_id, scanned_files, attributed_files
    )

    if isinstance(outcome, attribution.EmptyAttribution):
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason=(
                f"no file anywhere under {project_root} declares "
                f"'@feature-{feature_id}' -- attribution is empty (A = ∅)."
            ),
            advice=[
                f"head-tag the feature's own AT file(s) with '@feature-{feature_id}'.",
            ],
        )
    if isinstance(outcome, attribution.WrongScope):
        dirs = sorted({str(p.parent) for p in outcome.attributed_files})
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason=(
                "the scanned AT corpus does not intersect the files "
                f"attributed to '{feature_id}' (S = D ∩ A = ∅)."
            ),
            advice=[f"point the AT corpus at: {', '.join(dirs)}"],
        )
    if isinstance(outcome, attribution.NoDeclaredIdentity):
        # Unreachable in practice -- feature_id is a required str parameter
        # here -- but kept honest rather than assert-crashing an advisory
        # (never-veto) path.
        return wgs.advisory_stdout(
            _SPEC_COVERAGE_GATE_ID,
            reason="no feature identity was given -- spec-coverage cannot attribute.",
            advice=["pass a feature_id to spec_coverage_gate_stdout."],
        )

    with redirect_stdout(buffer):
        covered_or_exit = attribution.aggregate_covered_ids(
            outcome.scoped_files, _best_effort_ids
        )
    covered = covered_or_exit if isinstance(covered_or_exit, set) else set()

    counts = spec_coverage_cli._category_counts(requirements, covered)
    uncovered = attribution.uncovered_requirements(requirements, covered)
    if not uncovered:
        return wgs.pass_stdout(_SPEC_COVERAGE_GATE_ID)

    mandatory_uncovered = sorted(
        {
            req.category
            for req in uncovered
            if req.category in spec_coverage_cli.MANDATORY_CATEGORIES
        }
    )
    uncovered_rows = [
        {"id": req.req_id, "category": req.category, "text": req.text}
        for req in uncovered
    ]
    reason = (
        f"{len(uncovered)} of {len(requirements)} requirement(s) have NO "
        f"covering AT ({', '.join(row['id'] for row in uncovered_rows)})"
        + (
            f"; MANDATORY categories uncovered: {', '.join(mandatory_uncovered)}"
            if mandatory_uncovered
            else ""
        )
    )
    return 0, json.dumps(
        {
            "verdict": "advisory",
            "gate_id": _SPEC_COVERAGE_GATE_ID,
            "reason": reason,
            "uncovered": uncovered_rows,
            "mandatory_categories_uncovered": mandatory_uncovered,
            "counts": counts,
            "recovery_suggestions": [spec_coverage_cli._HOW_TO_FIX],
        }
    )


class SubagentStopService(SubagentStopPort):
    """Validates step completion when a subagent finishes.

    Flow:
      1. Read project_id via ExecutionLogReader.read_project_id()
         - If not found: return block (LOG_FILE_NOT_FOUND)
         - If mismatch: return block (PROJECT_ID_MISMATCH)
      2. Read step events via ExecutionLogReader.read_step_events()
      3. Validate completion via StepCompletionValidator.validate()
         - If invalid: log HOOK_SUBAGENT_STOP_FAILED, return block
      3.5. Verify git commit via CommitVerifier (if cwd provided)
         - If no matching commit: return block (COMMIT_NOT_VERIFIED)
         - Fail-closed: git errors also block
      4. Check scope via ScopeChecker.check_scope()
         - If violations: log SCOPE_VIOLATION (warning, does not block)
      5. Log HOOK_SUBAGENT_STOP_PASSED, return allow
    """

    def __init__(
        self,
        log_reader: ExecutionLogReader,
        completion_validator: StepCompletionValidator,
        scope_checker: ScopeChecker,
        audit_writer: AuditLogWriter,
        time_provider: TimeProvider,
        commit_verifier: CommitVerifier | None = None,
        integrity_validator: LogIntegrityValidator | None = None,
        wave_active_reader: WaveActiveReader | None = None,
        feature_delta_reader: FeatureDeltaReader | None = None,
        discuss_review_reader: DiscussReviewReader | None = None,
        review_readers: dict[str, DiscussReviewReader] | None = None,
        wave_active_writer: WaveActiveWriter | None = None,
    ) -> None:
        self._log_reader = log_reader
        self._completion_validator = completion_validator
        self._scope_checker = scope_checker
        self._audit_writer = audit_writer
        self._time_provider = time_provider
        self._commit_verifier = commit_verifier
        self._integrity_validator = integrity_validator
        self._wave_active_reader = wave_active_reader
        self._feature_delta_reader = feature_delta_reader
        self._discuss_review_reader = discuss_review_reader
        # fix-floor-auto-close-cross-wave: the WRITER capability the cross-wave
        # auto-close needs (clear() of the wave-active floor). Additive DI: an
        # unwired writer (None) makes the auto-close a no-op (the floor stays
        # armed -- the pre-feature behaviour), so the close fires ONLY on the
        # production-wired path.
        self._wave_active_writer = wave_active_writer
        # f-design-devops-review-gate slice-02 (the literal-lift): per-wave
        # review-verdict readers for the DESIGN / DEVOPS gate-out consumer rows
        # (verify-design-review / verify-devops-review). The DISCUSS PO-review
        # keeps its own dedicated reader (above) -- its gate-out stack also
        # carries the structural validate-feature-delta row, so it is not a plain
        # review-verdict consumer. degrade-LOUD: a wave with no wired reader makes
        # its review-verdict row a clean pass (the additive-DI skip-when-unwired
        # behavior preserved verbatim from the DISCUSS branch).
        self._review_readers: dict[str, DiscussReviewReader] = review_readers or {}

    def validate(
        self,
        context: SubagentStopContext,
        hook_id: str | None = None,
    ) -> HookDecision:
        """Validate step completion for a subagent.

        Args:
            context: Parsed context from the hook protocol
            hook_id: Optional correlation ID from the adapter hook invocation.
                When provided, included in all emitted audit events for correlation.

        Returns:
            HookDecision indicating allow or block
        """
        # Step -1: DISCUSS gate-OUT (slice-07). A discuss-wave RETURN must carry a
        # value-bearing slice plan (structural 5-column + slice-06 cohesion-MECC,
        # ONE call). The gate only VETOES (§22.0): a non-PASS DiscussGateOut token
        # -> block; an unreadable feature-delta -> INDETERMINATE degrade-LOUD
        # block (§17). It runs BEFORE the mode branch so it gates an atdd_pure
        # discuss return as well as a classic one. Additive DI: no
        # feature_delta_reader / wave_active_reader wired -> branch skipped (never
        # breaks existing wiring). The discriminant keys on the ACTIVE wave being
        # 'discuss' (read from the WaveActiveReader floor at cwd, never
        # self-reported); a non-discuss return falls through untouched.
        gate_out_block = self._discuss_gate_out_declarative(context, hook_id=hook_id)
        if gate_out_block is not None:
            return gate_out_block

        # Step -0.9: DISTILL gate-OUT verify-spec-coverage (evolution P3.1/P3.2,
        # ADVISORY-ONLY). Fires on EVERY DISTILL return (active wave == 'distill'
        # per the WaveActiveReader floor, never self-reported) independent of the
        # still-unwired sibling registry rows (see the module-level DISCOVERY
        # comment above `_distill_gate_out_spec_coverage`). Never returns a block
        # -- it only surfaces an advisory audit record when the checklist is
        # unarmed or a requirement is uncovered.
        self._distill_gate_out_spec_coverage(context, hook_id=hook_id)

        # Step -0.5: wave-only Agent()-dispatch guard (WGO-001, ADD-not-mutate).
        # A wave-only return is execution-log-free AND step-free (a DES-WAVE
        # marker + a project id, no execution-log step id -- the Agent()
        # orchestration return shape). The wave review-verdict gate-out above is
        # the ONLY decision such a return needs: if it found no objection (None),
        # the return is allowed; it must NEVER fall into the classic Step-1
        # execution-log read (which would block on LogFileNotFound for a context
        # that has no execution log by construction). Keyed on the wave-only
        # shape; the classic and atdd_pure entries are byte-stable (atdd_pure is
        # routed by the mode branch at Step 0; a classic context always carries
        # a non-empty execution_log_path + step_id).
        if context.step_id == "" and context.execution_log_path == "":
            if context.mode == "atdd_pure":
                return self._validate_atdd_pure(context, hook_id)
            # fix-floor-auto-close-cross-wave (Option A): the attested gate-OUT
            # above found no objection (a PASS). When this wave-only return is the
            # ACTIVE wave's OWNER's terminal return, close the wave-active floor so
            # the next cross-wave dispatch is not falsely blocked as a stale
            # in-wave bypass. In-wave sub-dispatches never reach here (they are
            # PreToolUse events), so in-wave persistence is preserved by
            # construction (I3/I4 untouched). The close is ADDITIVE -- the gate-OUT
            # ALLOW decision is unchanged.
            self._maybe_close_owner_floor(context)
            return HookDecision.allow()

        # Step 0: Mode branch (T-C / F-DES-ATDD-PURE-DISPATCH-LIFECYCLE).
        # An atdd_pure dispatch is roadmap-free and produces no
        # execution-log.json -- the classic step-1..3.5 pipeline (which reads
        # the execution-log via ExecutionLogReader and verifies commit
        # trailers) is structurally inapplicable. The atdd_pure return is
        # validated against the AT-completion ledger / commit-trailer surface;
        # T-C does the minimum to ALLOW the return (no execution-log demand),
        # trailer verification is deferred to T-G (HOOK-GATES slice-02).
        if context.mode == "atdd_pure":
            return self._validate_atdd_pure(context, hook_id)

        # Step 1: Read and validate project_id
        try:
            log_project_id = self._log_reader.read_project_id(
                context.execution_log_path
            )
        except LogFileNotFound:
            return HookDecision.block(
                reason=f"Execution log not found: {context.execution_log_path}",
                recovery_suggestions=[
                    "Create execution-log.json file",
                    "Run orchestrator to initialize log",
                ],
            )
        except LogFileCorrupted as e:
            return HookDecision.block(
                reason=f"Invalid JSON in execution log: {e}",
                recovery_suggestions=["Fix JSON syntax errors in execution-log.json"],
            )

        if log_project_id != context.project_id:
            return HookDecision.block(
                reason=f"Project ID mismatch: expected '{context.project_id}', found '{log_project_id}'",
                recovery_suggestions=[
                    f"Verify you're working on project '{context.project_id}'",
                    "Check DES-PROJECT-ID marker in prompt",
                ],
            )

        # Earned-Trust intake validation: project_id IS feature_id on DEV and
        # drives the Task-Id grep in commit verification. Empty/whitespace
        # values would silently disable AND-semantics at the verifier port,
        # so reject upstream rather than defensively clamping at the caller.
        if not context.project_id or not context.project_id.strip():
            return HookDecision.block(
                reason="EMPTY_PROJECT_ID: feature_id missing from execution context",
                recovery_suggestions=[
                    "Ensure execution-log carries a non-empty project_id",
                    "Check DES-PROJECT-ID marker in prompt",
                ],
            )

        # Step 2: Read step events
        try:
            events = self._log_reader.read_step_events(
                context.execution_log_path,
                context.step_id,
            )
        except (LogFileNotFound, LogFileCorrupted) as e:
            return HookDecision.block(
                reason=f"Failed to read step events: {e}",
                recovery_suggestions=["Check execution-log.json file integrity"],
            )

        # Step 2.5: Check and correct log integrity (BEFORE completion check)
        # Runs always, even on retry -- correction is better than blocking
        self._check_and_correct_integrity(context)

        # Re-read events after potential correction so completion validates
        # against corrected timestamps
        try:
            events = self._log_reader.read_step_events(
                context.execution_log_path,
                context.step_id,
            )
        except (LogFileNotFound, LogFileCorrupted):
            pass  # Use original events if re-read fails

        # Step 3: Validate completion
        completion = self._completion_validator.validate(events)

        if not completion.is_valid:
            error_parts = list(completion.error_messages)
            error_message = (
                "; ".join(error_parts) if error_parts else "Validation failed"
            )

            if context.stop_hook_active:
                # Second attempt: allow to prevent infinite loop, but still log FAILED
                self._log_failed(
                    context.project_id,
                    context.step_id,
                    error_parts,
                    allowed_despite_failure=True,
                    hook_id=hook_id,
                    turns_used=context.turns_used,
                    tokens_used=context.tokens_used,
                )
                return HookDecision.allow()

            # First attempt: block so sub-agent can try to fix
            self._log_failed(
                context.project_id,
                context.step_id,
                error_parts,
                hook_id=hook_id,
                turns_used=context.turns_used,
                tokens_used=context.tokens_used,
            )
            return HookDecision.block(
                reason=error_message,
                recovery_suggestions=completion.recovery_suggestions,
            )

        # Step 3.5: Verify git commit exists (only if phases passed and cwd provided)
        # SF parity (commit ae109bd8): require AND-semantics on Step-Id + Task-Id
        # to prevent cross-feature commit confusion. context.project_id IS the
        # feature_id on DEV (validated in step 1 above).
        if context.cwd and self._commit_verifier:
            commit_result = self._commit_verifier.verify_commit(
                context.step_id,
                context.cwd,
                feature_id_filter=context.project_id,
            )
            if not commit_result.verified:
                self._log_commit_not_verified(context, commit_result, hook_id=hook_id)
                return HookDecision.block(
                    reason=f"COMMIT_NOT_VERIFIED: {commit_result.error_reason}",
                    recovery_suggestions=[
                        f"Create a git commit with trailer 'Step-Id: {context.step_id}'",
                        f"Include trailer 'Task-Id: {context.project_id}' on the same commit",
                        "Ensure the COMMIT phase actually runs git commit",
                        "Check that git is available and you're in a git repository",
                    ],
                )
            self._log_commit_verified(context, commit_result, hook_id=hook_id)

        # Step 4: Check scope (warning only, does not block)
        self._check_and_log_scope(context)

        # Step 5: All valid
        self._log_passed(
            context.project_id,
            context.step_id,
            hook_id=hook_id,
            turns_used=context.turns_used,
            tokens_used=context.tokens_used,
        )
        return HookDecision.allow()

    def _maybe_close_owner_floor(self, context: SubagentStopContext) -> None:
        """Close the wave-active floor on the wave OWNER's terminal gate-OUT PASS.

        fix-floor-auto-close-cross-wave (Option A, Ale 2026-06-23): the
        cross-wave auto-close. Reached ONLY on the wave-only return PASS path
        (an execution-log-free, step-free return whose attested gate-OUT found
        no objection). Clears the floor IFF the returning ``subagent_type`` OWNS
        the ACTIVE wave -- ``WAVE_OWNERS[subagent_type] == active wave``, OR (the
        dual-ownership superset, slice-02) the returner is the platform-architect
        and the active wave is one of its two owned waves
        ``_PLATFORM_ARCHITECT_WAVES = {"design", "devops"}`` (mirrors
        ``wave_dispatch_guard_policy._marker_is_on_spine``). The un-gameable
        terminal "wave is over" signal. The active wave is read from the floor at
        cwd (never self-reported).

        A non-owner return (a reviewer / anything outside WAVE_OWNERS) does NOT
        close (AC-3): ``WAVE_OWNERS.get`` returns None, never equal to the active
        wave. A veto never reaches here (the gate-OUT blocked first, AC-4). An
        in-wave sub-dispatch never reaches here (PreToolUse, AC-2).

        Additive DI / fail-safe: an unwired reader or writer, no cwd, no floor,
        or a non-owner return -> no-op (the floor stays armed). The close only
        ever REMOVES a floor whose owner just terminally returned; it never arms.
        """
        if self._wave_active_reader is None or self._wave_active_writer is None:
            return
        if not context.cwd or not context.subagent_type:
            return

        from des.domain.wave_active import WaveActiveRecord
        from des.domain.wave_dispatch_guard_policy import (
            _PLATFORM_ARCHITECT,
            _PLATFORM_ARCHITECT_WAVES,
            WAVE_OWNERS,
        )

        project_root = Path(context.cwd)
        wave_state = self._wave_active_reader.read(project_root)
        if not isinstance(wave_state, WaveActiveRecord):
            return
        owner_wave = WAVE_OWNERS.get(context.subagent_type)
        if owner_wave is None:
            return
        if owner_wave == wave_state.wave:
            pass  # standard single-owner match (AC-6 design close preserved)
        elif (
            context.subagent_type == _PLATFORM_ARCHITECT
            and wave_state.wave in _PLATFORM_ARCHITECT_WAVES
        ):
            pass  # dual-owner closing its devops wave (AC-5)
        else:
            return
        self._wave_active_writer.clear(project_root)

    def _distill_gate_out_spec_coverage(
        self,
        context: SubagentStopContext,
        hook_id: str | None,
    ) -> None:
        """Fire the P3.2 spec-coverage gate on a DISTILL return -- NEVER blocks.

        Keyed on the ACTIVE wave being ``"distill"`` (read from the
        WaveActiveReader floor at cwd, never self-reported) -- mirrors the
        discriminant style of ``_maybe_close_owner_floor`` /
        ``_discuss_gate_out_declarative``. Additive DI / fail-safe: no
        wave_active_reader wired, no cwd, no active-distill floor, or no
        project_id -> no-op (never raises, never blocks -- this step has no
        HookDecision to return).

        The gate itself (`spec_coverage_gate_stdout`) always exits 0; when its
        verdict is ``advisory`` this emits a `HOOK_SUBAGENT_STOP_ADVISORY`
        audit record so the finding is surfaced LOUD (not a silent skip) even
        though it never vetoes the return.
        """
        if self._wave_active_reader is None or not context.cwd:
            return
        if not context.project_id:
            return

        from des.domain.wave_active import WaveActiveRecord

        project_root = Path(context.cwd)
        wave_state = self._wave_active_reader.read(project_root)
        if not isinstance(wave_state, WaveActiveRecord):
            return
        if wave_state.wave != _DISTILL_WAVE:
            return

        exit_code, stdout = spec_coverage_gate_stdout(project_root, context.project_id)
        self._emit_spec_coverage_advisory(exit_code, stdout, context, hook_id=hook_id)

    def _emit_spec_coverage_advisory(
        self,
        exit_code: int,
        stdout: str,
        context: SubagentStopContext,
        *,
        hook_id: str | None,
    ) -> None:
        """Audit-log the spec-coverage verdict when it is an advisory finding.

        A clean ``pass`` (every requirement covered) emits nothing -- an
        advisory record only exists to surface a NON-clean finding LOUD. Fail-
        OPEN on unparseable stdout (never raises; the gate verdict already
        stands as advisory-only, no HookDecision is affected either way).
        """
        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(payload, dict) or payload.get("verdict") != "advisory":
            return
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_ADVISORY",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.slice_id or "",
                hook_id=hook_id,
                data={
                    "gate_id": str(payload.get("gate_id", _SPEC_COVERAGE_GATE_ID)),
                    "reason": str(payload.get("reason", "")),
                    "exit_code": str(exit_code),
                },
            )
        )

    def _discuss_gate_out_declarative(
        self,
        context: SubagentStopContext,
        hook_id: str | None,
    ) -> HookDecision | None:
        """Run the DISCUSS gate-OUT stack DECLARATIVELY; return a block, or None.

        f-declarative-gate-composition (OB-1): the DISCUSS gate-OUT stack is
        declared as DATA in ``wave_gate_stacks.discuss.gate-out`` -- the readable
        2-row list ``[validate-feature-delta, verify-discuss-review]`` the
        imperative branch carried as two hand-coded sub-calls (the structural
        cohesion-MECC veto THEN the PO-review consumer veto). This generic path
        SELECTS that stack (off the active wave), ITERATES it via the EXISTING
        dispatcher core (iterate-in-order, halt-at-first-veto), and CARRIES each
        gate's specific reason + recovery through (OB-2 parity). The ordering
        (structural before PO-review) is now VISIBLE in the list, not buried in
        branch control-flow.

        Returns None (fall through) when: no reader/wave-reader wired, no cwd, the
        active wave is not 'discuss', or the declared stack is empty/clean. A
        non-PASS gate is a named-LOUD VETO; the per-gate decision is the SAME pure
        core the imperative branch ran (``DiscussGateOut.evaluate`` /
        ``DiscussReviewGate.evaluate``), keyed by gate-id.

        IDEMPOTENT: it reads only the sealed feature-delta artefact + the ledger
        record -- re-running on identical content re-earns the identical verdict
        (§21.2.4).
        """
        if self._feature_delta_reader is None or self._wave_active_reader is None:
            return None
        if not context.cwd:
            return None

        from des.application import wave_gate_stack_dispatch as wgs
        from des.domain.wave_active import WaveActiveRecord

        project_root = Path(context.cwd)
        wave_state = self._wave_active_reader.read(project_root)
        # f-design-devops-review-gate slice-02 (the literal-lift): the gate-out
        # dispatch keys on the ACTIVE wave, not the hardcoded "discuss" literal.
        # The closed set of waves carrying a review-verdict gate-out stack is the
        # discriminant; a wave outside it (or no floor) falls through untouched.
        # DISCUSS behavior is identical when the active wave == "discuss"
        # (resolve_stack("discuss", "gate-out") + the same invoker routing).
        if not isinstance(wave_state, WaveActiveRecord):
            return None
        active_wave = wave_state.wave
        if active_wave not in _REVIEW_GATE_OUT_WAVES:
            return None

        resolved = wgs.resolve_stack(active_wave, "gate-out", start=project_root)
        if resolved.indeterminate is not None:
            reason = f"WAVE_GATE_STACK_INDETERMINATE: {resolved.indeterminate}"
            return self._discuss_gate_block(
                context,
                reason=reason,
                gate_data={"wave_gate_stack": "indeterminate"},
                recovery_suggestions=[
                    "Reinstall so nWave/waves/ ships: "
                    "python scripts/install/install_nwave.py",
                    "Or name the registry explicitly: "
                    "NWAVE_WAVES_DIR=<repo>/nWave/waves",
                ],
                hook_id=hook_id,
            )
        stack = resolved.rows
        if not stack:
            return None

        content = self._feature_delta_reader.read(project_root, context.project_id)
        invoker = self._discuss_gate_out_invoker(
            context, project_root, content, active_wave
        )
        result = wgs.dispatch_wave_stack(stack, f"{active_wave}.gate-out", invoker)
        return self._block_from_gate_out_composition(result, context, hook_id=hook_id)

    def _discuss_gate_out_invoker(
        self,
        context: SubagentStopContext,
        project_root: Path,
        content: str | None,
        active_wave: str,
    ) -> Callable[[str, dict[str, str]], tuple[int, str]]:
        """Build the gate-OUT invoker routing catalog gate-ids to the pure cores.

        The structural row (``validate-feature-delta``) routes to
        ``DiscussGateOut.evaluate`` over the already-read feature-delta content;
        the DISCUSS PO-review row (``verify-discuss-review``) routes to
        ``DiscussReviewGate.evaluate`` over the ledger record + the content seal.

        f-design-devops-review-gate slice-02 (the literal-lift): the DESIGN /
        DEVOPS review-verdict consumer rows (``verify-design-review`` /
        ``verify-devops-review``) route to the wave-parametric
        ``ReviewVerdictGate.evaluate`` over the per-wave ledger record + the SAME
        content seal -- the SSOT-reuse proof (zero new verdict logic, only the
        wave name changes). An uncatalogued gate-id fails closed, named. The pure
        cores' verdicts and the tailored recovery are PRESERVED verbatim from the
        imperative branch.
        """
        from des.application import wave_gate_stack_dispatch as wgs

        def invoke(gate_id: str, _ctx: dict[str, str]) -> tuple[int, str]:
            if gate_id == "validate-feature-delta":
                return self._gate_out_structural(content)
            if gate_id == "verify-discuss-review":
                return self._gate_out_po_review(context, project_root, content)
            if gate_id in _REVIEW_VERDICT_GATE_IDS:
                return self._gate_out_review_verdict(
                    context, project_root, content, active_wave, gate_id
                )
            return wgs.unknown_gate_stdout(gate_id)

        return invoke

    def _gate_out_review_verdict(
        self,
        context: SubagentStopContext,
        project_root: Path,
        content: str | None,
        active_wave: str,
        gate_id: str,
    ) -> tuple[int, str]:
        """The wave-parametric review-verdict consumer veto (DESIGN / DEVOPS).

        The SSOT-reuse proof: the SAME generic ``ReviewVerdictGate.evaluate`` core
        the DESIGN / DEVOPS verify CLIs delegate to, driven here from the live
        SubagentStop gate-out dispatch. Reads the latest per-wave review verdict
        via the wired per-wave reader + seals the feature-delta content, then
        projects PASS -> pass / VETOED -> veto / INDETERMINATE -> veto (absence
        reads as a named-LOUD veto, never a silent pass -- DDD-7 / K1).

        Additive DI (skip-when-unwired, preserved verbatim from the DISCUSS
        PO-review branch): no per-wave reader wired -> a clean pass.
        """
        import hashlib

        from des.application import wave_gate_stack_dispatch as wgs
        from des.domain.review_verdict_gate import ReviewGateToken, ReviewVerdictGate

        reader = self._review_readers.get(active_wave)
        if reader is None:
            return wgs.pass_stdout(gate_id)
        assert content is not None
        record = reader.latest(project_root, context.project_id)
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        review = ReviewVerdictGate.evaluate(record, expected_hash)
        if review.token is ReviewGateToken.PASS:
            return wgs.pass_stdout(gate_id)
        reason = (
            f"{active_wave.upper()}_REVIEW_{review.token.value}: "
            f"{active_wave} review verdict {review.detail}"
        )
        return wgs.veto_stdout(
            gate_id,
            reason=reason,
            recovery=[
                f"The {active_wave.upper()} review verdict is "
                f"{review.token.value} ({review.detail}) -- record a fresh "
                f"APPROVED review verdict via `des record-{active_wave}-review` "
                "whose artefact hash matches the current "
                "docs/feature/<id>/feature-delta.md, then retry the return.",
                "If the verdict is stale (its sealed hash no longer matches the "
                f"current feature-delta), re-run the {active_wave} review against "
                "the latest feature-delta so the artefact-currency seal is "
                "current.",
            ],
        )

    def _gate_out_structural(self, content: str | None) -> tuple[int, str]:
        """The structural cohesion-MECC veto (DiscussGateOut.evaluate, gate-OUT row 1)."""
        from des.application import wave_gate_stack_dispatch as wgs
        from des.domain.discuss_gate import DiscussGateOut, DiscussGateOutToken

        gate_out = DiscussGateOut.evaluate(content)
        if gate_out.token is DiscussGateOutToken.PASS:
            return wgs.pass_stdout("validate-feature-delta")
        reason = f"DISCUSS_GATE_OUT_{gate_out.token.value}: {gate_out.detail}"
        return wgs.veto_stdout(
            "validate-feature-delta",
            reason=reason,
            recovery=[
                "The DISCUSS return was rejected -- the feature-delta slice plan is "
                "not value-bearing (e.g. every slice is pure infrastructure). "
                "Rewrite the slice plan in docs/feature/<id>/feature-delta.md so "
                "each slice delivers observable user value, then re-run the review.",
                "Ensure the feature-delta slice plan passes the DISCUSS gate-OUT "
                "review (value-bearing slices, current artefact hash), then retry "
                "the discuss return.",
            ],
        )

    def _gate_out_po_review(
        self,
        context: SubagentStopContext,
        project_root: Path,
        content: str | None,
    ) -> tuple[int, str]:
        """The PO-review consumer veto (DiscussReviewGate.evaluate, gate-OUT row 2).

        Reaches this row ONLY after the structural row passed (halt-at-first-veto),
        so ``content`` is guaranteed readable. Additive DI: no
        ``discuss_review_reader`` wired -> the row is a clean pass (the imperative
        branch's skip-when-unwired behavior, preserved).
        """
        import hashlib

        from des.application import wave_gate_stack_dispatch as wgs
        from des.domain.discuss_review_gate import (
            DiscussReviewGate,
            DiscussReviewGateToken,
        )

        if self._discuss_review_reader is None:
            return wgs.pass_stdout("verify-discuss-review")
        assert content is not None
        record = self._discuss_review_reader.latest(project_root, context.project_id)
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        review = DiscussReviewGate.evaluate(record, expected_hash)
        if review.token is DiscussReviewGateToken.PASS:
            return wgs.pass_stdout("verify-discuss-review")
        reason = f"DISCUSS_PO_REVIEW_{review.token.value}: {review.detail}"
        return wgs.veto_stdout(
            "verify-discuss-review",
            reason=reason,
            recovery=[
                "The DISCUSS PO-review returned NEEDS_REVISION -- address the "
                "reviewer's findings in docs/feature/<id>/feature-delta.md, then "
                "record a fresh APPROVED PO-review verdict whose artefact hash "
                "matches the updated feature-delta before retrying the return.",
                "If the verdict is stale (its sealed hash no longer matches the "
                "current feature-delta), re-run the PO-review against the latest "
                "feature-delta so the artefact-currency seal is current.",
            ],
        )

    def _block_from_gate_out_composition(
        self,
        result: object,
        context: SubagentStopContext,
        hook_id: str | None,
    ) -> HookDecision | None:
        """Map a halted gate-OUT composition to a named-LOUD block, or None.

        Carries the blocking gate's specific reason + recovery (OB-2 parity) and
        emits the SAME ``HOOK_SUBAGENT_STOP_FAILED`` audit event the imperative
        branch emitted. A clean iteration is "no objection found" -> None
        (Invariant 4 -- never an authorizing GO).
        """
        from des.application import wave_gate_stack_dispatch as wgs
        from des.application.flavor_dispatcher import CompositionResult

        assert isinstance(result, CompositionResult)
        if not result.halted or result.blocking_gate_id is None:
            return None
        blocking = next(
            (r for r in result.gate_results if r.gate_id == result.blocking_gate_id),
            None,
        )
        assert blocking is not None
        reason = wgs.reason_from_stdout(blocking.stdout, blocking.gate_id)
        return self._discuss_gate_block(
            context,
            reason=reason,
            gate_data={"discuss_gate_out": blocking.gate_id},
            recovery_suggestions=list(blocking.recovery_suggestions),
            hook_id=hook_id,
        )

    def _discuss_gate_block(
        self,
        context: SubagentStopContext,
        *,
        reason: str,
        gate_data: dict[str, str],
        recovery_suggestions: list[str],
        hook_id: str | None,
    ) -> HookDecision:
        """Emit the named-LOUD DISCUSS gate-OUT block (audit event + decision).

        Per-caller recovery (DESIGN O-1): the sink does NOT author the recovery
        list and does NOT parse the reason token -- each caller passes its own
        targeted recovery_suggestions naming the fix for its specific veto.
        """
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_FAILED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.slice_id or "",
                hook_id=hook_id,
                data={"reason": reason, **gate_data},
            )
        )
        return HookDecision.block(
            reason=reason, recovery_suggestions=recovery_suggestions
        )

    def _validate_atdd_pure(
        self,
        context: SubagentStopContext,
        hook_id: str | None,
    ) -> HookDecision:
        """Validate an atdd_pure crafter return (T-C — no execution-log demand).

        The atdd_pure dispatch lifecycle is execution-log-free: there is no
        execution-log.json to read, no classic step-event sequence to validate
        and no per-step git trailer to verify here (trailer verification is
        T-G). The minimum to ALLOW the return is: confirm a non-empty
        project_id (the feature_id) and emit the PASSED audit event. The
        ExecutionLogReader is never consulted.
        """
        if not context.project_id or not context.project_id.strip():
            return HookDecision.block(
                reason="EMPTY_PROJECT_ID: feature_id missing from atdd_pure dispatch context",
                recovery_suggestions=[
                    "Ensure the atdd_pure dispatch carries a non-empty DES-PROJECT-ID marker",
                ],
            )

        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_PASSED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.slice_id or "",
                hook_id=hook_id,
                data={
                    "mode": "atdd_pure",
                    "slice_id": context.slice_id,
                    "atdd_pure_phase": context.atdd_pure_phase,
                },
            )
        )
        return HookDecision.allow()

    def _check_and_correct_integrity(self, context: SubagentStopContext) -> None:
        """Check log integrity and correct fabricated timestamps (zero trust).

        Runs BEFORE stop_hook_active check -- correction always happens.
        Only corrects events for context.step_id written during task window.
        """
        if not self._integrity_validator:
            return

        try:
            all_events = self._log_reader.read_all_events(
                context.execution_log_path,
            )
        except (LogFileNotFound, LogFileCorrupted):
            return

        result = self._integrity_validator.validate(
            step_id=context.step_id,
            all_events=all_events,
            task_start_time=context.task_start_time or None,
        )

        # Correct fabricated timestamps; track which were actually corrected
        corrected_entries: set[int] = set()
        if result.correctable_entries:
            corrected_entries = self._correct_timestamps(
                context, result.correctable_entries
            )

        # Log remaining warnings (non-correctable issues like phase name typos)
        for warning in result.warnings:
            # Skip warnings that correspond to actually corrected entries
            is_corrected = any(
                entry.index in corrected_entries
                and entry.phase_name in warning
                and entry.original_timestamp in warning
                for entry in result.correctable_entries
            )
            if not is_corrected:
                self._audit_writer.log_event(
                    AuditEvent(
                        event_type="LOG_INTEGRITY_WARNING",
                        timestamp=self._time_provider.now_utc().isoformat(),
                        feature_name=context.project_id,
                        step_id=context.step_id,
                        data={"warning": warning},
                    )
                )

    def _correct_timestamps(
        self,
        context: SubagentStopContext,
        correctable: list[CorrectableEntry],
    ) -> set[int]:
        """Rewrite fabricated timestamps with interpolated real ones.

        Interpolation: distributes N timestamps evenly between task_start
        and now(), preserving phase ordering.

        Returns:
            Set of entry indices that were actually corrected.
        """
        from datetime import datetime, timezone

        corrected_indices: set[int] = set()

        # Determine time window
        now = self._time_provider.now_utc()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if context.task_start_time:
            try:
                start = datetime.fromisoformat(context.task_start_time)
            except (ValueError, TypeError):
                start = now
        else:
            start = now

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        # Calculate interpolated timestamps
        n = len(correctable)
        if n == 1:
            # Single entry: place at midpoint
            delta = (now - start) / 2
            interpolated = [start + delta]
        else:
            # Multiple entries: distribute evenly
            step = (now - start) / (n + 1)
            interpolated = [start + step * (i + 1) for i in range(n)]

        # Read raw JSON
        try:
            log_path = Path(context.execution_log_path)
            raw_data = json.loads(log_path.read_text())
        except Exception:
            return corrected_indices

        raw_events = raw_data.get("events", [])

        # Replace timestamps in raw event strings
        for entry, new_ts in zip(correctable, interpolated, strict=False):
            if entry.index < len(raw_events):
                old_event_str = raw_events[entry.index]
                if (
                    isinstance(old_event_str, str)
                    and entry.original_timestamp in old_event_str
                ):
                    new_ts_str = new_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
                    raw_events[entry.index] = old_event_str.replace(
                        entry.original_timestamp, new_ts_str
                    )
                    corrected_indices.add(entry.index)

                    # Log correction audit event
                    self._audit_writer.log_event(
                        AuditEvent(
                            event_type="LOG_INTEGRITY_CORRECTED",
                            timestamp=self._time_provider.now_utc().isoformat(),
                            feature_name=context.project_id,
                            step_id=context.step_id,
                            data={
                                "phase": entry.phase_name,
                                "original_timestamp": entry.original_timestamp,
                                "corrected_timestamp": new_ts_str,
                                "reason": entry.reason,
                            },
                        )
                    )

        # Write corrected JSON back
        try:
            raw_data["events"] = raw_events
            log_path.write_text(json.dumps(raw_data, indent=2))
        except Exception:
            pass  # Correction is best-effort

        return corrected_indices

    def _check_and_log_scope(self, context: SubagentStopContext) -> None:
        """Check scope violations and log warnings."""
        log_path = Path(context.execution_log_path)
        # execution-log.json is in docs/feature/{project}/
        project_root = log_path.parent.parent.parent

        scope_result = self._scope_checker.check_scope(
            project_root=project_root,
            # TODO: Extract allowed patterns from roadmap.json
            allowed_patterns=["**/*"],
        )

        if scope_result.has_violations:
            for file_path in scope_result.out_of_scope_files:
                self._audit_writer.log_event(
                    AuditEvent(
                        event_type="SCOPE_VIOLATION",
                        timestamp=self._time_provider.now_utc().isoformat(),
                        feature_name=context.project_id,
                        step_id=context.step_id,
                        data={
                            "out_of_scope_file": file_path,
                        },
                    )
                )

    @staticmethod
    def _add_execution_stats(
        data: dict[str, object],
        turns_used: int | None,
        tokens_used: int | None,
    ) -> None:
        """Add turns_used and tokens_used to event data dict when present.

        Centralizes the repeated conditional insertion of execution statistics
        into audit event data across _log_passed, _log_failed, and
        _log_commit_verified.

        Args:
            data: Mutable event data dict to enrich in place.
            turns_used: Number of turns used by the subagent, or None.
            tokens_used: Number of tokens used by the subagent, or None.
        """
        if turns_used is not None:
            data["turns_used"] = turns_used
        if tokens_used is not None:
            data["tokens_used"] = tokens_used

    def _log_passed(
        self,
        feature_name: str,
        step_id: str,
        hook_id: str | None = None,
        turns_used: int | None = None,
        tokens_used: int | None = None,
    ) -> None:
        """Log successful validation to the audit trail."""
        data: dict[str, object] = {}
        self._add_execution_stats(data, turns_used, tokens_used)
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_PASSED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=feature_name,
                step_id=step_id,
                hook_id=hook_id,
                data=data,
            )
        )

    def _log_failed(
        self,
        feature_name: str,
        step_id: str,
        error_messages: list[str],
        allowed_despite_failure: bool = False,
        hook_id: str | None = None,
        turns_used: int | None = None,
        tokens_used: int | None = None,
    ) -> None:
        """Log failed validation to the audit trail."""
        data: dict[str, object] = {
            "validation_errors": error_messages,
        }
        if allowed_despite_failure:
            data["allowed_despite_failure"] = True
        self._add_execution_stats(data, turns_used, tokens_used)
        self._audit_writer.log_event(
            AuditEvent(
                event_type="HOOK_SUBAGENT_STOP_FAILED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=feature_name,
                step_id=step_id,
                hook_id=hook_id,
                data=data,
            )
        )

    def _log_commit_verified(
        self,
        context: SubagentStopContext,
        result: CommitVerificationResult,
        hook_id: str | None = None,
    ) -> None:
        """Log successful commit verification to the audit trail."""
        data: dict[str, object] = {
            "commit_hash": result.commit_hash,
            "commit_date": result.commit_date,
            "commit_subject": result.commit_subject,
        }
        self._add_execution_stats(data, context.turns_used, context.tokens_used)
        self._audit_writer.log_event(
            AuditEvent(
                event_type="COMMIT_VERIFIED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.step_id,
                hook_id=hook_id,
                data=data,
            )
        )

    def _log_commit_not_verified(
        self,
        context: SubagentStopContext,
        result: CommitVerificationResult,
        hook_id: str | None = None,
    ) -> None:
        """Log failed commit verification to the audit trail."""
        self._audit_writer.log_event(
            AuditEvent(
                event_type="COMMIT_NOT_VERIFIED",
                timestamp=self._time_provider.now_utc().isoformat(),
                feature_name=context.project_id,
                step_id=context.step_id,
                hook_id=hook_id,
                data={
                    "error_reason": result.error_reason,
                },
            )
        )
