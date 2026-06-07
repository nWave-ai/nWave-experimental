"""RED regression tests for the git-pollution detective guard fixture.

Background
----------
On 2026-04-27 a pre-push pytest run mutated host `.git/config`
(`core.bare=true`, `core.hooksPath=/dev/null`) and reset the worktree HEAD
to a synthetic test-fixture commit. RCA in
`docs/analysis/rca-test-git-pollution-2026-04-27.md` traced the leak to
subprocess git invocations from `cwd=tmp_path` without
`GIT_CEILING_DIRECTORIES`, combined with the autouse chdir back to
project_root.

Step 01-02 (separate dispatch) will install an autouse detective fixture in
`tests/conftest.py` that snapshots `.git/config`, the resolved HEAD path,
and `.git/refs/{heads,tags}` before each test, diffs the snapshot
afterwards, and calls `pytest.fail()` naming the corruption type ("config",
"HEAD", "refs/") if pollution is detected.

This file is the self-validation harness for that guard. It MUST fail today
because the guard's pure-function seams do not yet exist in
`tests.conftest`. The expected RED failure is `ImportError` on the imports
below.

Once Step 01-02 is implemented, these tests must turn GREEN by exercising
the guard's diff over the EXACT subprocess pollution path that caused the
incident: real `git config core.hooksPath /dev/null` and real `git commit`
against a real on-disk repo, with NO mocks.

Design notes
------------
- The pollution `subprocess.run` deliberately omits `GIT_CEILING_DIRECTORIES`
  from its env, faithfully reproducing the failure mode. Containment comes
  from the fact that `tmp_path` itself contains a freshly-initialized
  `.git`; git's walk-up resolves to that directly without crossing into the
  host repo. The bug-victim path is the same shape; what differs is the
  presence of a closer `.git` to absorb the write.
- The driving port for the guard is the pair of pure functions
  `_compute_git_state_snapshot` and `_diff_git_state`. Testing them
  port-to-port at domain scope IS the correct port-to-port unit-testing
  pattern for the detective guard's domain logic.
- We snapshot before mutation, perform the real subprocess pollution,
  snapshot after, and assert that the diff reports the expected target
  name. The assertion mirrors what the autouse fixture in 01-02 will do
  inline (diff -> pytest.fail).
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

# Import the pure-function seams the detective guard will expose.
# These do not exist yet — that is the RED gate. Step 01-02 introduces them
# in tests/conftest.py.
from tests.conftest import (
    _atomic_restore_git_state,
    _compute_git_state_snapshot,
    _diff_git_state,
    _read_packed_refs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_isolated_repo(repo_root: Path) -> None:
    """Initialize a fresh git repo inside `repo_root`.

    Sets `GIT_CEILING_DIRECTORIES` for THIS call so the setup itself cannot
    escape `repo_root`. The pollution subprocess call later in the test
    deliberately does NOT set this env var — that is the failure-mode
    reproduction.
    """
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    subprocess.run(
        ["git", "init", "-b", "main", str(repo_root)],
        check=True,
        capture_output=True,
        env=env,
    )
    # Minimum identity so commits can be created.
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test")):
        subprocess.run(
            ["git", "-C", str(repo_root), "config", key, value],
            check=True,
            capture_output=True,
            env=env,
        )


def _create_initial_commit(repo_root: Path) -> None:
    """Create one commit so HEAD points at a real ref."""
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    (repo_root / "seed.txt").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "seed.txt"],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "seed"],
        check=True,
        capture_output=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_guard_detects_config_corruption(tmp_path: Path) -> None:
    """Real `git config core.hooksPath /dev/null` mutates `.git/config`.

    Reproduces the EXACT subprocess pollution path observed at
    `tests/release/test_cz_integration.py:66` and witnessed in the master
    worktree's mutated config on 2026-04-27. The diff predicate must report
    `"config"` so the autouse fixture in 01-02 can name the corruption type
    in its `pytest.fail()` message.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Real failure-mode reproduction: NO GIT_CEILING_DIRECTORIES in env.
    # cwd=repo_root contains a fresh .git so the walk-up resolves there
    # immediately — same shape as the incident, contained target.
    subprocess.run(
        ["git", "config", "core.hooksPath", "/dev/null"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    after = _compute_git_state_snapshot(repo_root)

    diff = _diff_git_state(before, after)
    assert "config" in diff, (
        f"Detective guard predicate failed to detect config corruption; "
        f"diff returned {diff!r}. Expected 'config' so the autouse fixture "
        f"can call pytest.fail() naming the corruption type."
    )


def test_guard_detects_head_corruption(tmp_path: Path) -> None:
    """Real `git commit` advances HEAD; the guard must report `"HEAD"`.

    Reproduces the Branch A failure mode from the RCA: a test commit
    landed in the host worktree's HEAD because subprocess git escaped
    `tmp_path`. Here we contain the commit inside `tmp_path/victim_repo`
    so the test is safe, but the diff predicate must still flag HEAD
    movement as corruption.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Real failure-mode reproduction: subprocess `git commit` with NO
    # GIT_CEILING_DIRECTORIES. Containment is structural (tmp_path has its
    # own .git), faithfulness to the bug is preserved (no env guard).
    (repo_root / "polluting.txt").write_text("would have hit host\n")
    subprocess.run(
        ["git", "add", "polluting.txt"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: something"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )

    after = _compute_git_state_snapshot(repo_root)

    diff = _diff_git_state(before, after)
    assert "HEAD" in diff, (
        f"Detective guard predicate failed to detect HEAD corruption; "
        f"diff returned {diff!r}. Expected 'HEAD' so the autouse fixture "
        f"can name the corruption type when a test escapes its tmp_path "
        f"and lands a commit on the host worktree."
    )


# ---------------------------------------------------------------------------
# Tests added in fixup pass for adversarial review findings (D1, D2, D3).
# ---------------------------------------------------------------------------


def test_guard_detects_refs_corruption(tmp_path: Path) -> None:
    """Real `git tag` creates a new ref; the guard must report `"refs"`.

    Adversarial review D3(a): the refs snapshot branch of
    `_compute_git_state_snapshot` (the rglob over refs/heads + refs/tags)
    had no test coverage. Real `git tag` writes a new file under
    refs/tags/<name>, and the diff predicate must flag this as `"refs"`
    so the autouse fixture surfaces the corruption type.

    Together with the head- and config-corruption tests, this test now
    covers all three branches of the snapshot dict ("config", "HEAD",
    "refs").
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Real failure-mode reproduction: subprocess git creates a new ref.
    # `git tag` writes refs/tags/v0.1.0 directly; identical shape to the
    # pollution path that would create refs/heads/<spurious-branch> in
    # the host repo if a test escaped its tmp_path.
    subprocess.run(
        ["git", "-C", str(repo_root), "tag", "v0.1.0"],
        check=True,
        capture_output=True,
    )

    after = _compute_git_state_snapshot(repo_root)

    diff = _diff_git_state(before, after)
    assert "refs" in diff, (
        f"Detective guard predicate failed to detect refs corruption; "
        f"diff returned {diff!r}. Expected 'refs' so the autouse fixture "
        f"can name the corruption type when a test creates a stray ref "
        f"under refs/heads/ or refs/tags/."
    )


def test_guard_restore_deletes_created_refs(tmp_path: Path) -> None:
    """Restore must DELETE refs created during the test, not just write back snapshot entries.

    Adversarial review D2: the original `_atomic_restore_git_state` only
    wrote snapshot-before entries back to disk. Refs CREATED during the
    test (e.g., a stray `refs/heads/foo` or `refs/tags/v0.1.0`) survived
    restore — only their bytes-before-test would be missing, but the new
    file was untouched. This test exercises the full snapshot -> mutate
    -> restore -> snapshot loop and asserts the diff is empty after
    restore.

    Mirrors `_restore_hooks_dir`'s deletion-pass pattern (lines 96-99).
    Failing today proves the deletion pass is necessary; passing after
    the D2 fix proves the deletion pass is correct.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Pollute: create a tag that did not exist in `before`.
    subprocess.run(
        ["git", "-C", str(repo_root), "tag", "stray-tag"],
        check=True,
        capture_output=True,
    )

    # Sanity check: before the restore, the diff must be non-empty.
    polluted = _compute_git_state_snapshot(repo_root)
    assert _diff_git_state(before, polluted) == ["refs"], (
        "Setup failure: pollution did not produce the expected refs diff."
    )

    # Restore from `before` snapshot.
    _atomic_restore_git_state(repo_root, before)

    # The restore must have deleted refs/tags/stray-tag — not just
    # written back the absent entry. Snapshot equality is the contract.
    after_restore = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after_restore)
    assert diff == [], (
        f"Restore left ref pollution behind; diff after restore: {diff!r}. "
        f"Adversarial review D2: restore must mirror _restore_hooks_dir "
        f"and delete refs that were not present in the snapshot-before."
    )

    # Belt-and-braces: assert the stray tag file is actually gone on disk.
    stray_path = repo_root / ".git" / "refs" / "tags" / "stray-tag"
    assert not stray_path.exists(), (
        f"Restore wrote back snapshot entries but did NOT delete the "
        f"newly-created ref at {stray_path}."
    )


def test_guard_does_not_trigger_on_packed_promotion(tmp_path: Path) -> None:
    """Promotion of a packed ref into a loose file is NOT pollution.

    Residual-RCA (2026-04-28): the v3.13.0 guard flags ANY new file under
    refs/heads/ or refs/tags/ as ``"refs"`` corruption — even when the new
    loose ref's SHA already exists in ``packed-refs`` and the file was
    therefore created by routine git housekeeping (``git fetch``,
    ``git update-ref``, branch checkout after a ``git pack-refs --all``).

    Failure-mode reproduction (real subprocess git, no mocks):

    1. Initialise a repo and create one commit so ``refs/heads/main`` is a
       real loose ref.
    2. Run ``git pack-refs --all`` — this moves every ref into
       ``packed-refs`` and DELETES the loose files. After this the only
       on-disk record of ``refs/heads/main`` is its line in
       ``.git/packed-refs``; ``.git/refs/heads/main`` is absent.
    3. Take the BEFORE snapshot. ``refs`` is the empty list (no loose
       files), but the ref is fully resolvable from ``packed-refs``.
    4. Re-create ``.git/refs/heads/main`` with the EXACT SHA from
       ``packed-refs``. This is what ``git fetch`` does when it pulls a
       remote ref the local repo had previously packed: it writes the
       loose file back with the same SHA, never touching ``packed-refs``.
       It is housekeeping, not user-driven mutation.
    5. Take the AFTER snapshot. The ``refs`` list now contains
       ``("refs/heads/main", <sha>)``.
    6. Compute the diff. The contract this test locks is: the guard MUST
       report an empty diff. The promoted ref's SHA matches the
       packed-refs entry, so no semantic state has changed — only the
       on-disk representation.

    Today this test FAILS: the snapshot has no awareness of
    ``packed-refs``, so the diff returns ``["refs"]``. Step 01-02 will
    add ``_read_packed_refs`` and teach ``_diff_git_state`` to ignore new
    loose refs whose SHA already lives in the packed-refs map.

    The companion test ``test_guard_detects_refs_corruption`` (above)
    locks the OPPOSITE contract: a genuinely new ref (created by
    ``git tag``, SHA NOT present in ``packed-refs``) MUST still trigger
    the guard. Together they pin the behavioural envelope: promotion is
    silent, creation is loud.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    # Step 1: confirm the loose ref exists at refs/heads/main BEFORE pack.
    main_ref_path = repo_root / ".git" / "refs" / "heads" / "main"
    assert main_ref_path.is_file(), (
        "Setup failure: expected loose refs/heads/main after initial commit; "
        "the test relies on `git commit` writing the loose file before pack."
    )
    sha_before_pack = main_ref_path.read_text().strip()
    assert len(sha_before_pack) == 40, (
        f"Setup failure: expected 40-char SHA in refs/heads/main, got "
        f"{sha_before_pack!r}."
    )

    # Step 2: pack all refs. This deletes the loose files and writes
    # them into .git/packed-refs.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    subprocess.run(
        ["git", "-C", str(repo_root), "pack-refs", "--all"],
        check=True,
        capture_output=True,
        env=env,
    )

    # Sanity: loose file is gone, packed-refs contains the SHA.
    assert not main_ref_path.exists(), (
        "Setup failure: `git pack-refs --all` should have deleted the loose "
        "refs/heads/main file. Without this precondition the rest of the test "
        "cannot exercise the promotion-vs-creation distinction."
    )
    packed_refs_path = repo_root / ".git" / "packed-refs"
    assert packed_refs_path.is_file(), (
        "Setup failure: `git pack-refs --all` should have written a "
        ".git/packed-refs file."
    )
    packed_text = packed_refs_path.read_text()
    assert sha_before_pack in packed_text, (
        f"Setup failure: expected SHA {sha_before_pack!r} in packed-refs; "
        f"contents were:\n{packed_text!r}"
    )

    # Step 3: snapshot AFTER the pack — `refs` list is empty, only
    # packed-refs holds the data.
    before = _compute_git_state_snapshot(repo_root)

    # Step 4: simulate `git fetch` / housekeeping promotion. Re-create
    # the loose file with the SAME SHA as in packed-refs. We use direct
    # filesystem write rather than `git update-ref` to make the test
    # independent of git internals; the on-disk shape is what the guard
    # observes either way.
    main_ref_path.parent.mkdir(parents=True, exist_ok=True)
    main_ref_path.write_text(sha_before_pack + "\n")

    # Step 5: snapshot after the promotion.
    after = _compute_git_state_snapshot(repo_root)

    # Step 6: the contract under test. Promotion is housekeeping, not
    # pollution. The diff must be empty.
    diff = _diff_git_state(before, after)
    assert diff == [], (
        f"Detective guard reported false-positive on packed-to-loose "
        f"promotion; diff returned {diff!r}. The promoted ref "
        f"refs/heads/main has SHA {sha_before_pack!r}, which is already "
        f"present in .git/packed-refs — no semantic state has changed. "
        f"This false-positive is the residual bug fixed in Step 01-02 by "
        f"teaching the guard to read packed-refs and ignore loose refs "
        f"whose SHA matches a packed entry."
    )


def test_guard_restore_preserves_symbolic_head(tmp_path: Path) -> None:
    """Restore must preserve the symbolic-ref form of HEAD, not write a raw SHA.

    Adversarial review D1: the original snapshot stored the RESOLVED
    target of HEAD (the commit SHA from refs/heads/<branch>) in the
    `"HEAD"` key, and the restore wrote those bytes back to the HEAD
    file. This left the worktree in detached-HEAD state because HEAD
    originally contained `ref: refs/heads/<branch>\\n`, not the SHA.

    The fix splits HEAD into `HEAD_raw` (the literal HEAD file bytes,
    used for restore) and `HEAD_resolved` (the resolved SHA, used for
    diff). This test asserts the restore writes the symbolic-ref TEXT
    back, so the worktree remains attached to its branch.

    Failing today: the restore writes the SHA. Passing after D1 fix:
    the restore writes `ref: refs/heads/main\\n`.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    head_path = repo_root / ".git" / "HEAD"
    original_head_text = head_path.read_text()
    # Sanity: confirm we start from a symbolic-ref HEAD on `main`.
    assert original_head_text.startswith("ref: refs/heads/main"), (
        f"Setup failure: expected symbolic-ref HEAD, got {original_head_text!r}."
    )

    before = _compute_git_state_snapshot(repo_root)

    # Pollute HEAD: simulate a test that detached HEAD by writing a raw
    # SHA. Equivalent in shape to `git checkout <sha>`.
    seed_sha = (repo_root / ".git" / "refs" / "heads" / "main").read_text().strip()
    head_path.write_text(seed_sha + "\n")

    # Restore from snapshot.
    _atomic_restore_git_state(repo_root, before)

    # The restored HEAD must contain the symbolic-ref TEXT, not the SHA.
    restored_head_text = head_path.read_text()
    assert restored_head_text == original_head_text, (
        f"Restore corrupted HEAD: expected symbolic-ref text "
        f"{original_head_text!r}, got {restored_head_text!r}. "
        f"Adversarial review D1: restore must write HEAD_raw (the literal "
        f"file bytes), not HEAD_resolved (the SHA target)."
    )
    # Belt-and-braces: explicitly check we did NOT leave HEAD detached.
    assert restored_head_text.startswith("ref:"), (
        f"Restore left HEAD detached; HEAD now reads {restored_head_text!r}. "
        f"Worktree should remain attached to refs/heads/main."
    )


# ---------------------------------------------------------------------------
# Step 01-02 unit tests: _read_packed_refs and genuine-creation regression.
# ---------------------------------------------------------------------------


def test_read_packed_refs_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    """No ``packed-refs`` file -> empty dict, never raises.

    Many freshly-initialised repos have no packed-refs file at all; the
    helper must treat absence as "no packed entries", not as an error.
    """
    common_dir = tmp_path / ".git"
    common_dir.mkdir()
    assert _read_packed_refs(common_dir) == {}


def test_read_packed_refs_returns_empty_dict_when_file_empty(tmp_path: Path) -> None:
    """Empty ``packed-refs`` file -> empty dict.

    git can produce a header-only or genuinely-empty packed-refs after
    ``git pack-refs --all`` on a repo with no refs to pack.
    """
    common_dir = tmp_path / ".git"
    common_dir.mkdir()
    (common_dir / "packed-refs").write_text("")
    assert _read_packed_refs(common_dir) == {}


def test_read_packed_refs_parses_real_pack_refs_output(tmp_path: Path) -> None:
    """Real ``git pack-refs --all`` output parses into name -> sha map.

    Skips comment lines and peeled-tag annotation lines (``^<sha>``).
    Pinned via real subprocess git so the parser is verified against the
    actual on-disk format git emits, not a hand-rolled imitation.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    # Create an annotated tag so packed-refs gets a peeled (`^...`) line.
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    subprocess.run(
        ["git", "-C", str(repo_root), "tag", "-a", "v0.0.1", "-m", "annotated"],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "pack-refs", "--all"],
        check=True,
        capture_output=True,
        env=env,
    )

    common_dir = repo_root / ".git"
    packed = _read_packed_refs(common_dir)

    # Both refs must be present, peeled line must NOT show up as its own
    # entry (it has no ref-name, just `^<sha>`).
    assert "refs/heads/main" in packed, (
        f"Expected refs/heads/main in packed-refs map; got {packed!r}"
    )
    assert "refs/tags/v0.0.1" in packed, (
        f"Expected refs/tags/v0.0.1 in packed-refs map; got {packed!r}"
    )
    # Each value must be a 40-char SHA hex string.
    for name, sha in packed.items():
        assert len(sha) == 40, f"Expected 40-char SHA for {name!r}, got {sha!r}"
        assert all(c in "0123456789abcdef" for c in sha), (
            f"Expected hex SHA for {name!r}, got {sha!r}"
        )
    # No spurious "^<sha>" key from the peeled line.
    assert not any(k.startswith("^") for k in packed), (
        f"Peeled-tag annotation line leaked into map: {packed!r}"
    )


