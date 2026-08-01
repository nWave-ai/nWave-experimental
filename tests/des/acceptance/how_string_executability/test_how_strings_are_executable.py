"""Every HOW a gate prints must prescribe an invocation the CLI accepts (GDP-4).

CONTRACT_SHAPE: observable-outcome
Outcome anchor: DISCUSS Elevator Pitch -- a refused gate hands back a repair
command that works when pasted, not one that looks like guidance and dead-ends.

The audit that motivated these tests found the defect is almost never a MISSING
HOW: it is a HOW that exists and that nobody has ever run. So these tests do not
count strings -- they EXECUTE every ``des`` invocation embedded in a HOW payload
and ask whether the CLI's parser accepts it. The population also includes
script invocations (``python3 scripts/...``) -- the norm for HOWs outside
``des`` (hooks, validation scripts) -- verified by the same execute-and-key-on-
argparse-vocabulary discipline.
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

#: Every root the audit walks, by name (used only for reporting/messages).
AUDITED_ROOTS: dict[str, Path] = {
    "src/des": REPO_ROOT / "src" / "des",
    "scripts": REPO_ROOT / "scripts",
}

#: Modules whose HOW payloads anchor the audited population. If the population
#: is derived purely from the SHAPE of the code it audits, a rename of the
#: ``how`` key turns every test here green by finding nothing -- the checker
#: would be exempt from the very class it checks. These anchors close on a
#: SECOND AXIS: named modules known to route their repair through a command
#: (``des`` or a script), asserted independently of how many the walk happens
#: to return. Paths are REPO_ROOT-relative so both audited roots share one list.
ANCHOR_MODULES = (
    "src/des/cli/commit_slice.py",
    "src/des/cli/verify_slice_commit_completeness.py",
    "src/des/cli/record_examine_verdict.py",
    "src/des/application/deliver_loop_projection.py",
    "scripts/validation/validate_mikado_tree_coherence.py",
)

#: Floor for the audited population, well under the count observed when these
#: tests were re-measured after widening the audit to `src/des` + `scripts`
#: (94). A collapse below it means the walk stopped seeing the payloads, not
#: that the tree got tidier.
POPULATION_FLOOR = 60


@pytest.fixture(scope="module")
def audited() -> list:
    collected: list = []
    for root in AUDITED_ROOTS.values():
        collected.extend(collect_invocations(root))
    return collected


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
        module=REPO_ROOT / "src" / "des" / "forged.py",
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
        module=REPO_ROOT / "src" / "des" / "forged.py",
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
        module=REPO_ROOT / "src" / "des" / "forged.py",
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

    seen = {str(i.module.relative_to(REPO_ROOT)) for i in audited}
    missing = [anchor for anchor in ANCHOR_MODULES if anchor not in seen]
    assert not missing, (
        f"modules known to route repair through a command contributed no "
        f"invocation to the audit: {missing}"
    )


def test_a_side_effecting_installer_script_is_never_executed_for_real() -> None:
    """Safety: a script whose flagless default performs a real action must
    never be run for shape-verification -- it must degrade to could-not-verify.

    Discovered empirically while implementing the script-invocation audit:
    ``python scripts/install/install_nwave.py`` (the real HOW at
    ``src/des/runtime/freshness.py:81``) takes ZERO required arguments --
    unlike every ``des`` subcommand, whose required argument makes a bare
    invocation fail fast at argparse before any business logic runs -- so
    naively executing it "just to check the shape" would perform a REAL
    install on the operator's machine.
    """
    forged = invocations_in(
        "reinstall via python scripts/install/install_nwave.py",
        module=REPO_ROOT / "src" / "des" / "forged.py",
        line=1,
        key="how",
    )

    assert len(forged) == 1
    refused, unverifiable = rejections(forged, cwd=REPO_ROOT)

    assert refused == [], "a side-effecting script HOW must not be reported refused"
    assert len(unverifiable) == 1, (
        "a side-effecting installer script was execute-verified for real instead "
        "of degrading to could-not-verify"
    )
    assert "install" in unverifiable[0].reason.lower()


def test_a_how_whose_placeholder_enumerates_choices_is_not_reported_refused() -> None:
    """Negative (A): an enumerated placeholder already names a legal value.

    ``<bugfix|prefactoring|charter|...>`` is not a value the CLI is asked to
    accept literally -- it is prose enumerating the legal choices. Substituting
    the literal "PLACEHOLDER" for it (the old behaviour) manufactured an
    "invalid choice" that says nothing about the HOW's actual shape.
    """
    forged = invocations_in(
        "des dispatch --lane <bugfix|prefactoring|charter|...> --project-id X",
        module=REPO_ROOT / "src" / "des" / "forged.py",
        line=1,
        key="how",
    )

    refused, _ = rejections(forged, cwd=REPO_ROOT)

    assert refused == [], (
        "a HOW whose placeholder enumerates its own legal choices was reported "
        f"refused: {refused}"
    )


def test_a_how_that_invokes_a_script_is_execute_verified() -> None:
    """Positive (B1): a script invocation is COLLECTED and execute-verified.

    ``python3 scripts/...`` is the norm for HOWs outside ``des`` (hooks,
    validation scripts). Before the fix ``_INVOCATION_RE`` only matched
    ``\\bdes\\s+<subcommand>``, so this whole population was invisible.
    """
    forged = invocations_in(
        "run python3 scripts/hooks/check_end_of_file.py --fix FILE",
        module=REPO_ROOT / "scripts" / "forged.py",
        line=1,
        key="how",
    )

    assert len(forged) == 1, (
        "a script invocation embedded in a HOW string was not collected at all"
    )
    assert forged[0].kind == "script"

    refused, unverifiable = rejections(forged, cwd=REPO_ROOT)

    assert refused == [], f"a working script HOW was reported refused: {refused}"
    assert unverifiable == [], (
        f"a working script HOW was reported could-not-verify: {unverifiable}"
    )


def test_a_how_naming_a_script_that_does_not_exist_is_rejected() -> None:
    """Negative (B1 twin): a HOW routing to a script that was never shipped.

    The script-side twin of
    ``test_a_how_naming_a_subcommand_that_does_not_exist_is_rejected``.
    """
    forged = invocations_in(
        "run python3 scripts/validation/no_such_gate.py --file X",
        module=REPO_ROOT / "scripts" / "forged.py",
        line=1,
        key="how",
    )

    refused, _ = rejections(forged, cwd=REPO_ROOT)

    assert len(refused) == 1, (
        "a HOW naming a script that does not exist on disk was not reported refused"
    )
    assert "no such script" in refused[0].cli_said


def test_a_helper_built_how_is_visible_to_the_audit(tmp_path: Path) -> None:
    """Positive (B2): a HOW built by a helper function must not be invisible.

    ``how=_build_how(path)`` is a ``Call``, not a literal -- before the fix
    ``_literal_of`` returned ``None`` for it and the whole payload vanished
    from the audit. ``validate_mikado_tree_coherence.py`` uses exactly this
    shape (``how=_how_explain(doc_path, node_id)``) 17 times and the audit saw
    ZERO of them.
    """
    module = tmp_path / "forged_helper_built_how.py"
    module.write_text(
        "def _build_how(path):\n"
        '    return f"run python3 scripts/hooks/check_end_of_file.py --fix {path}"\n'
        "\n"
        "\n"
        "def make_finding(path):\n"
        "    return dict(\n"
        '        what="a file is missing its trailing newline",\n'
        '        why="CI rejects it",\n'
        "        how=_build_how(path),\n"
        "    )\n",
        encoding="utf-8",
    )

    collected = collect_invocations(tmp_path)

    assert collected, (
        "a HOW built by a helper function (`how=_build_how(path)`) was not "
        "collected -- the audit is still blind to helper-built HOWs"
    )
    assert any(i.kind == "script" for i in collected), (
        f"the helper-built HOW's script invocation was not recognised: {collected}"
    )
