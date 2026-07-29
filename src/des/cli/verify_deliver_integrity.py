"""CLI: Verify deliver integrity before finalize.

Usage:
    des verify-integrity <project-dir> [--feature-id <id>]

The DELIVER spine is atdd_pure: roadmap-free and execution-log-free. The
verifier validates the AT-completion ledger for the feature under finalize.
A missing ledger is an integrity violation (exit 1), never a crash; a leftover
roadmap.json is a WARNING. The feature-end cycle records (batch refactor + deep
review + the gate heartbeats) must all be present before a feature is closeable.

(f-finalize-verify-single-spine slice-01: the classic `workflow.mode == classic`
roadmap/execution-log finalize leg, the `resolve_workflow_mode` dispatch, and the
`--roadmap-only` mode were removed -- `_verify_atdd_pure` is now the whole body of
`main()`. The `des verify-integrity` subcommand and the 0/1/2 exit-code
contract are preserved byte-for-byte.)

Exit codes:
    0 = feature verified (ledger present, feature-end cycle complete)
    1 = integrity violation (missing ledger / incomplete feature-end cycle)
    2 = usage error (no project_dir / --repo target)
    4 = cannot-evaluate (git absent / unreconciled bypass debt -- LOUD INDETERMINATE)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from des.adapters.driven.git.git_commit_trailer_read_adapter import (
    GitCommitTrailerReadAdapter,
)
from des.application.feature_end_na_marker_reconciliation import (
    feature_end_na_marker_reconciles,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.repo_path_resolver import feature_delta_path
from des.ports.driven_ports.commit_trailer_read_port import (
    CommitTrailerReadPort,
    Indeterminate,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-integrity",
        description=(
            "Verify deliver integrity for a feature before finalize. The "
            "atdd_pure spine is roadmap-free: the verifier validates the "
            "AT-completion ledger and the feature-end cycle records."
        ),
        epilog=(
            "Exit codes: 0 = feature verified | 1 = integrity violation | "
            "2 = usage error | 4 = cannot-evaluate (LOUD INDETERMINATE)."
        ),
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "Path to the feature project root holding the .nwave/ ledger "
            "substrate (atdd_pure spine is roadmap-free)."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo",
        type=Path,
        default=None,
        help=(
            "Path to the project root holding the .nwave/ ledger substrate. An "
            "alias for the positional project_dir used by the consolidated "
            "feature-end-cycle driving surface (atdd_pure spine is roadmap-free, "
            "so the project root IS the verification target)."
        ),
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help=(
            "The feature id under verification. In atdd_pure mode the verifier "
            "targets exactly `{feature-id}.jsonl` in the AT-completion telemetry "
            "directory. When omitted, the feature id is derived from the "
            "deliver directory layout (docs/feature/<id>/deliver/). A multi-"
            "feature telemetry directory MUST be disambiguated by this flag -- "
            "the verifier never falls through to an unrelated feature's ledger."
        ),
    )
    return parser


def _derive_feature_id(project_dir: Path) -> str | None:
    """Derive the feature id from the deliver-directory layout.

    The DELIVER spine runs against `docs/feature/<feature-id>/deliver/`, so the
    feature id is the parent directory name when `project_dir` is a `deliver`
    directory. Returns None when the layout does not match -- the caller then
    requires an explicit `--feature-id`.
    """
    resolved = project_dir.resolve()
    if resolved.name == "deliver":
        return resolved.parent.name
    return None


def _find_at_completion_ledger(
    project_dir: Path,
    feature_id: str | None = None,
    *,
    explicit: bool = False,
) -> Path | None:
    """Locate the AT-completion ledger for an atdd_pure feature (ADR-028 D3).

    The ledger is a single per-feature append-only JSONL file at
    `{project_dir}/.nwave/telemetry/atdd-pure/{feature_id}.jsonl`.

    F-DELIVER-INTEGRITY-LEDGER-TARGETING: the verifier no longer
    glob-and-picks the alphabetically-first file -- in a multi-feature
    telemetry directory that selected an unrelated already-shipped feature's
    ledger, yielding a false-PASS. Resolution rules:

    - `explicit=True` (operator passed `--feature-id`): target
      `{feature_id}.jsonl` EXACTLY. An absent named ledger returns None -- a
      verification failure, never a fall-through to another file.
    - `explicit=False` with a derived `feature_id`: prefer the derived
      ledger; if it is absent, fall back to the single-ledger rule below so
      callers whose project layout does not encode the feature id still work.
    - no usable `feature_id`: return the sole `*.jsonl` ledger if exactly one
      exists; a multi-feature directory returns None so the caller emits a
      disambiguation diagnostic (the false-PASS guard).

    Returns the ledger path, or None when no unambiguous ledger is found.
    """
    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    if not ledger_dir.is_dir():
        return None
    if feature_id is not None:
        named = ledger_dir / f"{feature_id}.jsonl"
        if named.is_file():
            return named
        if explicit:
            return None
    ledgers = sorted(ledger_dir.glob("*.jsonl"))
    return ledgers[0] if len(ledgers) == 1 else None


# A `Slice-Id:`/`Step-Id:` commit trailer carrying a `slice-NN` identifier.
_SLICE_ID_TRAILER_RE = re.compile(r"^(?:Slice-Id|Step-Id):\s*(slice-\d+)\s*$")

# The single-line JSON `event` marker the LOUD cannot-evaluate verdict carries on
# stdout when the commit-trailer history is unreadable (git absent / not a
# work-tree). Distinct from `FeatureUnreconciled` (exit 1, history WAS read).
INDETERMINATE_EVENT_NAME = "FeatureIndeterminate"

# The distinct cannot-evaluate non-pass exit code (D1): NOT one of the verifier's
# existing 0/1/2 codes, so it is unambiguously distinct from the exit-1
# FeatureUnreconciled verdict. Mirrors `gate_outcome.py:132 GateOutcome.indeterminate`.
CANNOT_EVALUATE_EXIT = 4


def _shipped_slices(
    project_dir: Path, trailer_port: CommitTrailerReadPort
) -> frozenset[str] | Indeterminate:
    """The set of `slice-NN` carried by `Slice-Id:` trailers in the git history.

    DDD-10: a slice is "shipped" when at least one commit's message carries its
    `Slice-Id:`/`Step-Id:` trailer. Reads the whole history through the
    `CommitTrailerReadPort` (git lives behind the adapter; this gate logic is
    Python + filesystem only -- AD-21/24 genericita mandate).

    When git is absent / `project_dir` is not a work-tree the port returns the
    LOUD `Indeterminate`, which this function PROPAGATES unchanged -- the
    done-gate then refuses with the cannot-evaluate verdict (exit 4) instead of
    silently fabricating an empty set that masks git-absence as "nothing
    shipped" (the AD-21/24 silent-fabrication this slice removes).
    """
    result = trailer_port.commit_messages(project_dir)
    if isinstance(result, Indeterminate):
        return result
    shipped: set[str] = set()
    for message in result.messages:
        for line in message.splitlines():
            match = _SLICE_ID_TRAILER_RE.match(line.strip())
            if match:
                shipped.add(match.group(1))
    return frozenset(shipped)


def _foreign_owned_slices(project_dir: Path, *, own_ledger: Path) -> frozenset[str]:
    """Slices POSITIVELY owned by OTHER features' AT-completion ledgers.

    F-DELIVER-INTEGRITY-LEDGER-TARGETING: a co-resident feature's slice lands
    in the shared git history (so it is in `shipped`) but is recorded in that
    other feature's ledger. Subtracting this set from `shipped - verified`
    removes the cross-feature false positive without dropping an own-feature
    slice that no other feature owns.

    Scans `.nwave/telemetry/atdd-pure/*.jsonl` EXCLUDING `own_ledger`; for each
    other ledger the owned set is `review_verdict_slices() | verified_slices()`
    (a slice reviewed OR verified by that feature). The union over every other
    ledger is foreign-owned. Computed from ledger FILES (filesystem), git-free.
    """
    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    own = own_ledger.resolve()
    foreign: set[str] = set()
    for ledger_file in sorted(ledger_dir.glob("*.jsonl")):
        if ledger_file.resolve() == own:
            continue
        other = AtCompletionLedger(ledger_file.stem, project_dir)
        try:
            foreign |= other.review_verdict_slices() | other.verified_slices()
        except LedgerIntegrityViolation:
            # A corrupt foreign ledger cannot positively own a slice -- treat
            # it as owning nothing rather than crashing this feature's verdict.
            continue
    return frozenset(foreign)


def _declared_slice_plan_slice_ids(project_dir: Path, feature_id: str) -> list[str]:
    """Every slice-id DECLARED in the feature's Slice-Plan (the `Slice` column).

    The feature's OWN slices, read from its feature-delta -- unlike the git-history
    `Slice-Id:` trailer set (`_shipped_slices`), which is NOT feature-tagged and
    over-counts across co-resident features (slice-ids are not globally unique).
    Used to report `reconciled_slices` accurately for a slice-plan feature when the
    verdict is FeatureReconciled (all declared slices are then reconciled), closing
    the phantom over-count F-VERIFY-INTEGRITY-RECONCILED-SLICES-OVERCOUNTS-PHANTOM.
    Empty when no feature-delta / Slice-Plan is present.
    """
    from des.cli.validate_feature_delta import (
        _SLICE_PLAN_HEADING_RE,
        SLICE_PLAN_COLUMNS,
        _is_separator_row,
        _parse_table_cells,
        _plan_table_rows,
    )

    delta_path = feature_delta_path(project_dir, feature_id)
    if not delta_path.is_file():
        return []
    rows = _plan_table_rows(
        delta_path.read_text(encoding="utf-8"), _SLICE_PLAN_HEADING_RE
    )
    if not rows:
        return []
    slice_index = SLICE_PLAN_COLUMNS.index("Slice")
    ids: list[str] = []
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        cells = _parse_table_cells(row)
        if len(cells) <= slice_index:
            continue
        sid = cells[slice_index].strip()
        if sid:
            ids.append(sid)
    return ids


def _undelivered_slice_plan_slices(project_dir: Path, feature_id: str) -> list[str]:
    """Planned Slice-Plan slices with NO delivered acceptance-test file (DDD-5).

    Un-gameable, git-free completeness oracle. Closes the truncated-feature hole
    the 2026-06-04 dogfood exposed: a feature whose Slice-Plan DECLARES a slice
    that was NEVER delivered must NOT be declarable done, even though every
    committed slice reconciled.

    The delivered-ness of a planned slice is DERIVED from a REAL artefact -- the
    existence of a ``@slice-NN``-tagged ``.feature`` file under the feature's
    ``@feature-{id}`` tag (``feature_files_for_slice``, a pure working-tree walk:
    no git, no manual ``Status`` text column an author could flip to dodge the
    gate). This is the no-silent-pass / un-gameable measure (Ale 2026-06-15,
    "confermo: ledger-derived not the gameable status text"):

      * a planned slice with >=1 such file WAS delivered -- its acceptance tests
        exist on disk -- even when several plan-slices were BUNDLED into one
        commit (the ``--no-verify`` era left features whose 2-3 plan-slices all
        shipped under a single ``Slice-Id: slice-01`` trailer; their slice-02/03
        ``.feature`` files exist, so they are correctly NOT flagged truncated).
      * a planned slice with NO such file was declared-but-never-delivered ->
        TRUNCATED (the 2026-06-04 hole: a plan row with no acceptance-test file).

    The PLANNED slice-ids are read via the canonical Slice-Plan parser from
    ``des.cli.validate_feature_delta`` (the `Slice` column); the `Status` text
    column is deliberately NOT read. An absent feature-delta / Slice-Plan /
    header-only plan yields an empty list -- the assertion never manufactures a
    refusal where no plan declares work.
    """
    from des.application.slice_at_completeness import feature_files_for_slice
    from des.cli.validate_feature_delta import (
        _SLICE_PLAN_HEADING_RE,
        SLICE_PLAN_COLUMNS,
        _is_separator_row,
        _parse_table_cells,
        _plan_table_rows,
    )

    delta_path = feature_delta_path(project_dir, feature_id)
    if not delta_path.is_file():
        return []
    rows = _plan_table_rows(
        delta_path.read_text(encoding="utf-8"), _SLICE_PLAN_HEADING_RE
    )
    if not rows:
        return []
    slice_index = SLICE_PLAN_COLUMNS.index("Slice")
    prose_delivered = _prose_delivered_slices(project_dir, feature_id)
    commit_verified_delivered = _slice_commit_verified_slices(project_dir, feature_id)
    undelivered: list[str] = []
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        cells = _parse_table_cells(row)
        if len(cells) <= slice_index:
            continue
        slice_id = cells[slice_index].strip()
        if not slice_id:
            continue
        # A PROSE slice (Decision-4 NON-code / prose surfaces, "NO ATs authored
        # for prose") is delivered WITHOUT a `.feature` file -- its delivery is
        # attested by a `SliceProseDelivered` ledger record (attested=true), the
        # un-gameable spine-emitted analogue of the `.feature`-presence oracle for
        # code slices. Exempting it is NOT the gameable `Status` text dodge: the
        # exemption keys on a real, hash-stamped ledger attestation, not a
        # hand-editable column. Closes the verify-integrity false-positive the
        # adversarial swarm 2026-06-29 exposed (a prose slice was wrongly flagged
        # TRUNCATED, theater-rejecting an honestly-delivered prose slice).
        if slice_id in prose_delivered:
            continue
        # THIRD delivery-recognition form (feature-end-attests-pytest-regression):
        # a slice carrying a `SliceCommitVerified` ledger record is DELIVERED,
        # regardless of `at_kind` -- the spine emits it ONLY after the slice's
        # E1+E2 commit gate passed (the regression test existed AND passed on the
        # committed tree). Additive: gherkin + prose recognition above are
        # unchanged. Recognizes a pytest-regression feature (no .feature file, no
        # SliceProseDelivered) so it can reach FeatureEnd instead of being
        # permanently TRUNCATED.
        if slice_id in commit_verified_delivered:
            continue
        if not feature_files_for_slice(project_dir, slice_id, feature_id):
            undelivered.append(slice_id)
    return undelivered


def _prose_delivered_slices(project_dir: Path, feature_id: str) -> frozenset[str]:
    """Slice-ids carrying an attested ``SliceProseDelivered`` ledger record.

    A prose slice (no acceptance-test ``.feature`` by design) is delivered when
    the spine emits a ``SliceProseDelivered`` record with ``attested: true`` for
    it. Un-gameable: the record is hash-stamped + reviewer-attested, NOT the
    hand-editable ``Status`` column. Returns the empty set when no ledger exists.
    """
    ledger = project_dir / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    if not ledger.is_file():
        return frozenset()
    delivered: set[str] = set()
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if '"SliceProseDelivered"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if (
                rec.get("event") == "SliceProseDelivered"
                and rec.get("attested") is True
                and isinstance(rec.get("slice_id"), str)
            ):
                delivered.add(rec["slice_id"])
    except OSError:
        return frozenset()
    return frozenset(delivered)


def _slice_commit_verified_slices(project_dir: Path, feature_id: str) -> frozenset[str]:
    """Slice-ids carrying a `SliceCommitVerified` ledger record (ANY at_kind).

    THIRD delivery-recognition form (feature-end-attests-pytest-regression):
    `SliceCommitVerified` IS the un-gameable delivery attestation -- the spine
    emits it ONLY after the slice's E1+E2 commit gate passed (the regression
    test existed AND passed on the committed tree). Recognized regardless of
    `at_kind` -- today's records carry no `at_kind` field at all (`args.at_kind`
    is read for gate-selection but never persisted), so an at_kind-specific
    filter would fail to recognize every already-committed record. Modelled on
    `_prose_delivered_slices`'s raw-JSONL ledger scan. Returns the empty set
    when no ledger exists.
    """
    ledger = project_dir / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    if not ledger.is_file():
        return frozenset()
    delivered: set[str] = set()
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if '"SliceCommitVerified"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("event") == "SliceCommitVerified" and isinstance(
                rec.get("slice_id"), str
            ):
                delivered.add(rec["slice_id"])
    except OSError:
        return frozenset()
    return frozenset(delivered)


_COMMON_AUDIT_LOG_REL = Path(".nwave") / "audit" / "atdd-pure-events.jsonl"


def _verify_common_audit_log(project_dir: Path, feature_id: str | None) -> int | None:
    """Validate the common audit log substrate (slice-01 SSOT consolidation).

    Returns an exit code (0 or 1) when the common audit log exists and was
    validated; returns None when no common audit log is present and the caller
    should fall through to the legacy per-feature behavior.

    Surfaces a `LedgerIntegrityViolation` as a structured operator-readable
    diagnostic that carries the violation class, the offending line number, and
    a pointer to ``docs/operations/repair-instructions.md`` (AMEND #1: the
    operator-recoverable diagnostic surface).
    """
    common_log = project_dir / _COMMON_AUDIT_LOG_REL
    if not common_log.is_file():
        return None

    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    try:
        # Singleton-shape construction: project_root-only, no feature_id at
        # construction time. The integrity sweep runs over every record in the
        # common log regardless of any optional filter passed below.
        AtCompletionLedger(project_root=project_dir).read_records(feature_id=feature_id)
    except LedgerIntegrityViolation as exc:
        # Structured operator-recoverable diagnostic: violation class +
        # offending line number + repair-instructions pointer. AMEND #1.
        print(
            "LedgerIntegrityViolation: the common audit log failed its M7 "
            f"integrity contract.\n"
            f"  - violation class: {exc.detail}\n"
            f"  - offending line {exc.line_number} in {common_log}\n"
            f"  - see {exc.repair_instructions} for recovery steps\n"
            f"  - detail: {exc}"
        )
        return 1
    return 0


def _verify_atdd_pure(
    project_dir: Path,
    roadmap_path: Path,
    feature_id: str | None = None,
    trailer_port: CommitTrailerReadPort | None = None,
) -> int:
    """Verify deliver integrity for an atdd_pure feature (ADR-028 D4.2).

    The atdd_pure spine is roadmap-free and execution-log-free. `--roadmap-only`
    and the execution-log cross-reference are no-ops here -- this branch never
    inspects either artifact for verdict purposes. The verifier validates the
    AT-completion ledger instead:

    - present ledger -> proceed to the feature-end cycle assertion;
    - absent ledger  -> structured integrity-violation diagnostic (exit 1),
      never a crash;
    - a leftover roadmap.json is the WRONG artifact for this spine, reported as
      a WARNING -- never an error.

    slice-05 revision (Finding 1): a present ledger is no longer sufficient.
    The feature-end cycle must have written an `EBatchRefactorCompleted` record
    AND a `FeatureEndReviewVerdict` record -- absent either, the cycle (batch
    refactor + deep review) never ran and integrity fails (exit 1). A corrupt
    ledger that breaks its M7 integrity contract is also exit 1, never a crash.

    SSOT consolidation (slice-01): when the common audit log
    ``.nwave/audit/atdd-pure-events.jsonl`` is present, the integrity check
    runs against it FIRST and surfaces a `LedgerIntegrityViolation` with the
    offending line number + a pointer to
    ``docs/operations/repair-instructions.md`` (AMEND #1 operator-readable
    diagnostic). With the common log present and integrity-clean OR absent,
    the verifier proceeds to the legacy per-feature feature-end cycle check.
    """
    # slice-01 SSOT consolidation: integrity-check the common audit log when
    # present. A corrupt common log is a verification failure (exit 1) carrying
    # the AMEND #1 operator-readable diagnostic; a clean (or absent) common log
    # falls through to the legacy per-feature feature-end-cycle assertion.
    common_verdict = _verify_common_audit_log(project_dir, feature_id)
    if common_verdict == 1:
        return 1

    explicit = feature_id is not None
    resolved_feature_id = feature_id or _derive_feature_id(project_dir)
    ledger_dir = project_dir / ".nwave" / "telemetry" / "atdd-pure"
    ledger_path = _find_at_completion_ledger(
        project_dir, resolved_feature_id, explicit=explicit
    )

    if ledger_path is None:
        if explicit:
            print(
                "INTEGRITY VIOLATION: the AT-completion ledger is missing for "
                f"feature '{resolved_feature_id}'.\n"
                f"  - expected the append-only JSONL ledger at "
                f"{ledger_dir / f'{resolved_feature_id}.jsonl'}\n"
                "  - the atdd_pure DELIVER spine records audit telemetry in the "
                "AT-completion ledger (ADR-028 D3); without it the feature has "
                "no verifiable integrity trace. The verifier targets THIS "
                "feature's ledger exactly -- an absent ledger is a verification "
                "failure, never a silent fall-through to another file."
            )
        else:
            print(
                "INTEGRITY VIOLATION: cannot determine which feature to verify.\n"
                f"  - the AT-completion telemetry directory {ledger_dir} holds "
                "more than one feature ledger (or none)\n"
                "  - pass --feature-id <id> so the verifier targets exactly "
                "that feature's ledger; it will NOT fall through to an "
                "unrelated feature's ledger (false-PASS protection)."
            )
        return 1

    # The ledger may have been resolved via the single-ledger fallback (no
    # explicit / no derived id). Bind the feature id to the located ledger so
    # the feature-end read below targets the file actually verified.
    resolved_feature_id = ledger_path.stem

    from des.adapters.driven.logging.at_completion_ledger import (
        AtCompletionLedger,
        LedgerIntegrityViolation,
    )

    # DDD-10 feature-end reconciliation: every commit carrying a `Slice-Id:`
    # trailer must have a matching `SliceCommitVerified` ledger record. When
    # the M-2 commit-time backstop was bypassed (--no-verify, a foreign commit
    # path), an unrecorded slice is caught here -- the authoritative
    # feature-close sweep.
    #
    # The ledger's verified set is read FIRST: it is the reconciliation DEMAND.
    # A ledger that records a `SliceCommitVerified` slice asserts that slice was
    # committed, so its `Slice-Id:` trailer MUST be cross-checkable in the git
    # history. If git is then unreadable, the demand cannot be satisfied and the
    # gate refuses LOUD (D1). A ledger with NO verified slice demands nothing,
    # so git-absence is harmless and the verdict falls through to the
    # feature-end-cycle assertion below (a non-git ledger-only project stays
    # evaluable -- git-present parity preserved byte-for-byte).
    try:
        ledger_for_reconciliation = AtCompletionLedger(resolved_feature_id, project_dir)
        verified = ledger_for_reconciliation.verified_slices()
        unreconciled_bypass = (
            ledger_for_reconciliation.unreconciled_bypass_debt_slices()
        )
    except LedgerIntegrityViolation as exc:
        print(
            json.dumps(
                {
                    "event": "LedgerIntegrityViolation",
                    "error": (
                        "the AT-completion ledger failed its M7 integrity "
                        f"contract ({exc.detail}): {exc}"
                    ),
                }
            )
        )
        return 1

    # f-nonbypassable-attestation slice-02 (DDD-3 / CT-4): a `--no-verify`
    # slice-commit left a `SliceCommitBypassed` debt record at the PreToolUse/Bash
    # surface. While that debt carries NO matching `SliceCommitVerified` (the
    # `des reverify-slice-commit` flip), the gate genuinely COULD NOT verify that
    # commit -> the §17 degrade-LOUD class: verdict INDETERMINATE (exit 4), never
    # PASS. This is checked BEFORE git-shipped reconciliation and the feature-end
    # cycle assertion so the unreconciled-debt verdict takes precedence; it does
    # NOT require git (the debt lives in the ledger, read git-free). The cause
    # fragment NAMES `SliceCommitBypassed` so this INDETERMINATE is told apart from
    # the git-absent `FeatureIndeterminate` (CT-7) path -- distinct cause, same
    # verdict (DDD-7: no sixth verdict).
    if unreconciled_bypass:
        print(
            json.dumps(
                {
                    "event": "FeatureBypassDebtUnreconciled",
                    "feature_id": resolved_feature_id,
                    "unreconciled_bypass_debt_slices": sorted(unreconciled_bypass),
                    "debt_record": "SliceCommitBypassed",
                    "error": (
                        f"cannot certify {resolved_feature_id!r} as done: it carries "
                        f"an unreconciled SliceCommitBypassed debt for "
                        f"{sorted(unreconciled_bypass)} -- a per-commit verification "
                        "was bypassed (git commit --no-verify) and never reconciled. "
                        "Run `des reverify-slice-commit` to emit the matching "
                        "SliceCommitVerified, then the done-gate can certify."
                    ),
                }
            )
        )
        return CANNOT_EVALUATE_EXIT

    # The done-gate reads the commit-trailer history through the port (git lives
    # behind the adapter; this gate logic is git-free). On git-absence /
    # not-a-work-tree the port returns the LOUD `Indeterminate`, NEVER the silent
    # `frozenset()` that masked git-absence as "nothing shipped" (the AD-21/24
    # silent-fabrication this slice removes).
    port = trailer_port if trailer_port is not None else GitCommitTrailerReadAdapter()
    shipped_or_indeterminate = _shipped_slices(project_dir, port)
    if isinstance(shipped_or_indeterminate, Indeterminate):
        # git is unreadable. Refuse with the distinct cannot-evaluate verdict
        # (exit 4) ONLY when the ledger demands reconciliation it can no longer
        # cross-check (D1 + DDD-G4: distinct from the exit-1 unreconciled). With
        # no reconciliation demand there is nothing git could have told us, so a
        # non-git project still falls through to the feature-end-cycle check.
        if verified:
            print(
                json.dumps(
                    {
                        "event": INDETERMINATE_EVENT_NAME,
                        "feature_id": resolved_feature_id,
                        "reason": shipped_or_indeterminate.reason,
                        "error": (
                            f"cannot evaluate deliver integrity for "
                            f"{resolved_feature_id!r}: the commit-trailer history "
                            f"is unreadable ({shipped_or_indeterminate.reason}). "
                            f"git is absent or {project_dir} is not a git "
                            "work-tree -- the gate refuses LOUD rather than "
                            "silently report the delivery as nothing-shipped."
                        ),
                    }
                )
            )
            return CANNOT_EVALUATE_EXIT
        shipped: frozenset[str] = frozenset()
    else:
        shipped = shipped_or_indeterminate
    if shipped:
        # F-DELIVER-INTEGRITY-LEDGER-TARGETING: start from the loud-safe
        # `shipped - verified` and SUBTRACT only slices POSITIVELY owned by
        # OTHER features' ledgers. A co-resident feature's slice shares this
        # repo's git history (so it is in `shipped`) but is recorded in that
        # other feature's ledger -- subtracting `foreign_owned` removes the
        # cross-feature false positive. An own-feature slice with the exit gate
        # skipped is in NEITHER this feature's verified/reviewed set NOR any
        # other feature's ledger, so it survives and is still reported (the
        # loud-safe done-gate). An isolated single-feature repo has an empty
        # `foreign_owned`, so the formula degenerates to `shipped - verified`.
        foreign_owned = _foreign_owned_slices(project_dir, own_ledger=ledger_path)
        unreconciled = sorted((shipped - verified) - foreign_owned)
        if unreconciled:
            print(
                json.dumps(
                    {
                        "event": "FeatureUnreconciled",
                        "feature_id": resolved_feature_id,
                        "unreconciled_slices": unreconciled,
                        "error": (
                            f"feature {resolved_feature_id!r} has Slice-Id "
                            f"commit(s) for {unreconciled} with no matching "
                            "SliceCommitVerified ledger record -- the slice "
                            "exit gate was skipped"
                        ),
                    }
                )
            )
            return 1
        # The sweep cleared -- but reconciliation and the feature-end-cycle
        # check COMPOSE: a feature with every slice reconciled while the batch
        # refactor + deep review never ran is NOT closeable. Fall through to
        # the feature-end-cycle check below rather than `return 0` here.

    if roadmap_path.exists():
        print(
            f"Warning: a leftover roadmap.json is present at {roadmap_path}. "
            "The atdd_pure spine is roadmap-free (ADR-028 D1); this stale "
            "artifact is ignored and may be removed."
        )

    # Finding 1: assert the feature-end cycle ran. The targeted feature id
    # (NOT the alphabetically-first glob match) drives the M7 fail-closed read.
    # fix-oss-environmental-e2e-gate slice-02: presence-of-proof done-gate
    # (principle 13) -- the env-e2e heartbeat MUST be present alongside the
    # E_BATCH_REFACTOR + deep-review records before the feature is closeable.
    # fix-walking-skeleton-feature-end-wiring slice-01: the walking-skeleton
    # heartbeat MUST also be present -- mirror of env-e2e slice-02, 5th sibling
    # of the pre-7af95a3d2 shipped-but-unread defect class.
    # fix-ws-done-gate-na-reconciliation slice-01: the heartbeat alone only
    # proves the gate was ENTERED -- a walking skeleton that ran and FAILED
    # still leaves the heartbeat behind, so a done-gate keyed on the
    # heartbeat alone let a FAILED walking skeleton close (the hole this fix
    # closes). `WalkingSkeletonTierVerified` is the done-gate's actual
    # PASS-only trust anchor (RM-3); it is now ALSO required, reconciled for
    # a legitimately-NA feature by the `WalkingSkeletonNotApplicable` marker
    # via `feature_end_na_marker_reconciles()` below -- never by the
    # heartbeat alone.
    # fix-distill-signoff-feature-end-wiring slice-01: the two coverage-map
    # touchpoint heartbeats (`CoverageMapVerifiedAtDistillExit` +
    # `CoverageMapVerifiedAtDeliverExit`) emitted by the slice-06 gate are
    # also required -- closes the named residue F-SLICE-06-U4-CONSUMER-MISSING
    # from Gate D slice-06 commit `a8c9dc9d8`.
    # f-nonbypassable-attestation slice-01 (DDD-4): the full-suite leg's
    # `FullSuiteLegRan` heartbeat is also required -- a feature declared done
    # over a full suite that never ran is refused on record-ABSENCE (the gate
    # reads the leg's ledger record, never a pytest exit code; AT-A2 read/write
    # split). 6th sibling of the env-e2e / walking-skeleton / coverage-map
    # heartbeat pattern. This set is held EQUAL to
    # `nWave/flavors/atdd_pure.yaml feature_end_required_records` (AT-A6): a
    # single-location edit would silently re-open the half-wired hole.
    #
    # techdebt drain (event-name-constants-split-port-adapter): unlike other
    # call sites, "EnvironmentalE2eGateRan" here MUST stay a plain string
    # literal, not the imported `ENVIRONMENTAL_E2E_GATE_RAN` constant --
    # `tests/build/f_nonbypassable_attestation/test_arch_required_sets_equal.py`
    # AST-parses this `required = {...}` assignment as pure DATA (no import
    # execution) to diff it against the atdd_pure.yaml SSOT; a `Name` node in
    # place of a `Constant` breaks that reader. Exempted (with reason) in
    # tests/build/test_feature_end_event_name_constants_ssot.py.
    required = {
        "CoverageMapVerifiedAtDeliverExit",
        "CoverageMapVerifiedAtDistillExit",
        "EBatchRefactorCompleted",
        "EnvironmentalE2eGateRan",
        "FeatureEndReviewVerdict",
        "FullSuiteLegRan",
        "WalkingSkeletonGateRan",
        "WalkingSkeletonTierVerified",
    }
    # fix-feature-end-ws-gate-applicability slice-04: each applicability-aware
    # required record is satisfied by itself OR its DISTINCT not-applicable
    # marker -- never a false `*Verified*`. The cycle mints the NA marker ONLY on
    # the un-gameable mechanical NA signal (WS-NA delta cross-check for env-e2e;
    # genuine-absence-under-repo-inactive-adoption for coverage). A leg with
    # NEITHER record is still caught (the silent-skip backstop is intact). The
    # `required` set is UNCHANGED (R3 sequencing caveat): it keeps demanding the
    # heartbeat / verified names so the done-gate contract for in-flight features
    # does not shift mid-stream; the NA marker merely reconciles the requirement.
    #
    # fix-na-marker-reconcile-drift slice-01: the NA-marker -> required-record
    # map is read from the ONE shared source (`feature_end_na_marker_reconciles`,
    # `des.application.feature_end_na_marker_reconciliation`) -- the SAME
    # function the SubagentStop hook's `_missing_feature_end_cycle_records`
    # consults. Before this fix this CLI hardcoded its own independent
    # three-entry literal (this comment's former home) while the hook only
    # reconciled the full-suite leg inline; the two surfaces silently
    # disagreed on every repo with inactive coverage-map adoption.
    _NA_MARKER_RECONCILES = feature_end_na_marker_reconciles()
    try:
        ledger = AtCompletionLedger(resolved_feature_id, project_dir)
        recorded = (
            ledger.feature_end_events()
            | ledger.environmental_e2e_events()
            | ledger.walking_skeleton_events()
            | ledger.coverage_map_touchpoint_events()
            | ledger.full_suite_leg_events()
        )
    except LedgerIntegrityViolation as exc:
        print(
            "INTEGRITY VIOLATION: the AT-completion ledger failed its M7 "
            f"integrity contract ({exc.detail}): {exc}"
        )
        return 1

    reconciled = {
        required_name
        for na_marker, required_name in _NA_MARKER_RECONCILES.items()
        if na_marker in recorded
    }
    missing = sorted(required - recorded - reconciled)
    if missing:
        # The structured `FeatureEndCycleIncomplete` verdict (machine-readable
        # `missing_records`) is emitted on EVERY incomplete feature-end -- the
        # consolidated feature-end-cycle driving surface reads the missing set
        # off this JSON to pin partial-done honesty (slice-03 AT-4), and the
        # DDD-10 shipped-slice reconciliation path consumes it unchanged. When
        # `Slice-Id:` commits are present the message names the reconciliation
        # framing; otherwise it names the plain incomplete-cycle framing -- the
        # event + missing_records shape is identical so every consumer reads one
        # contract.
        if shipped:
            error = (
                f"feature {resolved_feature_id!r} reconciled every slice commit "
                "but the feature-end cycle is incomplete -- the ledger is "
                f"missing {missing}; the batch refactor + deep review never ran"
            )
        else:
            error = (
                f"feature {resolved_feature_id!r} has an incomplete feature-end "
                f"cycle -- the ledger is missing {missing}; the batch refactor, "
                "deep review, or a gate heartbeat never ran and was recorded"
            )
        print(
            json.dumps(
                {
                    "event": "FeatureEndCycleIncomplete",
                    "feature_id": resolved_feature_id,
                    "missing_records": missing,
                    "error": error,
                }
            )
        )
        return 1

    # f-nonbypassable-attestation slice-03 (DDD-5): the slice-plan-all-delivered
    # assertion COMPOSES with the feature-end cycle + reconciliation above. A
    # feature whose every committed slice reconciled but whose Slice-Plan DECLARES
    # a slice with NO delivered acceptance-test file was TRUNCATED -- that slice
    # was never delivered. The done-gate refuses with a definite FAIL (exit 1: the
    # plan rows + the filesystem are readable, so it is a no, not an INDETERMINATE
    # -- DDD-7, no sixth verdict) and NAMES the undelivered slice (distinct cause
    # fragment so a blocked developer learns WHY). Delivered-ness is the
    # un-gameable ``.feature``-file presence, NOT the gameable `Status` text
    # column (Ale 2026-06-15). This closes the 2026-06-04 truncated-feature hole.
    undelivered = _undelivered_slice_plan_slices(project_dir, resolved_feature_id)
    if undelivered:
        print(
            json.dumps(
                {
                    "event": "FeatureSlicePlanPending",
                    "feature_id": resolved_feature_id,
                    "pending_slices": sorted(undelivered),
                    "error": (
                        f"cannot certify {resolved_feature_id!r} as done: its "
                        f"Slice-Plan declares {len(undelivered)} slice(s) with no "
                        f"delivered acceptance-test (@slice-NN .feature) file -- "
                        f"{sorted(undelivered)}; every committed slice reconciled "
                        "but the feature is TRUNCATED (slices declared but never "
                        "delivered). Deliver the missing slices before declaring "
                        "the feature done."
                    ),
                }
            )
        )
        return 1

    # Both checks cleared. With `Slice-Id:` commits this is the composed
    # reconciliation verdict (`FeatureReconciled`); otherwise the classic
    # plain-text trace verdict, unchanged.
    if shipped:
        # Report the feature's OWN reconciled slices, not the cross-feature
        # git-history `shipped` over-count (F-VERIFY-INTEGRITY-RECONCILED-SLICES-
        # OVERCOUNTS-PHANTOM, cross-tier swarm 2026-06-29): `shipped` is the
        # `Slice-Id:` trailer set, NOT feature-tagged, so it accumulates EVERY
        # co-resident feature's slice-ids (8 reported for a 4-slice feature).
        # Subtracting `foreign_owned` is WRONG (slice-ids are not globally unique
        # -> it removes THIS feature's own slices, an under-count). For a slice-
        # plan feature the accurate set is its DECLARED slice-ids -- all
        # reconciled here, since any undelivered slice would have FAILED the
        # truncation check above. A classic feature with no Slice-Plan falls back
        # to `shipped` (its historical behaviour, unchanged).
        declared = _declared_slice_plan_slice_ids(project_dir, resolved_feature_id)
        reconciled_ids = sorted(declared) if declared else sorted(shipped)
        print(
            json.dumps(
                {
                    "event": "FeatureReconciled",
                    "feature_id": resolved_feature_id,
                    "reconciled_slices": reconciled_ids,
                }
            )
        )
        return 0
    print(
        f"All slices have a complete AT-completion ledger trace: {ledger_path} "
        "and the feature-end cycle recorded its refactor + review verdict "
        "(atdd_pure: roadmap.json and execution-log.json cross-reference skipped)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    # f-finalize-verify-single-spine slice-01: the integrity gate carries
    # exactly ONE spine. The classic `workflow.mode == classic` finalize leg,
    # the `resolve_workflow_mode` dispatch, and `--roadmap-only` were removed;
    # `_verify_atdd_pure` is the whole body. The `des verify-integrity` subcommand
    # and the 0/1/2 exit-code contract are preserved byte-for-byte (exit 2 is the
    # argparse usage error below; exit 4 is the LOUD cannot-evaluate verdict).
    raw_args = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    args = parser.parse_args(raw_args)

    # `--repo` is the consolidated feature-end-cycle alias for the positional
    # project_dir; exactly one of the two locates the verification target.
    project_dir = args.project_dir if args.project_dir is not None else args.repo
    if project_dir is None:
        parser.error("a project_dir positional or --repo is required")
    roadmap_path = project_dir / "roadmap.json"

    # Composition root: default-wire the real git adapter and inject it down the
    # call chain (main -> _verify_atdd_pure -> _shipped_slices). The gate logic
    # stays git-free; git lives only behind GitCommitTrailerReadAdapter.
    return _verify_atdd_pure(
        project_dir,
        roadmap_path,
        args.feature_id,
        trailer_port=GitCommitTrailerReadAdapter(),
    )


if __name__ == "__main__":
    sys.exit(main())
