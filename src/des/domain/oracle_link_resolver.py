"""Pure helpers linking one `verification-scope.commands` entry to a
contract's own `acceptance-tests.locator` -- shared by `des dispatch`'s
BASE red-reason probe (`des.cli._oracle_red_reason_refusal`) and the
oracle-write PostToolUse classifier (`des.domain.oracle_write_classifier`).
Extracted from `_oracle_red_reason_refusal.py` (behavior-preserving move,
never a second algorithm) so a domain-layer consumer does not have to
import across the cli/domain boundary (AD-05: no shared logic in `cli/`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.verification_command_resolver import (
    django_test_labels,
    pytest_file_arguments,
)


if TYPE_CHECKING:
    from pathlib import Path


def command_argv(repo_root: Path, command: dict) -> list[str]:
    """The literal argv a `verification-scope.commands` entry projects to:
    `[path-or-name, *arguments]`, resolving a `repository`-kind executable
    against `repo_root`."""
    executable = command.get("executable", {})
    if executable.get("kind") == "repository":
        head = str(repo_root / str(executable.get("path", "")))
    else:
        head = str(executable.get("name", ""))
    return [head, *command.get("arguments", [])]


def oracle_forms(oracle_locator: str) -> set[str]:
    """The dotted-module-label and repository-relative-path spellings of
    one oracle locator -- either may legitimately appear in a verification
    command's own argv."""
    if not oracle_locator:
        return set()
    stem = oracle_locator[:-3] if oracle_locator.endswith(".py") else oracle_locator
    return {stem.replace("/", "."), oracle_locator}


def is_oracle_linked(command: dict, oracle_locator: str) -> bool:
    """True when `command` cites `oracle_locator` (either spelling) as a
    Django test label or a pytest file argument."""
    forms = oracle_forms(oracle_locator)
    if any(label in forms for label in django_test_labels(command)):
        return True
    return any(
        path_arg.split("::", 1)[0] in forms
        for path_arg in pytest_file_arguments(command)
    )
