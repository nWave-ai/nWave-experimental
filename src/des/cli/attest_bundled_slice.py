"""des-attest-bundled-slice -- attest a bundle-delivered carpaccio slice.

`F-ATTEST-BUNDLED-SLICE`. One sanctioned ``des attest-bundled-slice
--reason`` command, built on reverify's SHARED precondition/gate/record core
(``des.cli._reverify_core``), that attests a slice whose commit landed
BUNDLED with others -- the case the closure scorecard counts as partial.

slice-02 scope (feature-delta sec.5 / sec.11 row 2): this slice wired the
REUSED preconditions from the shared ``des.cli._reverify_core`` core into
``main()`` so ``des attest-bundled-slice`` fails closed -- BEFORE it ever
evaluates the bundle evidence -- on a non-ancestor, already-verified,
still-HEAD, or out-of-order slice. On any refusal the command emits
``SliceAttestRefused`` (exit 1) carrying the refusing precondition's diagnosis.

slice-03 scope (feature-delta sec.5 step 3 / sec.11 row 3): A2 -- the bundle
binding evidence -- REPLACES reverify's inherited strict P2 (trailer-name must
CONTAIN the slice) and P4 (in-commit-AT-presence refusal vocabulary), while the
REUSED P1/P3/P5/P6 stay intact. A2 is the conjunction of three evidence checks,
each carrying its OWN attest-specific diagnosis (NOT the inherited reverify
P2/P4 text):

  * A2.a -- real-AT presence: the slice's ``@slice-NN`` ``.feature`` AT is
            present in the bundle commit's tree OR recoverable from ``commit~1``
            (reverify's P4 evidence helpers ``_in_commit_at_presence`` +
            ``_tracked_before_at_presence`` reused VERBATIM, only the refusal
            diagnosis is A2-specific). Absent -> refused.
  * A2.b -- TWO-BRANCH carpaccio/wave-trailer PRESENCE:
                ``bool(extract_slice_ids(msg)) OR _has_step_id_line(msg)``.
            Branch 1 = a ``Slice-Id:``/``Step-Id:`` trailer NAMING any slice-NN
            (PRESENCE, not slice-membership -- so a bundle trailered for a
            DIFFERENT slice still passes); branch 2 = a raw ``Step-Id:`` line
            regardless of its value (the ``Step-Id: <feature>-design`` shape
            whose ``extract_slice_ids`` returns []). Neither -> refused.
  * A2.c -- no deferred scenario: the matched ``@slice-NN`` ``.feature`` is
            raw-line scanned for ``@skip``/``@xfail``/``@wip``; any tag ->
            refused (a deferred scenario must not be attested as if exercised).

When A2 clears, the run proceeds to the ``BundledSliceAttestPreconditionsCleared``
placeholder -- the gate composition (E1+E2) + ledger record land in slice-04.

stdlib-only (no `import yaml`) per the DES-bundle contract, mirroring the
shared core it imports. Single-line JSON events to stdout follow the gate
CLIs' ``_emit`` convention (re-used from the shared core).

Exit codes:
    0 = every reused precondition AND the A2 evidence check cleared -- the run
        proceeds past them (the gate/ledger flow lands in slice-04).
    1 = a reused precondition (P1/P3/P5/P6) OR an A2 evidence check
        (A2.a/A2.b/A2.c) refused the slice -- ``SliceAttestRefused``. No
        ledger/audit write (refusals run before any gate).
    2 = malformed input (bad ``--slice-id``/``--repo``/``--bundle-commit``) OR
        an argparse usage error (e.g. no ``--reason``). The floor is
        untouched, no ledger/audit write.

Reference: docs/feature/f-attest-bundled-slice/feature-delta.md sec.3 + sec.4
+ sec.5 + ADR-ABS-001 sec.4.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Source the attestation machinery from the SHARED reverify core -- the
# no-parallel-attestation-path guarantee (f-attest-bundled-slice slice-01,
# F-D-09: des.* + stdlib only). slice-01 wired the import seam; slice-02
# composes the REUSED preconditions (``_preconditions``); slice-03 reuses the
# P4 evidence helpers (``_in_commit_at_presence``/``_tracked_before_at_presence``)
# + the git/feature-scan primitives for A2.a/A2.c -- no re-impl.
from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.cli._reverify_core import (
    _compose_gates,
    _emit,
    _git,
    _in_commit_at_presence,
    _malformed_input,
    _orphan_state,
    _path_in_commit_tree,
    _preconditions,
    _predecessor_verified,
    _record_outcome,
    _refused,
)
from des.cli.verify_slice_commit_completeness import (
    extract_slice_ids,
    files_in_commit,
)


# The reverify-vocabulary event a precondition refusal carries (the shared
# ``_refused`` stamps ``SliceReverifyRefused``); slice-02 rebrands it to the
# attest vocabulary the AT drives on, preserving the reused diagnosis ``error``.
_REVERIFY_REFUSED_EVENT = "SliceReverifyRefused"
_ATTEST_REFUSED_EVENT = "SliceAttestRefused"

# The inherited reverify P2 (trailer-name) + P4 (in-commit-AT-presence) refusal
# diagnosis fragments. slice-03 REPLACES P2/P4 with A2, so a refusal carrying
# either fragment from the reused ``_preconditions`` group is the inherited
# precondition firing -- it is DROPPED and the A2 evidence check (which carries
# its OWN diagnosis) decides the trailer/AT-presence grounds instead. The
# remaining P1/P3/P5/P6 refusals pass through unchanged. These fragments are the
# stable contract text the 40 reverify ATs pin (``_reverify_core`` lines 159-162
# for P2, 285-289 for P4) -- the same fragments the slice-03 oracle asserts
# ABSENT from an A2 refusal.
_REVERIFY_P2_DIAGNOSIS = "is not in the commit's trailer set"
_REVERIFY_P4_DIAGNOSIS = "the slice's acceptance tests must live in the commit itself"

# Deferred-scenario tags A2.c refuses (the H2 anti-theater hole): a scenario
# carrying any of these is not genuinely exercised, so it must not be attested.
_DEFERRED_TAG_RE = re.compile(r"@(?:skip|xfail|wip)\b")


def _has_deferred_tag(feature_content: str) -> bool:
    """True iff a Gherkin TAG line carries ``@skip``/``@xfail``/``@wip`` (A2.c).

    Scans ONLY tag lines (a stripped line starting with ``@``). A deferred tag
    mentioned inside a ``#`` comment or step prose -- e.g. the common
    "Active-RED (atdd_pure / ADR-025, NOT @skip)" explanatory comment -- is NOT
    a deferred scenario and must never false-refuse a genuinely-exercised slice
    (found by dogfooding the primitive on f-deliver-wave-migration slice-02).
    """
    return any(
        line.lstrip().startswith("@") and _DEFERRED_TAG_RE.search(line)
        for line in feature_content.splitlines()
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des attest-bundled-slice",
        description="Attest a bundle-delivered carpaccio slice (human-GO required).",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the git repository carrying the bundled slice.",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="The feature whose bundled slice is being attested.",
    )
    parser.add_argument(
        "--slice-id",
        required=True,
        help="The bundled slice to attest (slice-NN).",
    )
    parser.add_argument(
        "--bundle-commit",
        required=True,
        help="The commit-ish carrying the bundled slice (e.g. HEAD).",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="The human-authored GO reason justifying the bundled-slice attestation.",
    )
    return parser


def _attest_refused(refusal: dict[str, str]) -> dict[str, str]:
    """Rebrand a reused precondition refusal to the attest vocabulary.

    The shared ``_preconditions`` returns a ``SliceReverifyRefused`` payload
    (or a ``LedgerIntegrityViolation`` payload for a corrupt ledger). The
    refusing-precondition diagnosis lives in the reused ``error`` text, which
    is preserved verbatim -- only the reverify-vocabulary ``event`` is
    rebranded to ``SliceAttestRefused`` so the attest CLI speaks its own
    terminal event name. A non-``SliceReverifyRefused`` payload (the inherited
    ``LedgerIntegrityViolation`` structural surfacing) is passed through
    unchanged.
    """
    if refusal.get("event") != _REVERIFY_REFUSED_EVENT:
        return refusal
    return {**refusal, "event": _ATTEST_REFUSED_EVENT}


def _is_replaced_precondition(refusal: dict[str, str]) -> bool:
    """True iff ``refusal`` is the inherited reverify P2 or P4 that A2 replaces.

    slice-03 REPLACES reverify's strict P2 (trailer-name must CONTAIN the slice)
    and P4 (in-commit-AT-presence) with the A2 evidence check. A refusal from the
    reused ``_preconditions`` group whose ``error`` carries the P2 or P4 contract
    fragment is one of those two replaced grounds -- it is dropped so the A2
    check (which carries its own diagnosis and PRESENCE-not-membership trailer
    semantics) decides those grounds instead. Every other precondition
    (P1/P3/P5/P6) passes through unchanged.
    """
    error = refusal.get("error", "")
    return _REVERIFY_P2_DIAGNOSIS in error or _REVERIFY_P4_DIAGNOSIS in error


def _surviving_precondition(
    repo: Path,
    feature_id: str,
    slice_id: str,
    commit: str,
    refusal: dict[str, str] | None,
) -> dict[str, str] | None:
    """Re-run P3/P5/P6 when a dropped P2/P4 short-circuited the reused group.

    The shared ``_preconditions`` runs P1->P2->P3->P4->P5->P6 in order and
    returns on the FIRST refusal. When the refusal it returned was P2 or P4
    (which A2 replaces, so we drop it), every precondition AFTER it never ran:
    a dropped P2 skips P3/P5/P6; a dropped P4 skips P5/P6. P1 always runs before
    P2, so it is already enforced. This helper re-runs the skipped P3 (already-
    verified / ledger integrity), P5 (orphan/buried), and P6 (predecessor
    verified) via the REUSED ``_reverify_core`` helpers so the attest path keeps
    the same fail-closed P1/P3/P5/P6 guarantee reverify has -- only P2/P4 are
    replaced by A2. Returns None when no refusal was dropped (the reused group
    already ran them) or when all three re-checks clear.
    """
    if refusal is None:
        return None
    # P3 -- not-already-verified; the verified map also feeds P6 (one read).
    try:
        verified = AtCompletionLedger(feature_id, repo).verified_slices()
    except LedgerIntegrityViolation as exc:
        return {
            "event": "LedgerIntegrityViolation",
            "detail": exc.detail,
            "error": f"AT-completion ledger is corrupt ({exc.detail}): {exc}",
        }
    if slice_id in verified:
        return _refused(
            f"--slice-id {slice_id!r} is already verified "
            "(carries a SliceCommitVerified ledger record); "
            "a repeat attestation is an idempotent no-op"
        )
    # P5 -- the commit must be a genuinely-buried (orphaned) slice.
    orphan_refusal = _orphan_state(repo, commit)
    if orphan_refusal is not None:
        return orphan_refusal
    # P6 -- the immediate predecessor slice must already be verified.
    return _predecessor_verified(slice_id, verified)


def _has_step_id_line(message: str) -> bool:
    """True iff ``message`` carries a raw ``Step-Id:`` line (any value).

    A2.b branch 2: a bundle commit trailered ``Step-Id: <feature>-design``
    (whose ``extract_slice_ids`` returns [] because the value is a feature-id,
    not a slice-NN) still binds to a recognised wave step -- the f-design
    531cfb59a shape. The presence of the raw line, regardless of its value, is
    the branch-2 evidence; A2.b branch 1 (``bool(extract_slice_ids)``) covers a
    slice-NN-naming trailer.
    """
    return any(line.strip().startswith("Step-Id:") for line in message.splitlines())


def _matched_slice_feature(repo: Path, slice_id: str, commit: str) -> str | None:
    """Return the ``@slice-NN`` ``.feature`` content owned by ``slice_id``, else None.

    The artifact A2.a binds on and A2.c scans. Reads the commit tree first (a
    ``.feature`` touched by ``commit`` and present in its tree, carrying the
    ``@slice_id`` tag), then falls back to ``commit~1`` (the carpaccio-split
    orphan recoverable from the parent, unmodified by ``commit``) -- mirroring
    the same two-source recovery the reused ``_in_commit_at_presence`` +
    ``_tracked_before_at_presence`` accept on. Returns the first matching blob's
    content so A2.c can raw-line scan the very ``.feature`` A2.a matched.
    """
    slice_tag = re.compile(rf"@{re.escape(slice_id)}\b")
    for rel_path in sorted(files_in_commit(repo, commit)):
        if not rel_path.endswith(".feature"):
            continue
        if not _path_in_commit_tree(repo, commit, rel_path):
            continue
        content = _git(repo, "show", f"{commit}:{rel_path}")
        if slice_tag.search(content):
            return content
    try:
        parent = _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}~1").strip()
    except Exception:
        parent = ""
    if not parent:
        return None
    touched = files_in_commit(repo, commit)
    tree = _git(repo, "ls-tree", "-r", "--name-only", parent)
    for rel_path in sorted(line for line in tree.splitlines() if line):
        if not rel_path.endswith(".feature") or rel_path in touched:
            continue
        content = _git(repo, "show", f"{parent}:{rel_path}")
        if slice_tag.search(content):
            return content
    return None


def _a2_bundle_evidence(
    repo: Path, slice_id: str, commit: str
) -> dict[str, str] | None:
    """A2: the bundle-binding evidence that replaces reverify's P2/P4.

    Runs A2.a (real-AT presence), A2.b (two-branch trailer presence), A2.c
    (no deferred scenario), in order; returns the first A2-specific refusal
    payload (``SliceAttestRefused`` vocabulary, its OWN diagnosis) or None when
    all three clear. None of these refusals reuse the inherited reverify P2/P4
    diagnosis text.
    """
    # A2.a -- the slice's real @slice-NN .feature AT must be present (in the
    # commit tree or recoverable from commit~1). The P4 evidence helpers are
    # reused verbatim; only the refusal diagnosis is A2-specific.
    at_present = _in_commit_at_presence(repo, slice_id, commit) is None
    if not at_present:
        return _attest_refusal(
            f"--bundle-commit {commit!r} binds no @{slice_id} .feature acceptance "
            f"evidence for {slice_id!r}; the bundled slice cannot be attested "
            "without the real acceptance test it claims to deliver (A2.a)"
        )

    # A2.b -- PRESENCE of a recognised carpaccio/wave trailer, by either branch:
    # branch 1 = a Slice-Id:/Step-Id: trailer naming any slice-NN (bool of the
    # set, NOT slice-membership); branch 2 = a raw Step-Id: line of any value.
    message = _git(repo, "log", "-1", "--format=%B", commit)
    if not (bool(extract_slice_ids(message)) or _has_step_id_line(message)):
        return _attest_refusal(
            f"--bundle-commit {commit!r} carries no recognised carpaccio or wave "
            "trailer (neither a Slice-Id:/Step-Id: trailer naming a slice nor a "
            "raw Step-Id: line); an arbitrary commit cannot be attested as a "
            "bundled slice (A2.b)"
        )

    # A2.c -- the matched @slice-NN .feature must carry no deferred scenario.
    feature_content = _matched_slice_feature(repo, slice_id, commit)
    if feature_content is not None and _has_deferred_tag(feature_content):
        return _attest_refusal(
            f"the @{slice_id} acceptance test carries a deferred scenario "
            "(@skip/@xfail/@wip); a deferred scenario is not genuinely exercised "
            "and must not be attested as if it were (A2.c)"
        )

    return None


def _attest_refusal(error: str) -> dict[str, str]:
    """An A2 refusal payload in the attest vocabulary with its OWN diagnosis.

    Mirrors the shared ``_refused`` shape but stamps the attest event name
    directly (A2 is attest-native -- it has no reverify origin to rebrand).
    """
    return {**_refused(error), "event": _ATTEST_REFUSED_EVENT}


def main(argv: list[str] | None = None) -> int:
    """Attest a bundled carpaccio slice (slice-03: A2 replaces P2/P4).

    The REUSED preconditions P1/P3/P5/P6 run first (via the shared
    ``_preconditions`` helper). Reverify's strict P2 (trailer-name) and P4
    (in-commit-AT-presence) refusals from that group are DROPPED -- A2 replaces
    those two grounds with the bundle-binding evidence (A2.a real-AT presence,
    A2.b two-branch trailer PRESENCE, A2.c no deferred scenario), which carries
    its OWN attest-specific diagnosis. A malformed input exits 2; any surviving
    precondition refusal OR any A2 refusal exits 1 with ``SliceAttestRefused``.

    When P1/P3/P5/P6 and A2 all clear, the run composes the two REAL gates via
    the REUSED ``_compose_gates`` (E1 ``check_slice_at_completeness`` + E2
    ``run_contract_gate`` -- run for real against the commit, never a flag) and
    records the outcome:

      * BLOCK -- a gate (E1 or E2) failed: append one ``SliceCommitBlocked`` and
        emit ``SliceAttestBlocked`` naming the failing gate (exit 1), via the
        REUSED ``_record_outcome`` -- the exact mirror of reverify's gate-fail
        path. NO ``SliceCommitVerified`` is appended (the anti-theater guarantee:
        a slice whose acceptance tests do not pass is never attested).
      * SUCCESS -- both gates passed: append a genuine origin-blind
        ``SliceCommitVerified`` (the scorecard-counted record) THEN the adjacent
        ``SliceAttestedFromBundle`` provenance record carrying the bundle_commit +
        the human ``--reason`` (I-6 loud audit trail), and emit
        ``SliceAttestedFromBundle`` (exit 0).
    """
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

    malformed = _malformed_input(repo, args.slice_id, args.bundle_commit)
    if malformed is not None:
        _emit(malformed)
        return 2

    refusal = _preconditions(repo, args.feature_id, args.slice_id, args.bundle_commit)
    if refusal is not None and not _is_replaced_precondition(refusal):
        # A surviving P1/P3/P5/P6 (or LedgerIntegrityViolation) refusal: keep it.
        _emit(_attest_refused(refusal))
        return 1

    # P2/P4 (if they fired) are dropped: A2 decides the trailer + AT-presence
    # grounds with its own evidence + diagnosis. Re-run P5/P6 explicitly, since
    # a dropped P2 may have short-circuited the reused group BEFORE P5/P6 ran.
    surviving = _surviving_precondition(
        repo, args.feature_id, args.slice_id, args.bundle_commit, refusal
    )
    if surviving is not None:
        _emit(_attest_refused(surviving))
        return 1

    a2_refusal = _a2_bundle_evidence(repo, args.slice_id, args.bundle_commit)
    if a2_refusal is not None:
        _emit(a2_refusal)
        return 1

    # P1/P3/P5/P6 and A2 all cleared: run the two REAL gates (E1 + E2) for real
    # against the commit via the REUSED ``_compose_gates`` -- never a flag, never
    # a stub (invariant I-2).
    failing_gate = _compose_gates(
        repo, args.bundle_commit, args.feature_id, args.slice_id
    )
    if failing_gate is not None:
        # BLOCK path: a gate failed. Append one genuine ``SliceCommitBlocked``
        # ledger record the identical way reverify's gate-fail path does, then
        # surface ``SliceAttestBlocked`` naming the failing gate. NO
        # ``SliceCommitVerified`` is appended -- the anti-theater guarantee that a
        # slice whose acceptance tests do not pass is never attested.
        _record_outcome(
            args.feature_id,
            repo,
            args.slice_id,
            ledger_events=("SliceCommitBlocked",),
            payload={
                "event": "SliceAttestBlocked",
                "slice_id": args.slice_id,
                "failing_gate": failing_gate,
                "error": (
                    f"gate {failing_gate} did not pass for {args.bundle_commit!r}; "
                    "the bundled slice is blocked and not attested"
                ),
            },
        )
        return 1

    # SUCCESS path: both gates passed. Append the origin-blind, scorecard-counted
    # ``SliceCommitVerified`` record FIRST (byte-shape-identical to a U2-/reverify-
    # minted one), THEN the adjacent ``SliceAttestedFromBundle`` provenance record
    # carrying the bundle_commit + the human ``--reason`` (I-6). Both writes ride
    # the ledger's M7 critical section, so the provenance fields are tamper-evident
    # and the writer stamps its own timestamp. ``verified_slices()`` keys only on
    # ``SliceCommitVerified``, so the second record never perturbs M8 ordering.
    ledger = AtCompletionLedger(args.feature_id, repo)
    ledger.append_gate_event(event="SliceCommitVerified", slice_id=args.slice_id)
    ledger.append_attested_from_bundle(args.slice_id, args.bundle_commit, args.reason)
    _emit(
        {
            "event": "SliceAttestedFromBundle",
            "slice_id": args.slice_id,
            "bundle_commit": args.bundle_commit,
            "reason": args.reason,
        }
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
