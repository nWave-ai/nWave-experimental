"""Oracle: one local run produces a verified decision bundle bound to one sha.

Every case drives the real command as a subprocess through
`experimental_decision_bundle_promise`, so the oracle and the declared local
verification exercise one identical stimulus.  That stimulus always names a
locally seeded bare destination, which the command observes read-only to bind
the really published predecessor into the bundle it emits.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from tests.release.experimental_decision_bundle_promise import (
    GENERATED_UNIT,
    GUESS_LEASE,
    GUESS_NAME,
    GUESS_VERSION,
    PATCH_REVIEW,
    REPO_ROOT,
    TARGET_BRANCH,
    TREE_REVIEW,
    CandidateSource,
    broken_reason,
    destination_fingerprint,
    observed_predecessor_independently,
    other_commit,
    produce,
    refusal_broken_reason,
    seed_destination,
)


DEAD_INDEX = {
    "PIP_INDEX_URL": "http://127.0.0.1:9/simple",
    "PIP_RETRIES": "0",
    "PIP_TIMEOUT": "1",
}


@pytest.fixture()
def isolated_checkout(tmp_path: Path) -> Path:
    """Copy the current candidate to a private checkout for release commands."""
    source = REPO_ROOT
    isolated = tmp_path / "isolated-repo"
    subprocess.run(
        ["git", "clone", "--quiet", str(source), str(isolated)],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=True,
    )

    changed = subprocess.run(
        ["git", "diff", "--name-only", "-z", "HEAD"],
        cwd=source,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=True,
    ).stdout
    delta = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=source,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=True,
    ).stdout
    if delta:
        subprocess.run(
            ["git", "apply", "--binary", "-"],
            cwd=isolated,
            input=delta,
            capture_output=True,
            timeout=120,
            check=True,
        )

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=source,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
        check=True,
    ).stdout
    candidate_paths = [
        *((raw_path, False) for raw_path in changed.split(b"\0")),
        *((raw_path, True) for raw_path in untracked.split(b"\0")),
    ]
    for raw_path, is_untracked in candidate_paths:
        if not raw_path:
            continue
        relative = Path(raw_path.decode())
        source_path = source / relative
        destination = isolated / relative
        if not source_path.exists() and not source_path.is_symlink():
            assert not destination.exists()
            continue
        if is_untracked:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_path.is_symlink():
                destination.symlink_to(source_path.readlink())
            else:
                shutil.copy2(source_path, destination)
        assert destination.is_symlink() == source_path.is_symlink()
        if source_path.is_symlink():
            assert destination.readlink() == source_path.readlink()
        else:
            assert destination.read_bytes() == source_path.read_bytes()

    return isolated


@pytest.mark.acceptance
@pytest.mark.slow
def test_one_local_run_emits_a_verified_bundle_bound_to_the_given_sha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], isolated_checkout: Path
) -> None:
    """The command promise runs from a private copy of the current candidate."""
    result = subprocess.run(
        [
            sys.executable,
            str(
                isolated_checkout
                / "tests/release/experimental_decision_bundle_promise.py"
            ),
        ],
        cwd=isolated_checkout,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=1800,
        check=False,
    )
    with capsys.disabled():
        sys.stdout.write(result.stdout)
        sys.stdout.write(result.stderr)

    assert "PROMISE: held" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0


@pytest.mark.acceptance
@pytest.mark.slow
def test_a_failing_candidate_build_refuses_and_leaves_no_bundle(
    tmp_path: Path,
    isolated_checkout: Path,
) -> None:
    """A build that cannot complete must refuse, never emit a bundle.

    The stimulus is the command's own process environment pointed at a dead
    package index, which makes the isolated candidate wheel build exit nonzero.
    The refusal must be bound to that exit status: no bundle may be left at
    --output on the strength of a build that failed.
    """
    run = produce(
        tmp_path / "work", env=DEAD_INDEX, source=CandidateSource(isolated_checkout)
    )

    assert run.returncode == 2, (run.returncode, run.stdout, run.stderr)
    refusals = [
        line for line in run.stderr.splitlines() if line.startswith("REFUSAL: ")
    ]
    assert len(refusals) == 1, run.stderr
    assert " WHY: " in refusals[0] and " HOW: " in refusals[0]
    assert not run.output.exists()
    assert run.status_after == run.status_before
    assert broken_reason(run) is not None


@pytest.mark.acceptance
@pytest.mark.slow
def test_an_unfaithful_plan_is_refused_with_no_output_and_an_untouched_destination(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    isolated_checkout: Path,
) -> None:
    """Inputs that cannot yield a faithful bundle refuse, cleanly and visibly.

    The operator's plan declares its generated publication material as coming
    from the candidate's PARENT commit while the run is asked to bind the
    candidate itself.  A bundle built from those inputs would be unfaithful to
    the given sha, so the one command must refuse instead of emitting one.

    The refusal is judged on what an operator can actually see and act on: a
    single operator-visible reason that names the offending unit and BOTH
    disagreeing shas, no partial output of any kind in the dedicated output
    directory, and a destination repository -- every ref and every object --
    byte-identical to the one the run was handed.  A recording `gh` sits first
    on PATH throughout, so `creates or publishes no release` is observed as a
    recorded fact rather than assumed.
    """
    destination = seed_destination(tmp_path / "destination.git")
    fingerprint_before = destination_fingerprint(destination)
    unfaithful_sha = other_commit(repo_root=isolated_checkout)

    run = produce(
        tmp_path / "work",
        destination=destination,
        plan_source_sha=unfaithful_sha,
        source=CandidateSource(isolated_checkout),
    )

    with capsys.disabled():
        sys.stdout.write(run.stdout)
        sys.stdout.write(run.stderr)

    assert refusal_broken_reason(run) is None, (run.returncode, run.stdout, run.stderr)

    assert run.returncode == 2
    assert run.plan_source_sha == unfaithful_sha != run.source_sha
    assert not run.output.exists()
    assert run.output_listing == []
    assert run.gh_calls == []
    assert run.status_after == run.status_before
    assert destination_fingerprint(destination) == fingerprint_before
    assert broken_reason(run) is not None


PUBLISHED_NAME = "nwave-ai"
PUBLISHED_VERSION = "4.0.0+atddpure.0badc0de1"


@pytest.mark.acceptance
@pytest.mark.slow
def test_the_emitted_bundle_binds_the_predecessor_observed_on_the_destination(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    isolated_checkout: Path,
) -> None:
    """The bundle names the release really published on the destination.

    The destination is a bare repository seeded HERE with an identity of this
    test's choosing, while the operator's plan hands the command a wrong guess.
    One run of the real command must therefore emit a bundle carrying the
    observed identity and the observed head as its CAS lease -- never the guess
    -- and must leave the destination byte-identical, having only read it.
    """
    destination = seed_destination(
        tmp_path / "destination.git",
        name=PUBLISHED_NAME,
        version=PUBLISHED_VERSION,
    )
    published_commit, published_name, published_version = (
        observed_predecessor_independently(destination)
    )
    assert (published_name, published_version) == (PUBLISHED_NAME, PUBLISHED_VERSION)

    run = produce(
        tmp_path / "work",
        destination=destination,
        source=CandidateSource(isolated_checkout),
    )

    with capsys.disabled():
        sys.stdout.write(run.stdout)
        sys.stdout.write(run.stderr)

    assert broken_reason(run, repo_root=isolated_checkout) is None, (
        run.stdout,
        run.stderr,
    )

    from scripts.release.release_migration_decision import decode_decision

    record = _extracted_decision(run.output, tmp_path / "extracted")
    decision = decode_decision(record, isolated_checkout)

    assert decision.predecessor is not None
    assert decision.predecessor.distribution_name == PUBLISHED_NAME
    assert decision.predecessor.version == PUBLISHED_VERSION

    leases = [
        unit.body.get("predecessor")
        for unit in decision.units
        if unit.kind == "git_branch" and unit.body.get("branch") == TARGET_BRANCH
    ]
    assert leases == [published_commit]

    emitted = record.read_text(encoding="utf-8")
    for guess in (GUESS_NAME, GUESS_VERSION, GUESS_LEASE):
        assert guess not in emitted, f"hand-supplied {guess!r} reached the bundle"

    assert run.destination_after == run.destination_before


def _extracted_decision(bundle: Path, into: Path) -> Path:
    """Extract the emitted bundle and return its decision record."""
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(into)
    return into / "decision.json"


def _git(*argv: str) -> str:
    completed = subprocess.run(
        ["git", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _unreachable_gh(tmp_path: Path) -> dict[str, str]:
    """Put an unreachable `gh` first on PATH.

    This oracle names a local bare destination on every invocation, so nothing
    it drives has a legitimate route to the public target.  The stub makes that
    incapacity observable rather than merely intended: any attempt to reach
    GitHub fails loudly instead of using ambient credentials.  Real Git stays
    available, because the publisher's local clone and push are exactly what is
    being observed.
    """
    bin_dir = tmp_path / "no-network-bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\necho 'gh is unreachable in this oracle' >&2\nexit 97\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def _extract_tar(archive: Path, into: Path) -> Path:
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:") as tar:
        tar.extractall(into)
    return into


@pytest.mark.acceptance
@pytest.mark.slow
def test_the_bundle_carries_the_tree_and_patch_the_publisher_would_publish(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    isolated_checkout: Path,
) -> None:
    """The carried material is exactly what publishing this candidate produces.

    The operator's plan declares one generated publication unit, so one run of
    the real command must capture that unit's tree archive and change patch into
    the bundle and announce them on its own `REVIEW:` line, tied to the
    candidate sha.

    The expectation is derived INDEPENDENTLY, and after the fact: the REAL
    publisher is then run against the SAME throwaway destination with the
    bundle's own decision record, and what it actually publishes is compared to
    what the bundle promised -- the published tree object, the published tree
    CONTENT against the extracted `tree.tar` (never tar bytes: `git archive`
    stamps entry mtimes at archive time), and the published parent against the
    patch the bundle carries.
    """
    destination = seed_destination(tmp_path / "destination.git")
    head_before, _, _ = observed_predecessor_independently(destination)

    run = produce(
        tmp_path / "work",
        destination=destination,
        source=CandidateSource(isolated_checkout),
    )

    with capsys.disabled():
        sys.stdout.write(run.stdout)
        sys.stdout.write(run.stderr)

    assert broken_reason(run, repo_root=isolated_checkout) is None, (
        run.stdout,
        run.stderr,
    )

    from scripts.release.release_migration_decision import decode_decision

    record = _extracted_decision(run.output, tmp_path / "extracted")
    decision = decode_decision(record, isolated_checkout)
    generated = [unit for unit in decision.units if unit.kind == "generated_commit"]
    assert [unit.body["id"] for unit in generated] == [GENERATED_UNIT]
    promised_tree = generated[0].body["tree_oid"]
    assert generated[0].body["parent_oid"] == head_before

    published = subprocess.run(
        [
            sys.executable,
            str(isolated_checkout / "scripts/release/publish_experimental.py"),
            "--ref",
            run.source_sha,
            "--push",
            "--migration-decision",
            str(record),
            "--target-local-repo",
            str(destination),
            "--allow-branch",
        ],
        cwd=isolated_checkout,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=1800,
        env={**os.environ, **_unreachable_gh(tmp_path)},
        check=False,
    )
    with capsys.disabled():
        sys.stdout.write(published.stdout)
        sys.stdout.write(published.stderr)
    assert published.returncode == 0, published.stdout + published.stderr

    head_after = _git(
        "--git-dir", str(destination), "rev-parse", f"refs/heads/{TARGET_BRANCH}"
    )
    assert head_after != head_before
    assert (
        _git("--git-dir", str(destination), "rev-parse", f"{head_after}^")
        == head_before
    )
    assert (
        _git("--git-dir", str(destination), "rev-parse", f"{head_after}^{{tree}}")
        == promised_tree
    )

    published_tar = tmp_path / "published.tar"
    published_tar.write_bytes(
        subprocess.run(
            [
                "git",
                "--git-dir",
                str(destination),
                "archive",
                "--format=tar",
                head_after,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=300,
            check=True,
        ).stdout
    )
    promised = _extract_tar(record.parent / TREE_REVIEW, tmp_path / "promised")
    really = _extract_tar(published_tar, tmp_path / "published")
    identical = subprocess.run(
        ["diff", "-r", "-q", str(promised), str(really)],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=300,
        check=False,
    )
    assert identical.returncode == 0, identical.stdout + identical.stderr

    reproduction = tmp_path / "reproduction"
    _git("clone", "--quiet", "--no-checkout", str(destination), str(reproduction))
    _git("-C", str(reproduction), "checkout", "--quiet", "--detach", head_before)
    _git(
        "-C",
        str(reproduction),
        "apply",
        "--binary",
        "--index",
        str(record.parent / PATCH_REVIEW),
    )
    assert _git("-C", str(reproduction), "write-tree") == promised_tree
