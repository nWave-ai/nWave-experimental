"""Ale's construction-over-file correction (2026-08-20): ATD's Bash
lockdown -- its entire Bash surface is `des fill-contract`, mirroring the
Auto-root Bash lockdown's own shape (shared injection-marker check, shared
quoted-heredoc discipline for the value payload). Pure-function coverage
plus a few end-to-end (stdin -> stdout JSON / exit code) checks, the same
harness shape as `test_auto_root_bash_lockdown.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


_VALID_STATUS = (
    "des fill-contract --repo-root /repo --delivery-id widget-color --status"
)
_VALID_FIELD_HEREDOC = (
    "des fill-contract --repo-root /repo --delivery-id widget-color "
    "--target pkg/widget.py --field justification <<'NW_FILL'\n"
    "Widget gains a ColorValidator helper.\n"
    "NW_FILL"
)
_VALID_OUTCOME_HEREDOC = (
    "des fill-contract --repo-root /repo --delivery-id widget-color "
    "--field outcome <<'NW_FILL'\n"
    "Widget gains a validated color attribute.\n"
    "NW_FILL"
)


class TestPureEvaluator:
    def test_status_query_is_allowed(self) -> None:
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(_VALID_STATUS)
            is None
        )

    def test_field_heredoc_call_is_allowed(self) -> None:
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _VALID_FIELD_HEREDOC
            )
            is None
        )

    def test_contract_level_field_heredoc_call_is_allowed(self) -> None:
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _VALID_OUTCOME_HEREDOC
            )
            is None
        )

    def test_empty_command_is_blocked(self) -> None:
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command("")
        assert result is not None
        assert result["decision"] == "block"

    def test_non_string_command_is_blocked(self) -> None:
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(None)
        assert result is not None

    @pytest.mark.parametrize(
        "operator",
        ["&&", "||", ";", "|", "&", "`", "$("],
    )
    def test_composition_operator_blocks_even_before_a_heredoc(
        self, operator: str
    ) -> None:
        command = f"des fill-contract --status {operator} rm -rf /"
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_field_call_without_a_heredoc_is_blocked(self) -> None:
        command = "des fill-contract --repo-root /repo --delivery-id id --field outcome"
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None
        assert "heredoc" in result["reason"].lower()

    def test_a_bare_argv_value_instead_of_a_heredoc_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            '--field outcome "some value"'
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_mechanical_field_name_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --field declared-imports <<'NW_FILL'\n"
            "cronsim.CronSim\n"
            "NW_FILL"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_a_non_fill_contract_des_subcommand_is_blocked(self) -> None:
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
            "des dispatch --repo-root /repo --delivery-contract x.json"
        )
        assert result is not None

    def test_git_command_is_blocked(self) -> None:
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
            "git status"
        )
        assert result is not None

    def test_unquoted_heredoc_delimiter_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --field justification <<NW_FILL\n"
            "real value\n"
            "NW_FILL"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_missing_terminator_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --field justification <<'NW_FILL'\n"
            "real value\n"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_trailing_content_after_terminator_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --field justification <<'NW_FILL'\n"
            "real value\n"
            "NW_FILL\n"
            "echo pwned"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_status_with_a_trailing_extra_token_is_blocked(self) -> None:
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
            "des fill-contract --repo-root /repo --delivery-id id --status extra"
        )
        assert result is not None


def _stdin(*, tool_name: str, tool_input: dict, agent_type: str | None) -> str:
    payload: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestEndToEnd:
    def test_atd_status_call_passes_through_the_real_handler(
        self, monkeypatch, capsys
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": _VALID_STATUS},
                agent_type="nw-acceptance-designer",
            ),
        )
        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    def test_atd_disallowed_bash_is_blocked_by_the_real_handler(
        self, monkeypatch, capsys
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                agent_type="nw-acceptance-designer",
            ),
        )
        assert exit_code == 2
        assert payload is not None
        assert payload["decision"] == "block"

    def test_non_atd_subagent_bash_is_untouched_by_this_lockdown(
        self, monkeypatch, capsys
    ) -> None:
        """The ATD-specific lockdown never fires for a different role --
        `nw-software-crafter`'s own broad Bash surface is unaffected."""
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                agent_type="nw-software-crafter",
            ),
        )
        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"
