"""Public acceptance oracle for the release-migration decision boundary.

The production entry point is deliberately absent while this oracle is being
constructed. These examples describe real CLI effects; a missing entry point
is therefore RED, never an allowed ``not implemented`` outcome.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import pytest
from packaging.utils import parse_wheel_filename

from tests.release.release_migration_fixtures import (
    FAKE_GH,
    FAKE_TWINE,
    candidate_version,
    candidate_wheel,
    decision,
    fake_executable,
    reference,
    rewrite_wheel_member,
    sha256,
    update_checkpoint,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/release/release_migration_decision.py"
SOURCE_PATH = "scripts/release/experimental_migration_decision.py"
GITHUB_PRERELEASE_VERSION = "1.2.3rc1"

# Deliberately a proxy, not a mock: every command is delegated to local git.
# On the one push that the race test selects it advances the bare ref first.
GIT_RACE_PROXY = r"""import os, subprocess, sys
real = os.environ["REAL_GIT"]
race_remote = os.environ.get("FAKE_GIT_RACE_REMOTE")
race_ref = os.environ.get("FAKE_GIT_RACE_REF")
marker = os.environ.get("FAKE_GIT_RACE_MARKER")
args = sys.argv[1:]
if race_remote and race_ref and marker and not os.path.exists(marker) and args and args[0] == "push":
    parent = subprocess.check_output([real, "--git-dir", race_remote, "rev-parse", "refs/heads/" + race_ref], input="", text=True, timeout=20).strip()
    tree = subprocess.check_output([real, "--git-dir", race_remote, "show", "-s", "--format=%T", parent], input="", text=True, timeout=20).strip()
    env = {**os.environ, "GIT_AUTHOR_NAME": "Competitor", "GIT_AUTHOR_EMAIL": "competitor@example.invalid",
           "GIT_AUTHOR_DATE": "@2 +0000", "GIT_COMMITTER_NAME": "Competitor",
           "GIT_COMMITTER_EMAIL": "competitor@example.invalid", "GIT_COMMITTER_DATE": "@2 +0000"}
    competitor = subprocess.check_output([real, "--git-dir", race_remote, "commit-tree", tree, "-p", parent], input="race\n", text=True, env=env, timeout=20).strip()
    subprocess.run([real, "--git-dir", race_remote, "update-ref", "refs/heads/" + race_ref, competitor, parent], check=True, input="", text=True, timeout=20)
    open(marker, "w").write(competitor)
