"""`run_acceptance.examine` measures a disposable snapshot of the delivery,
never the delivery itself -- so it can never write the hidden suite or the
acceptance venv into the original, and two concurrent calls over the same
workspace cannot race on a shared target/venv. The base version wrote both
directly into `workspace`: two concurrent calls raced on the same paths and
produced contradictory results, which is exactly what a measurement
instrument that changes its subject must not do.

Run: uv run pytest -q tests/scripts/analysis/test_run_acceptance_isolation.py
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from scripts.analysis.k4 import prepare_examiner_fixture as pef
from scripts.analysis.k4 import run_acceptance as ra


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _workspace(tmp_path):
    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    (workspace / "requirements.txt").write_text("# no real deps\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")
    # Row 2, K4 matrix: `examine` now refuses to score anything until the
    # row-2 self-probe (GDP-8 witness corollary) has proven the oracle goes
    # RED on this workspace's own base commit -- resolved via REAL git,
    # never the mockable `_run` seam (see `_base_commit_sha`). Every
    # workspace under test needs a real commit to serve as that base; a
    # test that commits more content of its own afterwards just adds a
    # second commit on top, which does not change what the root resolves to.
    _git("init", "-q", "-b", "master", cwd=workspace)
    _git("config", "user.email", "k4@example.test", cwd=workspace)
    _git("config", "user.name", "k4", cwd=workspace)
    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "seed", cwd=workspace)
    return workspace, suite


#: Every fake `_run` below must intercept the row-2 self-probe's suite run
#: BEFORE its own generic `ra._SUITE_LABEL in argv` branch: the self-probe
#: uses the identical label, distinguished only by running in its own
#: extracted-base snapshot, tagged `_SELF_PROBE_DIR_MARKER` in its cwd.
#: Answering RED there is not a stub convenience -- it is what an
#: undelivered subject actually does, so every existing assertion below
#: keeps measuring exactly what it always measured.
def _self_probe_branch(argv, cwd):
    if ra._SELF_PROBE_DIR_MARKER in str(cwd) and ra._SUITE_LABEL in argv:
        return 1, "FAIL: self-probe -- undelivered base, as expected"
    return None


def _digest(root: Path) -> dict[str, bytes]:
    """Content + relative name for every file under `root`, excluding only
    the setup-owned user-environment doc `examine` is allowed to remove."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != pef.DOC_NAME
    }


def _passing_run(seen: dict | None = None):
    def fake(argv, cwd, timeout=2400):
        if (probed := _self_probe_branch(argv, cwd)) is not None:
            return probed
        if "venv" in argv or "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
            if seen is not None:
                seen["manage.py"] = (Path(cwd) / "manage.py").read_text()
                seen["untracked"] = (
                    Path(cwd) / "hc" / "api" / "tests" / "untracked_delivery.py"
                ).read_text()
            return 0, "OK"
        raise AssertionError(f"unexpected argv: {argv}")

    return fake


def test_examine_measures_the_delivered_tree_and_leaves_the_original_untouched(
    tmp_path, monkeypatch
):
    """Falsifiers 1 & 4: the copy sees an untracked file and a post-commit
    modification to a tracked file (proving it measures the delivered tree,
    not HEAD), yet the original digest is byte-identical afterwards and
    neither the hidden-suite target nor the acceptance venv exist in it."""
    workspace, suite = _workspace(tmp_path)  # already a git repo with one commit

    (workspace / "manage.py").write_text("# modified after commit\n")
    untracked = workspace / "hc" / "api" / "tests" / "untracked_delivery.py"
    untracked.write_text("# untracked delivery file\n")

    before = _digest(workspace)
    seen: dict = {}
    monkeypatch.setattr(ra, "_run", _passing_run(seen))

    accepted, _ = ra.examine(workspace, suite)

    assert accepted is True
    assert seen["manage.py"] == "# modified after commit\n"
    assert seen["untracked"] == "# untracked delivery file\n"
    assert _digest(workspace) == before
    assert not (workspace / ra._SUITE_TARGET).exists()
    assert not (workspace / ra._ACCEPTANCE_VENV_NAME).exists()


