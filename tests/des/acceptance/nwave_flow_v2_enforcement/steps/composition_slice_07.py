"""Composition root for the nwave-flow-v2-enforcement slice-07 ATs.

The *only* place the production system is wired for slice-07. Two driving ports,
both composition-root (Mandate-13 driving-port-only, Layer 3 composition):

  * GATE-IN (DISCUSS entry) -- the REAL ``PreToolUseService.validate`` built via
    the production composition root (``service_factory.create_pre_tool_use_service``).
    The service is the SUT; the arranged precondition state is (a) a ``discuss``
    wave-active floor under ``project_root`` (slice-04 anchor, already shipped) and
    (b) the product SSOT shape under ``docs/product/`` (the DISCUSS gate-IN
    precondition the net-new ``ProductSsotReader`` reads). The assertion is on the
    service's ``HookDecision`` (allow vs block + the ``DISCUSS_GATE_IN_*`` reason).

  * GATE-OUT (DISCUSS exit) + SEAM -- the REAL ``SubagentStopService.validate``
    built via the production composition root
    (``service_factory.create_subagent_stop_service``). The service is the SUT;
    the arranged precondition state is the feature-delta artefact under
    ``project_root`` (the net-new ``FeatureDeltaReader`` reads it) plus a
    ``discuss`` wave-active floor (the gate-OUT discriminates a discuss-wave
    return). The seam idempotence AT re-runs the SAME service path on identical
    content and asserts the identical verdict token -- the §21.2.4 re-earnability
    property, driven through the gate-OUT surface (NOT a direct-domain call).

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
it. Step functions are thin delegations (Mandate-12: no business logic in step
bodies).

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate): the net-new
``src/des/domain/discuss_gate.py`` cores, the ``ProductSsotReader`` /
``FeatureDeltaReader`` capability ports + adapters, and their wiring into
``PreToolUseService`` (gate-IN branch) / ``SubagentStopService`` (gate-OUT branch)
do NOT exist at HEAD. So the production factories build the services WITHOUT a
DISCUSS gate-IN / gate-OUT branch:
  * gate-IN: an entering discuss dispatch with unmet SSOT preconditions falls
    through to the slice-04 wave-aware hinge, which ALLOWS a marked / non-bypass
    dispatch -> AT-1 fails with a semantic ``AssertionError`` (ALLOWED where a
    gate-IN DENY was expected).
  * gate-OUT: the atdd_pure return path ALLOWS cleanly (no execution-log demand,
    no gate-OUT branch) -> AT-2 / AT-4 fail with a semantic ``AssertionError``
    (ALLOWED where a gate-OUT BLOCK / INDETERMINATE was expected). AT-3 cannot
    observe a stable ``DISCUSS_GATE_OUT_*`` verdict to compare -> semantic
    ``AssertionError``.
No collection / import error in the test process (only test-local types +
already-shipped production composition are imported). GREEN once DELIVER ships the
cores + capability adapters + the two service branches.

DESIGN-PINNED CONTRACTS this AT-seed conforms to (feature-delta § slice-07 design
-- ONE SSOT shared by the AT-seed and the crafter's readers; no drift):
  * wave-active floor: single JSON object at the FIXED path
    ``{project_root}/.nwave/wave-active/active.json`` (slice-04 floor contract).
  * product SSOT: ``docs/product/{vision,backlog,glossary,jobs}.md`` presence
    under ``project_root`` (the migration-gate + the four SSOT docs, §8 gate-IN).
  * feature-delta: a single Markdown artefact whose ``## Wave: DISCUSS / [REF]
    Slice Plan`` table the reused ``validate_slice_plan_content`` MECC consumes.
The location + shape are NOT the crafter's choice -- they are DESIGN-PINNED; the
crafter's readers CONFORM to these exact paths/shapes, and only the read
mechanics (atomic / encoding) are the crafter's. If a crafter reader resolves a
different location, the gate cannot see the seeded state and the AT fails -- that
is the drift this fixed-path seed catches.

DISCUSS-side reason tokens the loud verdicts must carry (so a generic block
cannot satisfy the named assertion -- K1: a veto is LOUD, not a silent green):
  * gate-IN unmet precondition -> ``DISCUSS_GATE_IN_*`` (one of missing-ssot /
    migration-unmet / indeterminate).
  * gate-OUT slice-plan rejection -> ``DISCUSS_GATE_OUT_SLICE_PLAN_REJECTED``.
  * gate-OUT unreadable delta -> ``DISCUSS_GATE_OUT_INDETERMINATE``.

SUT STATE MACHINE (C2 -- AT module docstring requirement):
  gate-IN states  = {DISCUSS_ENTERING, NO_WAVE}.
    DISCUSS_ENTERING --(SSOT unmet)--> VETO (block, DISCUSS_GATE_IN_*)
    DISCUSS_ENTERING --(SSOT met)----> allow (no objection)
    NO_WAVE          --(bare dispatch)-> allow (S1 non-interference; illegal-event
                                          -from-no-wave: gate-IN does NOT fire)
  gate-OUT states = {DISCUSS_RETURNING}.
    DISCUSS_RETURNING --(slice-plan rejected)--> VETO (block, SLICE_PLAN_REJECTED)
    DISCUSS_RETURNING --(delta unreadable)------> INDETERMINATE (degrade-LOUD block)
    DISCUSS_RETURNING --(value-bearing plan)----> PASS (no objection, NOT a GO)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_07 import (
    GateDecision,
    SlicePlanShape,
    SsotPreconditions,
)


# tests/des/acceptance/nwave_flow_v2_enforcement/steps/composition_slice_07.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# DESIGN-PINNED floor path (slice-04 contract): a single JSON object at this FIXED
# relative path under project_root (one record per project, NOT a directory scan).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# DESIGN-PINNED product-SSOT layout (§8 gate-IN precondition): docs/product/ is the
# migration-gate; the four required SSOT docs live directly under it. The jobs slot
# is satisfied by the STRUCTURED docs/product/jobs.yaml registry (wired into
# validate_ssot_propagation + the discuss/diverge skills) -- NOT jobs.md. Forcing
# jobs to .md is pure churn; vision/backlog/glossary stay .md, only jobs is YAML.
_PRODUCT_DIR_REL = "docs/product"
_SSOT_MD_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md")
_JOBS_DOC = "jobs.yaml"
_REQUIRED_SSOT_DOCS: tuple[str, ...] = (*_SSOT_MD_DOCS, _JOBS_DOC)

# DESIGN-PINNED feature-delta path the gate-OUT FeatureDeltaReader reads. A single
# Markdown artefact under the feature folder; the AT-seed + the crafter reader
# share this one SSOT.
_FEATURE_ID = "nwave-flow-v2-enforcement"
_FEATURE_DELTA_REL = f"docs/feature/{_FEATURE_ID}/feature-delta.md"

# Reason-token discriminants the loud verdicts must carry. A generic block must
# not satisfy a named assertion (K1: a veto is named-LOUD, never silent).
_GATE_IN_TOKENS: tuple[str, ...] = (
    "discuss_gate_in",
    "missing-ssot",
    "migration-unmet",
    "precondition",
    "ssot",
)
_GATE_OUT_REJECT_TOKENS: tuple[str, ...] = (
    "discuss_gate_out",
    "slice-plan-rejected",
    "slice plan",
    "slice_plan",
)
_GATE_OUT_INDETERMINATE_TOKENS: tuple[str, ...] = (
    "indeterminate",
    "degrade",
    "unreadable",
    "cannot be read",
)

# A value-bearing slice-plan table (>=1 user-visible row) -- the MECC floor
# (validate_slice_plan_content) accepts this exact 5-column fixed-order shape.
_VALUE_BEARING_SLICE_PLAN = """\
## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | A user can run the thing and see a confirmation | pending | @walking-skeleton | the thinnest e2e |
| slice-02 | A user gets a clear error when the input is malformed | pending | | the first error path |
"""

# An infrastructure-only slice plan (every row @infrastructure) -- the slice-06
# cohesion-MECC veto (VERDICT_REJECTED_INFRA_ONLY), not value-bearing.
_INFRA_ONLY_SLICE_PLAN = """\
## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | wire the logging adapter | pending | @infrastructure | plumbing only |
| slice-02 | configure the CI matrix | pending | @infrastructure | plumbing only |
"""

# A minimal valid DISCUSS feature-delta wrapper the MECC reads the slice plan out
# of (one ## Wave heading + the slice-plan table).
_FEATURE_DELTA_HEADER = f"# Feature Delta: {_FEATURE_ID}\n\n"

# Keyless DiscussReviewVerdict record contract (oss-review-verdict-demotion S3:
# the review gate is ALWAYS armed; the legal discuss exit needs an APPROVED
# record bound to the current artefact -- present fields only, no hmac_sha256,
# no signing key anywhere). Mirrors the re-authored slice-07b keyless seed.
_LEDGER_REL = f".nwave/telemetry/atdd-pure/{_FEATURE_ID}.jsonl"
_DISCUSS_REVIEW_EVENT = "DiscussReviewVerdict"
_DISCUSS_SCHEMA_VERSION = "1.0.0"
_PO_REVIEWER_AGENT_ID = "nw-product-owner-reviewer"


@dataclass
class DiscussGateComposition:
    """Drives the production DISCUSS gate-IN / gate-OUT seams for the slice-07 ATs."""

    _project_root: Path | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _decision_action_rerun: str | None = field(default=None)
    _decision_reason_rerun: str | None = field(default=None)

    # ---- given (gate-IN) ----------------------------------------------------

    def given_discuss_wave_active_with_preconditions(
        self, tmp_path: Path, preconditions: SsotPreconditions
    ) -> None:
        """Arm a discuss wave and arrange the product-SSOT precondition state.

        The gate-IN scenario's dispatch is the wave-ENTERING one, so the floor
        is armed with the v1.1 anchor-owned ``entry_pending: true`` mark
        (slice-07c F3 structural signal -- the COMMAND arm writes it).
        """
        self._project_root = tmp_path
        self._arm_discuss_floor(tmp_path, entry_pending=True)
        self._seed_product_ssot(tmp_path, preconditions)

    def given_no_wave_active_with_preconditions(
        self, tmp_path: Path, preconditions: SsotPreconditions
    ) -> None:
        """Arrange NoWaveActive (the S1 floor) with the product preconditions state.

        No wave is armed -> the gate-IN must NOT fire (consent-gate, K2) even
        though the product preconditions are deliberately unmet.
        """
        self._project_root = tmp_path
        self._seed_product_ssot(tmp_path, preconditions)
        # No floor file written -> NoWaveActive.

    # ---- given (gate-OUT + seam) --------------------------------------------

    def given_discuss_return_with_slice_plan(
        self, tmp_path: Path, shape: SlicePlanShape
    ) -> None:
        """Arrange a discuss-wave return whose feature-delta has the given shape."""
        self._project_root = tmp_path
        self._arm_discuss_floor(tmp_path)
        self._seed_feature_delta(tmp_path, shape)

    def given_approved_review_recorded(self) -> None:
        """Record a keyless APPROVED product-owner review of the current artefact.

        oss-review-verdict-demotion S3: the DISCUSS review veto-gate is ALWAYS
        armed (the pre-S3 unarmed-gate escape -- no record + no key -> silent
        allow -- is deleted), so the legal discuss exit path requires an
        APPROVED ``DiscussReviewVerdict`` bound to the artefact's current
        bytes. The record carries present fields only (no ``hmac_sha256``); no
        signing key is provisioned anywhere. Must run AFTER the feature-delta
        is seeded (the seal binds the exact bytes).
        """
        import hashlib
        import json

        assert self._project_root is not None, (
            "seed the discuss-wave return (the feature-delta) before recording "
            "the approved review -- the seal binds the artefact's exact bytes"
        )
        root = self._project_root
        delta_hash = hashlib.sha256(
            (root / _FEATURE_DELTA_REL).read_bytes()
        ).hexdigest()
        record: dict[str, object] = {
            "event": _DISCUSS_REVIEW_EVENT,
            "schema_version": _DISCUSS_SCHEMA_VERSION,
            "feature_id": _FEATURE_ID,
            "verdict": "approved",
            "reviewer_agent_id": _PO_REVIEWER_AGENT_ID,
            "feature_delta_hash": delta_hash,
            "timestamp": "2026-06-11T00:00:00+00:00",
        }
        ledger_path = root / _LEDGER_REL
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    # ---- when (gate-IN) -----------------------------------------------------

    def when_wave_entering_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a wave-entering discuss dispatch.

        Layer 3 composition: ``wave_entering=True`` is the structural
        discriminant the production hook adapter computes from the armed
        pending floor via ``WaveActivationService.peek_entry`` (slice-07c F3
        NORMATIVO -- the AD-66 keyword heuristic is deleted; wording is inert).
        """
        self._run_pre_tool_use_gate(
            prompt=self._entering_discuss_prompt(), wave_entering=True
        )

    def when_bare_non_wave_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a bare non-wave dispatch (S1)."""
        self._run_pre_tool_use_gate(prompt="please tidy the helper for readability")

    # ---- when (gate-OUT + seam) ---------------------------------------------

    def when_discuss_return_checked(self) -> None:
        """Drive SubagentStopService.validate with a discuss-wave return."""
        action, reason = self._run_subagent_stop_gate()
        self._decision_action, self._decision_reason = action, reason

    def when_discuss_return_checked_twice(self) -> None:
        """Drive the gate-OUT service path TWICE on the identical artefact (§21.2.4)."""
        first = self._run_subagent_stop_gate()
        second = self._run_subagent_stop_gate()
        self._decision_action, self._decision_reason = first
        self._decision_action_rerun, self._decision_reason_rerun = second

    # ---- then (gate-IN) -----------------------------------------------------

    def then_entry_blocked(self) -> None:
        """The gate-IN BLOCKS the entering discuss dispatch (VETO, §22.0)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the discuss gate-IN must BLOCK an entering dispatch whose product "
            "preconditions (SSOT / migration) are unmet (a VETO, §22.0); it "
            f"returned {self._decision_action!r}. a wired ProductSsotReader + "
            f"DiscussGateIn.evaluate would block it. {self._observed()}"
        )

    def then_block_names_unmet_precondition(self) -> None:
        """The block names the unmet discuss precondition (K1: named-LOUD veto)."""
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _GATE_IN_TOKENS), (
            "the gate-IN block must NAME the unmet discuss precondition (one of "
            f"{_GATE_IN_TOKENS!r}) so it surfaces as a loud, attributable veto -- "
            f"not a generic block; got reason={self._decision_reason!r}. "
            f"{self._observed()}"
        )

    def then_entry_allowed_greenfield_advisory(self) -> None:
        """Greenfield declass (slice-05): docs/product/ absent (MIGRATION_UNMET) is
        an ADVISORY, NOT a veto -- the gate-IN ALLOWS the entry.

        The wave-optionality model declassed the MIGRATION_UNMET veto to a soft
        advisory: DISCUSS is optional, the greenfield product-SSOT is bootstrapped
        through the canonical DISCOVER -> DIVERGE -> DISCUSS order (DIVERGE owns
        the bootstrap), never as a hard DISCUSS precondition. The advisory is
        carried as an exit-0 soft signal INSIDE the gate stack (it does not halt
        the composition), so the gate-IN does NOT return a block -- the observable
        on the driving-port HookDecision is action == "allow". This is the ONLY
        gate-IN case that flips BLOCK->ADVISORY; MISSING_SSOT + INDETERMINATE still
        hard-veto (then_entry_blocked covers those, unchanged).
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the discuss gate-IN must ALLOW an entering dispatch on a greenfield "
            "project (docs/product/ absent -> MIGRATION_UNMET) -- the slice-05 "
            "declass turned the migration-unmet veto into a soft advisory (DIVERGE "
            "owns the greenfield bootstrap; DISCUSS is optional, never hard-blocked "
            "on an un-migrated product model); it returned "
            f"{self._decision_action!r}. {self._observed()}"
        )

    def then_entry_allowed_untouched(self) -> None:
        """S1 non-interference: a bare non-wave dispatch is allowed, untouched (K2)."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "a bare non-wave dispatch must NEVER be blocked by the discuss gate-IN "
            "when no wave is active (K2 consent-gate / zero false-positive); the "
            f"gate returned {self._decision_action!r}. {self._observed()}"
        )
        assert self._decision_reason in (None, ""), (
            "the bare dispatch must be left completely untouched (no block "
            f"reason); got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_entry_allowed_preconditions_satisfied(self) -> None:
        """The gate-IN ALLOWS an entering dispatch whose preconditions ARE satisfied.

        The jobs slot is satisfied by docs/product/jobs.yaml (the structured JOB
        registry), NOT jobs.md. RED-for-right-reason at HEAD: the production
        ProductSsotFilesystemReader's _REQUIRED_DOCS demands "jobs.md", so a
        docs/product/ holding jobs.yaml (and no jobs.md) reads jobs=False ->
        DiscussGateIn.evaluate -> MISSING_SSOT -> the service BLOCKS. This ALLOW
        assertion therefore fires now (gate returns 'block'); it goes GREEN once
        the adapter's jobs slot points at jobs.yaml.
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the discuss gate-IN must ALLOW an entering dispatch whose product "
            "preconditions are satisfied, where the jobs slot is satisfied by the "
            "structured docs/product/jobs.yaml registry (NOT jobs.md -- forcing "
            "jobs to .md is pure churn). PASS = no objection found (§22.0); the "
            f"gate returned {self._decision_action!r}. a ProductSsotReader whose "
            "jobs slot reads jobs.yaml would find no missing SSOT and allow it. "
            f"{self._observed()}"
        )

    # ---- then (gate-OUT) ----------------------------------------------------

    def then_handoff_blocked(self) -> None:
        """The gate-OUT BLOCKS the discuss-wave return (structural VETO)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the discuss gate-OUT must BLOCK a discuss-wave return whose slice "
            "plan is not value-bearing (the MECC structural veto); it returned "
            f"{self._decision_action!r}. a wired FeatureDeltaReader + "
            f"DiscussGateOut.evaluate would block it. {self._observed()}"
        )

    def then_block_names_rejected_slice_plan(self) -> None:
        """The block names the rejected slice plan (K1: named-LOUD veto)."""
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _GATE_OUT_REJECT_TOKENS), (
            "the gate-OUT block must NAME the rejected slice plan (one of "
            f"{_GATE_OUT_REJECT_TOKENS!r}) so it surfaces as a loud, attributable "
            f"veto; got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_handoff_allowed_no_objection(self) -> None:
        """A value-bearing slice plan -> PASS = no objection found (NOT a GO, §22.0)."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the discuss gate-OUT must ALLOW a discuss-wave return whose slice "
            "plan IS value-bearing (PASS = no objection found, NOT a GO -- the GO "
            f"stays human, §22.0); it returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_handoff_blocked_degrade_loud(self) -> None:
        """An unreadable delta -> INDETERMINATE block (degrade-LOUD, §17)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the discuss gate-OUT must BLOCK degrade-LOUD when the feature-delta "
            "is absent / unreadable -- it must NEVER be coerced to a silent PASS "
            f"(§17 no-silent-pass); it returned {self._decision_action!r}. "
            f"{self._observed()}"
        )
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _GATE_OUT_INDETERMINATE_TOKENS), (
            "the degrade-LOUD block must name the INDETERMINATE / unreadable cause "
            f"(one of {_GATE_OUT_INDETERMINATE_TOKENS!r}) so the failure is loud, "
            f"not masked; got reason={self._decision_reason!r}. {self._observed()}"
        )

    # ---- then (seam re-earn) ------------------------------------------------

    def then_both_checks_identical_verdict(self) -> None:
        """§21.2.4 idempotence: re-running the gate-OUT path re-earns the same verdict.

        The verdict is RE-EARNED, never inherited: identical artefact content ->
        identical (action, reason) token across the two runs. This is the seam
        re-runnability property a future DESIGN gate-IN relies on. RED-for-right-
        reason: with no gate-OUT branch the two runs both ALLOW (the verdict the
        future seam emits is absent), so first the BLOCK is missing -- but the
        idempotence assertion itself is the contract this AT pins, and it can only
        be GREEN once the gate-OUT verdict exists and is deterministic.
        """
        assert self._decision_action_rerun is not None, (
            "the gate-OUT must be run twice (When ... twice) before asserting "
            "re-earnability (Then)"
        )
        # The seam must first PRODUCE a gate-OUT verdict (a block on the seeded
        # infra-only plan) -- an ALLOW means the gate-OUT branch is absent, so
        # there is no re-earned verdict to speak of (RED-for-right-reason).
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the §21.2.4 seam can only re-earn a verdict once the gate-OUT "
            "produces one: the seeded infra-only slice plan must yield a BLOCK "
            f"verdict to re-earn; the first run returned {self._decision_action!r} "
            "(the gate-OUT branch / DiscussGateOut.evaluate is not wired). "
            f"{self._observed()}"
        )
        assert (self._decision_action, self._decision_reason) == (
            self._decision_action_rerun,
            self._decision_reason_rerun,
        ), (
            "the §21.2.4 seam must be IDEMPOTENT + RE-RUNNABLE: re-running the "
            "gate-OUT on the IDENTICAL feature-delta content must re-earn the "
            "IDENTICAL verdict token (same content -> same token), so a future "
            "DESIGN gate-IN re-earns the verdict from the sealed artefact rather "
            f"than inheriting it. run-1=({self._decision_action!r}, "
            f"{self._decision_reason!r}); run-2=({self._decision_action_rerun!r}, "
            f"{self._decision_reason_rerun!r})."
        )

    # ---- driving-port invocations -------------------------------------------

    def _run_pre_tool_use_gate(self, prompt: str, wave_entering: bool = False) -> None:
        """Drive the REAL PreToolUseService.validate via the production composition root."""
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._project_root)
            # Mirror the armed root into DES_PROJECT_DIR so `resolve_nwave_root()`
            # (now consulted by `_read_active_wave()`) resolves the SAME root the
            # floor was seeded at, not the per-test isolation root the autouse
            # `_isolate_nwave_root` fixture set (tests/conftest.py).
            os.environ["DES_PROJECT_DIR"] = str(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(prompt=prompt, wave_entering=wave_entering)
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
        self._decision_action = decision.action
        self._decision_reason = decision.reason

    def _run_subagent_stop_gate(self) -> tuple[str, str | None]:
        """Drive the REAL SubagentStopService.validate via the production composition root.

        Runs an atdd_pure discuss-wave return (execution-log-free path). The
        feature-delta + the discuss wave-active floor under project_root are the
        arranged preconditions the gate-OUT branch reads. RED-for-right-reason: the
        production service has no gate-OUT branch at HEAD, so the atdd_pure return
        ALLOWS cleanly where a value/cohesion veto is expected.
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import (
            SubagentStopContext,
            SubagentStopReturnKind,
        )

        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._project_root)
            # Mirror the armed root into DES_PROJECT_DIR (see
            # _run_pre_tool_use_gate above for the rationale).
            os.environ["DES_PROJECT_DIR"] = str(self._project_root)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    project_id=_FEATURE_ID,
                    return_kind=SubagentStopReturnKind.ATDD_PURE,
                    cwd=str(self._project_root),
                    slice_id="slice-07",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env
        return decision.action, decision.reason

    # ---- observable-surface reader ------------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the gate must be run (When) before asserting on its decision (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == "allow"
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _arm_discuss_floor(self, root: Path, *, entry_pending: bool = False) -> None:
        """Seed the wave-active floor with a discuss COMMAND record.

        ``entry_pending=True`` arms the floor v1.1 anchor-owned mark for an
        ENTERING-dispatch scenario (slice-07c); a returning / in-wave scenario
        keeps the key omitted (omitted <=> false per the floor contract).
        """
        import json

        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"wave": "discuss", "provenance": "command"}
        if entry_pending:
            record["entry_pending"] = True
        floor_path.write_text(json.dumps(record), encoding="utf-8")

    def _seed_product_ssot(self, root: Path, preconditions: SsotPreconditions) -> None:
        """Seed (or deliberately omit) the product-SSOT precondition state.

        MET / JOBS_AS_YAML -> docs/product/ with vision+backlog+glossary as .md
          AND the jobs slot satisfied by jobs.yaml (the structured JOB registry,
          NOT jobs.md). These two states are observably identical -- JOBS_AS_YAML
          names the intent explicitly for the jobs-format correctness scenario.
        JOBS_ABSENT -> docs/product/ with vision+backlog+glossary but NO jobs
          doc at all (neither .md nor .yaml) -- the regression that an entirely
          absent jobs slot still vetoes (the gate must not silently pass).
        UNMET -> docs/product/ absent entirely (migration-gate unmet) -- the
          coarsest unmet shape the gate-IN must veto.
        """
        if preconditions in (
            SsotPreconditions.MET,
            SsotPreconditions.JOBS_AS_YAML,
        ):
            self._write_product_docs(root, _REQUIRED_SSOT_DOCS)
        elif preconditions is SsotPreconditions.JOBS_ABSENT:
            self._write_product_docs(root, _SSOT_MD_DOCS)
        # UNMET: write nothing -> docs/product/ absent (migration-unmet).

    @staticmethod
    def _write_product_docs(root: Path, docs: tuple[str, ...]) -> None:
        """Write the named SSOT docs under docs/product/ (substrate plumbing)."""
        product_dir = root / _PRODUCT_DIR_REL
        product_dir.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")

    def _seed_feature_delta(self, root: Path, shape: SlicePlanShape) -> None:
        """Seed (or deliberately omit) the feature-delta artefact the gate-OUT reads."""
        delta_path = root / _FEATURE_DELTA_REL
        if shape is SlicePlanShape.UNREADABLE:
            # Write nothing -> the FeatureDeltaReader returns None -> the pure
            # core decides INDETERMINATE (degrade-LOUD).
            return
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        body = (
            _VALUE_BEARING_SLICE_PLAN
            if shape is SlicePlanShape.VALUE_BEARING
            else _INFRA_ONLY_SLICE_PLAN
        )
        delta_path.write_text(_FEATURE_DELTA_HEADER + body, encoding="utf-8")

    # ---- dispatch shapes ----------------------------------------------------

    def _entering_discuss_prompt(self) -> str:
        """A wave-entering discuss dispatch (carries the discuss-wave DES markers).

        SHAPE only: a marked in-wave dispatch (so the slice-04 S2 markerless-bypass
        branch is NOT what fires) -- the gate-IN precondition veto is the new
        behaviour AT-1 demands. The exact entering-discuss discriminant mechanics
        are crafter-owned (DESIGN slice-07 "Left to crafter").
        """
        return (
            "DES-VALIDATION: required\n"
            "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
            "DES-PROJECT-ROOT: .\n"
            "DES-STEP-ID: discuss-1\n"
            "begin the discuss wave"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision.action={self._decision_action!r}; "
            f"decision.reason={self._decision_reason!r}; "
            f"project_root={self._project_root!r}"
        )
