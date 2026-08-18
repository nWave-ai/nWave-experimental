"""K4 architecture gap: Auto-root Bash/Task lockdown.

Auto's root process (the process that itself observed `Skill(nw-auto)` in
its own transcript, carrying neither `agent_id` nor `agent_type`) is
restricted to a closed allowlist of `git` read/stage/commit subcommands on
Bash, and is denied `TaskCreate`/`TaskUpdate` outright — that task-signal
authority belongs to a dispatched role, not the root orchestrator.

Drives the real handler end-to-end (stdin -> stdout JSON / exit code), the
same harness shape as `test_k3a_additional_context_channel.py`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler
from scripts.analysis.k4.preflight import des_subcommands_root_is_told_to_run


def _transcript(
    tmp_path, *, auto: bool, mode_select: bool = False, malformed: bool = False
):
    transcript = tmp_path / "transcript.jsonl"
    if malformed:
        transcript.write_text("not-json\n", encoding="utf-8")
        return str(transcript)
    lines = []
    if auto:
        lines.append(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
        )
    if mode_select:
        lines.append(
            {
                "type": "tool_use",
                "name": "Skill",
                "input": {"skill": "nw-mode-select"},
            }
        )
    transcript.write_text(
        "\n".join(json.dumps(line) for line in lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    return str(transcript)


def _stdin(
    *,
    tool_name: str,
    tool_input: dict,
    transcript_path: str | None = None,
    **identity: str,
) -> str:
    payload: dict[str, object] = {"tool_name": tool_name, "tool_input": tool_input}
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestAutoRootBashAllowlist:
    """A confirmed Auto-root process's Bash calls: only a bare, single
    `git status|diff|rev-parse|branch|worktree|add|commit` survives."""

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git diff",
            "git rev-parse HEAD",
            "git branch --show-current",
            "git worktree list",
            "git add -A",
            'git commit -m "message"',
        ],
    )
    def test_clean_git_allowlisted_command_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        # Not vetoed by the Auto-root allowlist: whatever the downstream
        # outcome, it must not be the auto-root-specific block payload.
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_non_git_command_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "ls -la"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"] or "git" in payload["reason"]

    def test_disallowed_git_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git push origin main"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    @pytest.mark.parametrize(
        "command",
        [
            "git status && rm -rf /",
            "git status || echo pwned",
            "git status; rm -rf /",
            "git status | tee /tmp/x",
            "git status & rm -rf /",
            "git status `whoami`",
            "git status $(whoami)",
            "git status < /etc/passwd",
            "git status > /etc/passwd",
            "git status\nrm -rf /",
            "git status\rrm -rf /",
            "git status; git push origin main --force",
        ],
    )
    def test_every_injection_operator_blocks_even_with_leading_allowed_git(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_injection_operator_short_circuits_before_shlex_split(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """The lexical reject fires BEFORE `shlex.split` -- a poisoned
        allowlist string must never reach tokenization or the allow-list
        comparison."""

        def _boom(*args, **kwargs):
            raise AssertionError("shlex.split must not run for an operator input")

        monkeypatch.setattr(pre_tool_use_handler.shlex, "split", _boom)
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status && rm -rf /"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"


class TestAutoRootBashDesAllowlist:
    """A confirmed Auto-root process's Bash calls also allow a bare, single
    `des dispatch|validate-delivery-contract|charter-scaffold|
    resolve-charters|code-fact` invocation --
    the direct-cutover spine's only hook-controller-free CLI seam."""

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatch F-EXAMPLE",
            "des validate-delivery-contract docs/feature/x/delivery-contract.json",
            "des charter-scaffold F-EXAMPLE",
            "des resolve-charters --repo-root /tmp/repo --delivery-id auto-abc123 --examine true",
            "des code-fact query.atoms-in-file --root /tmp/repo/sendalerts.py",
        ],
        ids=[
            "dispatch",
            "validate-delivery-contract",
            "charter-scaffold",
            "resolve-charters",
            "code-fact",
        ],
    )
    def test_clean_des_allowlisted_command_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_des_missing_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "des"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatc F-EXAMPLE",
            "des Dispatch F-EXAMPLE",
            "des validate_delivery_contract x.json",
            "des status",
            "des help",
            "des dispatch-all",
        ],
        ids=[
            "near_miss_typo",
            "near_miss_case",
            "near_miss_underscore",
            "unknown_status",
            "unknown_help",
            "unknown_dispatch_all",
        ],
    )
    def test_des_unknown_or_near_miss_subcommand_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]

    @pytest.mark.parametrize(
        "command",
        [
            "des dispatch F-EXAMPLE && rm -rf /",
            "des dispatch F-EXAMPLE || echo pwned",
            "des dispatch F-EXAMPLE; rm -rf /",
            "des dispatch F-EXAMPLE | tee /tmp/x",
            "des dispatch F-EXAMPLE & rm -rf /",
            "des dispatch `whoami`",
            "des dispatch $(whoami)",
            "des dispatch F-EXAMPLE < /etc/passwd",
            "des dispatch F-EXAMPLE > /etc/passwd",
            "des dispatch F-EXAMPLE\nrm -rf /",
            "des dispatch F-EXAMPLE\rrm -rf /",
            "des dispatch F-EXAMPLE; des dispatch OTHER",
        ],
    )
    def test_des_composition_operator_blocks_even_with_leading_allowed_subcommand(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    def test_des_extra_executable_prefix_is_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "python -m des dispatch F-EXAMPLE"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]


