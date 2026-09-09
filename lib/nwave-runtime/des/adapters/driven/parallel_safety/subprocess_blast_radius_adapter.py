"""`SubprocessBlastRadiusAdapter` -- the real `SliceBlastRadiusPort` adapter.

Feature-delta: docs/feature/measured-parallel-safety-report/feature-delta.md
  ([REF] Driven Ports + Adapters, DC/D-6, OQ-5).

Shells `des blast-radius --repo <r> --paths <scope>` via `subprocess.run(...,
timeout=timeout_s)` and maps its single-line JSON verdict:

  * `BlastRadiusMeasured`  -> `SliceMeasurement` (touched-files axis = the
    report-supplied `--paths`, DB; boundary-files + consumer-symbols from the
    measured `measures` block).
  * `subprocess.TimeoutExpired` -> `SliceUnmeasured` (D-4, the honest
    do-not-know -- slice-02's UNMEASURED source).
  * `BlastRadiusInputRejected` / `BlastRadiusConfigRejected` -> a report-level
    `SubprocessBlastRadiusRejected` (a malformed measurement request).

This adapter owns 100% of the subprocess/git indirection; the report core
stays Python + filesystem only (D-6). `subprocess.run` spawns a Python process
(`des`) -- Python is the only runtime dependency (target-agnostic, T1).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING, cast

from des.domain.parallel_safety import SliceMeasurement, SliceUnmeasured
from des.ports.slice_blast_radius_port import SliceBlastRadiusPort


if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from des.ports.slice_blast_radius_port import SliceScope


class SubprocessBlastRadiusRejected(Exception):
    """`des blast-radius` rejected the measurement request (malformed input /
    rejected config). Surfaced by the report as an input rejection -- never a
    fabricated measurement."""


def _des_argv() -> list[str]:
    """The `des` invocation prefix: the installed console-script on PATH when
    present (OQ-5), else `[sys.executable, "-m", "des.cli"]` -- target-agnostic
    (Python is the only runtime dependency)."""
    des_binary = shutil.which("des")
    if des_binary is not None:
        return [des_binary]
    return [sys.executable, "-m", "des.cli"]


def _last_json_line(stdout: str) -> dict[str, object]:
    """The last `{...}`-shaped stdout line, parsed -- `des` may prefix an
    unrelated event line (mirrors the acceptance suite's `_last_json_line`)."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    if not json_lines:
        raise SubprocessBlastRadiusRejected(
            f"des blast-radius emitted no JSON verdict on stdout: {stdout!r}"
        )
    parsed: dict[str, object] = json.loads(json_lines[-1])
    return parsed


class SubprocessBlastRadiusAdapter(SliceBlastRadiusPort):
    """Measures a slice's scope by shelling the real `des blast-radius`."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    def measure(
        self, slice_id: str, scope: SliceScope, timeout_s: float
    ) -> SliceMeasurement | SliceUnmeasured:
        cmd = [
            *_des_argv(),
            "blast-radius",
            "--repo",
            str(self._repo),
            "--paths",
            *scope.paths,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SliceUnmeasured(
                slice_id=slice_id,
                paths=scope.paths,
                reason=(
                    f"des blast-radius exceeded the {timeout_s:g}s wall-clock "
                    f"budget measuring {', '.join(scope.paths)} -- a high-fan-in "
                    f"file cost, reported UNMEASURED rather than coerced (D-4)"
                ),
            )

        payload = _last_json_line(completed.stdout)
        event = payload.get("event")
        if event == "BlastRadiusMeasured":
            measures = cast("Mapping[str, object]", payload["measures"])
            boundary_files = cast("list[str]", measures.get("boundary_files", []))
            consumer_counts = cast(
                "Mapping[str, object]", measures.get("consumer_counts", {})
            )
            return SliceMeasurement(
                slice_id=slice_id,
                files=frozenset(scope.paths),
                boundary_files=frozenset(boundary_files),
                consumer_symbols=frozenset(consumer_counts),
            )
        raise SubprocessBlastRadiusRejected(
            f"des blast-radius rejected the measurement for {slice_id} "
            f"({', '.join(scope.paths)}): {payload.get('reasons', [event])}"
        )
