"""Tests for simulate_changelog — changelog generation simulation (step 03-01).

Validates that simulate_changelog() generates a changelog preview,
checks for non-empty output with version header, and reports PASS/FAIL
via StepResult.
"""

from __future__ import annotations

from scripts.release.simulate import Status, simulate_changelog


# ---------------------------------------------------------------------------
# Acceptance: simulate_changelog returns PASS for valid changelog
# ---------------------------------------------------------------------------


class TestSimulateChangelogAcceptance:
    """Acceptance: simulate_changelog generates preview and validates output."""

    def test_valid_changelog_returns_pass_with_nonempty_detail(self, monkeypatch):
        """Given commits exist, simulate_changelog should return PASS
        with a non-empty message containing a preview."""
        import scripts.release.generate_changelog as gen_mod

        monkeypatch.setattr(gen_mod, "_find_previous_tag", lambda s, v: "v3.2.0")
        monkeypatch.setattr(
            gen_mod,
            "_fetch_commits",
            lambda prev: (
                "feat(core): add new feature\x00\x00abc1234<<--EOR-->>"
                "fix(ui): fix button\x00\x00def5678<<--EOR-->>"
            ),
        )

        result = simulate_changelog("3.3.0", "rc")

        assert result.status == Status.PASS
        assert result.name == "Changelog generation"
        assert "preview" in result.message.lower() or "chars" in result.message.lower()
        assert "3.3.0" in result.message


# ---------------------------------------------------------------------------
# Unit: empty changelog still produces valid output (header present)
# ---------------------------------------------------------------------------


class TestSimulateChangelogEmptyCommits:
    """Unit: when no commits found, changelog still has a header."""

    def test_no_commits_still_returns_pass(self, monkeypatch):
        """Even with no commits, the renderer produces a header,
        so it should still PASS (non-empty output)."""
        import scripts.release.generate_changelog as gen_mod

        monkeypatch.setattr(gen_mod, "_find_previous_tag", lambda s, v: "")
        monkeypatch.setattr(gen_mod, "_fetch_commits", lambda prev: "")

        result = simulate_changelog("3.3.0", "rc")

        assert result.status == Status.PASS
        assert "chars" in result.message.lower() or "preview" in result.message.lower()


# ---------------------------------------------------------------------------
# Unit: version header present in changelog preview
# ---------------------------------------------------------------------------


class TestSimulateChangelogVersionHeader:
    """Unit: changelog preview must contain the version string."""

    def test_changelog_contains_version_in_message(self, monkeypatch):
        """The generated changelog must mention the version."""
        import scripts.release.generate_changelog as gen_mod

        monkeypatch.setattr(gen_mod, "_find_previous_tag", lambda s, v: "")
        monkeypatch.setattr(
            gen_mod,
            "_fetch_commits",
            lambda prev: "feat(core): something\x00\x00aaa1111<<--EOR-->>",
        )

        result = simulate_changelog("3.3.0", "rc")

        assert result.status == Status.PASS
        assert "3.3.0" in result.message


# ---------------------------------------------------------------------------
# Unit: generation error produces FAIL
# ---------------------------------------------------------------------------


class TestSimulateChangelogError:
    """Unit: when changelog generation raises an exception, return FAIL."""

    def test_generation_error_returns_fail(self, monkeypatch):
        """If _find_previous_tag raises, result is FAIL."""
        import scripts.release.generate_changelog as gen_mod

        def exploding_find(stage: str, version: str) -> str:
            raise OSError("git not found")

        monkeypatch.setattr(gen_mod, "_find_previous_tag", exploding_find)

        result = simulate_changelog("3.3.0", "rc")

        assert result.status == Status.FAIL
        assert "error" in result.message.lower() or "Error" in result.message
