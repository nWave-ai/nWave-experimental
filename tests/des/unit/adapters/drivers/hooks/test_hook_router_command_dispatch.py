"""`hook_router.main()` command dispatch -- every known command actually
reaches its handler.

Closes a real gap found while adding `subagent-stop` (stable-design report
2026-08-19 §1.1): the new route-branch's own handler import was silently
stripped by this environment's post-edit formatter (an "unused import" at
the moment the import was added, before the consuming branch existed) and
NOTHING in the existing test suite exercised `hook_router.main()` with
`sys.argv[1] == "subagent-stop"` end-to-end -- only `ruff check`'s static
`F821` caught the resulting `NameError`. These tests drive `main()` itself
(not the handler module directly) so a future re-break of this exact wiring
fails a test, not only a lint pass someone might skip.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from des.adapters.drivers.hooks import hook_router


def _run_router(monkeypatch, argv_command: str, stdin_text: str) -> int:
    monkeypatch.setattr("sys.argv", ["hook_router", argv_command])
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    with pytest.raises(SystemExit) as exc_info:
        hook_router.main()
    return exc_info.value.code


@pytest.fixture(autouse=True)
def active_project():
    with patch(
        "des.adapters.drivers.hooks.activation_gate._is_active_or_inactive_on_error",
        return_value=True,
    ):
        yield


class TestEveryKnownCommandReachesItsHandler:
    def test_subagent_start_dispatches_to_its_handler(
        self, monkeypatch, capsys
    ) -> None:
        exit_code = _run_router(
            monkeypatch,
            "subagent-start",
            json.dumps({"agent_type": "some-non-nw-agent"}),
        )
        assert exit_code == 0

    def test_subagent_stop_dispatches_to_its_handler(self, monkeypatch, capsys) -> None:
        exit_code = _run_router(
            monkeypatch,
            "subagent-stop",
            json.dumps({"agent_type": "some-non-nw-agent", "agent_id": "x"}),
        )
        assert exit_code == 0

    def test_unknown_command_reports_an_error(self, monkeypatch, capsys) -> None:
        exit_code = _run_router(monkeypatch, "not-a-real-command", "{}")
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "Unknown command" in out
