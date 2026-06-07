"""Standalone prepare-commit-msg hook for nWave attribution trailer.

Reads config cascade (project > global > default off), appends
Co-Authored-By trailer if enabled. Stdlib only -- no nwave imports.

Exit 0 on ALL error paths (never block commits).
"""

import json
import sys
from pathlib import Path


_DEFAULT_TRAILER = "Co-Authored-By: nWave <nwave@nwave.ai>"


def _write_json(path: Path, data: dict) -> None:
    """Write a JSON file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _read_json(path: Path) -> dict:
    """Read a JSON file, returning empty dict on any error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _resolve_attribution(global_config: dict, project_config: dict) -> tuple[bool, str]:
    """Resolve attribution enabled/trailer from config cascade.

    Project overrides global. Missing key = disabled.

    Returns:
        (enabled, trailer_value)
    """
    # Start with global
    global_attr = global_config.get("attribution", {})
    enabled = global_attr.get("enabled", False)
    trailer = global_attr.get("trailer", _DEFAULT_TRAILER)

    # Project override takes precedence
    project_attr = project_config.get("attribution")
    if project_attr is not None:
        enabled = project_attr.get("enabled", enabled)
        trailer = project_attr.get("trailer", trailer)

    return enabled, trailer


def process_commit_message(
    commit_msg_path: str,
    merge_source: str | None = None,
    global_config_dir: Path | None = None,
    project_config_dir: Path | None = None,
) -> int:
    """Process a commit message file, appending trailer if enabled.

    Args:
        commit_msg_path: Path to the commit message file (sys.argv[1]).
        merge_source: Merge source type (sys.argv[2] if present).
        global_config_dir: Override for ~/.nwave/ (testing).
        project_config_dir: Override for .nwave/ (testing).

    Returns:
        0 always (never block commits).
    """
    try:
        if global_config_dir is None:
            global_config_dir = Path.home() / ".nwave"
        if project_config_dir is None:
            project_config_dir = Path.cwd() / ".nwave"

        config_path = global_config_dir / "global-config.json"
        global_config = _read_json(config_path)
        project_config = _read_json(project_config_dir / "des-config.json")

        # If no attribution key in config, silently do nothing (default off).
        # Users enable via `nwave-ai attribution on` CLI command.
        if "attribution" not in global_config:
            return 0

        enabled, trailer = _resolve_attribution(global_config, project_config)
        if not enabled:
            return 0

        msg_path = Path(commit_msg_path)
        content = msg_path.read_text(encoding="utf-8")

        # Idempotency: check if trailer already present
        if trailer in content:
            return 0

        # Append blank line + trailer
        content = content.rstrip("\n") + "\n\n" + trailer + "\n"
        msg_path.write_text(content, encoding="utf-8")

    except Exception:
        pass  # Never block commits

    return 0


def main() -> int:
    """Entry point for git prepare-commit-msg hook."""
    if len(sys.argv) < 2:
        return 0

    commit_msg_path = sys.argv[1]
    merge_source = sys.argv[2] if len(sys.argv) > 2 else None

    return process_commit_message(commit_msg_path, merge_source)


if __name__ == "__main__":
    sys.exit(main())
