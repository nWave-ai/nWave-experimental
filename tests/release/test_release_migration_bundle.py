"""Public CLI contract for the local, non-publishing bundle producer."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "release" / "release_migration_bundle.py"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def _wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "nwave_ai-1.2.3.dist-info/METADATA", "Name: nwave-ai\nVersion: 1.2.3\n"
        )
        archive.writestr("nwave_ai/__init__.py", "")


def test_capture_then_assemble_retains_exact_bytes_without_remote_write(
    tmp_path: Path,
) -> None:
    source, generated = tmp_path / "source", tmp_path / "generated"
    for repo in (source, generated):
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.name", "Test")
        _git(repo, "config", "user.email", "test@example.invalid")
        (repo / "module.py").write_text("one\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "initial")
    source_sha = _git(source, "rev-parse", "HEAD")
    parent = _git(generated, "rev-parse", "HEAD")
    remote = tmp_path / "generated-remote.git"
    _git(generated, "init", "--bare", str(remote))
    _git(generated, "remote", "add", "capture", str(remote))
    _git(generated, "push", "capture", f"{parent}:refs/heads/rc-release")
    (generated / "module.py").write_text("two\n", encoding="utf-8")
    _git(generated, "add", ".")
    wheel, evidence = (
        tmp_path / "nwave_ai-1.2.3-py3-none-any.whl",
        tmp_path / "evidence.json",
    )
    _wheel(wheel)
    evidence.write_text('{"compatible":true}\n', encoding="utf-8")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "predecessor": None,
                "retained_artifacts": [str(evidence)],
                "publication_units": [
                    {
                        "id": "rc.beta.commit",
                        "kind": "generated_commit",
                        "original_source_sha": source_sha,
                        "parent_oid": parent,
                        "author_name": "Test",
                        "author_email": "test@example.invalid",
                        "author_date": "0 +0000",
                        "committer_name": "Test",
                        "committer_email": "test@example.invalid",
                        "committer_date": "0 +0000",
                        "message_template": "release {decision_sha256}\n",
                    },
                    {
                        "id": "rc.beta.branch",
                        "kind": "git_branch",
                        "branch": "rc-release",
                        "remote": str(remote),
                        "predecessor": parent,
                        "target": {
                            "kind": "generated-commit",
                            "producer_unit": "rc.beta.commit",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    prepared = tmp_path / "prepared"
    capture = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "capture-review-input",
            "--channel",
            "rc",
            "--source-repo",
            str(source),
            "--source-sha",
            source_sha,
            "--candidate-wheel",
            str(wheel),
            "--publication-plan",
            str(plan),
            "--generated-worktree",
            f"rc.beta.commit={generated}",
            "--output",
            str(prepared),
        ],
        text=True,
        capture_output=True,
    )
    assert capture.returncode == 0, capture.stderr
    facts = json.loads((prepared / "prepared-release.json").read_text())
    assert (
        facts["candidate"]["wheel"]["sha256"]
        == hashlib.sha256(wheel.read_bytes()).hexdigest()
    )
    assert facts["publication_units"][0]["tree_oid"] == _git(generated, "write-tree")
    assert (prepared / "generated" / "rc.beta.commit" / "tree.tar").is_file()
    migration = prepared / "migration.json"
    migration.write_text(
        json.dumps(
            {
                "required": False,
                "compatibility_boundary": "same public contract",
                "evidence": [{"file": f"artifacts/{evidence.name}", "sha256": digest}],
            }
        ),
        encoding="utf-8",
    )
    bundle = tmp_path / "release-migration-decision.zip"
    assembled = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(bundle),
        ],
        text=True,
        capture_output=True,
    )
    assert assembled.returncode == 0, assembled.stderr
    with zipfile.ZipFile(bundle) as archive:
        decision = json.loads(archive.read("decision.json"))
        assert decision["candidate"]["wheel"]["file"] == f"artifacts/{wheel.name}"
        assert archive.read(f"artifacts/{wheel.name}") == wheel.read_bytes()
        archive.extractall(tmp_path / "extracted")
    consumer = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release" / "release_migration_decision.py"),
            "prepare-generated-commit",
            "--channel",
            "rc",
            "--decision",
            str(tmp_path / "extracted" / "decision.json"),
            "--repo-root",
            str(source),
            "--unit",
            "rc.beta.commit",
            "--worktree",
            str(generated),
            "--output-ref",
            str(tmp_path / "generated-ref.json"),
        ],
        text=True,
        capture_output=True,
    )
    assert consumer.returncode == 0, consumer.stderr
    generated_ref = tmp_path / "generated-ref.json"
    publish = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release" / "release_migration_decision.py"),
            "publish-unit",
            "--channel",
            "rc",
            "--decision",
            str(tmp_path / "extracted" / "decision.json"),
            "--repo-root",
            str(source),
            "--target-repo-root",
            str(generated),
            "--unit",
            "rc.beta.branch",
            "--artifact-root",
            str(tmp_path / "extracted"),
            "--generated-ref",
            str(generated_ref),
        ],
        text=True,
        capture_output=True,
    )
    assert publish.returncode == 0, publish.stderr
    assert publish.stdout == "Published\n"
    assert (
        _git(remote, "rev-parse", "refs/heads/rc-release")
        == json.loads(generated_ref.read_text(encoding="utf-8"))["commit_oid"]
    )
    exact_retry = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(bundle),
        ],
        text=True,
        capture_output=True,
    )
    assert exact_retry.returncode == 0, exact_retry.stderr
    assert (
        json.loads(exact_retry.stdout)["decision_sha256"]
        == json.loads(assembled.stdout)["decision_sha256"]
    )
    original_bundle = bundle.read_bytes()
    os.utime(prepared / "artifacts" / wheel.name, (1_700_000_000, 1_700_000_000))
    mtime_retry = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(bundle),
        ],
        text=True,
        capture_output=True,
    )
    assert mtime_retry.returncode == 0 and bundle.read_bytes() == original_bundle
    conflicting = tmp_path / "conflicting.zip"
    conflicting.write_bytes(b"keep")
    conflict = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(conflicting),
        ],
        text=True,
        capture_output=True,
    )
    assert conflict.returncode == 2 and conflicting.read_bytes() == b"keep"
    (prepared / "artifacts" / evidence.name).write_text(
        '{"compatible":false}\n', encoding="utf-8"
    )
    changed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(tmp_path / "changed.zip"),
        ],
        text=True,
        capture_output=True,
    )
    assert changed.returncode == 2
    assert "REFUSAL:" in changed.stderr
    assert not (tmp_path / "changed.zip").exists()
    (prepared / "artifacts" / evidence.name).write_text(
        '{"compatible":true}\n', encoding="utf-8"
    )
    (prepared / "generated" / "rc.beta.commit" / "tree.tar").write_bytes(b"changed")
    changed_review = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(tmp_path / "changed-review.zip"),
        ],
        text=True,
        capture_output=True,
    )
    assert changed_review.returncode == 2
    assert "REFUSAL:" in changed_review.stderr
    assert not (tmp_path / "changed-review.zip").exists()
    nested = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "assemble-decision-bundle",
            "--prepared",
            str(prepared / "prepared-release.json"),
            "--migration",
            str(migration),
            "--output",
            str(prepared / "nested.zip"),
        ],
        text=True,
        capture_output=True,
    )
    assert nested.returncode == 2
    assert "REFUSAL:" in nested.stderr
    assert not (prepared / "nested.zip").exists()
    assert _git(source, "status", "--porcelain") == ""
    assert _git(generated, "rev-parse", "HEAD") == parent


def test_capture_refuses_unsafe_generated_unit_before_creating_or_escaping_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Test")
    _git(source, "config", "user.email", "test@example.invalid")
    (source / "module.py").write_text("one\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "initial")
    wheel = tmp_path / "nwave_ai-1.2.3-py3-none-any.whl"
    _wheel(wheel)
    plan = tmp_path / "unsafe-plan.json"
    plan.write_text(
        json.dumps(
            {
                "predecessor": None,
                "publication_units": [
                    {"id": "../../escaped", "kind": "generated_commit"}
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "capture"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "capture-review-input",
            "--channel",
            "rc",
            "--source-repo",
            str(source),
            "--source-sha",
            _git(source, "rev-parse", "HEAD"),
            "--candidate-wheel",
            str(wheel),
            "--publication-plan",
            str(plan),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "REFUSAL:" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "escaped").exists()
    assert _git(source, "status", "--porcelain") == ""


def test_capture_refuses_retained_archive_name_collision_without_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Test")
    _git(source, "config", "user.email", "test@example.invalid")
    (source / "module.py").write_text("one\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "initial")
    wheel = tmp_path / "nwave_ai-1.2.3-py3-none-any.whl"
    _wheel(wheel)
    first = tmp_path / "first" / "evidence.json"
    second = tmp_path / "second" / "evidence.json"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text('{"compatible":true}\n', encoding="utf-8")
    second.write_text('{"compatible":false}\n', encoding="utf-8")
    plan = tmp_path / "collision-plan.json"
    plan.write_text(
        json.dumps(
            {
                "predecessor": None,
                "retained_artifacts": [str(first), str(second)],
                "publication_units": [{"id": "rc.release", "kind": "github_release"}],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "capture"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "capture-review-input",
            "--channel",
            "rc",
            "--source-repo",
            str(source),
            "--source-sha",
            _git(source, "rev-parse", "HEAD"),
            "--candidate-wheel",
            str(wheel),
            "--publication-plan",
            str(plan),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "REFUSAL:" in result.stderr
    assert not output.exists()
    assert _git(source, "status", "--porcelain") == ""
