"""Composition root for the at-in-process-port-default slice-01 exemplar ATs.

Driving-port-only (Mandate-13). The behaviour is driven through the REAL
run-contract-gate entry --- ``des.cli.run_contract_gate.main(argv)`` --- called
IN-PROCESS (a direct function call), NEVER a ``subprocess.run([sys.executable,
...])`` fork. Driving the real entry in-process with terminal output captured IS
the walking-skeleton this feature ships: it proves the in-process active-RED
pattern is executable, which is the whole point of the bleeding-stop exemplar.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD the net-new production seam
this slice's DESIGN pins is ABSENT (verified 2026-06-24):

  * ``run_contract_gate.main`` has signature ``main(argv)`` ONLY --- it does NOT
    accept an injected ``OutputPort`` (DESIGN §2), and ``_build_parser`` defines
    NO ``--inprocess-exemplar`` route (DESIGN §1 / Component Decomposition);
  * the new ``OutputPort`` / ``StdoutOutput`` / ``CapturingOutput`` components are
    absent (verified: ``src/des/testing/`` does not exist; no
    ``src/des/ports/driven_ports/output_port.py``).

THE ACTIVE-RED MECHANISM (DESIGN P1-P4, F1 collection-semantics premise):

  P1  This module imports ONLY the STABLE ``main`` entry at module top --- never
      the absent ``OutputPort`` / ``CapturingOutput``. Importing an absent name at
      module top would raise ``ImportError`` during COLLECTION => a BROKEN test,
      not active-RED (the escalation trap the dispatch warned about). The absent
      names appear NOWHERE in this module --- collection imports only ``main``
      (present @ run_contract_gate.py:1711) + stdlib.
  P2  The driving call is ``main(["--repo", str(tmp), "--inprocess-exemplar"])``
      --- a DIRECT in-process call. No fork. ``forked_interpreter`` is
      structurally False (this module contains no ``subprocess`` import at all).
  P3  The not-yet-built behaviour is reached at RUNTIME inside the call: at HEAD
      ``--inprocess-exemplar`` is an unrecognised flag, so ``_build_parser().
      parse_args(argv)`` rejects it and argparse raises ``SystemExit(2)`` WITHIN
      the ``main()`` call (a runtime exception, NOT a collection error). We catch
      it and record ``route_recognised=False``.
  P4  Each Then asserts on the CAPTURED observable (``InProcessExemplarObservable``)
      --- the route is recognised + an in-process-routed verdict line is emitted.
      At HEAD neither holds, so each assertion is a NAMED semantic
      ``AssertionError`` (failure-for-the-right-reason), never an import traceback.

So the suite COLLECTS cleanly at HEAD and every current-slice scenario RED-fails
for the right reason (missing in-process-exemplar route + OutputPort injection).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks
a different surface shape):

  A1 (route): the wired surface is a ``--inprocess-exemplar`` route on
     ``run_contract_gate.main`` whose ``_mode`` drives the in-process exemplar
     and (per DESIGN §2) routes its output through the injected ``OutputPort``.
     ``main`` gains ``main(argv, output: OutputPort | None = None)`` defaulting to
     ``StdoutOutput()`` (back-compatible: existing callers pass nothing).
  A2 (verdict token): the recognised route emits the literal token
     ``IN_PROCESS_EXEMPLAR_OK`` on the captured terminal output (the line the
     ``CapturingOutput`` fake would record). The Then asserts that token is a
     substring of the captured output --- a NAMED observable, not a bare exit code.
  A3 (no fork): the exemplar drives ``main(argv)`` directly; the no-fork contract
     is pinned structurally (this composition imports no ``subprocess``).
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path

# P1: import ONLY the stable entry. NEVER the absent OutputPort / CapturingOutput.
from des.cli.run_contract_gate import main

from .domain_types import InProcessExemplarObservable


# A1: the in-process exemplar route the maintainer asks for (absent at HEAD).
_EXEMPLAR_FLAG = "--inprocess-exemplar"

# A2: the in-process-routed verdict token the recognised route emits (absent at HEAD).
_ROUTED_VERDICT_TOKEN = "IN_PROCESS_EXEMPLAR_OK"


@dataclass
class InProcessExemplarComposition:
    """Production-wired composition root driving the REAL gate entry in-process."""

    _repo_root: Path | None = field(default=None)
    _observable: InProcessExemplarObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # --- Given ---------------------------------------------------------------

    def given_real_repo(self, tmp_path: Path) -> None:
        """Materialise a real repo the contract gate can run against (real-IO)."""
        self._repo_root = tmp_path

    # --- When ----------------------------------------------------------------

    def drive_in_process_exemplar(self) -> None:
        """Drive the REAL ``main(argv)`` IN-PROCESS for the exemplar route (P2/P3).

        Captures stdout+stderr without forking. The unknown-flag rejection at HEAD
        surfaces as a runtime ``SystemExit`` inside the call --- caught + recorded,
        never propagated as a collection/setup error.
        """
        assert self._repo_root is not None, (
            "the real repo must be armed (Given) before the entry is driven."
        )
        # Snapshot the read-only-contract universe BEFORE the in-process call.
        self._universe_before = self.capture_universe()

        argv = ["--repo", str(self._repo_root), _EXEMPLAR_FLAG]
        out, err = io.StringIO(), io.StringIO()
        route_recognised = True
        exit_code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                exit_code = main(argv)  # P2: DIRECT in-process call, no fork.
            except SystemExit as exc:  # P3: argparse rejects the unknown flag at HEAD.
                # An unrecognised flag => argparse error => the route is NOT
                # recognised. A clean parse that nonetheless exits 0 is treated as
                # recognised (DELIVER's wired route returns an int normally).
                route_recognised = False
                exit_code = int(exc.code) if isinstance(exc.code, int) else 2

        captured = f"{out.getvalue()}\n{err.getvalue()}"
        self._observable = InProcessExemplarObservable(
            route_recognised=route_recognised,
            routed_verdict_emitted=_ROUTED_VERDICT_TOKEN in captured,
            # A3 / P2: structurally no fork --- this module imports no subprocess.
            forked_interpreter=False,
            captured_output=captured,
            exit_code=exit_code,
        )

    # --- observable accessor -------------------------------------------------

    def observable(self) -> InProcessExemplarObservable:
        assert self._observable is not None, (
            "the entry must have been driven (When) before an observable is read."
        )
        return self._observable

    def diag(self) -> str:
        """A diagnostic suffix naming what the in-process call actually produced."""
        obs = self._observable
        if obs is None:
            return "(the entry was never driven)"
        return (
            f"(route_recognised={obs.route_recognised}, "
            f"routed_verdict_emitted={obs.routed_verdict_emitted}, "
            f"exit_code={obs.exit_code}, captured={obs.captured_output!r})"
        )

    # --- universe (Mandate 8 --- port-exposed observable snapshot) -----------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for ``assert_state_delta`` (Mandate 8).

        The contract-gate exemplar reads the repo and writes ONLY terminal output;
        it must not mutate the maintainer's repo tree. The universe is the repo
        directory's existence and the count of entries directly under it ---
        port-exposed filesystem observables, never internal struct fields.
        """
        repo = self._repo_root
        exists = repo.exists() if repo is not None else False
        entry_count = (
            len(list(repo.iterdir())) if repo is not None and repo.is_dir() else 0
        )
        return {
            "repo.exists": exists,
            "repo.entry_count": entry_count,
        }

    def universe_before(self) -> dict[str, object]:
        assert self._universe_before is not None, (
            "the entry must have been driven (capturing the before-universe) "
            "before the read-only contract can be asserted."
        )
        return self._universe_before
