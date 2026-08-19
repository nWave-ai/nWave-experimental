"""Unit tests for the whole-suite-command detector (K4 Run 12 admission).

Run 12 repro: the subject's root CLAUDE.md states "Run the subject's own
tests: `k4-fixture-venv/bin/python manage.py test hc.api --noinput`" but
`verification-scope.commands` only ever carried the new oracle's own narrow
test. Detection must fire on that labeled shape and must not fire on
unrelated prose that merely contains a keyword with no attached command
(this repo's own CLAUDE.md says "Never run the whole suite" as a swarm rule).
"""

from __future__ import annotations

from pathlib import Path

from des.domain.workspace_test_command_resolver import (
    contract_covers_whole_suite,
    declared_whole_suite_command,
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


def test_oracle_only_scope_does_not_cover_the_declared_whole_suite(
    tmp_path: Path,
) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "- Run the subject's own tests: "
        "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n",
        encoding="utf-8",
    )
    contract = _contract(["manage.py", "test", "hc.api.tests.test_maintenance_windows"])

    assert contract_covers_whole_suite(tmp_path, contract) is False


def test_added_whole_suite_command_covers_it(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "- Run the subject's own tests: "
        "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n",
        encoding="utf-8",
    )
    contract = _contract(
        ["manage.py", "test", "hc.api.tests.test_maintenance_windows"],
        ["manage.py", "test", "hc.api"],
    )

    assert contract_covers_whole_suite(tmp_path, contract) is True


def test_no_declared_command_means_nothing_to_check(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# a project with no such line\n", encoding="utf-8"
    )
    contract = _contract(["manage.py", "test", "hc.api.tests.test_x"])

    assert contract_covers_whole_suite(tmp_path, contract) is True
