"""Wheel invariant: every DESPlugin.DES_HOOKS entry must be force-included.

Bug-fix regression guard for the fix-cross-host-sessionstart-packaging-path
RCA: `scripts/release/patch_pyproject.py` hand-listed exactly ONE
`scripts/hooks/*.py` file (`orchestrator_affordance_refresh.py`) in its wheel
force-include map, while `DESPlugin.DES_HOOKS` (scripts/install/plugins/
des_plugin.py) enumerates EIGHT scripts that the installer propagates to
`~/.claude/scripts/`. As long as the install-time source-directory
resolution for `scripts/hooks/` was ALSO broken (see
`tests/bugs/des/test_hook_scripts_source_dir_single_authority.py`), this gap
was invisible -- `validate_prerequisites`'s hook-presence check silently
no-opped because it could never find the (wrong) source directory at all.
Once that resolution was fixed to find the REAL nested wheel directory, the
presence check started (correctly) failing every wheel install outright: 7
of 8 `DES_HOOKS` scripts were never in the wheel to find.

This mirrors `tests/release/test_wheel_utility_scripts_invariant.py`'s
precedent exactly (same bug class, `UTILITY_SCRIPTS` vs. build_dist.py, the
v3.12.1 install regression) applied to the `scripts/hooks/` allow-list
instead of the top-level utility-script allow-list. `scripts/hooks/` also
carries this repo's OWN dev-only pre-commit tooling that must NEVER ship to
users, so the fix is an explicit per-file allow-list (`DES_HOOKS`), not a
directory-level force-include of the whole tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.install.plugins.des_plugin import DESPlugin
from scripts.release.patch_pyproject import patch_pyproject


def _patched_text(sample_pyproject_path: str, tmp_path) -> str:
    """Run the patcher against the shared fixture and return the rewritten TOML."""
    output_path = str(tmp_path / "patched.toml")
    patch_pyproject(
        input_path=sample_pyproject_path,
        output_path=output_path,
        target_name="nwave-ai",
        target_version="0.0.0",
    )
    return Path(output_path).read_text()


class TestHookScriptsForceIncluded:
    """Every DES_HOOKS entry is referenced in the wheel force-include map."""

    @pytest.mark.parametrize("script_name", DESPlugin.DES_HOOKS)
    def test_hook_script_is_force_included(
        self, script_name: str, sample_pyproject_path, tmp_path
    ):
        """For each hook script, the patched pyproject MUST contain a
        force-include entry mapping `scripts/hooks/<name>` to the NESTED
        wheel destination `nWave/nWave/hooks/<name>` --
        `_resolve_hook_scripts_source_dir` (des_plugin.py) probes that
        nested shape FIRST on a pipx/PyPI install.

        Failure mode this catches: an entry is missing from
        `_hook_scripts_force_include_block` in
        scripts/release/patch_pyproject.py, which produces a wheel without
        the hook script, which makes `validate_prerequisites` abort every
        installed-wheel `nwave-ai install` outright.
        """
        content = _patched_text(sample_pyproject_path, tmp_path)
        expected_entry = (
            f'"scripts/hooks/{script_name}" = "nWave/nWave/hooks/{script_name}"'
        )
        assert expected_entry in content, (
            f"Hook script '{script_name}' is not force-included in the "
            "wheel. Expected line in patched pyproject.toml's "
            "[tool.hatch.build.targets.wheel.force-include] block:\n"
            f"  {expected_entry}\n\n"
            "If you removed an entry from DESPlugin.DES_HOOKS, also remove "
            "it from scripts/release/patch_pyproject.py:"
            "_hook_scripts_force_include_block. If you added an entry to "
            "DES_HOOKS, also add the force-include declaration there."
        )


class TestHookScriptsForceIncludeMapInvariant:
    """The force-include block remains complete: every DES_HOOKS entry has
    a matching wheel declaration."""

    def test_no_hook_script_silently_dropped(self, sample_pyproject_path, tmp_path):
        """Equivalence between the installer's hook-script allow-list and
        the PyPI-wheel hook-script coverage.

        Ensures the two never drift: `DESPlugin.DES_HOOKS` (installer) and
        the force-include block (wheel) agree on which `scripts/hooks/*.py`
        files ship to users.
        """
        content = _patched_text(sample_pyproject_path, tmp_path)
        missing = [
            name
            for name in DESPlugin.DES_HOOKS
            if f'"scripts/hooks/{name}" = "nWave/nWave/hooks/{name}"' not in content
        ]
        assert not missing, (
            f"DES_HOOKS entries missing from wheel force-include map: {missing}. "
            "The PyPI wheel will ship without these scripts, and "
            "`validate_prerequisites` will abort every wheel-installed "
            "`nwave-ai install` on Claude Code targets. Fix: add a "
            "force-include line for each missing script in "
            "scripts/release/patch_pyproject.py:"
            "_hook_scripts_force_include_block."
        )
