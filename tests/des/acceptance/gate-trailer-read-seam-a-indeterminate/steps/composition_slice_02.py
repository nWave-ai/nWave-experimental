"""Composition root for the CommitTrailerReadPort port-contract hardening (slice-02).

This is the *only* place the production adapter is wired for the slice-02 ATs.
It drives the production ``GitCommitTrailerReadAdapter.commit_messages`` at the
**adapter boundary** -- the port-contract variant sanctioned by the DESIGN
Driving Surface table ("ATs drive the adapter directly or via a thin harness;
no CLI surface change").

WHY NOT THE CLI (Mandate-13 driving-port-only, port-contract exception):
``commit_messages`` is a port-contract method on a DRIVEN port. It has no
dedicated CLI surface: the done-gate calls it internally; there is no
``des`` subcommand that exposes it alone. The honest driving surface is the
port boundary itself. This mirrors the predecessor slice-02 (the git-free
gate-core injection seam) and the DESIGN table's explicit sanctioning of
"thin harness" for slice-02. ``GitCommitTrailerReadAdapter`` implements the
``CommitTrailerReadPort`` ABC; driving it via the port interface IS driving
through the composition-root driving surface the architecture designed for.

ADAPTER UNDER TEST: ``GitCommitTrailerReadAdapter.commit_messages(repo: Path)``
  * D1 many-cardinality: a REAL git work-tree with 3 commits (each carrying a
    distinct body) -- the adapter must return a CommitMessages whose messages
    tuple contains all 3 bodies. Proves the many-cardinality path never truncates.
  * D2 non-existent path: a Path that does not exist on the filesystem -- the OS
    raises FileNotFoundError before any git process starts (cwd is resolved by
    subprocess.run before exec). The adapter's except FileNotFoundError branch
    translates this to Indeterminate(reason). NOT an empty CommitMessages(()).
  * D3 exists-but-not-work-tree: a real directory with no .git -- git log returns
    non-zero (``fatal: not a git repository``). git_text's check=True raises
    CalledProcessError. The adapter's except CalledProcessError branch returns
    Indeterminate(reason). Proves the two C6a sub-partitions are both LOUD.

PURE-READ CONTRACT (Mandate 8, Layer-3 universe guard): commit_messages is a
pure read -- it MUST NOT modify the repo directory. ``capture_universe`` snapshots
the port-exposed filesystem observables; the When-step asserts every entry is
``unchanged`` across the invocation.

GREEN-on-author (all three partitions):
  D1: adapter iterates all git log output, split on \x1e gives N+1 elements for
      N commits. All 3 known bodies appear in the tuple -> assertion passes.
  D2: subprocess.run(cwd=non_existent) -> FileNotFoundError -> Indeterminate -> PASS.
  D3: git log on plain dir -> CalledProcessError -> Indeterminate -> PASS.
These are COVERAGE-PIN ATs: the behavior is already correct; the ATs prevent
silent regression on future refactors of the exception-translation path.

State lives on the instance; every ``given_/when_/then_`` method mutates or
reads that state. Step functions in ``test_slice_02_*.py`` are thin delegations
to these methods (Mandate-12 criterion 3: no business logic in step bodies).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.git.git_commit_trailer_read_adapter import (
    GitCommitTrailerReadAdapter,
)
from des.ports.driven_ports.commit_trailer_read_port import (
    CommitMessages,
    Indeterminate,
)


# Known commit message bodies planted in the multi-commit substrate.
# Each is a distinct domain-language string so the assertion is concrete.
COMMIT_BODY_A = "first: add tracking marker for many-cardinality test\n"
COMMIT_BODY_B = "second: extend tracking with intermediate step\n"
COMMIT_BODY_C = "third: finalize tracking sequence for slice-02 scan\n"

KNOWN_BODIES: tuple[str, str, str] = (COMMIT_BODY_A, COMMIT_BODY_B, COMMIT_BODY_C)


@dataclass
class CommitMessagesComposition:
    """Drives GitCommitTrailerReadAdapter.commit_messages for slice-02 ATs.

    Wires the production adapter (real git I/O for D1, real filesystem for
    D2/D3). Universe guard (Mandate 8) runs in the When-step to confirm the
    read is pure -- no modification to the repo directory.
    """

    _tmp: Path | None = field(default=None)
    _repo_path: Path | None = field(default=None)
    _adapter: GitCommitTrailerReadAdapter = field(
        default_factory=GitCommitTrailerReadAdapter
    )
    _result: CommitMessages | Indeterminate | None = field(default=None)

    # ---- given -----------------------------------------------------------------

    def given_real_worktree_with_three_commits(self) -> None:
        """Real git work-tree with three distinct commits, each with a known body."""
        self._tmp = Path(tempfile.mkdtemp(prefix="commit-msgs-d1-"))
        self._repo_path = self._tmp
        self._init_repo_three_commits(self._repo_path)

    def given_absent_path(self) -> None:
        """A Path that does not exist on the filesystem (D2 non-existent-path)."""
        tmp = Path(tempfile.mkdtemp(prefix="commit-msgs-d2-"))
        self._tmp = tmp
        # The target path is a child of the tmp dir that is never created.
        self._repo_path = tmp / "does-not-exist"
        assert not self._repo_path.exists(), (
            "the absent-path substrate must not exist -- construction error"
        )

    def given_existing_non_worktree_dir(self) -> None:
        """A directory that exists on the filesystem but has no .git (D3 not-a-work-tree)."""
        self._tmp = Path(tempfile.mkdtemp(prefix="commit-msgs-d3-"))
        self._repo_path = self._tmp
        assert self._repo_path.exists(), (
            "the not-a-work-tree substrate must exist -- construction error"
        )
        assert not (self._repo_path / ".git").exists(), (
            "the not-a-work-tree substrate must not contain .git -- construction error"
        )

    # ---- when ------------------------------------------------------------------

    def when_port_reads_commit_messages(self) -> None:
        """Invoke the adapter and guard pure-read via universe snapshot (Mandate 8).

        The universe guard snapshots the repo path BEFORE and AFTER the read.
        commit_messages is a pure observer -- the directory must be unchanged.
        """
        repo = self._require_repo_path()
        before = self.capture_universe(repo)
        self._result = self._adapter.commit_messages(repo)
        after = self.capture_universe(repo)
        self._assert_pure_read(before, after, repo)

    # ---- then ------------------------------------------------------------------

    def then_stream_contains_all_known_bodies(self) -> None:
        """All three known commit bodies appear somewhere in the returned tuple.

        The commit_messages adapter uses git log which lists commits newest-first.
        For N commits the \x1e-split yields N+1 elements (trailing empty). The
        assertion is membership (each known body present), not strict index equality,
        so it is robust to git log ordering and the trailing-empty artifact.
        """
        result = self._require_result()
        assert isinstance(result, CommitMessages), (
            "commit_messages on a real git work-tree with commits must return "
            f"CommitMessages, not {type(result).__name__!r}. "
            f"result={result!r}"
        )
        messages = result.messages
        for body in KNOWN_BODIES:
            assert any(body in msg for msg in messages), (
                f"the returned CommitMessages must contain the planted commit body "
                f"{body!r}. Found messages: {messages!r}"
            )

    def then_stream_not_truncated(self) -> None:
        """The tuple length covers all committed bodies (non-vacuity).

        For 3 commits the \x1e-split yields >= 3 elements. A buggy adapter that
        returned only the first commit body would have len(messages) == 1 (or 2
        with the trailing empty), failing this gate.
        """
        result = self._require_result()
        assert isinstance(result, CommitMessages), (
            "commit_messages must return CommitMessages for this assertion to hold"
        )
        # >= 3 because the actual split includes a trailing empty element after the
        # last \x1e separator. The invariant is "all N bodies reachable", not len==N.
        assert len(result.messages) >= len(KNOWN_BODIES), (
            f"the returned tuple must contain at least {len(KNOWN_BODIES)} elements "
            f"(one per committed body, plus potentially a trailing empty). "
            f"Got len={len(result.messages)}: {result.messages!r}"
        )

    def then_result_is_indeterminate(self) -> None:
        """The port returns Indeterminate (not an empty CommitMessages or an exception).

        LOUD degrade: git failure MUST surface as Indeterminate, never as an empty
        CommitMessages(()) that the done-gate would silently read as "nothing shipped".
        """
        result = self._require_result()
        assert isinstance(result, Indeterminate), (
            "commit_messages on a cannot-read path must return Indeterminate "
            "(degrade-LOUD per AD-24 / port contract). "
            f"Got {type(result).__name__!r}: {result!r}. "
            "An empty CommitMessages(()) is FORBIDDEN -- it would masquerade as a "
            "successful read with no history."
        )

    def then_indeterminate_has_reason(self) -> None:
        """The Indeterminate reason is a non-empty string describing why git failed."""
        result = self._require_result()
        assert isinstance(result, Indeterminate), (
            "this assertion requires Indeterminate -- call then_result_is_indeterminate first"
        )
        assert result.reason.strip() != "", (
            "the Indeterminate reason must be non-empty -- the adapter must name "
            f"the specific failure cause. Got reason={result.reason!r}"
        )

    def then_result_is_not_none(self) -> None:
        """Confirm the When-step completed; pure-read guard already ran there."""
        self._require_result()

    def then_indeterminate_shape_matches_absent_path(self) -> None:
        """The Indeterminate from a non-work-tree is structurally identical to absent-path.

        Both partitions (non-existent path and exists-but-not-a-work-tree) must
        return the same Indeterminate type with a non-empty reason. This confirms
        neither partition leaks as an empty CommitMessages or a raw exception.
        """
        result = self._require_result()
        assert isinstance(result, Indeterminate), (
            "the exists-but-not-a-work-tree partition must return Indeterminate "
            f"(not {type(result).__name__!r}: {result!r}). "
            "The two C6a sub-partitions must both degrade LOUD."
        )
        assert result.reason.strip() != "", (
            f"Indeterminate.reason must be non-empty. Got {result.reason!r}"
        )

    # ---- universe (Mandate 8 pure-read guard) ----------------------------------

    def capture_universe(self, path: Path) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate 8).

        Universe entries are filesystem observables that commit_messages might
        tempt to touch -- never internal struct fields.

        For D2 (absent path) the path does not exist; file_count=0 and
        dir_exists=False are the stable anchors that confirm no directory was
        created during the read.
        """
        if not path.exists():
            return {
                "repo.dir_exists": False,
                "repo.file_count": 0,
                "repo.git_present": False,
            }
        return {
            "repo.dir_exists": path.exists(),
            "repo.file_count": sum(1 for _ in path.rglob("*") if _.is_file()),
            "repo.git_present": (path / ".git").exists(),
        }

    def _assert_pure_read(
        self,
        before: dict[str, object],
        after: dict[str, object],
        path: Path,
    ) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert_state_delta(
            before=before,
            after=after,
            universe={
                "repo.dir_exists",
                "repo.file_count",
                "repo.git_present",
            },
            expected={
                "repo.dir_exists": unchanged(),
                "repo.file_count": unchanged(),
                "repo.git_present": unchanged(),
            },
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) -----------------

    def _init_repo_three_commits(self, path: Path) -> None:
        """git init + three commits each with a distinct known message body."""
        run = lambda *a: subprocess.run(  # noqa: E731
            list(a), cwd=path, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q")
        run("git", "config", "user.email", "slice02@example.com")
        run("git", "config", "user.name", "slice02-at")

        for i, body in enumerate(KNOWN_BODIES, start=1):
            (path / f"file_{i}.txt").write_text(f"content {i}\n", encoding="utf-8")
            run("git", "add", f"file_{i}.txt")
            run("git", "commit", "-q", "-m", body.rstrip("\n"))

    def _require_repo_path(self) -> Path:
        assert self._repo_path is not None, (
            "the repo path must be set by the Given step before running the port (When)"
        )
        return self._repo_path

    def _require_result(self) -> CommitMessages | Indeterminate:
        assert self._result is not None, (
            "commit_messages must be called (When) before asserting on its result (Then)"
        )
        return self._result

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
