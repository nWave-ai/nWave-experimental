"""Unit tests for the centralized ISO-8601 UTC round-trip idiom."""

from datetime import datetime, timezone

from des.domain.iso_utc import format_iso_utc, parse_iso_utc


class TestParseIsoUtc:
    def test_parses_trailing_z_as_utc_offset(self):
        parsed = parse_iso_utc("2026-01-26T10:00:00Z")

        assert parsed == datetime(2026, 1, 26, 10, 0, 0, tzinfo=timezone.utc)

    def test_parses_explicit_offset_form_unchanged(self):
        parsed = parse_iso_utc("2026-01-26T10:00:00+00:00")

        assert parsed == datetime(2026, 1, 26, 10, 0, 0, tzinfo=timezone.utc)

    def test_preserves_microseconds(self):
        parsed = parse_iso_utc("2026-01-26T10:00:00.123456Z")

        assert parsed.microsecond == 123456


class TestFormatIsoUtc:
    def test_formats_utc_datetime_with_trailing_z(self):
        value = datetime(2026, 1, 26, 10, 0, 0, tzinfo=timezone.utc)

        assert format_iso_utc(value) == "2026-01-26T10:00:00Z"

    def test_round_trip_through_parse_and_format(self):
        original = "2026-01-26T10:00:00Z"

        assert format_iso_utc(parse_iso_utc(original)) == original
