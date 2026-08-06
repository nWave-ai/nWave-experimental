"""Regression test: the installer's post-install import probe must verify
the EXACT import the installed `des` shim performs, not an unrelated module.

Defect (defects.md, `the-installer-verifies-an-import-different-from-the-one-
its-own-shim-will-use`): `DESPlugin.verify()` must probe the same
`from des.cli.__main__ import main` entry point the shim
(`nWave/scripts/des/des`) executes. Because the two packages are
copied independently and can diverge (`cli/` historically 10/87 files vs.
`application/` 26/46), the probe can report success while `des --help`
exits 1 on the installed copy.

This test derives the expected import from the shim source itself (the
class this repo already generalizes for its siblings: verifying that a
system that generates a consumer probes what that consumer will actually
do) so the two cannot silently diverge again.
"""

import inspect
import re
from pathlib import Path

from scripts.install.plugins.des_plugin import DESPlugin


SHIM_PATH = Path(__file__).resolve().parents[4] / "nWave" / "scripts" / "des" / "des"


def _shim_import_target() -> str:
    content = SHIM_PATH.read_text()
    match = re.search(r"from (\S+) import main", content)
    assert match, f"shim at {SHIM_PATH} has no 'from X import main' import"
    return match.group(1)


def test_verify_import_probe_matches_shim_entrypoint() -> None:
    shim_module = _shim_import_target()
    source = inspect.getsource(DESPlugin.verify)
    assert f"from {shim_module} import main" in source, (
        f"DESPlugin.verify() must probe 'from {shim_module} import main' "
        "(the same symbol the installed shim imports) so a broken/partial "
        "install copy is caught before the shim is invoked by the operator. "
        f"verify() source:\n{source}"
    )
