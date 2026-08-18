"""Run 8 (B): Auto-root Read/Grep/Glob source/test lockdown.

Root Read four test files (`test_update_check.py`, `test_create_check.py`,
`test_get_check.py`) plus `models.py`, and drafted a full test addition --
BEFORE its own Edit call was denied for touching role-owned source (GDP-1
violated: the denial arrived after the wasted reads, not before). Once
Auto is engaged, root's `Read`/`Grep`/`Glob` may only reach the docs/config
authority roots this repo's own guidance names -- everything else,
including any real implementation or test file, is denied up front.

Drives the real handler end-to-end (stdin -> stdout JSON / exit code), the
same harness shape as `test_auto_root_bash_lockdown.py`.
"""

from __future__ import annotations

import io
import json

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


def _transcript(tmp_path, *, auto: bool, mode_select: bool = False):
    transcript = tmp_path / "transcript.jsonl"
    lines = []
    if auto:
        lines.append(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
        )
    if mode_select:
        lines.append(
            {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-mode-select"}}
        )
    transcript.write_text(
        "\n".join(json.dumps(line) for line in lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    return str(transcript)


def _stdin(
    *, tool_name: str, tool_input: dict, transcript_path: str, cwd: str, **identity: str
) -> str:
    payload: dict[str, object] = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "transcript_path": transcript_path,
        "cwd": cwd,
    }
    payload.update(identity)
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


class TestAutoRootSourceReadDenied:
    @pytest.mark.parametrize(
        "tool_name,tool_input",
        [
            ("Read", {"file_path": "src/des/cli/dispatch.py"}),
            ("Read", {"file_path": "tests/des/unit/cli/test_dispatch.py"}),
            ("Read", {"file_path": "hc/api/models.py"}),
            ("Read", {"file_path": "src/some/README.md"}),  # nested, not top-level
            ("Grep", {"pattern": "def foo", "path": "src/des/cli"}),
            ("Glob", {"pattern": "*.py", "path": "hc/api/tests"}),
        ],
        ids=[
            "read_source_py",
            "read_test_py",
            "read_nested_models_py",
            "read_nested_readme_not_top_level",
            "grep_scoped_to_source_dir",
            "glob_scoped_to_test_dir",
        ],
    )
    def test_source_and_test_paths_are_denied(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_name, tool_input
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name=tool_name,
                tool_input=tool_input,
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        assert exit_code == 2
        assert payload["decision"] == "block"
        reason = payload["reason"]
        assert "WHAT:" in reason and "WHY:" in reason and "HOW:" in reason
        assert "des code-fact" in reason


class TestAutoRootSourceReadAllowed:
    @pytest.mark.parametrize(
        "tool_name,tool_input",
        [
            ("Read", {"file_path": "templates/docs/api.md"}),
            ("Read", {"file_path": "docs/product/roadmap.md"}),
            ("Read", {"file_path": "docs/delivery-contracts/auto-x.json"}),
            ("Read", {"file_path": "CLAUDE.md"}),
            ("Read", {"file_path": "AGENTS.md"}),
            ("Read", {"file_path": "README.md"}),
            ("Read", {"file_path": "TOP_LEVEL_NOTES.md"}),
            ("Read", {"file_path": ".nwave/wave-active/active.json"}),
            ("Grep", {"pattern": "TODO", "path": "docs"}),
            ("Glob", {"pattern": "*.md", "path": "docs/product"}),
        ],
        ids=[
            "api_docs",
            "product_roadmap",
            "delivery_contract_json",
            "claude_md",
            "agents_md",
            "readme_md",
            "top_level_arbitrary_md",
            "nwave_config_json",
            "grep_scoped_to_docs",
            "glob_scoped_to_docs",
        ],
    )
    def test_docs_and_config_paths_are_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path, tool_name, tool_input
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name=tool_name,
                tool_input=tool_input,
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_path_outside_the_repo_is_not_auto_root_blocked(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        outside_dir = tmp_path.parent / "outside-the-repo"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "notes.py"
        outside_file.write_text("x = 1\n", encoding="utf-8")
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": str(outside_file)},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_subagent_reading_source_is_unaffected(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "src/des/cli/dispatch.py"},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
                agent_type="nw-software-crafter",
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "Auto-root" not in payload.get("reason", "")

    def test_root_not_yet_auto_engaged_is_unaffected_by_this_guard(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=False, mode_select=False)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Read",
                tool_input={"file_path": "src/des/cli/dispatch.py"},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "des code-fact" not in payload.get("reason", "")

    def test_unscoped_grep_with_no_path_is_unaffected(
        self, monkeypatch, capsys, audit_events, tmp_path
    ) -> None:
        transcript_path = _transcript(tmp_path, auto=True, mode_select=True)
        _exit_code, payload = _run(
            monkeypatch,
            capsys,
            _stdin(
                tool_name="Grep",
                tool_input={"pattern": "TODO"},
                transcript_path=transcript_path,
                cwd=str(tmp_path),
            ),
        )
        if payload is not None and payload.get("decision") == "block":
            assert "des code-fact" not in payload.get("reason", "")