def test_concurrent_examine_calls_do_not_race_and_leave_the_original_unchanged(
    tmp_path, monkeypatch
):
    """Falsifier 2: two concurrent `examine` calls over the same workspace,
    driven by a thread-safe fake `_run`, must both accept, must leave the
    original unchanged, and -- the deterministic part -- must each have run
    the hidden and subject suites in their OWN snapshot directory. Recording
    the cwd of every hidden/subject invocation under the lock and asserting
    exactly two distinct values, neither the original workspace, is what
    makes this a falsifier: on the base version, which runs both suites
    directly in `workspace`, every invocation shares the same cwd and this
    assertion fails even though `results` and the digest both look fine."""
    workspace, suite = _workspace(tmp_path)
    before = _digest(workspace)
    lock = threading.Lock()
    call_count = {"n": 0}
    suite_cwds: list[str] = []

    def fake(argv, cwd, timeout=2400):
        if (probed := _self_probe_branch(argv, cwd)) is not None:
            with lock:
                call_count["n"] += 1
            return probed
        with lock:
            call_count["n"] += 1
            if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
                suite_cwds.append(str(cwd))
        if "venv" in argv or "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
            return 0, "OK"
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(ra, "_run", fake)

    results: list[tuple[bool, str] | None] = [None, None]

    def worker(index: int) -> None:
        results[index] = ra.examine(workspace, suite)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results[0] is not None and results[1] is not None
    assert results[0][0] is True
    assert results[1][0] is True
    assert call_count["n"] > 0
    assert _digest(workspace) == before
    assert not (workspace / ra._SUITE_TARGET).exists()
    assert not (workspace / ra._ACCEPTANCE_VENV_NAME).exists()

    distinct_cwds = set(suite_cwds)
    assert len(distinct_cwds) == 2, (
        f"expected exactly two distinct snapshot cwds, got {suite_cwds}"
    )
    assert str(workspace) not in distinct_cwds


@pytest.mark.parametrize(
    "bulky_name",
    [
        ".git",
        ".claude",
        ra._ACCEPTANCE_VENV_NAME,
        "k4-fixture-venv",
        "__pycache__",
        ".pytest_cache",
        ".hypothesis",
    ],
)
def test_snapshot_excludes_measurement_bulk_from_the_copy(
    tmp_path, monkeypatch, bulky_name
):
    """A prior acceptance venv, VCS metadata, a Claude runtime dir, an
    interpreter cache, or a Hypothesis cache sitting in the delivery must
    not ride into the snapshot the run actually executes against -- only
    production content does."""
    workspace, suite = _workspace(tmp_path)
    bulky = workspace / bulky_name
    # `.git` already exists -- `_workspace()` makes every workspace a real
    # git repo now, for the row-2 self-probe's own base-commit resolution.
    bulky.mkdir(exist_ok=True)
    (bulky / "marker").write_text("bulk, not production content\n")

    seen: dict = {}

    def fake(argv, cwd, timeout=2400):
        if (probed := _self_probe_branch(argv, cwd)) is not None:
            return probed
        if "venv" in argv or "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
            seen["present"] = (Path(cwd) / bulky_name).exists()
            return 0, "OK"
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(ra, "_run", fake)

    accepted, _ = ra.examine(workspace, suite)

    assert accepted is True
    assert seen["present"] is False
    assert bulky.exists()


def test_examine_preserves_delivery_symlinks_semantically(tmp_path, monkeypatch):
    """Falsifier 3: a delivery symlink to an existing delivery file remains a
    symlink in the snapshot with the same target, readable content, and both
    the source link and target are unchanged after examine."""
    workspace, suite = _workspace(tmp_path)
    _git("init", "-q", "-b", "master", cwd=workspace)
    _git("config", "user.email", "k4@example.test", cwd=workspace)
    _git("config", "user.name", "k4", cwd=workspace)

    target_file = workspace / "hc" / "api" / "tests" / "target_delivery.py"
    target_file.write_text("# delivery target file\n")
    symlink_file = workspace / "hc" / "api" / "tests" / "link_to_delivery.py"
    symlink_file.symlink_to("target_delivery.py")

    _git("add", "-A", cwd=workspace)
    _git("commit", "-q", "-m", "seed", cwd=workspace)

    before_link_target = symlink_file.readlink()
    before_link_content = symlink_file.read_text()
    before_target_content = target_file.read_text()

    seen: dict = {}

    def fake(argv, cwd, timeout=2400):
        if (probed := _self_probe_branch(argv, cwd)) is not None:
            return probed
        if "venv" in argv or "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
            snapshot_symlink = (
                Path(cwd) / "hc" / "api" / "tests" / "link_to_delivery.py"
            )
            snapshot_target = Path(cwd) / "hc" / "api" / "tests" / "target_delivery.py"
            seen["symlink_is_link"] = snapshot_symlink.is_symlink()
            seen["link_target"] = snapshot_symlink.readlink()
            seen["link_content"] = snapshot_symlink.read_text()
            seen["target_content"] = snapshot_target.read_text()
            return 0, "OK"
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(ra, "_run", fake)

    accepted, _ = ra.examine(workspace, suite)

    assert accepted is True
    assert seen["symlink_is_link"] is True
    assert seen["link_target"] == before_link_target
    assert seen["link_content"] == before_link_content
    assert seen["target_content"] == before_target_content
    assert symlink_file.readlink() == before_link_target
    assert symlink_file.read_text() == before_link_content
    assert target_file.read_text() == before_target_content


