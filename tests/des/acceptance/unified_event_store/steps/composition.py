"""Composition root for the unified-event-store slice-02 acceptance ATs.

Driving-port-only (Mandate-13). The ONE feature walking-skeleton drives the
real `des` CLI dispatcher via subprocess (`python -m des.cli event-store-probe
...`); every other scenario drives `des.cli.event_store_probe.main(argv,
output=CapturingOutput())` IN-PROCESS (Mandate-13 L2 default, no interpreter
fork -- the "CLI = e2e by construction" caveat is dissolved for this project,
`nw-distill-port-treatment-policy`).

active-RED (classic Mandate-7 scaffold usage, not the P1-P4
avoid-scaffolding pattern): `UnifiedEventStoreAdapter` / `StoreAvailabilityProbe`
are FULLY scaffolded modules (real files, `__SCAFFOLD__ = True`,
`AssertionError` bodies) -- importing `des.cli.event_store_probe` at module
top is therefore SAFE (no absent name), and the absent BEHAVIOUR surfaces as
an uncaught `AssertionError` raised from WITHIN the in-process `main()` call.
This composition catches that ONE exception class narrowly and records it on
the observable so `Then` steps report a business-meaningful failure instead
of a bare traceback.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from des.cli import event_store_probe
from des.domain.telemetry_paths import telemetry_root
from des.testing.output_capture import CapturingOutput

from .domain_types import InducedFault, ProbeObservable


class EventStoreProbeComposition:
    """Production-wired composition root driving the real event-store-probe CLI."""

    def __init__(self) -> None:
        self._sandbox_root: Path | None = None
        self._observable: ProbeObservable | None = None
        self._telemetry_listing_before: tuple[str, ...] | None = None
        self._made_unreadable: list[Path] = []

    # --- Given -------------------------------------------------------------

    def given_healthy_sandbox(self, tmp_path: Path) -> None:
        self._sandbox_root = tmp_path
        telemetry_root(tmp_path).mkdir(parents=True, exist_ok=True)

    def given_fault_induced(self, fault_text: str) -> None:
        assert self._sandbox_root is not None, (
            "the sandbox must be armed (given_healthy_sandbox) before a "
            "fault can be induced."
        )
        fault = InducedFault(fault_text)
        root = telemetry_root(self._sandbox_root)
        if fault is InducedFault.MISSING_DIRECTORY:
            if root.is_dir():
                shutil.rmtree(root)
            return
        if fault is InducedFault.PERMISSION_DENIED:
            root.mkdir(parents=True, exist_ok=True)
            self._made_unreadable.append(root)
            root.chmod(0o000)
            return
        if fault is InducedFault.NOT_A_DIRECTORY:
            if root.is_dir():
                shutil.rmtree(root)
            elif root.exists():
                root.unlink()
            root.parent.mkdir(parents=True, exist_ok=True)
            root.write_text("not a directory", encoding="utf-8")
            return

    def restore_permissions(self) -> None:
        """Undo every `chmod 0o000` this composition induced.

        pytest cannot remove a 0o000 directory, so without this the tmp tree
        survives as undeletable `garbage-*` in `/tmp/pytest-of-*` on a box
        shared with other lanes. Callers must invoke it from fixture teardown,
        never from a trailing step body a failing assertion would skip.
        """
        while self._made_unreadable:
            path = self._made_unreadable.pop()
            try:
                path.chmod(0o755)
            except OSError:
                pass

    # --- When ----------------------------------------------------------------

    def when_run_via_subprocess(self) -> None:
        assert self._sandbox_root is not None
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli",
                "event-store-probe",
                "--repo-root",
                str(self._sandbox_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self._observable = ProbeObservable(
            exit_code=result.returncode,
            captured_output=f"{result.stdout}\n{result.stderr}",
        )

    def when_run_in_process(self) -> None:
        assert self._sandbox_root is not None
        self._telemetry_listing_before = self.telemetry_root_listing()

        fake = CapturingOutput()
        argv = ["--repo-root", str(self._sandbox_root)]
        exit_code: int | None = None
        scaffold_error: str | None = None
        try:
            exit_code = event_store_probe.main(argv, output=fake)
        except AssertionError as exc:
            # RED at HEAD: UnifiedEventStoreAdapter is a scaffold. Caught
            # NARROWLY (only AssertionError) so a genuine test-authoring bug
            # elsewhere is never masked.
            scaffold_error = str(exc)
        self._observable = ProbeObservable(
            exit_code=exit_code,
            captured_output=fake.captured_text(),
            scaffold_error=scaffold_error,
        )

    # --- observable accessors -------------------------------------------

    def observable(self) -> ProbeObservable:
        assert self._observable is not None, (
            "the probe must have been driven (When) before an observable is read."
        )
        return self._observable

    def diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "(the probe was never driven)"
        return (
            f"(exit_code={obs.exit_code!r}, scaffold_error={obs.scaffold_error!r}, "
            f"captured={obs.captured_output!r})"
        )

    def sandbox_root(self) -> Path:
        assert self._sandbox_root is not None
        return self._sandbox_root

    # --- universe (Mandate 8 -- port-exposed observable snapshot) --------

    def telemetry_root_listing(self) -> tuple[str, ...]:
        """The sandbox's telemetry-root listing, a port-exposed filesystem
        observable.

        Four DISTINGUISHABLE states, not two (peer-review BLOCKER, closed):
        root-absent and root-present-but-empty both collapsed to `()` in an
        earlier version, which made this oracle VACUOUS on the
        missing-directory and not-a-directory fault rows -- a defect that
        refuses correctly (right exception, right message) but ALSO
        `mkdir -p`'s the root on the way out (a plausible copy-paste; the
        production `_append_record` does exactly this at line ~1645) left
        `before == after == ()`, so `unchanged()` passed over the created
        root. `root.exists()` is INSIDE the `try` deliberately: it raises
        `PermissionError` when an ancestor directory is unreadable, so it
        must not sit outside the guard. A permission-denied directory still
        collapses to one stable sentinel (chmod 0o000 blocks even listing),
        so a before/after comparison still holds when the fault keeps the
        directory equally inaccessible on both snapshots."""
        assert self._sandbox_root is not None
        root = telemetry_root(self._sandbox_root)
        try:
            if not root.exists():
                return ("<root-absent>",)
            if not root.is_dir():
                return ("<root-not-a-directory>",)
            return tuple(
                sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            )
        except PermissionError:
            return ("<permission-denied: cannot enumerate>",)

    def telemetry_root_listing_before(self) -> tuple[str, ...]:
        assert self._telemetry_listing_before is not None, (
            "the before-snapshot is only captured on the in-process driving path."
        )
        return self._telemetry_listing_before
