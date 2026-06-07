"""Composition root for the fix-validate-tests-path-precision acceptance slice.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is the real production helper
``scripts.hooks.validate_tests.get_targeted_test_dirs`` loaded via the same
``importlib.util.spec_from_file_location`` pattern used by the existing
``tests/hooks/test_validate_tests.py`` (avoids the ``scripts/hooks`` not
being a Python package issue). Per Mandate-13, the AT drives through this
in-process function call entry point -- the same entry point the pre-commit
hook itself invokes.

ALL business logic lives in the production helper. Step bodies in
``common_steps.py`` delegate to this composition's methods and never inline
business logic (Mandate-12 criterion 3).

The single slice is layer 3 (subprocess / FS acceptance) -- subprocess is
monkeypatched per scenario so the real ``git diff --cached`` is not invoked;
the real filesystem under pytest ``tmp_path`` IS used so the helper's
``Path(d).is_dir()`` post-filter runs honestly (per Mandate 6 real-I/O for
the driven filesystem adapter).
"""

from __future__ import annotations

import importlib.util
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .domain_types import StagedFilePath, TargetedTestDir


# Resolve repo root by walking up from this file:
# tests/hooks/fix_validate_tests_path_precision/steps/composition.py -> 4 levels.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_HOOK_PATH = _REPO_ROOT / "scripts" / "hooks" / "validate_tests.py"


def _load_validate_tests_module() -> Any:
    """Load the production hook module by file path (same pattern as
    tests/hooks/test_validate_tests.py)."""
    spec = importlib.util.spec_from_file_location(
        "validate_tests_under_test", _HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class ScopeResolverComposition:
    """Composition root over the production scope-resolver helper.

    Per-scenario fresh: a new tmp workspace, a fresh module load, a fresh
    monkeypatched ``subprocess.run`` capture.
    """

    workspace: Path | None = None
    staged_files: list[StagedFilePath] = field(default_factory=list)
    existing_dirs: list[Path] = field(default_factory=list)
    result: list[str] | None | str | None = None
    _module: Any = None
    _original_cwd: Path | None = None

    def use_workspace(self, workspace: Path) -> None:
        """Adopt a pytest tmp_path as the workspace; chdir into it so the
        helper's ``Path(d).is_dir()`` post-filter resolves relative paths
        against the workspace (not the repo root)."""
        import os

        self.workspace = workspace
        self._original_cwd = Path.cwd()
        os.chdir(workspace)

    def teardown(self) -> None:
        """Restore the original cwd (called by the conftest fixture finalizer)."""
        import os

        if self._original_cwd is not None:
            os.chdir(self._original_cwd)
            self._original_cwd = None

    def load_driving_port(self) -> None:
        """Load the production hook module fresh for this scenario."""
        self._module = _load_validate_tests_module()

    def stage_files(self, files: list[StagedFilePath]) -> None:
        """Record the staged-file list the resolver will see."""
        self.staged_files = list(files)

    def ensure_directory_exists(self, relative_path: str) -> None:
        """Create a directory under the scenario workspace so the helper's
        ``Path(d).is_dir()`` post-filter retains it (Mandate 6 real-I/O)."""
        assert self.workspace is not None, (
            "use_workspace() must be called before ensure_directory_exists()"
        )
        target = self.workspace / relative_path
        target.mkdir(parents=True, exist_ok=True)
        self.existing_dirs.append(target)

    def resolve_targeted_test_dirs(self) -> None:
        """Invoke the production driving port with a monkeypatched
        ``subprocess.run`` so the helper sees exactly the staged-file list
        the scenario declared (NEVER calls real git)."""
        assert self._module is not None, (
            "load_driving_port() must be called before resolve_targeted_test_dirs()"
        )

        staged_text = "\n".join(self.staged_files) + ("\n" if self.staged_files else "")
        fake_completed = subprocess.CompletedProcess(
            args=["git", "diff", "--cached", "--name-only"],
            returncode=0,
            stdout=staged_text,
            stderr="",
        )

        original_run = subprocess.run

        def _stub_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
            return fake_completed

        # Patch the module's own subprocess reference (it imports `subprocess`
        # at module level and calls subprocess.run inside get_targeted_test_dirs).
        self._module.subprocess.run = _stub_run
        try:
            self.result = self._module.get_targeted_test_dirs()
        finally:
            self._module.subprocess.run = original_run

    # --- assertions / observers (port-exposed) ------------------------------

    def scope_as_list(self) -> list[TargetedTestDir]:
        """Return the resolver result as a typed list (raises if the result
        is None or "skip" -- the test scenarios drive only the list-path)."""
        assert isinstance(self.result, list), (
            f"expected list of TargetedTestDir, got {self.result!r}"
        )
        return [TargetedTestDir(d) for d in self.result]
