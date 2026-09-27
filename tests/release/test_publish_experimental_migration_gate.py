"""Public CLI oracle for the experimental migration-decision write boundary.

Every invocation supplies a local bare target or an external command guard.
The test must therefore remain incapable of contacting the production target.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.release.experimental_migration_decision import short_sha_of
from scripts.release.release_migration_decision import (
    SCHEMA as WIRE_SCHEMA,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHER = REPO_ROOT / "scripts/release/publish_experimental.py"
MIGRATION_SOURCE_PATH = "scripts/release/publish_experimental.py"
MIGRATION_SOURCE_MEMBER = "nwave_ai_fixture/_migration_source.bin"
CHECKPOINTS = (
    "predecessor_identity",
    "candidate_wheel",
    "canonical_install_identity",
    "canonical_console_version",
    "canonical_installer",
    "public_des_migration",
    "doctor_json",
    "selected_root_config",
    "des_install_manifest",
)


def _run(argv: list[str], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    if env:
        environment.update(env)
    return subprocess.run(
        [sys.executable, str(PUBLISHER), *argv],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _git(*argv: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference(path: Path, record_dir: Path) -> dict[str, str]:
    return {"file": str(path.relative_to(record_dir)), "sha256": _sha(path)}


def _bare_target(
    tmp_path: Path, *, name: str = "nwave", version: str = "4.0.0+atddpure.predecessor"
) -> tuple[Path, str]:
    target = tmp_path / "experimental.git"
    _git("init", "--bare", "--initial-branch=main", str(target))
    seed = tmp_path / "seed"
    _git("init", "--initial-branch=main", str(seed))
    _git("config", "user.name", "Fixture", cwd=seed)
    _git("config", "user.email", "fixture@example.invalid", cwd=seed)
    (seed / "README.md").write_text("predecessor\n", encoding="utf-8")
    (seed / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\n', encoding="utf-8"
    )
    _git("add", "README.md", "pyproject.toml", cwd=seed)
    _git("commit", "-m", "predecessor", cwd=seed)
    _git("remote", "add", "origin", str(target), cwd=seed)
    _git("push", "origin", "main", cwd=seed)
    return target, _git("--git-dir", str(target), "rev-parse", "refs/heads/main")


def _git_show_bytes(sha: str, path: str, *, cwd: Path) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def _candidate_wheel(record_dir: Path, version: str, source_sha: str) -> Path:
    wheel = record_dir / "nwave_ai_fixture-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "nwave_ai_fixture-0.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: nwave-ai\nVersion: {version}\n",
        )
        # A required-migration decision's wheel_locator must point at a wheel
        # member with bytes identical to migration.path at candidate.source_sha
        # (see release_migration_decision._validate_required); embed it
        # unconditionally so both branches share one wheel builder.
        archive.writestr(
            MIGRATION_SOURCE_MEMBER,
            _git_show_bytes(source_sha, MIGRATION_SOURCE_PATH, cwd=REPO_ROOT),
        )
    return wheel


def _record(
    tmp_path: Path,
    *,
    predecessor: str,
    required: bool,
    source_sha: str,
) -> Path:
    record_dir = tmp_path / ("required" if required else "compatible")
    record_dir.mkdir()
    version = f"4.0.0+atddpure.{short_sha_of(source_sha)}"
    evidence = record_dir / "compatibility-evidence.json"
    evidence.write_text('{"boundary":"fixture"}\n', encoding="utf-8")
    wheel = _candidate_wheel(record_dir, version, source_sha)
    candidate = {
        "source_sha": source_sha,
        "name": "nwave-ai",
        "version": version,
        "wheel": _reference(wheel, record_dir),
    }
    predecessor_identity = {
        "name": "nwave",
        "version": "4.0.0+atddpure.predecessor",
    }
    migration: dict[str, object] = {
        "required": required,
        "compatibility_boundary": "fixture boundary",
        "evidence": [_reference(evidence, record_dir)],
    }
    if required:
        # These are controlled writer-contract fixtures.  They prove record
        # shape, path and digest binding only; they make no installed-upgrade
        # claim.  Installed upgrade evidence remains a separately retained
        # observation for the exact published candidate.
        proof = record_dir / "upgrade-proof.json"
        references = {}
        for checkpoint in CHECKPOINTS:
            stdout = record_dir / f"{checkpoint}.stdout.bin"
            stderr = record_dir / f"{checkpoint}.stderr.bin"
            if checkpoint == "predecessor_identity":
                observation = {
                    "distributions": {"nwave": predecessor_identity["version"]},
                    "module_owners": ["nwave"],
                }
            elif checkpoint == "candidate_wheel":
                observation = {
                    "Name": candidate["name"],
                    "Version": candidate["version"],
                    "SHA256": candidate["wheel"]["sha256"],
                }
            elif checkpoint == "canonical_install_identity":
                observation = {
                    "distributions": {"nwave-ai": candidate["version"]},
                    "module_owners": ["nwave-ai"],
                }
            elif checkpoint == "canonical_console_version":
                observation = {"version": candidate["version"]}
            elif checkpoint == "canonical_installer":
                observation = {
                    "installed_version": candidate["version"],
                    "status": "ok",
                }
            elif checkpoint == "public_des_migration":
                observation = {
                    "migration_path": "scripts/release/publish_experimental.py",
                    "status": "ok",
                }
            elif checkpoint == "doctor_json":
                observation = {"summary": {"failed": 0}, "status": "ok"}
            elif checkpoint == "selected_root_config":
                observation = {
                    "installed_version": candidate["version"],
                    "status": "ok",
                }
            else:
                observation = {
                    "installed_version": candidate["version"],
                    "status": "ok",
                }
            stdout.write_text(
                json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8"
            )
            stderr.write_bytes(b"")
            retained = record_dir / f"{checkpoint}.json"
            retained.write_text(
                json.dumps(
                    {
                        "checkpoint": checkpoint,
                        "candidate": candidate,
                        "predecessor": predecessor_identity,
                        "command": {
                            "argv": ["fixture", checkpoint],
                            "returncode": 0,
                            "stdout": _reference(stdout, record_dir),
                            "stderr": _reference(stderr, record_dir),
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            references[checkpoint] = _reference(retained, record_dir)
        proof.write_text(
            json.dumps(
                {
                    "kind": "public-distribution-upgrade-v1",
                    "candidate": candidate,
                    "predecessor": predecessor_identity,
                    "checkpoints": references,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        migration.update(
            {
                "path": MIGRATION_SOURCE_PATH,
                "source_locator": {"repo_path": MIGRATION_SOURCE_PATH},
                "wheel_locator": {"archive_member": MIGRATION_SOURCE_MEMBER},
                "upgrade_proof": {
                    "kind": "public-distribution-upgrade-v1",
                    "record": _reference(proof, record_dir),
                    "checkpoints": references,
                },
            }
        )
    record = record_dir / "decision.json"
    record.write_text(
        json.dumps(
            {
                "schema": WIRE_SCHEMA,
                "channel": "experimental",
                "candidate": candidate,
                "predecessor": {
                    "distribution_name": predecessor_identity["name"],
                    "version": predecessor_identity["version"],
                },
                "migration": migration,
                "publication_units": [
                    {
                        "id": "experimental.preview.branch",
                        "kind": "git_branch",
                        "branch": "main",
                        "remote": "local",
                        "predecessor": predecessor,
                        "target": source_sha,
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return record


def _source_sha() -> str:
    return _git("rev-parse", "HEAD", cwd=REPO_ROOT)


def _candidate_version(source_sha: str) -> str:
    return f"4.0.0+atddpure.{short_sha_of(source_sha)}"


def _guarded_path(tmp_path: Path) -> tuple[Path, Path]:
    """Return no-network gh/git guards and their invocation log.

    The real Git executable remains available for local source-ref inspection,
    while any gh clone is refused before it can use ambient credentials/network.
    """
    bin_dir = tmp_path / "guard-bin"
    bin_dir.mkdir()
    log = tmp_path / "guard.log"
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'printf "gh %s\\n" "$*" >> "$NWAVE_GUARD_LOG"\n'
        "exit 97\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    real_git = shutil.which("git")
    assert real_git is not None
    git = bin_dir / "git"
    git.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'printf "git %s\\n" "$*" >> "$NWAVE_GUARD_LOG"\n'
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8",
    )
    git.chmod(0o755)
    return bin_dir, log


def _local_target_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Guard every CLI test against an ignored local-target seam.

    `gh` has no route to the network.  Local Git remains real because the
    writer must exercise its actual clone and force-with-lease behavior.
    """
    guards, log = _guarded_path(tmp_path)
    return {
        "PATH": f"{guards}:{os.environ['PATH']}",
        "NWAVE_GUARD_LOG": str(log),
    }, log


