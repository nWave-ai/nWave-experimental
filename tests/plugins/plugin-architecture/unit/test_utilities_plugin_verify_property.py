"""RED->GREEN for techdebt row
``utilities-plugin-verify-passes-on-any-py-file-in-a-shared-directory``.

``UtilitiesPlugin.verify()`` declared success whenever
``target_scripts_dir.glob('*.py')`` was non-empty -- a designation check
(some .py file exists) instead of the property the plugin is actually
responsible for (each of its OWN declared ``UTILITY_SCRIPTS`` landed).
Because the target directory is shared with the DES plugin family (both
write into ``context.claude_dir / 'scripts'``), the DES plugin's own files
alone satisfied this check even when zero utility scripts were installed
(GDP-8: decide on the property, never the designation).

This test drives the bug directly: a target directory holding only an
UNRELATED .py file (standing in for a DES-family file, or any other
neighbour) must NOT satisfy verify() -- it must fail and NAME which
declared utility scripts are missing.
"""

import logging
from pathlib import Path

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.utilities_plugin import UtilitiesPlugin


@pytest.fixture
def test_logger() -> logging.Logger:
    logger = logging.getLogger("test.utilities_plugin_verify_property")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def project_root() -> Path:
    current = Path(__file__).resolve()
    return current.parents[4]


def test_verify_fails_when_only_an_unrelated_py_file_is_present(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
) -> None:
    """A shared-directory neighbour .py file must not satisfy the check."""
    claude_dir = tmp_path / ".claude-neighbour"
    scripts_dir = claude_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    # Stand-in for a DES-family (or any other) file in the SAME shared dir --
    # none of the plugin's own declared UTILITY_SCRIPTS.
    (scripts_dir / "some_other_plugins_script.py").write_text("# not a utility\n")

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )

    plugin = UtilitiesPlugin()

    result = plugin.verify(context)

    assert result.success is False
    for script_name in UtilitiesPlugin.UTILITY_SCRIPTS:
        assert script_name in result.message or any(
            script_name in err for err in (result.errors or [])
        )


def test_verify_succeeds_only_when_every_declared_script_present(
    tmp_path: Path, project_root: Path, test_logger: logging.Logger
) -> None:
    claude_dir = tmp_path / ".claude-complete"
    scripts_dir = claude_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for script_name in UtilitiesPlugin.UTILITY_SCRIPTS:
        (scripts_dir / script_name).write_text("# stub\n")

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts" / "install",
        templates_dir=project_root / "nWave" / "templates",
        logger=test_logger,
        project_root=project_root,
        framework_source=project_root / "nWave",
        dry_run=False,
    )

    plugin = UtilitiesPlugin()

    result = plugin.verify(context)

    assert result.success is True
