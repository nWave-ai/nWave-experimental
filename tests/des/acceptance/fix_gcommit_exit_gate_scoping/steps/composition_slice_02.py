"""Composition root for fix-gcommit-exit-gate-scoping slice-02 (Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): every service method drives the REAL
`des run-contract-gate --verify-gate-scope` CLI as a Layer-3 SUBPROCESS
black-box -- never a direct `from des.cli.run_contract_gate import ...` +
function-boundary call. The verify / digest functions are NEVER imported; the AT
observes only the CLI's verify-verdict event, its exit code, and its structured
health events. This is the same definition the U2 G_COMMIT exit-gate hook
invokes (port-to-port: `subagent_stop_handler._run_gate_subprocess`).

slice-02 (WIRING): the exit-gate verify check
(`run_contract_gate._mode_verify_gate_scope:488`) and the terminating Gate-Scope
trailer compute (`:547`) must switch from the WORKING-TREE
`gate_scope_digest(repo)` to the committed-scope digest shipped in slice-01.
These ATs materialise a real git repo, COMMIT a `Gate-Scope:` trailer carrying
the committed-scope digest, then drive `--verify-gate-scope` over that one pinned
commit under two working-tree states (pristine / +1 untracked co-resident file).
At HEAD the verify check digests the WORKING tree, so the untracked file
PERTURBS the fresh digest -> mismatch in the co-resident state (the RED witness).

The committed-scope digest used to build the MATCHING trailer is obtained from
the slice-01 `--committed-scope-digest` mode (already shipped) -- the trailer the
verify check must match is, by construction, the committed-tree digest, so once
the verify check is wired to committed-scope it verifies under BOTH working-tree
states.

git enters ONLY as a real subprocess inside the fixture builder (a driven
dependency of the test harness), never as production code the AT imports.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.cli.run_contract_gate import main as _run_contract_gate_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_02 import (
    CommittedSuiteShape,
    TrailerState,
    VerifyOutcome,
    WorkingTreeState,
)


_VERIFY_VERIFIED_EXIT = 0
_VERIFY_UNVERIFIED_EXIT = 1
_VERIFY_REFUSE_EXIT = 2


@dataclass
class VerifyRun:
    """The observable outcome of one `des run-contract-gate --verify-gate-scope`."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def outcome(self) -> VerifyOutcome:
        """How the verify check resolved -- derived EXIT-CODE-EXACT.

        exit 0 -> VERIFIED; exit 1 -> UNVERIFIED (absent / mismatch); exit 2 ->
        REFUSED (fail-closed); any other non-zero -> UNEXPECTED, so a verdict
        assertion never passes for the wrong reason (argparse error / crash).
        """
        if self.exit_code == _VERIFY_VERIFIED_EXIT:
            return VerifyOutcome.VERIFIED
        if self.exit_code == _VERIFY_UNVERIFIED_EXIT:
            return VerifyOutcome.UNVERIFIED
        if self.exit_code == _VERIFY_REFUSE_EXIT:
            return VerifyOutcome.REFUSED
        return VerifyOutcome.UNEXPECTED


