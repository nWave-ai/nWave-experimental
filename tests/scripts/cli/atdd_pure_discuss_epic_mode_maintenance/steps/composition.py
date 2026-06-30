"""Composition root for the discuss-epic-mode slice-05 maintenance slice.

Slice-05 value: a maintainer opening the epic-delta sees live progress -- feature
rows link ``docs/feature/{id}/`` when picked up and flip ``pending`` -> ``in-flight``
-> ``shipped`` -- and decides the next pickup from the plan, not from memory.

Honest mechanical-vs-prompt boundary (the central slice-05 decision)
====================================================================
The status flip + linkage is PERFORMED by the maintainer following the nw-discuss
skill procedure during a discuss / feature-end session. That act is PROMPT-SURFACE
-- not mechanically testable. Per the DESIGN slice-02/04/05 text contracts section:
the "code" of this slice is SKILL / COMMAND text (the linkage/status-flip
procedure); there is NO ``src/des`` surface; DESIGN pins the LSC contract
(LSC-1..LSC-6) as the AT-citable specification.

What these ATs PIN:
  - LSC-1 pick-up: ``pending`` -> ``in-flight`` AND the Feature cell gains its
    ``docs/feature/{id}/`` link -- one atomic edit. Witnessed against the
    suite-local reference producer (a golden-file analogue of the maintainer's
    flip).
  - Keystone-gate preservation (LSC-1/LSC-2 corollary): the FLIPPED epic-delta
    still clears slice-01's REAL CLI ``des validate-feature-delta
    --require-feature-plan --format=json`` -> ``accepted``. This is the GENUINE
    mechanical seam slice-05 drives -- slice-01's already-shipped surface, reached
    through its real ``main(argv)`` entry. Empirically: the validator does NOT
    validate Status cells (DC-1), so the flip provably preserves validity.
  - LSC-2 finalize: ``in-flight`` -> ``shipped`` (forward-only, LSC-5).
  - LSC-3 fractal JIT: no ``docs/feature/{id}/`` workspace exists for any row still
    ``pending`` (observed on a real tmp_path tree).
  - LSC-6 garbage-token rejection: an off-set Status token (e.g. ``done``) is
    rejected at the LSC PROCEDURE level. The slice-01 validator does NOT reject it
    (DC-1 -- ``done`` validates ``accepted`` through the keystone gate today), so
    this rejection is the slice-05 procedure's responsibility, NOT the gate's.

What stays PROMPT-SURFACE (deliberately NOT an AT):
  - LSC-4 (backlog cites the epic by name). The honest mechanical surface is the
    produced feature-workspace's delta citing the epic id; on the current tip the
    backlog citation is pure prose with no produced artifact to observe at the
    maintenance step, so it is reviewed by Sentinel in the landed backlog/skill
    text. A prose-grep of the backlog for the epic name would be the
    presence-watcher anti-pattern + Fixture Theater.

Active-RED contract (atdd_pure)
===============================
Slice-05 has NO net-new ``src/des`` maintenance seam (DESIGN reuse table: text-only;
the LSC procedure is prose). The active-RED is therefore at the BEHAVIOUR layer,
mirroring slice-02's artifact-absence RED and slice-04's behaviour-absence RED one
level up: the linkage/status-flip procedure is undefined on the current tip (the
procedure is the slice-05 deliverable). The designated GREEN wiring point is
``run_maintenance()``; on the current tip it is a documented NO-OP -- it imports
nothing from the reference oracle -- so NO flip is applied and every LSC observation
reads its absent default (``MAINTENANCE_ABSENT`` / unchanged plan) -> semantic
``AssertionError`` -- a deliberate missing-functionality RED, never a collection /
import error.

S2 driving-port-only: this composition imports ONLY slice-01's already-shipped CLI
(the gate-preservation leg) -- the single mechanical ``src/des`` seam, reached
through its real ``main(argv)`` entry. It imports ZERO ``des.{domain,application,
adapters}`` code. The reference producer is suite-local test-support. S2 = PASS.

S3 dormant-seam reconciliation: slice-05 declares ZERO net-new ``src/des`` seams.
The only seam driven is slice-01's already-shipped CLI; no net-new seam can ship
dormant -- S3 = PASS by construction.

Layer 3 (subprocess/FS acceptance): the driving ports are (a) the reference
producer's flip outcome, (b) the real slice-01 CLI for the gate-preservation leg,
and (c) the filesystem feature-workspace tree (LSC-3). No PBT machinery (Mandate
9/11) -- the LSC is a finite, enumerable closed contract over the 3-token status
set.
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

# The ONLY production import (S2 driving-port-only invariant): the slice-01
# validate-feature-delta CLI, already shipped (slice-05 depends on slice-02 which
# depends on slice-01). It is the sole mechanical `src/des` seam slice-05 drives --
# the keystone-gate-preservation leg (a flipped epic-delta must still validate
# `accepted`). The deterministic flip producer is NOT production code -- it is the
# suite-local reference producer (`_reference_oracle.py`), a golden-file analogue
# for the LLM-mediated maintenance act, wired ONLY at GREEN (see `run_maintenance`).
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import (
    EpicId,
    FeatureId,
    FeatureStatus,
    GateOutVerdict,
    MaintenanceAction,
    MaintenanceVerdict,
)


@dataclass(frozen=True)
class RowObservation:
    """Read-only observation of one Feature Plan row after a maintenance flip.

    On the current tip the maintenance procedure is undefined, so no flip is
    applied; ``verdict`` is ``MAINTENANCE_ABSENT`` and the row reads its
    pre-maintenance defaults -- the active-RED state.
    """

    verdict: MaintenanceVerdict
    status: FeatureStatus = FeatureStatus.PENDING
    has_workspace_link: bool = False


@dataclass
class GateOutResult:
    """Observable outcome of the slice-01 gate-OUT validation on a FLIPPED delta."""

    epic_delta_exists: bool
    exit_code: int
    output: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict`` field of the single JSON object the slice-01 CLI emits."""
        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "verdict" in obj:
                    return str(obj["verdict"])
        return None

    @property
    def verdict(self) -> GateOutVerdict:
        """Map the gate-OUT outcome onto the maintainer-observable verdict.

        Reads the STRUCTURED ``verdict`` token of the slice-01 CLI, never a
        free-text substring. When the flipped epic-delta is absent (the current
        tip), the gate cannot have accepted anything -> EPIC_DELTA_ABSENT, the
        active-RED signal.
        """
        if not self.epic_delta_exists:
            return GateOutVerdict.EPIC_DELTA_ABSENT
        if self.exit_code == 0 and self._verdict_token == "accepted":
            return GateOutVerdict.ACCEPTED
        return GateOutVerdict.NOT_ACCEPTED


