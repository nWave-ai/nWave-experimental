"""Discover the highest semantic version tag for a given pattern (dev or rc).

CLI interface:
    python discover_tag.py --pattern PATTERN [--validate TAG] [--tag-list TAG1,TAG2,...]

Patterns:
    dev  -> filters for dev pre-release tags (e.g. v1.1.23.dev1)
    rc   -> filters for rc pre-release tags (e.g. v1.1.23rc1)

Output: JSON to stdout:
    {"tag": "v1.1.23.dev1", "version": "1.1.23.dev1", "found": true, "commits_behind": null}

Exit codes:
    0 = tag found
    1 = no matching tags / tag not found
    2 = invalid input
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from packaging.version import InvalidVersion, Version


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover the highest semantic version tag for a pattern."
    )
    parser.add_argument(
        "--pattern",
        required=True,
        help="Tag pattern: 'dev' or 'rc'",
    )
    parser.add_argument(
        "--validate",
        default=None,
        help="Explicit tag to validate against the tag list",
    )
    parser.add_argument(
        "--tag-list",
        default=None,
        help="Comma-separated list of tags (when omitted, uses git tag -l)",
    )
    return parser.parse_args(argv)


def _emit_and_exit(payload: dict, exit_code: int) -> None:
    """Print JSON payload to stdout and exit with the given code."""
    print(json.dumps(payload))
    sys.exit(exit_code)


def _output_success(tag: str, version: str, commits_behind: int | None = None) -> None:
    _emit_and_exit(
        {
            "tag": tag,
            "version": version,
            "found": True,
            "commits_behind": commits_behind,
        },
        exit_code=0,
    )


def _output_not_found(error: str) -> None:
    _emit_and_exit(
        {"tag": None, "version": None, "found": False, "error": error},
        exit_code=1,
    )


def _output_error(error: str) -> None:
    _emit_and_exit({"error": error}, exit_code=2)


def _parse_tag(tag: str) -> Version | None:
    """Parse a tag string into a packaging.Version, returning None for invalid tags."""
    raw = tag.lstrip("v")
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def _is_dev_tag(version: Version) -> bool:
    return version.dev is not None


def _is_rc_tag(version: Version) -> bool:
    return version.pre is not None and version.pre[0] == "rc"


def _filter_by_pattern(tags: list[str], pattern: str) -> list[tuple[str, Version]]:
    """Filter tags by pattern, returning (original_tag, parsed_version) pairs."""
    matcher = _is_dev_tag if pattern == "dev" else _is_rc_tag
    results = []
    for tag in tags:
        parsed = _parse_tag(tag)
        if parsed is not None and matcher(parsed):
            results.append((tag, parsed))
    return results


def _split_tag_list(tag_list_str: str) -> list[str]:
    """Split a comma-separated tag list, filtering empty strings."""
    return [tag.strip() for tag in tag_list_str.split(",") if tag.strip()]


def _stage_guidance(pattern: str) -> str:
    if pattern == "dev":
        return "No dev tags found. Run Stage 1 (Dev Release) first."
    return "No rc tags found. Run Stage 2 (RC Release) first."


def _git_tags() -> list[str]:
    """Fetch all tags from the current git repository via git tag -l."""
    result = subprocess.run(
        ["git", "tag", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [tag.strip() for tag in result.stdout.strip().splitlines() if tag.strip()]


def _commits_behind(tag: str) -> int | None:
    """Count commits between tag and HEAD via git rev-list --count TAG..HEAD."""
    result = subprocess.run(
        ["git", "rev-list", "--count", f"{tag}..HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def discover(tags: list[str], pattern: str, use_git: bool = False) -> None:
    """Discover the highest semantic version tag matching pattern."""
    matched = _filter_by_pattern(tags, pattern)
    if not matched:
        _output_not_found(_stage_guidance(pattern))
        return

    _, highest_version = max(matched, key=lambda pair: pair[1])
    tag_str = f"v{highest_version}"
    staleness = _commits_behind(tag_str) if use_git else None
    _output_success(
        tag=tag_str,
        version=str(highest_version),
        commits_behind=staleness,
    )


def validate(tags: list[str], target: str) -> None:
    """Validate that a specific tag exists in the tag list."""
    if target in tags:
        parsed = _parse_tag(target)
        if parsed is not None:
            _output_success(
                tag=target,
                version=str(parsed),
                commits_behind=None,
            )
            return
    _output_not_found(f"Tag '{target}' not found in tag list.")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    pattern = args.pattern
    if pattern not in ("dev", "rc"):
        _output_error(f"Invalid pattern '{pattern}'. Must be 'dev' or 'rc'.")
        return

    use_git = args.tag_list is None
    tags = _git_tags() if use_git else _split_tag_list(args.tag_list)

    if args.validate is not None:
        validate(tags, args.validate)
    else:
        discover(tags, pattern, use_git=use_git)


if __name__ == "__main__":
    main()
