"""Regression: `des dispatch` must resolve its SSOT from the INSTALLED
runtime when run standalone (no --repo-root) against a NON-nWave target repo.

DEFECT (feature-delta: fix-dispatch-ssot-resolves-from-installed-runtime):
`des dispatch` reads `nWave/dispatch/{atdd_pure.yaml,vendors.yaml}` from the
TARGET repo root (cwd or `--repo-root`, dispatch.py main():300-301) -- but the
SSOT ships WITH nWave, not with the user's project. On ANY repo other than
the nwave-dev checkout the producing tool fails ("cannot read dispatch SSOT
at <target>/nWave/dispatch/atdd_pure.yaml") and the operator must know and
pass the path of a nWave checkout, reproduced live twice on the tsunami repo
(2026-07-11). Aggravation: the installed runtime does not even SHIP the
dispatch YAMLs (`~/.claude/lib/nWave/dispatch/` does not exist today --
confirmed empirically 2026-07-11: `_NWAVE_RUNTIME_ASSET_DIRS` in
`scripts/install/plugins/des_plugin.py` lists `("flavors", "data",
"templates", "schemas")` -- "dispatch" is absent).

Bug observable (the oracle): from a NON-nWave repo, `des dispatch --mode
atdd_pure ...` with NO --repo-root succeeds, generating a valid prompt -- the
SSOT resolves from the installed runtime assets. `--repo-root` remains an
explicit override (dev checkouts, forks). When NEITHER an installed SSOT nor
a repo-root SSOT exists, the existing degrade-LOUD refusal fires (its HOW
updated to name BOTH cures: reinstall for users, --repo-root for dev
checkouts).

INFERRED CRAFTER CONTRACT (documented here so the crafter has an unambiguous
target; flag back to DISTILL if a specific choice below is wrong):

  * SSOT resolution order in `src/des/cli/dispatch.py::main`: explicit
    `--repo-root` wins > cwd IF `cwd/nWave/dispatch/atdd_pure.yaml` exists >
    the installed-runtime assets dir > the existing LOUD refusal (HOW updated
    to name both cures).
  * The installed-runtime assets dir is a NEW module-level constant,
    `dispatch._INSTALLED_DISPATCH_ASSETS_DIR`, computed from its
    sibling-of-`lib/python` asset dir (`Path(__file__).resolve()
    .parents[N] / "nWave" / "dispatch"`). For `src/des/cli/dispatch.py`, N=3
    resolves to the checkout root in a DEV checkout (`src/des/cli/dispatch.py`
    -> parents[3] == repo root, verified empirically) AND to the installed
    `<claude_dir>/lib/` in an INSTALLED tree (`lib/python/des/cli/dispatch.py`
    -> parents[3] == `<claude_dir>/lib`, verified empirically against this
    machine's `~/.claude/lib/python/des/cli/dispatch.py`) -- ONE formula
    covers both layouts because `nWave/` sits as a sibling of the code root in
    BOTH cases. This module-level constant is the seam these ATs monkeypatch
    (`raising=False` since it does not exist until the crafter adds it).
  * `scripts/install/plugins/des_plugin.py::DESPlugin._NWAVE_RUNTIME_ASSET_DIRS`
    gains `"dispatch"` alongside the existing `("flavors", "data", "templates",
    "schemas")` -- so the installed runtime actually SHIPS the SSOT the new
    fallback reads.
  * The refusal's HOW (today: "fix: pass --repo-root pointing at a checkout
    containing nWave/dispatch/atdd_pure.yaml") gains a SECOND cure naming
    "reinstall" for the case where the installed runtime itself lacks the
    assets.

Driving surface: in-process against the REAL `des dispatch` CLI via
`tests/common/in_process_cli.run_cli_in_process` (mirrors
`test_dispatch_emits_at_kind_markers_for_pytest_feature.py`, the established
sibling in this same directory) -- the in-process analogue of
`python -m des.cli.__main__ dispatch ...`, with `cwd=` reproducing the
subprocess's cwd semantics faithfully (chdir + restore) and `monkeypatch`
controlling the installed-assets seam on the SAME cached `des.cli.dispatch`
module object `des.cli.__main__` dynamically imports.

RED-for-right-reason: scenario 1 (the bug) FAILS TODAY with a semantic
AssertionError (exit 2 / "cannot read dispatch SSOT", not exit 0) because
`main()` only ever resolves `repo_root` from `--repo-root` or `Path.cwd()`
(dispatch.py:300) -- it has no installed-runtime fallback branch, so the new
`_INSTALLED_DISPATCH_ASSETS_DIR` monkeypatch this AT sets is inert against
today's code. Scenarios 2/3 pin EXISTING correct precedence (already GREEN
today, must stay green post-fix). Scenario 4 documents which half of the HOW
is RED today. Scenario 5 (plugin) is RED today (`_NWAVE_RUNTIME_ASSET_DIRS`
omits "dispatch").

covers: fix-dispatch-ssot-resolves-from-installed-runtime, slice-01
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from des.cli import dispatch
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] is the checkout root (mirrors
# test_dispatch_emits_at_kind_markers_for_pytest_feature.py in this same dir).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_ATDD_PURE_YAML = _REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"
_REAL_VENDORS_YAML = _REPO_ROOT / "nWave" / "dispatch" / "vendors.yaml"
_REAL_MARKER_SYNTAX_LINE = 'marker_syntax: "<!-- {key} : {value} -->"'


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _copy_real_dispatch_ssot(
    dst_dir: Path, *, marker_syntax: str | None = None
) -> None:
    """Copy THIS checkout's real dispatch SSOT into ``dst_dir``.

    ``marker_syntax`` (given) replaces the claude_code vendor's real
    ``<!-- {key} : {value} -->`` rendering with a distinguishing literal --
    used to byte-compare WHICH SSOT source a dispatch actually read.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    atdd_pure_text = _REAL_ATDD_PURE_YAML.read_text(encoding="utf-8")
    vendors_text = _REAL_VENDORS_YAML.read_text(encoding="utf-8")
    if marker_syntax is not None:
        assert _REAL_MARKER_SYNTAX_LINE in vendors_text, (
            "fixture assumption stale -- the real vendors.yaml claude_code "
            f"marker_syntax line changed from {_REAL_MARKER_SYNTAX_LINE!r}"
        )
        vendors_text = vendors_text.replace(
            _REAL_MARKER_SYNTAX_LINE, f'marker_syntax: "{marker_syntax}"', 1
        )
    (dst_dir / "atdd_pure.yaml").write_text(atdd_pure_text, encoding="utf-8")
    (dst_dir / "vendors.yaml").write_text(vendors_text, encoding="utf-8")


