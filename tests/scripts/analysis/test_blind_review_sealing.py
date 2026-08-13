"""The compact packet contract: a delivered projection reconstructs exactly.

`seal` no longer copies a `delivery/` tree into the packet at all. Each
`deliveries/<opaque>/` holds exactly `DELIVERY-CHANGES.txt` and
`DELIVERY.patch` -- a `git apply`-able unified diff against the delivery
workspace's own HEAD. The whole compact contract stands or falls on one law:
apply that patch to a clean clone of HEAD and the result must equal, byte
for byte (content, mode, symlink target), what the delivery workspace
actually holds -- for every kind of change git can produce, not just text
edits.

Run: uv run pytest -q tests/scripts/analysis/test_blind_review_sealing.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.analysis import blind_review as br


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _git_out(*args, cwd):
    """Run git and return stdout."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


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


def _delivered_projection(root: Path) -> dict[str, dict]:
    """Deterministic projection of deliverable tree.

    Excludes .git paths and _excluded_path paths. Records: relative path,
    file kind (regular/symlink), exact bytes or symlink target, executable
    bit for regular files. Excludes directories and git metadata.
    """
    projection = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        rel_str = str(rel)

        if path.is_dir():
            continue

        if rel_str.startswith(".git") or "/.git" in rel_str:
            continue

        if br._excluded_path(rel_str):
            continue

        if path.is_symlink():
            target = str(path.readlink())
            projection[rel_str] = {
                "kind": "symlink",
                "target": target,
            }
        else:
            mode = path.stat().st_mode
            executable = bool(mode & 0o111)
            projection[rel_str] = {
                "kind": "regular",
                "bytes": path.read_bytes(),
                "executable": executable,
            }

    return projection


