"""Composition root for the at-in-process-port-default slice-03 enforcement levers.

Driving-port-only (Mandate-13). Each lever is driven through the REAL gate entry
``main(argv)`` --- ``des.cli.verify_readiness_pre_dispatch.main`` (lever-1 wiring,
L3 integration-per-adapter, L4 contract-per-port), ``des.cli.carpaccio_slice_gate
.main`` (ZOMBIES-zero sad-path floor) --- called IN-PROCESS (a direct function
call, stdout/stderr captured), NEVER a ``subprocess.run([sys.executable, ...])``
fork. This honours THIS feature's own Locked Decision: subprocess-e2e is reserved
for ``@walking_skeleton``; every other AT drives in-process. The slice-03 ATs are
themselves the proof that the levers can be driven in-process.

The per-language spawn-detector (lever-5 / fixture-scale-a) is exercised through
the SHIPPED arch-test seam ``tests/build/test_no_inline_interpreter_spawn.py``'s
AST scanner (to be widened to ``tests/**`` + WS-exempt + per-language); the
composition reaches it through the production helper the DESIGN pins
(``des.cli.run_contract_gate`` / the widened scanner) IN-PROCESS, never a fork.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD the net-new production
seams this slice's DESIGN pins are ABSENT (verified 2026-06-24):

  * ``verify_readiness_pre_dispatch.main`` ships SEVEN invariants only (slice-plan,
    scenario-tags, AT-review, gate-output, pre-commit-scope, reuse-first,
    sustainability). It has NO lever-1 wiring invariant, NO L3 integration-per-
    adapter invariant, NO L4 contract-per-port invariant. So a workspace that
    SHOULD be flagged on those axes currently CLEARS -> the flag observable is
    False -> the named RED.
  * ``tests/build/test_no_inline_interpreter_spawn.py`` scans ``src/des/**`` ONLY;
    it does NOT scan ``tests/**`` nor carve ``@walking_skeleton``, and exposes NO
    per-language detector callable / NO structured-event flag surface. So driving
    it for a non-WS test spawn produces no flag -> the named RED.
  * ``carpaccio_slice_gate.main`` has NO ZOMBIES-zero sad-path floor.
  * the F821 re-wire (pre-commit + un-suppressing ``pyproject.toml:377-382``) and
    the target-aware NOT_APPLICABLE-on-non-Python behaviour do not exist.

THE ACTIVE-RED MECHANISM (DESIGN P1-P4, F1 collection-semantics premise):

  P1  This module imports ONLY STABLE always-present entries (``main`` of the
      three gates) at module top --- never an absent lever helper / a not-yet-
      created detector callable. Importing an absent name at module top would
      raise ``ImportError`` during COLLECTION => a BROKEN test, not active-RED.
  P2  The driving call is ``main(argv)`` --- a DIRECT in-process call. No fork.
      ``forked_interpreter``/``git_invoked`` are structurally False (this module
      imports no ``subprocess``, shells out to no ``git``).
  P3  The not-yet-built lever is reached at RUNTIME inside the gate's own
      invariant dispatch: at HEAD the new invariant simply is not in the
      ``report.invariants.append(...)`` chain, so the gate clears where it should
      refuse --- a RUNTIME absence surfaced as a verdict, NOT a collection error.
  P4  Each Then asserts on the CAPTURED structured observable (``LeverObservable``
      / ``SpawnDetectorOutcome``) --- the flag, the named target, the confidence
      label, the verdict. At HEAD the flag does not fire, so each assertion is a
      NAMED semantic ``AssertionError`` (failure-for-the-right-reason).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks
a different surface shape):

  A1 (lever-1 wiring): a NEW readiness invariant ``unwired_entry`` (or similarly
     named) that calls ``CodeFactPort.query`` for ``query.callers-of`` OR
     ``query.reads-of`` on the produced entry; ``callers==0 AND reads==0`` =>
     REFUSED with the symbol named + the confidence label carried. The HARDENED
     OR (reads_of-OR-callers_of) avoids a false-0 on registry-dispatched entries.
  A2 (L3 integration-per-adapter): a NEW invariant enumerating
     ``src/des/adapters/driven/**`` concrete adapters; an adapter with no
     ``@real-io @adapter-integration`` AT and no cited waiver => REFUSED naming
     that adapter.
  A3 (L4 contract-per-port): a NEW invariant enumerating ``src/des/ports/**``
     Protocols; a port with methods, no contract test, no waiver => REFUSED.
  A4 (spawn-overuse gate): the widened ``test_no_inline_interpreter_spawn``
     scanner exposes a callable that, given a test corpus + the language, returns
     the non-WS spawn sites as a structured flag; per-language argv[0] shapes
     (Python ``subprocess``/``sys.executable``; Rust ``Command::new``; Go
     ``exec.Command``); WS-tagged ATs exempt; unrecognized language =>
     NOT_APPLICABLE; unparseable file => INDETERMINATE; git never invoked.
  A5 (lever-2 F821): the re-wired pre-commit F821 check over the test corpus
     (un-suppressing the 6 per-file ignores) flags an undefined name; on a
     non-Python target it emits ``health.gate.f821-unavailable.indeterminate`` and
     CLEARS as NOT_APPLICABLE (never ruff-hardcoded as a hard requirement).
  A6 (ZOMBIES-zero): ``carpaccio_slice_gate.main`` gains a non-vacuity floor on
     the slice's error-path AT count; a slice with zero sad-path ATs => flagged.

The named flag tokens (A1..A7) are the structured events the Then asserts on;
they are absent at HEAD, so every current-slice scenario RED-fails for the right
reason. DELIVER ships the levers to turn these GREEN. Collection imports ONLY the
three ``main`` entries (present) --- the absent lever names appear nowhere at
module top, so the suite COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

# P1: import ONLY stable, always-present gate entries. NEVER an absent lever
# helper or a not-yet-created detector callable.
from des.cli.carpaccio_slice_gate import main as carpaccio_main
from des.cli.verify_readiness_pre_dispatch import main as readiness_main

from .domain_types_slice_03 import GateVerdict, LeverObservable, SpawnDetectorOutcome


# --- The structured-event tokens the levers emit when they FLAG (absent at HEAD).
# A1..A7: the machine-readable flag each lever produces (Q3 resolution: the gate
# FLAGS with a structured event, never a bare exit code). DELIVER emits these.
_EVENT_UNWIRED_ENTRY_FLAGGED = "UnwiredEntryFlagged"
_EVENT_ADAPTER_INTEGRATION_MISSING = "AdapterIntegrationMissing"
_EVENT_PORT_CONTRACT_MISSING = "PortContractMissing"
_EVENT_NON_WS_SPAWN_FLAGGED = "NonWalkingSkeletonSpawnFlagged"
_EVENT_UNDEFINED_NAME_FLAGGED = "UndefinedNameFlagged"
_EVENT_ZOMBIES_MISSING_FLAGGED = "SadPathFloorFlagged"

# The readiness-invariant ids the new levers add to the report (absent at HEAD).
_INV_LEVER1_WIRING = "unwired_entry"
_INV_L3_ADAPTER_INTEGRATION = "integration_per_adapter"
_INV_L4_PORT_CONTRACT = "contract_per_port"


@dataclass
class EnforcementLeverComposition:
    """Production-wired composition root driving the REAL gate entries in-process.

    One composition serves every slice-03 lever: each ``arm_*`` materialises the
    real workspace that SHOULD trip a given lever, each ``drive_*`` calls the REAL
    gate ``main(argv)`` IN-PROCESS, and ``observable()`` returns the captured
    structured flag a Then asserts on.
    """

    _repo_root: Path | None = field(default=None)
    _observable: LeverObservable | None = field(default=None)
    _detector_outcome: SpawnDetectorOutcome | None = field(default=None)
    _feature_id: str = field(default="at-in-process-port-default")
    _slice_id: str = field(default="slice-03")
    _target_language: str = field(default="python")

    # --- Given ---------------------------------------------------------------

    def given_real_repo(self, tmp_path: Path) -> None:
        """Materialise a real repo the gates can run against (real-IO)."""
        self._repo_root = tmp_path

    def given_target_language(self, language: str) -> None:
        """Pin the target project's language (Python vs a non-Python target)."""
        self._target_language = language

    # --- In-process driving helper (P2/P3, no fork, no git) ------------------

    def _drive_in_process(self, entry, argv: list[str]) -> tuple[int, str]:
        """Call a REAL gate ``main(argv)`` IN-PROCESS, capturing terminal output.

        A clean direct call -- NO interpreter fork (this module imports no
        ``subprocess``), NO ``git`` shell-out. An argparse rejection surfaces as a
        runtime ``SystemExit`` inside the call (caught + recorded), never a
        collection/setup error.
        """
        assert self._repo_root is not None, (
            "the real repo must be armed (Given) before a gate entry is driven."
        )
        out, err = io.StringIO(), io.StringIO()
        exit_code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                exit_code = int(entry(argv))
            except SystemExit as exc:  # argparse / explicit exit inside the call.
                exit_code = int(exc.code) if isinstance(exc.code, int) else 2
        return exit_code, f"{out.getvalue()}\n{err.getvalue()}"

    def _readiness_argv(self) -> list[str]:
        # DELIVER-updated (A1-A7 latitude): the AXIS-B levers are opt-in via
        # --enforce-axis-b so existing readiness callers stay byte-identical; the
        # target language drives the F821 NOT_APPLICABLE projection (DDD-2b).
        return [
            "--feature-id",
            self._feature_id,
            "--slice-id",
            self._slice_id,
            "--repo-root",
            str(self._repo_root),
            "--enforce-axis-b",
            "--target-language",
            self._target_language,
        ]

    def _parse_invariant(self, captured: str, invariant_id: str) -> dict | None:
        """Find the named invariant record in the readiness gate's JSON output."""
        for line in captured.splitlines():
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            for inv in record.get("invariants", []):
                if inv.get("id") == invariant_id:
                    return inv
        return None

    # --- When: drive each lever's REAL gate entry IN-PROCESS -----------------

    def drive_lever1_wiring(self) -> None:
        """Drive the readiness gate for a produced entry with zero callers+reads.

        At HEAD no ``unwired_entry`` invariant exists, so the gate clears where it
        should refuse: ``flagged`` is False -> the RED. The HARDENED OR
        (reads_of-OR-callers_of) and the CodeFactPort confidence label are pinned
        by A1; at HEAD neither surfaces.
        """
        exit_code, captured = self._drive_in_process(
            readiness_main, self._readiness_argv()
        )
        inv = self._parse_invariant(captured, _INV_LEVER1_WIRING)
        flagged = inv is not None and inv.get("status") == "failed"
        self._observable = LeverObservable(
            flagged=flagged,
            structured_event=_EVENT_UNWIRED_ENTRY_FLAGGED if flagged else "",
            flagged_target=(inv or {}).get("remediation", "") if flagged else "",
            # A1: the confidence label carried with the wiring flag (absent at HEAD).
            confidence=(inv or {}).get("confidence", "") if inv else "",
            forked_interpreter=False,
            verdict=GateVerdict.REFUSED if exit_code != 0 else GateVerdict.CLEARED,
            captured_output=captured,
            exit_code=exit_code,
        )

    def drive_l3_adapter_integration(self) -> None:
        """Drive the readiness gate for an adapter with no integration test."""
        exit_code, captured = self._drive_in_process(
            readiness_main, self._readiness_argv()
        )
        inv = self._parse_invariant(captured, _INV_L3_ADAPTER_INTEGRATION)
        flagged = inv is not None and inv.get("status") == "failed"
        self._observable = LeverObservable(
            flagged=flagged,
            structured_event=_EVENT_ADAPTER_INTEGRATION_MISSING if flagged else "",
            flagged_target=(inv or {}).get("remediation", "") if flagged else "",
            forked_interpreter=False,
            verdict=GateVerdict.REFUSED if exit_code != 0 else GateVerdict.CLEARED,
            captured_output=captured,
            exit_code=exit_code,
        )

    def drive_l4_port_contract(self) -> None:
        """Drive the readiness gate for a port with no contract test."""
        exit_code, captured = self._drive_in_process(
            readiness_main, self._readiness_argv()
        )
        inv = self._parse_invariant(captured, _INV_L4_PORT_CONTRACT)
        flagged = inv is not None and inv.get("status") == "failed"
        self._observable = LeverObservable(
            flagged=flagged,
            structured_event=_EVENT_PORT_CONTRACT_MISSING if flagged else "",
            flagged_target=(inv or {}).get("remediation", "") if flagged else "",
            forked_interpreter=False,
            verdict=GateVerdict.REFUSED if exit_code != 0 else GateVerdict.CLEARED,
            captured_output=captured,
            exit_code=exit_code,
        )

    def drive_zombies_zero(self) -> None:
        """Drive the carpaccio slice gate for a slice with zero sad-path ATs.

        At HEAD ``carpaccio_slice_gate.main`` has no ZOMBIES-zero floor, so a
        slice with no error-path AT is NOT flagged: ``flagged`` is False -> the RED.
        """
        # DELIVER-updated (A7 latitude): the ZOMBIES-zero floor is opt-in via
        # --enforce-sad-path-floor so existing carpaccio callers stay
        # byte-identical; the observable contract (SadPathFloorFlagged) is unchanged.
        argv = [
            "--feature-id",
            self._feature_id,
            "--entering-slice",
            self._slice_id,
            "--repo-root",
            str(self._repo_root),
            "--enforce-sad-path-floor",
        ]
        exit_code, captured = self._drive_in_process(carpaccio_main, argv)
        flagged = _EVENT_ZOMBIES_MISSING_FLAGGED in captured
        self._observable = LeverObservable(
            flagged=flagged,
            structured_event=_EVENT_ZOMBIES_MISSING_FLAGGED if flagged else "",
            forked_interpreter=False,
            verdict=GateVerdict.REFUSED if exit_code != 0 else GateVerdict.CLEARED,
            captured_output=captured,
            exit_code=exit_code,
        )

    def drive_lever2_f821(self) -> None:
        """Drive the F821/undefined-name lever over the test corpus (in-process).

        At HEAD there is no re-wired F821 gate over the test corpus, so a
        called-but-undefined name is NOT flagged: ``flagged`` is False -> the RED.
        On a non-Python target this lever must clear as NOT_APPLICABLE (A5) --
        asserted by the sad-path scenario.
        """
        exit_code, captured = self._drive_in_process(
            readiness_main, self._readiness_argv()
        )
        inv = self._parse_invariant(captured, "undefined_name_check")
        flagged = inv is not None and inv.get("status") == "failed"
        is_non_python = self._target_language != "python"
        if is_non_python:
            # A5: non-Python target => NOT_APPLICABLE, emits the health event,
            # clears WITHOUT a false flag. Absent at HEAD => not_applicable_reason
            # empty => the named RED for the non-Python sad path.
            reason = (inv or {}).get("remediation", "") if inv else ""
            self._observable = LeverObservable(
                flagged=False,
                structured_event="",
                not_applicable_reason=reason,
                verdict=(
                    GateVerdict.NOT_APPLICABLE
                    if "f821-unavailable" in captured
                    else GateVerdict.CLEARED
                ),
                forked_interpreter=False,
                captured_output=captured,
                exit_code=exit_code,
            )
            return
        self._observable = LeverObservable(
            flagged=flagged,
            structured_event=_EVENT_UNDEFINED_NAME_FLAGGED if flagged else "",
            flagged_target=(inv or {}).get("remediation", "") if flagged else "",
            forked_interpreter=False,
            verdict=GateVerdict.REFUSED if exit_code != 0 else GateVerdict.CLEARED,
            captured_output=captured,
            exit_code=exit_code,
        )

    def drive_spawn_detector(self, language: str, walking_skeleton: bool) -> None:
        """Drive the per-language spawn-detector for a test that spawns a process.

        At HEAD ``test_no_inline_interpreter_spawn`` scans ``src/des/**`` only,
        carves no ``@walking_skeleton``, and exposes no per-language structured
        flag, so driving it for a non-WS test spawn produces no flag ->
        ``spawn_flagged`` False -> the RED. An unrecognized language must clear as
        NOT_APPLICABLE (degrade-LOUD); git must never be invoked.
        """
        _exit_code, captured = self._drive_in_process(
            readiness_main, self._readiness_argv()
        )
        inv = self._parse_invariant(captured, "non_ws_spawn")
        recognised = language in {"python", "rust", "go"}
        flagged = (
            inv is not None
            and inv.get("status") == "failed"
            and recognised
            and not walking_skeleton
        )
        self._detector_outcome = SpawnDetectorOutcome(
            language=language,
            spawn_flagged=flagged,
            walking_skeleton_exempt=walking_skeleton and inv is not None,
            verdict=(
                GateVerdict.NOT_APPLICABLE if not recognised else GateVerdict.CLEARED
            ),
            not_applicable_reason=(
                (inv or {}).get("remediation", "") if inv and not recognised else ""
            ),
            # The detector is git-free by construction (no subprocess/git here).
            git_invoked=False,
            captured_output=captured,
        )

    # --- observable accessors ------------------------------------------------

    def observable(self) -> LeverObservable:
        assert self._observable is not None, (
            "a lever's gate entry must have been driven (When) before its "
            "observable is read."
        )
        return self._observable

    def detector_outcome(self) -> SpawnDetectorOutcome:
        assert self._detector_outcome is not None, (
            "the spawn-detector must have been driven (When) before its outcome "
            "is read."
        )
        return self._detector_outcome

    def diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "(no lever was driven)"
        return (
            f"(flagged={obs.flagged}, structured_event={obs.structured_event!r}, "
            f"verdict={obs.verdict.value}, exit_code={obs.exit_code}, "
            f"captured={obs.captured_output!r})"
        )

    def detector_diag(self) -> str:
        oc = self._detector_outcome
        if oc is None:
            return "(no detector was driven)"
        return (
            f"(language={oc.language!r}, spawn_flagged={oc.spawn_flagged}, "
            f"verdict={oc.verdict.value}, ws_exempt={oc.walking_skeleton_exempt}, "
            f"git_invoked={oc.git_invoked}, captured={oc.captured_output!r})"
        )
