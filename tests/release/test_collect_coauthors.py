"""Tests for scripts/release/collect_coauthors.py

Collector of Co-Authored-By trailers for release-train sync commits.

Scenario inventory:
  Filter policy (pure):
    1. Claude variants are dropped (Claude, Claude Opus 4.6, claude-bot)
    2. [bot] suffix names dropped (dependabot[bot], github-actions[bot])
    3. Named bots dropped (semantic-release-bot, dependabot, renovate, github-actions, claude-code)
    4. noreply@anthropic.com dropped
    5. noreply@nwave.ai dropped (release-train bot self)
    6. nwave@nwave.ai preserved (allowlist, exact match)
    7. users.noreply.github.com NOT filtered (real humans)
    8. Substring 'nwave' does NOT trigger allowlist (only exact email)
    9. Unknown identities are included (default)

  Ordering & dedup (pure):
   10. Alphabetical by name case-insensitive
   11. Dedupe case-insensitive on email keeps first-seen casing of name
   12. Stable ordering across reruns

  Parsing (pure):
   13. Author + Co-Authored-By trailers from a commit are both collected
   14. Malformed trailer lines silently ignored
   15. Empty log -> empty output

  CLI / exclusion:
   16. --exclude-author "Name <email>" drops that identity
   17. Exclusion uses case-insensitive email match

  Tag resolution (integration, requires tmp_path git repo):
   18. Last v1.2.3 tag resolved when multiple tags including rc tags exist
   19. rcN tags are ignored for baseline computation
   20. No prior tag -> falls back to root commit range
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.release.collect_coauthors import (
    dedupe_and_sort,
    format_trailers,
    is_filtered,
    parse_identities_from_log,
    resolve_since_tag,
)


SCRIPT = "scripts/release/collect_coauthors.py"


# ---------------------------------------------------------------------------
# Filter policy (pure)
# ---------------------------------------------------------------------------


class TestFilterPolicy:
    @pytest.mark.parametrize(
        "name",
        [
            "Claude",
            "claude",
            "Claude Opus 4.6",
            "CLAUDE BOT",
            "claude-bot",
            "Claude-Bot",
            "claude-code",
        ],
    )
    def test_claude_variants_dropped(self, name):
        assert is_filtered(name, "anything@example.com")

    @pytest.mark.parametrize(
        "name",
        [
            "dependabot[bot]",
            "github-actions[bot]",
            "renovate[bot]",
            "Something[BOT]",
        ],
    )
    def test_bot_suffix_dropped(self, name):
        assert is_filtered(name, "anything@example.com")

    @pytest.mark.parametrize(
        "name",
        [
            "semantic-release-bot",
            "Semantic-Release-Bot",
            "dependabot",
            "renovate",
            "github-actions",
        ],
    )
    def test_named_bots_dropped(self, name):
        assert is_filtered(name, "anything@example.com")

    @pytest.mark.parametrize(
        "email",
        [
            "noreply@anthropic.com",
            "NoReply@Anthropic.COM",
            "noreply@nwave.ai",
            "NOREPLY@nwave.ai",
        ],
    )
    def test_noreply_emails_dropped(self, email):
        assert is_filtered("Someone Real", email)

    def test_nwave_exact_email_allowlisted(self):
        # Allowlist overrides drop: even if the name would match a pattern,
        # the exact email "nwave@nwave.ai" is preserved.
        assert not is_filtered("nwave", "nwave@nwave.ai")
        assert not is_filtered("NWAVE", "NWAVE@NWAVE.AI")

    def test_users_noreply_github_com_not_filtered(self):
        # These are real humans hiding their personal email.
        assert not is_filtered("Alice Example", "12345+alice@users.noreply.github.com")

    def test_substring_nwave_does_not_trigger_allowlist(self):
        # Only the exact email "nwave@nwave.ai" allowlists; a substring "nwave"
        # anywhere else doesn't protect against the drop rules.
        assert is_filtered("claude-bot", "nwave-support@nwave.ai")

    def test_unknown_identity_included_by_default(self):
        assert not is_filtered("Alice Example", "alice@example.com")

    def test_empty_name_or_email_dropped(self):
        # Defensive: malformed identities with no name or email are dropped.
        assert is_filtered("", "alice@example.com")
        assert is_filtered("Alice", "")


# ---------------------------------------------------------------------------
# Dedupe and sort (pure)
# ---------------------------------------------------------------------------


class TestDedupeAndSort:
    def test_alphabetical_case_insensitive(self):
        identities = [
            ("charlie", "c@example.com"),
            ("Alice", "a@example.com"),
            ("bob", "b@example.com"),
        ]
        result = dedupe_and_sort(identities)
        assert [n for n, _ in result] == ["Alice", "bob", "charlie"]

    def test_dedupe_case_insensitive_email_keeps_first_seen_name_casing(self):
        identities = [
            ("Alice Example", "alice@example.com"),
            ("ALICE EXAMPLE", "ALICE@EXAMPLE.COM"),
            ("alice example", "alice@example.com"),
        ]
        result = dedupe_and_sort(identities)
        assert len(result) == 1
        assert result[0] == ("Alice Example", "alice@example.com")

    def test_stable_across_reruns(self):
        identities = [
            ("Alice", "a@example.com"),
            ("Bob", "b@example.com"),
            ("alice", "A@example.com"),
        ]
        first = dedupe_and_sort(identities)
        second = dedupe_and_sort(identities)
        assert first == second

    def test_empty_input_yields_empty(self):
        assert dedupe_and_sort([]) == []


# ---------------------------------------------------------------------------
# Parsing (pure)
# ---------------------------------------------------------------------------


class TestParseIdentitiesFromLog:
    def test_single_commit_author_and_coauthor(self):
        # Each commit rendered as: AN\x00AE\x00BODY\x00\x00
        raw = (
            "Alice\x00alice@example.com\x00"
            "Some body text\n\nCo-Authored-By: Bob <bob@example.com>\n"
            "\x00\x00"
        )
        ids = parse_identities_from_log(raw)
        assert ("Alice", "alice@example.com") in ids
        assert ("Bob", "bob@example.com") in ids

    def test_multiple_coauthors_in_one_commit(self):
        raw = (
            "Alice\x00alice@example.com\x00"
            "subject\n\n"
            "Co-Authored-By: Bob <bob@example.com>\n"
            "Co-Authored-By: Carol <carol@example.com>\n"
            "\x00\x00"
        )
        ids = parse_identities_from_log(raw)
        names = sorted(n for n, _ in ids)
        assert names == ["Alice", "Bob", "Carol"]

    def test_malformed_trailer_lines_silently_ignored(self):
        raw = (
            "Alice\x00alice@example.com\x00"
            "subject\n\n"
            "Co-Authored-By: broken no angle brackets\n"
            "Co-Authored-By: <just-email@example.com>\n"
            "Co-Authored-By: Bob <bob@example.com>\n"
            "\x00\x00"
        )
        ids = parse_identities_from_log(raw)
        assert ("Alice", "alice@example.com") in ids
        assert ("Bob", "bob@example.com") in ids
        # Malformed entries dropped
        assert all("broken" not in n for n, _ in ids)

    def test_empty_log_yields_empty(self):
        assert parse_identities_from_log("") == []

    def test_trailer_case_insensitive(self):
        raw = (
            "Alice\x00alice@example.com\x00"
            "subject\n\nco-authored-by: Bob <bob@example.com>\n"
            "\x00\x00"
        )
        ids = parse_identities_from_log(raw)
        assert ("Bob", "bob@example.com") in ids


# ---------------------------------------------------------------------------
# Format trailers
# ---------------------------------------------------------------------------


class TestFormatTrailers:
    def test_canonical_format(self):
        lines = format_trailers([("Alice", "alice@example.com")])
        assert lines == ["Co-Authored-By: Alice <alice@example.com>"]

    def test_empty_input_yields_empty_list(self):
        assert format_trailers([]) == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def _run_collector(*args, cwd=None):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
        cwd=cwd or Path(__file__).resolve().parents[2],
    )


def _git(repo: Path, *args, env_extra=None):
    env = {
        "GIT_AUTHOR_NAME": "Alice",
        "GIT_AUTHOR_EMAIL": "alice@example.com",
        "GIT_COMMITTER_NAME": "Alice",
        "GIT_COMMITTER_EMAIL": "alice@example.com",
        "HOME": str(repo),
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {args} failed: {result.stderr}")
    return result


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "tag.gpgsign", "false")
    return repo


def _commit(repo: Path, message: str, author=None):
    (repo / "file.txt").write_text(message)
    env_extra = {}
    if author:
        name, email = author
        env_extra = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email}
    _git(repo, "add", "-A", env_extra=env_extra)
    _git(repo, "commit", "-q", "-m", message, env_extra=env_extra)


class TestCLIIntegration:
    def test_empty_range_yields_empty_stdout(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "initial")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--since-sha",
            head,
            "--repo-path",
            str(repo),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""

    def test_collects_author_and_coauthor_filters_and_sorts(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()

        # A real commit with a bot author and a human co-author
        (repo / "a.txt").write_text("a")
        _git(repo, "add", "-A")
        _git(
            repo,
            "commit",
            "-q",
            "-m",
            "feat: something\n\n"
            "Co-Authored-By: Zelda Human <zelda@example.com>\n"
            "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>\n"
            "Co-Authored-By: dependabot[bot] <dep@example.com>\n"
            "Co-Authored-By: nwave <nwave@nwave.ai>\n",
            env_extra={
                "GIT_AUTHOR_NAME": "Alice Human",
                "GIT_AUTHOR_EMAIL": "alice@example.com",
            },
        )
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--since-sha",
            base,
            "--repo-path",
            str(repo),
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert lines == [
            "Co-Authored-By: Alice Human <alice@example.com>",
            "Co-Authored-By: nwave <nwave@nwave.ai>",
            "Co-Authored-By: Zelda Human <zelda@example.com>",
        ]

    def test_exclude_author_drops_that_identity(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()

        (repo / "b.txt").write_text("b")
        _git(repo, "add", "-A")
        _git(
            repo,
            "commit",
            "-q",
            "-m",
            "feat: stuff\n\nCo-Authored-By: Bob <bob@example.com>\n",
            env_extra={
                "GIT_AUTHOR_NAME": "Alice Human",
                "GIT_AUTHOR_EMAIL": "alice@example.com",
            },
        )
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--since-sha",
            base,
            "--repo-path",
            str(repo),
            "--exclude-author",
            "Alice Human <alice@example.com>",
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert lines == ["Co-Authored-By: Bob <bob@example.com>"]

    def test_exclude_author_case_insensitive_email(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "base")
        base = _git(repo, "rev-parse", "HEAD").stdout.strip()

        _commit(
            repo,
            "feat x",
            author=("Alice Human", "alice@example.com"),
        )
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--since-sha",
            base,
            "--repo-path",
            str(repo),
            "--exclude-author",
            "Alice Human <ALICE@EXAMPLE.COM>",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""

    def test_auto_since_tag_picks_last_vX_Y_Z_ignoring_rc(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "c1")
        _git(repo, "tag", "v1.0.0")
        _commit(repo, "c2")
        _git(repo, "tag", "v1.1.0")
        _commit(repo, "c3", author=("Alice Human", "alice@example.com"))
        _git(repo, "tag", "v1.2.0rc1")  # rc tag MUST be ignored
        _commit(repo, "c4", author=("Bob Human", "bob@example.com"))
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--auto-since-tag",
            "--repo-path",
            str(repo),
        )
        assert result.returncode == 0, result.stderr
        # Commits after v1.1.0 are c3 and c4 -> Alice and Bob
        lines = result.stdout.strip().splitlines()
        assert lines == [
            "Co-Authored-By: Alice Human <alice@example.com>",
            "Co-Authored-By: Bob Human <bob@example.com>",
        ]

    def test_auto_since_tag_no_prior_tag_falls_back_to_root(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "c1", author=("Alice Human", "alice@example.com"))
        _commit(repo, "c2", author=("Bob Human", "bob@example.com"))
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        result = _run_collector(
            "--source-sha",
            head,
            "--auto-since-tag",
            "--repo-path",
            str(repo),
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert "Co-Authored-By: Alice Human <alice@example.com>" in lines
        assert "Co-Authored-By: Bob Human <bob@example.com>" in lines


class TestResolveSinceTag:
    def test_picks_latest_vXYZ_ignoring_rc_tags(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "c1")
        _git(repo, "tag", "v1.0.0")
        _commit(repo, "c2")
        _git(repo, "tag", "v1.1.0")
        _commit(repo, "c3")
        _git(repo, "tag", "v1.2.0rc1")
        assert resolve_since_tag(str(repo)) == "v1.1.0"

    def test_no_tag_returns_none(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "c1")
        assert resolve_since_tag(str(repo)) is None


class TestCLIArgValidation:
    def test_missing_source_sha_errors(self):
        result = _run_collector("--since-sha", "deadbeef")
        assert result.returncode != 0

    def test_conflicting_since_and_auto_errors(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit(repo, "c1")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        result = _run_collector(
            "--source-sha",
            head,
            "--since-sha",
            head,
            "--auto-since-tag",
            "--repo-path",
            str(repo),
        )
        assert result.returncode != 0
