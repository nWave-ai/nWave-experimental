"""Unit tests for SessionStart hook handler.

Tests all behaviors via handle_session_start() driving port.
Test budget: 11 behaviors x 2 = 22 unit tests max.
(3 new behaviors added for housekeeping integration: B6, B7, B8)
(2 new behaviors added for substrate probe wiring: B10, B11)
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from des.application.update_check_service import UpdateCheckResult, UpdateStatus


@pytest.fixture(autouse=True)
def _silence_probe(request):
    """Silence substrate probe by default so tests that don't test probe are unaffected.

    Tests in TestSessionStartHandlerSubstrateProbe patch run_probe themselves
    and are excluded from this autouse fixture via marker.
    """
    if request.node.get_closest_marker("probe_test"):
        yield
        return
    with patch(
        "des.adapters.drivers.hooks.session_start_handler.run_probe",
        return_value="",
    ):
        yield


@pytest.fixture(autouse=True)
def _silence_orchestrator_affordance(monkeypatch):
    """Neutralize the orchestrator-affordance injection (slice-01) so tests
    that assert an empty/single-line stdout keep asserting their OWN
    scenario's output, not the new always-on affordance additionalContext.

    handle_session_start now unconditionally injects the affordance loaded
    from the shipped nWave/data/orchestrator-affordance/*.md (which exist on
    disk), a by-design zero-empty-stdout change ("fires every session" per
    the charter). This mirrors `_silence_probe` for run_probe.
    """
    monkeypatch.setattr(
        "des.adapters.drivers.hooks.session_start_handler.load_orchestrator_affordance",
        lambda assets_dir: None,
    )


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
        # Wrapped form for context injection + visible systemMessage.
        assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "additionalContext" in payload["hookSpecificOutput"]
        assert "systemMessage" in payload

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
        msg = payload["hookSpecificOutput"]["additionalContext"]
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


class TestBuildUpdateOutputContract:
    """Regression: update notice must be user-visible AND injected via the wrapped form.

    Bug: the handler emitted a bare {"additionalContext": ...}. That form is (a)
    never shown to the user and (b) dropped by current Claude Code versions, so
    no update notice ever surfaced. The payload must carry a top-level
    systemMessage (visible) plus hookSpecificOutput.additionalContext (canonical
    context injection).
    """

    def test_payload_has_visible_message_and_wrapped_context(self):
        from des.adapters.drivers.hooks.session_start_handler import (
            _build_update_output,
        )

        payload = _build_update_output(
            local="3.17.0", latest="3.18.0", changelog="- thing"
        )

        # Visible, top-level (not nested) -> rendered to the user at startup.
        assert payload["systemMessage"] == (
            "nWave update available: 3.17.0 → 3.18.0. Run /nw-update to update."
        )
        # Wrapped form -> reliably injected into the model context.
        hso = payload["hookSpecificOutput"]
        assert hso["hookEventName"] == "SessionStart"
        assert hso["additionalContext"] == (
            "nWave update available: 3.17.0 → 3.18.0. Changes: - thing"
        )
        # The bare form must NOT be present at top level (the original bug).
        assert "additionalContext" not in payload


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
        assert payload["hookSpecificOutput"]["additionalContext"] == expected
        # Visible message shown to the user (no changelog body, just the prompt).
        assert payload["systemMessage"] == (
            "nWave update available: 1.0.0 \u2192 2.0.0. Run /nw-update to update."
        )

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
        assert payload["hookSpecificOutput"]["additionalContext"] == expected

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


class TestSessionStartHandlerSubstrateProbe:
    """B10-B11: substrate probe advisory written to stderr when non-empty; silent on healthy install.

    The advisory is a plain-text (non-JSON) line. stdout is the channel every
    consumer parses as JSON, so the advisory MUST NOT land there -- it goes to
    stderr, where it stays visible to a terminal watcher without touching the
    parsed channel.
    """

    @pytest.mark.probe_test
    def test_advisory_written_to_stderr_when_probe_returns_non_empty(
        self, capsys, tmp_path
    ):
        """B10: run_probe() non-empty advisory is written to stderr, not stdout."""
        import io

        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )
        from des.application.update_check_service import UpdateCheckResult, UpdateStatus

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)
        stdin_envelope = json.dumps({"cwd": str(tmp_path)})

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler.run_probe",
                return_value="advisory line\n",
            ),
            patch("sys.stdin", io.StringIO(stdin_envelope)),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.err == "advisory line\n"
        assert captured.out == ""

    @pytest.mark.probe_test
    def test_no_output_when_probe_returns_empty(self, capsys, tmp_path):
        """B11: run_probe() empty string produces no advisory output on either stream."""
        import io

        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )
        from des.application.update_check_service import UpdateCheckResult, UpdateStatus

        result = UpdateCheckResult(status=UpdateStatus.UP_TO_DATE)
        stdin_envelope = json.dumps({"cwd": str(tmp_path)})

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler.run_probe",
                return_value="",
            ),
            patch("sys.stdin", io.StringIO(stdin_envelope)),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        captured = capsys.readouterr()
        # When update check returns UP_TO_DATE and probe returns empty, neither
        # stream carries anything.
        assert captured.out == ""
        assert captured.err == ""


class TestSessionStartHandlerAdvisoryDoesNotCorruptStdoutJson:
    """Regression: a plain-text health advisory must not corrupt stdout's JSON.

    Property under test: when handle_session_start ALSO emits a JSON envelope
    on stdout in the same invocation (e.g. UPDATE_AVAILABLE), and the
    substrate probe reports issues in that same invocation, stdout -- taken as
    a whole -- must still parse as exactly one JSON object. Asserting only
    "the advisory is on stderr" is a weaker property: it would still pass if
    stdout ALSO carried a stray copy of the advisory. This test parses the
    captured stdout to prove the channel itself is clean.
    """

    @pytest.mark.probe_test
    def test_stdout_parses_as_json_when_probe_reports_issues_alongside_a_json_write(
        self, capsys, tmp_path
    ):
        import io

        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )
        from des.application.update_check_service import UpdateCheckResult, UpdateStatus

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE, latest="9.9.9", changelog=None
        )
        advisory = (
            "⚠ nWave install health check: 2 issues found"
            " (run `nwave-ai doctor` for details).\n"
        )
        stdin_envelope = json.dumps({"cwd": str(tmp_path)})

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch(
                "des.adapters.drivers.hooks.session_start_handler.run_probe",
                return_value=advisory,
            ),
            patch("sys.stdin", io.StringIO(stdin_envelope)),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "install health check" in captured.err
        # The property: stdout, taken whole, parses as ONE JSON object.
        payload = json.loads(captured.out)
        assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


class TestSessionStartHandlerSingleCombinedPayload:
    """Regression for techdebt rows:
    session-start-handler-multiple-uncoordinated-prints-corrupt-stdout-json /
    session-start-handler-two-emitters-still-use-broken-bare-additionalcontext-form.

    Before the fix, `handle_session_start` called `print(json.dumps(...))`
    independently for up to six triggers (workflow-mode guidance, update
    notice, gate-affordance nudge, hook-version skew, orchestrator affordance)
    -- two of them (workflow guidance, skew) using the BARE
    ``{"additionalContext": ...}`` form the module's own docstring says
    current Claude Code drops. When 2+ triggers fired in one session, stdout
    held several JSON objects on separate lines: not valid JSON as a whole,
    and any consumer parsing the full stdout as one document lost every
    contribution but the first.
    """

    def test_four_simultaneous_triggers_produce_one_parseable_json_object(
        self, tmp_path, capsys
    ):
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        project = tmp_path
        (project / ".nwave").mkdir()
        feature_dir = project / "docs" / "feature" / "demo"
        feature_dir.mkdir(parents=True)
        (feature_dir / "feature-delta.md").write_text("delta\n", encoding="utf-8")

        result = UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE, latest="9.9.9", changelog="notes"
        )
        stdin_payload = json.dumps({"cwd": str(project)})

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch(
                "des.adapters.drivers.hooks.session_start_handler."
                "_read_installed_hook_version",
                return_value="0.9.0",
            ),
            patch("sys.stdin", io.StringIO(stdin_payload)),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        lines = [line for line in out.splitlines() if line.strip()]
        # RED before the fix: 4 triggers fired here (workflow guidance,
        # update notice, gate-affordance nudge, hook-version skew), each
        # printing its own JSON line -- 4 lines, not one JSON document.
        assert len(lines) == 1, (
            f"expected exactly one combined stdout line, got {len(lines)}: {out!r}"
        )
        payload = json.loads(lines[0])  # must not raise json.JSONDecodeError

        # The bare form must never reach stdout -- only wrapped inside
        # hookSpecificOutput.
        assert "additionalContext" not in payload
        hso = payload["hookSpecificOutput"]
        assert hso["hookEventName"] == "SessionStart"
        ctx = hso["additionalContext"]

        assert "atdd_pure" in ctx, "workflow-mode guidance missing from combined ctx"
        assert "9.9.9" in ctx, "update notice missing from combined ctx"
        assert "des feature-delta-doctor" in ctx or "des dispatch" in ctx, (
            "gate-affordance nudge missing from combined ctx"
        )
        assert "HookVersionSkew" in ctx, "hook-version-skew finding missing from ctx"
        assert payload["systemMessage"], "visible update notice must be preserved"

    def test_single_trigger_still_uses_wrapped_form_never_bare(self, tmp_path, capsys):
        """The skew finding alone (no other trigger) must reach stdout wrapped,
        never as the bare ``{"additionalContext": ...}`` form it used before
        the fix."""
        from des.adapters.drivers.hooks.session_start_handler import (
            handle_session_start,
        )

        project = tmp_path
        (project / ".nwave").mkdir()
        stdin_payload = json.dumps({"cwd": str(project)})
        result = UpdateCheckResult(status=UpdateStatus.SKIP)

        with (
            patch(
                "des.adapters.drivers.hooks.session_start_handler._build_update_check_service"
            ) as mock_factory,
            patch(
                "des.adapters.drivers.hooks.session_start_handler._get_local_version",
                return_value="1.0.0",
            ),
            patch(
                "des.adapters.drivers.hooks.session_start_handler."
                "_read_installed_hook_version",
                return_value="0.9.0",
            ),
            # Isolate the skew finding: this fresh `.nwave/` project would
            # also fire the workflow-mode guidance, which is a separate
            # trigger already covered by the multi-trigger test above.
            patch(
                "des.adapters.drivers.hooks.session_start_handler."
                "_workflow_mode_session_guidance",
                return_value=None,
            ),
            patch("sys.stdin", io.StringIO(stdin_payload)),
        ):
            mock_svc = MagicMock()
            mock_svc.check_for_updates.return_value = result
            mock_factory.return_value = mock_svc

            exit_code = handle_session_start()

        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        assert out, "expected a skew finding on stdout"
        payload = json.loads(out)
        assert "additionalContext" not in payload, (
            "skew finding must never use the bare top-level additionalContext "
            "form -- it is dropped by current Claude Code"
        )
        assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "HookVersionSkew" in payload["hookSpecificOutput"]["additionalContext"]
