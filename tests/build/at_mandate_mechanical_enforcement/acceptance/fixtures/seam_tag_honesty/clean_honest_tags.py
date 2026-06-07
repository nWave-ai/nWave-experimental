"""GOLDEN FIXTURE (clean corpus -- honest seam tags) -- CM-I gate.

This file is NOT a real test. It is the precision-half corpus the slice-05 gate
scans: a well-formed suite the CM-I rule MUST NOT flag
(``detect(...).flagged is False``). It carries the two honest shapes plus the
precision near-miss a naive scanner would over-fire on:

  1. A test tagged ``@pytest.mark.wiring_e2e`` whose body GENUINELY spawns a real
     subprocess (``subprocess.run([sys.executable, "-m", "des", ...])``). The tag
     MATCHES the spawn shape -- honest, not a breach.

  2. THE PRECISION NEAR-MISS: a test whose body drives ``main(argv)`` IN-PROCESS
     -- exactly the spawn shape that is dishonest UNDER A SUBPROCESS TAG -- but
     which is HONESTLY tagged ``@pytest.mark.component`` (it claims an in-process
     component test, which is what it is). The gate must NOT flag it: the body
     shape alone is not the breach; the breach is the MISMATCH between a
     real-subprocess CLAIM and an in-process body. An honest in-process tag over
     an in-process body is clean.

The gate must approach 100% precision: flagging the honest @component in-process
test (#2) would push authors back toward the O(N) per-CLI-subprocess ice-cream
cone the feature exists to remove. The trap proves the gate keys on the
TAG-vs-SPAWN cross-check, never on the body shape in isolation.

The ``main`` / ``redirect_stdout`` symbols are stand-in helpers so the corpus
parses; the gate reads structure (the marker tag + the spawn shape), not
behaviour.
"""

import io
import subprocess
import sys
from contextlib import redirect_stdout

import pytest


def main(argv):  # stand-in in-process CLI entry so the corpus parses.
    return 0


@pytest.mark.wiring_e2e
def test_install_through_real_subprocess():
    # HONEST: @wiring_e2e CLAIMS a real subprocess, and the body genuinely spawns
    # one. Tag MATCHES spawn shape -- clean.
    completed = subprocess.run(
        [sys.executable, "-m", "des", "install", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0


@pytest.mark.component
def test_install_reports_plan_in_process():
    # PRECISION NEAR-MISS: the body drives main(argv) in-process (the shape that
    # is dishonest UNDER a subprocess tag), but it is HONESTLY tagged @component.
    # Tag MATCHES spawn shape -- clean. The gate must NOT flag this.
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(["install", "--dry-run"])
    assert exit_code == 0
