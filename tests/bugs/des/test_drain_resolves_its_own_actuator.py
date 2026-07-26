# @feature-drain-resolves-its-own-actuator
"""Regression AT -- `des refactor` resolves ITS OWN installed actuator.

RCA (dispatch, confirmed): `des refactor --pile <f> --agent-cmd 'scripts/
refactor_agent.py {prompt}'` drains ZERO items on any project other than
nWave-dev itself. Two-part root cause:

1. `ShellAgentInvocationAdapter.probe()` (`src/des/adapters/driven/refactor/
   shell_agent_invocation_adapter.py`) does `shutil.which(shlex.split(
   agent_cmd)[0])` -- NO shell, so no `~`/`$HOME` expansion, and a
   repo-relative path resolves against the TARGET repo's cwd, never the
   actuator's real location.
2. The installer places the actuator at `<claude_config_dir>/scripts/
   refactor_agent.py` (`scripts/install/plugins/utilities_plugin.py`), NOT
   inside the consumer repo -- so the documented relative path can never
   resolve there regardless of (1).

The fix: `--agent-cmd` becomes OPTIONAL. In its absence, the drain resolves
the installed actuator itself, reusing the EXISTING seam
`des.runtime.interpreter._des_root()` -- `_des_root()`'s PARENT directory is
the repo root (dev checkout) or the config dir (installed layout) either
way, so `<that>/scripts/refactor_agent.py` is the actuator in BOTH layouts,
for ANY config-dir NAME (never a `parent.name == ".claude"` string match --
a known defect elsewhere in this tree this fix must not repeat).

Charter: docs/product/expectations/drain-resolves-its-own-actuator/
a-maintainer-drains-their-own-project-without-configuring-the-tool.md
(EXP-drain-resolves-its-own-actuator-1)

## Driving surface -- subprocess (Layer 1), justified beyond the single
## walking-skeleton default (Mandate 2's explicit-justification carve-out)

Every "omit --agent-cmd" direction below forks a REAL `python -m
des.cli.__main__ refactor` subprocess with `PYTHONPATH` pointed at a
FRESH COPY of the CURRENT `des` package tree, rooted under a synthetic
`tmp_path` layout (never a real `~/.claude*` install -- that would mutate
the operator's machine, which is out of bounds). This is the slice's own
value: actuator resolution IS install-path integration behaviour, and it is
governed by `Path(__file__).resolve()` inside `des.runtime.interpreter`,
which follows symlinks back to wherever `des` genuinely loaded from. An
in-process monkeypatch of `_des_root` would only intercept a LAZY,
same-module call and would silently miss a top-level `from ... import
_des_root` alias bound at a different module's collection time --
exactly the kind of import-order fragility a resolution regression test
must not carry. A real subprocess with an overridden `PYTHONPATH`
sidesteps that risk entirely: whatever module the eventual fix calls
`_des_root()` from, the resolved value is genuinely anchored to the fake
tree, because that IS where the running interpreter loaded `des` from.
Verified empirically that `PYTHONPATH` shadows the project's own editable
install correctly under this repo's `.venv`.

Direction 4 (explicit `--agent-cmd` preserved) needs no fake tree at all --
it drives the already-established in-process `RefactorSwarmComposition.
call_refactor_main_in_process` surface (Layer 2 composition, `tests/des/
refactor/composition.py`), proving the new default-resolution path is never
even consulted when the flag is present.

## RED-for-right-reason

At HEAD, `--agent-cmd` is `required=True` in `src/des/cli/refactor.py`'s
argparse contract -- every "omit --agent-cmd" subprocess below currently
exits 2 with argparse's own "the following arguments are required:
--agent-cmd" usage error on stderr. Every assertion below is a semantic
check on the subprocess's exit code / stdout+stderr content (never a
collection or import error) -- so today's failures show a genuine, readable
diagnostic naming exactly what is still missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from des.runtime import interpreter
from tests.des.refactor.composition import RefactorSwarmComposition
from tests.des.refactor.domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance

_FAKE_ACTUATOR_SCRIPT = (
    "#!/usr/bin/env python3\n"
    "# Stand-in for the real refactor_agent.py -- always self-reports\n"
    "# REFACTOR_SAFE regardless of how it was invoked, so this AT proves\n"
    "# RESOLUTION, not the real actuator's own agent-dispatch behaviour.\n"
    "print('REFACTOR_SAFE')\n"
)

_REMEDIATION_HINT = "nwave-ai install"


# --- fixture builders (synthetic tmp_path layouts, NEVER a real install) ---


def _build_fake_installed_root(
    tmp_path: Path, *, config_dir_name: str, include_actuator: bool
) -> Path:
    """Synthetic installed-shape tree: `<fake_root>/lib/python/des/...` (a
    FRESH COPY of the currently-running `des` package -- so this always
    tracks whatever fix lands in `src/des`, never a frozen snapshot) plus
    `<fake_root>/scripts/refactor_agent.py` (present or absent per
    ``include_actuator``). Returns the `lib/python` dir to point
    `PYTHONPATH` at.
    """
    fake_root = tmp_path / config_dir_name
    lib_python = fake_root / "lib" / "python"
    real_src = Path(interpreter._des_root())
    shutil.copytree(
        real_src / "des",
        lib_python / "des",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    scripts_dir = fake_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    if include_actuator:
        actuator_path = scripts_dir / "refactor_agent.py"
        actuator_path.write_text(_FAKE_ACTUATOR_SCRIPT, encoding="utf-8")
        actuator_path.chmod(0o755)
    return lib_python


def _run_refactor_subprocess_without_agent_cmd(
    composition: RefactorSwarmComposition, *, pythonpath: str
) -> subprocess.CompletedProcess[str]:
    """Fork the REAL `des refactor` CLI with NO `--agent-cmd` token at all,
    `PYTHONPATH` overridden to shadow the project's own editable `des`
    install with the fake tree under test."""
    env = {**os.environ, "PYTHONPATH": pythonpath}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "des.cli.__main__",
            "refactor",
            "--pile",
            str(composition.pile_path),
        ],
        cwd=composition.project_root,
        env=env,
        capture_output=True,
        text=True,
    )


def _new_composition(tmp_path: Path, dir_name: str) -> RefactorSwarmComposition:
    project_root = tmp_path / dir_name
    project_root.mkdir()
    composition = RefactorSwarmComposition(project_root)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    return composition


# --- Direction 1 + 2: installed layout resolves, under ANY config-dir name -


@pytest.mark.parametrize(
    "config_dir_name",
    [
        pytest.param(".claude", id="default-profile-name"),
        pytest.param(".claude-alt3", id="alternative-profile-name"),
    ],
)
def test_drain_resolves_installed_actuator_without_agent_cmd_flag(
    tmp_path, config_dir_name
):
    """Given a pile with one item and an INSTALLED-shape actuator tree (no
    `--agent-cmd` passed), When `des refactor` runs, Then it resolves the
    actuator itself and completes the drain -- it must NOT refuse with a
    probe failure, and this holds regardless of the config directory's NAME
    (a maintainer sharing one nWave install via `CLAUDE_CONFIG_DIR` under a
    non-default profile name gets the identical working behaviour).

    CONTRACT_SHAPE: bounded-change
    """
    lib_python = _build_fake_installed_root(
        tmp_path, config_dir_name=config_dir_name, include_actuator=True
    )
    composition = _new_composition(tmp_path, f"repo-{config_dir_name.lstrip('.')}")
    composition.seed_pile_item(item_id="TD-001")

    result = _run_refactor_subprocess_without_agent_cmd(
        composition, pythonpath=str(lib_python)
    )

    assert result.returncode == 0, (
        f"omitting --agent-cmd with a real installed actuator on disk "
        f"(config dir {config_dir_name!r}) must still drain the item; got "
        f"returncode={result.returncode}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}"
    )
    assert not composition.pile_contains("TD-001"), (
        "TD-001 must be drained (removed from techdebt.md) once the "
        "self-resolved actuator runs -- a probe failure would leave it "
        "untouched"
    )
    assert composition.paid_contains("TD-001"), (
        "TD-001 must be recorded in paidtechdebt.md once the self-resolved "
        "actuator completes the drain"
    )


# --- Direction 3: actuator absent -> loud, self-explaining refusal ---------


def test_drain_refuses_loudly_naming_searched_path_and_remediation_when_actuator_absent(
    tmp_path,
):
    """Given NO `--agent-cmd` and an installed-shape tree whose actuator
    script is MISSING, When `des refactor` runs, Then it refuses LOUDLY:
    non-zero exit, a message naming the exact path it searched, and a
    message pointing at the remediation (`nwave-ai install`) -- it must
    NEVER silently no-op, and it must never read the same as "the pile was
    empty" (the exact regression this fix must not reintroduce, per the
    charter's own negative oracle).

    CONTRACT_SHAPE: bounded-change
    """
    config_dir_name = "fake-claude-no-actuator"
    lib_python = _build_fake_installed_root(
        tmp_path, config_dir_name=config_dir_name, include_actuator=False
    )
    fake_root = tmp_path / config_dir_name
    composition = _new_composition(tmp_path, "repo-actuator-absent")
    composition.seed_pile_item(item_id="TD-003")

    result = _run_refactor_subprocess_without_agent_cmd(
        composition, pythonpath=str(lib_python)
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "a missing actuator must refuse (non-zero exit), never silently "
        f"proceed; got returncode={result.returncode}, output={combined!r}"
    )
    assert "arguments are required" not in combined.lower(), (
        "the refusal must not be the argparse-level '--agent-cmd is "
        "required' usage error -- the flag must be OPTIONAL, refused only "
        f"because the actuator genuinely could not be found; got: "
        f"{combined!r}"
    )
    searched_path = str(fake_root / "scripts" / "refactor_agent.py")
    assert searched_path in combined or "refactor_agent.py" in combined, (
        "the refusal must NAME the exact path it searched for the "
        f"actuator (WHAT/WHY/HOW); got: {combined!r}"
    )
    assert _REMEDIATION_HINT in combined, (
        f"the refusal must point at the remediation ({_REMEDIATION_HINT!r}) "
        f"so the maintainer has a concrete next step; got: {combined!r}"
    )
    assert "is empty, nothing to drain" not in combined, (
        "a missing-actuator refusal must be unmistakably distinguishable "
        f"from the genuinely-empty-pile message; got: {combined!r}"
    )
    assert composition.pile_contains("TD-003"), (
        "TD-003 must remain untouched in techdebt.md -- a missing-actuator "
        "refusal must never drain the item as a side effect"
    )
    assert not composition.paid_contains("TD-003"), (
        "TD-003 must NOT be recorded as drained when the actuator never resolved"
    )
    assert "refactor-TD-003" not in composition.worktree_list(), (
        "no worktree may be left behind for TD-003 -- the refusal must "
        "fire BEFORE any worktree is created, exactly like every other "
        "startup-probe refusal in this drain loop"
    )


# --- Direction 4: explicit --agent-cmd is untouched, byte-identical --------


def test_explicit_agent_cmd_flag_is_preserved_byte_identical(tmp_path):
    """Given an explicit `--agent-cmd` naming a real, working command, When
    `des refactor` runs, Then it behaves exactly as it does today -- the new
    default-resolution path applies ONLY in `--agent-cmd`'s ABSENCE, and
    must never be consulted or interfere when the flag is present.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = _new_composition(tmp_path, "repo-explicit-agent-cmd")
    composition.seed_pile_item(item_id="TD-004")
    explicit_cmd = composition.agent_cmd_emitting_verdict(
        EntryGateAgentVerdict.REFACTOR_SAFE
    )

    exit_code = composition.call_refactor_main_in_process(agent_cmd=explicit_cmd)

    assert exit_code == 0, (
        "an explicit --agent-cmd must drain the item exactly as before "
        f"this fix; got exit_code={exit_code}"
    )
    assert not composition.pile_contains("TD-004"), (
        "TD-004 must still be removed from techdebt.md via the explicit "
        "--agent-cmd path, unaffected by the new default-resolution logic"
    )
    assert composition.paid_contains("TD-004"), (
        "TD-004 must still be recorded as drained via the explicit --agent-cmd path"
    )