@dataclass
class MaintenanceComposition:
    """Composition root for the slice-05 epic-delta maintenance slice.

    ``repo_dir`` is a real tmp_path acting as the repository root. An authored
    epic-delta (every row ``pending``) lives at ``docs/epic/{id}/epic-delta.md``
    (slice-02's output). The maintenance procedure flips individual rows as the
    maintainer picks up + finalizes features. This composition observes the flip
    outcome, the keystone-gate preservation via the real slice-01 CLI, and the
    fractal-JIT invariant on the feature-workspace tree.
    """

    repo_dir: Path
    epic_id: EpicId = field(default=EpicId("flow-v2-wave-migrations"))
    target_feature: FeatureId = field(default=FeatureId("design-wave-migration"))
    action: MaintenanceAction = field(default=MaintenanceAction.PICK_UP)
    candidate_token: str = field(default="")
    seed_status: FeatureStatus = field(default=FeatureStatus.PENDING)
    _flip: object = field(default=None, init=False, repr=False)
    _token_verdict: object = field(default=None, init=False, repr=False)
    _maintained: bool = field(default=False, init=False, repr=False)

    # --- paths ---------------------------------------------------------------

    @property
    def _epic_dir(self) -> Path:
        return self.repo_dir / "docs" / "epic" / self.epic_id

    @property
    def epic_delta_path(self) -> Path:
        return self._epic_dir / "epic-delta.md"

    @property
    def _feature_workspace_root(self) -> Path:
        return self.repo_dir / "docs" / "feature"

    # --- Given: an authored epic-delta with pending rows ---------------------

    def open_authored_epic(self, epic_id: EpicId) -> None:
        """Author the epic-delta (every row ``pending``) -- slice-02's output.

        The maintenance procedure operates on an ALREADY-authored epic-delta
        (slice-05 depends on slice-02). This establishes that starting state on a
        real tmp_path: the epic-delta exists with all rows ``pending`` and ZERO
        feature workspaces (LSC-3 JIT holds for an un-picked-up epic).
        """
        from ._reference_oracle import author_epic_delta, default_epic_plan

        self.epic_id = epic_id
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        author_epic_delta(self.repo_dir, default_epic_plan(epic_id))

    def seed_feature_status(self, feature_id: FeatureId, status: FeatureStatus) -> None:
        """Establish the row's STARTING status before the action under test (LSC-5).

        AT-2 (finalize) needs the row already ``in-flight`` before the finalize
        flip. The seed advances the row through the legal forward flips so the
        starting state is reachable (never hand-set to an illegal intermediate).
        """
        self.target_feature = feature_id
        self.seed_status = status

    def target(self, feature_id: FeatureId, action: MaintenanceAction) -> None:
        """Record which feature the maintainer acts on, and the action (LSC-1/2)."""
        self.target_feature = feature_id
        self.action = action

    def _starting_plan(self):
        """The epic plan in its pre-maintenance starting state (seed applied)."""
        from ._reference_oracle import default_epic_plan, seed_row_status

        return seed_row_status(
            default_epic_plan(self.epic_id), self.target_feature, self.seed_status
        )

    def propose_status_token(self, token: str) -> None:
        """Record a candidate Status token for LSC-6 procedure-level classification."""
        self.candidate_token = token

    # --- When: the maintainer runs the maintenance procedure -----------------

    def run_maintenance(self) -> None:
        """Run the epic-delta MAINTENANCE procedure (the LSC flip).

        PROMPT-SURFACE boundary: the flip is the maintainer following the
        nw-discuss skill procedure during a discuss / feature-end session. The
        slice-05 deliverable is PROSE (DESIGN slice-02/04/05 text contracts: the
        slice's "code" is SKILL / COMMAND text, there is NO ``src/des`` surface).

        DESIGNATED GREEN WIRING POINT (atdd_pure), wired at DELIVER (slice-05):
        the suite-local reference producer -- a golden-file analogue, NOT a
        ``src/des`` import -- is wired here. It applies the LSC flip, re-renders
        the flipped epic-delta at its production path, and classifies the
        candidate Status token (LSC-6); ``observe_row`` reads the LSC verdict.
        The paired prose deliverable (the linkage/status-flip procedure + JIT
        rule + backlog-cites-epic-by-name) lives in
        ``nWave/skills/nw-discuss/SKILL.md`` §Epic-delta maintenance (LSC).
        Filling this seam is NOT a Driving-Port-Only-Boundary violation;
        importing ``src/des`` would be.
        """
        # DELIVER (slice-05) GREEN: the suite-local reference producer (a golden-file
        # analogue of the maintainer's LLM-mediated flip, NOT a ``src/des`` import) is
        # wired at this designated seam. It applies the LSC flip + re-renders the
        # flipped epic-delta at its production path; the prose deliverable (the
        # linkage/status-flip procedure + JIT rule + backlog-cites-epic) is authored
        # in ``nWave/skills/nw-discuss/SKILL.md`` §Epic-delta maintenance (LSC).
        from ._reference_oracle import (
            apply_flip,
            author_epic_delta,
            classify_status_token,
            feature_workspace_path,
        )

        flip = apply_flip(self._starting_plan(), self.target_feature, self.action)
        author_epic_delta(self.repo_dir, flip.plan)
        # LSC-1 / LSC-3: a non-pending (picked-up / finalized) feature gets its
        # docs/feature/{id}/ workspace; a pending row gets none (fractal JIT).
        for row in flip.plan.rows:
            if row.status is not FeatureStatus.PENDING:
                feature_workspace_path(self.repo_dir, row.feature_id).mkdir(
                    parents=True, exist_ok=True
                )
        self._flip = flip
        self._token_verdict = classify_status_token(self.candidate_token)
        self._maintained = True

    # --- observations: LSC contract on the flipped row -----------------------

    def observe_row(self) -> RowObservation:
        """Observe the maintained row against the LSC flip contract (LSC-1/2/5)."""
        if not self._maintained or self._flip is None:
            return RowObservation(verdict=MaintenanceVerdict.MAINTENANCE_ABSENT)
        flip = self._flip
        row = next(r for r in flip.plan.rows if r.feature_id == self.target_feature)
        return RowObservation(
            verdict=flip.verdict,
            status=row.status,
            has_workspace_link=row.has_workspace_link,
        )

    def observe_token_verdict(self) -> MaintenanceVerdict:
        """Observe the LSC-6 procedure-level classification of the candidate token."""
        if not self._maintained or self._token_verdict is None:
            return MaintenanceVerdict.MAINTENANCE_ABSENT
        return self._token_verdict

    def validate_gate_out(self) -> GateOutResult:
        """Re-validate the FLIPPED epic-delta via the REAL slice-01 CLI (LSC-1/2).

        Drives ``des validate-feature-delta --require-feature-plan --format=json
        <epic-delta>`` -- slice-01's already-shipped driving port -- through its
        real ``main(argv)`` entry. The flip must NOT break structural validity: a
        well-formed flipped epic-delta still returns ``accepted``. When no flip was
        applied (current tip), the production-path artifact is the unmaintained
        absent default -> EPIC_DELTA_ABSENT.
        """
        if not self._maintained or not self.epic_delta_path.exists():
            return GateOutResult(epic_delta_exists=False, exit_code=1, output="")
        argv = [
            "--require-feature-plan",
            "--format=json",
            str(self.epic_delta_path),
        ]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return GateOutResult(
            epic_delta_exists=True, exit_code=exit_code, output=buffer.getvalue()
        )

    def count_pending_feature_workspaces(self) -> int:
        """Count ``docs/feature/{id}/`` workspaces for rows still ``pending`` (LSC-3).

        Fractal JIT: a ``pending`` row has NO ``docs/feature/{id}/`` workspace --
        only the picked-up (``in-flight``) feature gets a workspace. A non-zero
        count means a workspace exists for an un-picked-up feature -- an LSC-3
        violation.
        """
        if not self._maintained or self._flip is None:
            return 0
        flip = self._flip
        pending_ids = [
            r.feature_id for r in flip.plan.rows if r.status is FeatureStatus.PENDING
        ]
        root = self._feature_workspace_root
        if not root.exists():
            return 0
        return sum(1 for fid in pending_ids if (root / fid).is_dir())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The maintenance flip's observable surface: the gate-OUT verdict on the
        flipped delta stays ``accepted`` (the flip preserved validity) and zero
        ``pending``-row workspaces exist (LSC-3). Both are port-exposed -- the
        validator verdict token + the filesystem workspace count -- never internal
        struct fields.
        """
        return {
            "gate_out.verdict": self.validate_gate_out().verdict.value,
            "pending_workspaces.count": self.count_pending_feature_workspaces(),
        }