os.execv(real, [real, *args])"""


def _source(repo: Path = ROOT) -> tuple[str, bytes]:
    """Read the source blob from the selected commit, never the checkout."""
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        input="",
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    ).stdout.strip()
    source = subprocess.run(
        ["git", "show", f"{sha}:{SOURCE_PATH}"],
        cwd=repo,
        input="",
        capture_output=True,
        check=True,
        timeout=20,
    ).stdout
    return sha, source


def _run(
    root: Path, *args: str, extra: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    fake_executable(bindir / "gh", FAKE_GH)
    fake_executable(bindir / "twine", FAKE_TWINE)
    if extra and "FAKE_GIT_RACE_REMOTE" in extra:
        fake_executable(bindir / "git", GIT_RACE_PROXY)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "FAKE_GH_STATE": str(root / "gh.json"),
        "FAKE_TWINE_STATE": str(root / "index.json"),
        "FAKE_GH_SOURCE_REFS": str(root / "source-refs.json"),
        "GIT_ALLOW_PROTOCOL": "file",
        "REAL_GIT": shutil.which("git") or "/usr/bin/git",
        "FAKE_GIT_RACE_MARKER": str(root / "race-injected"),
    }
    if extra:
        env.update(extra)
    command = list(args)
    if command and command[0] == "publish-unit" and "--target-repo-root" not in command:
        command.extend(("--target-repo-root", str(cwd or ROOT)))
    return subprocess.run(
        [sys.executable, str(CLI), *command],
        cwd=cwd or ROOT,
        text=True,
        input="",
        capture_output=True,
        timeout=45,
        check=False,
        env=env,
    )


def _must_succeed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def _refuse(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0
    assert "refus" in (result.stdout + result.stderr).lower()


def _notes(root: Path, title: str) -> Path:
    path = root / "artifacts" / "RELEASE_NOTES.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\nDecision-bound release notes.\n", encoding="utf-8")
    return path


def _record(
    root: Path,
    *,
    channel: str = "dev",
    units: list[dict[str, object]],
    required: bool = False,
    source_repo: Path = ROOT,
    version: str | None = None,
    predecessor: str | None = None,
) -> Path:
    source_sha, source_bytes = _source(source_repo)
    version = candidate_version(channel, version)
    wheel = root / "dist" / f"nwave_ai-{version}-py3-none-any.whl"
    return decision(
        root,
        channel=channel,
        units=units,
        required=required,
        source_sha=source_sha,
        source_path=SOURCE_PATH,
        source_bytes=source_bytes,
        wheel=wheel if wheel.exists() else None,
        version=version,
        predecessor=predecessor,
    )


def _release_units(
    root: Path,
    channel: str = "dev",
    *,
    prerelease: bool = True,
    source_repo: Path = ROOT,
    target: object | None = None,
    version: str | None = None,
) -> list[dict[str, object]]:
    """Bind the exact candidate wheel, title, notes, target, and release state."""
    source_sha, source_bytes = _source(source_repo)
    version = candidate_version(channel, version)
    wheel, _ = candidate_wheel(
        root, channel=channel, version=version, source_bytes=source_bytes
    )
    artifact = root / "artifacts" / wheel.name
    artifact.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(wheel, artifact)
    title = f"{channel} {wheel.stem}"
    notes = _notes(root, title)
    metadata = {
        "id": f"{channel}.release",
        "kind": "github_release_metadata",
        "repository": "nWave-ai/nWave",
        "tag": f"v{version}",
        "target": source_sha if target is None else target,
        "title": title,
        "notes": reference(notes, root),
        "notes_sha256": sha256(notes),
        "prerelease": prerelease,
        "publication_predecessor": None,
    }
    return [
        metadata,
        {
            "id": f"{channel}.asset.{wheel.name}",
            "kind": "github_release_asset",
            "release_unit": metadata["id"],
            "file": wheel.name,
            "sha256": sha256(artifact),
            "size": artifact.stat().st_size,
        },
    ]


def _state(root: Path) -> dict[str, object]:
    return json.loads((root / "gh.json").read_text(encoding="utf-8"))


def _seed_gh_tag(root: Path, tag: str, target: str) -> None:
    """A release metadata write observes an already-created, exact Git tag."""
    write_json(
        root / "gh.json",
        {"calls": [], "releases": {}, "tags": {tag: target}, "runs": []},
    )


def _release_tag(channel: str) -> str:
    return f"v{candidate_version(channel)}"


@contextmanager
def _package_index(root: Path):
    """Expose fake immutable files through Simple and exact-version APIs."""
    state_path = root / "index.json"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state = (
                json.loads(state_path.read_text())
                if state_path.exists()
                else {"files": []}
            )
            files = state.get("files", [])
            if self.path == "/simple/nwave-ai/":
                payload = {
                    "meta": {"api-version": "1.0"},
                    "name": "nwave-ai",
                    "files": [{"filename": item["filename"]} for item in files],
                }
            else:
                prefix, suffix = "/pypi/nwave-ai/", "/json"
                if not self.path.startswith(prefix) or not self.path.endswith(suffix):
                    self.send_error(404, "unknown endpoint")
                    return
                version = unquote(self.path[len(prefix) : -len(suffix)]).strip("/")
                matching = []
                for item in files:
                    try:
                        _, file_version, _, _ = parse_wheel_filename(item["filename"])
                    except ValueError:
                        continue
                    if str(file_version) == version:
                        matching.append(item)
                if not matching:
                    self.send_error(404, "version not found")
                    return
                payload = {
                    "info": {"name": "nwave-ai", "version": version},
                    "urls": [
                        {
                            "filename": item["filename"],
                            "digests": {"sha256": item["sha256"]},
                        }
                        for item in matching
                    ],
                }
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/pypi/nwave-ai/json"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "channel,prerelease",
    [
        ("dev", True),
        ("rc", True),
        ("github-prerelease", True),
    ],
)
def test_exact_candidate_metadata_and_tag_paths_publish_for_each_channel(
    tmp_path: Path, channel: str, prerelease: bool
) -> None:
    units = _release_units(tmp_path, channel, prerelease=prerelease)
    record = _record(tmp_path, channel=channel, units=units, required=channel == "rc")
    version = candidate_version(channel)
    tag = f"v{version}"
    _seed_gh_tag(tmp_path, tag, str(units[0]["target"]))
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            channel,
            "--decision",
            str(record),
            "--unit",
            f"{channel}.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    release = _state(tmp_path)["releases"][tag]
    assert json.loads(record.read_text())["candidate"]["version"] == version
    assert release["tag_name"] == tag
    assert release["target_commitish"] == units[0]["target"]
    assert release["name"] == units[0]["title"]
    assert release["body"] == (
        _notes(tmp_path, str(units[0]["title"])).read_text()
        + f"\nMigration decision SHA-256: {sha256(record)}\n"
    )
    assert release["prerelease"] is prerelease
    assert "decision_sha256" not in release  # not a fictional GitHub API field


@pytest.mark.parametrize("required", [False, True])
def test_candidate_wheel_is_the_exact_asset_for_compatible_and_required_decisions(
    tmp_path: Path, required: bool
) -> None:
    units = _release_units(tmp_path, "dev")
    record = _record(tmp_path, units=units, required=required)
    asset_unit = units[1]
    tag = _release_tag("dev")
    _seed_gh_tag(tmp_path, tag, str(units[0]["target"]))
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            "dev.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            str(asset_unit["id"]),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    asset = _state(tmp_path)["releases"][tag]["assets"][0]
    assert asset["name"] == asset_unit["file"]
    assert asset["digest"] == f"sha256:{asset_unit['sha256']}"


def test_nonwheel_release_asset_retains_its_own_declared_identity(
    tmp_path: Path,
) -> None:
    units = _release_units(tmp_path, "dev")
    sums = tmp_path / "artifacts" / "SHA256SUMS"
    sums.write_text("fixture checksum\n", encoding="utf-8")
    units.append(
        {
            "id": "dev.release.sums",
            "kind": "github_release_asset",
            "release_unit": units[0]["id"],
            "file": sums.name,
            "sha256": sha256(sums),
            "size": sums.stat().st_size,
        }
    )
    record = _record(tmp_path, units=units)
    _seed_gh_tag(tmp_path, _release_tag("dev"), str(units[0]["target"]))
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            "dev.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            "dev.release.sums",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    assert _state(tmp_path)["releases"][_release_tag("dev")]["assets"][-1] == {
        "name": "SHA256SUMS",
        "size": sums.stat().st_size,
        "digest": f"sha256:{sha256(sums)}",
        "id": 1,
    }


def test_wrong_valid_live_github_predecessor_refuses_before_first_tag_push(
    tmp_path: Path,
) -> None:
    bare, work, source_sha = _seed_source_repo(tmp_path, "predecessor-gate")
    unit = {
        "id": "stable.tag",
        "kind": "git_tag",
        "repository": "nWave-ai/nWave",
        "tag": "v1.2.3",
        "remote": str(bare),
        "target": source_sha,
        "publication_predecessor": {
            "release_id": 8,
            "tag": "v1.2.2",
            "version": "1.2.2",
            "target_sha": "a" * 40,
        },
    }
    record = _record(tmp_path, channel="stable", units=[unit], source_repo=work)
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "runs": [],
            "tags": {"v1.2.2": "b" * 40},
            "releases": {
                "v1.2.2": {
                    "id": 9,
                    "tag_name": "v1.2.2",
                    "target_commitish": "ignored-by-predecessor-observer",
                    "name": "previous stable",
                    "body": "previous",
                    "draft": False,
                    "prerelease": False,
                    "assets": [],
                }
            },
        },
    )
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "stable",
            "--decision",
            str(record),
            "--unit",
            "stable.tag",
            "--artifact-root",
            str(tmp_path),
            cwd=work,
        )
    )
    assert not _git(["ls-remote", str(bare), "refs/tags/v1.2.3"], work)
    assert not any(
        call[:2] == ["release", "create"] for call in _state(tmp_path)["calls"]
    )


def test_github_predecessor_peels_a_remote_only_tag_sha_before_tag_push(
    tmp_path: Path,
) -> None:
    bare, work, source_sha = _seed_source_repo(tmp_path, "remote-only-predecessor")
    remote_sha = "b" * 40
    unit = {
        "id": "stable.tag",
        "kind": "git_tag",
        "repository": "nWave-ai/nWave",
        "tag": "v1.2.3",
        "remote": str(bare),
        "target": source_sha,
        "publication_predecessor": {
            "release_id": 9,
            "tag": "v1.2.1",
            "version": "1.2.1",
            "target_sha": remote_sha,
        },
    }
    record = _record(tmp_path, channel="stable", units=[unit], source_repo=work)
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "runs": [],
            "tags": {"v1.2.1": remote_sha},
            "releases": {
                "v1.2.1": {
                    "id": 9,
                    "tag_name": "v1.2.1",
                    "target_commitish": "not-the-peeled-sha",
                    "name": "previous stable",
                    "body": "previous",
                    "draft": False,
                    "prerelease": False,
                    "assets": [],
                }
            },
        },
    )
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "stable",
            "--decision",
            str(record),
            "--unit",
            "stable.tag",
            "--artifact-root",
            str(tmp_path),
            cwd=work,
        )
    )
    assert _git(["rev-parse", "v1.2.3^{commit}"], bare) == source_sha
    assert subprocess.run(
        ["git", "cat-file", "-e", f"{remote_sha}^{{commit}}"],
        cwd=work,
        input="",
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    ).returncode


def test_empty_qualifying_history_allows_null_initial_release(
    tmp_path: Path,
) -> None:
    units = _release_units(tmp_path, "stable", prerelease=False)
    record = _record(tmp_path, channel="stable", units=units)
    _seed_gh_tag(tmp_path, "v1.2.3", str(units[0]["target"]))
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "stable",
            "--decision",
            str(record),
            "--unit",
            "stable.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    history_calls = [call for call in _state(tmp_path)["calls"] if "--paginate" in call]
    assert history_calls and "--slurp" in history_calls[0]
    assert not any("/latest" in " ".join(call) for call in _state(tmp_path)["calls"])


def test_exact_release_retry_ignores_a_later_channel_release(
    tmp_path: Path,
) -> None:
    units = _release_units(tmp_path, "stable", prerelease=False)
    record = _record(tmp_path, channel="stable", units=units)
    metadata, asset = units
    candidate_tag = "v1.2.3"
    artifact = tmp_path / "artifacts" / str(asset["file"])
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "runs": [],
            "tags": {candidate_tag: metadata["target"], "v1.2.4": "c" * 40},
            "releases": {
                candidate_tag: {
                    "id": 9,
                    "tag_name": candidate_tag,
                    "target_commitish": metadata["target"],
                    "name": metadata["title"],
                    "body": _notes(tmp_path, str(metadata["title"])).read_text()
                    + f"\nMigration decision SHA-256: {sha256(record)}\n",
                    "prerelease": False,
                    "assets": [
                        {
                            "id": 1,
                            "name": artifact.name,
                            "size": artifact.stat().st_size,
                            "digest": f"sha256:{sha256(artifact)}",
                        }
                    ],
                },
                "v1.2.4": {
                    "id": 10,
                    "tag_name": "v1.2.4",
                    "target_commitish": "c" * 40,
                    "name": "later stable",
                    "body": "later",
                    "prerelease": False,
                    "assets": [],
                },
            },
        },
    )
    result = _run(
        tmp_path,
        "publish-unit",
        "--channel",
        "stable",
        "--decision",
        str(record),
        "--unit",
        "stable.release",
        "--artifact-root",
        str(tmp_path / "artifacts"),
    )
    _must_succeed(result)
    assert result.stdout.strip() == "PublishedExact"
    assert not any(
        call[:2] == ["release", "create"] for call in _state(tmp_path)["calls"]
    )


def test_malformed_github_pagination_refuses_without_tag_mutation(
    tmp_path: Path,
) -> None:
    bare, work, source_sha = _seed_source_repo(tmp_path, "malformed-history")
    unit = {
        "id": "stable.tag",
        "kind": "git_tag",
        "repository": "nWave-ai/nWave",
        "tag": "v1.2.3",
        "remote": str(bare),
        "target": source_sha,
        "publication_predecessor": None,
    }
    record = _record(tmp_path, channel="stable", units=[unit], source_repo=work)
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "release_pages": {"not": "pages"},
            "releases": {},
            "tags": {},
            "runs": [],
        },
    )
    result = _run(
        tmp_path,
        "publish-unit",
        "--channel",
        "stable",
        "--decision",
        str(record),
        "--unit",
        "stable.tag",
        "--artifact-root",
        str(tmp_path),
        cwd=work,
    )
    assert result.returncode == 3
    assert "pagination" in (result.stdout + result.stderr).lower()
    assert not _git(["ls-remote", str(bare), "refs/tags/v1.2.3"], work)


@pytest.mark.parametrize("corruption", ["mapped-bytes", "canonical-ownership"])
def test_rehashed_required_proof_mismatch_refuses_without_mutation(
    tmp_path: Path, corruption: str
) -> None:
    units = _release_units(tmp_path)
    record = _record(tmp_path, units=units, required=True)
    if corruption == "mapped-bytes":
        rewrite_wheel_member(
            record, "nwave_ai/release/decision.py", b"not source bytes\n"
        )
    else:
        update_checkpoint(
            record,
            "canonical_install_identity",
            {
                "checkpoint": "canonical_install_identity",
                "candidate": {"name": "other"},
                "ownership": {"nwave_ai.release.decision": "other-dist"},
            },
        )
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            "dev.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    assert not (tmp_path / "gh.json").exists()


@pytest.mark.parametrize("defect", ["wrong-candidate", "wrong-predecessor"])
def test_invalid_decision_starts_valid_and_refuses_only_its_selected_unit(
    tmp_path: Path, defect: str
) -> None:
    if defect == "wrong-predecessor":
        bare = tmp_path / "predecessor.git"
        _git(["clone", "--bare", str(ROOT), str(bare)], tmp_path)
        work = tmp_path / "predecessor-work"
        _git(["clone", str(bare), str(work)], tmp_path)
        _git(["config", "core.hooksPath", "/dev/null"], work)
        candidate, predecessor = (
            _git(["rev-parse", "HEAD"], ROOT),
            _git(["rev-parse", "HEAD^"], ROOT),
        )
        _git(
            ["push", str(bare), f"{predecessor}:refs/heads/decision-predecessor"], ROOT
        )
        unit = {
            "id": "rc.predecessor",
            "kind": "git_branch",
            "branch": "decision-predecessor",
            "remote": str(bare),
            "predecessor": predecessor,
            "target": candidate,
        }
        record = _record(tmp_path, channel="rc", units=[unit], predecessor=predecessor)
        value = json.loads(record.read_text())
        # This is another real selected-repository commit, not a malformed OID.
        value["predecessor"]["target_commit"] = _git(["rev-parse", "HEAD~2"], ROOT)
        write_json(record, value)
        _refuse(
            _run(
                tmp_path,
                "publish-unit",
                "--channel",
                "rc",
                "--decision",
                str(record),
                "--unit",
                "rc.predecessor",
                "--artifact-root",
                str(tmp_path / "artifacts"),
                cwd=work,
            )
        )
        assert (
            _git(["rev-parse", "refs/heads/decision-predecessor"], bare) == predecessor
        )
        return
    units = _release_units(tmp_path, "rc")
    record = _record(tmp_path, channel="rc", units=units)
    _seed_gh_tag(tmp_path, "v1.2.3rc1", str(units[0]["target"]))
    value = json.loads(record.read_text())
    value["candidate"]["version"] = "9.9.9"
    write_json(record, value)
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "rc",
            "--decision",
            str(record),
            "--unit",
            "rc.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    # Reads are legitimate observations. Mutation means only a create/upload.
    assert not any(
        call[:2] in (["release", "create"], ["release", "upload"])
        for call in _state(tmp_path).get("calls", [])
    )


def test_partial_exact_release_uploads_only_missing_candidate_asset_once(
    tmp_path: Path,
) -> None:
    units = _release_units(tmp_path, "dev")
    record = _record(tmp_path, units=units)
    metadata, asset = units
    tag = _release_tag("dev")
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "tags": {tag: metadata["target"]},
            "runs": [],
            "releases": {
                tag: {
                    "id": 7,
                    "tag_name": tag,
                    "target_commitish": metadata["target"],
                    "name": metadata["title"],
                    "body": _notes(tmp_path, str(metadata["title"])).read_text()
                    + f"\nMigration decision SHA-256: {sha256(record)}\n",
                    "prerelease": True,
                    "assets": [],
                }
            },
        },
    )
    for _ in range(2):
        _must_succeed(
            _run(
                tmp_path,
                "publish-unit",
                "--channel",
                "dev",
                "--decision",
                str(record),
                "--unit",
                str(asset["id"]),
                "--artifact-root",
                str(tmp_path / "artifacts"),
            )
        )
    state = _state(tmp_path)
    assert len(state["releases"][tag]["assets"]) == 1
    assert sum(call[:2] == ["release", "upload"] for call in state["calls"]) == 1


@pytest.mark.parametrize(
    "assets",
    [
        [
            {
                "name": "nwave_ai_fixture-1.2.3rc1-py3-none-any.whl",
                "size": 1,
                "digest": "sha256:" + "0" * 64,
                "id": 2,
            }
        ],
        [
            {
                "name": "undeclared.whl",
                "size": 1,
                "digest": "sha256:" + "0" * 64,
                "id": 3,
            }
        ],
    ],
)
def test_wrong_named_bytes_or_undeclared_asset_refuses_without_clobber(
    tmp_path: Path, assets: list[dict[str, object]]
) -> None:
    units = _release_units(tmp_path, "dev")
    record = _record(tmp_path, units=units)
    metadata = units[0]
    tag = _release_tag("dev")
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "tags": {tag: metadata["target"]},
            "runs": [],
            "releases": {
                tag: {
                    "id": 1,
                    "tag_name": tag,
                    "target_commitish": metadata["target"],
                    "name": metadata["title"],
                    "body": _notes(tmp_path, str(metadata["title"])).read_text()
                    + f"\nMigration decision SHA-256: {sha256(record)}\n",
                    "prerelease": True,
                    "assets": assets,
                }
            },
        },
    )
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            str(units[1]["id"]),
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    assert not any(
        call[:2] == ["release", "upload"] for call in _state(tmp_path)["calls"]
    )


@pytest.mark.parametrize("missing", ["title", "notes"])
def test_release_missing_title_or_notes_is_not_a_valid_metadata_completion(
    tmp_path: Path, missing: str
) -> None:
    units = _release_units(tmp_path, "dev")
    record = _record(tmp_path, units=units)
    metadata = units[0]
    tag = _release_tag("dev")
    release = {
        "id": 1,
        "tag_name": tag,
        "target_commitish": metadata["target"],
        "name": metadata["title"],
        "body": _notes(tmp_path, str(metadata["title"])).read_text()
        + f"\nMigration decision SHA-256: {sha256(record)}\n",
        "prerelease": True,
        "assets": [],
    }
    release["name" if missing == "title" else "body"] = ""
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "tags": {tag: metadata["target"]},
            "runs": [],
            "releases": {tag: release},
        },
    )
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--unit",
            "dev.release",
            "--artifact-root",
            str(tmp_path / "artifacts"),
        )
    )
    assert not any(
        call[:2] == ["release", "create"] for call in _state(tmp_path)["calls"]
    )


def test_snapshot_never_authorizes_a_live_write_and_publish_rejects_observations(
    tmp_path: Path,
) -> None:
    units = _release_units(tmp_path, "dev")
    record = _record(tmp_path, units=units)
    snapshot = write_json(tmp_path / "snapshot.json", {"releases": {}})
    _must_succeed(
        _run(
            tmp_path,
            "classify-snapshot",
            "--channel",
            "dev",
            "--decision",
            str(record),
            "--observations",
            str(snapshot),
        )
    )
    tag = _release_tag("dev")
    write_json(
        tmp_path / "gh.json",
        {
            "calls": [],
            "releases": {
                tag: {
                    "id": 1,
                    "tag_name": tag,
                    "target_commitish": "0" * 40,
                    "name": "wrong",
                    "body": "wrong",
                    "prerelease": False,
                    "assets": [],
                }
            },
            "tags": {},
            "runs": [],
        },
    )
    result = _run(
        tmp_path,
        "publish-unit",
        "--channel",
        "dev",
        "--decision",
        str(record),
        "--unit",
        "dev.release",
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--observations",
        str(snapshot),
    )
    assert (
        result.returncode != 0
        and "observations" in (result.stdout + result.stderr).lower()
    )
    assert not any(
        call[:2] == ["release", "create"] for call in _state(tmp_path)["calls"]
    )


def _git(args: list[str], cwd: Path) -> str:
    # The local bare-target setup must not inherit a hook path from the
    # enclosing developer checkout.  The publication CLI still uses its real
    # local Git boundary; this only keeps test setup hermetic.
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=cwd,
        input="",
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
        env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"},
    ).stdout.strip()


def _seed_source_repo(root: Path, name: str) -> tuple[Path, Path, str]:
    """Create a source repository containing the decision-bound source blob."""
    bare, work = root / f"{name}.git", root / f"{name}-work"
    _git(["init", "--bare", str(bare)], root)
    _git(["clone", str(bare), str(work)], root)
    _git(["config", "core.hooksPath", "/dev/null"], work)
    _git(["config", "user.name", "Fixture"], work)
    _git(["config", "user.email", "fixture@example.invalid"], work)
    source = work / SOURCE_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes(b"BOUND_MIGRATION = 'fixture'\n")
    (work / "payload").write_text("seed\n", encoding="utf-8")
    _git(["add", "."], work)
    _git(["commit", "-m", "seed source"], work)
    return bare, work, _git(["rev-parse", "HEAD"], work)


def test_generated_commit_is_byte_identical_then_publishes_branch_and_tag_with_lease(
    tmp_path: Path,
) -> None:
    bare, work, source_sha = _seed_source_repo(tmp_path, "target")
    # The remote starts at the decision-bound predecessor before its generated
    # candidate is prepared in the source worktree.
    _git(["push", "origin", f"{source_sha}:refs/heads/master-release"], work)
    assert _git(["rev-parse", "refs/heads/master-release"], bare) == source_sha
    parent, tree = source_sha, _git(["write-tree"], work)
    spec = {
        "id": "stable.master-commit",
        "kind": "generated_commit",
        "original_source_sha": source_sha,
        "tree_oid": tree,
        "parent_oid": parent,
        "author_name": "Bot",
        "author_email": "bot@example.invalid",
        "author_date": "1 +0000",
        "committer_name": "Bot",
        "committer_email": "bot@example.invalid",
        "committer_date": "1 +0000",
        "message_template": "release {decision_sha256}\n",
    }
    generated_target = {"kind": "generated-commit", "producer_unit": spec["id"]}
    release, asset = _release_units(
        tmp_path, "stable", prerelease=False, source_repo=work, target=generated_target
    )
    units = [
        spec,
        {
            "id": "stable.master-branch",
            "kind": "git_branch",
            "branch": "master-release",
            "remote": str(bare),
            "predecessor": parent,
            "target": generated_target,
        },
        {
            "id": "stable.tag",
            "kind": "git_tag",
            "repository": "nWave-ai/nWave",
            "tag": "v1.2.3",
            "remote": str(bare),
            "target": generated_target,
            "publication_predecessor": None,
        },
        release,
        asset,
    ]
    record = _record(
        tmp_path, channel="stable", units=units, required=True, source_repo=work
    )
    record_value = json.loads(record.read_text())
    candidate = record_value["candidate"]
    assert candidate["source_sha"] == spec["original_source_sha"] == source_sha
    assert candidate["version"] == "1.2.3"
    assert release["tag"] == "v1.2.3"
    assert release["target"] == generated_target
    assert asset["file"] == "nwave_ai-1.2.3-py3-none-any.whl"
    assert Path(str(candidate["wheel"]["file"])).name == asset["file"]
    assert asset["sha256"] == candidate["wheel"]["sha256"]
    assert asset["size"] == (tmp_path / "artifacts" / str(asset["file"])).stat().st_size
    assert (
        sha256(tmp_path / "artifacts" / str(asset["file"]))
        == candidate["wheel"]["sha256"]
    )
    with zipfile.ZipFile(tmp_path / candidate["wheel"]["file"]) as wheel:
        assert wheel.read("nwave_ai-1.2.3.dist-info/METADATA") == (
            b"Metadata-Version: 2.1\nName: nwave-ai\nVersion: 1.2.3\n"
        )
    proof = json.loads(
        (
            tmp_path / record_value["migration"]["upgrade_proof"]["record"]["file"]
        ).read_text()
    )
    checkpoint = json.loads(
        (tmp_path / proof["checkpoints"]["candidate_wheel"]["file"]).read_text()
    )
    observed = json.loads(
        (tmp_path / checkpoint["command"]["stdout"]["file"]).read_text()
    )
    assert proof["candidate"] == checkpoint["candidate"] == candidate
    assert observed == {
        "Name": "nwave-ai",
        "Version": "1.2.3",
        "SHA256": candidate["wheel"]["sha256"],
    }
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for output in (first, second):
        _must_succeed(
            _run(
                tmp_path,
                "prepare-generated-commit",
                "--channel",
                "stable",
                "--decision",
                str(record),
                "--unit",
                spec["id"],
                "--worktree",
                str(work),
                "--output-ref",
                str(output),
                cwd=work,
            )
        )
    generated_ref = json.loads(first.read_text())
    oid = generated_ref["commit_oid"]
    assert json.loads(second.read_text()) == generated_ref
    assert generated_ref["producer_unit"] == spec["id"]
    assert oid != source_sha == parent
    commit = _git(["cat-file", "-p", oid], work)
    assert f"tree {tree}" in commit and f"parent {parent}" in commit
    assert "author Bot <bot@example.invalid> 1 +0000" in commit
    assert "committer Bot <bot@example.invalid> 1 +0000" in commit
    assert f"release {sha256(record)}" in commit
    generated_ref_arg = ("--generated-ref", str(first))
    for unit in ("stable.master-branch", "stable.tag", "stable.tag"):
        _must_succeed(
            _run(
                tmp_path,
                "publish-unit",
                "--channel",
                "stable",
                "--decision",
                str(record),
                "--unit",
                unit,
                "--artifact-root",
                str(tmp_path / "artifacts"),
                *generated_ref_arg,
                cwd=work,
            )
        )
    assert _git(["rev-parse", "refs/heads/master-release"], bare) == oid
    tag_oid = _git(["rev-parse", "v1.2.3^{commit}"], bare)
    assert tag_oid == oid
    _seed_gh_tag(tmp_path, "v1.2.3", tag_oid)
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "stable",
            "--decision",
            str(record),
            "--unit",
            str(release["id"]),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            *generated_ref_arg,
            cwd=work,
        )
    )
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "stable",
            "--decision",
            str(record),
            "--unit",
            str(asset["id"]),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            *generated_ref_arg,
            cwd=work,
        )
    )
    state = _state(tmp_path)
    published = state["releases"]["v1.2.3"]
    assert state["tags"]["v1.2.3"] == tag_oid == generated_ref["commit_oid"]
    assert published["tag_name"] == release["tag"]
    assert published["target_commitish"] == tag_oid
    assert published["prerelease"] is False
    assert published["assets"] == [
        {
            "name": asset["file"],
            "size": asset["size"],
            "digest": f"sha256:{asset['sha256']}",
            "id": 1,
        }
    ]


def test_generated_commit_uses_explicit_distinct_source_and_target_repositories(
    tmp_path: Path,
) -> None:
    _, source, source_sha = _seed_source_repo(tmp_path, "source")
    target_bare, target = (
        tmp_path / "generated-target.git",
        tmp_path / "generated-target-work",
    )
    _git(["init", "--bare", str(target_bare)], tmp_path)
    _git(["clone", str(target_bare), str(target)], tmp_path)
    _git(["config", "core.hooksPath", "/dev/null"], target)
    _git(["config", "user.name", "Fixture"], target)
    _git(["config", "user.email", "fixture@example.invalid"], target)
    (target / "projection").write_text("parent\n", encoding="utf-8")
    _git(["add", "projection"], target)
    _git(["commit", "-m", "target parent"], target)
    parent = _git(["rev-parse", "HEAD"], target)
    _git(["push", "origin", "HEAD:refs/heads/public"], target)
    (target / "projection").write_text("generated\n", encoding="utf-8")
    _git(["add", "projection"], target)
    tree = _git(["write-tree"], target)
    assert source_sha != parent and tree != _git(
        ["show", "-s", "--format=%T", parent], target
    )
    spec = {
        "id": "rc.public-commit",
        "kind": "generated_commit",
        "original_source_sha": source_sha,
        "tree_oid": tree,
        "parent_oid": parent,
        "author_name": "Bot",
        "author_email": "bot@example.invalid",
        "author_date": "1 +0000",
        "committer_name": "Bot",
        "committer_email": "bot@example.invalid",
        "committer_date": "1 +0000",
        "message_template": "generated {decision_sha256}\n",
    }
    generated = {"kind": "generated-commit", "producer_unit": spec["id"]}
    units = [
        spec,
        {
            "id": "rc.public-branch",
            "kind": "git_branch",
            "branch": "public",
            "remote": str(target_bare),
            "predecessor": parent,
            "target": generated,
        },
    ]
    record = _record(
        tmp_path, channel="rc", units=units, source_repo=source, predecessor=parent
    )
    output = tmp_path / "generated-ref.json"
    _must_succeed(
        _run(
            tmp_path,
            "prepare-generated-commit",
            "--channel",
            "rc",
            "--decision",
            str(record),
            "--repo-root",
            str(source),
            "--unit",
            spec["id"],
            "--worktree",
            str(target),
            "--output-ref",
            str(output),
            cwd=target,
        )
    )
    ref = json.loads(output.read_text())
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "rc",
            "--decision",
            str(record),
            "--repo-root",
            str(source),
            "--target-repo-root",
            str(target),
            "--unit",
            "rc.public-branch",
            "--artifact-root",
            str(tmp_path),
            "--generated-ref",
            str(output),
            cwd=target,
        )
    )
    assert _git(["rev-parse", "refs/heads/public"], target_bare) == ref["commit_oid"]
    assert _git(["rev-parse", "HEAD"], source) == source_sha


def test_branch_lease_race_refuses_and_preserves_competing_head(tmp_path: Path) -> None:
    bare, work, parent = _seed_source_repo(tmp_path, "race")
    _git(["push", "origin", "HEAD:race"], work)
    (work / "payload").write_text("desired\n", encoding="utf-8")
    _git(["add", "payload"], work)
    _git(["commit", "-m", "desired candidate"], work)
    desired = _git(["rev-parse", "HEAD"], work)
    assert desired != parent
    record = _record(
        tmp_path,
        channel="stable",
        units=[
            {
                "id": "stable.race",
                "kind": "git_branch",
                "branch": "race",
                "remote": str(bare),
                "predecessor": parent,
                "target": desired,
            }
        ],
        source_repo=work,
        predecessor=parent,
    )
    result = _run(
        tmp_path,
        "publish-unit",
        "--channel",
        "stable",
        "--decision",
        str(record),
        "--unit",
        "stable.race",
        "--artifact-root",
        str(tmp_path),
        cwd=work,
        extra={"FAKE_GIT_RACE_REMOTE": str(bare), "FAKE_GIT_RACE_REF": "race"},
    )
    assert result.returncode != 0
    assert any(
        word in (result.stdout + result.stderr).lower() for word in ("retry", "refus")
    )
    competitor = (tmp_path / "race-injected").read_text()
    assert _git(["rev-parse", "race"], bare) == competitor
    assert competitor not in {parent, desired}


def test_github_prerelease_first_tag_is_a_standalone_tag_unit_not_a_dispatch(
    tmp_path: Path,
) -> None:
    # Use a local clone of this repository so the selected source object exists
    # at the target; the unit is intentionally a tag, never workflow_dispatch.
    bare = tmp_path / "standalone.git"
    _git(["clone", "--bare", str(ROOT), str(bare)], tmp_path)
    work = tmp_path / "standalone-work"
    _git(["clone", str(bare), str(work)], tmp_path)
    _git(["config", "core.hooksPath", "/dev/null"], work)
    source_sha, _ = _source(work)
    tag = f"release-migration-fixture-v{GITHUB_PRERELEASE_VERSION}"
    assert not _git(["ls-remote", str(bare), f"refs/tags/{tag}"], ROOT)
    unit = {
        "id": "github-prerelease.tag",
        "kind": "git_tag",
        "repository": "nWave-ai/nWave",
        "tag": tag,
        "remote": str(bare),
        "target": source_sha,
        "publication_predecessor": None,
    }
    record = _record(
        tmp_path,
        channel="github-prerelease",
        units=[unit],
        version=GITHUB_PRERELEASE_VERSION,
        source_repo=work,
    )
    _must_succeed(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "github-prerelease",
            "--decision",
            str(record),
            "--unit",
            "github-prerelease.tag",
            "--artifact-root",
            str(tmp_path),
            cwd=work,
        )
    )
    assert _git(["rev-parse", f"{tag}^{{commit}}"], bare) == source_sha


@pytest.mark.parametrize(
    "parent,child,workflow",
    [
        ("rc", "dev", "release-dev.yml"),
        ("dev", "rc", "release-rc.yml"),
        ("rc", "stable", "release-prod.yml"),
    ],
)
def test_nested_dispatch_requires_its_own_downstream_decision_and_correlates_retry(
    tmp_path: Path, parent: str, child: str, workflow: str
) -> None:
    child_source, _ = _source()
    child_unit = {
        "id": f"{child}.selected-tag",
        "kind": "git_tag",
        "repository": "nWave-ai/nWave",
        "tag": f"{child}-candidate",
        "remote": str(tmp_path / "child.git"),
        "target": child_source,
        "publication_predecessor": None,
    }
    child_record = _record(tmp_path / "child", channel=child, units=[child_unit])
    unit = {
        "id": f"{parent}.dispatch-{child}",
        "kind": "workflow_dispatch",
        "repository": "nWave-ai/nWave",
        "workflow": workflow,
        "ref": "master",
        "source_sha": child_source,
        "downstream_channel": child,
        "downstream_decision_sha256": sha256(child_record),
        "downstream_decision_handle": "--downstream-decision",
        "downstream_source_sha": child_source,
    }
    parent_record = _record(tmp_path / "parent", channel=parent, units=[unit])
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            parent,
            "--decision",
            str(parent_record),
            "--unit",
            str(unit["id"]),
            "--artifact-root",
            str(tmp_path),
        )
    )
    assert not (tmp_path / "gh.json").exists()
    write_json(tmp_path / "source-refs.json", {"master": child_source})
    args = (
        "publish-unit",
        "--channel",
        parent,
        "--decision",
        str(parent_record),
        "--unit",
        str(unit["id"]),
        "--artifact-root",
        str(tmp_path),
        "--downstream-decision",
        str(child_record),
    )
    _must_succeed(_run(tmp_path, *args))
    _must_succeed(_run(tmp_path, *args))
    state = _state(tmp_path)
    assert sum(call[:2] == ["workflow", "run"] for call in state["calls"]) == 1
    run = state["runs"][0]
    assert run["headSha"] == child_source
    assert run["source_sha"] == child_source
    assert run["decision_sha256"] == sha256(child_record)
    wrong_channel = _record(
        tmp_path / "wrong-channel", channel="github-prerelease", units=[child_unit]
    )
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            parent,
            "--decision",
            str(parent_record),
            "--unit",
            str(unit["id"]),
            "--artifact-root",
            str(tmp_path),
            "--downstream-decision",
            str(wrong_channel),
        )
    )
    wrong_source = _record(
        tmp_path / "wrong-source",
        channel=child,
        units=[{**child_unit, "target": "0" * 40}],
    )
    wrong_value = json.loads(wrong_source.read_text())
    wrong_value["candidate"]["source_sha"] = "0" * 40
    write_json(wrong_source, wrong_value)
    _refuse(
        _run(
            tmp_path,
            "publish-unit",
            "--channel",
            parent,
            "--decision",
            str(parent_record),
            "--unit",
            str(unit["id"]),
            "--artifact-root",
            str(tmp_path),
            "--downstream-decision",
            str(wrong_source),
        )
    )
    assert (
        sum(call[:2] == ["workflow", "run"] for call in _state(tmp_path)["calls"]) == 1
    )


def test_package_index_observer_uses_named_endpoint_and_immutable_candidate_bytes(
    tmp_path: Path,
) -> None:
    wheel, _ = candidate_wheel(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    candidate = artifacts / wheel.name
    shutil.copyfile(wheel, candidate)
    with _package_index(tmp_path) as endpoint:
        unit = {
            "id": "rc.testpypi",
            "kind": "package_index_upload",
            "repository": "testpypi",
            "endpoint": endpoint,
            "file": candidate.name,
            "sha256": sha256(candidate),
            "size": candidate.stat().st_size,
            "publication_predecessor_version": None,
        }
        record = _record(tmp_path, channel="rc", units=[unit])
        args = (
            "publish-unit",
            "--channel",
            "rc",
            "--decision",
            str(record),
            "--unit",
            "rc.testpypi",
            "--artifact-root",
            str(artifacts),
            "--package-index-endpoint",
            endpoint,
        )
        # The exact candidate's 404 and an empty official Index inventory are
        # an observed initial publication, not an outage.
        _must_succeed(_run(tmp_path, *args))
        _must_succeed(_run(tmp_path, *args))
        state = json.loads((tmp_path / "index.json").read_text())
        assert state["files"] == [
            {"filename": candidate.name, "sha256": sha256(candidate)}
        ]
        assert state["uploads"] == [
            {"filename": candidate.name, "sha256": sha256(candidate)}
        ]
        state["files"] = [{"filename": candidate.name, "sha256": "0" * 64}]
        write_json(tmp_path / "index.json", state)
        _refuse(_run(tmp_path, *args))


def test_wrong_valid_live_package_predecessor_refuses_before_upload(
    tmp_path: Path,
) -> None:
    wheel, _ = candidate_wheel(tmp_path, channel="rc")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    candidate = artifacts / wheel.name
    shutil.copyfile(wheel, candidate)
    with _package_index(tmp_path) as endpoint:
        unit = {
            "id": "rc.testpypi",
            "kind": "package_index_upload",
            "repository": "testpypi",
            "endpoint": endpoint,
            "file": candidate.name,
            "sha256": sha256(candidate),
            "size": candidate.stat().st_size,
            "publication_predecessor_version": "1.2.1rc1",
        }
        record = _record(tmp_path, channel="rc", units=[unit])
        write_json(
            tmp_path / "index.json",
            {
                "files": [
                    {
                        "filename": "nwave_ai-1.2.1rc1-py3-none-any.whl",
                        "sha256": "a" * 64,
                    },
                    {
                        "filename": "nwave_ai-1.2.2rc1-py3-none-any.whl",
                        "sha256": "b" * 64,
                    },
                ],
                "uploads": [],
            },
        )
        _refuse(
            _run(
                tmp_path,
                "publish-unit",
                "--channel",
                "rc",
                "--decision",
                str(record),
                "--unit",
                "rc.testpypi",
                "--artifact-root",
                str(artifacts),
                "--package-index-endpoint",
                endpoint,
            )
        )
        assert json.loads((tmp_path / "index.json").read_text())["uploads"] == []


def test_exact_package_retry_ignores_a_later_qualifying_version(
    tmp_path: Path,
) -> None:
    wheel, _ = candidate_wheel(tmp_path, channel="rc")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    candidate = artifacts / wheel.name
    shutil.copyfile(wheel, candidate)
    with _package_index(tmp_path) as endpoint:
        unit = {
            "id": "rc.testpypi",
            "kind": "package_index_upload",
            "repository": "testpypi",
            "endpoint": endpoint,
            "file": candidate.name,
            "sha256": sha256(candidate),
            "size": candidate.stat().st_size,
            "publication_predecessor_version": "1.2.2rc1",
        }
        record = _record(tmp_path, channel="rc", units=[unit])
        write_json(
            tmp_path / "index.json",
            {
                "files": [
                    {"filename": candidate.name, "sha256": sha256(candidate)},
                    {
                        "filename": "nwave_ai-1.2.4rc1-py3-none-any.whl",
                        "sha256": "d" * 64,
                    },
                ],
                "uploads": [],
            },
        )
        result = _run(
            tmp_path,
            "publish-unit",
            "--channel",
            "rc",
            "--decision",
            str(record),
            "--unit",
            "rc.testpypi",
            "--artifact-root",
            str(artifacts),
            "--package-index-endpoint",
            endpoint,
        )
        _must_succeed(result)
        assert result.stdout == "PublishedExact\n"
        assert json.loads((tmp_path / "index.json").read_text())["uploads"] == []
