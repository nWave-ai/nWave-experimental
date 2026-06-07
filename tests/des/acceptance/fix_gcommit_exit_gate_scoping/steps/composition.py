"""Composition root for fix-gcommit-exit-gate-scoping (Mandate-12 SSOT).

Mandate-13 (driving-port-only boundary): every service method drives the REAL
`des run-contract-gate` CLI as a Layer-3 SUBPROCESS black-box -- never a direct
`from des.cli.run_contract_gate import ...` + function-boundary call. The
digest-computation function is NEVER imported; the AT only observes the CLI's
stdout digest line, its exit code, and its structured health events. This is
the same definition the U2 G_COMMIT exit gate invokes (port-to-port).

DISTINCT MODE (re-scope 2026-05-31, orchestrator-ratified): the digest these
ATs drive is the NEW `des run-contract-gate --committed-scope-digest` mode,
NOT the GENERAL `--collect-only --print-digest`. The two modes are deliberately
separate surfaces:

  * GENERAL `--collect-only --print-digest` -- working-tree collection,
    non-git-OK, collect-then-classify (genuinely-empty -> exit 0; untrustworthy
    -> exit 2 MalformedInput). The `atdd_pure_spine_dogfood_defects` slice-01
    ATs + every existing pre-commit / CI / hook consumer depend on this. It is
    UNTOUCHED by this feature.
  * NEW `--committed-scope-digest` -- collection restricted to the COMMITTED
    file-set at HEAD (reproducible: invariant to untracked WIP), git-REQUIRED:
    git-absent / not-a-worktree / SHA-unresolvable -> LOUD
    `health.gate.committed-scope.indeterminate` + exit 2 (fail-closed refuse).

The reproducible committed-scope digest is a NEW capability; it MUST NOT
override the general digest's working-tree, non-git-OK semantics. The
G_COMMIT exit-gate `Gate-Scope` trailer + the hook's `--verify-gate-scope`
consume the NEW committed-scope mode (that is where reproducibility matters).

The SUT operates over a real git repository. The composition materialises a
minimal committed contract tree, pins its HEAD, and drives the committed-scope
digest CLI under two working-tree states (pristine / +1 untracked co-resident
file) so the reproducibility property can be witnessed at one fixed commit.
git enters ONLY as a real subprocess inside the fixture builder (a driven
dependency of the test harness), never as production code the AT imports.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    CommittedContent,
    CommittedSuiteShape,
    Digest,
    DigestOutcome,
    WorkingTreeState,
)


# The exit code `run_contract_gate` returns when it fails closed (it emits a
# `MalformedInput` event and returns 2). Exit-code-exact: any OTHER non-zero is
# a WRONG failure mode, surfaced as DigestOutcome.UNEXPECTED.
_GATE_REFUSE_EXIT = 2


@dataclass
class DigestRun:
    """The observable outcome of one `des run-contract-gate --committed-scope-digest`."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def outcome(self) -> DigestOutcome:
        """How the gate resolved -- derived EXIT-CODE-EXACT.

        exit 0 -> DIGEST_PRINTED; exit 2 -> REFUSED (fail-closed); any other
        non-zero -> UNEXPECTED, so a refusal assertion never passes for the
        wrong reason (e.g. an argparse error or an uncaught crash).
        """
        if self.exit_code == 0:
            return DigestOutcome.DIGEST_PRINTED
        if self.exit_code == _GATE_REFUSE_EXIT:
            return DigestOutcome.REFUSED
        return DigestOutcome.UNEXPECTED

    @property
    def digest(self) -> Digest:
        """The bare SHA-256 digest line printed on stdout (empty when none)."""
        lines = [ln.strip() for ln in self.stdout.splitlines() if ln.strip()]
        # The digest is a bare 64-hex line; ignore any JSON/log chatter lines.
        for line in lines:
            if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
                return Digest(line)
        return Digest("")


