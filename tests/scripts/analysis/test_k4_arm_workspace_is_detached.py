"""K4 arm workspaces must land delivery in the SAME directory acceptance and
blind review later inspect.

Observed defect: `git clone <sut> .` leaves HEAD attached to the SUT's
default branch. `nw-auto`'s own worktree-ownership rule
(`nWave/skills/nw-auto/SKILL.md`) treats an attached, non-isolated checkout as
one it must abandon in favour of a NEW detached worktree it creates
elsewhere -- so the real delivery lands outside `pair-dir/{control,nwave}`,
and `run_acceptance.py` / blind review, which only ever inspect
`pair-dir/{arm}`, see the unchanged clone instead.

RED on base: the declared git steps of both arms' setup leave HEAD attached.
GREEN once setup detaches HEAD in place, which is the OTHER branch of Auto's
own rule ("if the current checkout is already an isolated detached worktree,
keep using it") -- Auto then reuses this directory instead of relocating.

This test executes the real git steps against a local throwaway SUT (no
network); the auth-seeding and `nwave-ai install` steps are out of scope for
the property under test (which directory HEAD ends up attached to) and need
infrastructure this test does not have, so they are not executed here.

Run: uv run pytest -q tests/scripts/analysis/test_k4_arm_workspace_is_detached.py
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.analysis.k4 import preflight


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _head_sha(repo) -> str:
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def _make_local_sut(tmp_path):
    """A tiny local repo standing in for the real SUT -- `git clone` accepts
    a local path exactly as it accepts a URL, so this proves the same
    behaviour without touching the network. Returns (repo path, HEAD sha):
    the pinned-revision checkout step (`preflight._SUT_PINNED_REV`) needs a
    commit that actually exists in THIS throwaway repo, never the real
    SUT's pin."""
    sut = tmp_path / "sut"
    sut.mkdir()
    _git("init", "-q", "-b", "master", cwd=sut)
    _git("config", "user.email", "k4@example.test", cwd=sut)
    _git("config", "user.name", "k4", cwd=sut)
    (sut / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=sut)
    _git("commit", "-q", "-m", "seed", cwd=sut)
    return sut, _head_sha(sut)


def _is_detached(workspace) -> bool:
    """`git symbolic-ref` resolves HEAD to a branch and fails exactly when it
    cannot -- i.e. exactly when HEAD is detached. Same property Auto's own
    worktree-ownership rule keys on."""
    done = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return done.returncode != 0


def _run_git_steps(steps, workspace) -> None:
    for step in steps:
        if step[0] != "git":
            continue
        subprocess.run(step, cwd=workspace, check=True, capture_output=True, text=True)


def _make_control_steps(venv, auth):
    return preflight.control_setup_steps(auth)


def _make_nwave_steps(venv, auth):
    return preflight.nwave_setup_steps(venv, auth)


@pytest.mark.parametrize(
    "steps_factory",
    [
        pytest.param(_make_control_steps, id="control"),
        pytest.param(_make_nwave_steps, id="nwave"),
    ],
)
def test_arm_workspace_is_detached_after_setup(tmp_path, monkeypatch, steps_factory):
    sut, sut_head = _make_local_sut(tmp_path)
    monkeypatch.setattr(preflight, "_SUT", str(sut))
    monkeypatch.setattr(preflight, "_SUT_PINNED_REV", sut_head)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    steps = steps_factory(tmp_path / "venv-unused", tmp_path / "auth-unused")
    _run_git_steps(steps, workspace)

    assert _is_detached(workspace), (
        "HEAD is still attached to a branch after setup: nw-auto's "
        "worktree-ownership rule treats this as a shared/non-isolated "
        "checkout and creates ANOTHER detached worktree elsewhere for "
        "delivery, so acceptance and blind review -- which only ever "
        "inspect this workspace -- would see the unchanged clone"
    )


def test_both_arms_detach_the_same_way(tmp_path):
    """No treatment-only locator convention: the git steps that establish
    workspace identity must be identical across arms, not merely both
    'detached' by coincidentally different means."""
    control_git = [
        s for s in preflight.control_setup_steps(tmp_path / "auth") if s[0] == "git"
    ]
    nwave_git = [
        s
        for s in preflight.nwave_setup_steps(tmp_path / "venv", tmp_path / "auth")
        if s[0] == "git"
    ]

    assert control_git == nwave_git


def test_delivery_fixture_step_is_shared_and_credential_free(tmp_path):
    """Both delivery arms prepare the SAME runtime without an examiner key."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    control_step = pef.delivery_setup_step()
    nwave_step = pef.delivery_setup_step()

    assert control_step == nwave_step
    assert control_step[-1] == "--delivery-only"

    control_steps = preflight.control_setup_steps(tmp_path / "auth")
    nwave_steps = preflight.nwave_setup_steps(tmp_path / "venv", tmp_path / "auth")

    control_git_positions = [i for i, s in enumerate(control_steps) if s[0] == "git"]
    nwave_git_positions = [i for i, s in enumerate(nwave_steps) if s[0] == "git"]
    control_fixture_index = control_steps.index(control_step)
    nwave_fixture_index = nwave_steps.index(nwave_step)

    assert control_fixture_index > control_git_positions[-1], (
        "control arm must prepare the fixture only after its clone/detach git steps"
    )
    assert nwave_fixture_index > nwave_git_positions[-1], (
        "nwave arm must prepare the fixture only after its clone/detach git steps"
    )
    assert (control_fixture_index - control_git_positions[-1]) == (
        nwave_fixture_index - nwave_git_positions[-1]
    ), (
        "the fixture step must sit at the same lifecycle position relative to "
        "clone/detach in both arms"
    )
