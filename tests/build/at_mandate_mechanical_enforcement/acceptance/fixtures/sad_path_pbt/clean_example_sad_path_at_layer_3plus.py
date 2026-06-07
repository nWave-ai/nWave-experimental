"""GOLDEN FIXTURE (clean -- example-based sad path at layer 3+) -- M11 gate.

This file is NOT a real test. It is the precision-half corpus the slice-07 gate
scans: enumerated example-based sad-path tests at a layer-3+ file (the
composition supplies a synthetic ``integration`` path). This is EXACTLY what
Mandate 11 prescribes -- sad paths at layers 3+ stay example-based, one named
example per failure mode. The M11 rule MUST NOT flag it
(``detect(...).flagged is False``).

The near-miss trap: the docstring and a comment MENTION the word ``given`` and
``hypothesis`` as prose, but there is NO ``@given`` decorator and NO stateful-PBT
import -- the gate must key on STRUCTURE (decorators + module imports), not on
textual occurrences of PBT vocabulary. A gate that flags this clean corpus on a
textual match is over-firing (a false positive blocks a commit).
"""

import subprocess


def test_install_fails_when_disk_full():
    # Example-based sad path: one enumerated failure example. The word
    # "given" here is prose, not a hypothesis decorator.
    result = subprocess.run(["true"], capture_output=True, text=True, check=False)
    assert result.returncode == 0


def test_install_fails_when_permission_denied():
    # A second enumerated sad-path example -- still no PBT machinery.
    result = subprocess.run(["true"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
