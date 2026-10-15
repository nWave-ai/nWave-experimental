"""Release scripts import their own checkout, not a stale installed ``scripts``.

A development install can leave an older ``scripts`` package in site-packages
while an editable ``.pth`` also lists the checkout root later on ``sys.path``.
A guard that only inserts the root when it is absent then lets the stale copy
win, and the publisher's strip step fails with an ImportError.
"""

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RELEASE_SCRIPTS = [
    "scripts/release/strip_private_agents.py",
    "scripts/release/publish_experimental.py",
    "scripts/release/release_migration_bundle.py",
    "scripts/release/release_migration_decision.py",
    "scripts/release/patch_pyproject.py",
    "scripts/release/verify_wheel_privacy.py",
    "scripts/release/verify_plugin_privacy.py",
]


@pytest.mark.parametrize("script", RELEASE_SCRIPTS)
def test_release_script_prefers_its_checkout_over_a_stale_scripts_package(
    tmp_path: Path, script: str
) -> None:
    # Same shape as an installed copy: `scripts` is a namespace directory (like
    # the checkout's), its subpackages are regular packages missing new code.
    stale = tmp_path / "site" / "scripts"
    for package in (stale / "shared", stale / "release"):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("STALE = True\n", encoding="utf-8")
    # The bundle producer imports scripts.* lazily; public_destination() is a
    # side-effect-free function that crosses one of those imports.
    load = (
        "import runpy, sys; "
        f"sys.path[1:1] = [{str(tmp_path / 'site')!r}, {str(ROOT)!r}]; "
        f"g = runpy.run_path({str(ROOT / script)!r}, run_name='imported'); "
        "'public_destination' in g and g['public_destination']()"
    )
    completed = subprocess.run(
        [sys.executable, "-c", load],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
