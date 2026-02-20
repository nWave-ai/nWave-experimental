"""Compose traceability commit messages for cross-repo sync.

Two formats:
  - RC (stage 2): header + source SHA, dev tag, pipeline URL
  - Stable (stage 3): header + full chain (source, dev, rc, stable, pipeline)

CLI usage:
    python trace_message.py --stage STAGE --version VERSION --commit-sha SHA \
        [--dev-tag TAG] [--rc-tag TAG] [--stable-tag TAG] [--pipeline-url URL]

Exit codes:
    0 = success (message printed to stdout)
    1 = invalid stage
    2 = missing required fields
"""

from __future__ import annotations

import argparse
import sys


def compose_trace_message(
    *,
    stage: str,
    version: str,
    commit_sha: str,
    dev_tag: str | None = None,
    rc_tag: str | None = None,
    stable_tag: str | None = None,
    pipeline_url: str | None = None,
) -> str:
    """Compose a traceability commit message for the given release stage.

    Args:
        stage: Release stage ("rc" or "stable").
        version: Version string (e.g. "1.1.22rc1" or "1.1.22").
        commit_sha: Full commit SHA from nwave-dev.
        dev_tag: Dev tag (e.g. "v1.1.22.dev3").
        rc_tag: RC tag (e.g. "v1.1.22rc1"), required for stable stage.
        stable_tag: Stable tag (e.g. "v1.1.22"), required for stable stage.
        pipeline_url: URL of the pipeline run.

    Returns:
        The composed commit message string.

    Raises:
        ValueError: If stage is invalid or required fields are missing.
    """
    valid_stages = ("rc", "stable")
    if stage not in valid_stages:
        raise ValueError(
            f"Invalid stage '{stage}'. Trace messages are only for: {', '.join(valid_stages)}"
        )

    # Validate required fields per stage
    missing = []
    if not commit_sha:
        missing.append("--commit-sha")
    if not dev_tag:
        missing.append("--dev-tag")
    if not pipeline_url:
        missing.append("--pipeline-url")

    if stage == "stable":
        if not rc_tag:
            missing.append("--rc-tag")
        if not stable_tag:
            missing.append("--stable-tag")

    if missing:
        raise ValueError(
            f"Missing required fields for stage '{stage}': {', '.join(missing)}"
        )

    # Header
    header = f"chore(release): v{version}"

    # Body lines
    body_lines = [
        f"Source: nwave-dev@{commit_sha}",
        f"Dev tag: {dev_tag}",
    ]

    if stage == "stable":
        body_lines.append(f"RC tag: {rc_tag}")
        body_lines.append(f"Stable tag: {stable_tag}")

    body_lines.append(f"Pipeline: {pipeline_url}")

    return header + "\n\n" + "\n".join(body_lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compose traceability commit messages for cross-repo sync."
    )
    parser.add_argument("--stage", required=True, help="Release stage: rc or stable")
    parser.add_argument("--version", required=True, help="Version string")
    parser.add_argument("--commit-sha", required=True, help="Source commit SHA")
    parser.add_argument("--dev-tag", default=None, help="Dev tag")
    parser.add_argument("--rc-tag", default=None, help="RC tag (stable only)")
    parser.add_argument("--stable-tag", default=None, help="Stable tag (stable only)")
    parser.add_argument("--pipeline-url", default=None, help="Pipeline run URL")

    args = parser.parse_args(argv)

    try:
        message = compose_trace_message(
            stage=args.stage,
            version=args.version,
            commit_sha=args.commit_sha,
            dev_tag=args.dev_tag,
            rc_tag=args.rc_tag,
            stable_tag=args.stable_tag,
            pipeline_url=args.pipeline_url,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        error_msg = str(exc)
        if "Invalid stage" in error_msg:
            return 1
        return 2

    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
