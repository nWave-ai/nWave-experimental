"""Composition root for des-spine-control-plane-ssot slice-02 (Mandate-12 SSOT).

Pillar 3 (App as in production): the SUT is the REAL `des run-contract-gate` CLI
— the contract-gate driving port wired at `des.cli.__main__:69` — invoked exactly
as the operator / the G_COMMIT exit-gate hook invokes it
(`subagent_stop_handler._run_gate_subprocess`). The producer-fallback-removal
(AD-23) behavior is observed via the process exit code + the structured
`ContractGateResult` / `health.gate.committed-scope.indeterminate` events on the
gate's output, never by importing the digest functions.

Mandate-13 (invariant 1+2): every service method drives the CLI as a Layer-3
SUBPROCESS black-box — NEVER a direct
`from des.cli.run_contract_gate import gate_scope_digest` + function-boundary
call, NEVER `from des.adapters.driven.git.committed_scope_adapter import ...`.
The committed-scope / digest / verify functions are NEVER imported; the AT
observes only the CLI's exit code + structured events. git enters ONLY as a real
subprocess inside the fixture builder (a driven dependency of the TEST harness),
never as production code the AT imports.

Mandate-13 (invariant 5) — GIT-FREE in the test mechanics for the SUT path:
the GIT-ABSENT topology is constructed by simply NOT creating a `.git/`
directory (a plain filesystem dir). The slice-02 AT proves the producer's
git-ABSENT path degrades LOUD (committed-scope.indeterminate, NO trailer) — the
target-machine-independence assertion (git is NOT a runtime dependency of the
gate logic; it sits behind the optional `CommittedScopePort` and degrades LOUD
when absent). The GIT-TREE fixture uses real git, but only as a test-harness
dependency to MATERIALISE a committed tree the production gate then reads through
its port.

Mandate-12 criterion 2/3: `ContractGateFixture` is the single source of truth for
ALL business logic the step methods need. Step bodies in `steps_slice_02_*.py`
delegate here — each body is ≤2 statements ending in one `fixture.<method>(...)`
call (or one assertion), no control flow inline.

DISTILL-authored RED scaffold (ADR-025): `des run-contract-gate` ALREADY EXISTS,
but slice-02's NEW behavior does NOT:
  * AD-23 — the producer (`_mode_run_suite:638-645`) STILL falls back to a
    WORKING-tree digest on git-absent (`:645 digest = gate_scope_digest(repo)`)
    SILENTLY, with NO `committed-scope.indeterminate` marker. Empirically
    witnessed at DISTILL HEAD: a git-absent default suite-run exits 0 and emits a
    `ContractGateResult` WITH a `gate_scope_digest` and NO indeterminate event.
  * ADR-CP-002 OQ-A5 — the `GitCommittedScopeAdapter` has NO `probe()` (Earned
    Trust): grep-confirmed `def probe` absent on both port + adapter.
So AT-02 RED-fails (the git-absent producer must stamp NO digest + emit the LOUD
marker; today it stamps a working-tree digest + is silent) for MISSING_FUNCTIONALITY
— NOT import error (Mandate-7 RED-vs-BROKEN preserved). AT-01 (git-tree portable
trailer) + AT-03 (round-trip verify) are regression pins that pass today on the
git path AND tighten the contract: AT-01 asserts the stamped digest EQUALS the
independent `--committed-scope-digest` (committed-scope, not working-tree).

Layer 3 (subprocess against tmp_path, @real-io — the driven set includes a real
filesystem adapter + the real git work-tree): example-only (Mandate 9 v2). No PBT
machinery. Sad path (git-absent) is one explicit named example (Mandate 11).
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_02 import (
    COMMITTED_SCOPE_INDETERMINATE_EVENT,
    CONTRACT_GATE_RESULT_EVENT,
    ContractTreeProbe,
    ProducerOutcome,
    ProducerRun,
    RevisionControl,
    VerifyOutcome,
    VerifyRun,
)


_PRODUCER_PASS_EXIT = 0
_VERIFY_VERIFIED_EXIT = 0
_VERIFY_UNVERIFIED_EXIT = 1
_VERIFY_REFUSE_EXIT = 2


def _iter_json_events(combined: str) -> list[dict]:
    """Parse every single-line JSON object from a combined stdout+stderr stream.

    The CLI emits one JSON object per line on stdout and/or stderr; freshness
    chatter and the human verdict line are NON-JSON and skipped. Pure function.
    """
    events: list[dict] = []
    for raw_line in combined.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _contract_gate_result_digest(combined: str) -> tuple[bool, str | None]:
    """Return (result_event_present, stamped_digest) from the producer stream.

    `ContractGateResult` is the producer's structured verdict. When a portable
    trailer was stampable it carries a `gate_scope_digest`; post-slice-02, on a
    git-absent tree NO digest is present (the AD-23 fix). Returns the digest as
    `None` when the event is present without one, or when no event is present.
    Pure function — SSOT for the digest-extraction logic so step bodies stay thin.
    """
    for event in _iter_json_events(combined):
        if event.get("event") == CONTRACT_GATE_RESULT_EVENT:
            digest = event.get("gate_scope_digest")
            return True, (digest if isinstance(digest, str) and digest else None)
    return False, None


def _indeterminate_emitted(combined: str) -> bool:
    """True iff the LOUD `committed-scope.indeterminate` marker is on the stream.

    Pure function — SSOT for the degrade-LOUD detection so the step body that
    asserts the git-absent path stays a thin delegate (Mandate-12 criterion 3).
    """
    return any(
        event.get("event") == COMMITTED_SCOPE_INDETERMINATE_EVENT
        for event in _iter_json_events(combined)
    )


@dataclass
class ContractGateFixture:
    """Composition-root service for des-spine-control-plane-ssot slice-02 ATs.

    Pillar 3: drives the SAME `des run-contract-gate` CLI the operator + the
    G_COMMIT exit-gate hook invoke, against a synthetic contract tree under
    tmp_path. The git-vs-git-absent seam, the portable-trailer stamp, and the
    degrade-LOUD indeterminate are all expressed as filesystem topology. The AT
    observes the gate's decision via exit code + structured events.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing more.
    """

    _tmp_path: Path
    last_producer_run: ProducerRun | None = field(default=None)

    # --- contract-tree construction (the git-vs-git-absent seam) -----------

    def build_contract_tree(
        self, *, revision_control: RevisionControl
    ) -> ContractTreeProbe:
        """Lay out a synthetic marker-tagged contract suite under tmp_path.

        GIT_TREE   → a real `.git/` work-tree whose HEAD commits the contract
                     suite (git as a TEST-harness dependency). HEAD is resolved
                     so the verifier (AT-03) can pin it.
        GIT_ABSENT → a plain directory with the SAME contract suite but NO
                     `.git/` (GIT-FREE construction — the dir is simply never
                     `git init`-ed). The producer cannot pin it to a committed
                     revision → the degrade-LOUD path slice-02 fixes.
        """
        root = self._tmp_path / revision_control.name.lower()
        root.mkdir(parents=True, exist_ok=True)
        self._write_committed_contract(root)
        if revision_control is RevisionControl.GIT_ABSENT:
            return ContractTreeProbe(
                root_path=str(root),
                revision_control=revision_control,
                pinned_commit=None,
            )
        self._git_init_commit(root, "committed contract suite")
        pinned = self._git(root, "rev-parse", "HEAD").strip()
        return ContractTreeProbe(
            root_path=str(root),
            revision_control=revision_control,
            pinned_commit=pinned,
        )

    # --- the driving-port fire (real `des run-contract-gate` subprocess) ----

    def run_contract_gate(self, tree: ContractTreeProbe) -> ProducerRun:
        """Fire the REAL `des run-contract-gate` producer (default mode).

        Mandate-13 Layer-3 subprocess black-box: spawn the canonical CLI by
        module-path and observe only its stdout / stderr / exit code. The
        digest / committed-scope functions are NEVER imported. This is the SAME
        definition the terminating crafter run + the G_COMMIT exit-gate hook
        invoke. On a git tree the producer stamps the committed-scope digest of
        HEAD into the `ContractGateResult`; on a git-absent tree (post-slice-02)
        it emits the LOUD `committed-scope.indeterminate` marker and stamps NO
        digest, while the suite still runs.

        `NWAVE_FRESHNESS=skip` isolates the slice-01 install-freshness gate so
        the producer-fallback behavior is observed without freshness chatter
        confounding the assertion (DV-1: per-subprocess tests set skip).
        """
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                tree.root_path,
            ],
            capture_output=True,
            text=True,
            env=self._gate_env(),
            timeout=120,
        )
        run = self._classify_producer_run(completed)
        self.last_producer_run = run
        return run

    def verify_stamped_trailer(self, tree: ContractTreeProbe) -> VerifyRun:
        """Round-trip: stamp the producer's portable trailer, then verify it.

        AT-03 (the round-trip discriminator): a producer-stamped portable trailer
        is only a GUARANTEE if the verifier independently re-derives the SAME
        committed-scope digest (ADR-CP-001 producer==verifier). This drives the
        REAL `--committed-scope-digest` mode to obtain the producer's committed
        digest, amends it as a `Gate-Scope:` trailer onto HEAD, then drives the
        REAL `--verify-gate-scope` mode over that pinned commit. VERIFIED proves
        the stamped digest IS the verifiable committed-scope digest, not a
        present-but-unverifiable token. All three are real CLI subprocesses; no
        production digest function is imported.
        """
        assert tree.revision_control is RevisionControl.GIT_TREE
        root = Path(tree.root_path)
        digest = self._committed_scope_digest(root)
        self._amend_with_trailer(root, digest)
        pinned = self._git(root, "rev-parse", "HEAD").strip()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.run_contract_gate",
                "--repo",
                str(root),
                "--commit",
                pinned,
                "--verify-gate-scope",
            ],
            capture_output=True,
            text=True,
            env=self._gate_env(),
            timeout=120,
        )
        return VerifyRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            outcome=self._verify_outcome(completed.returncode),
        )

    # --- pure classifiers (SSOT for the observable-outcome derivation) ------

    @staticmethod
    def _classify_producer_run(
        completed: subprocess.CompletedProcess[str],
    ) -> ProducerRun:
        """Derive the port-exposed ProducerRun from a completed subprocess.

        The portable-trailer verdict is EXIT-CODE-EXACT + structured-event-exact:
        a STAMPED_PORTABLE run exits 0 AND carries a `gate_scope_digest`; a
        RAN_NO_TRAILER run exits 0, carries NO digest, AND emits the LOUD
        `committed-scope.indeterminate` marker (the suite still ran). Anything
        else is UNEXPECTED so a verdict never passes for the wrong reason.
        """
        combined = completed.stdout + "\n" + completed.stderr
        present, digest = _contract_gate_result_digest(combined)
        indeterminate = _indeterminate_emitted(combined)
        outcome = ContractGateFixture._producer_outcome(
            completed.returncode, present, digest, indeterminate
        )
        return ProducerRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            outcome=outcome,
            stamped_digest=digest,
            indeterminate_emitted=indeterminate,
        )

    @staticmethod
    def _producer_outcome(
        exit_code: int,
        result_present: bool,
        digest: str | None,
        indeterminate: bool,
    ) -> ProducerOutcome:
        """Map (exit, result-present, digest, indeterminate) → ProducerOutcome.

        Pure decision table — SSOT so neither the step body nor the dataclass
        re-derives the verdict.
        """
        if exit_code != _PRODUCER_PASS_EXIT:
            return ProducerOutcome.UNEXPECTED
        if result_present and digest is not None and not indeterminate:
            return ProducerOutcome.STAMPED_PORTABLE
        if indeterminate and digest is None:
            return ProducerOutcome.RAN_NO_TRAILER
        return ProducerOutcome.UNEXPECTED

    @staticmethod
    def _verify_outcome(exit_code: int) -> VerifyOutcome:
        """Map a verify exit code → VerifyOutcome (EXIT-CODE-EXACT)."""
        if exit_code == _VERIFY_VERIFIED_EXIT:
            return VerifyOutcome.VERIFIED
        if exit_code == _VERIFY_UNVERIFIED_EXIT:
            return VerifyOutcome.UNVERIFIED
        if exit_code == _VERIFY_REFUSE_EXIT:
            return VerifyOutcome.REFUSED
        return VerifyOutcome.UNEXPECTED

    # --- committed-scope equality (AT-01 second observable) ----------------

    def stamped_digest_matches_committed_scope(
        self, run: ProducerRun, tree: ContractTreeProbe
    ) -> bool:
        """True iff the stamped trailer EQUALS the tree's committed-scope digest.

        SSOT for the ADR-CP-001 producer==verifier equality check so the step
        body stays a thin delegate (Mandate-12 criterion 3 — no inline import /
        private-method reach-in in the step). Drives the shipped
        `--committed-scope-digest` mode independently and compares.
        """
        independent = self._committed_scope_digest(Path(tree.root_path))
        return run.stamped_digest == independent

    # --- committed-scope digest (shipped mode) used to build the trailer ----

    def _committed_scope_digest(self, repo: Path) -> str:
        """Return the committed-scope digest of ``repo`` at HEAD (shipped mode).

        Driven through the shipped `--committed-scope-digest` CLI (subprocess),
        not an import. The trailer the verify check must MATCH is, by
        construction, the committed-tree digest — so once the producer is
        committed-scope, the round-trip verifies (AT-03).
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
            env=self._gate_env(),
            timeout=120,
        )
        for line in (ln.strip() for ln in completed.stdout.splitlines()):
            if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
                return line
        raise AssertionError(
            "could not derive a committed-scope digest to build the trailer "
            f"(exit {completed.returncode}); stdout={completed.stdout!r} "
            f"stderr={completed.stderr!r}"
        )

    # --- git as a test-harness dependency (NOT production import) ----------

    @staticmethod
    def _gate_env() -> dict[str, str]:
        """Env for the gate subprocess: inherit + isolate the freshness gate.

        `NWAVE_FRESHNESS=skip` short-circuits the slice-01 install-freshness gate
        so the slice-02 committed-scope behavior is observed in isolation (DV-1).
        """
        import os

        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        return env

    @staticmethod
    def _write_committed_contract(root: Path) -> None:
        """Write a minimal, marker-tagged contract suite into ``root``."""
        (root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'markers = ["unit", "integration", "acceptance"]\n',
            encoding="utf-8",
        )
        (root / "test_committed_contract.py").write_text(
            "import pytest\n\n"
            "@pytest.mark.unit\ndef test_a():\n    assert True\n\n"
            "@pytest.mark.acceptance\ndef test_b():\n    assert True\n",
            encoding="utf-8",
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
        """Run a git command in ``repo`` (raises on non-zero), return stdout.

        git is a TEST-HARNESS dependency used ONLY to materialise the committed
        topology — NEVER a production import. The production gate reads git
        through its own `CommittedScopePort` adapter, which the AT does not touch.
        """
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout


__all__ = ["ContractGateFixture"]
