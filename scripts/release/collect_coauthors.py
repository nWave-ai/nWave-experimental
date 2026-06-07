"""Collect Co-Authored-By trailers for release-train sync commits.

Walks the commit range (since..source) in a source repo and extracts the
union of all authors and Co-Authored-By trailers, filtered by the project's
bot-exclusion policy and emitted as canonical trailer lines on stdout.

Filter policy (see tests for full spec):
  - Drop: name contains '[bot]', name starts with 'Claude', named bots
    (claude-bot, dependabot, github-actions, semantic-release-bot, renovate,
    claude-code), email noreply@anthropic.com or noreply@nwave.ai.
  - Allowlist (overrides drop): exact email match 'nwave@nwave.ai'.
  - Do NOT filter '*@users.noreply.github.com' -- these are real humans.

CLI usage:
    python collect_coauthors.py \
        --source-sha SHA \
        (--since-sha SHA | --auto-since-tag) \
        [--exclude-author "Name <email>"] ... \
        [--repo-path PATH]

Output:
    One canonical 'Co-Authored-By: Name <email>' per line, alphabetical by
    name (case-insensitive), deduped case-insensitively on email. Empty
    stdout if no trailers. Exit 0 on success; non-zero on arg/git errors.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Filter policy (pure)
# ---------------------------------------------------------------------------

_ALLOWLIST_EMAILS = frozenset({"nwave@nwave.ai"})

_DROP_NAMES_EXACT = frozenset(
    {
        "claude-bot",
        "dependabot",
        "github-actions",
        "semantic-release-bot",
        "renovate",
        "claude-code",
    }
)

_DROP_EMAILS_EXACT = frozenset(
    {
        "noreply@anthropic.com",
        "noreply@nwave.ai",
    }
)


def is_filtered(name: str, email: str) -> bool:
    """Return True if the (name, email) identity should be dropped.

    Allowlist (exact email, case-insensitive) overrides all drop rules.
    """
    if not name or not email:
        return True

    email_lc = email.lower()
    name_lc = name.lower()

    if email_lc in _ALLOWLIST_EMAILS:
        return False

    if email_lc in _DROP_EMAILS_EXACT:
        return True

    if "[bot]" in name_lc:
        return True

    if name_lc.startswith("claude"):
        return True

    return name_lc in _DROP_NAMES_EXACT


# ---------------------------------------------------------------------------
# Dedupe and sort (pure)
# ---------------------------------------------------------------------------


def dedupe_and_sort(
    identities: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Dedupe by case-insensitive email (keep first-seen name casing),
    then sort alphabetically by name case-insensitively."""
    seen: dict[str, tuple[str, str]] = {}
    for name, email in identities:
        key = email.lower()
        if key not in seen:
            seen[key] = (name, email)
    return sorted(seen.values(), key=lambda ne: ne[0].lower())


# ---------------------------------------------------------------------------
# Parsing (pure)
# ---------------------------------------------------------------------------

# Match "Co-Authored-By: Name <email>" (case-insensitive trailer key,
# requires a non-empty name token and an email in angle brackets).
_TRAILER_RE = re.compile(
    r"^\s*Co-Authored-By:\s*(?P<name>[^<>]+?)\s*<(?P<email>[^<>\s]+)>\s*$",
    re.IGNORECASE,
)


