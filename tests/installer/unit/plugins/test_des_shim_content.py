"""Tests for DES CLI shim file content.

Verifies that the consolidated des shim in nWave/scripts/des/ has the
correct structure: Python shebang, sys.path insertion, correct import,
and sys.exit(main()) call.

Slice-01 of fix-des-single-entry-point-consolidation reduced the 5 prior
des-* shims to a single ``des`` dispatcher (DDD-9 + DDD-8).
"""

import re
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "nWave" / "scripts" / "des"

SHIM_MODULE_MAP = {
    "des": "des.cli.__main__",
}

SHIM_NAMES = list(SHIM_MODULE_MAP.keys())


def _read_shim(name: str) -> str:
    return (SCRIPTS_DIR / name).read_text()


def test_all_shims_exist() -> None:
    """Every declared shim file must exist in nWave/scripts/des/."""
    for name in SHIM_NAMES:
        path = SCRIPTS_DIR / name
        assert path.exists(), f"Shim not found: {path}"
        assert path.is_file(), f"Expected a file, not a directory: {path}"


def test_shebang_is_python3_env() -> None:
    """Each shim must start with exactly '#!/usr/bin/env python3'."""
    for name in SHIM_NAMES:
        content = _read_shim(name)
        first_line = content.splitlines()[0]
        assert first_line == "#!/usr/bin/env python3", (
            f"{name}: expected shebang '#!/usr/bin/env python3', got {first_line!r}"
        )


def test_shim_pins_the_resolved_runtime_at_sys_path_head() -> None:
    """Each shim must pin its resolved runtime dir at sys.path[0].

    This asserts the structural invariant only -- position 0, and the dir
    the shim itself resolved. HOW that dir is chosen (NWAVE_RUNTIME env >
    ~/.nwave/active-runtime pointer > CLAUDE_CONFIG_DIR-aware Claude default
    > host-neutral fallback) is owned by the execution-based suite in
    test_des_shim_runtime_resolution.py, which runs each branch for real;
    duplicating that semantics as a literal here is what made this test pin
    the superseded `_CLAUDE_DIR / "lib" / "python"` spelling that commit
    8f60e04db replaced with `_RUNTIME_DIR`.
    """
    expected = "sys.path.insert(0, str(_RUNTIME_DIR))"
    for name in SHIM_NAMES:
        content = _read_shim(name)
        assert expected in content, (
            f"{name}: missing the resolved-runtime sys.path pin.\n"
            f"Expected: {expected!r}"
        )


def test_shim_imports_correct_main() -> None:
    """Each shim must import main from its specific des.cli module."""
    for name, module in SHIM_MODULE_MAP.items():
        content = _read_shim(name)
        expected_import = f"from {module} import main"
        assert expected_import in content, (
            f"{name}: missing import line.\nExpected: {expected_import!r}"
        )


def test_shim_calls_sys_exit_main() -> None:
    """Each shim must call sys.exit(main()) as the entry point."""
    for name in SHIM_NAMES:
        content = _read_shim(name)
        assert "sys.exit(main())" in content, f"{name}: missing 'sys.exit(main())' call"


def test_no_shell_shebangs_in_des_scripts() -> None:
    """Zero-shell policy: no #!/bin/bash or #!/bin/sh shebangs allowed."""
    shell_pattern = re.compile(r"^#!/bin/(bash|sh)\b")
    violations = []
    for path in SCRIPTS_DIR.iterdir():
        if path.is_file():
            try:
                first_line = path.read_text().splitlines()[0]
                if shell_pattern.match(first_line):
                    violations.append(str(path))
            except (IndexError, UnicodeDecodeError):
                pass
    assert not violations, (
        f"Shell scripts found (zero-shell policy violation): {violations}"
    )
