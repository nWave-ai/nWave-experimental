"""Unit tests for `nwave_ai.sync` (DDD-4 implementation).

Covers the pure-function core (`compute_sync_plan`, `parse_worktree_porcelain`)
and the CLI shell smoke. Acceptance scenarios under
``tests/des/acceptance/lean_wave_documentation/`` carry the real-IO
end-to-end coverage; these tests focus on the planner so plan-shape bugs
surface without spinning up real git repositories.
"""

from __future__ import annotations

from pathlib import Path

from nwave_ai.sync import (
    WorktreeRecord,
    compute_sync_plan,
    parse_worktree_porcelain,
)


class TestParseWorktreePorcelain:
    """`parse_worktree_porcelain` filters to refs/heads/feature/<id>."""

    def test_extracts_feature_branches_only(self) -> None:
        porcelain = (
            "worktree /home/m/master\n"
            "HEAD abc123\n"
            "branch refs/heads/master\n"
            "\n"
            "worktree /home/m/wt-alpha\n"
            "HEAD def456\n"
            "branch refs/heads/feature/feat-alpha\n"
            "\n"
            "worktree /home/m/wt-beta\n"
            "HEAD ghi789\n"
            "branch refs/heads/feature/feat-beta\n"
        )
        records = parse_worktree_porcelain(porcelain)
        feature_ids = {r.feature_id for r in records}
        assert feature_ids == {"feat-alpha", "feat-beta"}

    def test_skips_detached_worktrees(self) -> None:
        porcelain = (
            "worktree /home/m/detached\nHEAD abc123\ndetached\n\n"
            "worktree /home/m/wt-alpha\n"
            "branch refs/heads/feature/feat-alpha\n"
        )
        records = parse_worktree_porcelain(porcelain)
        assert [r.feature_id for r in records] == ["feat-alpha"]

    def test_returns_empty_on_empty_input(self) -> None:
        assert parse_worktree_porcelain("") == []


class TestComputeSyncPlan:
    """`compute_sync_plan` is a pure function — no I/O, deterministic."""

    def _record(self, feature_id: str, path: str) -> WorktreeRecord:
        return WorktreeRecord(
            worktree_path=Path(path),
            branch=f"feature/{feature_id}",
            feature_id=feature_id,
        )

    def test_no_worktrees_no_existing_returns_empty_plan(self) -> None:
        plan = compute_sync_plan([], Path("/tmp/master"), set())
        assert plan == []

    def test_each_feature_worktree_produces_copy_op(self) -> None:
        master = Path("/tmp/master")
        records = [
            self._record("feat-alpha", "/tmp/wt-alpha"),
            self._record("feat-beta", "/tmp/wt-beta"),
        ]
        plan = compute_sync_plan(records, master, set())
        copy_ops = [op for op in plan if op.op_type == "copy"]
        assert len(copy_ops) == 2
        feature_ids = {op.feature_id for op in copy_ops}
        assert feature_ids == {"feat-alpha", "feat-beta"}

    def test_copy_op_targets_master_in_flight_directory(self) -> None:
        master = Path("/tmp/master")
        records = [self._record("feat-alpha", "/tmp/wt-alpha")]
        plan = compute_sync_plan(records, master, set())
        op = plan[0]
        assert op.target_path == master / ".nwave" / "in-flight" / "feat-alpha.md"
        assert op.source_path == (
            Path("/tmp/wt-alpha")
            / "docs"
            / "feature"
            / "feat-alpha"
            / "feature-delta.md"
        )

    def test_stale_mirror_entry_produces_remove_op(self) -> None:
        """Mirror entry whose feature has no live worktree -> remove."""
        master = Path("/tmp/master")
        plan = compute_sync_plan(
            feature_worktrees=[],
            master_path=master,
            existing_mirror_ids={"feat-merged"},
        )
        assert len(plan) == 1
        assert plan[0].op_type == "remove"
        assert plan[0].feature_id == "feat-merged"
        assert plan[0].target_path == (
            master / ".nwave" / "in-flight" / "feat-merged.md"
        )

    def test_master_worktree_record_excluded_from_copies(self) -> None:
        """When the master appears in `git worktree list`, it is filtered."""
        master = Path("/tmp/master").resolve()
        master_record = WorktreeRecord(
            worktree_path=master,
            branch="feature/master-itself",  # contrived
            feature_id="master-itself",
        )
        plan = compute_sync_plan([master_record], master, set())
        assert plan == []

    def test_copy_ops_emitted_in_deterministic_order(self) -> None:
        master = Path("/tmp/master")
        records = [
            self._record("feat-z", "/tmp/wt-z"),
            self._record("feat-a", "/tmp/wt-a"),
            self._record("feat-m", "/tmp/wt-m"),
        ]
        plan = compute_sync_plan(records, master, set())
        ids = [op.feature_id for op in plan]
        assert ids == ["feat-a", "feat-m", "feat-z"]


class TestCLIShellSmoke:
    """`run_sync` / `main` smoke tests — the planner-level coverage above is
    where the real assertions live, but we exercise the CLI shell on a real
    git repo to catch wiring breakage (e.g. wrong argument order in the
    subprocess call).
    """

    def test_sync_module_is_no_longer_a_red_scaffold(self) -> None:
        """The DDD-4 acceptance gate: scaffold marker disabled in GREEN."""
        from nwave_ai import sync as sync_module

        assert getattr(sync_module, "__SCAFFOLD__", True) is False, (
            "nwave_ai.sync still carries __SCAFFOLD__ = True; "
            "DDD-4 implementation is incomplete."
        )

    def test_run_sync_against_empty_git_repo(self, tmp_path: Path) -> None:
        """A repo with only the master worktree and no feature worktrees
        should be a no-op (no plan, no log, exit 0).
        """
        import subprocess

        from nwave_ai.sync import run_sync

        # Initialise a minimal git repo. The HOME-pollution guard requires
        # explicit identity per `git -c`.
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t.invalid",
                "-c",
                "user.name=t",
                "-c",
                "init.defaultBranch=master",
                "init",
                "--initial-branch=master",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("seed", encoding="utf-8")
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t.invalid",
                "-c",
                "user.name=t",
                "add",
                ".",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t.invalid",
                "-c",
                "user.name=t",
                "commit",
                "-m",
                "seed",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        rc = run_sync(tmp_path)
        assert rc == 0
        # No mirror dir should be created when no feature worktrees exist.
        assert not (tmp_path / ".nwave" / "in-flight").exists()
