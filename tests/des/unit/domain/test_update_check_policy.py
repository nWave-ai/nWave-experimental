"""Unit tests for UpdateCheckPolicy domain rule.

Tests the pure policy for determining whether an update check should be
performed based on frequency windows, skipped versions, and first-run detection.

Test Budget: 5 distinct behaviors x 2 = 10 max unit tests.
Behaviors:
  1. frequency=never always SKIPs
  2. version in skipped_versions SKIPs
  3. absent update_check key (first run) returns CHECK
  4. last_checked within frequency window SKIPs
  5. last_checked outside frequency window returns CHECK
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from des.domain.update_check_policy import CheckDecision, UpdateCheckPolicy


class TestUpdateCheckPolicyNever:
    """Behavior 1: frequency=never always returns SKIP."""

    @pytest.fixture
    def policy(self):
        return UpdateCheckPolicy()

    def test_never_frequency_returns_skip(self, policy):
        """Given frequency=never, policy should always return SKIP."""
        result = policy.evaluate(
            frequency="never",
            last_checked=None,
            latest_version=None,
            skipped_versions=[],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.SKIP

    def test_never_frequency_skips_even_with_old_timestamp(self, policy):
        """Given frequency=never, SKIP even when last_checked is very old."""
        old_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
        result = policy.evaluate(
            frequency="never",
            last_checked=old_time,
            latest_version="1.0.0",
            skipped_versions=[],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.SKIP


class TestUpdateCheckPolicySkippedVersion:
    """Behavior 2: latest_version in skipped_versions returns SKIP."""

    @pytest.fixture
    def policy(self):
        return UpdateCheckPolicy()

    def test_skipped_version_returns_skip(self, policy):
        """Given latest_version in skipped list, policy returns SKIP."""
        result = policy.evaluate(
            frequency="daily",
            last_checked=datetime(2000, 1, 1, tzinfo=timezone.utc),
            latest_version="2.0.0",
            skipped_versions=["2.0.0", "1.9.0"],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.SKIP

    def test_non_skipped_version_is_not_skipped(self, policy):
        """Given latest_version NOT in skipped list, SKIP is not returned for this reason."""
        result = policy.evaluate(
            frequency="every_session",
            last_checked=None,
            latest_version="3.0.0",
            skipped_versions=["2.0.0", "1.9.0"],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.CHECK


class TestUpdateCheckPolicyFirstRun:
    """Behavior 3: absent update_check config (first run) returns CHECK."""

    @pytest.fixture
    def policy(self):
        return UpdateCheckPolicy()

    def test_first_run_no_config_returns_check(self, policy):
        """Given no config present (last_checked=None, no frequency), returns CHECK."""
        result = policy.evaluate(
            frequency=None,
            last_checked=None,
            latest_version=None,
            skipped_versions=[],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.CHECK


class TestUpdateCheckPolicyWithinWindow:
    """Behavior 4: last_checked within frequency window returns SKIP."""

    @pytest.fixture
    def policy(self):
        return UpdateCheckPolicy()

    @pytest.mark.parametrize(
        "frequency,hours_ago",
        [
            ("daily", 12),
            ("weekly", 100),
        ],
    )
    def test_within_window_returns_skip(self, policy, frequency, hours_ago):
        """Given last_checked within the window, policy returns SKIP."""
        current_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        last_checked = current_time - timedelta(hours=hours_ago)

        result = policy.evaluate(
            frequency=frequency,
            last_checked=last_checked,
            latest_version=None,
            skipped_versions=[],
            current_time=current_time,
        )
        assert result == CheckDecision.SKIP


class TestUpdateCheckPolicyOutsideWindow:
    """Behavior 5: last_checked outside frequency window returns CHECK."""

    @pytest.fixture
    def policy(self):
        return UpdateCheckPolicy()

    @pytest.mark.parametrize(
        "frequency,hours_ago",
        [
            ("daily", 25),
            ("weekly", 170),
            ("every_session", 1),
        ],
    )
    def test_outside_window_returns_check(self, policy, frequency, hours_ago):
        """Given last_checked outside the window (or every_session), returns CHECK."""
        current_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        last_checked = current_time - timedelta(hours=hours_ago)

        result = policy.evaluate(
            frequency=frequency,
            last_checked=last_checked,
            latest_version=None,
            skipped_versions=[],
            current_time=current_time,
        )
        assert result == CheckDecision.CHECK

    def test_every_session_with_no_last_checked_returns_check(self, policy):
        """every_session with no prior check always returns CHECK."""
        result = policy.evaluate(
            frequency="every_session",
            last_checked=None,
            latest_version=None,
            skipped_versions=[],
            current_time=datetime.now(timezone.utc),
        )
        assert result == CheckDecision.CHECK
