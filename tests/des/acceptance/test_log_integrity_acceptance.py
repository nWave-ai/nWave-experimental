"""Acceptance coverage for transcript-context extraction."""

from des.adapters.drivers.hooks.subagent_stop_handler import (
    extract_des_context_from_transcript,
)


class TestMissingTranscript:
    """A missing transcript has no recoverable DES context."""

    def test_missing_transcript_returns_none(self, tmp_path) -> None:
        result = extract_des_context_from_transcript(
            str(tmp_path / "does-not-exist.jsonl")
        )
        assert result is None