def _assert_no_gh(log: Path) -> None:
    guarded = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "gh " not in guarded, guarded


def _rewrite_checkpoint_observation(
    record: Path, checkpoint: str, observation: dict[str, object]
) -> None:
    """Keep the proof-reference chain valid while corrupting observed meaning."""
    root = record.parent
    stdout = root / f"{checkpoint}.stdout.bin"
    stdout.write_text(json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8")
    checkpoint_path = root / f"{checkpoint}.json"
    checkpoint_value = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint_value["command"]["stdout"]["sha256"] = _sha(stdout)
    checkpoint_path.write_text(
        json.dumps(checkpoint_value, sort_keys=True) + "\n", encoding="utf-8"
    )
    proof_path = root / "upgrade-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["checkpoints"][checkpoint]["sha256"] = _sha(checkpoint_path)
    proof_path.write_text(json.dumps(proof, sort_keys=True) + "\n", encoding="utf-8")
    decision = json.loads(record.read_text(encoding="utf-8"))
    decision["migration"]["upgrade_proof"]["checkpoints"][checkpoint]["sha256"] = _sha(
        checkpoint_path
    )
    decision["migration"]["upgrade_proof"]["record"]["sha256"] = _sha(proof_path)
    record.write_text(json.dumps(decision, sort_keys=True) + "\n", encoding="utf-8")


def test_public_push_refuses_without_decision_before_clone(tmp_path: Path) -> None:
    """The public CLI must reject before any clone or writer subprocess."""
    guards, log = _guarded_path(tmp_path)
    result = _run(
        ["--push", "--allow-branch"],
        env={
            "PATH": f"{guards}:{os.environ['PATH']}",
            "NWAVE_GUARD_LOG": str(log),
        },
    )

    assert result.returncode != 0
    assert "migration decision" in (result.stdout + result.stderr).lower()
    guarded = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "gh repo clone" not in guarded, guarded
    assert "git clone" not in guarded and "git push" not in guarded, guarded


def test_required_false_accepts_evidence_and_boundary_without_upgrade_proof(
    tmp_path: Path,
) -> None:
    """Compatibility-only decisions do not need an irrelevant upgrade proof."""
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=False,
        source_sha=_source_sha(),
    )
    env, log = _local_target_env(tmp_path)

    result = _run(
        [
            "--push",
            "--allow-branch",
            "--target-local-repo",
            str(target),
            "--migration-decision",
            str(record),
        ],
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_no_gh(log)
    head = _git("--git-dir", str(target), "rev-parse", "refs/heads/main")
    assert head != predecessor
    message = _git("--git-dir", str(target), "log", "-1", "--format=%B")
    decision_hash = _sha(record)
    assert f"Source: {_source_sha()}" in message
    assert "Candidate: nwave-ai 4.0.0+atddpure." in message
    assert f"Decision-SHA256: {decision_hash}" in message


@pytest.mark.parametrize(
    "corrupt",
    [
        "missing-proof",
        "stale-predecessor",
        "bad-hash",
        "wrong-wheel",
        "wrong-name",
        "wrong-predecessor-observation",
        "wrong-canonical-observation",
    ],
)
def test_required_true_rejects_unbound_or_corrupt_upgrade_proof(
    tmp_path: Path, corrupt: str
) -> None:
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=True,
        source_sha=_source_sha(),
    )
    value = json.loads(record.read_text(encoding="utf-8"))
    if corrupt == "missing-proof":
        value["migration"].pop("upgrade_proof")
    elif corrupt == "stale-predecessor":
        value["publication_units"][0]["predecessor"] = "0" * 40
    elif corrupt == "bad-hash":
        value["candidate"]["wheel"]["sha256"] = "0" * 64
    elif corrupt == "wrong-wheel":
        value["candidate"]["version"] = "4.0.0+atddpure.wrong"
    elif corrupt == "wrong-name":
        value["candidate"]["name"] = "nwave"
    if corrupt == "wrong-predecessor-observation":
        _rewrite_checkpoint_observation(
            record,
            "predecessor_identity",
            {"distributions": {"nwave": "wrong"}, "module_owners": ["nwave"]},
        )
    elif corrupt == "wrong-canonical-observation":
        _rewrite_checkpoint_observation(
            record,
            "canonical_install_identity",
            {"distributions": {"nwave-ai": "wrong"}, "module_owners": ["nwave-ai"]},
        )
    else:
        record.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    env, log = _local_target_env(tmp_path)

    result = _run(
        [
            "--push",
            "--allow-branch",
            "--target-local-repo",
            str(target),
            "--migration-decision",
            str(record),
        ],
        env=env,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    _assert_no_gh(log)
    assert _git("--git-dir", str(target), "rev-parse", "refs/heads/main") == predecessor


def test_retry_footer_requires_one_unconflicted_value_per_key() -> None:
    from scripts.release.experimental_migration_decision import (
        Candidate,
        Decision,
        Predecessor,
        retry_message_matches,
    )

    decision = Decision(
        b"fixture",
        Path(),
        Candidate("source", "nwave-ai", "1+atddpure.x", {}),
        Predecessor("target", "nwave", "0"),
        {"required": False},
    )
    valid = f"Source: source\nCandidate: nwave-ai 1+atddpure.x\nDecision-SHA256: {decision.digest}\nChannel: experimental\n"
    assert retry_message_matches(valid, decision)
    assert not retry_message_matches(valid + "Source: other\n", decision)


def test_predecessor_metadata_check_refuses_a_null_predecessor_without_crashing() -> (
    None
):
    """A v4 decision may declare a null predecessor for an initial publication.

    The check binds an OBSERVED target commit to a DECLARED predecessor's
    package identity, so a null predecessor has nothing to bind against. It
    must fail loud with a DecisionRefusal (WHAT/WHY/HOW via the caller), not
    an AttributeError -- this module became a shared library one caller
    widened into a second (publish_experimental.py, then the release train's
    decode_decision), and an unguarded attribute access is exactly the
    unverified-agreement defect class this repair closes elsewhere.
    """
    from scripts.release.experimental_migration_decision import (
        DecisionRefusal,
        validate_predecessor_metadata,
    )

    decision = types.SimpleNamespace(predecessor=None)
    commit = "a" * 40

    with pytest.raises(DecisionRefusal, match="predecessor"):
        validate_predecessor_metadata(
            commit, '[project]\nname = "x"\nversion = "1"\n', decision, commit
        )


def test_required_true_accepts_a_complete_bound_writer_record(tmp_path: Path) -> None:
    """The writer's required branch is not a reject-all branch.

    This fixture proves only schema, source-path and byte-hash binding at the
    writer boundary.  It does not assert an installed-upgrade observation.
    """
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=True,
        source_sha=_source_sha(),
    )
    env, log = _local_target_env(tmp_path)

    result = _run(
        [
            "--push",
            "--allow-branch",
            "--target-local-repo",
            str(target),
            "--migration-decision",
            str(record),
        ],
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_no_gh(log)
    assert _git("--git-dir", str(target), "rev-parse", "refs/heads/main") != predecessor


def test_matching_retry_is_already_published_but_digest_mismatch_refuses(
    tmp_path: Path,
) -> None:
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=False,
        source_sha=_source_sha(),
    )
    argv = [
        "--push",
        "--allow-branch",
        "--target-local-repo",
        str(target),
        "--migration-decision",
        str(record),
    ]
    env, log = _local_target_env(tmp_path)
    first = _run(argv, env=env)
    assert first.returncode == 0, first.stdout + first.stderr
    _assert_no_gh(log)
    published = _git("--git-dir", str(target), "rev-parse", "refs/heads/main")

    retry = _run(argv, env=env)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert "ALREADY_PUBLISHED" in retry.stdout + retry.stderr
    assert _git("--git-dir", str(target), "rev-parse", "refs/heads/main") == published

    value = json.loads(record.read_text(encoding="utf-8"))
    value["migration"]["compatibility_boundary"] = "other boundary"
    record.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    mismatch = _run(argv, env=env)
    assert mismatch.returncode != 0, mismatch.stdout + mismatch.stderr
    assert _git("--git-dir", str(target), "rev-parse", "refs/heads/main") == published


