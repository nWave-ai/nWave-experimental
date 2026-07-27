"""Composition root for fix-wave-bypass-recovery-truthful slice-02 ATs (JOB-019).

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
``des wave-clear`` subcommand invoked through the production CLI dispatcher
(``python -m des.cli wave-clear ...``). The subcommand is the SUT; the observables
are the process exit code, the wave-active floor file on disk (removed / left),
and the audit-log file the run appends. No production module is imported-and-called
at the step boundary -- the only entry is a real subprocess (Layer 3 subprocess,
the preferred CLI driving surface).

INTENT (slice-02, OB-B=B1): a maintainer/LLM-operator facing a stale wave floor
must clear it through ONE sanctioned, loud, auditable command instead of
hand-editing active.json. The clear reuses ``WaveActiveWriter.clear()`` via a new
``WaveActivationService.clear_floor()`` method, requires ``--reason`` so the human
(not the tool) authorizes the clear, and writes an audit record on every run.

EXIT-CODE / FLOOR-STATE CONTRACT (the DESIGN `des wave-clear` CLI contract table):
  * floor present (stale inferred record) -> removed, exit 0, loud + audited; the
    next legitimate dispatch no longer sees WAVE_MARKER_BYPASS.
  * --reason absent -> usage error exit 2, no floor touched, no audit record.
  * floor absent -> no-op SUCCESS exit 0, idempotent, still audited.
  * floor corrupt/unreadable -> INDETERMINATE degrade-LOUD exit 1, audited, NEVER
    a fabricated success.
  * provenance closed set {command, inferred} UNCHANGED -- the clear removes the
    record, never writes a third value.

DORMANT-SEAM RECONCILIATION (D11): the DESIGN driving-surface declares the net-new
seam ``WaveActivationService.clear_floor()`` reached from the REAL ``des
wave-clear`` entry point (Tsunami: ``WaveActiveWriter.clear`` has ZERO external
callers today -- the CLI is its first operator-facing consumer). This AT names
THAT seam and drives it through the REAL ``des wave-clear`` subprocess, asserting
the observable effect (floor removed / exit code / audit record) -- not the
component in isolation.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``des wave-clear`` is
UNREGISTERED in the dispatcher registry (Tsunami + grep: zero matches tree-wide),
so the real dispatcher rejects it with ``invalid choice: 'wave-clear'`` (exit 2)
-- the command-not-found / unregistered-subcommand RED signal. The observable
effect never happens (floor not removed / wrong exit code / no audit record), so
each Then fires a semantic AssertionError, never a collection / import error.
GREEN once DELIVER registers the ``wave-clear`` row + ships ``src/des/cli/
wave_clear.py`` + ``WaveActivationService.clear_floor()``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_wave_bypass_recovery import ClearOutcome, FloorState


# DESIGN-PINNED floor path (slice-04 contract).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# The stale wave the empirically-hit floor carried.
_STALE_WAVE = "distill"

# A plausible operator reason (the human GO token the audit record captures).
_REASON_TEXT = "stale inferred distill floor blocking a legitimate dispatch"


@dataclass
class WaveClearComposition:
    """Drives the REAL ``des wave-clear`` subcommand via subprocess."""

    _project_root: Path | None = field(default=None)
    _floor_state: FloorState | None = field(default=None)
    _with_reason: bool = field(default=True)
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")
    _stderr: str = field(default="")

    # ---- given --------------------------------------------------------------

    def given_floor_state(self, tmp_path: Path, state: FloorState) -> None:
        """Arm the wave-active floor in one of its three read classifications."""
        self._project_root = tmp_path
        self._floor_state = state
        self._arm_floor(tmp_path, state)

    def given_clear_invoked_without_reason(self) -> None:
        """Flag the next clear to omit the mandatory ``--reason`` argument."""
        self._with_reason = False

    # ---- when ---------------------------------------------------------------

    def when_operator_runs_wave_clear(self) -> None:
        """Invoke the REAL ``des wave-clear`` subcommand; capture exit + output.

        The floor under test lives in the tmp project_root, passed via the
        DESIGN-contract ``--project-root`` argument; the subprocess itself runs
        from the repo checkout so the DES runtime-freshness guard auto-skips (a
        tmp dir has no install manifest -> the guard would refuse with exit 78,
        masking the subcommand contract). The clear operates on the tmp floor.
        """
        assert self._project_root is not None
        argv = ["wave-clear", "--project-root", str(self._project_root)]
        if self._with_reason:
            argv += ["--reason", _REASON_TEXT]
        self._run_des(argv)

    # ---- then ---------------------------------------------------------------

    def then_clear_exits(self, expected: ClearOutcome) -> None:
        """The operator-visible exit code matches the DESIGN contract for the state."""
        assert self._exit_code == expected.value, (
            f"des wave-clear must exit {expected.value} ({expected.name}) for "
            f"floor-state {self._floor_state!r} / with_reason={self._with_reason}; "
            f"got exit {self._exit_code}. {self._observed()}"
        )

    def then_floor_record_removed(self) -> None:
        """The stale floor file no longer exists after the clear (the seam's effect)."""
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert not floor_path.exists(), (
            "des wave-clear must remove the stale floor record (via "
            "WaveActivationService.clear_floor -> WaveActiveWriter.clear); the "
            f"floor file still exists. {self._observed()}"
        )

    def then_usage_error_names_the_reason_argument(self) -> None:
        """The usage error must be the GENUINE missing-``--reason`` argparse error.

        DISCRIMINATING oracle (prevents a false GREEN at HEAD): at HEAD the
        unregistered subcommand ALSO exits 2 with ``invalid choice: 'wave-clear'``
        -- the exit code alone would coincidentally match USAGE_ERROR. The stderr
        of the genuine error names the mandatory ``--reason`` argument
        (argparse ``required=True``); the unregistered-choice error does not. So
        this assertion is RED at HEAD and GREEN only once the subcommand exists and
        enforces ``--reason``.
        """
        combined = f"{self._stdout}\n{self._stderr}"
        assert "--reason" in combined and "invalid choice" not in combined, (
            "a missing --reason must produce the genuine argparse usage error "
            "naming --reason (not the HEAD unregistered-subcommand 'invalid "
            f"choice' error); stderr did not. {self._observed()}"
        )

    def then_floor_record_untouched(self) -> None:
        """A usage error must leave the stale floor exactly as it was (no clear)."""
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert floor_path.exists(), (
            "a usage error (missing --reason) must NOT touch the floor; the stale "
            f"floor record was removed. {self._observed()}"
        )

    def then_next_dispatch_no_longer_bypass_blocked(self) -> None:
        """After the clear, the same markerless dispatch is no longer WAVE_MARKER_BYPASS.

        The end-to-end value: clearing the stale floor unblocks the next
        legitimate dispatch. Driven through the REAL PreToolUseService (Layer 3
        composition) so the proof is observable, not asserted on internal state.
        """
        assert self._next_markerless_dispatch_reason() != "WAVE_MARKER_BYPASS", (
            "after des wave-clear removes the stale floor, the next markerless "
            "dispatch must NOT be vetoed by WAVE_MARKER_BYPASS (no active wave); "
            f"it still is. {self._observed()}"
        )

    def then_an_audit_record_was_written(self) -> None:
        """Every run is loud + auditable: an audit record was appended (Constraint 5)."""
        assert self._audit_record_count() >= 1, (
            "des wave-clear must write an audit record on every run (clear / "
            "no-op / indeterminate) so the authorized clear is recorded; no audit "
            f"record was found. {self._observed()}"
        )

    def then_clear_writes_no_third_provenance_value(self) -> None:
        """The clear removes the record; it never writes a third provenance value.

        Observable-artifact oracle (Constraint 6, no domain import): the stale
        floor carried provenance ``inferred`` (a member of the closed set
        {command, inferred}); after the clear the floor FILE is gone, so the clear
        wrote NO provenance at all -- it can never have introduced a third
        out-of-set value. Asserted on the floor file on disk, not a domain enum.
        """
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert not floor_path.exists(), (
            "the clear must remove the record rather than rewrite it with a new "
            "provenance -- a surviving floor file would mean the clear mutated "
            f"provenance instead of clearing. {self._observed()}"
        )

    def then_noop_message_names_project_root(self) -> None:
        """The NOOP_SUCCESS message names the project_root inspected for the floor.

        Regression oracle: an operator running wave-clear from the wrong root
        (e.g. the repo root when the floor lives in a worktree under it) must not
        be able to mistake NOOP_SUCCESS for "the floor is gone" -- the message
        must name which root was inspected, not just assert absence.
        """
        assert self._project_root is not None
        assert str(self._project_root) in self._stdout, (
            "the NOOP_SUCCESS message must name the inspected project_root so an "
            "operator cannot mistake 'no floor found here' for 'the floor is "
            f"gone'; stdout did not carry the path. {self._observed()}"
        )

    def then_indeterminate_diagnostic_on_stderr(self) -> None:
        """The INDETERMINATE degrade-LOUD diagnostic is routed to stderr.

        Stream-routing oracle (wave_clear.py:_emit routes INDETERMINATE to
        sys.stderr, every other outcome to sys.stdout). The existing CORRUPT
        scenario asserts only the exit code + the audit record -- a regression
        that mis-routed the degrade-LOUD diagnostic to stdout (where a downstream
        parser consuming stdout could mistake it for a success line) would pass
        every other Then. This pins the stream.
        """
        assert "INDETERMINATE" in self._stderr, (
            "the INDETERMINATE degrade-LOUD diagnostic must be written to stderr "
            "(wave_clear.py:_emit routes the corrupt/unreadable outcome there); "
            f"stderr did not carry it. {self._observed()}"
        )

    def then_stdout_carries_no_outcome_line(self) -> None:
        """stdout carries no wave-clear outcome line on the INDETERMINATE path."""
        assert "wave-clear:" not in self._stdout, (
            "stdout must carry NO wave-clear outcome line on the INDETERMINATE "
            "path -- the degrade-LOUD diagnostic belongs on stderr so stdout is "
            f"never mistaken for a success signal. {self._observed()}"
        )

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_des(self, argv: list[str]) -> None:
        """Invoke the REAL des dispatcher: ``python -m des.cli <argv...>``.

        Subprocess is Layer 3 subprocess -- the preferred CLI driving surface
        (Mandate-13). Runs from the repo checkout (``cwd=REPO_ROOT``) so the DES
        runtime-freshness guard auto-skips via .git adjacency; the floor under
        test is addressed by ``--project-root``. At HEAD the dispatcher rejects
        ``wave-clear`` with ``invalid choice`` (exit 2) -- the
        unregistered-subcommand RED signal.
        """
        # In-process analogue of ``python -m des.cli <argv...>`` (Mandate-13 CLI
        # driving surface). PYTHONPATH=<repo>/src is set on os.environ so any
        # subprocess the dispatcher itself forks resolves `des`; restored after.
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(_repo_root() / "src")
        try:
            exit_code, out, err = run_cli_in_process(list(argv), cwd=str(_repo_root()))
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._exit_code = exit_code
        self._stdout = out
        self._stderr = err

    def _next_markerless_dispatch_reason(self) -> str:
        """Drive the REAL PreToolUseService once more; return the block error-code prefix."""
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(
                PreToolUseInput(
                    prompt="please tidy the helper for readability",
                    wave_entering=False,
                )
            )
        finally:
            os.chdir(prev_cwd)
        reason = decision.reason or ""  # type: ignore[attr-defined]
        return reason.split(":", 1)[0] if reason else ""

    # ---- observable-surface readers -----------------------------------------

    def _audit_record_count(self) -> int:
        """Count audit records the run appended under the project's audit-log dir.

        Reads the audit-log FILE on disk (a shipped artifact the SUT produced),
        not a fabricated oracle. Scans the standard DES audit-log location for any
        JSONL record naming a wave-floor clear event.
        """
        assert self._project_root is not None
        count = 0
        for log_path in self._project_root.rglob("*.jsonl"):
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if "wave.floor.clear" in line:
                    count += 1
        return count

    # ---- precondition arming (per-state steering) ---------------------------

    def _arm_floor(self, root: Path, state: FloorState) -> None:
        if state is FloorState.STALE_INFERRED_RECORD:
            self._write_floor(
                root,
                json.dumps({"wave": _STALE_WAVE, "provenance": "inferred"}),
            )
        elif state is FloorState.CORRUPT:
            self._write_floor(root, "{not valid json")
        elif state is FloorState.ABSENT:
            # No floor file -- NoWaveActive (the idempotent no-op case).
            pass

    def _write_floor(self, root: Path, content: str) -> None:
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(content, encoding="utf-8")

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; floor_state={self._floor_state!r}; "
            f"with_reason={self._with_reason}; project_root={self._project_root!r}; "
            f"stdout={self._stdout!r}; stderr={self._stderr!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/wave_bypass_recovery/wave_bypass_recovery_steps/<file>
      parents[5] = REPO_ROOT. Running the subprocess from here lets the DES
    runtime-freshness guard auto-skip via .git adjacency.
    """
    return Path(__file__).resolve().parents[5]
