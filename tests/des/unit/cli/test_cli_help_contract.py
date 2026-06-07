"""Fast-gate CLI --help contract tests for all 5 DES CLI modules.

Asserts that every DES CLI entry point accepts --help (and -h) and signals
success (exit code 0). Two compliant implementation patterns exist:

- argparse-based CLIs: raise SystemExit(0) via parser.parse_args(['--help'])
- Custom-parser CLIs: return 0 directly (e.g., verify_deliver_integrity, roadmap)

Both patterns are compliant. The test captures either and asserts zero exit.
Any module that exits with a non-zero code or raises an unexpected exception
is caught here in the unit layer — no container required.

Marked @pytest.mark.fast_gate for pre-commit/pre-push hook registration.
"""

import importlib

import pytest


_DES_CLI_MODULES = [
    "des.cli.log_phase",
    "des.cli.init_log",
    "des.cli.verify_deliver_integrity",
    "des.cli.roadmap",
    "des.cli.health_check",
]


def _call_main_help(module_name: str, flag: str) -> int:
    """Invoke module.main(argv=[flag]) and return the effective exit code.

    Handles both implementation patterns:
    - argparse raises SystemExit(0) for --help → we catch and return .code
    - custom parser returns 0 directly → we return that value
    """
    module = importlib.import_module(module_name)
    try:
        result: int | None = module.main(argv=[flag])
        return result if result is not None else 0
    except SystemExit as exc:
        code = exc.code
        return int(code) if code is not None else 0


@pytest.mark.fast_gate
@pytest.mark.parametrize("module_name", _DES_CLI_MODULES)
def test_cli_main_accepts_help_with_zero_exit(module_name: str) -> None:
    """Assert main(argv=['--help']) signals exit code 0.

    Compliant implementations either raise SystemExit(0) (argparse) or
    return 0 directly. Both patterns are accepted; any non-zero code fails.
    """
    exit_code = _call_main_help(module_name, "--help")
    assert exit_code == 0, (
        f"{module_name}.main(argv=['--help']) signalled exit code "
        f"{exit_code!r}, expected 0"
    )


@pytest.mark.fast_gate
@pytest.mark.parametrize("module_name", _DES_CLI_MODULES)
def test_cli_main_accepts_short_help_with_zero_exit(module_name: str) -> None:
    """Assert main(argv=['-h']) signals exit code 0.

    Verifies that the short form -h is also registered and exits cleanly.
    """
    exit_code = _call_main_help(module_name, "-h")
    assert exit_code == 0, (
        f"{module_name}.main(argv=['-h']) signalled exit code {exit_code!r}, expected 0"
    )
