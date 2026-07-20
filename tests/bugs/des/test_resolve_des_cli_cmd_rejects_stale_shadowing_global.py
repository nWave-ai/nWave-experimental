"""Regression: `resolve_des_cli_cmd` must resolve the ACTIVE venv's own
`des` console-script, never a stale-but-`--help`-passing global `des`
shadowing it earlier on PATH.

Charter: docs/product/expectations/bugfix-shutil-which-des-fragility/
  a-test-run-uses-the-correct-venv-des-build-never-a-stale-shadowing-global.md

DEFECT: the original `resolve_des_cli_cmd` (`tests/cli_resolve.py`) probed
a PATH-resolved shim with `_shim_runs` -- `--help` exits 0 AND no
`ModuleNotFoundError` in stderr. A stale global `des` missing only a NEWER
subcommand still passes that probe cleanly (it IS `des`, it just lacks one
command), so it silently shadowed the correct, currently-active venv build
whenever it was first on PATH. Confirmed independently in row5's
`WorktreeCleanupFixture.run_sweep_subprocess` (commit
`1e05a7bda`/`c2d7f5e44`), fixed there by resolving from
`Path(sys.executable).parent / "des"` directly, never PATH. This regression
proves the SAME fix applied centrally to the shared `resolve_des_cli_cmd`
helper, so every OTHER AT fixture reusing it is protected too -- not just
the two named sites (see also
`tests/des/acceptance/blast_radius_measured_tier/
test_blast_radius_slice01_walking_skeleton.py`, fixed alongside this).

Driving surface: calls `resolve_des_cli_cmd` directly (the unit under
test), never a subprocess of `des` itself -- a unit-level regression on the
helper's resolution LOGIC, not on `des` behavior.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from tests.cli_resolve import resolve_des_cli_cmd


_STALE_HELP_TEXT = "usage: des [-h] {log-phase,verify-integrity}\n"


def _write_help_passing_shim(path: Path, help_text: str) -> None:
    """A script that passes a `--help` probe cleanly (exit 0, no
    `ModuleNotFoundError`) but is NOT the real `des` build -- simulates an
    older, still-runnable global install."""
    path.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        'if "--help" in sys.argv:\n'
        f"    sys.stdout.write({help_text!r})\n"
        "    sys.exit(0)\n"
        'sys.stderr.write("stale shim: unknown subcommand\\n")\n'
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_resolve_des_cli_cmd_rejects_stale_shadowing_global(
    tmp_path, monkeypatch
) -> None:
    """A stale-but-`--help`-passing global `des` earlier on PATH must NOT
    shadow the active venv's own `des` build -- the exact fragility class
    named in the charter."""
    venv_des = Path(sys.executable).parent / "des"
    assert venv_des.exists(), (
        "this regression requires a real venv-built `des` console-script "
        "(uv sync) -- if missing, the dev environment install is the "
        "problem, not this test"
    )

    stale_dir = tmp_path / "stale_global_bin"
    stale_dir.mkdir()
    stale_shim = stale_dir / "des"
    _write_help_passing_shim(stale_shim, _STALE_HELP_TEXT)

    # The stale shim is first on PATH -- the exact shadowing scenario.
    monkeypatch.setenv("PATH", f"{stale_dir}{os.pathsep}{os.environ['PATH']}")

    resolved = resolve_des_cli_cmd("des", "des.cli.__main__")

    assert resolved == [str(venv_des)], (
        f"expected the ACTIVE venv's own des build ({venv_des}), got "
        f"{resolved!r} -- the stale global on PATH shadowed it"
    )


def test_resolve_des_cli_cmd_still_uses_a_working_global_when_venv_lacks_the_shim(
    tmp_path, monkeypatch
) -> None:
    """Negative: a shim name the active venv does NOT build at all must
    still resolve via a working PATH-resolved global -- the fix must not
    break the legitimate no-venv / global-only case."""
    shim_name = "des-not-built-in-this-venv"
    assert not (Path(sys.executable).parent / shim_name).exists()

    global_dir = tmp_path / "global_bin"
    global_dir.mkdir()
    global_shim = global_dir / shim_name
    _write_help_passing_shim(global_shim, "usage: des-not-built-in-this-venv [-h]\n")

    monkeypatch.setenv("PATH", f"{global_dir}{os.pathsep}{os.environ['PATH']}")

    resolved = resolve_des_cli_cmd(shim_name, "des.cli.__main__")

    assert resolved == [str(global_shim)]


def test_resolve_des_cli_cmd_resolves_known_good_venv_build_without_path_shims(
    monkeypatch,
) -> None:
    """Negative: the strengthened probe must not reject a known-good venv
    build -- resolution succeeds even with PATH cleared entirely (the venv
    branch never consults PATH)."""
    venv_des = Path(sys.executable).parent / "des"
    assert venv_des.exists()

    monkeypatch.delenv("PATH", raising=False)

    resolved = resolve_des_cli_cmd("des", "des.cli.__main__")

    assert resolved == [str(venv_des)]
