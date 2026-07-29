"""Every HOW a gate prints must prescribe an invocation the CLI accepts (GDP-4).

CONTRACT_SHAPE: observable-outcome
Outcome anchor: DISCUSS Elevator Pitch -- a refused gate hands back a repair
command that works when pasted, not one that looks like guidance and dead-ends.

The audit that motivated these tests found the defect is almost never a MISSING
HOW: it is a HOW that exists and that nobody has ever run. So these tests do not
count strings -- they EXECUTE every ``des`` invocation embedded in a HOW payload
and ask whether the CLI's parser accepts it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.how_executability import (
    HOW_KEYS,
    collect_invocations,
    invocations_in,
    rejections,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPO_ROOT / "src" / "des"

#: Modules whose HOW payloads anchor the audited population. If the population
#: is derived purely from the SHAPE of the code it audits, a rename of the
#: ``how`` key turns every test here green by finding nothing -- the checker
#: would be exempt from the very class it checks. These anchors close on a
#: SECOND AXIS: named modules known to route their repair through a `des`
#: command, asserted independently of how many the walk happens to return.
ANCHOR_MODULES = (
    "cli/commit_slice.py",
    "cli/verify_slice_commit_completeness.py",
    "cli/record_examine_verdict.py",
    "application/deliver_loop_projection.py",
)

#: Floor for the audited population, well under the count observed when these
#: tests were written (42). A collapse below it means the walk stopped seeing
#: the payloads, not that the tree got tidier.
POPULATION_FLOOR = 25


@pytest.fixture(scope="module")
def audited() -> list:
    return collect_invocations(SOURCE_ROOT)


def test_every_des_invocation_a_how_prescribes_is_accepted_by_the_cli(audited) -> None:
    """The headline property, verified by RUNNING each prescribed invocation."""
    refused, _ = rejections(audited, cwd=REPO_ROOT)

    detail = "\n".join(
        f"  {r.invocation.module.relative_to(REPO_ROOT)}:{r.invocation.line}\n"
        f"    HOW prescribes : {r.invocation.rendered}\n"
        f"    the CLI answers: {r.cli_said}"
        for r in refused
    )
    assert not refused, (
        f"{len(refused)} of {len(audited)} HOW-prescribed invocations are refused by "
        f"the CLI when executed. A consumer who pastes one gets an argument error, "
        f"not a repair:\n{detail}"
    )


def test_a_how_naming_a_flag_the_cli_rejects_is_never_reported_clean() -> None:
    """Negative: the audit must fail a HOW whose flag the producing tool lacks."""
    forged = invocations_in(
        "add the row via des feature-delta-doctor --no-such-flag <id>",
        module=SOURCE_ROOT / "forged.py",
        line=1,
        key="how",
    )

    refused, _ = rejections(forged, cwd=REPO_ROOT)

    assert len(refused) == 1, (
        "a HOW naming a flag the producing tool does not accept was reported clean; "
        "the audit is counting strings instead of executing them"
    )
    assert "--no-such-flag" in refused[0].cli_said


def test_a_how_naming_a_subcommand_that_does_not_exist_is_rejected() -> None:
    """Negative: a HOW routing to a tool that was never shipped must not pass."""
    forged = invocations_in(
        "re-run des verify-nothing-at-all to repair",
        module=SOURCE_ROOT / "forged.py",
        line=1,
        key="how",
    )

    refused, _ = rejections(forged, cwd=REPO_ROOT)

    assert len(refused) == 1
    assert "invalid choice" in refused[0].cli_said


def test_a_subcommand_whose_help_exits_nonzero_is_not_reported_broken() -> None:
    """Negative: the oracle keys on the PROPERTY, never on one response's form.

    ``des feature-delta-schema`` hand-rolls its usage and exits 1 on ``--help``.
    An oracle that treated a non-zero ``--help`` as "no such subcommand" would
    report this working HOW broken -- the exact false positive that keying on
    argparse's rejection vocabulary avoids.
    """
    forged = invocations_in(
        "emit the canonical heading with des feature-delta-schema inject --wave design",
        module=SOURCE_ROOT / "forged.py",
        line=1,
        key="how",
    )

    refused, _ = rejections(forged, cwd=REPO_ROOT)

    assert refused == [], (
        "a HOW prescribing a working invocation was reported broken because its "
        f"--help exits non-zero: {refused}"
    )


def test_a_how_that_could_not_be_verified_is_never_folded_into_the_pass(
    audited,
) -> None:
    """The third state reaches the aggregate instead of passing silently (GDP-6/8).

    ``des blast-radius --repo {repo} {scope}`` renders its scope only at
    runtime. Executing it with a stand-in proves nothing, so it must surface as
    could-not-verify -- not as a refusal (a false alarm), and not as a pass (the
    silent-wrong).
    """
    refused, unverifiable = rejections(audited, cwd=REPO_ROOT)

    assert unverifiable, (
        "no HOW was reported could-not-verify, yet the tree carries HOWs whose "
        "arguments are interpolated at render time -- the third state has "
        "collapsed into the pass"
    )
    unverified = {i.invocation.rendered for i in unverifiable}
    assert any("blast-radius" in rendered for rendered in unverified), (
        f"the interpolated-scope blast-radius HOW is not among the "
        f"could-not-verify population: {sorted(unverified)}"
    )
    assert unverified.isdisjoint({r.invocation.rendered for r in refused}), (
        "an invocation is reported both refused and could-not-verify; the "
        "three states must partition the population"
    )


def test_the_audited_population_never_collapses_to_a_handful(audited) -> None:
    """Guard against green-by-absence: the walk must still be finding payloads."""
    assert len(audited) >= POPULATION_FLOOR, (
        f"only {len(audited)} HOW-prescribed invocations found, below the "
        f"{POPULATION_FLOOR} floor -- the walk has stopped seeing the payloads "
        f"(a renamed key among {sorted(HOW_KEYS)}?), so every other test here is "
        f"green because it audited nothing"
    )

    seen = {str(i.module.relative_to(SOURCE_ROOT)) for i in audited}
    missing = [anchor for anchor in ANCHOR_MODULES if anchor not in seen]
    assert not missing, (
        f"modules known to route repair through a des command contributed no "
        f"invocation to the audit: {missing}"
    )
