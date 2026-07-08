"""Acceptance tests -- proactive gate-affordance nudge at SessionStart.

Feature: wave-entry-gate-affordance-nudge (WS-17-A / GDP-2, slice-01).
Charter: docs/product/expectations/wave-entry-gate-affordance-nudge/
         the-session-start-hook-proactively-surfaces-the-gate-affordance.md
Feature-delta: docs/feature/wave-entry-gate-affordance-nudge/feature-delta.md

Drives the production contract (not yet implemented -- DISTILL active-RED
scaffold, ADR-025):

    def build_gate_affordance_nudge(cwd: str | None) -> str | None

Returns the proactive nudge text when an active feature-delta
(``docs/feature/<id>/feature-delta.md``) exists under ``cwd``, else ``None``.
Fail-open: any error degrades to ``None``, never raises.

RED-not-BROKEN discipline (P1/P3, `nw-distill-red-scaffolding`): the absent
symbol is imported ONLY inside a test-body helper (`_get_build_gate_affordance_nudge`),
never at module top, so pytest collection never touches the absent name. The
helper converts the resulting ``ImportError`` into a semantic ``AssertionError``
(RED == MISSING_FUNCTIONALITY), never a collection/BROKEN failure.

Test functions are MODULE-LEVEL `def test_...` (not class methods) so the
carpaccio gate's pytest-regression AST counter (which counts module-level
`test_*` defs) finds them.
"""

from __future__ import annotations

import io
import json
import os
from unittest.mock import MagicMock, patch

import pytest


def _get_build_gate_affordance_nudge():
    """Import ``build_gate_affordance_nudge``, RED-not-BROKEN (P1/P3).

    The symbol does not exist yet in
    ``des.adapters.drivers.hooks.session_start_handler`` (the production
    contract this feature adds). Importing it here -- inside a helper called
    from within a test body, never at module top -- keeps the absent name out
    of pytest's collection phase (P1). The resulting ``ImportError`` is
    converted to a semantic ``AssertionError`` so the fail-for-right-reason
    classification is MISSING_FUNCTIONALITY (correct RED), not IMPORT_ERROR
    (wrong RED / BLOCK).
    """
    try:
        from des.adapters.drivers.hooks.session_start_handler import (
            build_gate_affordance_nudge,
        )
    except ImportError as exc:
        raise AssertionError(
            "build_gate_affordance_nudge not yet implemented in "
            "des.adapters.drivers.hooks.session_start_handler -- RED scaffold "
            f"(production function missing): {exc}"
        ) from exc
    return build_gate_affordance_nudge


def _write_active_feature_delta(repo_root, feature_id: str = "demo") -> None:
    """Create ``docs/feature/<feature_id>/feature-delta.md`` under repo_root."""
    feature_dir = repo_root / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "feature-delta.md").write_text(
        "# demo feature-delta\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Scenario 1 (POSITIVE) -- active feature-delta present
# ---------------------------------------------------------------------------


def test_nudge_names_producing_tool_and_proactive_framing(tmp_path):
    # covers: charter-expected-1
    _write_active_feature_delta(tmp_path)
    build_gate_affordance_nudge = _get_build_gate_affordance_nudge()

    nudge = build_gate_affordance_nudge(str(tmp_path))

    assert nudge is not None, (
        "expected a non-None nudge when an active feature-delta exists under cwd"
    )
    assert nudge.strip() != "", "nudge text must be non-empty"
    assert "des feature-delta-doctor" in nudge or "des dispatch" in nudge, (
        "nudge must name at least one concrete producing tool by literal "
        "string (`des feature-delta-doctor` and/or `des dispatch`)"
    )
    assert "before" in nudge.lower(), (
        "nudge must name the proactive framing -- satisfy gates BEFORE they fire"
    )


# ---------------------------------------------------------------------------
# Scenario 2 (POSITIVE) -- handle_session_start stays fail-open (exit 0)
# AND surfaces the nudge when an active feature-delta exists under cwd
# ---------------------------------------------------------------------------


def test_handler_stdout_contains_nudge_when_feature_delta_active(tmp_path, capsys):
    _write_active_feature_delta(tmp_path)

    from des.adapters.drivers.hooks.session_start_handler import (
        handle_session_start,
    )
    from des.application.update_check_service import (
        UpdateCheckResult,
        UpdateStatus,
    )

    skip_result = UpdateCheckResult(status=UpdateStatus.SKIP)
    stdin_payload = json.dumps({"cwd": str(tmp_path)})

    with (
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._build_update_check_service"
        ) as mock_factory,
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._session_cwd_is_atdd_pure",
            return_value=False,
        ),
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates.return_value = skip_result
        mock_factory.return_value = mock_service

        with patch("sys.stdin", io.StringIO(stdin_payload)):
            exit_code = handle_session_start()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() != "", (
        "expected the gate-affordance nudge on stdout when an active "
        "feature-delta exists under cwd -- RED until "
        "build_gate_affordance_nudge is wired into handle_session_start"
    )
    output = json.loads(captured.out.strip())
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "des feature-delta-doctor" in ctx or "des dispatch" in ctx