def test_concurrent_target_head_is_preserved_by_cli_force_with_lease(
    tmp_path: Path,
) -> None:
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=False,
        source_sha=_source_sha(),
    )
    racer = tmp_path / "racer"
    _git("clone", str(target), str(racer))
    _git("config", "user.name", "Racer", cwd=racer)
    _git("config", "user.email", "racer@example.invalid", cwd=racer)
    (racer / "race.txt").write_text("concurrent\n", encoding="utf-8")
    _git("add", "race.txt", cwd=racer)
    _git("commit", "-m", "concurrent target advance", cwd=racer)
    race_head = _git("rev-parse", "HEAD", cwd=racer)

    env, log = _local_target_env(tmp_path)
    bin_dir = tmp_path / "race-bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'if [ "$1" = "push" ] && [ ! -e "$NWAVE_RACE_DONE" ]; then\n'
        '  touch "$NWAVE_RACE_DONE"\n'
        '  "$REAL_GIT" -C "$NWAVE_RACER" push origin main\n'
        "fi\n"
        'exec "$REAL_GIT" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    real_git = shutil.which("git")
    assert real_git is not None

    result = _run(
        [
            "--push",
            "--allow-branch",
            "--target-local-repo",
            str(target),
            "--migration-decision",
            str(record),
        ],
        env={
            **env,
            "PATH": f"{bin_dir}:{env['PATH']}",
            "REAL_GIT": real_git,
            "NWAVE_RACER": str(racer),
            "NWAVE_RACE_DONE": str(tmp_path / "race-done"),
        },
    )

    assert result.returncode != 0, result.stdout + result.stderr
    _assert_no_gh(log)
    assert _git("--git-dir", str(target), "rev-parse", "refs/heads/main") == race_head


