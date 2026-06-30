"""Composition root for wave-gateout slice-05 (un-gameable attestation property).

WHAT slice-05 ASSERTS (the cross-wave un-gameable seal property -- cure #2):
  A per-wave review-verdict ledger record, SEALED against the feature-delta hash, is
  REQUIRED for wave closure under Agent(). The slice asserts TWO un-gameable
  properties over the EXISTING mechanism (ReviewVerdictGate.evaluate + the sealed
  ledger records), not a new family:

    (A) ABSENT review verdict  -> block (the cross-wave property: a return with no
        recorded review can NEVER close the wave, for ANY governed wave). This is
        GREEN-ON-KEYSTONE -- the mechanism is wired; slices 01/02/04 already cover
        absent->block per wave; slice-05 LOCKS it as the cross-wave invariant.

    (B) STALE review verdict   -> block (the SEAL property: a verdict recorded then
        the feature-delta CHANGED -- the seal no longer matches -- degrades LOUD to
        INDETERMINATE("stale-artefact"), NOT silent-allow). This is the un-gameable
        property the slice exists to assert: an operator cannot record an APPROVED
        verdict, then edit the deliverable, and still close the wave on the stale
        approval. GREEN-ON-KEYSTONE -- ReviewVerdictGate.evaluate
        (review_verdict_gate.py:103-104) ALREADY blocks on feature_delta_hash drift.

GREEN-ON-KEYSTONE (NOT active-RED, NOT @skip): both arms PASS on the committed
slice-01 code (2ff1bbab). slice-05 is a regression-lock proving the un-gameable
attestation property holds end-to-end through the REAL hook entry.

DRIVING SURFACE (Mandate-13 driving-port-only -- REUSED from slice-01/02..04):
  * Layer 3 composition -- the REAL ``handle_subagent_stop`` hook entry, driven as a
    subprocess with a WAVE-ONLY orchestration return on stdin (a DES-WAVE marker + a
    DES-PROJECT-ID, no DES-STEP-ID). The hook routes through the production
    composition root into ``SubagentStopService.validate``; the observable is the
    hook decision carried as a ``{"decision":"block"|"allow","reason":...}`` JSON
    body on stdout. No ``des.domain.*`` import at the step boundary -- the hook
    process IS the SUT.
  * Layer 3 subprocess -- the REAL ``des record-<wave>-review`` producer CLI as a
    black-box process (No Fixture Theater: the verdict is written by the REAL CLI,
    sealed against the feature-delta hash at record time, never authored by a
    fixture). The STALE arm records an approved verdict, then MUTATES the
    feature-delta so the recorded seal no longer matches the current artefact.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-05 declares NO net-new seam --
it drives the SAME wave-only reachability seam slice-01 shipped (seam-1), through
the SAME real hook entry, asserting the SAME observable (the gate-out block/allow
decision). It witnesses the seal property over the existing seam.

REUSE (Mandate-12): ``HookResult`` + ``_run_module`` + ``arm_design_floor`` are
REUSED from the slice-01 surface; the producer-CLI subcommand + reviewer map are
REUSED from the slice-02..04 parametric surface. This composition re-derives NO
plumbing; it adds ONLY the cross-wave absent property + the stale-seal mutation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .composition_wave_gateout import HookResult, _run_module
from .domain_types import ReviewState, Wave, WaveClosure
from .floor_fixture import activate_des_governance, arm_design_floor


# The production des dispatcher (single entry) drives the REAL producer CLIs.
_DES_MODULE = "des.cli.__main__"

# The REAL Claude Code hook adapter + the subagent-stop command.
_HOOK_ADAPTER_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_SUBAGENT_STOP_COMMAND = "subagent-stop"

# The synthetic feature under gate, provisioned in the tmp work-tree.
_GATED_FEATURE_ID = "synthetic-orchestrated-attestation-feature"

# The per-wave reviewer whose verdict the producer records (brief / DDD-5). The
# review-verdict gate-out arms for _REVIEW_GATE_OUT_WAVES = {discuss, design, devops}.
_REVIEWER_AGENT_ID: dict[Wave, str] = {
    Wave.DESIGN: "nw-solution-architect-reviewer",
    Wave.DEVOPS: "nw-platform-architect-reviewer",
    Wave.DISCUSS: "nw-product-owner-reviewer",
}

# The per-wave producer CLI subcommand.
_RECORD_CLI: dict[Wave, str] = {
    Wave.DESIGN: "record-design-review",
    Wave.DEVOPS: "record-devops-review",
    Wave.DISCUSS: "record-discuss-review",
}

# A value-bearing DISCUSS slice plan -- the DISCUSS structural gate-out row
# (validate-feature-delta) must PASS before the PO-review-verdict row is reached
# (halt-at-first-veto). Used only when the gated wave is DISCUSS so the seal
# property is asserted at the review-verdict row, not the structural row.
_VALUE_BEARING_DISCUSS_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | the maintainer can trust a closed wave was reviewed under "
    "autonomous orchestration | pending | @walking-skeleton | thinnest "
    "user-observable value vertical |\n"
)


@dataclass
class WaveAttestationComposition:
    """Drives the un-gameable attestation property for slice-05.

    Operates on a tmp work-tree carrying the armed wave floor + the feature-delta the
    verdict seals against + the AT-completion ledger the verdict is recorded into. The
    orchestration return is a wave-only stdin payload fed to the REAL ``subagent-stop``
    hook subcommand. Reuses the slice-01/02..04 subprocess primitives (Mandate-12).
    """

    repo_dir: Path
    wave: Wave = field(default=Wave.DESIGN)
    feature_id: str = field(default=_GATED_FEATURE_ID)
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

    # ---- given: select the gated wave ----------------------------------------

    def given_wave(self, wave: Wave) -> None:
        """Select the governed wave whose attestation seal the return is gated on."""
        self.wave = wave

    # ---- given: the orchestration return precondition state ------------------

    def given_agent_returning_under_orchestration(self) -> None:
        """Provision the tmp wave feature + arm the wave floor (precondition state).

        Precondition state ONLY (NOT the SUT): a docs/feature/<id>/feature-delta.md the
        verdict seals against, an armed wave floor (the active-wave discriminant the
        gate-out keys on, never self-reported), and a wave-only agent transcript (a
        DES-WAVE marker + a project id, NO execution-log step identifier). No fixture
        authors any verdict here -- the ledger stays empty until a When records one
        through the REAL producer CLI.
        """
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            self._feature_delta_content(seal_token="original"), encoding="utf-8"
        )
        arm_design_floor(self.repo_dir, self.wave.value)
        self._write_wave_only_transcript()

    def _feature_delta_content(self, *, seal_token: str) -> str:
        """The feature-delta bytes the verdict seals against.

        ``seal_token`` perturbs the bytes so the stale arm can MUTATE the artefact
        AFTER recording -- the recorded verdict's seal (over the ``original`` bytes)
        no longer matches the current (``mutated``) bytes. For DISCUSS the delta
        carries a value-bearing slice plan so the seal property is asserted at the
        review-verdict row, not the structural row.
        """
        if self.wave is Wave.DISCUSS:
            return (
                "# Feature Delta: synthetic orchestrated discuss attestation "
                f"({seal_token})\n\n" + _VALUE_BEARING_DISCUSS_PLAN
            )
        return (
            f"# Feature Delta: synthetic orchestrated {self.wave.value} attestation "
            f"({seal_token})\n\n"
            f"## Wave: {self.wave.value.upper()}\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            f"| n/a | a synthetic {self.wave.value} deliverable the gate seals "
            "against | n/a | the bytes the review verdict's content seal binds to |\n"
        )

    def _write_wave_only_transcript(self) -> None:
        """Write a wave-only agent transcript: DES-WAVE + DES-PROJECT-ID, no step-id."""
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
        """Record the wave's review verdict via the REAL producer CLI (or not / stale).

        NONE     -- leave the ledger empty (the un-reviewed deliverable -> absent).
        APPROVED -- record an approved verdict sealed against the CURRENT feature-delta.
        STALE    -- record an approved verdict against the current feature-delta, THEN
                    MUTATE the feature-delta so the recorded seal no longer matches the
                    current artefact (the un-gameable seal property). No fixture writes
                    the verdict -- it is the REAL CLI's; only the artefact bytes change
                    after the fact, exactly as an operator editing the deliverable
                    post-approval would.
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
        if state is ReviewState.STALE:
            # The deliverable is edited AFTER the approval was sealed: the recorded
            # verdict's feature_delta_hash now refers to bytes that no longer exist.
            # The gate-out re-reads the CURRENT feature-delta -> hash drift ->
            # ReviewVerdictGate.evaluate -> INDETERMINATE("stale-artefact") -> veto.
            self._feature_delta_path.write_text(
                self._feature_delta_content(seal_token="mutated-after-approval"),
                encoding="utf-8",
            )

    # ---- when: the orchestration return is evaluated at the wave boundary ----

    def when_orchestration_return_evaluated(self) -> None:
        """Drive the REAL subagent-stop hook with the wave-only return on stdin."""
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

    def then_wave_closure_refused_absent(self) -> None:
        """A return with NO recorded review is REFUSED, naming the absent verdict.

        The cross-wave un-gameable property (A): for ANY governed wave, a return with
        no recorded review can never close the wave. Absence reads as a refusal --
        degrade-LOUD, never a silent pass. The block reason NAMES the missing-review
        seam: ``absent`` is the wave-agnostic INDETERMINATE detail every wave's
        gate-out projects (design/devops emit ``..._REVIEW_INDETERMINATE: ... absent``;
        discuss emits ``DISCUSS_PO_REVIEW_indeterminate: absent``) -- the un-gameable
        cross-wave token, never a per-wave-specific phrasing.
        """
        self._assert_closure(WaveClosure.REFUSED, reason_must_name=("absent",))

    def then_wave_closure_refused_stale(self) -> None:
        """A return whose recorded approval is STALE is REFUSED (the seal property).

        The un-gameable seal property (B): an APPROVED verdict whose sealed
        feature-delta hash no longer matches the current artefact (the deliverable was
        edited after approval) degrades LOUD to INDETERMINATE("stale-artefact") -> the
        gate-out vetoes. The operator cannot game closure by approving then editing.
        The block reason NAMES the stale-artefact seam -- never a silent allow on a
        stale seal.
        """
        self._assert_review_recorded_cleanly()
        self._assert_closure(
            WaveClosure.REFUSED, reason_must_name=("review", "stale-artefact")
        )

    def then_wave_closure_allowed(self) -> None:
        """A return with an artefact-CURRENT approved review is ALLOWED.

        The discriminating anchor: only a CURRENT sealed approved verdict closes the
        wave (so the refusals above are not unconditional). The verdict was recorded
        through the REAL producer CLI and the feature-delta was NOT mutated, so the
        seal is current -> ReviewVerdictGate.evaluate -> PASS -> allow.
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
            f"the wave-only {self.wave.value.upper()} return must reach "
            "SubagentStopService.validate so the un-gameable attestation gate-out "
            f"projects the wave closure as {expected.value!r} onto the hook's stdout "
            'decision body (REFUSED -> {"decision":"block"}, ALLOWED -> no block '
            "body). The un-gameable attestation (sealed review-verdict ledger record) "
            "is the EXISTING mechanism (ReviewVerdictGate.evaluate); this regression-"
            f"lock must be GREEN on the committed code. Observed closure "
            f"{result.closure.value!r} (decision={result.decision!r}). {self._observed()}"
        )
        if reason_must_name:
            reason = result.block_reason.lower()
            missing = [
                token for token in reason_must_name if token.lower() not in reason
            ]
            assert not missing, (
                "the refusal must NAME the attestation seam reason (degrade-LOUD, "
                f"never a silent pass). The hook's block reason must contain "
                f"{list(reason_must_name)!r}; it is missing {missing!r}. "
                f"observed_reason={result.block_reason[:300]!r}. {self._observed()}"
            )

    def _assert_review_recorded_cleanly(self) -> None:
        record = self._record_result
        assert record is not None, (
            f"this arm must record an approved review via the REAL `des "
            f"{_RECORD_CLI[self.wave]}` producer CLI (When) before asserting closure"
        )
        assert record.exit_code == 0, (
            f"the `des {_RECORD_CLI[self.wave]}` producer CLI must record the approved "
            "verdict cleanly (exit 0) so the gate-out has a verdict to seal-check -- "
            f"the producer exited {record.exit_code}. record_stderr={record.stderr[:200]!r}"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        hook = self._hook_result
        return (
            f"wave={self.wave.value}; review_state={self._review_state.value}; "
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
