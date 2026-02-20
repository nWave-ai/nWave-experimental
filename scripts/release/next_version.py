"""Calculate the next PEP 440 version based on stage and existing tags.

CLI interface:
    python next_version.py --stage STAGE --current-version VERSION
        [--existing-tags TAG1,TAG2,...] [--public-version-floor FLOOR]
        [--current-public-version VERSION]

Stages:
    dev     -> X.Y.Z.devN  (sequential counter from existing dev tags)
    rc      -> X.Y.ZrcN    (sequential counter from existing RC tags)
    stable  -> X.Y.Z       (strip rc/dev suffix)
    nwave-ai -> version for public package (auto-bump or floor override)

Output: JSON to stdout:
    {"version": "1.1.22.dev1", "tag": "v1.1.22.dev1", "base_version": "1.1.22", "pep440_valid": true}

Exit codes:
    0 = success
    1 = no version bump needed
    2 = invalid input
"""

from __future__ import annotations

import argparse
import json
import sys

from packaging.version import InvalidVersion, Version


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate next PEP 440 version.")
    parser.add_argument(
        "--stage",
        required=True,
        help="Release stage: dev, rc, stable, nwave-ai",
    )
    parser.add_argument(
        "--current-version",
        required=True,
        help="Current version from pyproject.toml (e.g. 1.1.21)",
    )
    parser.add_argument(
        "--existing-tags",
        default="",
        help="Comma-separated list of existing tags (e.g. v1.1.22.dev1,v1.1.22.dev2)",
    )
    parser.add_argument(
        "--public-version-floor",
        default="",
        help="Minimum public version floor for nwave-ai stage",
    )
    parser.add_argument(
        "--current-public-version",
        default="",
        help="Current public version for nwave-ai stage",
    )
    parser.add_argument(
        "--no-bump",
        action="store_true",
        help="Signal that no conventional commits require a bump",
    )
    return parser.parse_args(argv)


def _validate_stage(stage: str) -> None:
    valid = {"dev", "rc", "stable", "nwave-ai"}
    if stage not in valid:
        _error_exit(
            f"Invalid stage '{stage}'. Must be one of: {', '.join(sorted(valid))}"
        )


def _validate_version(version_str: str, label: str = "version") -> Version:
    if not version_str or not version_str.strip():
        _error_exit(f"Missing {label}: empty string provided.")
    try:
        return Version(version_str)
    except InvalidVersion:
        _error_exit(f"Invalid {label} '{version_str}': not PEP 440 compliant.")


def _validate_tags(tags: list[str]) -> list[Version]:
    versions = []
    for tag in tags:
        raw = tag.lstrip("v")
        try:
            versions.append(Version(raw))
        except InvalidVersion:
            _error_exit(f"Tag '{tag}' does not match PEP 440 format.")
    return versions


def _error_exit(message: str, code: int = 2) -> None:
    print(json.dumps({"error": message}), file=sys.stdout)
    sys.exit(code)


def _success_output(version_str: str, base_version: str) -> None:
    try:
        Version(version_str)
        pep440_valid = True
    except InvalidVersion:
        pep440_valid = False
    result = {
        "version": version_str,
        "tag": f"v{version_str}",
        "base_version": base_version,
        "pep440_valid": pep440_valid,
    }
    print(json.dumps(result))
    sys.exit(0)


def _bump_minor(version: Version) -> str:
    return f"{version.major}.{version.minor + 1}.0"


def _bump_patch(version: Version) -> str:
    return f"{version.major}.{version.minor}.{version.micro + 1}"


def _highest_counter(tag_versions: list[Version], base: str, suffix_type: str) -> int:
    """Find the highest N for devN or rcN tags matching the base version."""
    highest = 0
    for v in tag_versions:
        v_base = f"{v.major}.{v.minor}.{v.micro}"
        if v_base != base:
            continue
        if suffix_type == "dev" and v.dev is not None:
            highest = max(highest, v.dev)
        elif suffix_type == "rc" and v.pre is not None and v.pre[0] == "rc":
            highest = max(highest, v.pre[1])
    return highest


def calculate_dev(
    current_version: Version, existing_tags: list[Version], no_bump: bool
) -> None:
    if no_bump:
        _error_exit("No version bump needed.", code=1)

    base = _bump_patch(current_version)
    highest = _highest_counter(existing_tags, base, "dev")
    next_dev = highest + 1
    version_str = f"{base}.dev{next_dev}"
    _success_output(version_str, base)


def calculate_rc(current_version: str, existing_tags: list[Version]) -> None:
    # current_version for RC is the base version (e.g. "1.1.22")
    # or a dev tag like "v1.1.22.dev3" -> strip to "1.1.22"
    raw = current_version.lstrip("v")
    try:
        parsed = Version(raw)
    except InvalidVersion:
        _error_exit(
            f"Invalid current version '{current_version}': not PEP 440 compliant."
        )
        return  # unreachable, for type checker

    base = f"{parsed.major}.{parsed.minor}.{parsed.micro}"
    highest = _highest_counter(existing_tags, base, "rc")
    next_rc = highest + 1
    version_str = f"{base}rc{next_rc}"
    _success_output(version_str, base)


def calculate_stable(current_version: str) -> None:
    raw = current_version.lstrip("v")
    try:
        parsed = Version(raw)
    except InvalidVersion:
        _error_exit(
            f"Invalid current version '{current_version}': not PEP 440 compliant."
        )
        return

    base = f"{parsed.major}.{parsed.minor}.{parsed.micro}"
    _success_output(base, base)


def calculate_nwave_ai(floor: str, current_public: str) -> None:
    floor_v = _validate_version(floor, "public-version-floor")
    current_v = _validate_version(current_public, "current-public-version")

    version_str = str(floor_v) if floor_v > current_v else _bump_patch(current_v)
    base = version_str
    _success_output(version_str, base)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    _validate_stage(args.stage)

    existing_tags_raw = [t.strip() for t in args.existing_tags.split(",") if t.strip()]
    tag_versions = _validate_tags(existing_tags_raw) if existing_tags_raw else []

    if args.stage == "dev":
        current_v = _validate_version(args.current_version, "current-version")
        calculate_dev(current_v, tag_versions, args.no_bump)
    elif args.stage == "rc":
        calculate_rc(args.current_version, tag_versions)
    elif args.stage == "stable":
        calculate_stable(args.current_version)
    elif args.stage == "nwave-ai":
        calculate_nwave_ai(args.public_version_floor, args.current_public_version)


if __name__ == "__main__":
    main()
