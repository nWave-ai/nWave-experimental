"""Composition root -- fix-floor-auto-close-cross-wave (slice-01).

Drives the wave-active floor auto-close through the REAL production driving
surfaces (Mandate-16, Driving-Port-Only). NO mocks of the service or the store.

  * Terminal/owner gate-OUT return -> the REAL ``SubagentStopService.validate()``
    composed via ``service_factory.create_subagent_stop_service()`` (Layer-3
    composition). Observable = the wave-active floor RECORD read back through the
    REAL ``WaveActiveFilesystemStore.read(cwd)`` (CLEARED <=> NoWaveActive /
    STILL_ARMED <=> WaveActiveRecord) + ``HookDecision.action``.

  * In-wave sub-dispatch (AC-2) -> the REAL shipped ``PreToolUseService`` (the
    production service wired with a real ``DesMarkerParser`` + the real
    ``WaveActiveFilesystemStore`` reading the SAME seeded floor). An in-wave
    sub-dispatch is a PreToolUse event that NEVER reaches the SubagentStop
    gate-OUT, so the floor must be untouched by construction.

The floor is seeded on disk at the tmp repo root; the production reader resolves
it because the composition ``os.chdir``'s into that root for the validate call
(the service reads the floor via ``WaveActiveReader.read(cwd)``), then restores
the cwd.

ACTIVE-RED / live-green split (atdd_pure -- NOT @skip):
  * AC-1 cross-wave-close is ACTIVE-RED: at HEAD ``SubagentStopService`` consumes
    only a read-only ``WaveActiveReader`` and its ``SubagentStopContext`` carries
    NO ``subagent_type`` -- so nothing closes the floor on the owner's terminal
    PASS. The floor is read back STILL_ARMED and the AC-1 Then (expecting CLEARED)
    fires a semantic AssertionError. GREEN requires DELIVER to (a) add a
    ``subagent_type`` field to ``SubagentStopContext``, (b) inject a
    ``WaveActiveWriter`` into the service, (c) chain ``clear()`` off the attested
    gate-OUT PASS when ``WAVE_OWNERS[subagent_type] == active_wave``.
  * AC-3 non-terminal-no-close is ALSO active-RED-safe: a non-owner return must
    leave the floor armed; at HEAD nothing closes anyway, so it ALREADY holds (a
    live-green guard that the eventual owner-gating must not regress).
  * AC-2 in-wave-persist + AC-4 gate-OUT-veto-unchanged are live-green regression
    guards: they assert behaviors the current code ALREADY exhibits (an in-wave
    PreToolUse dispatch never touches the floor; a review-verdict veto blocks and
    leaves the floor armed), pinning the invariants the close must not break.

Step bodies delegate here (Mandate-15, no logic in step bodies). The contract the
AT declares -- the ``subagent_type`` field on ``SubagentStopContext`` -- is built
defensively: if the field is absent at HEAD the context is built without it (so
collection does NOT error), the close cannot identify the owner, and AC-1 fails
for the RIGHT reason (the floor stays armed), never on a ``TypeError`` at
construction.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.adapters.drivers.hooks import service_factory
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import (
    NoWaveActive,
    WaveActiveRecord,
    WaveProvenance,
)
from des.ports.driver_ports.pre_tool_use_port import HookDecision, PreToolUseInput
from des.ports.driver_ports.subagent_stop_port import SubagentStopContext
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import (
    NON_OWNER_TYPE,
    OWNER_WAVE,
    FloorOutcome,
    WaveFloorWave,
    WaveOwner,
)


_FEATURE_ID = "probe-floor-auto-close"

# The DISCUSS PO-review verdict record family the gate-OUT consumer row reads.
_DISCUSS_REVIEW_EVENT = "DiscussReviewVerdict"

# slice-02 (dual-aware DEVOPS close): the platform-architect's subagent_type +
# the per-wave review-verdict event each review-gated wave's gate-OUT consumer row
# reads (mirrors design_review_ledger_reader.DESIGN_REVIEW_EVENT /
# devops_review_ledger_reader.DEVOPS_REVIEW_EVENT; the AT seeds an APPROVED record
# so the wave's gate-OUT review-verdict row PASSes and the terminal return reaches
# the floor-close assertion instead of being vetoed on an absent record).
_PLATFORM_ARCHITECT = "nw-platform-architect"
_REVIEW_VERDICT_EVENT_BY_WAVE = {
    "design": "DesignReviewVerdict",
    "devops": "DevopsReviewVerdict",
}

# The closed set of waves whose SubagentStop gate-OUT (Step -1) carries a
# review-verdict stack (mirrors ``subagent_stop_service._REVIEW_GATE_OUT_WAVES``;
# the AT does not import it -- it seeds the PASS preconditions so an owner whose
# wave is review-gated reaches the floor-close assertion instead of being vetoed
# at the gate-OUT). A discuss owner needs BOTH gate-OUT rows to PASS (the
# structural value-bearing delta AND a matching APPROVED PO-review verdict).
_REVIEW_GATED_WAVES = frozenset({"discuss", "design", "devops"})


@pytest.fixture
def floor() -> FloorAutoCloseComposition:
    return FloorAutoCloseComposition()


@dataclass
class FloorAutoCloseComposition:
    """Drives the floor auto-close against ONE seeded floor + one return/dispatch."""

    _root: Path | None = None
    _subagent: str = ""
    _wave: str = ""
    # observed
    _decision: HookDecision | None = None
    _captured: dict[str, object] = field(default_factory=dict)

    # ---- GIVEN: arm the on-disk wave-active floor -------------------------------

    def use_project_root(self, root: Path) -> None:
        self._root = root
        (root / ".nwave" / "des").mkdir(parents=True, exist_ok=True)
        seed_dev_checkout_marker(root)

    def given_active_floor_owned_by(self, owner: WaveOwner) -> None:
        """Arm an ACTIVE (non-entering) wave floor for the owner's wave.

        When the owner's wave is review-gated (discuss / design / devops), the
        SubagentStop gate-OUT (Step -1) runs a review-verdict stack BEFORE the
        terminal return is allowed. Without a PASS precondition that stack would
        VETO the return -- the floor-close assertion would never be reached and
        AC-1 would fail for the WRONG reason (a gate-OUT block, not the un-
        implemented auto-close). So we seed the gate-OUT PASS preconditions here:
        the terminal PASS return then reaches the floor-close Then and AC-1 fails
        ONLY on the floor reading back STILL_ARMED (the right active-RED reason).
        """
        self._subagent = owner.value
        self._wave = OWNER_WAVE[owner.value]
        if self._wave in _REVIEW_GATED_WAVES:
            self._seed_gate_out_pass(self._wave)
        self._arm_floor(self._wave)

    def given_active_floor_for_non_owner_return(self, owner: WaveOwner) -> None:
        """Arm an active floor for ``owner``'s wave; the RETURN is a non-owner."""
        self._wave = OWNER_WAVE[owner.value]
        self._subagent = NON_OWNER_TYPE
        self._arm_floor(self._wave)

    # ---- slice-02 (dual-aware DEVOPS close) -------------------------------------

    def given_platform_architect_floor(self, floor_wave: WaveFloorWave) -> None:
        """Arm a ``design`` OR ``devops`` floor; the RETURN is the platform-architect.

        The platform-architect owns BOTH waves (dual ownership). The floor's wave
        is decoupled from the owner identity here: AC-5 arms ``devops`` (the gap),
        AC-6 arms ``design`` (the slice-01 superset, live-green). Both waves are
        review-gated, so the per-wave review-verdict gate-OUT row is seeded to PASS
        (an APPROVED record sealing the value-bearing delta) -- the terminal return
        then reaches the floor-close assertion instead of being vetoed on an absent
        review record (the wrong-reason failure).
        """
        self._subagent = _PLATFORM_ARCHITECT
        self._wave = floor_wave.value
        self._seed_gate_out_pass(self._wave)
        self._seed_review_verdict_pass(
            _REVIEW_VERDICT_EVENT_BY_WAVE[self._wave], _value_bearing_feature_delta()
        )
        self._arm_floor(self._wave)

    def given_non_owner_under_devops_floor(self) -> None:
        """Arm a ``devops`` floor; the RETURN is a NON-platform-architect agent.

        The dual-aware close must not OVER-close: only the dual-owner
        (platform-architect) closes a ``devops`` floor. A non-owner (a reviewer,
        ABSENT from the dual-ownership set) leaves it armed. The devops gate-OUT
        review-verdict row is seeded to PASS so the non-owner return is ALLOWED and
        the floor-stays-armed outcome is attributable to the OWNER-gating (the real
        invariant), never to an unrelated review veto.
        """
        self._subagent = NON_OWNER_TYPE
        self._wave = WaveFloorWave.DEVOPS.value
        self._seed_gate_out_pass(self._wave)
        self._seed_review_verdict_pass(
            _REVIEW_VERDICT_EVENT_BY_WAVE[self._wave], _value_bearing_feature_delta()
        )
        self._arm_floor(self._wave)

    def _arm_floor(self, wave: str) -> None:
        assert self._root is not None
        WaveActiveFilesystemStore().arm(
            self._root,
            WaveActiveRecord(
                wave=wave,
                provenance=WaveProvenance.COMMAND,
                entry_pending=False,  # non-entering: an in-wave / terminal return
            ),
        )

    def _seed_gate_out_pass(self, wave: str) -> None:
        """Seed the gate-OUT PASS preconditions so a review-gated owner's terminal
        return is ALLOWED (the PASS path the auto-close chains off).

        Writes a value-bearing feature-delta (the structural
        ``validate-feature-delta`` row PASSes) AND -- for a discuss owner whose
        gate-OUT stack also carries the PO-review consumer row -- an APPROVED
        ``DiscussReviewVerdict`` ledger record whose ``feature_delta_hash`` seals
        the EXACT delta content (the artefact-currency seal the
        ``DiscussReviewGate`` checks). With both rows PASSing the gate-OUT returns
        "no objection" and the return reaches ``then_floor_is_cleared``.
        """
        assert self._root is not None
        content = _value_bearing_feature_delta()
        delta = self._root / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
        delta.parent.mkdir(parents=True, exist_ok=True)
        delta.write_text(content, encoding="utf-8")
        if wave == "discuss":
            self._seed_review_verdict_pass(_DISCUSS_REVIEW_EVENT, content)

    def _seed_review_verdict_pass(self, event: str, content: str) -> None:
        """Append an APPROVED review-verdict record (``event``) sealing ``content``.

        The wave-neutral seeder: DISCUSS PO-review (``DiscussReviewVerdict``) and
        the slice-02 DESIGN / DEVOPS review-verdict (``DesignReviewVerdict`` /
        ``DevopsReviewVerdict``) share the SAME ledger shape + path SSOT
        (``.nwave/telemetry/atdd-pure/{feature}.jsonl``) and the SAME
        artefact-currency seal (``feature_delta_hash`` over the EXACT delta
        content). The APPROVED + artefact-current verdict makes the per-wave gate's
        pure core return PASS (no objection), so the gate-OUT review row does not
        veto and the floor-close assertion is reached.
        """
        assert self._root is not None
        delta_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ledger = (
            self._root / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
        )
        ledger.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event": event,
            "schema_version": "1.0.0",
            "feature_id": _FEATURE_ID,
            "verdict": "approved",
            "reviewer_agent_id": "probe-reviewer",
            "feature_delta_hash": delta_hash,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    def _seed_design_veto(self) -> None:
        """Seed a DESIGN floor with NO design-review record -> gate-OUT VETOES.

        The real design gate-OUT review-verdict row reads the latest
        ``DesignReviewVerdict`` off the ledger; an absent record -> the pure
        ``ReviewVerdictGate`` returns INDETERMINATE('absent') -> a named-LOUD veto
        (no-silent-pass). The feature-delta is sealed so the gate-OUT can compute
        the artefact-currency hash.
        """
        assert self._root is not None
        delta = self._root / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
        delta.parent.mkdir(parents=True, exist_ok=True)
        # A value-bearing slice plan so the STRUCTURAL gate-OUT row passes and the
        # composition halts on the REVIEW-VERDICT row (the veto AC-4 asserts).
        delta.write_text(_value_bearing_feature_delta(), encoding="utf-8")
        _ = hashlib.sha256  # artefact-currency is computed inside the gate

    # ---- WHEN: drive the REAL service / the REAL PreToolUse ---------------------

    def when_owner_returns_through_gate_out(self) -> None:
        """Drive the REAL SubagentStopService over a terminal/owner gate-OUT return."""
        self._decision = self._run_subagent_stop()

    def when_non_owner_returns_through_gate_out(self) -> None:
        """Drive the REAL SubagentStopService over a NON-owner attested return."""
        self._decision = self._run_subagent_stop()

    def when_in_wave_sub_dispatch_is_evaluated(self) -> None:
        """Drive the REAL PreToolUseService over an in-wave sub-dispatch.

        An in-wave sub-dispatch is a PreToolUse event (NOT a SubagentStop
        gate-OUT return): it carries the matching DES-WAVE marker, the floor is
        already armed for that wave, and it is NOT entering the wave. The
        PreToolUse path NEVER calls the SubagentStop close, so the floor stays.
        """
        assert self._root is not None
        service = PreToolUseService(
            marker_parser=DesMarkerParser(),
            prompt_validator=_AllowAllValidator(),
            audit_writer=NullAuditLogWriter(),
            time_provider=SystemTimeProvider(),
            wave_active_reader=WaveActiveFilesystemStore(),
        )
        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._root)
            # Mirror the armed root into DES_PROJECT_DIR so `resolve_nwave_root()`
            # (now consulted by `_read_active_wave()`) resolves the SAME root the
            # floor was seeded at, not the per-test isolation root the autouse
            # `_isolate_nwave_root` fixture set (tests/conftest.py).
            os.environ["DES_PROJECT_DIR"] = str(self._root)
            self._decision = service.validate(
                PreToolUseInput(
                    prompt=f"<!-- DES-WAVE: {self._wave} -->\nin-wave sub-dispatch",
                    subagent_type=self._subagent,
                    wave_entering=False,
                )
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env

    def when_owner_returns_with_review_veto(self) -> None:
        """Drive the REAL service over a DESIGN owner return that the gate-OUT VETOES."""
        self._seed_design_veto()
        self._decision = self._run_subagent_stop()

    def _run_subagent_stop(self) -> HookDecision:
        """Run the production-wired SubagentStopService over a wave-only return.

        A wave-only / terminal return is execution-log-free (``execution_log_path``
        == "" AND ``step_id`` == ""): the service runs the attested gate-OUT then
        allows. The ``subagent_type`` -- the owner identity the close gates on --
        is threaded into the context IF the field exists (the contract this AT
        declares); at HEAD the field is absent so the context is built without it
        and nothing can identify the owner (AC-1 fails for the right reason).
        """
        assert self._root is not None
        service = service_factory.create_subagent_stop_service()
        context = _build_subagent_stop_context(
            project_id=_FEATURE_ID,
            cwd=str(self._root),
            subagent_type=self._subagent,
        )
        prev_cwd = Path.cwd()
        prev_env = os.environ.get("DES_PROJECT_DIR")
        try:
            os.chdir(self._root)
            # Mirror the armed root into DES_PROJECT_DIR (see
            # when_in_wave_sub_dispatch_is_evaluated above for the rationale).
            os.environ["DES_PROJECT_DIR"] = str(self._root)
            return service.validate(context)
        finally:
            os.chdir(prev_cwd)
            if prev_env is None:
                os.environ.pop("DES_PROJECT_DIR", None)
            else:
                os.environ["DES_PROJECT_DIR"] = prev_env

    # ---- THEN: observable-surface readers (the Universe = floor record state) ---

    def _floor_outcome(self) -> FloorOutcome:
        assert self._root is not None
        record = WaveActiveFilesystemStore().read(self._root)
        if isinstance(record, NoWaveActive):
            return FloorOutcome.CLEARED
        if isinstance(record, WaveActiveRecord):
            return FloorOutcome.STILL_ARMED
        # An Indeterminate (corrupt floor) is neither a clean close nor a clean
        # persist -- surface it so the Then fires a semantic AssertionError.
        return FloorOutcome.STILL_ARMED

    def then_floor_is_cleared(self) -> None:
        assert self._floor_outcome() is FloorOutcome.CLEARED, (
            "the wave-active floor MUST be CLEARED (NoWaveActive) after the wave "
            "OWNER returns through the attested gate-OUT with PASS -- the "
            "cross-wave auto-close. At HEAD the SubagentStopService consumes only "
            "a read-only WaveActiveReader and its SubagentStopContext carries no "
            "subagent_type, so nothing closes the floor on the terminal PASS; the "
            f"floor is read back STILL_ARMED. {self._observed()}"
        )

    def then_floor_stays_armed(self) -> None:
        assert self._floor_outcome() is FloorOutcome.STILL_ARMED, (
            "the wave-active floor MUST STAY ARMED (a WaveActiveRecord is still "
            "present) -- in-wave persistence / non-terminal return preserved; only "
            "the wave OWNER's terminal gate-OUT PASS may close it. "
            f"{self._observed()}"
        )

    def then_return_is_allowed(self) -> None:
        assert self._decision is not None and self._decision.action == "allow", (
            "the attested gate-OUT must ALLOW this return (the PASS path the "
            f"auto-close chains off). {self._observed()}"
        )

    def then_return_is_blocked(self) -> None:
        assert self._decision is not None and self._decision.action == "block", (
            "the gate-OUT review-verdict VETO must BLOCK the return (the existing "
            f"BLOCK behavior is unchanged -- no close on a non-PASS gate-OUT). "
            f"{self._observed()}"
        )

    def _observed(self) -> str:
        action = self._decision.action if self._decision is not None else None
        return (
            f"decision.action={action!r}; subagent={self._subagent!r}; "
            f"wave={self._wave!r}; floor_now={self._read_repr()!r}; "
            f"root={self._root!r}"
        )

    def _read_repr(self) -> str:
        assert self._root is not None
        return repr(WaveActiveFilesystemStore().read(self._root))


# --- module helpers (Mandate-15: no logic in step bodies) --------------------


class _AllowAllValidator:
    """A trivial classic prompt validator for the in-wave PreToolUse path.

    The in-wave AT-3 branch returns before Step 5 (the validator), so this stub is
    never reached; it allows if it ever were, so it can never MASK the floor
    observable AC-2 asserts.
    """

    def validate_prompt(self, prompt: str):
        from des.ports.driver_ports.validator_port import ValidationResult

        return ValidationResult(errors=[], task_invocation_allowed=True)


def _build_subagent_stop_context(
    *, project_id: str, cwd: str, subagent_type: str
) -> SubagentStopContext:
    """Build a wave-only SubagentStopContext, threading ``subagent_type`` if it exists.

    The owner identity (the field the close gates on) is the contract this AT
    declares. If ``SubagentStopContext`` does not yet carry a ``subagent_type``
    field (HEAD), the context is built WITHOUT it -- so collection never errors --
    and the close cannot identify the owner, making AC-1 fail for the right reason
    (a semantic AssertionError on the STILL_ARMED floor, NOT a TypeError).
    """
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(SubagentStopContext)}
    base = {
        "execution_log_path": "",
        "project_id": project_id,
        "step_id": "",
        "cwd": cwd,
    }
    if "subagent_type" in field_names:
        base["subagent_type"] = subagent_type
    return SubagentStopContext(**base)


def _value_bearing_feature_delta() -> str:
    """A minimal value-bearing feature-delta the DESIGN structural gate-OUT passes."""
    return (
        "# Feature Delta: probe-floor-auto-close\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        "| slice-01 | A user observes the wave floor auto-close on the owner's "
        "terminal return. | pending | | value-bearing |\n"
    )


def _ledger_record(verdict: str, feature_id: str, delta_hash: str) -> dict[str, object]:
    """Build a DesignReviewVerdict ledger record (kept for an explicit-veto variant)."""
    return {
        "event": "DesignReviewVerdict",
        "schema_version": "1.0.0",
        "feature_id": feature_id,
        "verdict": verdict,
        "reviewer_agent_id": "probe-reviewer",
        "feature_delta_hash": delta_hash,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


_ = json  # retained for the explicit-veto ledger variant if DELIVER needs it