def test_clone_disables_maintenance_autodetach_to_prevent_directory_not_empty(
    tmp_path: Path,
) -> None:
    """Publisher must disable autodetach settings in cloned targets.

    When temporary clones are removed and detached git maintenance processes are
    still running, cleanup fails with "Directory not empty" errors. The publisher
    prevents this by disabling gc.autodetach and maintenance.autodetach on the
    clone immediately after creation, ensuring all git operations are synchronous.

    This test uses --project-into to capture the publisher's own clone, verifying
    that the publisher (not the test) applies these settings, and that the clone
    remains functional for subsequent operations.
    """
    # Setup: local bare target and migration record
    target, predecessor = _bare_target(tmp_path)
    record = _record(
        tmp_path,
        predecessor=predecessor,
        required=False,
        source_sha=_source_sha(),
    )
    env, log = _local_target_env(tmp_path)

    # Execute: publisher with --project-into to capture the clone for inspection
    # (not --push, so no publication occurs; the clone remains after publisher exits)
    project_dir = tmp_path / "project"
    result = _run(
        [
            "--project-into",
            str(project_dir),
            "--allow-branch",
            "--target-local-repo",
            str(target),
            "--migration-decision",
            str(record),
        ],
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_no_gh(log)

    # Verify: inspect the clone the publisher created (before any commit).
    # The publisher projects to --project-into/target and stops before committing,
    # leaving the clone with exact configuration applied by the publisher itself.
    clone = project_dir / "target"
    assert clone.is_dir(), f"Expected publisher to project clone at {clone}"

    # Read autodetach settings from the publisher's clone.
    # These values must have been written by the publisher (via git config),
    # not pre-existing or inherited from system/user config. The publisher writes
    # them immediately after clone, using git -C, before any other operation.
    gc_autodetach = _git("config", "gc.autodetach", cwd=clone).strip()
    maintenance_autodetach = _git("config", "maintenance.autodetach", cwd=clone).strip()

    # Both must be explicitly "false"; if the publisher did not write them,
    # they would be absent (empty output) or show inherited values. The test
    # itself does not configure the clone—only the publisher does.
    assert gc_autodetach == "false", (
        f"Publisher must set gc.autodetach=false in clone; got '{gc_autodetach}'"
    )
    assert maintenance_autodetach == "false", (
        f"Publisher must set maintenance.autodetach=false in clone; "
        f"got '{maintenance_autodetach}'"
    )

    # Verify the clone is functional for git operations (add/commit/push integration).
    # The synchronous cleanup ensures that subsequent git operations (add, commit,
    # push) do not spawn detached maintenance processes that outlive the tempdir.
    status = _git("status", "--porcelain", cwd=clone)
    assert status is not None  # should succeed without error
