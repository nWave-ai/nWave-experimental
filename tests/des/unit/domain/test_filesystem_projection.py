"""Laws for the byte-preserving native filesystem projection."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from des.domain import filesystem_projection
from des.domain.filesystem_projection import (
    STRICT_DELIVERY_POLICY,
    FileState,
    FilesystemProjectionError,
    GitPath,
    PathTransition,
    ProjectionIndeterminate,
    ProjectionPolicy,
    WorkspaceProjection,
    observe_workspace,
    projection_from_bytes,
    projection_to_bytes,
)


def _state(projection: WorkspaceProjection, raw: bytes) -> FileState:
    return projection.state_at(GitPath(raw))


def test_values_refuse_invalid_or_ambiguous_construction() -> None:
    digest = "a" * 64

    for raw in (b"", b"/absolute", b"one//two", b"./one", b"one/../two", b"nul\0"):
        with pytest.raises(FilesystemProjectionError):
            GitPath(raw)
    with pytest.raises(FilesystemProjectionError):
        GitPath.from_base64("YQ")
    with pytest.raises(TypeError):
        FileState("regular", 0o100644, 0, digest)
    state = FileState.regular(0o100644, 0, digest)
    with pytest.raises(AttributeError, match="immutable"):
        state._kind = "symlink"  # type: ignore[misc]
    with pytest.raises(TypeError):
        FileState(object(), "regular", 0o100644, 0, digest)
    with pytest.raises(FilesystemProjectionError):
        FileState.regular(0o100600, 0, digest)
    with pytest.raises(FilesystemProjectionError):
        FileState.regular(0o100644, True, digest)
    with pytest.raises(FilesystemProjectionError):
        FileState.symlink(0, digest.upper())
    with pytest.raises(FilesystemProjectionError):
        PathTransition.changed(
            GitPath(b"same"),
            FileState.regular(0o100644, 0, digest),
            FileState.regular(0o100644, 0, digest),
        )
    with pytest.raises(FilesystemProjectionError):
        ProjectionPolicy((GitPath(b"user-owned"),))


def test_validated_values_refuse_normal_api_mutation() -> None:
    digest = "a" * 64
    path = GitPath(b"path")
    before = FileState.absent()
    after = FileState.regular(0o100644, 0, digest)
    transition = PathTransition.changed(path, before, after)
    projection = WorkspaceProjection.from_states({path: after})
    policy = ProjectionPolicy.native_capture()

    for value, attribute, replacement in (
        (path, "_raw", b"forged"),
        (after, "_kind", "forged"),
        (transition, "_after", before),
        (projection, "_states", ()),
        (policy, "_excluded_roots", ()),
    ):
        with pytest.raises(AttributeError, match="immutable"):
            setattr(value, attribute, replacement)
        with pytest.raises(AttributeError, match="immutable"):
            delattr(value, attribute)


def test_canonical_projection_round_trips_only_its_exact_bytes() -> None:
    digest = hashlib.sha256(b"\xff\x00").hexdigest()
    projection = WorkspaceProjection.from_states(
        {
            GitPath(b"z"): FileState.symlink(4, hashlib.sha256(b"../x").hexdigest()),
            GitPath(b"a\xff"): FileState.regular(0o100755, 2, digest),
        }
    )

    raw = projection_to_bytes(projection)

    assert raw == (
        b'{"schema_version":1,"states":[{"path":"Yf8=","state":{"kind":"regular","mode":"100755","sha256":"'
        + digest.encode()
        + b'","size":2}},{"path":"eg==","state":{"kind":"symlink","mode":"120000","sha256":"'
        + hashlib.sha256(b"../x").hexdigest().encode()
        + b'","size":4}}]}\n'
    )
    assert projection_from_bytes(raw) == projection
    with pytest.raises(FilesystemProjectionError, match="canonical"):
        projection_from_bytes(raw[:-1])
    with pytest.raises(FilesystemProjectionError):
        projection_from_bytes(b'{"schema_version":1,"schema_version":1,"states":[]}\n')
    with pytest.raises(FilesystemProjectionError):
        projection_from_bytes(
            b'{"schema_version":1,"states":[{"path":"YQ==","state":{"kind":"absent"}},{"path":"YQ==","state":{"kind":"absent"}}]}\n'
        )
    noncanonical = (
        json.dumps(
            {"schema_version": True, "states": []}, separators=(",", ":")
        ).encode()
        + b"\n"
    )
    with pytest.raises(FilesystemProjectionError):
        projection_from_bytes(noncanonical)


def test_observer_includes_ignored_files_and_excludes_only_constructed_des_roots(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_bytes(b"still observed")
    hidden = tmp_path / ".nwave" / "des" / "logs" / "turns" / "turn.json"
    hidden.parent.mkdir(parents=True)
    hidden.write_bytes(b"DES-owned record")
    visible = tmp_path / ".nwave" / "ordinary.txt"
    visible.write_bytes(b"included")

    observed = observe_workspace(tmp_path, ProjectionPolicy.native_capture())

    assert (
        _state(observed, b"ignored.txt").sha256
        == hashlib.sha256(b"still observed").hexdigest()
    )
    assert (
        _state(observed, b".nwave/ordinary.txt").sha256
        == hashlib.sha256(b"included").hexdigest()
    )
    assert _state(observed, b".nwave/des/logs/turns/turn.json").kind == "absent"


def test_strict_delivery_rules_match_legacy_basename_and_root_scopes(
    tmp_path: Path,
) -> None:
    """Setup rules prune first, while root-only residue stays legitimate below root."""
    outside = tmp_path.parent / "outside-python"
    outside.write_bytes(b"outside")
    fixture = tmp_path / "k4-fixture-venv" / "bin"
    fixture.mkdir(parents=True)
    (fixture / "python3.12").symlink_to(outside)
    nested = tmp_path / "delivery"
    (nested / "__pycache__").mkdir(parents=True)
    (nested / "__pycache__" / "cache.pyc").write_bytes(b"ignored")
    (nested / ".claude.json").write_bytes(b"ignored")
    (nested / ".venv-custom").mkdir()
    (nested / ".venv-custom" / "python").write_bytes(b"ignored")
    (nested / "hc.sqlite").write_bytes(b"delivery keeps this root-only name")
    (tmp_path / "hc.sqlite").write_bytes(b"fixture residue")
    (nested / "kept.txt").write_bytes(b"kept")

    arbitrary = ProjectionPolicy.from_excluded_roots((GitPath(b"setup"),))
    assert arbitrary.excludes(GitPath(b"setup/nested"))
    assert not arbitrary.excludes(GitPath(b"delivery"))
    observed = observe_workspace(tmp_path, STRICT_DELIVERY_POLICY)
    assert _state(observed, b"delivery/kept.txt").kind == "regular"
    assert _state(observed, b"delivery/hc.sqlite").kind == "regular"
    assert _state(observed, b"hc.sqlite").kind == "absent"
    assert _state(observed, b"k4-fixture-venv/bin/python3.12").kind == "absent"
    assert _state(observed, b"delivery/__pycache__/cache.pyc").kind == "absent"
    assert _state(observed, b"delivery/.claude.json").kind == "absent"
    assert _state(observed, b"delivery/.venv-custom/python").kind == "absent"

    (tmp_path / "unsafe-delivery-link").symlink_to(outside)
    with pytest.raises(ProjectionIndeterminate, match="escapes"):
        observe_workspace(tmp_path, STRICT_DELIVERY_POLICY)


@pytest.mark.skipif(os.name == "nt", reason="POSIX carries native filename bytes")
def test_observer_preserves_non_utf8_posix_filename_bytes(tmp_path: Path) -> None:
    name = b"non-utf8-\xff"
    location = os.fsencode(tmp_path) + b"/" + name
    descriptor = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(descriptor, b"bytes")
    finally:
        os.close(descriptor)

    observed = observe_workspace(tmp_path, ProjectionPolicy())

    assert _state(observed, name).sha256 == hashlib.sha256(b"bytes").hexdigest()
    assert GitPath(name).base64 == "bm9uLXV0Zjgt/w=="


def test_observer_records_binary_bytes_executable_mode_and_safe_link(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\x00\xff\x80payload")
    binary.chmod(0o755)
    (tmp_path / "inside.txt").write_bytes(b"target")
    (tmp_path / "safe-link").symlink_to("inside.txt")

    observed = observe_workspace(tmp_path, ProjectionPolicy())

    binary_state = _state(observed, b"binary.bin")
    assert binary_state == FileState.regular(
        0o100755,
        len(b"\x00\xff\x80payload"),
        hashlib.sha256(b"\x00\xff\x80payload").hexdigest(),
    )
    link_state = _state(observed, b"safe-link")
    assert link_state == FileState.symlink(
        len(b"inside.txt"), hashlib.sha256(b"inside.txt").hexdigest()
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX special bits are unavailable")
def test_observer_refuses_special_modes_nested_git_and_special_files(
    tmp_path: Path,
) -> None:
    special = tmp_path / "special"
    special.write_bytes(b"no")
    special.chmod(0o644 | stat.S_ISUID)
    with pytest.raises(ProjectionIndeterminate, match="special permission"):
        observe_workspace(tmp_path, ProjectionPolicy())

    special.chmod(0o644)
    nested = tmp_path / "nested" / ".git"
    nested.mkdir(parents=True)
    with pytest.raises(ProjectionIndeterminate, match="nested Git"):
        observe_workspace(tmp_path, ProjectionPolicy())

    nested.rmdir()
    nested.parent.rmdir()
    if hasattr(os, "mkfifo"):
        os.mkfifo(tmp_path / "pipe")
        with pytest.raises(
            ProjectionIndeterminate, match="unsupported filesystem type"
        ):
            observe_workspace(tmp_path, ProjectionPolicy())


def test_observer_refuses_escaping_and_dangling_links(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.write_bytes(b"outside")
    (tmp_path / "escape").symlink_to(outside)
    with pytest.raises(ProjectionIndeterminate, match="escapes"):
        observe_workspace(tmp_path, ProjectionPolicy())

    (tmp_path / "escape").unlink()
    (tmp_path / "dangling").symlink_to("missing")
    with pytest.raises(ProjectionIndeterminate, match="not safely realizable"):
        observe_workspace(tmp_path, ProjectionPolicy())


def test_windows_observer_excludes_git_and_observes_regular_and_directory_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"metadata")
    (tmp_path / "ordinary").write_bytes(b"file")
    (tmp_path / "target").mkdir()
    (tmp_path / "directory-link").symlink_to("target", target_is_directory=True)
    monkeypatch.setattr(
        filesystem_projection,
        "_git_index_modes",
        lambda _: {b"ordinary": 0o100755},
    )
    monkeypatch.setattr(filesystem_projection.os, "name", "nt")
    monkeypatch.delattr(filesystem_projection.os, "O_NOFOLLOW", raising=False)

    observed = observe_workspace(tmp_path, ProjectionPolicy())

    assert _state(observed, b".git/HEAD").kind == "absent"
    assert _state(observed, b"ordinary").mode == 0o100755
    assert _state(observed, b"directory-link").kind == "symlink"


def test_observer_refuses_an_index_gitlink_without_network(tmp_path: Path) -> None:
    def git(*arguments: str) -> bytes:
        completed = subprocess.run(
            ["git", "-C", str(tmp_path), *arguments],
            check=True,
            capture_output=True,
        )
        return completed.stdout

    git("init", "--quiet")
    git(
        "-c",
        "user.name=projection",
        "-c",
        "user.email=projection@example.invalid",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "seed",
    )
    commit = git("rev-parse", "HEAD").strip().decode("ascii")
    git("update-index", "--add", "--cacheinfo", f"160000,{commit},linked")

    with pytest.raises(ProjectionIndeterminate, match="Gitlink"):
        observe_workspace(tmp_path, ProjectionPolicy())


def test_snapshot_comparison_reports_additions_and_deletions_in_raw_path_order(
    tmp_path: Path,
) -> None:
    (tmp_path / "gone").write_bytes(b"old")
    before = observe_workspace(tmp_path, ProjectionPolicy())
    (tmp_path / "gone").unlink()
    (tmp_path / "added").write_bytes(b"new")
    after = observe_workspace(tmp_path, ProjectionPolicy())

    transitions = before.transitions_to(after)

    assert [
        (item.path.raw, item.before.kind, item.after.kind) for item in transitions
    ] == [
        (b"added", "absent", "regular"),
        (b"gone", "regular", "absent"),
    ]
