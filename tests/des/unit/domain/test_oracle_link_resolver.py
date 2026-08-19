"""Unit tests for the shared oracle-link helpers (extracted from
`des.cli._oracle_red_reason_refusal`, now the SSOT both that module and
`des.domain.oracle_write_classifier` import)."""

from __future__ import annotations

from pathlib import Path

from des.domain.oracle_link_resolver import (
    command_argv,
    is_oracle_linked,
    oracle_forms,
)


def test_oracle_forms_includes_dotted_and_path_spellings() -> None:
    assert oracle_forms("hc/api/tests/test_x.py") == {
        "hc.api.tests.test_x",
        "hc/api/tests/test_x.py",
    }


def test_oracle_forms_empty_for_empty_locator() -> None:
    assert oracle_forms("") == set()


def test_is_oracle_linked_matches_django_test_label() -> None:
    command = {
        "executable": {"kind": "repository", "path": "manage.py"},
        "arguments": ["test", "hc.api.tests.test_x"],
    }
    assert is_oracle_linked(command, "hc/api/tests/test_x.py") is True


def test_is_oracle_linked_matches_pytest_path() -> None:
    command = {
        "executable": {"kind": "toolchain", "name": "pytest"},
        "arguments": ["-q", "hc/api/tests/test_x.py"],
    }
    assert is_oracle_linked(command, "hc/api/tests/test_x.py") is True


def test_is_oracle_linked_false_for_unrelated_command() -> None:
    command = {
        "executable": {"kind": "repository", "path": "manage.py"},
        "arguments": ["test", "hc.api.tests.test_other"],
    }
    assert is_oracle_linked(command, "hc/api/tests/test_x.py") is False


def test_command_argv_resolves_repository_executable(tmp_path: Path) -> None:
    command = {
        "executable": {"kind": "repository", "path": "manage.py"},
        "arguments": ["test"],
    }
    argv = command_argv(tmp_path, command)
    assert argv == [str(tmp_path / "manage.py"), "test"]


def test_command_argv_resolves_toolchain_executable(tmp_path: Path) -> None:
    command = {"executable": {"kind": "toolchain", "name": "pytest"}, "arguments": []}
    assert command_argv(tmp_path, command) == ["pytest"]
