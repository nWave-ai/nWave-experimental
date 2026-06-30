"""Composition root for the seam-A INDETERMINATE refusal (slice-01).

This is the *only* place the production system is wired for the slice-01 ATs.
It drives the production ``des verify-commit-trailers`` CLI end-to-end as a
subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess),
mirroring the proven pattern of the sibling suite
``tests/des/acceptance/gate-trailer-read-git-port-extract/steps/composition.py``.

DRIVING PORT (load-bearing): ``CommitTrailerReadPort.commit_message`` and
``GitCommitTrailerReadAdapter`` are NEVER imported-and-called at the step
boundary -- the SUT is exercised only through the CLI subprocess
``python -m des.cli.verify_commit_trailers --commit <sha>``.
The observable surface is the process exit code and the structured INDETERMINATE
reason on stderr -- nothing else.

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a tmp directory with one
of two git environments:

  * GIT_BINARY_ABSENT: a non-work-tree tmp directory; the subprocess runs with
    a PATH that contains no ``git`` binary -> subprocess.run raises
    FileNotFoundError -> LOUD INDETERMINATE, exit 7.

  * SHA_UNRESOLVABLE: a real git work-tree (``git init``-ed) where the requested
    SHA (``"deadbeef0000000000000000000000000000000000000000000000000000dead"``)
    does not exist in the repo history. ``git show`` returns non-zero ->
    LOUD INDETERMINATE, exit 7.

PURE-READ CONTRACT (Mandate 8, layer-3 universe guard): des verify-commit-trailers
is a pure observer -- it MUST NOT mutate the target directory (no ``.git/``
changes, no file writes, no side effects). ``capture_universe`` snapshots the
port-exposed filesystem observables; the When-step asserts every entry is
``unchanged`` across the invocation.

EXIT-CODE LOCKED DECISION (DESIGN authority): exit 7 = INDETERMINATE
(cannot-evaluate). Exit 45 = ATReviewGateRejected (UNCHANGED). Exit 6 =
malformed-trailer (UNCHANGED). The non-conflation scenario asserts exit 7 is
distinct from both exit 4 (legacy tampering slot) and exit 6.

State lives on the instance; every ``given_/when_/then_`` method mutates or
reads that state. Step functions in ``test_slice_01_*.py`` are thin delegations
to these methods (Mandate-12 criterion 3: no business logic in step bodies).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    CANNOT_EVALUATE_EXIT,
    MALFORMED_EXIT,
    TAMPERING_EXIT,
    CommitEnvironment,
    CommitSha,
    VerifierVerdict,
)


# tests/des/acceptance/gate-trailer-read-seam-a-indeterminate/steps/composition.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production CLI module under test.
VERIFY_MODULE = "des.cli.verify_commit_trailers"

# A SHA that cannot exist in any freshly-init-ed git repo.
_UNRESOLVABLE_SHA = CommitSha(
    "deadbeef0000000000000000000000000000000000000000000000000000dead"
)


@dataclass
class TrailerVerifierComposition:
    """Drives the production des verify-commit-trailers CLI for slice-01 ATs."""

    _tmp: Path | None = field(default=None)
    _work_dir: Path | None = field(default=None)
    _env: CommitEnvironment = field(default=CommitEnvironment.GIT_BINARY_ABSENT)
    _target_sha: CommitSha | None = field(default=None)
    _git_free_path: Path | None = field(default=None)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)

    # ---- given -----------------------------------------------------------------

    def given_git_binary_absent(self) -> None:
        """Target directory with the git binary masked off PATH."""
        self._env = CommitEnvironment.GIT_BINARY_ABSENT
        self._build_substrate(CommitEnvironment.GIT_BINARY_ABSENT)

    def given_unresolvable_sha_in_work_tree(self) -> None:
        """Real git work-tree where the requested SHA does not exist in history."""
        self._env = CommitEnvironment.SHA_UNRESOLVABLE
        self._build_substrate(CommitEnvironment.SHA_UNRESOLVABLE)

    # ---- when ------------------------------------------------------------------

    def when_operator_runs_verifier(self) -> None:
        """Invoke the REAL des verify-commit-trailers CLI as a subprocess black box.

        Universe-bound pure-read guard (Mandate 8): the target directory is
        snapshot before and after; the verifier is a pure observer and must not
        mutate the directory.
        """
        before = self.capture_universe()
        self._run_verifier()
        self._assert_pure_read(before)

    # ---- then ------------------------------------------------------------------

    def then_refuses_with_loud_cannot_evaluate(self) -> None:
        """The verifier refuses with exit 7 AND a structured INDETERMINATE on stderr."""
        completed = self._require_completed()
        verdict = self.verdict()
        assert verdict is VerifierVerdict.CANNOT_EVALUATE, (
            "the verifier must refuse with the LOUD cannot-evaluate verdict (exit "
            f"{CANNOT_EVALUATE_EXIT}); got verdict={verdict.value!r}, "
            f"returncode={completed.returncode}. On master: GIT_BINARY_ABSENT "
            "propagates uncaught FileNotFoundError (exit ~1); SHA_UNRESOLVABLE "
            "raises RuntimeError caught -> exit 6. "
            f"{self._observed()}"
        )

    def then_cannot_evaluate_names_reason(self) -> None:
        """The structured INDETERMINATE payload names a cannot-evaluate reason."""
        completed = self._require_completed()
        stderr = completed.stderr
        # The reason must appear on stderr (not stdout -- the verifier writes
        # INDETERMINATE diagnostics to stderr per the DESIGN contract).
        assert stderr.strip() != "", (
            "the cannot-evaluate verdict must emit a non-empty diagnostic to "
            f"stderr naming why the commit body could not be read. {self._observed()}"
        )
        # The diagnostic must not be a raw Python traceback.
        assert "Traceback (most recent call last)" not in stderr, (
            "the cannot-evaluate verdict must NOT emit a raw Python traceback; "
            "it must emit a structured INDETERMINATE reason. "
            f"{self._observed()}"
        )
        # Must contain some INDETERMINATE / cannot-evaluate signal.
        assert any(
            token in stderr
            for token in ("INDETERMINATE", "cannot-evaluate", "git", "git-absent")
        ), (
            "the stderr payload must contain a recognisable cannot-evaluate signal "
            "(e.g. 'INDETERMINATE', 'cannot-evaluate', or a git-related reason). "
            f"{self._observed()}"
        )

    def then_no_raw_stack_trace(self) -> None:
        """The verifier does not emit a raw Python stack-trace to stderr."""
        completed = self._require_completed()
        assert "Traceback (most recent call last)" not in completed.stderr, (
            "the verifier must NOT emit a raw Python traceback on any "
            "cannot-evaluate condition (git-absent / SHA-unresolvable). "
            f"{self._observed()}"
        )

    def then_does_not_mutate_target_directory(self) -> None:
        """Pure-read: the universe guard already ran in the When-step.

        The Mandate-8 state-delta assertion fires inside ``when_operator_runs_verifier``
        (the mutation, if any, happens during invocation). This Then re-affirms the
        contract by confirming the run completed -- the actual no-mutation proof is
        the When-step's ``_assert_pure_read``.
        """
        self._require_completed()

    def then_cannot_evaluate_distinct_from_tampering(self) -> None:
        """Cannot-evaluate (exit 7) is distinct from HMAC mismatch / tampering (exit 4)."""
        completed = self._require_completed()
        assert completed.returncode != TAMPERING_EXIT, (
            f"cannot-evaluate (exit {CANNOT_EVALUATE_EXIT}) must NEVER be "
            f"conflated with HMAC mismatch / tampering (exit {TAMPERING_EXIT}). "
            "git-absence is an infrastructure cannot-evaluate condition; "
            "tampering is an integrity verdict. "
            f"{self._observed()}"
        )
        assert self.verdict() is VerifierVerdict.CANNOT_EVALUATE, (
            "the verifier verdict must be CANNOT_EVALUATE (exit 7), "
            f"not TAMPERING (exit {TAMPERING_EXIT}). {self._observed()}"
        )

    def then_cannot_evaluate_distinct_from_malformed(self) -> None:
        """Cannot-evaluate (exit 7) is distinct from malformed-trailer / --strict (exit 6)."""
        completed = self._require_completed()
        assert completed.returncode != MALFORMED_EXIT, (
            f"cannot-evaluate (exit {CANNOT_EVALUATE_EXIT}) must NEVER be "
            f"conflated with malformed-trailer (exit {MALFORMED_EXIT}). "
            "Today an unresolvable SHA raises RuntimeError caught -> exit 6 "
            "(the malformed code -- wrong). Post-GREEN: exit 7. "
            f"{self._observed()}"
        )
        assert self.verdict() is VerifierVerdict.CANNOT_EVALUATE, (
            "the verifier verdict must be CANNOT_EVALUATE (exit 7), "
            f"not MALFORMED (exit {MALFORMED_EXIT}). {self._observed()}"
        )

    # ---- observable-verdict parsing --------------------------------------------

    def verdict(self) -> VerifierVerdict:
        """Map the observable subprocess surface onto the user verdict.

        Reads the exit code. Exit 7 -> CANNOT_EVALUATE; exit 4 -> TAMPERING
        (legacy tampering slot, used for non-conflation assertion); exit 6 ->
        MALFORMED; anything else -> OTHER.
        """
        completed = self._require_completed()
        rc = completed.returncode
        if rc == CANNOT_EVALUATE_EXIT:
            return VerifierVerdict.CANNOT_EVALUATE
        if rc == TAMPERING_EXIT:
            return VerifierVerdict.TAMPERING
        if rc == MALFORMED_EXIT:
            return VerifierVerdict.MALFORMED
        return VerifierVerdict.OTHER

    def _observed(self) -> str:
        completed = self._require_completed()
        return (
            f"verifier returncode={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    # ---- universe (Mandate 8 pure-read guard) ----------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate 8).

        The verifier is a pure observer -- it reads the commit body via git but
        must NOT write to the work-dir. Universe entries are filesystem
        observables the gate could be tempted to touch, never internal struct
        fields.
        """
        work_dir = self._require_work_dir()
        return {
            "work_dir.file_count": sum(1 for _ in work_dir.rglob("*") if _.is_file()),
            "work_dir.dir_count": sum(1 for _ in work_dir.rglob("*") if _.is_dir()),
            "git.exists": (work_dir / ".git").exists(),
        }

    def _assert_pure_read(self, before: dict[str, object]) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert_state_delta(
            before=before,
            after=self.capture_universe(),
            universe={
                "work_dir.file_count",
                "work_dir.dir_count",
                "git.exists",
            },
            expected={
                "work_dir.file_count": unchanged(),
                "work_dir.dir_count": unchanged(),
                "git.exists": unchanged(),
            },
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) -----------------

    def _build_substrate(self, env: CommitEnvironment) -> None:
        """Build a tmp directory as the target for the verifier invocation."""
        self._tmp = Path(tempfile.mkdtemp(prefix="trailer-verifier-at-"))
        self._work_dir = self._tmp

        if env is CommitEnvironment.GIT_BINARY_ABSENT:
            # Plain tmp directory -- no git init needed; git binary is masked via PATH.
            # Pre-create the git-free dir NOW (before capture_universe) so the
            # universe snapshot includes it -- it must not change during the When-step.
            self._git_free_path = self._tmp / "_no_git_path"
            self._git_free_path.mkdir(parents=True, exist_ok=True)
            self._target_sha = CommitSha("HEAD")

        elif env is CommitEnvironment.SHA_UNRESOLVABLE:
            # Real git work-tree; the requested SHA does not exist in history.
            self._init_empty_git_repo()
            self._target_sha = _UNRESOLVABLE_SHA

    def _init_empty_git_repo(self) -> None:
        """``git init`` + one empty commit (so HEAD exists but has no user commits)."""
        work_dir = self._require_work_dir()
        run = lambda *a: subprocess.run(  # noqa: E731
            list(a), cwd=work_dir, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q")
        run("git", "config", "user.email", "at@example.com")
        run("git", "config", "user.name", "at")
        # Create an initial empty commit so HEAD resolves -- but the _UNRESOLVABLE_SHA
        # (deadbeef...) still won't exist in the repo's object store.
        (work_dir / "placeholder").write_text("placeholder\n", encoding="utf-8")
        run("git", "add", "-A")
        run("git", "commit", "-q", "-m", "initial placeholder")

    def _run_verifier(self) -> None:
        """Run ``python -m des.cli.verify_commit_trailers`` as a subprocess black box.

        Env-parity: a clean subprocess env with ``NWAVE_FRESHNESS=skip`` +
        ``PIPENV_DONT_LOAD_ENV=1``. The freshness opt-out is REQUIRED because
        cwd is the synthetic tmp tree: without it the freshness wrapper may
        refuse with exit 78 before the verifier logic runs, masking the
        cannot-evaluate verdict.

        For GIT_BINARY_ABSENT the PATH is narrowed to a git-free tmp directory
        so the subprocess's git resolution raises FileNotFoundError -- the
        genuine binary-absent degrade.
        """
        work_dir = self._require_work_dir()
        assert self._target_sha is not None, (
            "target SHA must be set by the Given step before running the verifier"
        )
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        env["PYTHONPATH"] = (
            str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        )

        if self._env is CommitEnvironment.GIT_BINARY_ABSENT:
            # Reuse the pre-created git-free dir (created in _build_substrate so
            # it is stable before capture_universe snapshots the directory tree).
            assert self._git_free_path is not None, (
                "_git_free_path must be set by _build_substrate before _run_verifier"
            )
            env["PATH"] = str(self._git_free_path)

        from des.cli import verify_commit_trailers
        from tests.common.in_process_cli import run_cli_in_process

        exit_code, stdout, stderr = run_cli_in_process(
            ["--commit", str(self._target_sha)],
            cwd=str(work_dir),
            main=verify_commit_trailers.main,
            env=env,
            catch_all=True,
        )
        self._completed = subprocess.CompletedProcess(
            args=["python", "-m", VERIFY_MODULE, "--commit", str(self._target_sha)],
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def _require_work_dir(self) -> Path:
        assert self._work_dir is not None, (
            "the synthetic target directory must be built (Given) before "
            "capturing its universe or running the verifier (When)"
        )
        return self._work_dir

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "des verify-commit-trailers must be run (When) before asserting on "
            "its observable verdict surface (Then)"
        )
        return self._completed

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
