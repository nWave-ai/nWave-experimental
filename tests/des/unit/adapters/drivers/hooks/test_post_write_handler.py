"""Hook-harness tests for `handle_post_write` (ADR-SSOT-002 Section 4/4b
item 1): the PostToolUse oracle-write classifier. Mirrors the existing
`handle_pre_write` test shape (`test_k3a_additional_context_channel.py`) --
`sys.stdin` patched to the exact JSON payload the real hook receives,
handler driven directly, stdout captured via `capsys`.

Advisory-only by construction: every scenario asserts `exit_code == 0`
(this handler never blocks -- see its own module docstring).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from des.adapters.drivers.hooks import post_write_handler as adapter


_ORACLE_RELATIVE = "pkg/tests/test_widget.py"

#: A python -c invocation that deterministically prints a real assertion
#: failure and exits 1 -- crafted so `is_oracle_linked` still recognizes it
#: as citing `_ORACLE_RELATIVE` (a trailing pytest-shaped argv tail after
#: `-c CODE`, ignored by the script itself, satisfies the SAME pytest-
#: command/file-argument recognizer a real `pytest <file>` invocation
#: would) -- deterministic output beats a real pytest run against a
#: fixture file for THIS test's purposes.
#: Classification here is exit code + declared-symbol match (never a
#: Python-vocabulary text pattern) -- the RED script must cite the
#: contract's own declared symbol (`Widget`) to land as right-reason.
_RED_SCRIPT = (
    "print(\"ImportError: cannot import name 'Widget'\"); import sys; sys.exit(1)"
)
_UNRELATED_FAILURE_SCRIPT = (
    "print('  File \\'x.py\\', line 3'); print('SyntaxError: invalid syntax'); "
    "import sys; sys.exit(1)"
)
_GREEN_SCRIPT = "print('1 passed')"


def _command(script: str) -> dict:
    return {
        "executable": {"kind": "toolchain", "name": sys.executable},
        "arguments": ["-c", script, "pytest", _ORACLE_RELATIVE],
    }


def _seed_contract(
    repo_root: Path, *, route: str = "RED_TO_GREEN", script: str = _RED_SCRIPT
) -> None:
    contracts_dir = repo_root / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True)
    contract = {
        "delivery-route": route,
        "targets": {
            "pkg/widget.py": {"justification": "creates Widget", "overlap": ""}
        },
        "acceptance-tests": {"locator": _ORACLE_RELATIVE},
        "verification-scope": {"commands": [_command(script)]},
    }
    (contracts_dir / "widget-color.json").write_text(
        json.dumps(contract), encoding="utf-8"
    )


def _stdin(
    repo_root: Path,
    *,
    tool_name: str = "Write",
    file_path: str | None = None,
    agent_type: str | None = "nw-acceptance-designer",
) -> str:
    payload: dict = {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path or str(repo_root / _ORACLE_RELATIVE)},
        "cwd": str(repo_root),
    }
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return json.dumps(payload)


def _run(monkeypatch, capsys, stdin: str) -> tuple[int, dict | None]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = adapter.handle_post_write()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out) if out else None
    return exit_code, payload


def _context(payload: dict | None) -> str:
    assert payload is not None
    return payload["hookSpecificOutput"]["additionalContext"]


def test_red_right_reason_is_relayed(monkeypatch, capsys, tmp_path: Path) -> None:
    _seed_contract(tmp_path, route="RED_TO_GREEN", script=_RED_SCRIPT)
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path))
    assert exit_code == 0
    assert "ORACLE-WRITE-CLASSIFICATION: RED-right-reason" in _context(payload)


def test_failure_citing_no_declared_symbol_is_relayed_as_wrong_reason(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    _seed_contract(tmp_path, route="RED_TO_GREEN", script=_UNRELATED_FAILURE_SCRIPT)
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path))
    assert exit_code == 0
    assert "ORACLE-WRITE-CLASSIFICATION: RED-wrong-reason" in _context(payload)


def test_already_green_for_red_to_green_is_flagged(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    _seed_contract(tmp_path, route="RED_TO_GREEN", script=_GREEN_SCRIPT)
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path))
    assert exit_code == 0
    assert "ORACLE-WRITE-CLASSIFICATION: GREEN-for-RED_TO_GREEN" in _context(payload)


def test_green_to_green_passing_is_expected(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    _seed_contract(tmp_path, route="GREEN_TO_GREEN", script=_GREEN_SCRIPT)
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path))
    assert exit_code == 0
    assert "ORACLE-WRITE-CLASSIFICATION: GREEN-as-expected" in _context(payload)


def test_non_atd_role_is_silent(monkeypatch, capsys, tmp_path: Path) -> None:
    _seed_contract(tmp_path)
    exit_code, payload = _run(
        monkeypatch,
        capsys,
        _stdin(tmp_path, agent_type="nw-software-crafter"),
    )
    assert exit_code == 0
    assert payload is None


def test_root_write_with_no_agent_type_is_silent(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    _seed_contract(tmp_path)
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path, agent_type=None))
    assert exit_code == 0
    assert payload is None


def test_write_outside_any_contracts_oracle_locator_is_silent(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    _seed_contract(tmp_path)
    unrelated = tmp_path / "pkg" / "widget.py"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("x = 1\n", encoding="utf-8")
    exit_code, payload = _run(
        monkeypatch, capsys, _stdin(tmp_path, file_path=str(unrelated))
    )
    assert exit_code == 0
    assert payload is None


def test_no_delivery_contracts_dir_is_silent(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    exit_code, payload = _run(monkeypatch, capsys, _stdin(tmp_path))
    assert exit_code == 0
    assert payload is None


def test_empty_stdin_allows_silently(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    exit_code = adapter.handle_post_write()
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""


def test_malformed_json_allows_silently(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    exit_code = adapter.handle_post_write()
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""
