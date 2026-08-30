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
    "--batch <<'NW_FILL'\n[]\nNW_FILL"
)
# The provider-safe batch-file carrier transport: no heredoc, no JSON
# anywhere on the command line -- ATD wrote the identical array to the
# deterministic carrier file first.
_VALID_BATCH_FILE_COMMAND = (
    "des fill-contract --repo-root /repo --delivery-id widget-color "
    "--batch --batch-file"
)
_VALID_OUTCOME_HEREDOC = _VALID_FIELD_HEREDOC
_VALID_BATCH_HEREDOC = (
    "des fill-contract --repo-root /repo --delivery-id widget-color "
    "--batch <<'NW_FILL'\n"
    '[{"field":"outcome","value":"Widget gains a validated color attribute."},'
    '{"field":"justification","target":"pkg/widget.py",'
    '"value":"Reuse the existing validator."}]\n'
    "NW_FILL"
)

# K4 camp6 denial-RCA C-f2: the EXACT body data from p2's outcome fill --
# it carries `checks/<uuid:code>` (literal `<` and `>` bytes) inside a
# QUOTED heredoc body, which is opaque to the shell by definition. A scan
# that reads the body sees "composition operators" in inert data.
_P2_EXACT_OUTCOME_HEREDOC = (
    "des fill-contract --repo-root "
    "/tmp/nwave-k4-camp6-0253d8dce/campaign/pair-2/nwave "
    "--delivery-id auto-d6c8911618f6e8d5 --batch <<'NW_FILL'\n"
    "Feature: Maintenance windows for checks. An operator can declare "
    "recurring maintenance windows on a check. While a check is inside one "
    "of its maintenance windows, a failure must not deliver a notification "
    "on any channel, and the outage must still be visible in that check's "
    "own history. The management API v3 check representation (shared "
    'v1/v2/v3) gains one field: "maintenance_windows": [{"schedule": '
    '"0 2 * * SUN", "duration": 3600}], readable via GET and writable via '
    "POST/PUT on the existing checks/<uuid:code> endpoint.\n"
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

    def test_batch_heredoc_call_is_allowed(self) -> None:
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _VALID_BATCH_HEREDOC
            )
            is None
        )

    def test_status_first_query_is_allowed(self) -> None:
        """K4 camp6 denial-RCA C-f1 (false rejection): p2's EXACT status
        query -- `--status` in FIRST position -- was rejected as "not a
        well-formed invocation", while the same invocation with
        `--status` last passed 4/4 times in p3. `--status` is a
        value-less flag: the parser is flag-order-insensitive."""
        command = (
            "des fill-contract --status --repo-root "
            "/tmp/nwave-k4-camp6-0253d8dce/campaign/pair-2/nwave "
            "--delivery-id auto-d6c8911618f6e8d5"
        )
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
            is None
        )

    def test_status_mid_position_query_is_allowed(self) -> None:
        command = "des fill-contract --repo-root /repo --status --delivery-id id"
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
            is None
        )

    def test_p2_exact_heredoc_body_with_angle_bracket_data_is_allowed(self) -> None:
        """The quoted body is opaque bytes: `checks/<uuid:code>` in the
        DATA must never trip the composition-operator scan."""
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _P2_EXACT_OUTCOME_HEREDOC
            )
            is None
        )

    def test_heredoc_with_a_single_trailing_newline_is_allowed(self) -> None:
        """`...\\nNW_FILL\\n` and `...\\nNW_FILL` are the same shell
        construct -- a Bash tool call routinely ends with a final newline.
        Rejecting it fell through to the whole-command scan, which then
        blamed the opaque body's data as a composition operator."""
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _P2_EXACT_OUTCOME_HEREDOC + "\n"
            )
            is None
        )

    def test_invalid_header_never_scans_the_quoted_body_as_shell(self) -> None:
        """A heredoc whose HEADER is invalid (mechanical field) with p2's
        angle-bracket data in the body: the rejection must blame the
        header, never claim a composition operator from the opaque body."""
        command = _P2_EXACT_OUTCOME_HEREDOC.replace(
            "--batch", "--retired-field declared-imports"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None
        assert "shell-composition" not in result["reason"]
        assert "header" in result["reason"]

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
        command = "des fill-contract --repo-root /repo --delivery-id id --retired-field outcome"
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None
        assert "well-formed" in result["reason"].lower()

    def test_batch_call_without_a_heredoc_is_blocked(self) -> None:
        command = "des fill-contract --repo-root /repo --delivery-id id --batch"
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None
        assert "heredoc" in result["reason"].lower()

    def test_a_bare_argv_value_instead_of_a_heredoc_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            '--retired-field outcome "some value"'
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_mechanical_field_name_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --retired-field declared-imports <<'NW_FILL'\n"
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
            "--target pkg/widget.py --retired-field justification <<NW_FILL\n"
            "real value\n"
            "NW_FILL"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_missing_terminator_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --retired-field justification <<'NW_FILL'\n"
            "real value\n"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_trailing_content_after_terminator_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id "
            "--target pkg/widget.py --retired-field justification <<'NW_FILL'\n"
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


class TestBatchFileCarrierTransport:
    """Ale's provider-safe carrier correction: a Bash command may carry
    --batch-file instead of a heredoc, but must then carry NO JSON at all."""

    def test_batch_file_call_with_no_heredoc_is_allowed(self) -> None:
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(
                _VALID_BATCH_FILE_COMMAND
            )
            is None
        )

    @pytest.mark.parametrize(
        "command",
        [
            "des fill-contract --batch-file --repo-root /repo --delivery-id id --batch",
            "des fill-contract --repo-root /repo --batch --delivery-id id --batch-file",
            "des fill-contract --batch --batch-file --repo-root /repo --delivery-id id",
        ],
        ids=["batch-file-first", "batch-file-last", "batch-file-middle"],
    )
    def test_batch_file_flag_is_order_insensitive(self, command: str) -> None:
        """K4 camp6 denial-RCA C-f1's own lesson applied to the new flag:
        position must never matter for a value-less flag."""
        assert (
            pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
            is None
        )

    def test_batch_file_without_batch_is_blocked(self) -> None:
        command = (
            "des fill-contract --repo-root /repo --delivery-id id --status --batch-file"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_batch_file_call_still_carrying_json_on_argv_is_blocked(self) -> None:
        """--batch-file replaces the heredoc/stdin transport -- it is never
        an excuse to also put the JSON literally on the command line."""
        command = (
            "des fill-contract --repo-root /repo --delivery-id id --batch "
            '--batch-file [{"field":"outcome","value":"x"}]'
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None

    def test_batch_file_heredoc_combination_is_rejected(self) -> None:
        """--batch-file and the NW_FILL heredoc are mutually exclusive JSON
        transports: heredoc compatibility is preserved only in the ABSENCE
        of --batch-file. Combining both is a refusal, not a tolerated hybrid."""
        command = (
            "des fill-contract --repo-root /repo --delivery-id widget-color "
            "--batch --batch-file <<'NW_FILL'\n[]\nNW_FILL"
        )
        result = pre_tool_use_handler._evaluate_atd_fill_contract_bash_command(command)
        assert result is not None
        assert result["decision"] == "block"


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
    def test_atd_batch_call_passes_through_the_real_handler(
        self, monkeypatch, capsys
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": _VALID_BATCH_HEREDOC},
                agent_type="nw-acceptance-designer",
            ),
        )
        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

    def test_atd_batch_file_call_passes_through_the_real_handler(
        self, monkeypatch, capsys
    ) -> None:
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": _VALID_BATCH_FILE_COMMAND},
                agent_type="nw-acceptance-designer",
            ),
        )
        assert exit_code == 0
        assert payload is None or payload.get("decision") != "block"

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
