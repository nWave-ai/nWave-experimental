"""Domain types for f-spine-runs-tests-not-git-hooks (Mandate-12 criterion 1).

The Gherkin nouns of this feature, expressed once via the type system. Step
methods consume these typed values (criterion 2); no raw ``str`` where a domain
enum exists. The vocabulary is the slice-AT execution domain: the verdict the
spine slice-AT gate projects onto its exit code, the colour of a slice's ATs
(green vs RED), and the kind of target runner the gate resolves.

These mirror the production ``GateVerdict`` SSOT (``src/des/domain/gate_outcome.py``)
projected onto the slice-AT gate's process exit code per DDD-6: slice AT green ->
PASS (0); slice AT RED -> FAIL (1); runner unrecognized/absent -> INDETERMINATE
(!= {0,1}); no real slice AT -> NOT_APPLICABLE (0). The AT set drives the REAL
``des run-slice-ats`` executor (Layer-3 subprocess) and reads its exit code +
stdout JSON line -- never a test-fabricated oracle.
"""

from __future__ import annotations

from enum import Enum


class SliceVerdict(Enum):
    """The verdict the spine slice-AT gate projects onto its process exit code.

    The five values map 1:1 onto the production ``GateVerdict`` SSOT (DDD-6: no
    sixth verdict). The slice-AT gate's exit-code contract:

    * ``PASS``           -> exit 0   (the entering slice's ATs RAN and were green)
    * ``FAIL``           -> exit 1   (the entering slice's ATs RAN and a RED one failed)
    * ``INDETERMINATE``  -> exit != {0,1} (runner unrecognized/absent; degrade-LOUD)
    * ``NOT_APPLICABLE`` -> exit 0   (no real ``.feature`` for the entering slice)

    ``UNVERIFIED`` is in the SSOT but not produced by this gate; carried for the
    arch-test that asserts the closed verdict set (AT-A3).
    """

    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNVERIFIED = "UNVERIFIED"


class SliceAtColour(Enum):
    """Whether the entering slice's planted acceptance test is green or RED.

    The slice executor's whole reason for being is that a RED slice AT must
    VETO (the acceleration that genuinely RUNS, not collect-only). The colour
    is the precondition the gate is driven against.
    """

    GREEN = "green"
    RED = "red"


class TargetRunner(Enum):
    """The kind of test runner a target project resolves to via TestRunnerPort.

    ``PYTEST`` is the nWave-dev dogfood runner (one row among equals). ``VITEST``
    / ``GO_TEST`` / ``CARGO_TEST`` are the other recognized runners. ``ABSENT``
    is a target with NO recognized lockfile -> the port returns ``Indeterminate``
    (degrade-LOUD, never a silent pytest fallback) -> the gate maps it to
    INDETERMINATE.
    """

    PYTEST = "pytest"
    VITEST = "vitest"
    GO_TEST = "go-test"
    CARGO_TEST = "cargo-test"
    ABSENT = "absent"


class CommitStage(Enum):
    """A git hook stage in ``.pre-commit-config.yaml`` (slice-03 vocabulary)."""

    PRE_COMMIT = "pre-commit"
    PRE_PUSH = "pre-push"
