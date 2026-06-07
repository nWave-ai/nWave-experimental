"""
Shared helper functions for rigor global config acceptance test steps.

These are pure utility functions for reading and writing JSON config files.
They contain no test logic or assertions -- just filesystem operations
that multiple step definition files need.
"""

import json
from pathlib import Path


def write_json_config(config_path: Path, data: dict) -> None:
    """Write JSON data to a config file, creating parent dirs if needed."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Semantic aliases for call-site readability
write_project_config = write_json_config
write_global_config = write_json_config


def read_json_file(path: Path) -> dict:
    """Read and parse a JSON config file."""
    return json.loads(path.read_text(encoding="utf-8"))
