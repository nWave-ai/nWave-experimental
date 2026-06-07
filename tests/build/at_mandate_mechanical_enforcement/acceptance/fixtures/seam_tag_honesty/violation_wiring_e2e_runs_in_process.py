"""GOLDEN FIXTURE (planted violation -- dishonest seam tag) -- CM-I gate.

This file is NOT a real test. It is the recall-half corpus the slice-05 gate
scans: a test tagged ``@pytest.mark.wiring_e2e`` (a CLAIM that it spawns a real
interpreter through the shared dispatch/packaging/exit seam) whose body actually
drives the CLI's ``main(argv)`` IN-PROCESS (under ``redirect_stdout``, with NO
``subprocess.run`` / real spawn). The shared seam is therefore never exercised,
yet the tag asserts it is -- the exact labelling failure of the 7 fires
(TD-5/11/28/37/41/45/46). The CM-I rule MUST flag it
(``detect(...).flagged is True``), naming the offending test
``test_install_reports_plan`` with claim tag ``wiring_e2e``.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). The ``main`` / ``redirect_stdout`` symbols are stand-in
helpers so the corpus parses; the gate reads structure (the marker tag + the
spawn shape of the body), not behaviour.
"""

import io
from contextlib import redirect_stdout


def main(argv):  # stand-in in-process CLI entry so the corpus parses.
    return 0


import pytest  # noqa: E402


@pytest.mark.wiring_e2e
def test_install_reports_plan():
    # VIOLATION: tagged @wiring_e2e (CLAIMS a real subprocess) but the body only
    # drives main(argv) in-process -- no subprocess.run, no real spawn.
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(["install", "--dry-run"])
    assert exit_code == 0
