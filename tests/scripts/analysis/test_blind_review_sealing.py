"""Sealing exclusions and the delivery manifest.

Contaminated blind review found two holes in `seal`: it did not exclude
`AGENTS.md` or the generated `test_k4_acceptance.py` (however deep they sit),
and a sealed packet carried no authoritative list of what the delivery
actually changed, so a reviewer had no way to tell delivery content from
installer footprint by reading the packet alone.

Run: uv run pytest -q tests/scripts/analysis/test_blind_review_sealing.py
"""

from __future__ import annotations

import json
import subprocess

import pytest

from scripts.analysis import blind_review as br


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(workspace):
    workspace.mkdir(parents=True)
    _git("init", "-q", cwd=workspace)
    _git("config", "user.email", "test@example.com", cwd=workspace)
    _git("config", "user.name", "test", cwd=workspace)


def _campaign_with_workspace(tmp_path, populate):
    """One usable pair-1/nwave.json payload plus its workspace, git-committed
    with a HEAD, then handed to `populate` to make the delivery's own changes."""
    campaign = tmp_path / "campaign"
    pair = campaign / "pair-1"
    pair.mkdir(parents=True)
    workspace = pair / "nwave"
    _init_repo(workspace)
    (workspace / "manage.py").write_text("# baseline\n")
    (workspace / ".gitignore").write_text("*.pyc\n")
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "baseline", cwd=workspace)

    populate(workspace)

    payload = {
        "session_id": "sess-abc123",
        "is_error": False,
        "total_cost_usd": 1.0,
        "num_turns": 3,
        "duration_ms": 5000,
        "usage": {
            "input_tokens": 1,
            "output_tokens": 1,
            "cache_creation_input_tokens": 1,
            "cache_read_input_tokens": 1,
        },
    }
    (pair / "nwave.json").write_text(json.dumps(payload))
    return campaign, workspace


def _seal(tmp_path, campaign):
    out = tmp_path / "sealed"
    map_path = tmp_path / "map.json"
    code = br.seal(campaign, out, map_path)
    assert code == 0, "seal must succeed for these fixtures"
    (opaque_dir,) = (out / "deliveries").iterdir()
    return opaque_dir


@pytest.mark.parametrize(
    "relative_path",
    [
        "AGENTS.md",
        "nested/dir/AGENTS.md",
        "hc/api/tests/test_k4_acceptance.py",
        "test_k4_acceptance.py",
    ],
)
def test_forbidden_names_are_excluded_however_nested(tmp_path, relative_path):
    def populate(workspace):
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("must never leave the workspace\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    matches = list((opaque_dir / "delivery").rglob(relative_path.split("/")[-1]))
    assert matches == [], f"{relative_path} leaked into the sealed packet"


def test_manifest_excludes_setup_only_gitignore_and_installer_paths(tmp_path):
    def populate(workspace):
        (workspace / ".nwave").mkdir()
        (workspace / ".nwave" / "local-config.json").write_text("{}\n")
        (workspace / "CLAUDE.md").write_text("setup wrote this\n")
        gitignore = workspace / ".gitignore"
        gitignore.write_text(
            gitignore.read_text()
            + "# nWave activation marker (keep .nwave/local-config.json trackable)\n"
            ".nwave/*\n"
            "!.nwave/local-config.json\n"
        )

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest = (opaque_dir / "DELIVERY-CHANGES.txt").read_text()
    assert ".nwave" not in manifest
    assert "CLAUDE.md" not in manifest
    assert ".gitignore" not in manifest  # only the setup block changed


def test_manifest_includes_real_tracked_and_untracked_delivery_changes(tmp_path):
    def populate(workspace):
        (workspace / "manage.py").write_text("# baseline\n# delivery edit\n")
        (workspace / "hc").mkdir()
        (workspace / "hc" / "new_feature.py").write_text("def feature(): ...\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest = (opaque_dir / "DELIVERY-CHANGES.txt").read_text()
    lines = set(manifest.splitlines())
    assert "M manage.py" in lines
    assert "A hc/new_feature.py" in lines


def test_manifest_records_deletions_explicitly(tmp_path):
    def populate(workspace):
        (workspace / "manage.py").unlink()

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest = (opaque_dir / "DELIVERY-CHANGES.txt").read_text()
    assert "D manage.py" in manifest.splitlines()


def test_manifest_records_exact_rename_direction(tmp_path):
    def populate(workspace):
        _git("mv", "manage.py", "manage_renamed.py", cwd=workspace)

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest = (opaque_dir / "DELIVERY-CHANGES.txt").read_text()
    lines = set(manifest.splitlines())
    assert "R manage.py -> manage_renamed.py" in lines
    assert "R manage_renamed.py -> manage.py" not in lines


def test_manifest_is_deterministic_and_names_no_arm_or_session(tmp_path):
    def populate(workspace):
        (workspace / "a_new_file.py").write_text("x = 1\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest = (opaque_dir / "DELIVERY-CHANGES.txt").read_text()
    assert manifest == "\n".join(sorted(manifest.splitlines())) + "\n"
    assert "nwave" not in manifest.lower()
    assert "sess-abc123" not in manifest
