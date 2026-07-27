"""LocDiffPort must not collide with pytest's default collection naming.

Regression test for techdebt row
``src-test-prefixed-production-files-pytest-naming-collision``: the port used to
live in ``src/des/ports/driven_ports/test_loc_diff_port.py`` as
``class TestLocDiffPort(Protocol)``. Both the filename (``test_*.py``) and the
class name (``Test*``) matched pytest's default collection patterns
(``python_files``/``python_classes``); if this module were ever collected by a
pytest run that scans outside the configured ``testpaths`` (e.g. the
stale-build-dir defect that hands the repo root, unpruned, to a gate worker),
pytest would try to instantiate the ``Protocol`` class directly and raise
``TypeError``. The fix renamed the file to ``loc_diff_port.py`` and the class to
``LocDiffPort`` — the port is a production interface, not a test module.

NOTE on scope: the same row also names ``src/des/ports/test_runner_port.py`` as a
second offender. That file's NAME still matches pytest's ``test_*.py`` pattern, but
(verified by AST walk here) it defines no ``Test*``-prefixed class — so the sharper
half of the defect (a ``Protocol``/class that pytest would try to instantiate) does
not apply to it. Renaming that module was deliberately deferred out of this drain
pass: it is imported by 25+ production/test files, several via a bare
``from des.ports import test_runner_port`` module alias and in-file line-number
citations in comments/docstrings — a much larger, higher-blast-radius rename than
this one. This test therefore only enforces the *class*-name half of the guard
repo-wide, and enforces the filename half only for the file this pass fixed.
"""

from __future__ import annotations

import ast
from pathlib import Path


SRC_DES = Path(__file__).resolve().parents[5] / "src" / "des"


def test_loc_diff_port_importable_under_its_new_name():
    from des.ports.driven_ports.loc_diff_port import LocDiffPort

    assert LocDiffPort.__name__ == "LocDiffPort"


def test_loc_diff_port_file_no_longer_matches_pytest_default_collection_name():
    """The renamed file itself must not regress back to a test_*.py name."""
    driven_ports_dir = SRC_DES / "ports" / "driven_ports"
    offenders = [
        path
        for path in driven_ports_dir.glob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    ]
    assert offenders == [], (
        f"production port module(s) match pytest's default collection "
        f"filename pattern: {offenders}"
    )


def test_no_src_des_ports_class_matches_pytest_default_test_classes_pattern():
    """No class defined under src/des/ports is named Test* (pytest python_classes).

    This is the sharper half of the original defect: a `Test*`-named class is what
    would make pytest attempt direct instantiation (a `Protocol` raises TypeError).
    Covers the whole src/des/ports tree, including test_runner_port.py (which is
    confirmed clean by this same assertion — see the module docstring above).
    """
    offenders: list[str] = []
    for path in (SRC_DES / "ports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                offenders.append(f"{path}:{node.name}")
    assert offenders == [], (
        f"class name(s) under src/des/ports match pytest's default "
        f"collection class pattern: {offenders}"
    )
