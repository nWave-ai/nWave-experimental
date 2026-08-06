"""
Helper functions for DES Installation Bug Acceptance Tests.

These utilities are shared across step definition modules.
Separated to avoid circular imports with conftest.py.
"""

from pathlib import Path


def scan_for_bad_imports(des_path: Path) -> list[str]:
    """
    Scan installed DES directory for bad import patterns.

    Returns list of files containing "from src.des" or "import src.des".
    """
    bad_files = []
    if not des_path.exists():
        return bad_files

    for py_file in des_path.rglob("*.py"):
        try:
            content = py_file.read_text()
            if "from src.des" in content or "import src.des" in content:
                bad_files.append(str(py_file))
        except Exception:
            pass

    return bad_files
