"""Check every tracked source JSON file for valid UTF-8 JSON syntax."""

import json
import subprocess
import sys
from pathlib import Path


_EXCLUDED_DIRECTORY_NAMES = {".git", "dist", "node_modules"}


def _tracked_json_files() -> list[Path]:
    """Return versioned JSON paths, excluding tracked dependency directories."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.json"],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"could not list tracked JSON files: {error}") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"could not list tracked JSON files: {detail or result.returncode}"
        )
    return [
        Path(item.decode("utf-8", errors="surrogateescape"))
        for item in result.stdout.split(b"\0")
        if item
        and not any(
            part in _EXCLUDED_DIRECTORY_NAMES
            for part in Path(item.decode("utf-8", errors="surrogateescape")).parts
        )
    ]


def main() -> int:
    try:
        json_files = _tracked_json_files()
    except RuntimeError as error:
        print(f"JSON error: {error}")
        return 1

    errors: list[str] = []
    for json_file in json_files:
        try:
            with json_file.open(encoding="utf-8") as fh:
                json.load(fh)
        except UnicodeDecodeError as error:
            errors.append(f"{json_file}: invalid UTF-8: {error}")
        except json.JSONDecodeError as error:
            errors.append(f"{json_file}: invalid JSON: {error}")
        except OSError as error:
            errors.append(f"{json_file}: could not read JSON: {error}")

    if errors:
        for e in errors:
            print(f"JSON error: {e}")
        return 1

    print("All JSON files have valid syntax")
    return 0


if __name__ == "__main__":
    sys.exit(main())
