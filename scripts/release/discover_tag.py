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


def _output_success(tag: str, version: str, commits_behind: int | None = None) -> None:
    result = {
        "tag": tag,
        "version": version,
        "found": True,
        "commits_behind": commits_behind,
    }
    print(json.dumps(result))
    sys.exit(0)


def _output_not_found(error: str) -> None:
    result = {
        "tag": None,
        "version": None,
        "found": False,
        "error": error,
    }
    print(json.dumps(result))
    sys.exit(1)


def _output_error(error: str) -> None:
    result = {
        "error": error,
    }
    print(json.dumps(result))
    sys.exit(2)


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
    return [t.strip() for t in tag_list_str.split(",") if t.strip()]


def _stage_guidance(pattern: str) -> str:
    if pattern == "dev":
        return "No dev tags found. Run Stage 1 (Dev Release) first."
    return "No rc tags found. Run Stage 2 (RC Release) first."


def _version_to_tag(version: Version) -> str:
    return f"v{version}"


def _version_to_str(version: Version) -> str:
    return str(version)


def discover(tags: list[str], pattern: str) -> None:
    """Discover the highest semantic version tag matching pattern."""
    matched = _filter_by_pattern(tags, pattern)
    if not matched:
        _output_not_found(_stage_guidance(pattern))

    _highest_tag, highest_version = max(matched, key=lambda pair: pair[1])
    _output_success(
        tag=_version_to_tag(highest_version),
        version=_version_to_str(highest_version),
        commits_behind=None,
    )


def validate(tags: list[str], target: str, pattern: str) -> None:
    """Validate that a specific tag exists in the tag list."""
    if target in tags:
        parsed = _parse_tag(target)
        if parsed is not None:
            _output_success(
                tag=target,
                version=_version_to_str(parsed),
                commits_behind=None,
            )
    _output_not_found(f"Tag '{target}' not found in tag list.")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    pattern = args.pattern
    if pattern not in ("dev", "rc"):
        _output_error(f"Invalid pattern '{pattern}'. Must be 'dev' or 'rc'.")

    tag_list_str = args.tag_list if args.tag_list is not None else ""
    tags = _split_tag_list(tag_list_str)

    if args.validate is not None:
        validate(tags, args.validate, pattern)
    else:
        discover(tags, pattern)


if __name__ == "__main__":
    main()