def _base_argv(
    *,
    project_id: str = "demo-project",
    slice_id: str = "slice-01",
    repo_root: Path | None = None,
) -> list[str]:
    argv = [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        "--phase",
        "A_GREEN",
        "--intent",
        "verify SSOT resolution",
    ]
    if repo_root is not None:
        argv += ["--repo-root", str(repo_root)]
    return argv


def _run_dispatch(argv: list[str], *, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *argv], cwd=cwd)


# ---------------------------------------------------------------------------
# AT-1 -- POSITIVE: the bug. cwd has no nWave/dispatch, no --repo-root ->
# the installed-runtime assets dir must be consulted as the fallback.
# ---------------------------------------------------------------------------


def test_installed_runtime_fallback_used_when_cwd_has_no_ssot_and_no_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The oracle scenario: a NON-nWave repo, no --repo-root, succeeds via the
    installed-runtime fallback.

    FAILS TODAY: `main()` never looks past `--repo-root`/`Path.cwd()`
    (dispatch.py:300-301), so it reads
    `<non_nwave_repo>/nWave/dispatch/atdd_pure.yaml`, gets an `OSError`, and
    exits 2 with "cannot read dispatch SSOT" -- never reaching exit 0.
    """
    non_nwave_repo = tmp_path / "target-repo"
    non_nwave_repo.mkdir()

    installed_assets_dir = tmp_path / "installed" / "nWave" / "dispatch"
    _copy_real_dispatch_ssot(installed_assets_dir)
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", installed_assets_dir, raising=False
    )

    exit_code, stdout, stderr = _run_dispatch(_base_argv(), cwd=non_nwave_repo)

    assert exit_code == 0, (
        "expected `des dispatch` to fall back to the installed-runtime SSOT "
        f"when cwd ({non_nwave_repo}) carries no nWave/dispatch/ and no "
        f"--repo-root was given; got exit {exit_code}. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert "<!-- DES-PROJECT-ID : demo-project -->" in stdout, (
        "installed-runtime SSOT fallback did not produce a marker-carrying "
        f"prompt.\nstdout={stdout!r}\nstderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# AT-2 -- PRECEDENCE: an explicit --repo-root wins over the installed
# fallback even when the fallback is armed and cwd is neither source.
# ---------------------------------------------------------------------------


def test_repo_root_flag_wins_over_installed_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--repo-root` stays the explicit override -- pinned to survive the fix.

    Distinguishing element: the installed copy carries a DIFFERENT
    (fabricated) vendor marker_syntax; the rendered prompt must carry the
    real `--repo-root` copy's marker syntax, never the installed copy's.
    """
    repo_root_dir = tmp_path / "explicit-repo-root"
    _copy_real_dispatch_ssot(repo_root_dir / "nWave" / "dispatch")

    installed_assets_dir = tmp_path / "installed" / "nWave" / "dispatch"
    _copy_real_dispatch_ssot(installed_assets_dir, marker_syntax="[[{key}::{value}]]")
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", installed_assets_dir, raising=False
    )

    neutral_cwd = tmp_path / "neutral-cwd"
    neutral_cwd.mkdir()

    exit_code, stdout, stderr = _run_dispatch(
        _base_argv(repo_root=repo_root_dir), cwd=neutral_cwd
    )

    assert exit_code == 0, (
        f"--repo-root pointing at a valid SSOT must still succeed; got "
        f"exit {exit_code}. stdout={stdout!r} stderr={stderr!r}"
    )
    assert "<!-- DES-PROJECT-ID : demo-project -->" in stdout, (
        f"--repo-root's real marker syntax must win the render.\nstdout={stdout!r}"
    )
    assert "[[DES-PROJECT-ID::demo-project]]" not in stdout, (
        "the installed-fallback's DISTINGUISHING marker syntax leaked into "
        "the output even though --repo-root was given explicitly -- "
        f"--repo-root must win precedence.\nstdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# AT-3 -- CWD-PRECEDENCE: cwd already carries nWave/dispatch/*.yaml -> used
# directly, without needing --repo-root (pre-fix behaviour, pinned).
# ---------------------------------------------------------------------------


def test_cwd_ssot_used_without_repo_root_flag_pre_fix_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cwd-resident SSOT resolves without --repo-root -- today's baseline,
    must remain true post-fix.

    The installed-fallback seam is armed pointing at an ABSENT directory:
    proves cwd resolution short-circuits before ever consulting the fallback.
    """
    cwd_repo = tmp_path / "cwd-repo"
    _copy_real_dispatch_ssot(cwd_repo / "nWave" / "dispatch")

    absent_installed_dir = tmp_path / "does-not-exist" / "nWave" / "dispatch"
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", absent_installed_dir, raising=False
    )

    exit_code, stdout, stderr = _run_dispatch(_base_argv(), cwd=cwd_repo)

    assert exit_code == 0, (
        "pre-fix baseline: cwd-resident nWave/dispatch/*.yaml must resolve "
        f"without --repo-root. got exit {exit_code}. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert "<!-- DES-PROJECT-ID : demo-project -->" in stdout


# ---------------------------------------------------------------------------
# AT-4 -- NEGATIVE: neither an installed nor a repo-root/cwd SSOT exists ->
# the LOUD refusal fires, HOW naming BOTH cures.
# ---------------------------------------------------------------------------


def test_dispatch_refuses_with_both_cures_when_neither_ssot_source_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The degrade-LOUD refusal must survive the fix AND grow a second cure.

    Today's message names only the dev-checkout cure (--repo-root); the
    aggravation this bug names explicitly is that the installed runtime does
    not even ship the assets, so the HOW must ALSO tell an end user to
    reinstall. Report honestly which half is RED today.
    """
    non_nwave_repo = tmp_path / "target-repo"
    non_nwave_repo.mkdir()

    absent_installed_dir = tmp_path / "not-installed" / "nWave" / "dispatch"
    monkeypatch.setattr(
        dispatch, "_INSTALLED_DISPATCH_ASSETS_DIR", absent_installed_dir, raising=False
    )

    exit_code, stdout, stderr = _run_dispatch(_base_argv(), cwd=non_nwave_repo)

    assert exit_code == dispatch._EXIT_USAGE_ERROR, (
        "expected the LOUD refusal exit "
        f"({dispatch._EXIT_USAGE_ERROR}) when neither an installed nor a "
        f"repo-root/cwd SSOT exists; got {exit_code}. "
        f"stdout={stdout!r} stderr={stderr!r}"
    )
    assert "--repo-root" in stderr, (
        f"HOW must still name the dev-checkout cure (--repo-root): {stderr!r}"
    )
    assert "reinstall" in stderr.lower(), (
        "HOW must ALSO name the end-user cure (reinstall the runtime) -- "
        f"today's refusal names only --repo-root, never 'reinstall': {stderr!r}"
    )


# ---------------------------------------------------------------------------
# AT-5 -- PLUGIN HALF: the DES install plugin must ship nWave/dispatch/ so
# the installed-runtime fallback above has assets to read on a real install.
# ---------------------------------------------------------------------------


def test_installed_runtime_assets_ship_dispatch_yaml_directory(tmp_path: Path) -> None:
    """`DESPlugin._install_nwave_runtime_assets` must ship `nWave/dispatch/`
    alongside the other runtime asset families.

    Mirrors `tests/installer/unit/plugins/test_des_nwave_runtime_assets.py`'s
    established seam/fixture shape for this SAME method.

    The fixture must build a source tree the method RECOGNISES as an nWave
    tier: `_install_nwave_runtime_assets` returns N/A early when the tree
    carries no `framework-catalog.yaml`, because a target with no nWave tier is
    a legitimate install target under target-machine agnosticism. A fixture that
    supplies only `dispatch/` never reaches the copy loop at all -- it exercises
    the early return and then reports the miss as if the asset-dir list were at
    fault. The catalogue file below is what makes this test measure the thing it
    names.
    """
    project_root = tmp_path / "project"
    nwave_source = project_root / "nWave"
    _copy_real_dispatch_ssot(nwave_source / "dispatch")
    # Marks the tree as an nWave source tier; without it the method declares N/A.
    (nwave_source / "framework-catalog.yaml").write_text(
        "agents: []\n", encoding="utf-8"
    )

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=tmp_path / "scripts",
        templates_dir=nwave_source / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=None,
    )

    DESPlugin()._install_nwave_runtime_assets(context=context, using_prebuilt=False)

    shipped_dispatch_dir = claude_dir / "lib" / "nWave" / "dispatch"
    shipped_files = sorted(p.name for p in claude_dir.rglob("*") if p.is_file())
    assert (shipped_dispatch_dir / "atdd_pure.yaml").is_file(), (
        "des_plugin.py's _NWAVE_RUNTIME_ASSET_DIRS omits 'dispatch' -- the "
        "installed runtime never ships nWave/dispatch/*.yaml, which is "
        f"exactly what the installed-runtime fallback needs to read. "
        f"shipped files: {shipped_files}"
    )
    assert (shipped_dispatch_dir / "vendors.yaml").is_file(), (
        f"vendors.yaml missing from the shipped dispatch dir. shipped files: {shipped_files}"
    )


