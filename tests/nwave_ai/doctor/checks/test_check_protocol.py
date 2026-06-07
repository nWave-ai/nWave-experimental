"""Parametrized test verifying all check classes expose the name/description protocol.

Each check must have non-empty `name` and `description` class attributes.
This single parametrized test replaces 7 identical copies across check test files.
"""

from __future__ import annotations

import pytest
from nwave_ai.doctor.checks.des_module import DesModuleCheck
from nwave_ai.doctor.checks.framework_files import FrameworkFilesCheck
from nwave_ai.doctor.checks.hook_python_path import HookPythonPathCheck
from nwave_ai.doctor.checks.hooks_registered import HooksRegisteredCheck
from nwave_ai.doctor.checks.path_env import PathEnvCheck
from nwave_ai.doctor.checks.python_version import PythonVersionCheck
from nwave_ai.doctor.checks.shims_deployed import ShimsDeployedCheck


@pytest.mark.parametrize(
    "check_class",
    [
        PythonVersionCheck,
        DesModuleCheck,
        HooksRegisteredCheck,
        HookPythonPathCheck,
        ShimsDeployedCheck,
        PathEnvCheck,
        FrameworkFilesCheck,
    ],
)
def test_check_has_name_and_description(check_class: type) -> None:
    """Every check class exposes non-empty name and description class attributes."""
    assert isinstance(check_class.name, str)
    assert len(check_class.name) > 0
    assert isinstance(check_class.description, str)
    assert len(check_class.description) > 0
