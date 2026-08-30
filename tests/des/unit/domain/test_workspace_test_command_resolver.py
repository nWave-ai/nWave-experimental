"""Unit tests for the whole-suite-command detector (K4 Run 12 admission).

Run 12 repro: the subject's root CLAUDE.md states "Run the subject's own
tests: `k4-fixture-venv/bin/python manage.py test hc.api --noinput`" but
`verification-scope.commands` only ever carried the new oracle's own narrow
test. Detection must fire on that labeled shape and must not fire on
unrelated prose that merely contains a keyword with no attached command
(this repo's own CLAUDE.md says "Never run the whole suite" as a swarm rule).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from des.domain.workspace_test_command_resolver import (
    declared_whole_suite_command,
    resolve_preservation_vector,
)


def _contract(*command_argument_lists: list[str]) -> dict:
    return {
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "toolchain", "name": "python"},
                    "arguments": arguments,
                }
                for arguments in command_argument_lists
            ]
        }
    }


def test_declares_none_when_claude_md_absent(tmp_path: Path) -> None:
    assert declared_whole_suite_command(tmp_path) is None


def test_declares_none_on_keyword_with_no_attached_command(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "- Never run the whole suite, and never fire two heavy gates at "
        "once. Gate on `MemAvailable`.\n",
        encoding="utf-8",
    )
    assert declared_whole_suite_command(tmp_path) is None


def test_extracts_the_labeled_whole_suite_command(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "- Run the subject's own tests: "
        "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n",
        encoding="utf-8",
    )
    assert declared_whole_suite_command(tmp_path) == [
        "k4-fixture-venv/bin/python",
        "manage.py",
        "test",
        "hc.api",
        "--noinput",
    ]


def test_new_contract_commands_bind_repository_script_bytes_at_b(
    tmp_path: Path,
) -> None:
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    contract = _contract([])
    contract["verification-scope"]["commands"] = [
        {"executable": {"path": "./verify.sh"}, "arguments": []}
    ]
    vector = resolve_preservation_vector(
        tmp_path, contract, contract_locator="new-delivery.json"
    )
    assert vector.argv == (("./verify.sh",),)
    assert vector.sources == (
        ("verify.sh", hashlib.sha256(script.read_bytes()).hexdigest()),
    )


def test_ambient_command_without_a_base_owned_source_is_an_evidence_gap(
    tmp_path: Path,
) -> None:
    contract = _contract([])
    contract["verification-scope"]["commands"] = [
        {"executable": {"name": "git"}, "arguments": ["diff", "--check"]}
    ]
    with pytest.raises(ValueError, match="no base-owned preservation command"):
        resolve_preservation_vector(tmp_path, contract)


def test_unambiguous_literal_direct_script_is_a_preservation_vector(
    tmp_path: Path,
) -> None:
    document = tmp_path / "authority.md"
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    line = "./verify.sh"
    document.write_text(f"# Verify\n\n```sh\n{line}\n```\n", encoding="utf-8")
    contract = {
        "verification-scope": {
            "literal-script-block": {
                "locator": "authority.md#verify",
                "content-digest": "sha256:" + hashlib.sha256(line.encode()).hexdigest(),
                "lines": [line],
            }
        }
    }
    vector = resolve_preservation_vector(tmp_path, contract)
    assert vector.argv == (("./verify.sh",),)
    assert vector.sources[1] == (
        "verify.sh",
        hashlib.sha256(script.read_bytes()).hexdigest(),
    )


def test_opaque_literal_is_not_treated_as_preservation(tmp_path: Path) -> None:
    document = tmp_path / "authority.md"
    document.write_text(
        "# Verify\n\n```sh\n./verify.sh | tee result\n```\n", encoding="utf-8"
    )
    contract = {
        "verification-scope": {
            "literal-script-block": {
                "locator": "authority.md#verify",
                "content-digest": "sha256:"
                + hashlib.sha256(b"./verify.sh | tee result").hexdigest(),
                "lines": ["./verify.sh | tee result"],
            }
        }
    }
    with pytest.raises(ValueError, match="direct repository script"):
        resolve_preservation_vector(tmp_path, contract)