# ---------------------------------------------------------------------------
# AT-6 -- HARDENING: the PRODUCTION script-mode entry (`python
# scripts/install/install_nwave.py`, the real subprocess target of
# nwave_ai/cli.py:221's `_run_script`) must never resolve
# `scripts.install.plugins.des_plugin` from a stale decoy snapshot placed
# earlier on PYTHONPATH than the repo root.
#
# RCA this AT closes (feature-end hardening slice, escaped-seam class):
# AT-5 above exercises `DESPlugin()._install_nwave_runtime_assets` IN-PROCESS
# -- pytest's own sys.path always resolves the REPO plugin module there, so
# AT-5 structurally cannot observe this defect. The production entry is a
# SUBPROCESS in script mode; there, `sys.path[0]` is the script's own
# directory and an editable-install `.pth` appends the repo root AFTER
# site-packages -- a PRESENCE-GUARDED bootstrap (`if repo_root not in
# sys.path: insert(0, ...)`) sees the repo root already present (just in the
# WRONG position) and does nothing, leaving an earlier stale site-packages
# `scripts/` snapshot to win PEP-420 namespace-portion resolution. The
# landed fix (install_nwave.py's `_project_root` bootstrap, both
# occurrences) makes the move-to-front UNCONDITIONAL (remove-then-insert(0))
# instead of presence-guarded.
#
# Oracle: plant a FULL stale-snapshot copy of `scripts/install/plugins/`
# (not a single missing file -- `scripts.install.plugins` is a REGULAR
# package via its `__init__.py`, so whichever sys.path portion wins supplies
# ALL of its submodules; a partial decoy would ModuleNotFoundError on
# sibling plugins instead of exercising the same-file-shadowing defect),
# with `des_plugin.py` swapped for a stand-in that writes a sentinel file
# the moment it is IMPORTED. Run `python install_nwave.py --help` (returns
# before any install side-effect, per install_nwave.py's own `if args.help:
# show_help(); return 0`) as a real subprocess with PYTHONPATH =
# [decoy, repo_root] -- decoy first, repo root second, reproducing the
# editable-.pth ordering the RCA names. Assert the sentinel was NEVER
# written: the repo module resolved, never the decoy.
# ---------------------------------------------------------------------------