def test_handler_exits_zero_when_no_feature_delta(tmp_path):
    # Charter point 3: the hook returns exit 0 in BOTH states. Witnessed
    # at the HANDLER level for the absent-feature-delta state. RED-not-
    # BROKEN: gate on the absent symbol first (semantic AssertionError
    # while missing), then spy that handle_session_start actually invokes
    # the nudge builder -- so this witnesses WIRING + fail-open, not the
    # already-true bare exit-0.
    real_fn = _get_build_gate_affordance_nudge()

    from des.adapters.drivers.hooks.session_start_handler import (
        handle_session_start,
    )
    from des.application.update_check_service import (
        UpdateCheckResult,
        UpdateStatus,
    )

    # tmp_path has NO docs/feature/<id>/feature-delta.md.
    skip_result = UpdateCheckResult(status=UpdateStatus.SKIP)
    stdin_payload = json.dumps({"cwd": str(tmp_path)})

    with (
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._build_update_check_service"
        ) as mock_factory,
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._session_cwd_is_atdd_pure",
            return_value=False,
        ),
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            ".build_gate_affordance_nudge",
            wraps=real_fn,
        ) as nudge_spy,
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates.return_value = skip_result
        mock_factory.return_value = mock_service

        with patch("sys.stdin", io.StringIO(stdin_payload)):
            exit_code = handle_session_start()

    assert exit_code == 0, (
        "the hook must return exit 0 when no feature-delta is present "
        "(fail-open, charter point 3)"
    )
    # Witness the wiring: handle_session_start must invoke the nudge
    # builder even in the no-feature-delta state (it returns None there).
    # RED until wired -- assert_called_once() raises AssertionError if not.
    nudge_spy.assert_called_once()


def test_handler_exits_zero_when_feature_delta_malformed(tmp_path):
    # Charter point 4: a malformed feature-delta must NOT crash the hook --
    # the None return from build_gate_affordance_nudge must be absorbed and
    # the handler still exits 0. RED-not-BROKEN via the same symbol gate.
    real_fn = _get_build_gate_affordance_nudge()

    # Malformed: feature-delta.md exists as a DIRECTORY where a file is
    # expected -- build_gate_affordance_nudge must degrade to None.
    feature_dir = tmp_path / "docs" / "feature" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").mkdir()

    from des.adapters.drivers.hooks.session_start_handler import (
        handle_session_start,
    )
    from des.application.update_check_service import (
        UpdateCheckResult,
        UpdateStatus,
    )

    skip_result = UpdateCheckResult(status=UpdateStatus.SKIP)
    stdin_payload = json.dumps({"cwd": str(tmp_path)})

    with (
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._build_update_check_service"
        ) as mock_factory,
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            "._session_cwd_is_atdd_pure",
            return_value=False,
        ),
        patch(
            "des.adapters.drivers.hooks.session_start_handler"
            ".build_gate_affordance_nudge",
            wraps=real_fn,
        ) as nudge_spy,
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates.return_value = skip_result
        mock_factory.return_value = mock_service

        with patch("sys.stdin", io.StringIO(stdin_payload)):
            exit_code = handle_session_start()

    assert exit_code == 0, (
        "a malformed feature-delta must not crash the hook -- the None "
        "return must be absorbed and the handler still exit 0 (charter "
        "point 4)"
    )
    # Witness the wiring: the handler must invoke the nudge builder even on
    # a malformed feature-delta (its None return is fail-open, not a crash).
    # RED until wired -- assert_called_once() raises AssertionError if not.
    nudge_spy.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 3 (POSITIVE) -- malformed/unreadable feature-delta degrades to
# None, never raises
# ---------------------------------------------------------------------------


def test_nudge_is_none_when_feature_delta_path_is_unreadable(tmp_path):
    # feature-delta.md is a DIRECTORY where a file is expected --
    # read_text() raises IsADirectoryError; build_gate_affordance_nudge
    # must catch this and degrade to None, never propagate.
    feature_dir = tmp_path / "docs" / "feature" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").mkdir()

    build_gate_affordance_nudge = _get_build_gate_affordance_nudge()

    result = build_gate_affordance_nudge(str(tmp_path))

    assert result is None, (
        "a malformed/unreadable feature-delta must degrade to None, not raise"
    )


def test_nudge_is_none_when_feature_delta_file_is_permission_denied(tmp_path):
    feature_dir = tmp_path / "docs" / "feature" / "demo"
    feature_dir.mkdir(parents=True)
    delta_file = feature_dir / "feature-delta.md"
    delta_file.write_text("# demo\n", encoding="utf-8")
    delta_file.chmod(0o000)

    try:
        build_gate_affordance_nudge = _get_build_gate_affordance_nudge()
        result = build_gate_affordance_nudge(str(tmp_path))
        # `os.access` performs the real syscall-level check, so it
        # correctly reports True when running as root (common in
        # sandboxes/CI containers) even though the mode bits say
        # otherwise -- the fail-open assertion below only applies when
        # the permission bit was actually honored, so the test is never
        # flaky under a root-executed suite; either branch must never
        # raise (already proven by reaching this line without one).
        permission_actually_denied = not os.access(delta_file, os.R_OK)
    finally:
        delta_file.chmod(0o644)

    if permission_actually_denied:
        assert result is None, (
            "an unreadable feature-delta (permission denied) must "
            "degrade to None, not raise"
        )
    else:
        assert result is not None, (
            "running as root bypasses the permission bit -- the file is "
            "readable, so a nudge is the correct outcome here"
        )


# ---------------------------------------------------------------------------
# Scenario 4 (NEGATIVE) -- no active feature-delta => no nudge
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "seed_repo",
    [
        lambda root: None,
        lambda root: (root / "docs" / "feature").mkdir(parents=True),
        lambda root: (root / "docs" / "feature" / "demo").mkdir(parents=True),
    ],
    ids=["no-docs-tree", "empty-feature-dir", "feature-dir-without-delta-file"],
)
def test_nudge_is_not_emitted_when_no_active_feature_delta(tmp_path, seed_repo):
    seed_repo(tmp_path)
    build_gate_affordance_nudge = _get_build_gate_affordance_nudge()

    result = build_gate_affordance_nudge(str(tmp_path))

    assert result is None, (
        "the WRONG outcome (a nudge with no active feature-delta) must NOT be produced"
    )
