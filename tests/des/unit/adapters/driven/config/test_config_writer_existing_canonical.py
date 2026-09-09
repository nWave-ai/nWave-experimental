"""Regression coverage for bootstrap over pre-existing canonical authorities."""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.config.config_writer import ConfigWriter


def test_bootstrap_validates_existing_canonical_global_without_rewriting_it(
    tmp_path: Path,
) -> None:
    """A reinstall preserves public scalar preferences and foreign user keys."""
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    global_path.parent.mkdir(parents=True)
    original = {
        "schema-version": 1,
        "attribution": "on",
        "verbosity": "terse",
        "foreign-user-key": {"preserve": True},
    }
    global_path.write_text(json.dumps(original), encoding="utf-8")
    original_bytes = global_path.read_bytes()

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert result.created_paths == (repo / ".nwave" / "config.json",)
    assert json.loads(global_path.read_text(encoding="utf-8")) == original
    assert global_path.read_bytes() == original_bytes
