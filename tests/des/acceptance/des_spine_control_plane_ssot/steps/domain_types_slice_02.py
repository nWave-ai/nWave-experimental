"""Domain types for des-spine-control-plane-ssot slice-02 (committed-scope trailer).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-02 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-02 SUT = the `des run-contract-gate` CLI (the contract-gate driving port,
wired at `des.cli.__main__:69` kebab dispatcher). The slice-02 BEHAVIOR is the
AD-23 producer fix (ADR-CP-001 + ADR-CP-002):

  * On a GIT tree the default suite-run (producer) stamps a committed-scope digest
    (`ContractGateResult.gate_scope_digest`) the verifier re-derives BYTE-IDENTICALLY
    — a PORTABLE, verifiable trailer.
  * On a GIT-ABSENT tree the producer today SILENTLY falls back to a WORKING-tree
    digest (`run_contract_gate.py:645`, `digest = gate_scope_digest(repo)`) — a
    trailer no checkout can verify. Slice-02 REMOVES that fallback: the producer
    emits the LOUD `health.gate.committed-scope.indeterminate` marker and stamps
    NO digest, while the suite still RUNS (degrade-LOUD, never silent-pass).

The vocabulary deliberately MIRRORS the sibling `fix_gcommit_exit_gate_scoping`
slice-02 (which shipped the VERIFY-path committed-scope fix) — same
`COMMITTED_SCOPE_INDETERMINATE_EVENT`, same exit-code-exact verdict shape — but
lives independently so THIS feature's slice DELIVER+COMMITs without dragging the
sibling tree into pre-commit scope (atdd_pure per-slice isolation).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# The LOUD health event the producer must emit when it cannot pin the tree to a
# committed revision (git-absent / not-a-work-tree). Verbatim from the production
# constant `run_contract_gate._COMMITTED_SCOPE_INDETERMINATE_EVENT` (`:60`); the
# AT asserts against THIS structured surface, never a substring of the raw stream.
COMMITTED_SCOPE_INDETERMINATE_EVENT = "health.gate.committed-scope.indeterminate"

# The structured event the producer emits carrying its run verdict + (when a
# trailer is stampable) the gate-scope digest. On the GIT path this event carries
# a `gate_scope_digest`; on the GIT-ABSENT path (post-fix) NO digest is present —
# the trailer is the absence the AT asserts on.
CONTRACT_GATE_RESULT_EVENT = "ContractGateResult"


class RevisionControl(str, Enum):
    """Whether the contract tree the operator runs the gate against is under git.

    GIT_TREE is the common case: a real `.git/` work-tree whose HEAD is a
    committed contract suite. The producer derives the committed-scope digest of
    HEAD → a PORTABLE trailer (verifiable on any checkout of that commit).

    GIT_ABSENT is the target-machine-agnostic case (the generality/agnosticism
    mandate — Python is the ONLY runtime dependency; git is NOT): a plain
    directory carrying a contract suite but NO `.git/`. The producer cannot pin
    the tree to a committed revision, so (post-slice-02) it degrades LOUD —
    emits `committed-scope.indeterminate` and stamps NO digest — rather than
    silently fingerprinting the working tree. The `.value` strings are the
    human-readable Gherkin phrases the step decorators parse.

    GIT-FREE test mechanics (Mandate-13 invariant 5): GIT_ABSENT is constructed
    by simply NOT creating a `.git/` directory — never by shelling out to git to
    "remove" version control. GIT_TREE uses real git ONLY as a test-harness
    dependency inside the fixture builder, never as production code the AT imports.
    """

    GIT_TREE = "git work-tree"
    GIT_ABSENT = "tree that is not under revision control"


class ProducerOutcome(str, Enum):
    """How `des run-contract-gate` (default producer mode) resolves — EXIT-CODE-EXACT.

    * STAMPED_PORTABLE (exit 0, `ContractGateResult` WITH a `gate_scope_digest`)
      — a git tree: the suite ran AND a committed-scope trailer digest is stamped.
      The verdict slice-02 AT-01 requires on the git path.
    * RAN_NO_TRAILER (exit 0, `ContractGateResult` WITHOUT a `gate_scope_digest`
      + a LOUD `committed-scope.indeterminate` marker) — a git-absent tree: the
      suite still RAN (the producer's other job) but NO portable trailer could be
      honored, so none is stamped. The verdict slice-02 AT-02 requires on the
      git-absent path (degrade-LOUD, the AD-23 fix).
    * UNEXPECTED — any other exit code, so a verdict assertion never passes for
      the wrong reason (argparse error / crash / collection failure).
    """

    STAMPED_PORTABLE = "stamped portable trailer"  # exit 0 + digest present
    RAN_NO_TRAILER = "ran the suite, stamped no trailer"  # exit 0 + indeterminate
    UNEXPECTED = "unexpected"


class VerifyOutcome(str, Enum):
    """How `des run-contract-gate --verify-gate-scope` resolves — EXIT-CODE-EXACT.

    Used by AT-03 (the round-trip discriminator): a producer-stamped portable
    trailer, fed back to the verifier, must VERIFY — proving the stamped digest
    IS the committed-scope digest the verifier independently re-derives (the
    ADR-CP-001 producer==verifier contract), not merely a present-but-unverifiable
    token.

    * VERIFIED (exit 0, `GateScopeVerified`).
    * UNVERIFIED (exit 1, `GateScopeUnverified` — absent or mismatch).
    * REFUSED (exit 2, fail-closed committed-scope INDETERMINATE / MalformedInput).
    * UNEXPECTED — any other non-zero (crash / argparse error).
    """

    VERIFIED = "verified"  # exit 0
    UNVERIFIED = "unverified"  # exit 1
    REFUSED = "refused"  # exit 2
    UNEXPECTED = "unexpected"


# --- Frozen probe / outcome dataclasses ----------------------------------


@dataclass(frozen=True)
class ContractTreeProbe:
    """A handle on a synthetic contract tree the operator runs the gate against.

    Wraps a tmp_path-scoped directory carrying a minimal marker-tagged contract
    suite. `revision_control` records whether the tree is a real `.git/`
    work-tree (GIT_TREE) or a plain directory (GIT_ABSENT) — the seam the
    committed-scope port interrogates and the slice-02 fix degrades LOUD across.
    `pinned_commit` is the resolved HEAD SHA on a git tree (None for git-absent).
    """

    root_path: str  # the directory the gate's --repo points at
    revision_control: RevisionControl
    pinned_commit: str | None  # resolved HEAD SHA (None for GIT_ABSENT)


@dataclass(frozen=True)
class ProducerRun:
    """Observable outcome of one `des run-contract-gate` default-producer fire.

    Universe entries `assert_state_delta` tracks are built from THIS dataclass's
    port-exposed fields: `exit_code`, `outcome`, `stamped_digest`,
    `indeterminate_emitted`. Internal plumbing (Popen handle, env dict, raw
    stream bytes) is NEVER in the universe (Mandate 8 — port-exposed observables
    only).
    """

    exit_code: int
    stdout: str
    stderr: str
    outcome: ProducerOutcome
    stamped_digest: str | None  # the gate_scope_digest, when one was stamped
    indeterminate_emitted: bool  # the LOUD committed-scope.indeterminate marker


@dataclass(frozen=True)
class VerifyRun:
    """Observable outcome of one `des run-contract-gate --verify-gate-scope` fire."""

    exit_code: int
    stdout: str
    stderr: str
    outcome: VerifyOutcome


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

REVISION_CONTROL_BY_PHRASE: dict[str, RevisionControl] = {
    r.value: r for r in RevisionControl
}


__all__ = [
    "COMMITTED_SCOPE_INDETERMINATE_EVENT",
    "CONTRACT_GATE_RESULT_EVENT",
    "REVISION_CONTROL_BY_PHRASE",
    "ContractTreeProbe",
    "ProducerOutcome",
    "ProducerRun",
    "RevisionControl",
    "VerifyOutcome",
    "VerifyRun",
]
