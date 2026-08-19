"""Static existence check for `verification-scope.commands` test paths.

K4 Run 9: ATD wrote a `manage.py test` command citing the test labels
`api.tests.test_create_check` / `api.tests.test_flip_model` /
`api.tests.test_update_check` -- missing the real Django app-label prefix
`hc.` (the app lives at `hc/api`, not `api`). `des dispatch` accepted the
contract as-is (nothing checked `verification-scope.commands` at all); the
crafter spent 525.8s across 62 tool calls discovering the command itself
was wrong before correctly refusing to guess a fix -- a full dispatch's
cost that one static check, run before CONTRACT_READY is ever forwarded,
would have caught for free.

Python-only and static: no test framework or `manage.py` is imported or
executed here, only path existence on disk is checked, mirroring
`declared_import_resolver`'s discipline (K4 row 12 / Run 4-6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def _dotted_to_candidate_paths(root: Path, dotted: str) -> tuple[Path, Path]:
    """A dotted Django test label as a module file or a package `__init__.py`."""
    segments = dotted.split(".")
    module_file = root.joinpath(*segments[:-1], segments[-1] + ".py")
    package_init = root.joinpath(*segments, "__init__.py")
    return module_file, package_init


def _is_django_manage_test_command(command: dict) -> bool:
    executable = command.get("executable", {})
    if executable.get("kind") != "repository":
        return False
    path = str(executable.get("path", ""))
    if not (path == "manage.py" or path.endswith("/manage.py")):
        return False
    arguments = command.get("arguments", [])
    return bool(arguments) and arguments[0] == "test"


def _is_pytest_command(command: dict) -> bool:
    executable = command.get("executable", {})
    name_or_path = str(executable.get("name") or executable.get("path") or "")
    if "pytest" in name_or_path.lower():
        return True
    # `<python> -m pytest ...` -- pytest run as a module through the
    # interpreter, the shape this repo's own checked-in contracts use.
    return "pytest" in command.get("arguments", [])


def django_test_labels(command: dict) -> list[str]:
    """Every non-flag argument after `test` in a `manage.py test ...` command."""
    if not _is_django_manage_test_command(command):
        return []
    return [arg for arg in command["arguments"][1:] if not arg.startswith("-")]


def pytest_file_arguments(command: dict) -> list[str]:
    """Every `.py`-shaped argument (optionally with a `::node::id` suffix)
    in a pytest invocation."""
    if not _is_pytest_command(command):
        return []
    found: list[str] = []
    for arg in command.get("arguments", []):
        if arg.startswith("-"):
            continue
        file_part = arg.split("::", 1)[0]
        if file_part.endswith(".py"):
            found.append(arg)
    return found


def _oracle_equivalent_forms(oracle_locator: str) -> set[str]:
    """The dotted-module-label and repository-relative-path spellings of
    this contract's own `acceptance-tests.locator` -- a verification
    command may legitimately cite the SAME oracle file ATD authored, under
    either spelling, and that file is not a "missing" path merely because
    it did not exist before this delivery."""
    if not oracle_locator:
        return set()
    stem = oracle_locator[:-3] if oracle_locator.endswith(".py") else oracle_locator
    dotted = stem.replace("/", ".")
    return {dotted, oracle_locator}


def missing_verification_paths(repo_root: Path, contract: dict) -> list[str]:
    """Every `verification-scope.commands` argument naming a test module or
    file absent from the base tree and not this contract's own oracle --
    empty when every command is either unrecognized (not a `manage.py
    test`/pytest shape this checker covers) or fully resolvable."""
    oracle_locator = str(contract.get("acceptance-tests", {}).get("locator", ""))
    oracle_forms = _oracle_equivalent_forms(oracle_locator)

    missing: list[str] = []
    for command in contract.get("verification-scope", {}).get("commands", []):
        for label in django_test_labels(command):
            if label in oracle_forms:
                continue
            module_file, package_init = _dotted_to_candidate_paths(repo_root, label)
            if module_file.is_file() or package_init.is_file():
                continue
            missing.append(label)
        for path_arg in pytest_file_arguments(command):
            file_part = path_arg.split("::", 1)[0]
            if file_part in oracle_forms:
                continue
            if (repo_root / file_part).is_file():
                continue
            missing.append(path_arg)
    return missing
