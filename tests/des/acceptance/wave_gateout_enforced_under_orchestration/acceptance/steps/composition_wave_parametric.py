"""Composition root for wave-gateout slices 02/03/04 (wave-parametric regression-locks).

GREEN-ON-KEYSTONE COMPLETENESS COVERAGE (NOT active-RED scaffolds, NOT @skip):
  The keystone slice-01 (commit 2ff1bbab) delivered the FULL wave-parametric
  reachability route -- not just the DESIGN gate-out. ``_resolve_des_context``
  accepts any ``declared_wave in WAVE_VOCABULARY``; the gate-out arms for
  ``_REVIEW_GATE_OUT_WAVES = {discuss, design, devops}`` (subagent_stop_service.py:52);
  the per-wave review readers are wired (service_factory.py:131-134). So a DEVOPS or
  DISCUSS wave-only return ALREADY reaches its gate-out on the current committed code.

  These slices are REGRESSION-LOCKS: they PASS on the current code and prove the
  single keystone route covers all FOUR RCA blast-radius gate-outs
  (verify-design-review / verify-devops-review / DISCUSS-structural
  validate-feature-delta / verify-discuss-review). They are GREEN today by
  construction -- the cure is already shipped.

DRIVING SURFACE (Mandate-13 driving-port-only -- identical to slice-01, REUSED):
  * Layer 3 composition -- the REAL ``handle_subagent_stop`` hook entry, driven as a
    subprocess (``python -m des.adapters.drivers.hooks.claude_code_hook_adapter
    subagent-stop``) with a constructed WAVE-ONLY return on stdin (a DES-WAVE marker
    + a DES-PROJECT-ID, NO DES-STEP-ID -- the Agent()-dispatched return shape). The
    hook routes through the production composition root
    (service_factory.create_subagent_stop_service) into SubagentStopService.validate;
    the observable is the hook decision carried as a
    ``{"decision":"block"|"allow", "reason":...}`` JSON body on stdout. No
    des.domain.* import at this composition boundary; no production business-logic
    service imported-and-called at the step boundary -- the hook process IS the SUT.
  * Layer 3 subprocess -- the REAL ``des record-<wave>-review`` producer CLI as a
    black-box process (No Fixture Theater: the verdict is written by the REAL CLI,
    sealed against the feature-delta hash, never authored by a fixture). DEVOPS uses
    ``record-devops-review``; DISCUSS-PO-review uses ``record-discuss-review``.

PER-SLICE GATE-OUT SEAM (the wave-parametric route -- ALREADY shipped by slice-01):
  * slice-02 (DEVOPS): the wave-only DEVOPS return reaches ``_gate_out_review_verdict``
    over ``review_readers["devops"]`` -> ReviewVerdictGate.evaluate. Absent record ->
    INDETERMINATE -> veto reason ``DEVOPS_REVIEW_INDETERMINATE: devops review verdict
    absent``. An approved verdict (REAL ``des record-devops-review``) -> PASS -> allow.
  * slice-03 (DISCUSS structural): the wave-only DISCUSS return reaches the FIRST
    gate-out row ``validate-feature-delta`` -> ``_gate_out_structural`` ->
    DiscussGateOut.evaluate over the feature-delta slice-plan content. A malformed /
    non-value-bearing slice plan -> SLICE_PLAN_REJECTED veto
    (``DISCUSS_GATE_OUT_slice-plan-rejected: ... not value-bearing``). A well-formed
    value-bearing slice plan -> PASS (not blocked on structural grounds).
  * slice-04 (DISCUSS PO-review): the wave-only DISCUSS return reaches the SECOND
    gate-out row ``verify-discuss-review`` -> ``_gate_out_po_review`` ->
    DiscussReviewGate.evaluate. Reached only with a value-bearing slice plan
    (halt-at-first-veto). An absent PO-review verdict -> INDETERMINATE -> veto reason
    ``DISCUSS_PO_REVIEW_indeterminate: absent``. An approved verdict (REAL ``des
    record-discuss-review``) -> PASS -> allow.

REUSE (Mandate-12): the subprocess driving primitives (``HookResult``, ``_run_module``)
and the floor-arming fixture helper are REUSED from the slice-01 surface
(``composition_wave_gateout`` / ``floor_fixture``) -- this composition root re-derives
NO plumbing; it only parametrizes the wave + the DISCUSS gate-out row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .composition_wave_gateout import HookResult, _run_module
from .domain_types import DiscussGateRow, ReviewState, Wave, WaveClosure
from .floor_fixture import activate_des_governance, arm_design_floor


# The production des dispatcher (single entry) drives the REAL producer CLIs.
_DES_MODULE = "des.cli.__main__"

# The REAL Claude Code hook adapter + the subagent-stop command (the SubagentStop
# hook is a hook-adapter entry point, NOT a `des` dispatcher subcommand).
_HOOK_ADAPTER_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_SUBAGENT_STOP_COMMAND = "subagent-stop"

# The synthetic feature under gate, provisioned in the tmp work-tree.
_GATED_FEATURE_ID = "synthetic-orchestrated-wave-feature"

# The per-wave reviewer whose verdict the producer records (brief / DDD-5).
_REVIEWER_AGENT_ID: dict[Wave, str] = {
    Wave.DEVOPS: "nw-platform-architect-reviewer",
    Wave.DISCUSS: "nw-product-owner-reviewer",
}

# The per-wave producer CLI subcommand (REUSE: same arg shape as record-design-review).
_RECORD_CLI: dict[Wave, str] = {
    Wave.DEVOPS: "record-devops-review",
    Wave.DISCUSS: "record-discuss-review",
}

# A value-bearing DISCUSS slice plan (passes DiscussGateOut structural MECC: a
# five-column `## Wave: DISCUSS / [REF] Slice Plan` table with >=1 non-@infrastructure
# row). Used by the structural-PASS arm (slice-03) and EVERY DISCUSS-PO arm (slice-04
# reaches the PO-review row only after the structural row passes -- halt-at-first-veto).
_VALUE_BEARING_SLICE_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | the maintainer can trust a closed wave was reviewed under "
    "autonomous orchestration | pending | @walking-skeleton | thinnest "
    "user-observable value vertical |\n"
)

# A non-value-bearing DISCUSS slice plan (ALL data rows are @infrastructure): the
# cohesion-MECC floor rejects it -> DiscussGateOut SLICE_PLAN_REJECTED (slice-03 veto
# arm). Structurally well-formed five columns, but no row carries user-visible value.
_INFRA_ONLY_SLICE_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | rewire the internal plumbing | pending | @infrastructure | "
    "pure internal mechanics, no user-observable value |\n"
)


@dataclass
class WaveParametricGateoutComposition:
    """Drives the wave-parametric gate-out route for slices 02/03/04.

    Operates on a tmp work-tree carrying the armed wave floor + the feature-delta the
    verdict seals against (and, for DISCUSS, the slice-plan section the structural row
    evaluates) + the AT-completion ledger the verdict is recorded into. The
    orchestration return is a wave-only stdin payload fed to the REAL ``subagent-stop``
    hook subcommand. Reuses the slice-01 subprocess primitives (Mandate-12).
    """

    repo_dir: Path
    wave: Wave = field(default=Wave.DEVOPS)
    feature_id: str = field(default=_GATED_FEATURE_ID)
    _discuss_row: DiscussGateRow | None = field(default=None)
    _value_bearing: bool = field(default=True)
    _review_state: ReviewState = field(default=ReviewState.NONE)
    _record_result: HookResult | None = field(default=None)
    _hook_result: HookResult | None = field(default=None)

    def __post_init__(self) -> None:
        # ADR-AG-001 precondition: opt the synthetic project into DES governance
        # so the hook DISPATCHES into the production handler instead of the
        # activation gate silencing it (exit 0) before the wave gate-out runs.
        activate_des_governance(self.repo_dir)

    # ---- paths --------------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    @property
    def _transcript_path(self) -> Path:
        return self.repo_dir / ".nwave" / "_at" / "wave_only_transcript.json"

    # ---- given: select the wave + the DISCUSS gate-out row -------------------

    def given_wave(self, wave: Wave) -> None:
        """Select the governed wave whose gate-out veto the return must reach."""
        self.wave = wave

    def given_discuss_gate_row(self, row: DiscussGateRow) -> None:
        """Select which DISCUSS gate-out row the scenario targets (DISCUSS only)."""
        self.wave = Wave.DISCUSS
        self._discuss_row = row

    def given_slice_plan_value_bearing(self, value_bearing: bool) -> None:
        """Choose the DISCUSS slice-plan shape (value-bearing vs infra-only)."""
        self._value_bearing = value_bearing

    # ---- given: the orchestration return precondition state ------------------

    def given_agent_returning_under_orchestration(self) -> None:
        """Provision the tmp wave feature + arm the wave floor (precondition state).

        Precondition state ONLY (NOT the SUT): a docs/feature/<id>/feature-delta.md the
        verdict seals against (carrying a value-bearing OR infra-only DISCUSS slice plan
        per the selected shape, for the DISCUSS structural row), an armed wave floor
        (the active-wave discriminant the gate-out keys on, never self-reported), and a
        wave-only agent transcript (a DES-WAVE marker + a project id, NO execution-log
        step identifier -- the Agent()-dispatched return shape). No fixture authors any
        verdict here -- the ledger stays empty until a When records one through the REAL
        producer CLI.
        """
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            self._feature_delta_content(), encoding="utf-8"
        )
        # Arm the wave floor through the REAL WaveActiveFilesystemStore adapter (the
        # domain VO is constructed in the fixture helper, OUTSIDE this composition root
        # -- Mandate-13 import boundary). REUSE: ``arm_design_floor`` is wave-parametric
        # (it takes the wave name); only the literal "design" -> the selected wave.
        arm_design_floor(self.repo_dir, self.wave.value)
        self._write_wave_only_transcript()

    def _feature_delta_content(self) -> str:
        """The feature-delta bytes the verdict seals against (+ DISCUSS slice plan).

        DEVOPS: a minimal section is sufficient (the DEVOPS gate-out is review-verdict
        only -- it reads the bytes solely to seal the verdict hash, never structurally
        validating the headings). DISCUSS: the structural row
        (``DiscussGateOut.evaluate`` -> ``validate_feature_delta``) parses EVERY
        ``## Wave: <NAME>`` heading against the D2 schema (``<NAME> / [REF|WHY|HOW]
        <Section>``), so the DISCUSS delta must carry ONLY schema-compliant wave
        headings -- a bare ``## Wave: DISCUSS`` is itself a structural reject
        (malformed-wave-heading). It therefore contains exactly the schema-compliant
        ``## Wave: DISCUSS / [REF] Slice Plan`` section -- value-bearing -> structural
        PASS, infra-only -> SLICE_PLAN_REJECTED.
        """
        if self.wave is Wave.DISCUSS:
            plan = (
                _VALUE_BEARING_SLICE_PLAN
                if self._value_bearing
                else _INFRA_ONLY_SLICE_PLAN
            )
            return (
                "# Feature Delta: synthetic orchestrated discuss feature fixture\n\n"
                + plan
            )
        return (
            f"# Feature Delta: synthetic orchestrated {self.wave.value} feature "
            "fixture\n\n"
            f"## Wave: {self.wave.value.upper()}\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            f"| n/a | a synthetic {self.wave.value} deliverable the gate seals "
            "against | n/a | the bytes the review verdict's content seal binds to |\n"
        )

    def _write_wave_only_transcript(self) -> None:
        """Write a wave-only agent transcript: DES-WAVE + DES-PROJECT-ID, no step-id.

        The marker subset an Agent()-dispatched wave-agent return carries: the
        validation marker + a DES-WAVE marker (the selected wave) + a project id + the
        project root, but deliberately NO DES-STEP-ID and NO atdd_pure markers -- the
        exact shape the slice-01 keystone route resolves to ``_WaveOnlyResolvedContext``.
        """
        markers = (
            "<!-- DES-VALIDATION : required -->\n"
            f"<!-- DES-WAVE : {self.wave.value} -->\n"
            f"<!-- DES-PROJECT-ID : {self.feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self.repo_dir} -->\n"
        )
        transcript_line = json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "content": markers}}
        )
        self._transcript_path.parent.mkdir(parents=True, exist_ok=True)
        self._transcript_path.write_text(transcript_line + "\n", encoding="utf-8")

    def given_review_recorded(self, state: ReviewState) -> None:
        """Record the wave's review verdict via the REAL producer CLI, or not.

        ``ReviewState.NONE`` leaves the ledger empty (the un-reviewed deliverable).
        ``ReviewState.APPROVED`` drives the REAL ``des record-<wave>-review`` producer
        CLI (REUSE: same arg shape as record-design-review) to append an approved
        verdict sealed against the feature-delta (No Fixture Theater).
        """
        self._review_state = state
        if state is ReviewState.NONE:
            return
        self._record_result = _run_module(
            _DES_MODULE,
            [
                _RECORD_CLI[self.wave],
                "--feature-id",
                self.feature_id,
                "--verdict",
                "approved",
                "--reviewer-agent-id",
                _REVIEWER_AGENT_ID[self.wave],
                "--repo-root",
                str(self.repo_dir),
            ],
            cwd=self.repo_dir,
        )

    # ---- when: the orchestration return is evaluated at the wave boundary ----

    def when_orchestration_return_evaluated(self) -> None:
        """Drive the REAL subagent-stop hook with the wave-only return on stdin.

        Feeds the Claude Code hook protocol payload (an Agent() return: agent transcript
        path + cwd, no direct DES execution-log fields) to the REAL ``subagent-stop``
        hook subcommand, which routes through the production composition root into
        SubagentStopService.validate. REUSE: ``_run_module`` from the slice-01 surface.
        """
        hook_input = {
            "agent_type": f"nw-{self.wave.value}-agent",
            "agent_id": f"at-orchestrated-{self.wave.value}",
            "agent_transcript_path": str(self._transcript_path),
            "cwd": str(self.repo_dir),
        }
        self._hook_result = _run_module(
            _HOOK_ADAPTER_MODULE,
            [_SUBAGENT_STOP_COMMAND],
            cwd=self.repo_dir,
            stdin=json.dumps(hook_input),
        )

    # ---- then: the projected wave-closure decision ---------------------------

    def then_wave_closure_refused_naming(self, *reason_tokens: str) -> None:
        """The orchestration return is REFUSED, the block reason NAMING the seam.

        The wave-parametric route reaches the wave's gate-out so the veto fires (the
        keystone route already covers this wave). The observable is the hook's stdout
        ``{"decision":"block"}`` body AND its ``reason`` text, which must NAME the
        gate-out seam (degrade-LOUD, never a silent pass).
        """
        self._assert_closure(WaveClosure.REFUSED, reason_must_name=reason_tokens)

    def then_wave_closure_not_blocked_structurally(self) -> None:
        """The DISCUSS structural row does NOT block (value-bearing slice plan).

        slice-03 well-formed arm: a value-bearing slice plan passes the structural
        ``validate-feature-delta`` row. With NO PO-review recorded the PO-review row
        (slice-04's concern) WOULD veto downstream -- so the discriminating observable
        for the structural arm is that the block, if any, is NOT the structural
        SLICE_PLAN_REJECTED veto. The structural row passed.
        """
        self._assert_not_structural_block()

    def then_wave_closure_allowed(self) -> None:
        """The orchestration return is ALLOWED (an approved review was recorded).

        The wave-parametric route reaches the gate-out and the review-verdict veto
        finds "no objection" (an artefact-current approved verdict recorded through the
        REAL producer CLI) -> the hook allows (no block body on stdout). Pins the
        discriminating allow so a regression that blocks unconditionally is caught.
        """
        self._assert_review_recorded_cleanly()
        self._assert_closure(WaveClosure.ALLOWED)

    # ---- assertion helpers ---------------------------------------------------

    def _assert_closure(
        self,
        expected: WaveClosure,
        *,
        reason_must_name: tuple[str, ...] = (),
    ) -> None:
        result = self._hook_result
        assert result is not None, (
            "the orchestration return must be evaluated at the wave boundary (When) "
            "before asserting the wave-closure decision (Then)"
        )
        assert result.closure is expected, (
            f"the wave-only {self.wave.value.upper()} return (a DES-WAVE marker + a "
            "project id, no execution-log step id -- the Agent() orchestration return "
            "shape) must reach SubagentStopService.validate so the gate-out projects "
            f"the wave closure as {expected.value!r} onto the hook's stdout decision "
            'body (REFUSED -> {"decision":"block"}, ALLOWED -> no block body). The '
            "keystone slice-01 route is wave-parametric over "
            "_REVIEW_GATE_OUT_WAVES={discuss,design,devops}, so this regression-lock "
            f"must be GREEN on the current code. Observed closure {result.closure.value!r} "
            f"(decision={result.decision!r}). {self._observed()}"
        )
        if reason_must_name:
            reason = result.block_reason.lower()
            missing = [
                token for token in reason_must_name if token.lower() not in reason
            ]
            assert not missing, (
                "the refusal must NAME the gate-out seam reason (degrade-LOUD, never a "
                f"silent pass). The hook's block reason must contain {list(reason_must_name)!r}; "
                f"it is missing {missing!r}. observed_reason={result.block_reason[:300]!r}. "
                f"{self._observed()}"
            )

    def _assert_not_structural_block(self) -> None:
        result = self._hook_result
        assert result is not None, (
            "the orchestration return must be evaluated at the wave boundary (When) "
            "before asserting the structural row did not block"
        )
        reason = result.block_reason.lower()
        assert (
            "slice-plan-rejected" not in reason and "not value-bearing" not in reason
        ), (
            "the DISCUSS structural row (validate-feature-delta) must PASS for a "
            "value-bearing slice plan -- the wave-only DISCUSS return reaches the "
            "structural gate-out row, and a value-bearing plan is NOT blocked on "
            "structural grounds (DiscussGateOut.evaluate -> PASS). A "
            "SLICE_PLAN_REJECTED reason means the structural row wrongly vetoed a "
            f"value-bearing plan. observed_reason={result.block_reason[:300]!r}. "
            f"{self._observed()}"
        )

    def _assert_review_recorded_cleanly(self) -> None:
        record = self._record_result
        assert record is not None, (
            f"the allow arm must record an approved review via the REAL `des "
            f"{_RECORD_CLI[self.wave]}` producer CLI (When) before asserting the allow"
        )
        assert record.exit_code == 0, (
            f"the `des {_RECORD_CLI[self.wave]}` producer CLI must record the "
            "approved verdict cleanly (exit 0) so the gate-out has an artefact-current "
            f"verdict to read -- the producer exited {record.exit_code}. "
            f"record_stderr={record.stderr[:200]!r}"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        hook = self._hook_result
        return (
            f"wave={self.wave.value}; discuss_row="
            + (self._discuss_row.value if self._discuss_row else "n/a")
            + f"; value_bearing={self._value_bearing}; "
            f"review_state={self._review_state.value}; "
            f"floor_armed={(self.repo_dir / '.nwave' / 'wave-active' / 'active.json').is_file()}; "
            f"feature_delta_exists={self._feature_delta_path.is_file()}; "
            "hook=(decision="
            + (repr(hook.decision) if hook else "n/a")
            + ", stdout="
            + (repr(hook.stdout[:300]) if hook else "n/a")
            + ", stderr="
            + (repr(hook.stderr[:300]) if hook else "n/a")
            + ")"
        )
