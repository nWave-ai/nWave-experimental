"""Strict delivery capture proves a packet reconstructs its full projection.

Run: uv run pytest -q tests/scripts/analysis/test_strict_delivery_capture.py
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from scripts.analysis import blind_review as br


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def _init_repo(root: Path) -> str:
    root.mkdir()
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "test@example.com", cwd=root)
    _git("config", "user.name", "test", cwd=root)
    (root / "edited.txt").write_text("before\n")
    (root / "deleted.txt").write_text("delete me\n")
    (root / "renamed.txt").write_text("rename me\n")
    executable = root / "run.sh"
    executable.write_text("#!/bin/sh\necho baseline\n")
    executable.chmod(0o644)
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "baseline", cwd=root)
    return _git("rev-parse", "HEAD", cwd=root).stdout.strip()


def _projection(root: Path) -> dict[str, tuple[str, int, bytes | str]]:
    """Independent filesystem observation for the resulting fresh checkout."""
    observed: dict[str, tuple[str, int, bytes | str]] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or path.is_dir():
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            observed[rel] = ("symlink", 0o120000, str(path.readlink()))
        else:
            observed[rel] = ("regular", mode & 0o777, path.read_bytes())
    return observed


def test_capture_reconstructs_committed_complete_delivery_from_exact_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)

    (workspace / "edited.txt").write_text("after\n")
    (workspace / "deleted.txt").unlink()
    _git("mv", "renamed.txt", "moved.txt", cwd=workspace)
    (workspace / "binary.bin").write_bytes(b"\x00\xff\x10binary\x00")
    executable = workspace / "run.sh"
    executable.write_text("#!/bin/sh\necho delivery\n")
    executable.chmod(0o755)
    links = workspace / "links"
    links.mkdir()
    (links / "safe-ref").symlink_to("../moved.txt")
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "committed delivery", cwd=workspace)
    (workspace / "after-commit.txt").write_text("still part of delivery\n")

    target = tmp_path / "packet"
    capture = br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert capture.target == target
    assert capture.baseline == baseline
    assert set(capture.paths) == {
        "after-commit.txt",
        "binary.bin",
        "edited.txt",
        "links/safe-ref",
        "moved.txt",
        "run.sh",
    }
    assert capture.projection is not None
    transitions = {os.fsdecode(item.path.raw): item for item in capture.transitions}
    assert transitions["binary.bin"].after.kind == "regular"
    assert transitions["run.sh"].after.mode == 0o100755
    assert transitions["links/safe-ref"].after.kind == "symlink"
    assert transitions["deleted.txt"].after.kind == "absent"
    assert sorted(path.name for path in target.iterdir()) == [
        "DELIVERY-CHANGES.txt",
        "DELIVERY.patch",
    ]
    patch = (target / "DELIVERY.patch").read_text(encoding="utf-8")
    assert "after-commit.txt" in patch
    assert "GIT binary patch" in patch
    assert "old mode 100644" in patch
    assert "new mode 100755" in patch
    assert "deleted file mode" in patch
    manifest = (target / "DELIVERY-CHANGES.txt").read_text(encoding="utf-8")
    assert "M run.sh\n" in manifest
    assert "D deleted.txt\n" in manifest

    clone = tmp_path / "independent-clone"
    _git("clone", "-q", "--no-local", str(workspace), str(clone), cwd=tmp_path)
    _git("checkout", "-q", "--detach", baseline, cwd=clone)
    _git("apply", "--binary", str(target / "DELIVERY.patch"), cwd=clone)
    assert _projection(clone) == _projection(workspace)


def test_capture_canonicalizes_relative_workspace_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "controlled-cwd"
    workspace = root / "workspaces" / "delivery"
    workspace.parent.mkdir(parents=True)
    baseline = _init_repo(workspace)
    (workspace / "delivery.txt").write_text("relative paths work\n")

    monkeypatch.chdir(root)
    capture = br.capture_delivery_packet(
        Path("workspaces/delivery"), Path("packets/delivery"), baseline=baseline
    )

    assert capture.workspace == workspace.resolve()
    assert capture.target == (root / "packets/delivery").resolve()
    assert capture.target.is_dir()


@pytest.mark.skipif(os.name == "nt", reason="POSIX raw filename bytes")
def test_capture_preserves_non_utf8_path_and_symlink_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    root = os.fsencode(workspace)
    raw_name = b"result-\xff.bin"
    descriptor = os.open(root + b"/" + raw_name, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        os.write(descriptor, b"\x00\xffpayload")
    finally:
        os.close(descriptor)
    os.symlink(raw_name, root + b"/result-link")  # noqa: PTH211 - raw POSIX bytes

    target = tmp_path / "packet"
    capture = br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert any(item.path.raw == raw_name for item in capture.transitions)
    assert "@b64:" in (target / "DELIVERY-CHANGES.txt").read_text(encoding="utf-8")
    clone = tmp_path / "clone-non-utf8"
    _git("clone", "-q", "--no-local", str(workspace), str(clone), cwd=tmp_path)
    _git("checkout", "-q", "--detach", baseline, cwd=clone)
    _git("apply", "--binary", str(target / "DELIVERY.patch"), cwd=clone)
    assert br._delivery_projection(clone) == br._delivery_projection(workspace)


def test_capture_refuses_missing_or_head_baseline_without_target(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _init_repo(workspace)

    with pytest.raises(TypeError):
        br.capture_delivery_packet(workspace, tmp_path / "missing")  # type: ignore[call-arg]

    target = tmp_path / "head"
    with pytest.raises(br.DeliveryCaptureError, match="WHAT: strict capture"):
        br.capture_delivery_packet(workspace, target, baseline="HEAD")
    assert not target.exists()

    target = tmp_path / "unreachable"
    with pytest.raises(br.DeliveryCaptureError, match="not reachable"):
        br.capture_delivery_packet(workspace, target, baseline="0" * 40)
    assert not target.exists()


def test_capture_refuses_unsafe_symlink_without_partial_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    (workspace / "unsafe").symlink_to("/outside-the-delivery")
    target = tmp_path / "packet"

    with pytest.raises(br.DeliveryCaptureError, match="unsafe target"):
        br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert not target.exists()


def test_capture_refuses_gitignore_link_before_strip_can_write_through(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    outside = tmp_path / "outside-gitignore"
    original_bytes = (
        b"# nWave configuration (keep .nwave/config.json trackable)\n"
        b".nwave/*\n"
        b"!.nwave/config.json\n"
    )
    outside.write_bytes(original_bytes)
    (workspace / ".gitignore").symlink_to(outside)
    target = tmp_path / "packet"

    with pytest.raises(br.DeliveryCaptureError, match="unsafe target"):
        br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert outside.read_bytes() == original_bytes
    assert not target.exists()


def test_capture_refuses_tampered_writer_packet_without_partial_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    (workspace / "delivery.txt").write_text("real delivery\n")
    original_writer = br.write_delivery_packet

    def tampered_writer(workspace: Path, target: Path, baseline: str | None) -> int:
        result = original_writer(workspace, target, baseline)
        (target / "DELIVERY.patch").write_text("not a git patch\n", encoding="utf-8")
        return result

    monkeypatch.setattr(br, "write_delivery_packet", tampered_writer)
    target = tmp_path / "packet"

    with pytest.raises(br.DeliveryCaptureError, match="does not apply"):
        br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert not target.exists()


def test_capture_refuses_an_applicable_tampered_packet_with_wrong_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    (workspace / "delivery.txt").write_text("real delivery\n")
    original_writer = br.write_delivery_packet

    def incomplete_writer(workspace: Path, target: Path, baseline: str | None) -> int:
        result = original_writer(workspace, target, baseline)
        (target / "DELIVERY.patch").write_text("", encoding="utf-8")
        return result

    monkeypatch.setattr(br, "write_delivery_packet", incomplete_writer)
    target = tmp_path / "packet"

    with pytest.raises(br.DeliveryCaptureError, match="projection differs"):
        br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert not target.exists()


@pytest.mark.parametrize("manifest", ["", "M delivery.txt\n"])
def test_capture_refuses_complete_patch_with_empty_or_false_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest: str
) -> None:
    workspace = tmp_path / "workspace"
    baseline = _init_repo(workspace)
    (workspace / "delivery.txt").write_text("real delivery\n")
    original_writer = br.write_delivery_packet

    def false_manifest_writer(
        workspace: Path, target: Path, baseline: str | None
    ) -> int:
        result = original_writer(workspace, target, baseline)
        (target / "DELIVERY-CHANGES.txt").write_text(manifest, encoding="utf-8")
        return result

    monkeypatch.setattr(br, "write_delivery_packet", false_manifest_writer)
    target = tmp_path / "packet"

    with pytest.raises(br.DeliveryCaptureError, match="manifest differs"):
        br.capture_delivery_packet(workspace, target, baseline=baseline)

    assert not target.exists()
