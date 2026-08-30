"""The difference between the two campaign arms is COMPUTED, not maintained.

The comment above `control_setup_steps` has always said the arms "must differ
only in what their setup installs". Nothing computed that, and nothing failed
when it stopped being true -- a fourth step added to either list would have left
every gate in this repo green while the campaign quietly stopped measuring nWave
and kept computing ratios anyway.

`preflight.arm_footprint_problems` is that computation. The declared set has
exactly three members and no fourth: the git identity label, the examiner
fixture's ephemeral port, and the two treatment steps. Everything else must be
byte-equal across the arms.

The falsifier is the point of this file: each test below injects ONE undeclared
difference and asserts the check refuses; `test_the_real_arms_pass` is the other
half -- with the difference removed, the real declared arms pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.k4 import preflight


@pytest.fixture
def venv(tmp_path: Path) -> Path:
    return tmp_path / "nwave-venv"


@pytest.fixture
def auth_profile(tmp_path: Path) -> Path:
    return tmp_path / "auth-profile"


@pytest.fixture
def arms(venv: Path, auth_profile: Path) -> tuple[list[list[str]], list[list[str]]]:
    """The REAL declared arms, from the same two functions preflight ships to
    `arms.json`. A hand-built fixture pair could pass while the shipped arms
    failed, which is the class of vacuous green this repo already paid for."""
    return (
        preflight.control_setup_steps(auth_profile),
        preflight.nwave_setup_steps(venv, auth_profile),
    )


def test_the_real_arms_pass(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    control, nwave = arms
    assert preflight.arm_footprint_problems(control, nwave, venv=venv) == []


def test_the_three_declared_points_are_really_there(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    """A check that passed because the arms were IDENTICAL would be worthless.
    The declared diff must exist for the pass above to mean anything."""
    control, nwave = arms
    assert control != nwave
    assert all(step in nwave for step in preflight.treatment_steps(venv))
    assert ["git", "config", "user.name", "K4 nwave arm"] in nwave
    assert ["git", "config", "user.email", "k4-control@nwave.invalid"] in control


def test_an_undeclared_step_on_the_nwave_arm_is_refused(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    control, nwave = arms
    tainted = [*nwave, ["git", "config", "core.hooksPath", ".githooks"]]
    problems = preflight.arm_footprint_problems(control, tainted, venv=venv)
    assert problems, "an extra step on the treatment arm must be a refusal"
    assert any("core.hooksPath" in problem for problem in problems)
    # ...and removing it makes it pass again. Both directions, one test.
    assert preflight.arm_footprint_problems(control, nwave, venv=venv) == []


def test_an_undeclared_step_on_the_control_arm_is_refused(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    control, nwave = arms
    tainted = [*control, ["pip", "install", "something-only-the-control-gets"]]
    problems = preflight.arm_footprint_problems(tainted, nwave, venv=venv)
    assert any("something-only-the-control-gets" in problem for problem in problems)


def test_a_changed_shared_step_is_refused(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    """The subtlest breach: same STEP COUNT, one argument different. A check
    that compared lengths would call this pair identical."""
    control, nwave = arms
    tainted = [
        [*step, "--depth", "1"] if step[:2] == ["git", "clone"] else step
        for step in nwave
    ]
    problems = preflight.arm_footprint_problems(control, tainted, venv=venv)
    assert any("--depth" in problem for problem in problems)


def test_the_treatment_going_missing_is_refused(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    """A campaign whose treatment arm never installs nWave measures nothing and
    still computes three ratios. That is a footprint breach, not a null result."""
    control, nwave = arms
    treatment = preflight.treatment_steps(venv)
    tainted = [step for step in nwave if step != treatment[0]]
    problems = preflight.arm_footprint_problems(control, tainted, venv=venv)
    assert any("does not carry the declared treatment step" in p for p in problems)


def test_the_treatment_leaking_into_the_control_is_refused(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    control, nwave = arms
    tainted = [*control, preflight.treatment_steps(venv)[0]]
    problems = preflight.arm_footprint_problems(tainted, nwave, venv=venv)
    assert any("the control arm carries the treatment step" in p for p in problems)


def test_a_foreign_git_identity_is_refused_not_masked(
    arms: tuple[list[list[str]], list[list[str]]], venv: Path
) -> None:
    """The identity VALUE is per-arm and therefore masked before comparison --
    but masked is not exempt. Run 10 of the K4 matrix saw a retry carrying the
    operator's real name; a blanket mask would have hidden that authorship leak
    behind 'this field is allowed to differ'."""
    control, nwave = arms
    tainted = [
        ["git", "config", "user.name", "Alessandro Di Gioia"]
        if step[:3] == ["git", "config", "user.name"]
        else step
        for step in nwave
    ]
    problems = preflight.arm_footprint_problems(control, tainted, venv=venv)
    assert any("Alessandro Di Gioia" in problem for problem in problems)


def test_the_fixture_ports_differing_is_NOT_a_problem(
    venv: Path, auth_profile: Path
) -> None:
    """Declared point two. `pef.free_port()` binds a fresh OS-assigned port per
    arm on purpose (run 14: a fixed port collided with every later run forever),
    so two arms built independently carry two different ports and still pass."""
    control = preflight.control_setup_steps(auth_profile)
    nwave = preflight.nwave_setup_steps(venv, auth_profile)
    ports = {
        step[-1]
        for step in control + nwave
        if len(step) == 3 and step[-1].isdigit() and step[1].endswith(".py")
    }
    assert len(ports) == 2, f"expected one distinct port per arm, saw {ports}"
    assert preflight.arm_footprint_problems(control, nwave, venv=venv) == []


def test_the_refusal_explains_what_why_and_how(
    arms: tuple[list[list[str]], list[list[str]]],
    venv: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    control, nwave = arms
    tainted = [*nwave, ["curl", "https://example.invalid"]]
    assert preflight.refuse_undeclared_arm_footprint(control, tainted, venv=venv) == 1
    message = capsys.readouterr().err
    assert "WHAT:" in message
    assert "WHY:" in message
    assert "HOW:" in message
    assert "treatment_steps" in message, "the HOW must name the producing surface"
    assert preflight.refuse_undeclared_arm_footprint(control, nwave, venv=venv) == 0
