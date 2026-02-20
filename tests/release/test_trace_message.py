"""Tests for scripts/release/trace_message.py

Composes traceability commit messages for cross-repo sync.
Two formats: RC (stage 2) and stable (stage 3, full chain).

BDD scenario mapping:
  - journey-rc-release.feature: "Cross-repo traceability is complete" (Scenario 11)
  - journey-stable-release.feature: "Full traceability chain in public repo commit" (Scenario 9)
  - US-RTR-006: Cross-Repo Traceability (all scenarios).
"""

import pytest

from scripts.release.trace_message import compose_trace_message


SAMPLE_SHA = "abc123def456789012345678901234567890abcd"
SAMPLE_PIPELINE_URL = (
    "https://github.com/Undeadgrishnackh/crafter-ai/actions/runs/12345"
)


class TestRCTraceMessage:
    """Traceability commit message for RC releases (Stage 2)."""

    def test_rc_message_contains_release_header(self):
        """Given stage=rc and version=1.1.22rc1,
        when composing the trace message,
        then the first line is 'chore(release): v1.1.22rc1'.
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        first_line = message.split("\n")[0]
        assert first_line == "chore(release): v1.1.22rc1"

    def test_rc_message_contains_source_sha(self):
        """The message body contains 'Source: nwave-dev@{sha}'.

        Maps to: nWave-beta commit message contains source SHA.
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert f"Source: nwave-dev@{SAMPLE_SHA}" in message

    def test_rc_message_contains_dev_tag(self):
        """The message body contains 'Dev tag: v1.1.22.dev3'.

        Maps to: nWave-beta commit message contains dev tag.
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert "Dev tag: v1.1.22.dev3" in message

    def test_rc_message_contains_pipeline_url(self):
        """The message body contains 'Pipeline: {url}'.

        Maps to: nWave-beta commit message contains pipeline run URL.
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert f"Pipeline: {SAMPLE_PIPELINE_URL}" in message

    def test_rc_message_does_not_contain_rc_or_stable_tags(self):
        """RC messages should NOT include RC tag or Stable tag fields
        (those are for Stage 3 only).
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert "RC tag:" not in message
        assert "Stable tag:" not in message

    def test_rc_message_full_format(self):
        """Full integration check for the RC message format.

        Expected:
            chore(release): v1.1.22rc1

            Source: nwave-dev@abc123def456789012345678901234567890abcd
            Dev tag: v1.1.22.dev3
            Pipeline: https://github.com/.../actions/runs/12345
        """
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        expected = (
            "chore(release): v1.1.22rc1\n"
            "\n"
            f"Source: nwave-dev@{SAMPLE_SHA}\n"
            "Dev tag: v1.1.22.dev3\n"
            f"Pipeline: {SAMPLE_PIPELINE_URL}"
        )
        assert message == expected


class TestStableTraceMessage:
    """Traceability commit message for stable releases (Stage 3, full chain)."""

    def test_stable_message_contains_release_header(self):
        """Given stage=stable and version=1.1.22,
        when composing the trace message,
        then the first line is 'chore(release): v1.1.22'.
        """
        message = compose_trace_message(
            stage="stable",
            version="1.1.22",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            rc_tag="v1.1.22rc1",
            stable_tag="v1.1.22",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        first_line = message.split("\n")[0]
        assert first_line == "chore(release): v1.1.22"

    def test_stable_message_contains_full_chain(self):
        """The stable message includes all four trace fields:
        Source, Dev tag, RC tag, Stable tag, Pipeline.

        Maps to: "Full traceability chain in public repo commit".
        """
        message = compose_trace_message(
            stage="stable",
            version="1.1.22",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            rc_tag="v1.1.22rc1",
            stable_tag="v1.1.22",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert f"Source: nwave-dev@{SAMPLE_SHA}" in message
        assert "Dev tag: v1.1.22.dev3" in message
        assert "RC tag: v1.1.22rc1" in message
        assert "Stable tag: v1.1.22" in message
        assert f"Pipeline: {SAMPLE_PIPELINE_URL}" in message

    def test_stable_message_full_format(self):
        """Full integration check for the stable message format.

        Expected:
            chore(release): v1.1.22

            Source: nwave-dev@abc123def456789012345678901234567890abcd
            Dev tag: v1.1.22.dev3
            RC tag: v1.1.22rc1
            Stable tag: v1.1.22
            Pipeline: https://github.com/.../actions/runs/12345
        """
        message = compose_trace_message(
            stage="stable",
            version="1.1.22",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            rc_tag="v1.1.22rc1",
            stable_tag="v1.1.22",
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        expected = (
            "chore(release): v1.1.22\n"
            "\n"
            f"Source: nwave-dev@{SAMPLE_SHA}\n"
            "Dev tag: v1.1.22.dev3\n"
            "RC tag: v1.1.22rc1\n"
            "Stable tag: v1.1.22\n"
            f"Pipeline: {SAMPLE_PIPELINE_URL}"
        )
        assert message == expected


class TestTraceMessageEdgeCases:
    """Edge cases and error paths for trace message composition."""

    def test_special_characters_in_tag_preserved(self):
        """Given a tag name with dots and 'dev' suffix,
        the tag is rendered verbatim in the message (no URL encoding).
        """
        tag_with_dots = "v1.1.22.dev3"
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag=tag_with_dots,
            pipeline_url=SAMPLE_PIPELINE_URL,
        )
        assert f"Dev tag: {tag_with_dots}" in message
        # Verify no URL encoding happened (e.g. dots not replaced with %2E)
        assert "%2E" not in message

    def test_pipeline_url_with_long_run_id(self):
        """Pipeline URLs with large run IDs (> 10 digits) are preserved correctly."""
        long_url = (
            "https://github.com/Undeadgrishnackh/crafter-ai/actions/runs/99999999999999"
        )
        message = compose_trace_message(
            stage="rc",
            version="1.1.22rc1",
            commit_sha=SAMPLE_SHA,
            dev_tag="v1.1.22.dev3",
            pipeline_url=long_url,
        )
        assert f"Pipeline: {long_url}" in message

    def test_missing_required_field_raises_error(self):
        """Given stage=stable but --rc-tag is omitted,
        then the script exits with a clear error about the missing field.
        """
        with pytest.raises(ValueError, match="--rc-tag"):
            compose_trace_message(
                stage="stable",
                version="1.1.22",
                commit_sha=SAMPLE_SHA,
                dev_tag="v1.1.22.dev3",
                rc_tag=None,
                stable_tag="v1.1.22",
                pipeline_url=SAMPLE_PIPELINE_URL,
            )

    def test_invalid_stage_raises_error(self):
        """Given --stage 'dev' (trace messages are only for rc and stable),
        then the script exits with an error explaining dev stage has no trace message.
        """
        with pytest.raises(ValueError, match="Invalid stage 'dev'"):
            compose_trace_message(
                stage="dev",
                version="1.1.22.dev1",
                commit_sha=SAMPLE_SHA,
                dev_tag="v1.1.22.dev1",
                pipeline_url=SAMPLE_PIPELINE_URL,
            )
