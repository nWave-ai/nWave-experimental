"""Regression coverage for the bounded candidate-radius subprocess boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from des.application import candidate_radius as radius


def test_timeout_reaps_the_real_cpu_bound_measurement_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller returns promptly and leaves no direct CPU worker behind."""
    pid_file = tmp_path / "worker.pid"
    worker = (
        "import os, sys\n"
        "from pathlib import Path\n"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "while True:\n"
        "    pass\n"
    )
    monkeypatch.setattr(
        radius,
        "_blast_radius_argv",
        lambda _root, _paths: [sys.executable, "-c", worker],
    )
    monkeypatch.setattr(radius, "RADIUS_TIMEOUT_SECONDS", 0.35)

    started = time.monotonic()
    actual = radius.candidate_radius(tmp_path, ("slow.py",))
    elapsed = time.monotonic() - started

    assert actual == radius.INDETERMINATE
    assert elapsed < 3.0, f"timeout returned only after {elapsed:.3f}s"
    worker_pid = int(pid_file.read_text())

    for _ in range(20):
        try:
            os.kill(worker_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail(f"timed-out blast-radius worker {worker_pid} is still alive")


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        (
            0,
            'preamble\n{"event": "BlastRadiusMeasured", "tier": "M", '
            '"measures": {"files": 2, "boundary_files": ["api.py"], '
            '"consumer_counts": {"pkg.entry": 4}}}\n',
            "tier=M files=2 boundary=1 consumers=max 4 (pkg.entry)",
        ),
        (0, "{not-json}\n", radius.INDETERMINATE),
        (
            0,
            '{"event": "BlastRadiusMeasured", "tier": "S", '
            '"measures": {"files": 1, "boundary_files": [], '
            '"consumer_counts": {}}}\nmalformed final line\n',
            radius.INDETERMINATE,
        ),
        (2, json.dumps({"event": "BlastRadiusInputRejected"}), radius.INDETERMINATE),
    ],
)
def test_candidate_radius_accepts_only_a_successful_measured_cli_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    expected: str,
) -> None:
    """Malformed and nonzero producer results degrade to the existing L row."""
    monkeypatch.setattr(
        radius,
        "spawn",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], returncode, stdout),
    )

    assert radius.candidate_radius(tmp_path, ("candidate.py",)) == expected