@pytest.mark.parametrize(
    "case_name,populate",
    [
        (
            "modified_text",
            lambda ws: (ws / "manage.py").write_text("# baseline\n# delivery edit\n"),
        ),
        ("deletion", lambda ws: (ws / "manage.py").unlink()),
        (
            "git_mv_rename",
            lambda ws: _git("mv", "manage.py", "manage_renamed.py", cwd=ws),
        ),
        (
            "untracked_text",
            lambda ws: (ws / "new_text.py").write_text("def new(): pass\n"),
        ),
        (
            "untracked_binary",
            lambda ws: (ws / "data.bin").write_bytes(b"\x00\x01\x02\xff"),
        ),
        (
            "executable_mode",
            lambda ws: (
                (ws / "script.sh").write_text("#!/bin/bash\necho hi\n"),
                (ws / "script.sh").chmod(0o755),
            ),
        ),
        (
            "relative_symlink",
            lambda ws: (ws / "ref.link").symlink_to("manage.py"),
        ),
    ],
)
def test_reconstruction_law(tmp_path, case_name, populate):
    """Patch is git-applicable and reconstructed clone equals delivery workspace."""

    def do_populate(workspace):
        populate(workspace)

    campaign, delivery_ws = _campaign_with_workspace(tmp_path, do_populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest_path = opaque_dir / "DELIVERY-CHANGES.txt"
    patch_path = opaque_dir / "DELIVERY.patch"
    assert manifest_path.is_file(), f"{case_name}: DELIVERY-CHANGES.txt missing"
    assert patch_path.is_file(), f"{case_name}: DELIVERY.patch missing"

    patch_text = patch_path.read_text()
    delivery_projection = _delivered_projection(delivery_ws)

    # Patch should apply cleanly to a clone of HEAD
    head_sha = _git_out("rev-parse", "HEAD", cwd=delivery_ws).strip()
    clone = tmp_path / f"clone-{case_name}"
    _git("clone", "-q", str(delivery_ws), str(clone), cwd=tmp_path)
    _git("checkout", "-q", head_sha, cwd=clone)

    if patch_text:
        result = subprocess.run(
            ["git", "apply", "--check", str(patch_path)],
            cwd=clone,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"{case_name}: patch cannot apply: {result.stderr}"
        )

        # Actually apply the patch
        result = subprocess.run(
            ["git", "apply", str(patch_path)],
            cwd=clone,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"{case_name}: patch apply failed: {result.stderr}"
        )

    # Compare reconstructed clone to delivery workspace
    clone_projection = _delivered_projection(clone)
    assert clone_projection == delivery_projection, (
        f"{case_name}: clone projection does not match delivery workspace"
    )

    # Verify patch headers name only deliverable paths (not _NEVER_SEAL)
    from scripts.analysis.blind_review import _diff_header_paths

    paths_in_patch = _diff_header_paths(patch_text)
    for path in paths_in_patch:
        assert not br._excluded_path(path), (
            f"{case_name}: excluded path {path!r} in patch"
        )


@pytest.mark.parametrize(
    "case_name,populate,expected_status",
    [
        (
            "modified_text",
            lambda ws: (ws / "manage.py").write_text("edit\n"),
            "M manage.py",
        ),
        ("deletion", lambda ws: (ws / "manage.py").unlink(), "D manage.py"),
        (
            "git_mv_rename",
            lambda ws: _git("mv", "manage.py", "manage_renamed.py", cwd=ws),
            "R manage.py -> manage_renamed.py",
        ),
        (
            "untracked_text",
            lambda ws: (ws / "new_text.py").write_text("new\n"),
            "A new_text.py",
        ),
        (
            "untracked_binary",
            lambda ws: (ws / "data.bin").write_bytes(b"\x00\x01\x02\xff"),
            "A data.bin",
        ),
        (
            "executable_mode",
            lambda ws: (
                (ws / "script.sh").write_text("#!/bin/bash\n"),
                (ws / "script.sh").chmod(0o755),
            ),
            "A script.sh",
        ),
        (
            "relative_symlink",
            lambda ws: (ws / "ref.link").symlink_to("manage.py"),
            "A ref.link",
        ),
    ],
)
def test_manifest_agrees_with_changes(tmp_path, case_name, populate, expected_status):
    """Manifest reports correct status for every change type."""

    def do_populate(workspace):
        populate(workspace)

    campaign, _ = _campaign_with_workspace(tmp_path, do_populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest_path = opaque_dir / "DELIVERY-CHANGES.txt"
    assert manifest_path.is_file(), f"{case_name}: DELIVERY-CHANGES.txt missing"

    manifest = manifest_path.read_text()
    assert expected_status in manifest, (
        f"{case_name}: expected {expected_status!r} in manifest"
    )


def test_setup_gitignore_stripped_delivery_gitignore_survives(tmp_path):
    """Setup-only block stripped; delivery's own gitignore edits preserved."""

    # Case 1: only setup block changed -> .gitignore excluded from manifest
    def populate_setup_only(workspace):
        gitignore = workspace / ".gitignore"
        gitignore.write_text(
            gitignore.read_text()
            + "# nWave activation marker (keep .nwave/local-config.json trackable)\n"
            ".nwave/*\n"
            "!.nwave/local-config.json\n"
        )

    campaign1, _ = _campaign_with_workspace(tmp_path / "run1", populate_setup_only)
    opaque1 = _seal(tmp_path / "seal1", campaign1)
    manifest1 = (opaque1 / "DELIVERY-CHANGES.txt").read_text()
    assert ".gitignore" not in manifest1, (
        "setup-only change should not appear in manifest"
    )

    # Case 2: setup block + delivery edit -> .gitignore in manifest, but setup lines stripped
    def populate_mixed(workspace):
        gitignore = workspace / ".gitignore"
        gitignore.write_text(
            gitignore.read_text()
            + "# nWave activation marker (keep .nwave/local-config.json trackable)\n"
            ".nwave/*\n"
            "!.nwave/local-config.json\n"
            "# delivery\n"
            "*.log\n"
        )

    campaign2, _ = _campaign_with_workspace(tmp_path / "run2", populate_mixed)
    opaque2 = _seal(tmp_path / "seal2", campaign2)
    manifest2 = (opaque2 / "DELIVERY-CHANGES.txt").read_text()
    patch2 = (opaque2 / "DELIVERY.patch").read_text()
    assert "M .gitignore" in manifest2, "gitignore with delivery edits should appear"
    assert ".nwave" not in patch2, "setup .nwave line should be stripped"
    assert "!.nwave/local-config.json" not in patch2, (
        "setup negation should be stripped"
    )
    assert "*.log" in patch2, "delivery edit should survive"


def test_deterministic_seal_identical_content(tmp_path):
    """Two seals with identical content produce identical manifest+patch bytes."""

    def populate1(workspace):
        (workspace / "new.py").write_text("x = 1\n")

    # First seal
    campaign1, _ = _campaign_with_workspace(tmp_path / "run1", populate1)
    out1 = tmp_path / "sealed1"
    map1 = tmp_path / "map1.json"
    assert br.seal(campaign1, out1, map1) == 0

    # Second seal with identical changes
    def populate2(workspace):
        (workspace / "new.py").write_text("x = 1\n")

    campaign2, _ = _campaign_with_workspace(tmp_path / "run2", populate2)
    out2 = tmp_path / "sealed2"
    map2 = tmp_path / "map2.json"
    assert br.seal(campaign2, out2, map2) == 0

    # Extract and compare packets
    opaque1 = next(iter((out1 / "deliveries").iterdir()))
    opaque2 = next(iter((out2 / "deliveries").iterdir()))

    manifest1 = (opaque1 / "DELIVERY-CHANGES.txt").read_bytes()
    manifest2 = (opaque2 / "DELIVERY-CHANGES.txt").read_bytes()
    assert manifest1 == manifest2, "manifests differ for identical changes"

    patch1 = (opaque1 / "DELIVERY.patch").read_bytes()
    patch2 = (opaque2 / "DELIVERY.patch").read_bytes()
    assert patch1 == patch2, "patches differ for identical changes"


def test_source_workspace_unchanged_after_seal(tmp_path):
    """Seal does not modify the source workspace tree or index."""

    def populate(workspace):
        (workspace / "new.py").write_text("x = 1\n")
        _git("add", "new.py", cwd=workspace)

    campaign, delivery_ws = _campaign_with_workspace(tmp_path, populate)

    before_projection = _delivered_projection(delivery_ws)
    before_index = _git_out("ls-files", "--stage", "-z", cwd=delivery_ws)

    opaque_dir = _seal(tmp_path, campaign)
    assert (opaque_dir / "DELIVERY-CHANGES.txt").is_file()
    assert (opaque_dir / "DELIVERY.patch").is_file()

    after_projection = _delivered_projection(delivery_ws)
    after_index = _git_out("ls-files", "--stage", "-z", cwd=delivery_ws)

    assert before_projection == after_projection, "workspace tree was modified"
    assert before_index == after_index, "git index was modified"


def test_non_git_input_fails(tmp_path):
    """Non-git workspace fails before creating handoff-ready bundle."""
    campaign = tmp_path / "campaign"
    pair = campaign / "pair-1"
    pair.mkdir(parents=True)
    workspace = pair / "nwave"
    workspace.mkdir(parents=True)
    (workspace / "manage.py").write_text("# not git\n")

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

    out = tmp_path / "sealed"
    map_path = tmp_path / "map.json"
    code = br.seal(campaign, out, map_path)

    assert code != 0, "seal should fail on non-git input"
    # Verify no handoff-ready bundle was created (no REVIEW-THESE.txt)
    if (out / "REVIEW-THESE.txt").exists():
        pytest.fail("bundle was created despite non-git input")


def test_map_path_inside_out_fails(tmp_path):
    """Map path inside bundle fails before leaving a handoff-ready state."""

    def populate(workspace):
        (workspace / "new.py").write_text("x = 1\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    out = tmp_path / "sealed"
    map_path = out / "nested" / "map.json"

    code = br.seal(campaign, out, map_path)
    assert code != 0, "seal should fail when map is inside bundle"
    assert not (out / "REVIEW-THESE.txt").exists(), (
        "REVIEW-THESE.txt should not be created"
    )
    assert not map_path.exists(), "map should not be created"
    assert not (out / "deliveries").exists() or not any(
        (out / "deliveries").iterdir()
    ), "no deliveries should be created"


def test_packet_contains_exactly_two_files(tmp_path):
    """Each packet holds only DELIVERY-CHANGES.txt and DELIVERY.patch."""

    def populate(workspace):
        (workspace / "new.py").write_text("x = 1\n")
        (workspace / ".nwave").mkdir(parents=True, exist_ok=True)
        (workspace / ".nwave" / "local.json").write_text("{}\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    assert opaque_dir.is_dir(), f"packet directory missing: {opaque_dir}"
    files = sorted(p.name for p in opaque_dir.iterdir())
    assert files == ["DELIVERY-CHANGES.txt", "DELIVERY.patch"], f"packet files: {files}"

    # Verify delivery/ subdirectory was never created
    assert not (opaque_dir / "delivery").exists(), (
        "delivery/ subdirectory should not exist"
    )


def test_no_credentials_or_identity_in_packet(tmp_path):
    """Packet contains no session_id, arm name, or credential keys."""

    def populate(workspace):
        (workspace / "new.py").write_text("x = 1\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest_path = opaque_dir / "DELIVERY-CHANGES.txt"
    patch_path = opaque_dir / "DELIVERY.patch"
    assert manifest_path.is_file(), "DELIVERY-CHANGES.txt missing"
    assert patch_path.is_file(), "DELIVERY.patch missing"

    manifest = manifest_path.read_text()
    patch = patch_path.read_text()

    forbidden = [
        "sess-abc123",
        "nwave",
        "claudeAiOauth",
        "accessToken",
        "refreshToken",
    ]
    for term in forbidden:
        assert term not in manifest, f"{term} leaked into manifest"
        assert term not in patch, f"{term} leaked into patch"


def test_excluded_paths_never_leak(tmp_path):
    """_NEVER_SEAL patterns never appear in manifest or patch."""

    def populate(workspace):
        # Try to add various excluded paths
        (workspace / ".claude-k4").mkdir(exist_ok=True)
        (workspace / ".claude-k4" / "config.json").write_text("{}\n")
        (workspace / "AGENTS.md").write_text("agents\n")
        (workspace / "test_k4_acceptance.py").write_text("test\n")
        (workspace / "new.py").write_text("x = 1\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest_path = opaque_dir / "DELIVERY-CHANGES.txt"
    patch_path = opaque_dir / "DELIVERY.patch"
    assert manifest_path.is_file(), "DELIVERY-CHANGES.txt missing"
    assert patch_path.is_file(), "DELIVERY.patch missing"

    manifest = manifest_path.read_text()
    patch = patch_path.read_text()

    excluded = [".claude-k4", "AGENTS.md", "test_k4_acceptance.py"]
    for term in excluded:
        assert term not in manifest, f"{term} leaked into manifest"
        assert term not in patch, f"{term} leaked into patch"

    # Delivery's own file should be present
    assert "new.py" in manifest or "new.py" in patch, "delivery's own file was excluded"


def test_hypothesis_cache_with_binary_excluded(tmp_path):
    """`.hypothesis/` runtime cache with non-UTF8 bytes does not crash seal."""

    def populate(workspace):
        # Hypothesis runtime cache with binary content (non-UTF8)
        hypothesis_dir = workspace / ".hypothesis"
        hypothesis_dir.mkdir(exist_ok=True)
        (hypothesis_dir / "cache.bin").write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
        (hypothesis_dir / "examples.db").write_bytes(b"binary_data_\xff\xfe")
        # Legitimate delivery change
        (workspace / "new.py").write_text("x = 1\n")

    campaign, _ = _campaign_with_workspace(tmp_path, populate)
    opaque_dir = _seal(tmp_path, campaign)

    manifest_path = opaque_dir / "DELIVERY-CHANGES.txt"
    patch_path = opaque_dir / "DELIVERY.patch"
    assert manifest_path.is_file(), "DELIVERY-CHANGES.txt missing"
    assert patch_path.is_file(), "DELIVERY.patch missing"

    manifest = manifest_path.read_text()
    patch = patch_path.read_text()

    # `.hypothesis` should never appear in manifest or patch
    assert ".hypothesis" not in manifest, ".hypothesis leaked into manifest"
    assert ".hypothesis" not in patch, ".hypothesis leaked into patch"

    # Delivery file should be present
    assert "new.py" in manifest or "new.py" in patch, "delivery file was excluded"
