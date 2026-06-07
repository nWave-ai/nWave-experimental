"""DesModuleCheck — verifies the DES module is present in claude_dir/lib/python."""

from __future__ import annotations

import importlib.machinery
from typing import TYPE_CHECKING

from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    from pathlib import Path

    from nwave_ai.doctor.context import DoctorContext

_DES_PACKAGE = "des"
_DES_SUBMODULE = "domain"


class DesModuleCheck:
    """Check that des.domain is present under claude_dir/lib/python/."""

    name: str = "des_module"
    description: str = "DES module (des.domain) is present under ~/.claude/lib/python"

    def run(self, context: DoctorContext) -> CheckResult:
        """Return passed=True when des.domain is findable in the context lib/python path.

        Uses importlib.machinery.PathFinder.find_spec with an explicit search
        path restricted to context.claude_dir/lib/python.  This avoids both:
          - Hardcoded file-name assumptions (phase_events.py was renamed)
          - False positives from the process sys.path containing a different
            DES installation

        Args:
            context: Filesystem roots for this run.

        Returns:
            CheckResult with presence details in message.
        """
        lib_python = context.claude_dir / "lib" / "python"
        search_path = [str(lib_python)]

        # Find the top-level 'des' package restricted to our search path.
        top_spec = importlib.machinery.PathFinder.find_spec(
            _DES_PACKAGE, path=search_path
        )
        if top_spec is None:
            return self._missing(lib_python)

        # Find the 'des.domain' subpackage using the parent's submodule_search_locations.
        if top_spec.submodule_search_locations is None:
            return self._missing(lib_python)

        sub_spec = importlib.machinery.PathFinder.find_spec(
            _DES_SUBMODULE,
            path=list(top_spec.submodule_search_locations),
        )
        if sub_spec is None:
            return self._missing(lib_python)

        return CheckResult(
            passed=True,
            error_code=None,
            message=f"DES module 'des.domain' found under {lib_python}",
            remediation=None,
        )

    @staticmethod
    def _missing(lib_python: Path) -> CheckResult:
        return CheckResult(
            passed=False,
            error_code="DES_MODULE_MISSING",
            message=(
                f"DES module 'des.domain' not found under {lib_python}. "
                "The DES runtime may not be installed."
            ),
            remediation=(
                "Re-run `nwave-ai install` to reinstall the DES runtime, "
                "or check that ~/.claude/lib/python/des/ exists."
            ),
        )