_REPO_ROOT = Path(__file__).resolve().parents[6]
_K4_TASK_TXT = _REPO_ROOT / "scripts" / "analysis" / "k4" / "task.txt"
_NW_AUTO_SKILL_MD = _REPO_ROOT / "nWave" / "skills" / "nw-auto" / "SKILL.md"


class TestAutoRootBashAllowlistCoversSkillMandatedSubcommands:
    """Regression guard for the `des resolve-charters` drift class: the
    root's Auto-root Bash allowlist must be a SUPERSET of every `des
    <subcommand>` nw-auto/SKILL.md's root steps actually instruct root to
    run -- never the reverse (the allowlist may legitimately carry extra
    subcommands other callers of this same gate need, e.g. `charter-
    scaffold` for nw-bugfix). A missing entry here reproduces the exact
    installed defect: the skill tells root to run a command the hook then
    denies.

    The fence parser itself now lives in `scripts/analysis/k4/preflight.py`
    (`des_subcommands_root_is_told_to_run`), imported here rather than
    redefined -- `route_walk_steps` in that same module drives its own
    root-Bash coverage checks off the identical parser, so this guard and
    the permanent preflight gate can never carry two independently
    hand-typed mandated-subcommand lists that silently drift apart.
    """

    def test_parser_is_not_vacuous(self) -> None:
        """A parser that finds nothing can never fail the coverage check
        below -- a silent, undiscriminating pass. Pin the known baseline
        so a SKILL.md format change that breaks the fence parser is
        itself caught, not silently swallowed."""
        found = des_subcommands_root_is_told_to_run(
            _NW_AUTO_SKILL_MD.read_text(encoding="utf-8")
        )
        assert {"dispatch", "prepare-ordinary-request", "resolve-charters"} <= found

    def test_every_skill_mandated_subcommand_is_allowlisted(self) -> None:
        mandated = des_subcommands_root_is_told_to_run(
            _NW_AUTO_SKILL_MD.read_text(encoding="utf-8")
        )
        allowed = pre_tool_use_handler._AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS
        missing = mandated - allowed
        assert not missing, (
            f"nw-auto/SKILL.md instructs root to run {sorted(missing)}, but "
            "the Auto-root Bash allowlist does not permit it -- the hook "
            "would deny root's own documented next step."
        )


