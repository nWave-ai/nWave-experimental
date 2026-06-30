"""Composition root -- fix-verify-wave-dispatch-exemption-ssot (slice-01).

Reconciles the TWO dispatch-exemption checks that today give OPPOSITE verdicts on
the same dispatch, onto ONE canonical model (AT-3-BLOCK, ratified Ale 2026-06-23).
The composition drives BOTH real checks through their real driving surfaces:

  * verify-wave-dispatch -- the IN-TREE gate ``des.cli.verify_wave_dispatch``
    (Mandate-13, Layer-3 subprocess). Invoked as ``python -m
    des.cli.verify_wave_dispatch`` with ARGS + a tmp prompt FILE, ``cwd`` = the
    tmp repo root holding the seeded wave-active floor. Observable = the process
    EXIT CODE (0 ALLOW / 1 BLOCK) + the one JSON verdict line on stdout.

  * PreToolUse AT-3 -- the REAL shipped ``PreToolUseService`` (Layer-3
    composition: the production service wired with a real ``DesMarkerParser`` +
    the real filesystem ``WaveActiveFilesystemStore`` reading the SAME seeded
    floor). Observable = ``HookDecision.action`` ("allow"|"block") -> the
    ALLOW/BLOCK binary AT-3 actually emits in production. This is the CANONICAL
    reference the
    reconcile aligns verify-wave-dispatch TO.

The collision case (AC-1 / AC-5) is: an ACTIVE wave floor (entry_pending cleared)
+ a dispatch carrying ONLY a matching ``<!-- DES-WAVE: <wave> -->`` marker (no
DES-VALIDATION -> ``carries_partial_wave_context``) + NOT wave-entering. AT-3
BLOCKs it (WAVE_MARKER_BYPASS). verify-wave-dispatch ALLOWs it today (a matching
marker reads as on-spine, floor-blind). The reconcile makes verify-wave-dispatch
ALSO BLOCK -> the two checks AGREE (AC-5).

DRIVING-PORT-ONLY (Mandate-16): no decomposed helper is tested -- both checks are
driven through their composition-root driving surfaces. A correctly-leveled AT
makes TBU structurally impossible: delete the new collision-BLOCK branch from
``decide_dispatch`` and AC-1 + AC-5 go RED.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD ``decide_dispatch`` is floor-blind, so
verify-wave-dispatch ALLOWs the collision while AT-3 BLOCKs it -> AC-1 (expects
BLOCK) and AC-5 (expects agreement) fire semantic AssertionErrors against the
observed ALLOW. The preserved-path scenarios (AC-2/3/4) assert the verdicts the
current code ALREADY emits -> live-green regression guards.

Step bodies delegate here (Mandate-12, no logic in step bodies). The Universe the
ATs track is the port-exposed names (exit code / verdict token /
HookDecision.action), never internal regex objects.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.cli import verify_wave_dispatch
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import (
    REVIEWER_TYPE,
    DispatchMarker,
    FloorState,
    SkipAuthorization,
    Verdict,
    WaveOwner,
)


# tests/des/acceptance/wave_dispatch_exemption_ssot/steps/<this file>
#   parents[5] = REPO_ROOT (steps→feature→acceptance→des→tests→REPO_ROOT)
REPO_ROOT = Path(__file__).resolve().parents[5]

# The DES-WAVE token the DISTILL owner's spine dispatch carries (mirrors the
# policy WAVE_OWNERS map -- the AT does not import it; it asserts the verdict).
_OWNER_WAVE: dict[str, str] = {
    WaveOwner.ACCEPTANCE_DESIGNER.value: "distill",
    WaveOwner.SOLUTION_ARCHITECT.value: "design",
    WaveOwner.PRODUCT_OWNER.value: "discuss",
}

_SESSION_ID = "sess-ssot-0001"
_PROBE_FEATURE_ID = "probe"
_WAVE_SKIP_HEADING_TEMPLATE = "## Wave: {wave} / [REF] Wave Skipped"


class _AllowAllValidator(ValidatorPort):
    """A trivial classic prompt validator.

    The collision path (``not markers.is_des_task`` -> the AT-3 WAVE_MARKER_BYPASS
    branch) NEVER calls ``validate_prompt`` -- the service returns its decision
    before Step 5. This stub is wired only to satisfy the required ctor arg; if it
    were ever reached it would allow (so it can never MASK the AT-3 verdict).
    """

    def validate_prompt(self, prompt: str) -> ValidationResult:
        return ValidationResult(errors=[], task_invocation_allowed=True)


@pytest.fixture
def reconcile() -> ExemptionReconcileComposition:
    return ExemptionReconcileComposition()


@dataclass
class ExemptionReconcileComposition:
    """Drives BOTH dispatch-exemption checks against ONE seeded floor + dispatch."""

    _root: Path | None = None
    _subagent: str = ""
    _floor: FloorState = FloorState.ABSENT
    _marker: DispatchMarker = DispatchMarker.NONE
    _skip_auth: SkipAuthorization = SkipAuthorization.NONE
    _session_id: str = _SESSION_ID
    # observed
    _verify_exit: int | None = None
    _verify_stdout: str = ""
    _at3_allowed: bool | None = None
    _captured: dict[str, object] = field(default_factory=dict)

    # ---- GIVEN: arm the dispatch + the on-disk floor / witness / grant state ----

    def use_project_root(self, root: Path) -> None:
        self._root = root
        (root / ".nwave" / "des").mkdir(parents=True, exist_ok=True)
        # Trigger the des.cli freshness autoskip on the manifest-less tmp tree
        # (harness wiring only -- changes neither args nor any asserted observable).
        seed_dev_checkout_marker(root)

    def given_owner(self, owner: WaveOwner) -> None:
        self._subagent = owner.value

    def given_reviewer(self) -> None:
        self._subagent = REVIEWER_TYPE

    def given_floor(self, floor: FloorState) -> None:
        self._floor = floor

    def given_marker(self, marker: DispatchMarker) -> None:
        self._marker = marker

    def given_skip_authorization(self, skip: SkipAuthorization) -> None:
        self._skip_auth = skip

    def _wave_token(self) -> str:
        return _OWNER_WAVE.get(self._subagent, "distill")

    def _write_floor(self) -> None:
        """Write ``.nwave/wave-active/active.json`` per the armed FloorState."""
        assert self._root is not None
        if self._floor is FloorState.ABSENT:
            return
        store = WaveActiveFilesystemStore()
        entering = self._floor is FloorState.ACTIVE_ENTERING
        store.arm(
            self._root,
            WaveActiveRecord(
                wave=self._wave_token(),
                provenance=WaveProvenance.COMMAND,
                entry_pending=entering,
            ),
        )

    def _prompt_text(self) -> str:
        """Build the dispatch prompt per the armed DispatchMarker shape."""
        wave = self._wave_token()
        if self._marker is DispatchMarker.NONE:
            return "work the wave"
        if self._marker is DispatchMarker.PARTIAL_WAVE_ONLY:
            return f"<!-- DES-WAVE: {wave} -->\nwork the wave"
        # FULL_VALIDATED -- a complete classic dispatch (carries DES-VALIDATION).
        return (
            f"<!-- DES-WAVE: {wave} -->\n"
            "<!-- DES-VALIDATION : required -->\n"
            "work the wave"
        )

    def _write_skip_witness(self, rationale: str) -> None:
        assert self._root is not None
        heading = _WAVE_SKIP_HEADING_TEMPLATE.format(wave=self._wave_token().upper())
        body = f"\n{rationale}\n" if rationale else "\n"
        path = self._root / "docs" / "feature" / _PROBE_FEATURE_ID / "feature-delta.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Feature Delta: probe\n\n{heading}\n{body}\n## Wave: NEXT\n",
            encoding="utf-8",
        )

    def _write_pre_grant(self, ttl_seconds: int) -> None:
        assert self._root is not None
        grant = (
            self._root / ".nwave" / "des" / f"wave-skip-grant-{self._session_id}.json"
        )
        granted_at = time.time()
        grant.write_text(
            json.dumps(
                {
                    "session_id": self._session_id,
                    "granted_at": granted_at,
                    "ttl_seconds": ttl_seconds,
                    "expires_at": granted_at + ttl_seconds,
                    "authorized_by": "human",
                }
            ),
            encoding="utf-8",
        )

    def _materialize_skip_authorization(self) -> None:
        if self._skip_auth is SkipAuthorization.FORM_VALID_WITNESS:
            self._write_skip_witness("human authorized this skip for a real reason")
        elif self._skip_auth is SkipAuthorization.VALID_PRE_GRANT:
            self._write_pre_grant(ttl_seconds=3600)
        elif self._skip_auth is SkipAuthorization.EXPIRED_PRE_GRANT:
            self._write_pre_grant(ttl_seconds=-3600)

    # ---- WHEN: drive BOTH checks against the same on-disk state -----------------

    def when_both_checks_evaluate(self) -> None:
        """Materialize floor/witness/grant, then drive BOTH real checks."""
        assert self._root is not None
        self._write_floor()
        self._materialize_skip_authorization()
        self._drive_verify_wave_dispatch()
        self._drive_pre_tool_use_at3()

    def when_verify_wave_dispatch_evaluates(self) -> None:
        """Drive ONLY verify-wave-dispatch (preserved-path guards that AT-3 does
        not cover at the same surface -- witness / pre-grant live in the policy)."""
        assert self._root is not None
        self._write_floor()
        self._materialize_skip_authorization()
        self._drive_verify_wave_dispatch()

    def _drive_verify_wave_dispatch(self) -> None:
        assert self._root is not None
        prompt_path = self._root / ".nwave" / "des" / "dispatch-prompt.txt"
        prompt_path.write_text(self._prompt_text(), encoding="utf-8")
        # In-process analogue of ``python -m des.cli.verify_wave_dispatch ...``:
        # call the production CLI EDGE ``verify_wave_dispatch.main`` directly.
        # src-layout: the `des` package ships under REPO_ROOT/src, so PYTHONPATH
        # is set on os.environ (inherited by any subprocess the gate forks) and
        # restored after.
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [str(REPO_ROOT / "src"), str(REPO_ROOT)]
        )
        try:
            exit_code, out, err = run_cli_in_process(
                [
                    "--subagent-type",
                    self._subagent,
                    "--prompt-path",
                    str(prompt_path),
                    "--repo-root",
                    str(self._root),
                    "--session-id",
                    self._session_id,
                ],
                cwd=str(self._root),
                main=verify_wave_dispatch.main,
            )
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._verify_exit = exit_code
        self._verify_stdout = out + err

    def _drive_pre_tool_use_at3(self) -> None:
        """Run the REAL PreToolUseService over the SAME seeded floor (cwd-rooted).

        The service reads the floor via ``WaveActiveFilesystemStore.read(cwd())`` --
        so the subprocess and this in-process check observe the identical floor.
        ``wave_entering`` is the deterministic adapter signal: True iff the floor's
        ``entry_pending`` is set (the COMMAND arm wrote it on a genuine entry).
        """
        assert self._root is not None
        service = PreToolUseService(
            marker_parser=DesMarkerParser(),
            prompt_validator=_AllowAllValidator(),
            audit_writer=NullAuditLogWriter(),
            time_provider=SystemTimeProvider(),
            wave_active_reader=WaveActiveFilesystemStore(),
        )
        wave_entering = self._floor is FloorState.ACTIVE_ENTERING
        prev = Path.cwd()
        try:
            os.chdir(self._root)
            decision = service.validate(
                PreToolUseInput(
                    prompt=self._prompt_text(),
                    subagent_type=self._subagent,
                    wave_entering=wave_entering,
                )
            )
        finally:
            os.chdir(prev)
        # HookDecision exposes the verdict via ``action`` ("allow"|"block") /
        # ``exit_code`` (0 allow / 2 block) -- there is no ``is_allowed`` field.
        # Read the ALLOW/BLOCK binary off the canonical ``action`` token.
        self._at3_allowed = decision.action == "allow"

    # ---- THEN: observable-surface readers ---------------------------------------

    def _verify_verdict(self) -> Verdict:
        assert self._verify_exit is not None, "must drive verify-wave-dispatch first"
        if self._verify_exit in (0, 1, 2):
            return Verdict(self._verify_exit)
        # A non-{0,1,2} exit (e.g. module-absence / a crash) is NOT a clean verdict;
        # surface it as MALFORMED so the Then naming the expected verdict fires a
        # semantic AssertionError rather than a coercion crash.
        return Verdict.MALFORMED

    def then_verify_wave_dispatch_blocks(self) -> None:
        assert self._verify_verdict() is Verdict.BLOCK, (
            "verify-wave-dispatch must BLOCK (exit 1) the collision case the "
            "PreToolUse AT-3 floor check already blocks (active floor + a "
            "non-entering partial-marker in-wave dispatch); at HEAD decide_dispatch "
            "is floor-blind and ALLOWs it (a matching DES-WAVE marker reads as "
            f"on-spine). {self._observed()}"
        )

    def then_verify_wave_dispatch_allows(self) -> None:
        assert self._verify_verdict() is Verdict.ALLOW, (
            "verify-wave-dispatch must ALLOW this preserved exemption path "
            f"(legit entry / non-owner / witness / valid grant). {self._observed()}"
        )

    def then_pre_tool_use_at3_blocks(self) -> None:
        assert self._at3_allowed is False, (
            "the PreToolUse AT-3 floor check is expected to BLOCK the collision "
            "case (this pins the canonical reference verify-wave-dispatch aligns "
            f"to). {self._observed()}"
        )

    def then_both_checks_agree(self) -> None:
        """AC-5: for the evaluated dispatch, the two checks emit the SAME verdict.

        The load-bearing SSOT assertion: a verify-wave-dispatch ALLOW paired with
        an AT-3 BLOCK (the contradiction this feature dissolves) is a FAILURE.
        """
        assert self._at3_allowed is not None and self._verify_exit is not None, (
            "must drive BOTH checks (When) before asserting agreement"
        )
        verify_allowed = self._verify_verdict() is Verdict.ALLOW
        assert verify_allowed == self._at3_allowed, (
            "the two dispatch-exemption checks MUST present ONE consistent verdict "
            "for the collision case (AC-5 SSOT agreement). verify-wave-dispatch "
            f"allowed={verify_allowed!r}; PreToolUse AT-3 allowed={self._at3_allowed!r} "
            "-- a disagreement is exactly the contradiction this reconcile dissolves. "
            f"{self._observed()}"
        )

    def _observed(self) -> str:
        return (
            f"verify_exit={self._verify_exit!r}; at3_allowed={self._at3_allowed!r}; "
            f"subagent={self._subagent!r}; floor={self._floor.value!r}; "
            f"marker={self._marker.value!r}; skip={self._skip_auth.value!r}; "
            f"root={self._root!r}; "
            f"verify_stdout[:400]={self._verify_stdout[:400]!r}"
        )
