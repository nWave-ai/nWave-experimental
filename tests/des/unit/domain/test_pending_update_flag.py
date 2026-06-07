"""Unit tests for PendingUpdateFlag domain dataclass."""

from __future__ import annotations

import pytest

from des.domain.pending_update_flag import PendingUpdateFlag


def _make(**overrides: object) -> PendingUpdateFlag:
    defaults: dict[str, object] = {
        "pm": "pipx",
        "pm_binary_abspath": "/usr/local/bin/pipx",
        "target_version": "1.2.3",
        "requested_at": "2026-04-16T10:00:00Z",
    }
    defaults.update(overrides)
    return PendingUpdateFlag(**defaults)  # type: ignore[arg-type]


class TestPendingUpdateFlagShould:
    def test_construct_with_all_required_fields(self) -> None:
        flag = _make()
        assert flag.pm == "pipx"
        assert flag.pm_binary_abspath == "/usr/local/bin/pipx"
        assert flag.target_version == "1.2.3"
        assert flag.requested_at == "2026-04-16T10:00:00Z"
        assert flag.attempt_count == 0
        assert flag.last_error is None

    @pytest.mark.parametrize(
        "count,expected",
        [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (99, True),
        ],
    )
    def test_report_attempt_cap_reached_when_count_at_or_above_three(
        self, count: int, expected: bool
    ) -> None:
        flag = _make(attempt_count=count)
        assert flag.attempt_cap_reached() is expected

    def test_round_trip_through_dict_for_json_persistence(self) -> None:
        original = _make(attempt_count=2, last_error="network timeout")
        restored = PendingUpdateFlag.from_dict(original.to_dict())
        assert restored == original

    def test_reject_invalid_pm_literal_in_from_dict(self) -> None:
        payload = _make().to_dict()
        payload["pm"] = "brew"
        with pytest.raises(ValueError, match="pm"):
            PendingUpdateFlag.from_dict(payload)