_REAL_INSTALL_NWAVE_SCRIPT = _REPO_ROOT / "scripts" / "install" / "install_nwave.py"
_REAL_PLUGINS_DIR = _REPO_ROOT / "scripts" / "install" / "plugins"


def _plant_decoy_plugins_snapshot(decoy_root: Path, sentinel_file: Path) -> None:
    """Plant a full stale-snapshot copy of ``scripts/install/plugins/`` under
    ``decoy_root``, with ``des_plugin.py`` swapped for a stand-in that writes
    ``sentinel_file`` the instant it is IMPORTED.

    A full copy (not a single-file decoy) mirrors the real incident's shape:
    a stale FULL site-packages ``scripts/`` snapshot, one file behind
    version -- and it is REQUIRED for the PEP-420 mechanics to isolate the
    defect under test: ``scripts.install.plugins`` carries ``__init__.py``
    (a regular package), so whichever sys.path portion resolves it first
    supplies ALL of its submodules; a partial decoy would ModuleNotFoundError
    on sibling plugins (e.g. ``agents_plugin``) instead of exercising the
    same-file-shadowing defect this AT targets.
    """
    decoy_plugins_dir = decoy_root / "scripts" / "install" / "plugins"
    shutil.copytree(
        _REAL_PLUGINS_DIR,
        decoy_plugins_dir,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (decoy_plugins_dir / "des_plugin.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(sentinel_file)!r}).write_text('decoy-imported', encoding='utf-8')\n"
        "\n"
        "\n"
        "class DESPlugin:\n"
        "    def __init__(self, *_args, **_kwargs) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )


def _run_install_help_with_decoy_ahead_of_repo_root(
    *, script_path: Path, decoy_root: Path, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    """Run ``python <script_path> --help`` with the decoy plugins snapshot
    FIRST and the repo root SECOND on PYTHONPATH -- reproducing the RCA's
    editable-install ``.pth`` ordering (repo root present, but appended AFTER
    site-packages).

    Hermetic: HOME/CLAUDE_CONFIG_DIR redirected under ``tmp_path`` even
    though ``--help`` returns before any install side-effect could fire
    (defense in depth -- never touches the real ``~/.claude*``). No network.
    """
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    path_entries = [str(decoy_root), str(_REPO_ROOT)]
    if existing_pythonpath:
        path_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(path_entries)
    hermetic_home = tmp_path / "hermetic-home"
    hermetic_home.mkdir(exist_ok=True)
    env["HOME"] = str(hermetic_home)
    env["CLAUDE_CONFIG_DIR"] = str(hermetic_home / ".claude")
    return subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=55,
    )


def test_entry_script_never_resolves_stale_site_packages_plugin(
    tmp_path: Path,
) -> None:
    """The production SCRIPT-MODE entry must resolve
    `scripts.install.plugins.des_plugin` from the repo, never a stale decoy
    snapshot placed earlier on PYTHONPATH -- the exact defect AT-5 cannot
    observe (it runs in-process, where pytest's own sys.path always wins).

    FAILS on the pre-fix presence-guarded bootstrap (see the red-proof
    validation run recorded in this feature's DISTILL report): reverting
    install_nwave.py's `_project_root` move-to-front to the old `if not in
    sys.path: insert(0, ...)` form lets the decoy win, because the repo root
    is already present in sys.path (via PYTHONPATH) -- just in the wrong
    position -- so the presence guard does nothing.
    """
    decoy_root = tmp_path / "decoy-site-packages"
    sentinel_file = tmp_path / "decoy-imported.sentinel"
    _plant_decoy_plugins_snapshot(decoy_root, sentinel_file)

    result = _run_install_help_with_decoy_ahead_of_repo_root(
        script_path=_REAL_INSTALL_NWAVE_SCRIPT, decoy_root=decoy_root, tmp_path=tmp_path
    )

    assert result.returncode == 0, (
        "`--help` must exit 0 without ever reaching install side-effects; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert not sentinel_file.exists(), (
        "the decoy scripts/install/plugins/des_plugin.py was IMPORTED inside "
        "the subprocess -- the move-to-front bootstrap failed to put the "
        "repo root ahead of the earlier-on-PYTHONPATH decoy snapshot, so "
        "the installed-runtime SSOT fallback this feature ships could "
        "silently read a stale plugin instead of the repo's. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AT-7 -- HARDENING (feature-end reloop, Vera's independent examine): a
# PARTIAL/broken installed runtime must never let the `des` launcher shim
# crash with a raw traceback -- it must degrade LOUD with the same two-cure
# guidance this feature promises for the dispatch SSOT refusal.
#
# RCA (Vera's finding, reproduced): the shim source `nWave/scripts/des/des`
# (copied verbatim by `DESPlugin._install_des_shims` to `~/.claude*/bin/des`)
# does `from des.cli.__main__ import main` with NO guard. Importing
# `des.cli.__main__` first imports its parent package `des.cli`, whose
# `__init__.py` does `from des.runtime.freshness import
# assert_fresh_or_explain` at MODULE level -- so ANY broken/partial `des`
# package under the installed `lib/python/` (missing entirely, or missing
# just `des.runtime`) raises before a single line of CLI code runs. Python
# prints the raw traceback to stderr; the slice's promised two-cure refusal
# never gets a chance to fire.
#
# Oracle: copy ONLY the shim source (never mutated) into a tmp "bin/" dir;
# run it as a real subprocess with HOME redirected so the shim's hardcoded
# `Path.home() / ".claude" / "lib" / "python"` resolution lands on a tmp
# tree that carries NO `des` package at all (simplest faithful shape of "a
# broken/partial install" -- team-lead's dispatch names this as one of two
# equally-valid decoy shapes, the other being a `des` package with
# `des/runtime` deleted).
#
# LOAD-BEARING interpreter isolation (`-S`): this project's own dev venv has
# `des` editable-installed (confirmed: AT-1..AT-6 above `from des.cli import
# dispatch` at module scope) -- `sys.executable` alone would resolve `des`
# via the ambient venv's site-packages .pth REGARDLESS of what tmp_path's
# fake install carries, making the fixture vacuous (empirically confirmed:
# without `-S` the shim ran clean via the dev venv's editable des, exit 0,
# full CLI help). `-S` skips `site.py` entirely -- no site-packages, no
# .pth processing -- so ONLY the shim's own `sys.path.insert(0, ...)` line
# controls what `des` resolves to, same as a real end-user's `pipx`-isolated
# interpreter with no ambient dev checkout.
# ---------------------------------------------------------------------------


_REAL_DES_SHIM = _REPO_ROOT / "nWave" / "scripts" / "des" / "des"


def test_broken_runtime_never_emits_raw_traceback_from_des_shim(tmp_path: Path) -> None:
    """The `des` launcher shim must degrade LOUD -- never a raw traceback --
    when the installed runtime is broken or partial.

    FAILS TODAY (Vera's independent feature-end examine): the shim's
    `from des.cli.__main__ import main` (nWave/scripts/des/des:8) has no
    try/except. A broken install makes Python print a raw
    `ModuleNotFoundError` traceback to stderr and exit 1 -- zero WHAT, zero
    WHY, zero HOW. Empirically reproduced (this AT's own RED run):
    ``Traceback (most recent call last): ... ModuleNotFoundError: No module
    named 'des'``.

    Hermetic: copies ONLY the shim source into a tmp "bin/" dir (never
    mutates `nWave/scripts/des/des`); HOME redirected to a tmp broken-home
    so the shim's hardcoded `Path.home() / ".claude" / "lib" / "python"`
    resolution lands on the broken tmp tree -- never touches the real
    `~/.claude*`. `-S` neutralizes the dev venv's own editable `des`
    install so the fixture cannot be silently bypassed (see module comment
    above). No network.
    """
    shim_copy = tmp_path / "bin" / "des"
    shim_copy.parent.mkdir(parents=True, exist_ok=True)
    shim_copy.write_text(_REAL_DES_SHIM.read_text(encoding="utf-8"), encoding="utf-8")
    shim_copy.chmod(0o755)

    broken_home = tmp_path / "broken-home"
    # ~/.claude/lib/python/ exists (the shim's sys.path.insert target is a
    # real directory) but carries NO `des` package at all -- the simplest
    # faithful shape of a partial/interrupted install.
    (broken_home / ".claude" / "lib" / "python").mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(broken_home)
    env.pop("PYTHONPATH", None)  # belt-and-braces: -S already blocks this leak

    result = subprocess.run(
        [sys.executable, "-S", str(shim_copy)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0, (
        "a broken install must exit non-zero, not silently succeed. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Traceback" not in result.stderr, (
        "the des shim leaked a RAW Python traceback to stderr on a broken "
        "install -- it must catch the ImportError and print a "
        f"self-explaining message instead. stderr={result.stderr!r}"
    )
    stderr_lower = result.stderr.lower()
    assert "pipx install" in stderr_lower or "nwave_ai.cli" in stderr_lower, (
        "the refusal must name the reinstall cure (`python -m nwave_ai.cli "
        f"install` or `pipx install nwave-ai`). stderr={result.stderr!r}"
    )
    assert "checkout" in stderr_lower or "source" in stderr_lower, (
        "the refusal must ALSO name the dev-checkout cure (run from a "
        f"nWave source checkout). stderr={result.stderr!r}"
    )