def test_guard_detects_genuine_ref_creation_not_promotion(tmp_path: Path) -> None:
    """Brand-new ref (SHA NOT in packed-refs) MUST still flag as ``"refs"``.

    Companion to ``test_guard_does_not_trigger_on_packed_promotion``: pins
    the OTHER edge of the behavioural envelope. After the 01-02 fix
    teaches the snapshot to ignore promotions, we MUST still surface
    genuine creation — otherwise pollution that creates a new ref slips
    through.

    Setup: one commit, then snapshot. Then ``git tag v9.9.9`` which
    creates a ref whose SHA was never in packed-refs. The diff must
    contain ``"refs"``.
    """
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)

    before = _compute_git_state_snapshot(repo_root)

    # Genuine creation: the SHA points at HEAD (which IS in main's history)
    # but the REF NAME refs/tags/v9.9.9 is brand new — never existed in
    # packed-refs. The promotion-detection logic must not silence this.
    subprocess.run(
        ["git", "-C", str(repo_root), "tag", "v9.9.9"],
        check=True,
        capture_output=True,
    )

    after = _compute_git_state_snapshot(repo_root)
    diff = _diff_git_state(before, after)
    assert "refs" in diff, (
        f"Genuine ref creation must still flag as 'refs'; diff={diff!r}. "
        f"Promotion detection must not silence creation of brand-new ref names."
    )
