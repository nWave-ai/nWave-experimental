"""Unit tests for SessionStart hook handler.

Tests all behaviors via handle_session_start() driving port.
Test budget: 8 behaviors x 2 = 16 unit tests max.
(3 new behaviors added for housekeeping integration: B6, B7, B8)
"""

import io
import json
from unittest.mock import MagicMock, patch

from des.application.update_check_service import UpdateCheckResult, UpdateStatus


class TestSessionStartHandlerUpdateAvailable:
    """B1: UPDATE_AVAILABLE writes additionalContext JSON to stdout."""

    def test_writes_additional_context_json_to_stdout(self, capsys):
        """UPDATE_AVAILABLE writes valid JSON with additionalContext key."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            latest="2.0.0",
            changelog="New features",
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        assert "additionalContext" in payload

    def test_additional_context_contains_local_latest_changelog(self, capsys):
        """additionalContext includes local version, latest version, and changelog."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            latest="3.1.0",
            changelog="- Fix A\n- Fix B",
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.5.0",
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            handle_session_start()

        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        msg = payload["additionalContext"]
        assert "1.5.0" in msg
        assert "3.1.0" in msg
        assert "Fix A" in msg


class TestSessionStartHandlerUpToDate:
    """B2: UP_TO_DATE produces no stdout, exits 0."""

    def test_no_stdout_and_exit_0_when_up_to_date(self, capsys):
        """UP_TO_DATE: stdout is empty, exit code 0."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""


class TestSessionStartHandlerSkip:
    """B3: SKIP produces no stdout, exits 0."""

    def test_no_stdout_and_exit_0_when_skip(self, capsys):
        """SKIP: stdout is empty, exit code 0."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(status=UpdateStatus.SKIP)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""


class TestSessionStartHandlerFailOpen:
    """B4: Any exception exits 0 (fail-open) - session must not be blocked."""

    def test_exception_in_service_factory_exits_0_with_no_output(self, capsys):
        """Exception building service: exits 0, no stdout output."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service",
                side_effect=RuntimeError("boom"),
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            exit_code = handle_session_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""

    def test_exception_in_check_for_updates_exits_0_with_no_output(self, capsys):
        """Exception in check_for_updates: exits 0, no stdout output."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.side_effect = RuntimeError("network error")
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""


class TestSessionStartHandlerOutputFormat:
    """B5: Output JSON format matches specification."""

    def test_output_format_matches_spec_with_changelog(self, capsys):
        """Output format: {"additionalContext": "nWave update available: {local} → {latest}. Changes: {changelog}"}"""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            latest="2.0.0",
            changelog="changelog text",
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            handle_session_start()

        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        expected = "nWave update available: 1.0.0 \u2192 2.0.0. Changes: changelog text"
        assert payload["additionalContext"] == expected

    def test_output_format_without_changelog(self, capsys):
        """Output format when changelog is None: Changes field is empty."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            latest="2.0.0",
            changelog=None,
        )

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            handle_session_start()

        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        expected = "nWave update available: 1.0.0 \u2192 2.0.0. Changes: "
        assert payload["additionalContext"] == expected


class TestSessionStartHandlerHousekeepingIntegration:
    """B6-B8: Housekeeping is called at session start with independent failure isolation."""

    def test_handle_session_start_calls_run_housekeeping(self):
        """B6: handle_session_start() invokes _run_housekeeping exactly once."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._run_housekeeping"
            ) as mock_hk,
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        mock_hk.assert_called_once()

    def test_housekeeping_failure_does_not_prevent_update_check(self):
        """B7: Exception in _run_housekeeping does not skip update check."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._run_housekeeping",
                side_effect=RuntimeError("housekeeping failed"),
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        mock_svc.check_for_updates.assert_called_once()

    def test_housekeeping_runs_before_update_check(self):
        """B8: _run_housekeeping is called before update check service is built."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        call_order = []

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        def record_housekeeping(*args, **kwargs):
            call_order.append("housekeeping")

        def record_update_check_build(des_config):
            call_order.append("update_check")
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            return mock_svc

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service",
                side_effect=record_update_check_build,
            ),
            patch(
                "des.adapters.drivers.hooks.session_start_handler._run_housekeeping",
                side_effect=record_housekeeping,
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            handle_session_start()

        assert call_order == ["housekeeping", "update_check"]

    def test_des_config_instance_shared_between_housekeeping_and_update_check(self):
        """B9: The same DESConfig object is passed to _run_housekeeping and UpdateCheckService.

        Step 03-01 AC: 'DESConfig shared between housekeeping and update check.'
        A single DESConfig() instance is created in handle_session_start() and
        passed to both operations — confirmed by identity (is), not equality (==).
        """
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        captured: dict = {}

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)

        def capture_housekeeping_config(des_config):
            captured["housekeeping_config"] = des_config

        def capture_update_check_config(des_config):
            captured["update_check_config"] = des_config
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            return mock_svc

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service",
                side_effect=capture_update_check_config,
            ),
            patch(
                "des.adapters.drivers.hooks.session_start_handler._run_housekeeping",
                side_effect=capture_housekeeping_config,
            ),
            patch("sys.stdin", io.StringIO("{}")),
        ):
            handle_session_start()

        assert "housekeeping_config" in captured, "_run_housekeeping was not called"
        assert "update_check_config" in captured, (
            "_build_update_check_service was not called"
        )
        assert captured["housekeeping_config"] is captured["update_check_config"], (
            "DESConfig must be the same object passed to both housekeeping and update check"
        )
