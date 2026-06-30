"""Composition root for the fix-slicecommitverified-emission ATs.

slice-01: the carpaccio entry-gate auto-backfill happy path.
slice-02: the carpaccio entry-gate auto-backfill FAIL-CLOSED rows -- the
backfill must NOT false-allow on bad/missing E2-evidence (absent or
stale ``Gate-Scope:`` trailer, or no predecessor commit on disk). Each
slice-02 AT asserts BOTH that the entering slice is BLOCKED and that NO
``SliceCommitVerified`` record was appended (the anti-false-allow keystone).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION composition-root driving port -- the real U1 carpaccio PreToolUse
intercept ``intercept_atdd_pure_dispatch``
(``des.adapters.drivers.hooks.carpaccio_intercept``). This is the Layer-3
composition driving surface (the hook driver), exactly as the shipped
``atdd_pure_spine_hardening`` slice-01 ATs drive it. The composition NEVER
imports the intercept's order-block / backfill logic and calls it at the step
boundary -- the only entry is the production intercept driving port.

The production ``AtCompletionLedger`` writer + reader is used ONLY to
(a) seed the precondition substrate (the predecessor's ledger state) and
(b) read back the observable ``SliceCommitVerified`` record the auto-backfill
appends. This is the audit SUBSTRATE the hook consumes, not the SUT -- the
adjudicated real-git + real-ledger carve-out for this feature. This mirrors the
shipped ``atdd_pure_spine_hardening/steps/slice01_composition.py`` pattern
(it seeds ``SliceCommitVerified`` through the same writer for the same M8
order-check ledger universe).

The git repo, the feature-delta ``[REF] Slice Plan``, and the ledger JSONL are
all real I/O -- a layer-3 ``@real-io`` surface (Mandate 9/11: example only, no
PBT machinery; layer-3 sad/edge paths enumerated explicitly).

Business logic lives in the production module; step bodies delegate to
``BackfillEntryGateComposition`` methods and never inline logic
(Mandate-12 criterion 3).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    intercept_atdd_pure_dispatch,
)
from des.cli import run_contract_gate
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    EntryGateVerdict,
    FeatureId,
    GateScopeSeed,
    PredecessorLedgerState,
    SliceId,
)


_FEATURE_ID = FeatureId("slicecommit-backfill-demo")
_STALE_DIGEST = "0" * 64


def _git(repo: Path, *args: str) -> str:
    """Run a real git command in ``repo`` (no test double -- real I/O)."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _fresh_gate_scope_digest(repo: Path) -> str:
    """Compute the verifiable Gate-Scope digest the in-gate verify recomputes.

    Runs the PRODUCTION ``run_contract_gate --collect-only --print-digest``
    against the seeded test repo -- the exact code path the in-gate
    ``--verify-gate-scope`` recomputes a fresh digest from, so the seeded
    trailer is guaranteed byte-identical to the fresh recomputation. The bare
    digest is printed on stdout (the JSON event goes to stderr).

    Driven in-process via ``run_cli_in_process`` against the in-process-ready
    ``run_contract_gate.main`` EDGE -- the analogue of the former
    ``des.cli.run_contract_gate --collect-only --print-digest`` module-form
    subprocess. The gate isolates its pytest collection in its OWN short-lived
    worker subprocess (``run_contract_gate._collect_scope``), so driving ``main``
    in-process never nests a pytest session in the outer one. ``check=True``
    parity: a non-zero exit raises (the digest seed must succeed).
    """
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "--collect-only",
            "--print-digest",
            "--repo",
            str(repo),
        ],
        cwd=repo,
        main=run_contract_gate.main,
    )
    if exit_code != 0:
        raise RuntimeError(
            "run_contract_gate --collect-only --print-digest exited "
            f"{exit_code} for repo {repo}: {stderr.strip()}"
        )
    return stdout.strip().splitlines()[-1].strip()


