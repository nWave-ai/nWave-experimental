"""pytest-bdd binding for f-spine-runs-tests-not-git-hooks slice-01.

THE ACCELERATION + the genuine RUN. The SUT is the NEW in-tree executor
``des.cli.run_slice_ats`` (CRITICAL-1/CRITICAL-2): resolve()->scope->RUN->verdict.
Step bodies delegate to the shared composition root (composition.py); no business
logic in step bodies (Mandate-12). HERMETIC: drives the executor via
``python -m des.cli.run_slice_ats`` ARGS over a tmp workspace -- no developer
home-directory read anywhere (the acceptance-hermeticity guard forbids it).

Driving surface (Mandate-13, Layer-3 subprocess): ``python -m des.cli.run_slice_ats``
with ``--repo-root`` / ``--entering-slice``. observable = exit code (PASS=0 /
FAIL=1) + the one JSON line on stdout.

S1 (step-text uniqueness): the shared verbs ("a developer commits the entering
slice", "the spine slice-AT gate runs") live ONCE in conftest. THIS module
declares only the slice-01-unique verbs (green/broken planted AT, pass/refuse/
ran-only). They do not recur in slice-02's module (whose vocabulary is the runner
resolution + NA verbs) -- no cross-module shadow.

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-01's DELIVER ships
the ``des.cli.run_slice_ats`` executor + ``RunnerAdapter.run()`` + the
``pytest_runner`` adapter + the ``run-slice-ats`` subcommand row. At HEAD the
executor module is absent, so the subprocess exits non-zero (NEITHER PASS=0 nor
FAIL=1) -> semantic AssertionErrors against the expected verdict.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then

from .composition import SliceRunComposition, spine  # noqa: F401
from .domain_types import SliceAtColour, SliceVerdict


scenarios("../slice-01-spine-runs-the-slice-ats.feature")


# --- Given (slice-01 unique) -----------------------------------------------
# NOTE: "the entering slice has a green acceptance test" is the SHARED SSOT verb
# (declared once in conftest -- used by slice-01 + slice-02). This module declares
# only the slice-01-unique "broken acceptance test" verb (no cross-module shadow).


@given("the entering slice has a broken acceptance test")
def given_broken_slice_at(spine: SliceRunComposition) -> None:
    spine.given_planted_slice_at(SliceAtColour.RED)


# --- Then (slice-01 unique) ------------------------------------------------
# NOTE: "the spine slice-AT gate passes the commit" is the SHARED SSOT Then
# (declared once in conftest -- used by slice-01 + slice-02). This module declares
# only the slice-01-unique "refuses the commit" + "ran only ..." verbs.


@then("the spine slice-AT gate refuses the commit")
def then_gate_refuses(spine: SliceRunComposition) -> None:
    spine.then_verdict_is(SliceVerdict.FAIL)


@then("the spine slice-AT gate ran only the entering slice's tests")
def then_ran_only_entering_slice(spine: SliceRunComposition) -> None:
    spine.then_ran_only_entering_slice()