@dataclass
class GcommitVerifyComposition:
    """Production composition root driving the real `--verify-gate-scope` CLI."""

    last_run: VerifyRun | None = field(default=None)
    pinned_commit: str | None = field(default=None)

    # --- fixture builders (real git repo; git is a test-harness dependency) ---

    def make_commit_pinning_its_committed_suite(
        self, root: Path, trailer: TrailerState
    ) -> Path:
        """Materialise a git repo whose HEAD commit carries a `Gate-Scope:` trailer.

        * TrailerState.MATCHING -- the trailer pins the commit's actual
          committed-scope digest. The verify check should return VERIFIED, and
          (after slice-02 wiring) must stay VERIFIED across the untracked-WIP
          perturbation (AT-1).
        * TrailerState.STALE -- the FINAL HEAD commit carries a PRESENT
          `Gate-Scope:` trailer whose digest is the committed-scope digest of an
          EARLIER tree (before an extra test was committed), so the trailer no
          longer matches the pinned commit's OWN committed tree. The verify check
          reads the present trailer, computes a fresh digest, and they DIFFER ->
          `GateScopeUnverified reason=mismatch` (NOT reason=absent). This proves
          the committed-tree regression witness is preserved (AT-2, OPT-b breadth
          guard): a committed change that moves the digest still fails verify.
        """
        self._write_committed_contract(root)
        self._git_init_commit(root, "committed contract suite")
        if trailer is TrailerState.MATCHING:
            # The trailer pins the commit's OWN committed-scope digest -> verify
            # should MATCH (AT-1 happy path).
            self._amend_with_trailer(root, self._committed_scope_digest(root))
            self.pinned_commit = self._git(root, "rev-parse", "HEAD").strip()
            return root
        # STALE: capture the would-be-stale digest of the CURRENT (smaller) tree
        # BEFORE moving it, then commit an unrelated test so the committed tree
        # moves PAST that digest, then amend the STALE trailer onto the FINAL
        # HEAD. The verified commit therefore carries a PRESENT trailer that
        # MISMATCHES its own committed tree -> reason=mismatch (not absent).
        stale_digest = self._committed_scope_digest(root)
        other = root / "unrelated_area"
        other.mkdir(exist_ok=True)
        (other / "test_unrelated_committed.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.integration\ndef test_unrelated():\n    assert True\n"
        )
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "a committed change moving the digest")
        self._amend_with_trailer(root, stale_digest)
        self.pinned_commit = self._git(root, "rev-parse", "HEAD").strip()
        return root

    def make_commit_pinning_committed_mixed_suite(
        self, root: Path, shape: CommittedSuiteShape
    ) -> Path:
        """Materialise a commit pinning a committed MIXED (`.py` + `.feature`) suite.

        The genuine-witness twin (mirrored from slice-01 AT-4): the committed
        contract suite mixes a `.py` test module AND a specification `.feature`
        file -- the file-kind composition the `.py`-only fixtures never witnessed
        (the real tree has 227 committed `.feature`). The trailer pins this
        commit's committed-scope digest; under the untracked-WIP perturbation the
        verify check must verify the mixed suite IDENTICALLY in both states.
        """
        assert shape is CommittedSuiteShape.MIXED_PY_AND_FEATURE
        self._write_committed_contract(root)
        (root / "committed_behaviour.feature").write_text(
            "Feature: a committed specification\n"
            "  Scenario: a committed scenario\n"
            "    Given a precondition\n"
            "    When an action occurs\n"
            "    Then an outcome is observed\n"
        )
        self._git_init_commit(root, "committed mixed contract suite")
        self._amend_with_trailer(root, self._committed_scope_digest(root))
        self.pinned_commit = self._git(root, "rev-parse", "HEAD").strip()
        return root

    def make_non_git_trailer_target(self, root: Path) -> Path:
        """Materialise a contract tree that is NOT a git work-tree (git-absent).

        slice-02 AT-3 (git-absent -> LOUD INDETERMINATE -> refuse, inherited from
        the committed-scope mode): the dir carries a real contract test but has
        no `.git/`, so the verify check cannot pin the (synthetic) commit to a
        committed revision. The fail-closed gate MUST emit the LOUD INDETERMINATE
        health event and REFUSE -- never silently digest the working tree.
        """
        self._write_committed_contract(root)
        self.pinned_commit = "HEAD"
        return root

    def place_working_tree(self, repo: Path, state: WorkingTreeState) -> Path:
        """Bring ``repo`` into the requested working-tree state.

        PRISTINE leaves only committed files on disk. CORESIDENT_UNTRACKED adds
        ONE untracked co-resident contract-marked test file (NOT committed) --
        the exact perturbation that moves a WORKING-TREE-collected fresh digest
        (today's verify check) but must NOT move a committed-tree-collected one.
        """
        coresident = repo / "test_coresident_feature_b_untracked.py"
        if state is WorkingTreeState.CORESIDENT_UNTRACKED:
            coresident.write_text(
                "import pytest\n\n"
                "@pytest.mark.unit\ndef test_coresident_untracked():\n"
                "    assert True\n"
            )
        elif coresident.exists():
            coresident.unlink()
        return repo

    # --- driving port: the real `des run-contract-gate --verify-gate-scope` ---

    def verify_gate_scope(self, repo: Path) -> VerifyRun:
        """Drive `des run-contract-gate --verify-gate-scope` (subprocess).

        Mandate-13 Layer-3 subprocess black-box: spawn the real CLI by module and
        observe only its stdout / stderr / exit code. The verify / digest
        functions are never imported. This is the SAME definition the U2 G_COMMIT
        exit-gate hook invokes as a separate subprocess
        (`subagent_stop_handler._run_gate_subprocess` -> `:631-644`). slice-02
        switches the digest this mode computes from the WORKING tree (`:488`) to
        the committed tree at the pinned commit.
        """
        assert self.pinned_commit is not None, "no commit pinned for verify"
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--repo",
                str(repo),
                "--commit",
                self.pinned_commit,
                "--verify-gate-scope",
            ],
            cwd=repo,
            main=_run_contract_gate_main,
        )
        self.last_run = VerifyRun(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )
        return self.last_run

    # --- committed-scope digest (slice-01 mode) used to build the trailer ---

    def _committed_scope_digest(self, repo: Path) -> str:
        """Return the slice-01 committed-scope digest of ``repo`` at HEAD.

        The trailer the verify check must MATCH is, by construction, the
        committed-tree digest -- so once slice-02 wires the verify check to
        committed-scope, the verdict is invariant to untracked WIP. Driven
        through the shipped `--committed-scope-digest` CLI (subprocess), not an
        import.
        """
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--repo",
                str(repo),
                "--committed-scope-digest",
            ],
            cwd=repo,
            main=_run_contract_gate_main,
        )
        for line in (ln.strip() for ln in stdout.splitlines()):
            if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
                return line
        raise AssertionError(
            "could not derive a committed-scope digest to build the trailer "
            f"(exit {exit_code}); stdout={stdout!r} "
            f"stderr={stderr!r}"
        )

    # --- git as a test-harness dependency (NOT production import) ---

    def _write_committed_contract(self, root: Path) -> None:
        """Write a minimal, marker-tagged contract suite into ``root``."""
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        (root / "test_committed_contract.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
            "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
        )

    def _git_init_commit(self, root: Path, message: str) -> None:
        """Init a repo in ``root`` and commit everything with ``message``."""
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "atdd@nwave.ai")
        self._git(root, "config", "user.name", "atdd")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", message)

    def _amend_with_trailer(self, root: Path, digest: str) -> None:
        """Amend HEAD so its message carries the `Gate-Scope:` trailer."""
        original = self._git(root, "log", "-1", "--format=%B", "HEAD").strip()
        self._git(
            root,
            "commit",
            "-q",
            "--amend",
            "-m",
            f"{original}\n\nGate-Scope: {digest}",
        )

    @staticmethod
    def _git(repo: Path, *args: str) -> str:
        """Run a git command in ``repo`` (raises on non-zero), return stdout."""
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