def _dispatch_prompt(slice_id: str) -> str:
    """Render a valid atdd_pure A_GREEN_ATS dispatch entering ``slice_id``."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        "\natdd_pure dispatch body.\n"
    )


@dataclass
class EntryGateOutcome:
    """The observable result of one carpaccio entry-gate evaluation."""

    verdict: EntryGateVerdict
    event: str | None


class BackfillEntryGateComposition:
    """Production-wired composition root for the auto-backfill entry gate slice.

    The driving port is ``intercept_atdd_pure_dispatch`` (the production U1
    PreToolUse intercept). The observable surface is the entry-gate verdict +
    emitted event, and the ``SliceCommitVerified`` ledger record the backfill
    appends (read back through the production ledger reader).
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._entering_slice = "slice-02"
        self._predecessor = "slice-01"
        self._ledger = AtCompletionLedger(self._feature_id, repo)

    # --- precondition substrate (real git + real ledger) --------------------

    def init_repo(self) -> None:
        """Initialise a real git repo with a first commit (HEAD resolvable)."""
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-m", "chore: seed")

    def enter_slice(self, slice_id: SliceId) -> None:
        """The dispatch under test enters ``slice_id`` (the successor)."""
        self.__setattr__("_entering_slice", str(slice_id))

    def predecessor_in_state(self, state: PredecessorLedgerState) -> None:
        """Seed the predecessor slice into ``state`` -- the backfill precondition.

        A real commit carrying the predecessor's Slice-Id AND a VERIFIABLE
        ``Gate-Scope:`` trailer (the E2 evidence the resolved backfill contract
        recomputes against) is written to disk in both states;
        ``COMMITTED_AND_RECORDED`` additionally appends the
        ``SliceCommitVerified`` ledger record (the idempotent case). The body
        delegates the commit + record seeding to the substrate helpers.
        """
        self._seed_predecessor_commit(GateScopeSeed.VERIFIABLE)
        self._seed_predecessor_record_if(state)

    def predecessor_with_bad_gate_scope(self, gate_scope: GateScopeSeed) -> None:
        """Seed a committed-but-unrecorded predecessor whose E2 evidence is bad.

        slice-02 fail-closed prep: a real commit carrying the predecessor's
        Slice-Id and its `.feature` AT file (so E1 completeness passes) but a
        ``Gate-Scope:`` trailer that is ABSENT (no trailer) or STALE (the
        ``0``*64 forged digest). The in-gate ``run_contract_gate
        --verify-gate-scope`` returns ``GateScopeUnverified`` for both, so the
        backfill refuses and appends NO ``SliceCommitVerified`` record. No
        ledger record is seeded (the unrecorded precondition). The body
        delegates the commit seeding to the parameterized substrate helper.
        """
        self._seed_predecessor_commit(gate_scope)

    def predecessor_not_committed(self) -> None:
        """Seed a predecessor with NO commit on disk carrying its Slice-Id.

        slice-02 fail-closed prep: the repo has only the seed commit; no commit
        carries a ``Slice-Id: slice-01`` trailer, so ``_predecessor_commit_sha``
        returns None, the backfill cannot run, and the block stands (genuine
        out-of-order). Nothing is committed and no ledger record is seeded -- a
        no-op precondition that records the absence as the SUT state.
        """
        return None

    def _seed_predecessor_commit(self, gate_scope: GateScopeSeed) -> None:
        """Write a real predecessor commit carrying a ``Gate-Scope:`` trailer.

        Two-step so the trailer digest is VERIFIABLE under the resolved backfill
        contract (E1-in-gate + E2-evidence-by-digest-VERIFICATION): first commit
        the predecessor's .feature so the test repo's contract-collection scope
        is fixed, THEN compute the digest via the production
        ``run_contract_gate --collect-only --print-digest`` against that exact
        repo state and amend it as ``Gate-Scope: <digest>``. The seeded digest
        is byte-identical to what the in-gate ``--verify-gate-scope`` recomputes
        (same code path, same repo state) -- so AT-1/AT-2's backfill->allow path
        GREENs once the production backfill branch exists, never blocking for a
        substrate (Gate-Scope-absent) reason. ``gate_scope`` is
        ``GateScopeSeed.VERIFIABLE`` for slice-01; the ABSENT / STALE variants
        feed slice-02's fail-closed rows (parameterizable seed helper).
        """
        feature_file = self._write_predecessor_feature_file()
        _git(self._repo, "add", str(feature_file.relative_to(self._repo)))
        _git(
            self._repo,
            "commit",
            "-m",
            f"feat: predecessor work\n\nSlice-Id: {self._predecessor}",
        )
        self._amend_gate_scope_trailer(gate_scope)

    def _write_predecessor_feature_file(self) -> Path:
        """Write the predecessor's .feature file under the feature acceptance dir."""
        slice_dir = (
            self._repo
            / "tests"
            / "des"
            / "acceptance"
            / self._feature_id
            / "acceptance"
        )
        slice_dir.mkdir(parents=True, exist_ok=True)
        feature_file = slice_dir / f"{self._predecessor}.feature"
        feature_file.write_text(
            f"@feature-{self._feature_id} @{self._predecessor}\n"
            f"Feature: predecessor slice\n  Scenario: x\n    Given y\n",
            encoding="utf-8",
        )
        return feature_file

    def _amend_gate_scope_trailer(self, gate_scope: GateScopeSeed) -> None:
        """Amend the predecessor HEAD commit with the seeded ``Gate-Scope:`` digest."""
        digest = self._gate_scope_digest_for(gate_scope)
        message = f"feat: predecessor work\n\nSlice-Id: {self._predecessor}" + (
            f"\nGate-Scope: {digest}" if digest is not None else ""
        )
        _git(self._repo, "commit", "--amend", "-m", message)

    def _gate_scope_digest_for(self, gate_scope: GateScopeSeed) -> str | None:
        """Resolve the digest to seed for ``gate_scope`` (None == omit trailer)."""
        digest_by_seed = {
            GateScopeSeed.VERIFIABLE: lambda: _fresh_gate_scope_digest(self._repo),
            GateScopeSeed.STALE: lambda: _STALE_DIGEST,
            GateScopeSeed.ABSENT: lambda: None,
        }
        return digest_by_seed[gate_scope]()

    def _seed_predecessor_record_if(self, state: PredecessorLedgerState) -> None:
        """Append the predecessor SliceCommitVerified record for the recorded state."""
        if state is PredecessorLedgerState.COMMITTED_AND_RECORDED:
            self._ledger.append_gate_event(
                event="SliceCommitVerified", slice_id=self._predecessor
            )

    # --- driving-port invocation: the real entry gate -----------------------

    def evaluate_entry_gate(self) -> EntryGateOutcome:
        """Evaluate the production U1 carpaccio intercept for the entering slice.

        The backfill (when it exists) runs the real verify-then-record CLI as a
        subprocess against the predecessor commit -- NO stub. The carpaccio
        runner is pre-cleared so the observable under test is purely the order
        gate's backfill-then-allow decision.
        """
        decision = intercept_atdd_pure_dispatch(
            prompt=_dispatch_prompt(self._entering_slice),
            feature_id=self._feature_id,
            project_root=self._repo,
            carpaccio_runner=lambda _f, _s: (
                0,
                json.dumps({"event": "SliceCleared", "slice_id": _s}),
            ),
            readiness_runner=lambda _f, _s: (0, ""),
        )
        return EntryGateOutcome(
            verdict=(
                EntryGateVerdict.BLOCKED
                if decision.is_block
                else EntryGateVerdict.ALLOWED
            ),
            event=decision.event,
        )

    # --- observable readback (ledger SSOT) ----------------------------------

    def predecessor_verified_record_count(self) -> int:
        """Count of SliceCommitVerified records for the predecessor in the ledger."""
        return sum(
            1
            for record in self._ledger.read_records()
            if record["event"] == "SliceCommitVerified"
            and record["slice_id"] == self._predecessor
        )

    def predecessor_is_verified(self) -> bool:
        """Whether the predecessor now carries a SliceCommitVerified record."""
        return self._predecessor in self._ledger.verified_slices()