def parse_identities_from_log(raw_log: str) -> list[tuple[str, str]]:
    """Parse identities from a custom-format git log output.

    Record format emitted by _fetch_raw_log:
        <author_name>\x00<author_email>\x00<body>\x00\x00

    Returns a list of (name, email) pairs in the order encountered, including
    duplicates. Filtering/deduping happens separately.
    """
    if not raw_log:
        return []

    identities: list[tuple[str, str]] = []
    # Records separated by double-null
    for record in raw_log.split("\x00\x00"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x00")
        if len(parts) < 3:
            continue
        author_name = parts[0].strip()
        author_email = parts[1].strip()
        body = parts[2]

        if author_name and author_email:
            identities.append((author_name, author_email))

        for line in body.splitlines():
            match = _TRAILER_RE.match(line)
            if not match:
                continue
            name = match.group("name").strip()
            email = match.group("email").strip()
            if name and email:
                identities.append((name, email))

    return identities


def format_trailers(identities: list[tuple[str, str]]) -> list[str]:
    """Format identities as canonical Co-Authored-By trailer lines."""
    return [f"Co-Authored-By: {name} <{email}>" for name, email in identities]


# ---------------------------------------------------------------------------
# Git interaction (impure, isolated)
# ---------------------------------------------------------------------------

_VERSION_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def resolve_since_tag(repo_path: str) -> str | None:
    """Resolve the most recent vX.Y.Z tag merged into HEAD.

    Ignores rcN suffix tags (the baseline is always a plain vX.Y.Z).
    Returns None if no matching tag exists.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "tag",
                "--list",
                "v*.*.*",
                "--sort=-v:refname",
                "--merged",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None

    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        if _VERSION_TAG_RE.match(tag):
            return tag
    return None


def _fetch_raw_log(
    repo_path: str,
    since_sha: str | None,
    source_sha: str,
) -> str:
    """Fetch git log between since_sha..source_sha (or all ancestors of
    source_sha if since_sha is None), formatted for parse_identities_from_log.
    """
    record_fmt = "%an%x00%ae%x00%B%x00%x00"
    revision = f"{since_sha}..{source_sha}" if since_sha else source_sha
    cmd = [
        "git",
        "log",
        "--no-merges",
        f"--pretty=format:{record_fmt}",
        revision,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git log failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Orchestration (impure)
# ---------------------------------------------------------------------------


def _normalize_exclusion(spec: str) -> tuple[str, str] | None:
    """Parse 'Name <email>' into (name, email). Returns None if malformed."""
    match = re.match(r"^\s*(?P<name>[^<>]+?)\s*<(?P<email>[^<>\s]+)>\s*$", spec)
    if not match:
        return None
    return match.group("name").strip(), match.group("email").strip()


def collect(
    *,
    repo_path: str,
    source_sha: str,
    since_sha: str | None,
    auto_since_tag: bool,
    exclude_authors: list[str],
) -> list[str]:
    """Collect trailers for the given range. Returns formatted lines."""
    effective_since = since_sha
    if auto_since_tag:
        effective_since = resolve_since_tag(repo_path)

    raw_log = _fetch_raw_log(repo_path, effective_since, source_sha)
    identities = parse_identities_from_log(raw_log)

    # Apply exclusions (case-insensitive on email)
    excluded_emails = set()
    for spec in exclude_authors:
        parsed = _normalize_exclusion(spec)
        if parsed is None:
            continue
        excluded_emails.add(parsed[1].lower())

    filtered = [
        (name, email)
        for name, email in identities
        if not is_filtered(name, email) and email.lower() not in excluded_emails
    ]

    return format_trailers(dedupe_and_sort(filtered))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Collect Co-Authored-By trailers for release-train sync commits.")
    )
    parser.add_argument("--source-sha", required=True, help="Source commit SHA")
    parser.add_argument(
        "--since-sha",
        default=None,
        help="Baseline commit SHA (exclusive). Mutually exclusive with --auto-since-tag.",
    )
    parser.add_argument(
        "--auto-since-tag",
        action="store_true",
        help="Auto-resolve baseline from last vX.Y.Z tag in --repo-path.",
    )
    parser.add_argument(
        "--exclude-author",
        action="append",
        default=[],
        help='Identity to drop, formatted as "Name <email>". Repeatable.',
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to the source git repository (default: cwd).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.since_sha and args.auto_since_tag:
        print(
            "Error: --since-sha and --auto-since-tag are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    if not args.since_sha and not args.auto_since_tag:
        print(
            "Error: one of --since-sha or --auto-since-tag is required",
            file=sys.stderr,
        )
        return 2

    repo_path = str(Path(args.repo_path).resolve())

    try:
        lines = collect(
            repo_path=repo_path,
            source_sha=args.source_sha,
            since_sha=args.since_sha,
            auto_since_tag=args.auto_since_tag,
            exclude_authors=args.exclude_author,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