@pytest.mark.parametrize(
    "case",
    [
        pytest.param("no-manifest", id="manifest-absent-no-delta"),
        pytest.param("addition-only", id="base-native-dep-plus-addition"),
        pytest.param("delta-fails", id="delta-install-fails"),
    ],
)
def test_examine_dev_requirements_delta_install_order_and_failure_handling(
    tmp_path, monkeypatch, case
):
    """Install order is requirements.txt -> derived test-dependency delta ->
    time-machine -> suites, and only the delta -- never the whole
    requirements-dev.txt -- is ever installed.

    Falsifies: (1) an absent manifest yields no delta and no extra install
    call; (2) a delivery that adds `hypothesis==6.140.4` on top of a
    pre-existing, possibly-unbuildable `mysqlclient` pin installs ONLY the
    addition, in a file whose contents are exactly that one line, between
    requirements.txt and time-machine; (3) a failing delta install
    short-circuits before time-machine and both suites, with evidence naming
    the addition and never the pre-existing dependency."""
    workspace, suite = _workspace(tmp_path)

    if case != "no-manifest":
        _git("init", "-q", "-b", "master", cwd=workspace)
        _git("config", "user.email", "k4@example.test", cwd=workspace)
        _git("config", "user.name", "k4", cwd=workspace)
        (workspace / "requirements-dev.txt").write_text("mysqlclient\n")
        _git("add", "-A", cwd=workspace)
        _git("commit", "-q", "-m", "seed", cwd=workspace)
        (workspace / "requirements-dev.txt").write_text(
            "mysqlclient\nhypothesis==6.140.4\n"
        )

    calls = []
    seen: dict = {}

    def fake(argv, cwd, timeout=2400):
        if ra._SELF_PROBE_DIR_MARKER in str(cwd):
            # Row-2 self-probe traffic, satisfied transparently and never
            # recorded: the install-order assertions below are about the
            # MAIN scored run, and the self-probe never has a dev delta to
            # install, so mixing it into `calls` would misorder them.
            if ra._SUITE_LABEL in argv:
                return 1, "FAIL: self-probe -- undelivered base, as expected"
            return 0, ""
        joined = " ".join(argv)
        calls.append(joined)
        if "venv" in argv:
            return 0, ""
        if ra._DEV_DELTA_REQUIREMENTS_NAME in joined:
            seen["delta_contents"] = Path(argv[-1]).read_text()
            if case == "delta-fails":
                return 1, "ERROR: Could not find a version satisfying the requirement"
            return 0, ""
        if "requirements.txt" in joined:
            return 0, ""
        if "time-machine" in joined:
            return 0, ""
        if ra._SUITE_LABEL in argv or "--exclude-tag" in argv:
            return 0, "OK"
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(ra, "_run", fake)

    accepted, evidence = ra.examine(workspace, suite)

    install_calls = [c for c in calls if "install" in c]
    req_txt_idx = next(
        i
        for i, c in enumerate(install_calls)
        if c.rstrip().endswith("requirements.txt")
    )
    delta_indices = [
        i for i, c in enumerate(install_calls) if ra._DEV_DELTA_REQUIREMENTS_NAME in c
    ]
    time_machine_indices = [
        i for i, c in enumerate(install_calls) if "time-machine" in c
    ]

    if case == "no-manifest":
        assert accepted is True
        assert len(delta_indices) == 0
        assert req_txt_idx < time_machine_indices[0]
    elif case == "addition-only":
        assert accepted is True
        assert len(delta_indices) == 1
        assert seen["delta_contents"] == "hypothesis==6.140.4\n"
        assert req_txt_idx < delta_indices[0] < time_machine_indices[0]
    else:
        assert accepted is False
        assert len(delta_indices) == 1
        assert seen["delta_contents"] == "hypothesis==6.140.4\n"
        assert "hypothesis==6.140.4" in evidence
        assert "mysqlclient" not in evidence
        assert len(time_machine_indices) == 0
        assert not any(ra._SUITE_LABEL in c for c in calls)
        assert not any("--exclude-tag" in c for c in calls)