@dataclass
class GcommitScopingComposition:
    """Production composition root driving the real `des run-contract-gate` CLI."""

    last_run: DigestRun | None = field(default=None)

    # --- fixture builders (real git repo; git is a test-harness dependency) ---

    def make_committed_contract_repo(self, root: Path) -> Path:
        """Materialise a git repo whose contract suite is fully COMMITTED.

        Two contract-marked tests are written and committed, so HEAD pins a
        real, non-empty committed contract suite. No untracked files remain --
        the PRISTINE working-tree state. This is the fixed commit the
        reproducibility property is witnessed at.
        """
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        (root / "test_committed_contract.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
            "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
        )
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "atdd@nwave.ai")
        self._git(root, "config", "user.name", "atdd")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "committed contract suite")
        return root

    def make_committed_mixed_contract_repo(
        self, root: Path, shape: CommittedSuiteShape
    ) -> Path:
        """Materialise a git repo whose committed suite has the requested shape.

        The genuine-witness twin: MIXED_PY_AND_FEATURE commits a realistic mix
        -- a `.py` test module AND a specification `.feature` file -- mirroring
        the real repo's committed contract suite (227 committed `.feature`).
        Passing the committed `.feature` to pytest as a `--path` makes pytest
        exit 4 today (it cannot collect a `.feature` directly), so the gate fails
        closed instead of fingerprinting the committed suite. The small
        `.py`-only fixtures masked this; this commits the missing twin.
        """
        assert shape is CommittedSuiteShape.MIXED_PY_AND_FEATURE
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        (root / "test_committed_contract.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
            "@pytest.mark.acceptance\ndef test_b():\n    assert True\n"
        )
        # The committed `.feature` spec -- the file-kind the `.py`-only fixtures
        # never committed, and the exact trigger for pytest collection exit 4.
        (root / "committed_behaviour.feature").write_text(
            "Feature: a committed specification\n"
            "  Scenario: a committed scenario\n"
            "    Given a precondition\n"
            "    When an action occurs\n"
            "    Then an outcome is observed\n"
        )
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "atdd@nwave.ai")
        self._git(root, "config", "user.name", "atdd")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-qm", "committed mixed contract suite")
        return root

    def place_working_tree(self, repo: Path, state: WorkingTreeState) -> Path:
        """Bring ``repo`` into the requested working-tree state.

        PRISTINE leaves only committed files on disk. CORESIDENT_UNTRACKED adds
        ONE untracked co-resident contract-marked test file (NOT committed) --
        the exact perturbation that changes a working-tree-collected digest but
        must NOT change a committed-tree-collected digest at the same commit.
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

    def commit_new_contract_test(self, repo: Path, content: CommittedContent) -> Digest:
        """Commit a NEW contract test ANYWHERE in the tree, return the new digest.

        slice-01 AT-2 (whole-committed-tree breadth, OPT-a guard): a committed
        test anywhere must be IN the digest, so committing it MOVES the digest.
        The new test lives under an UNRELATED subdirectory (a different feature
        area) -- the OPT-a regression (feature-scoping the digest) would let it
        fall outside the committing feature's scope and NOT move a narrowed
        digest. This pins that the digest stays a whole-committed-tree witness.
        """
        assert content is CommittedContent.NEW_COMMITTED_TEST
        other = repo / "unrelated_area"
        other.mkdir(exist_ok=True)
        (other / "test_unrelated_committed.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.integration\ndef test_unrelated():\n    assert True\n"
        )
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-qm", "another committed contract test elsewhere")
        return self.derive_digest(repo).digest

    def make_non_git_contract_dir(self, root: Path) -> Path:
        """Materialise a contract tree that is NOT a git work-tree.

        slice-01 AT-3 (git-absent -> LOUD INDETERMINATE -> refuse): the dir
        carries a real contract-marked test but has no `.git/`, so the
        `CommittedScopePort` cannot establish the committed contract. The
        fail-closed gate MUST emit the LOUD INDETERMINATE health event and
        REFUSE -- never silently fingerprint the working tree.
        """
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n'
        )
        (root / "test_ungit.py").write_text(
            "import pytest\n\n@pytest.mark.unit\ndef test_x():\n    assert True\n"
        )
        return root

    # --- driving port: the real `des run-contract-gate` CLI subprocess ---

    def derive_digest(self, repo: Path) -> DigestRun:
        """Drive `des run-contract-gate --committed-scope-digest` (subprocess).

        Mandate-13 Layer-3 subprocess black-box: the AT spawns the real CLI by
        module and observes only its stdout / stderr / exit code. The digest
        function is never imported. Run via `sys.executable -m
        des.cli.run_contract_gate` so the test's own interpreter resolves `des`
        without depending on a `des` console-script being on PATH.

        Re-scope (2026-05-31): drives the NEW `--committed-scope-digest` mode,
        NOT the general `--collect-only --print-digest`. The committed-scope
        mode collects only the COMMITTED file-set at HEAD (reproducible) and is
        git-REQUIRED (git-absent -> LOUD INDETERMINATE + exit 2). This keeps the
        general working-tree digest -- which the dogfood ATs + backward-compat
        consumers depend on -- entirely untouched (no collision).
        """
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                str(repo),
                "--committed-scope-digest",
            ],
            capture_output=True,
            text=True,
        )
        self.last_run = DigestRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return self.last_run

    # --- git as a test-harness dependency (NOT production import) ---

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        """Run a git command in ``repo`` (raises on non-zero)."""
        subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