class TestAutoRootBashValueSeedStdinHeredoc:
    """ADR-SSOT-002 'VALUE-SEED transport' mandates delivering the exact
    value-seed bytes to `des prepare-ordinary-request`'s stdin, never
    shell-reinterpreted -- never argv/env/temp-file. The generic
    composition-operator block would otherwise make that producer
    permanently unreachable from Auto-root Bash, since both stdin-feeding
    constructs (`|`, `<<`) are unconditionally rejected. Exactly one shape
    is carved out: a bounded `des prepare-ordinary-request <argv>` header
    ending in a QUOTED heredoc redirect, an opaque body, and a terminator
    line that is exactly the delimiter with nothing after it."""

    _HEADER = (
        "des prepare-ordinary-request --size M --repo-root /tmp/repo "
        '--architecture-authority "ARCHITECTURE-COVERED: docs/x.md#anchor" '
        "--delivery-route RED_TO_GREEN --examine true --independent-review false"
    )

    @staticmethod
    def _heredoc(
        body: str,
        *,
        header: str | None = None,
        quote: str = "'",
        delimiter: str = "NW_SEED",
    ) -> str:
        head = (
            header
            if header is not None
            else TestAutoRootBashValueSeedStdinHeredoc._HEADER
        )
        return f"{head} <<{quote}{delimiter}{quote}\n{body}\n{delimiter}"

    def test_plain_seed_heredoc_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc("the value seed text")
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_double_quoted_delimiter_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc("the value seed text", quote='"')
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_flag_equals_value_token_form_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        header = (
            "des prepare-ordinary-request --size=M --repo-root=/tmp/repo "
            '--architecture-authority="ARCHITECTURE-COVERED: docs/x.md#anchor" '
            "--delivery-route=RED_TO_GREEN --examine=true --independent-review=false"
        )
        command = self._heredoc("the value seed text", header=header)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_real_k4_task_body_containing_apostrophes_pipes_and_blank_lines_round_trips(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """The real seed corpus this repo already carries -- multi-line,
        blank lines, punctuation, no escaping applied -- must pass through
        the heredoc carve-out unblocked, exactly the property a quoted
        heredoc (vs. the abandoned printf-pipe shape) is chosen for."""
        seed_body = _K4_TASK_TXT.read_text(encoding="utf-8")
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc(seed_body)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_bare_ampersand_after_the_matched_shape_still_blocks(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """The exact bypass the reviewer found against the abandoned
        printf-pipe carve-out: a trailing `& <second command>` riding an
        otherwise-recognized shape must still block."""
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc("seed", header=self._HEADER + " & rm -rf ~")
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"

    @pytest.mark.parametrize(
        "command",
        [
            # unquoted delimiter -- shell would expand `$(...)`/backticks
            # inside the body; must never be trusted as opaque.
            f"{_HEADER} <<NW_SEED\nseed\nNW_SEED",
            # unterminated heredoc -- no line is exactly the delimiter
            f"{_HEADER} <<'NW_SEED'\nseed with no terminator",
            # extra command riding after the terminator line
            f"{_HEADER} <<'NW_SEED'\nseed\nNW_SEED\nrm -rf /",
            # a second heredoc redirect appended to the header
            f"{_HEADER} <<'NW_SEED' <<'OTHER'\nseed\nNW_SEED\nx\nOTHER",
            # bare & riding the header before the redirect
            f"{_HEADER} & rm -rf ~ <<'NW_SEED'\nseed\nNW_SEED",
            # composition marker inside the header prefix
            f"{_HEADER}; rm -rf / <<'NW_SEED'\nseed\nNW_SEED",
            # a flag outside the closed vocabulary
            "des prepare-ordinary-request --size M --unknown-flag x <<'NW_SEED'\nseed\nNW_SEED",
            # wrong subcommand
            "des dispatch F-EXAMPLE <<'NW_SEED'\nseed\nNW_SEED",
            # not even a des call
            "cat <<'NW_SEED'\nseed\nNW_SEED",
            # mismatched delimiter -- terminator does not match the opener
            f"{_HEADER} <<'NW_SEED'\nseed\nOTHER",
            # delimiter line has trailing content on the same line
            f"{_HEADER} <<'NW_SEED'\nseed\nNW_SEED extra",
        ],
        ids=[
            "unquoted_delimiter",
            "unterminated_heredoc",
            "trailing_command_after_terminator",
            "second_heredoc_redirect",
            "bare_ampersand_before_redirect",
            "semicolon_in_header",
            "unknown_flag",
            "wrong_des_subcommand",
            "not_a_des_call",
            "mismatched_delimiter",
            "trailing_content_on_terminator_line",
        ],
    )
    def test_anything_off_the_exact_seed_heredoc_shape_still_blocks(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"


class TestAutoRootBashValueSeedStdinHeredocResolveCharters:
    """Run 7 evidence: `des resolve-charters` now needs the SAME VALUE-SEED
    on stdin (to build the PO envelope on AUTHOR) that
    `des prepare-ordinary-request` does, and nw-auto/SKILL.md step 2
    documents the identical quoted-heredoc shape for it -- but the
    Auto-root Bash carve-out only ever recognized `prepare-ordinary-request`
    as a heredoc-eligible subcommand, so root's own documented next command
    was denied. The carve-out is generalized to the closed SET of seed-
    bearing producers, each with its own bounded flag vocabulary."""

    _HEADER = (
        "des resolve-charters --repo-root /tmp/repo "
        "--delivery-id auto-0123456789abcdef --examine true"
    )

    @staticmethod
    def _heredoc(
        body: str,
        *,
        header: str | None = None,
        quote: str = "'",
        delimiter: str = "NW_SEED",
    ) -> str:
        head = (
            header
            if header is not None
            else TestAutoRootBashValueSeedStdinHeredocResolveCharters._HEADER
        )
        return f"{head} <<{quote}{delimiter}{quote}\n{body}\n{delimiter}"

    def test_plain_seed_heredoc_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc("the value seed text")
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_double_quoted_delimiter_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc("the value seed text", quote='"')
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_flag_equals_value_token_form_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        header = (
            "des resolve-charters --repo-root=/tmp/repo "
            "--delivery-id=auto-0123456789abcdef --examine=true"
        )
        command = self._heredoc("the value seed text", header=header)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_real_k4_task_body_round_trips(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        seed_body = _K4_TASK_TXT.read_text(encoding="utf-8")
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        command = self._heredoc(seed_body)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    @pytest.mark.parametrize(
        "command",
        [
            # a flag outside resolve-charters' own closed vocabulary --
            # prepare-ordinary-request's flags must NOT leak across
            "des resolve-charters --repo-root /tmp/repo --delivery-id "
            "auto-0123456789abcdef --examine true --size M <<'NW_SEED'\nseed\nNW_SEED",
            # a subcommand outside the whole heredoc-eligible SET
            "des charter-scaffold --repo-root /tmp/repo --delivery-id "
            "auto-0123456789abcdef <<'NW_SEED'\nseed\nNW_SEED",
            # unquoted delimiter
            f"{_HEADER} <<NW_SEED\nseed\nNW_SEED",
            # unterminated
            f"{_HEADER} <<'NW_SEED'\nseed with no terminator",
            # trailing command after terminator
            f"{_HEADER} <<'NW_SEED'\nseed\nNW_SEED\nrm -rf /",
        ],
        ids=[
            "prepare_ordinary_request_flag_does_not_leak",
            "charter_scaffold_not_in_heredoc_set",
            "unquoted_delimiter",
            "unterminated_heredoc",
            "trailing_command_after_terminator",
        ],
    )
    def test_anything_off_the_exact_shape_still_blocks(
        self, monkeypatch, capsys, audit_events, tmp_path, command
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": command},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"


class TestAutoRootBashMalformedCommandFailsClosed:
    """Once Auto-root is armed, a malformed `command` (missing/empty/
    whitespace-only/non-string) must fail CLOSED -- blocked -- not fall
    through to mode-select or attribution as an implicit allow."""

    @pytest.mark.parametrize(
        "tool_input",
        [
            {},
            {"command": ""},
            {"command": "   \t  "},
            {"command": 12345},
        ],
        ids=["missing", "empty", "whitespace_only", "non_string"],
    )
    def test_malformed_command_is_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_input
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input=tool_input,
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "Auto-root" in payload["reason"]


class TestAutoRootTaskToolLockdown:
    @pytest.mark.parametrize("tool_name", ["TaskCreate", "TaskUpdate"])
    def test_task_create_update_blocked_for_auto_root(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_name
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(tool_name=tool_name, tool_input={}, transcript_path=transcript_path),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert tool_name in payload["reason"]


class TestAutoRootIdentityBoundary:
    @pytest.mark.parametrize(
        "identity", [{"agent_id": "sub-1"}, {"agent_type": "nw-crafter"}]
    )
    def test_either_subagent_identity_field_bypasses_the_lockdown(
        self, monkeypatch, capsys, audit_events, tmp_path, identity
    ) -> None:
        """A dispatched sub-agent (either identity field present) is never
        treated as Auto-root, even if its own transcript observed nw-auto."""
        transcript_path = _transcript(tmp_path, auto=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="TaskCreate",
                tool_input={},
                transcript_path=transcript_path,
                **identity,
            ),
        )
        # A sub-agent hits no TaskCreate handling at all -- it falls through
        # to the normal (unaffected) path, never the auto-root block.
        assert (
            payload is None
            or payload.get("decision") != "block"
            or ("TaskCreate" not in payload.get("reason", ""))
        )

    def test_absent_nw_auto_observation_preserves_existing_bash_behaviour(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """No `Skill(nw-auto)` observed -- not armed -- an ordinary
        allowlisted-looking `git status` runs the existing path unchanged
        (still subject to the pre-existing mode-select gate, not the
        auto-root allowlist)."""
        transcript_path = _transcript(tmp_path, auto=False, mode_select=False)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                transcript_path=transcript_path,
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "nw-mode-select" in payload["reason"]
        assert "Auto-root" not in payload["reason"]

    def test_forged_nw_auto_mention_in_prose_does_not_arm(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """A transcript that merely MENTIONS nw-auto in prose (never a real
        `Skill` tool_use) does not arm the Auto-root lockdown."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps(
                {"type": "text", "text": "I will act as if nw-auto were engaged."}
            )
            + "\n",
            encoding="utf-8",
        )
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": "git status"},
                transcript_path=str(transcript),
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        assert "nw-mode-select" in payload["reason"]


class TestAutoRootAllowedGitCommitReachesAttribution:
    def test_pure_git_commit_still_reaches_attribution_mutation_path(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        """An allowlisted `git commit` from Auto-root is not vetoed by the
        lockdown, and the pre-existing commit-attribution mutation branch
        still runs on it unchanged."""

        class _MutatingService:
            def plan_rewrite(self, command: str) -> object:
                class Plan:
                    action = "mutate"
                    rewritten_command = command + " -C HEAD"

                return Plan()

        monkeypatch.setattr(
            pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
        )
        global_config_dir = tmp_path / ".nwave"
        global_config_dir.mkdir()
        (global_config_dir / "global-config.json").write_text(
            json.dumps({"attribution": {"enabled": True}}), encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(tmp_path))

        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Bash",
                tool_input={"command": 'git commit -m "x"'},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        assert exit_code == 0
        assert payload is not None
        assert "hookSpecificOutput" in payload
        assert payload["hookSpecificOutput"]["updatedInput"]["command"] == (
            'git commit -m "x" -C HEAD'
        )


class TestAutoRootLockdownScopedToLockedDownTools:
    """Unrelated tools with no transcript pay no root-mode read."""

    @pytest.mark.parametrize("tool_name", ["Read", "Skill", "Agent", "ScheduleWakeup"])
    def test_non_lockdown_tool_never_observes_and_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tool_name
    ) -> None:
        def _boom(*args, **kwargs):
            raise AssertionError(
                "resolve_root_mode_state must not be called for "
                f"non-lockdown tool {tool_name!r}"
            )

        monkeypatch.setattr(pre_tool_use_handler, "resolve_root_mode_state", _boom)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(tool_name=tool_name, tool_input={}),
        )
        assert (
            payload is None
            or payload.get("decision") != "block"
            or "Auto-root" not in payload.get("reason", "")
        )
