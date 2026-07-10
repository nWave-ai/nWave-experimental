"""des-verify-slice-commit-completeness -- slice-commit verify-then-record gate.

slice-14 of the atdd-pure-roadmap-free-rollout (E1, the completeness check) +
slice-02 of simplify-atdd-pure-carpaccio-spine (DDD-3, the atomic
verify-then-record exit gate).

Given a commit carrying a `Slice-Id:` trailer, this CLI runs two checks in
order -- E1 completeness then E2 the feature-scoped contract gate -- and
appends a `SliceCommitVerified` ledger record IF AND ONLY IF both exit 0, in
the same process. On any non-zero half the CLI exits non-zero and appends
nothing: an unverified slice never leaves a record behind (the M-3
non-vacuity contract, wall W3).

E1 completeness: assert every scenario tagged `@slice-NN` for the slice lives
in a git-tracked `.feature` file that is EITHER present in this commit OR
already tracked and unmodified by this slice. Under `--feature-id` the
`.feature` search is scoped to that feature via the `@feature-{id}` tag
(wall W5 -- a global `rglob` collides `@slice-NN` tags across features).

E2 contract gate: compose `run_contract_gate --feature-id` as a subprocess --
the feature-scoped contract suite with the M-1/M-8 non-vacuity floor.

Bounded-change: the ONLY filesystem mutation is one `SliceCommitVerified`
record appended per listed slice to the feature's M7 AT-completion ledger
(`.nwave/telemetry/atdd-pure/{feature_id}.jsonl`, via
`AtCompletionLedger.append_gate_event`), performed IFF E1 exit 0 AND E2 exit 0.
Reads otherwise (`git show`, `.feature` files).

MUST be stdlib-only (no `import yaml`) per the DES-bundle contract -- the very
contract the slice-01 regression violated. Every import below is stdlib or an
intra-package `des` module that is itself stdlib-only:
`carpaccio_slice_gate._feature_tag_files` (the `@feature-{id}` resolver, the
same import `run_contract_gate` uses for its `--feature-id` scope) and
`AtCompletionLedger` (the M7 ledger writer -- `fcntl` / `hashlib` / `json`,
all stdlib).

A commit MAY carry MULTIPLE `Slice-Id:` trailer lines -- the whole-tree-stashing
pre-commit hook forces interleaved multi-slice work to batch into ONE commit,
which then lists every slice it covers as a separate `Slice-Id:` trailer (see
friction F-07, docs/analysis/atdd-pure-dogfooding-friction-2026-05-20.md). The
gate verifies slice-commit completeness for EVERY listed slice and certifies
the commit only when every listed slice is complete; a single-`Slice-Id:`
commit is the one-element case of the same logic.

Exit codes:
    0 = verified -- E1 and E2 both cleared; exactly one `SliceCommitVerified`
        record was appended for the slice(s).
    1 = refused -- E1 (completeness) or E2 (contract gate) failed; the JSON
        payload names the failed half. Nothing was appended.
    2 = malformed input -- no `Slice-Id:` trailer, or repo / commit unreadable.

Reference: docs/feature/atdd-pure-roadmap-free-rollout/feature-delta.md
           # slice-14 design note (E1);
           docs/feature/simplify-atdd-pure-carpaccio-spine/feature-delta.md
           # slice-02 (DDD-3).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.slice_at_completeness import (
    feature_files_for_slice,
    files_in_commit,
    missing_at_files,
)
from des.cli.carpaccio_format import _lane_profile_for_slice, parse_slice_plan
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.lane_profile import AtRequirement
from des.domain.repo_path_resolver import feature_delta_path
from des.domain.slice_id_trailer import (
    _SLICE_ID_TRAILER_RE,
    extract_slice_id,
    extract_slice_ids,
)
from des.runtime.interpreter import InterpreterUnavailable, des_spawn


# The contract gate's dedicated INDETERMINATE exit code (DDD-2): the E2 gate
# could not resolve a usable interpreter on this machine and degraded LOUD
# INDETERMINATE-and-proceed rather than hard-refusing. Mirrors
# ``run_contract_gate._GATE_INDETERMINATE_EXIT_CODE`` -- distinct from 0
# (cleared), 1 (refused), 2 (hard-refuse / malformed). On this outcome the
# exit gate mints an honest ``SliceCommitIndeterminate``, never a fabricated
# ``SliceCommitVerified`` and never a bare refusal.
_GATE_INDETERMINATE_EXIT_CODE = 3


# DDD-3 identity guarantee: re-export the pure-function SSOT symbols so the
# 18 pre-existing callers (reverify_slice_commit + the multi-slice-trailer /
# atdd-pure-exit-gate ATs) keep importing from this module unchanged. The
# completeness symbols' canonical home is ``des.application.slice_at_completeness``;
# the pure trailer-parsers (``extract_slice_id`` / ``extract_slice_ids`` and the
# ``_SLICE_ID_TRAILER_RE`` they share) are domain logic homed in
# ``des.domain.slice_id_trailer`` (AD-05 layering fix -- adapters imported them
# downward from this CLI module). This module is the CLI driving port that wraps
# them with argparse + verdict emission. ``__all__`` marks the re-exported names
# as intentional so autoflake keeps the otherwise-internally-unused regex.
__all__ = [
    "_SLICE_ID_TRAILER_RE",
    "extract_slice_id",
    "extract_slice_ids",
    "feature_files_for_slice",
    "files_in_commit",
    "main",
    "missing_at_files",
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-slice-commit",
        description="Verify a slice commit carries the slice's .feature AT files.",
    )
    parser.add_argument(
        "--repo", required=True, help="Path to the git repository to inspect."
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="The commit-ish to inspect (e.g. HEAD).",
    )
    parser.add_argument(
        "--feature-id",
        help=(
            "The feature the slice commit belongs to. When given, the CLI runs "
            "the atomic verify-then-record exit gate: E1 completeness scoped to "
            "this feature, then E2 the feature-scoped contract gate, then one "
            "SliceCommitVerified ledger record IFF both clear. When omitted the "
            "CLI runs the legacy E1-only completeness check (classic-mode "
            "callers -- reverify_slice_commit, the U2 hook)."
        ),
    )
    parser.add_argument(
        "--expected-head",
        help=(
            "The pinned HEAD SHA the gate was launched against (M9). When "
            "present, the CLI re-reads HEAD and fails closed with "
            "CommitHeadRaced if HEAD has moved off this SHA. When absent, no "
            "race check runs -- behaviour is byte-for-byte unchanged."
        ),
    )
    parser.add_argument(
        "--scope-feature-id",
        help=(
            "Scope the legacy E1-only completeness check to this feature's "
            "`@feature-{id}`-tagged `.feature` files (slice-03). Unlike "
            "`--feature-id` (which flips the CLI into the verify-then-record "
            "exit gate -- E1 + E2 + a SliceCommitVerified ledger record), "
            "`--scope-feature-id` keeps the legacy E1-only verdict shape and "
            "writes NO ledger record: it only narrows E1's `.feature` candidate "
            "scan so a co-resident feature sharing the slice number on the tree "
            "is not cross-bound into this commit's completeness check. The U2 "
            "hook supplies it so E1 runs scoped while the hook stays the sole "
            "author of the verified record (E1 runs once, one record)."
        ),
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        default="gherkin",
        choices=("gherkin", "pytest-regression"),
        help=(
            "The acceptance-test kind the slice's E2 leg attests (default: "
            "gherkin, byte-identical for every existing caller). "
            "'pytest-regression' (#13) replaces the feature-scoped contract "
            "gate -- which cannot resolve a pytest-regression bugfix's "
            "structure -- with a BEHAVIORAL attestation: it actually runs "
            "--regression-test-file on the committed tree and uses its exit "
            "code as the E2 verdict."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        dest="regression_test_file",
        default=None,
        help=(
            "Repo-relative path to the pytest regression file E2 runs "
            "behaviorally (paired with --at-kind pytest-regression)."
        ),
    )
    parser.add_argument(
        "--slice-id",
        dest="slice_id",
        default=None,
        help=(
            "Override slice id for a bare legacy commit carrying NO "
            "Slice-Id: trailer (#51). When the commit has no resolvable "
            "trailer, this supplies the slice id instead of failing -- "
            "attesting on the BEHAVIORAL proof (the E2 pytest-regression "
            "leg passing on the committed tree) rather than the trailer. "
            "REQUIRES --at-kind pytest-regression + --regression-test-file "
            "(behavioral proof is mandatory without a trailer). REFUSES if "
            "it conflicts with a real Slice-Id: trailer already on the "
            "commit. The written SliceCommitVerified record carries a "
            "transparent attested_via: 'slice-id-override' field."
        ),
    )
    return parser


def _commit_head_raced(
    repo: Path, expected_head: str | None
) -> dict[str, object] | None:
    """Detect a HEAD that has raced off the pinned ``expected_head`` SHA (M9 / F3).

    Returns a `CommitHeadRaced` payload when HEAD has moved off the pinned SHA;
    None when HEAD still matches (or no `--expected-head` was given, so no race
    check runs). Under a concurrent amend/rebase the HEAD the gate was launched
    against can move before the gate inspects it -- a stale verdict. Re-reading
    HEAD makes the race detectable and fail-closed.
    """
    if expected_head is None:
        return None
    try:
        current = _git(repo, "rev-parse", "HEAD").strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {
            "event": "CommitHeadRaced",
            "pinned_sha": expected_head,
            "current_sha": "",
            "error": f"cannot re-read HEAD to verify the pinned SHA: {exc}",
        }
    if current == expected_head:
        return None
    return {
        "event": "CommitHeadRaced",
        "pinned_sha": expected_head,
        "current_sha": current,
        "error": (
            "HEAD moved during the G_COMMIT exit gate "
            f"(pinned {expected_head}, now {current}); re-run the gate"
        ),
    }


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object on BOTH stdout and stderr.

    The pre-existing machine-readable contract (DISCUSS row 4: no breaking
    change for existing pre-commit / CI / hook consumers) keeps the event on
    stdout; the slice-02 human-readable surface co-emits it on stderr so a
    single channel carries both the structured event and the new colored
    verdict line.
    """
    line = json.dumps(payload)
    print(line)
    print(line, file=sys.stderr)


def _human_summary_for(payload: dict[str, object]) -> tuple[Verdict, str]:
    """Return the (verdict, summary) pair the named ``event`` maps to.

    Per slice-02 verdict mapping: SliceCommitComplete / SliceCommitVerified
    → ✅ PASS, every refusal / malformed input → ❌ FAIL. The summary names
    the listed slice(s) when available so the operator immediately sees what
    cleared / refused.
    """
    event = payload.get("event")
    slice_ids = payload.get("slice_ids")
    slice_label = (
        ", ".join(slice_ids) if isinstance(slice_ids, list) and slice_ids else ""
    )
    if event in ("SliceCommitComplete", "SliceCommitVerified"):
        verdict = Verdict.PASS
        summary = (
            f"slice commit verified ({slice_label})"
            if slice_label
            else "slice commit verified"
        )
        return verdict, summary
    verdict = Verdict.FAIL
    error = payload.get("error")
    summary = (
        f"slice commit refused: {error}"
        if isinstance(error, str) and error
        else "slice commit refused"
    )
    return verdict, summary


def _emit_with_human_surface(payload: dict[str, object]) -> None:
    """Emit the JSON event on both channels plus the human-readable verdict line.

    Composes ``_emit`` (dual-channel JSON) with ``print_human_summary``: every
    operator-facing verdict point in this CLI carries BOTH surfaces, so the
    operator sees a colored ✅/❌ line and the structured event lands on
    stderr for the slice-02 AT assertions.
    """
    _emit(payload)
    verdict, summary = _human_summary_for(payload)
    print_human_summary(verdict, summary)


def _is_at_exempt_lane(repo: Path, feature_id: str, slice_id: str) -> bool:
    """Resolve whether ``slice_id`` is AT-EXEMPT, mirroring the entry gate.

    Reads the SAME `[REF] Slice Plan` datum the carpaccio ENTRY gate consults
    (`_lane_profile_for_slice`, `carpaccio_format.py:640-655`) via the SAME
    `feature_delta_path` + `parse_slice_plan` resolution
    (`carpaccio_slice_gate.py:880-892`) -- the single shared consulting
    mechanism (D11/D12), so the exit gate's lane awareness never diverges
    from the entry gate's. Returns ``False`` (never exempt) when the
    feature-delta is absent or the slice carries no `@prefactoring`
    annotation -- the fail-closed default that leaves the non-exempt path
    byte-identical.
    """
    delta_path = feature_delta_path(repo, feature_id)
    if not delta_path.is_file():
        return False
    plan = parse_slice_plan(delta_path.read_text(encoding="utf-8"))
    profile = _lane_profile_for_slice(plan, slice_id)
    return profile is not None and profile.at_requirement is AtRequirement.EXEMPT


def _run_contract_gate(repo: Path, feature_id: str, slice_id: str) -> int:
    """Run E2 -- the feature-scoped contract gate -- for one slice.

    Composes `run_contract_gate --feature-id` as a subprocess (DDD-12: the
    test-runner seam stays inside `run_contract_gate`; this CLI adds no pytest
    call site of its own). Returns the contract gate's exit code -- 0 when the
    feature-scoped suite cleared, non-zero on a refusal or a malformed scope.

    DDD-1/DDD-2 degrade-LOUD: when ``des_spawn`` itself cannot resolve a usable
    interpreter on this machine it raises ``InterpreterUnavailable`` (the spawn
    boundary, not the child). That is the same non-Python-target interpreter
    absence the gate's own collection path degrades on -- map it to the
    dedicated ``_GATE_INDETERMINATE_EXIT_CODE`` so the caller records an honest
    ``SliceCommitIndeterminate`` instead of crashing. INDETERMINATE is never
    coerced to 0 (a pass) -- a runnable-but-failing gate returns its own
    non-zero code unchanged.
    """
    try:
        completed = des_spawn(
            None,
            "des.cli.run_contract_gate",
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--entering-slice",
            slice_id,
            capture_output=True,
            text=True,
        )
    except InterpreterUnavailable:
        return _GATE_INDETERMINATE_EXIT_CODE
    return completed.returncode


def _run_regression_gate(repo: Path, regression_test_file: str) -> int:
    """Run E2 BEHAVIORALLY for a pytest-regression slice (#13, Ale-ratified).

    The feature-scoped contract gate cannot resolve a pytest-regression
    bugfix's structure, so this path replaces it with an execution-observing
    attestation: it actually RUNS the declared ``regression_test_file`` on
    the committed tree (``-m pytest <file> -q`` via ``des_spawn`` -- the SAME
    interpreter-resolution boundary ``_run_contract_gate`` uses, mirroring
    ``verify_red_green.py``'s subprocess pattern) and uses ITS exit code as
    the E2 verdict. Only an OBSERVED pass (exit 0) ever earns E2-clear.

    Every interpreter spawn in ``src/des`` MUST route through
    ``des.runtime.interpreter.python_for`` (the build-tier arch-test
    ``test_no_inline_interpreter_spawn.py`` bans a raw ``sys.executable``) --
    ``des_spawn("pytest", ...)`` composes that resolution BY CONSTRUCTION, so
    this never trusts the running interpreter's name.

    A declared file that is missing, or whose interpreter ``des_spawn``
    itself cannot resolve (``InterpreterUnavailable``), is NEVER trusted by
    presence alone -- it returns the SAME ``_GATE_INDETERMINATE_EXIT_CODE``
    sentinel ``_run_contract_gate`` uses for its own degrade-LOUD path, so
    the caller routes it through the existing ``SliceCommitIndeterminate``
    machinery (never a fabricated ``SliceCommitVerified``, never a silent
    pass).
    """
    test_path = repo / regression_test_file
    if not test_path.is_file():
        return _GATE_INDETERMINATE_EXIT_CODE
    try:
        completed = des_spawn(
            "pytest",
            "pytest",
            str(test_path),
            "-q",
            cwd=repo,
            capture_output=True,
            text=True,
        )
    except InterpreterUnavailable:
        return _GATE_INDETERMINATE_EXIT_CODE
    return completed.returncode


def _append_slice_commit_verified(
    repo: Path,
    feature_id: str,
    slice_ids: list[str],
    *,
    attested_via: str | None = None,
) -> None:
    """Record one `SliceCommitVerified` event per verified slice (DDD-3).

    The single filesystem mutation of this CLI -- performed only after E1 and
    E2 have both cleared. Each record is written through
    ``AtCompletionLedger.append_gate_event`` (REUSE-unchanged, DDD-3 Reuse
    Analysis), so it lands on the carpaccio chain's read substrate
    (``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``) carrying the M7
    integrity fields (gap-free ``seq`` + ``record_hash``) the slice-03
    predecessor check and the M-2 backstop fail-closed on.

    Idempotency (C4a): ``AtCompletionLedger.verified_slices()`` is set-valued,
    so a re-run on an already-verified commit appends a further record yet the
    carpaccio chain still sees the slice exactly once -- the predecessor
    ordering it depends on is uncorrupted.

    ``attested_via`` (#51): when supplied (the ``--slice-id`` override path),
    threaded through to the ledger record as a transparent field so the audit
    shows the trailer was bypassed. Absent/None on the normal trailer path --
    that record stays byte-unchanged.
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for slice_id in slice_ids:
        ledger.append_gate_event(
            "SliceCommitVerified", slice_id, attested_via=attested_via
        )


def _append_slice_commit_indeterminate(
    repo: Path,
    feature_id: str,
    slice_ids: list[str],
    reason: str = "contract_gate_interpreter_unavailable",
) -> None:
    """Record one honest `SliceCommitIndeterminate` event per slice (DDD-2 / DDD-6).

    The non-Python-target degrade record: the E2 contract gate could not resolve
    a usable interpreter on this machine and degraded LOUD INDETERMINATE, so the
    ledger states "unverified on this machine" truthfully -- NEVER a fabricated
    `SliceCommitVerified` (no-silent-pass) and never a bare refusal that wedges
    the slice chain. Written through the SSOT mint
    ``AtCompletionLedger.append_slice_commit_indeterminate`` (DDD-6 reuse -- the
    SAME writer ``des commit-slice``'s committed-scope-digest degrade routes
    through), so the record carries the free-text ``reason`` plus the honesty
    fields (`gate_scope == "INDETERMINATE"`, `at_verified == False`) and lands on
    the carpaccio chain's read substrate. The in-order guard's
    predecessor-satisfied predicate (which accepts an INDETERMINATE predecessor)
    then lets the successor slice dispatch.
    """
    ledger = AtCompletionLedger(feature_id, repo)
    for slice_id in slice_ids:
        ledger.append_slice_commit_indeterminate(slice_id, reason)


def _resolve_slice_ids(
    repo: Path, commit: str, slice_id_override: str | None = None
) -> tuple[list[str], str, int | None, bool]:
    """Read a commit's `Slice-Id:` trailer(s) + its SHA.

    Returns ``(slice_ids, commit_sha, error_code, used_override)``.
    ``error_code`` is None on success, or the exit code (2) when the commit is
    unreadable / has no trailer and no override / the override conflicts with
    a real trailer -- in which case the malformed/refusal verdict has already
    been emitted. ``used_override`` is True iff the commit carried NO
    resolvable trailer AND ``slice_id_override`` supplied the slice id instead
    (#51, the ``--slice-id`` legacy-commit-attestation path) -- False on every
    other outcome, including a matching (idempotent) override.
    """
    try:
        commit_message = _git(repo, "log", "-1", "--format=%B", commit)
        commit_sha = _git(repo, "rev-parse", commit).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": f"cannot read commit {commit!r}: {exc}",
            }
        )
        return [], "", 2, False

    slice_ids = extract_slice_ids(commit_message)
    if not slice_ids:
        if slice_id_override is not None:
            return [slice_id_override], commit_sha, None, True
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": "commit carries no Slice-Id:/Step-Id: trailer",
            }
        )
        return [], "", 2, False

    if slice_id_override is not None and slice_id_override not in slice_ids:
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "commit": commit,
                "error": (
                    f"--slice-id {slice_id_override!r} conflicts with the "
                    f"commit's real Slice-Id: trailer(s) {slice_ids!r} -- an "
                    "override must never silently contradict a real trailer"
                ),
                "how": (
                    "drop --slice-id (the commit already carries a real "
                    "Slice-Id: trailer) or correct the mismatched slice id"
                ),
            }
        )
        return [], "", 2, False

    return slice_ids, commit_sha, None, False


def _missing_by_slice(
    repo: Path, commit: str, slice_ids: list[str], feature_id: str | None
) -> tuple[dict[str, list[str]], int | None]:
    """Run E1 completeness for every listed slice.

    Returns ``(deficient, error_code)``: ``deficient`` maps each slice with
    missing `.feature` files to that list; ``error_code`` is 2 (and the
    malformed verdict already emitted) when the repository is unreadable.
    """
    try:
        missing = {
            slice_id: missing_at_files(repo, commit, slice_id, feature_id)
            for slice_id in slice_ids
        }
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _emit_with_human_surface(
            {
                "event": "MalformedInput",
                "error": f"cannot inspect repository: {exc}",
            }
        )
        return {}, 2
    return {sid: m for sid, m in missing.items() if m}, None


def _effective_scope(
    repo: Path, slice_ids: list[str], scope_feature_id: str | None
) -> str | None:
    """Resolve the feature scope E1 narrows its `.feature` scan to (Seam A).

    Returns ``scope_feature_id`` when that feature actually owns at least one
    `@feature-{id}`-tagged `.feature` file for one of the listed slices, so the
    scoped scan ignores a co-resident feature sharing the slice number (the
    slice-03 cross-feature isolation property). Returns ``None`` -- the legacy
    whole-tree scan -- when ``scope_feature_id`` is absent OR resolves to ZERO
    candidate files: a feature that tags no `.feature` under its id must NOT
    have its completeness check silently degrade to a vacuous always-pass.
    Falling back to the whole-tree scan keeps the genuine-incompleteness guard
    intact for callers whose `.feature` files predate the `@feature-{id}`
    convention (anti-vacuity: scoping narrows, it never blinds the check).
    """
    if scope_feature_id is None:
        return None
    has_scoped_candidate = any(
        feature_files_for_slice(repo, slice_id, scope_feature_id)
        for slice_id in slice_ids
    )
    return scope_feature_id if has_scoped_candidate else None


def _run_legacy_completeness(repo: Path, args: argparse.Namespace) -> int:
    """The legacy E1-only completeness check (no `--feature-id`).

    Classic-mode callers -- `reverify_slice_commit`, the U2 hook -- invoke the
    CLI without `--feature-id` and expect the original `SliceCommitComplete` /
    `SliceCommitIncomplete` verdict shape and the pure-read git contract.

    slice-03 (Seam A): when `--scope-feature-id` is supplied the E1 `.feature`
    candidate scan is scoped to that feature's `@feature-{id}`-tagged files, so
    a co-resident feature sharing the slice number on the tree is not
    cross-bound into this commit's completeness check. The verdict shape stays
    the legacy E1-only `SliceCommitComplete` / `SliceCommitIncomplete` and NO
    ledger record is written -- the verify-then-record seam (`--feature-id`) is
    not entered.
    """
    slice_ids, _commit_sha, error_code, _used_override = _resolve_slice_ids(
        repo, args.commit
    )
    if error_code is not None:
        return error_code

    scope = _effective_scope(repo, slice_ids, args.scope_feature_id)
    deficient, error_code = _missing_by_slice(repo, args.commit, slice_ids, scope)
    if error_code is not None:
        return error_code

    if deficient:
        _emit_with_human_surface(
            {
                "event": "SliceCommitIncomplete",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "missing_feature_files_by_slice": deficient,
                "error": "; ".join(
                    f"slice {slice_id} commit is missing "
                    f"{len(missing)} .feature AT file(s): " + ", ".join(missing)
                    for slice_id, missing in deficient.items()
                ),
            }
        )
        return 1

    _emit_with_human_surface(
        {
            "event": "SliceCommitComplete",
            "slice_ids": slice_ids,
            "commit": args.commit,
        }
    )
    return 0


def _run_verify_then_record(repo: Path, args: argparse.Namespace) -> int:
    """The atomic verify-then-record exit gate (`--feature-id` given, DDD-3).

    Runs E1 (completeness, feature-scoped) then E2 (the feature-scoped
    contract gate) and appends one `SliceCommitVerified` record IFF both
    clear. On any non-zero half the CLI refuses (exit 1, naming the failed
    half) and appends nothing.
    """
    feature_id = args.feature_id
    slice_id_override = getattr(args, "slice_id", None)

    # Honesty guard #1 (#51, GDP-6, fail-closed): --slice-id overrides a
    # trailer only on the strength of a behavioral proof -- a bare structural
    # attestation cannot be trusted without a trailer. Checked BEFORE any
    # repo access so the refusal is deterministic and self-explaining.
    if slice_id_override is not None and (
        args.at_kind != "pytest-regression" or not args.regression_test_file
    ):
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "commit": args.commit,
                "error": (
                    "--slice-id requires --at-kind pytest-regression and "
                    "--regression-test-file -- behavioral proof is "
                    "mandatory when overriding a missing Slice-Id: trailer"
                ),
                "how": (
                    "pass --at-kind pytest-regression --regression-test-file "
                    "<repo-relative-path> alongside --slice-id"
                ),
            }
        )
        return 2

    slice_ids, commit_sha, error_code, used_override = _resolve_slice_ids(
        repo, args.commit, slice_id_override
    )
    if error_code is not None:
        return error_code

    # E1 -- completeness. A deficient slice refuses before E2 is reached.
    deficient, error_code = _missing_by_slice(repo, args.commit, slice_ids, feature_id)
    if error_code is not None:
        return error_code
    if deficient:
        _emit_with_human_surface(
            {
                "event": "SliceCommitRefused",
                "refused_half": "E1",
                "slice_ids": slice_ids,
                "commit": args.commit,
                "missing_feature_files_by_slice": deficient,
                "error": "; ".join(
                    f"slice {slice_id} commit is missing "
                    f"{len(missing)} .feature AT file(s): " + ", ".join(missing)
                    for slice_id, missing in deficient.items()
                ),
                "how": (
                    "stage and land the missing .feature AT file(s) into the "
                    "slice commit via `des commit-slice`"
                ),
            }
        )
        return 1

    # E2 -- one run per listed slice. Default (`gherkin`): the feature-scoped
    # contract gate, unchanged. `--at-kind pytest-regression` (#13): a
    # BEHAVIORAL attestation -- actually runs `--regression-test-file` on the
    # committed tree in place of the contract gate, which cannot resolve a
    # pytest-regression bugfix's structure.
    is_pytest_regression = args.at_kind == "pytest-regression"
    for slice_id in slice_ids:
        if _is_at_exempt_lane(repo, feature_id, slice_id):
            # Mirrors the entry gate's `LaneAtExemptionAccepted` early-return
            # (carpaccio_format.py:627-633): a 0-AT `@prefactoring` slice has
            # no `@slice-NN` scenarios to intersect, so `run_contract_gate`'s
            # M-8 non-vacuity floor would refuse it `empty-intersection`. The
            # SAME lane exemption the entry gate honors is honored here --
            # short-circuit E2 to an honest clear instead of spawning the
            # vacuous feature-scoped contract-gate subprocess.
            continue
        if is_pytest_regression:
            if not args.regression_test_file:
                _emit_with_human_surface(
                    {
                        "event": "SliceCommitRefused",
                        "refused_half": "E2",
                        "slice_ids": slice_ids,
                        "commit": args.commit,
                        "failed_slice": slice_id,
                        "error": (
                            "--at-kind pytest-regression requires "
                            "--regression-test-file"
                        ),
                        "how": (
                            "pass --regression-test-file <repo-relative-path> "
                            "alongside --at-kind pytest-regression"
                        ),
                    }
                )
                return 1
            contract_code = _run_regression_gate(repo, args.regression_test_file)
        else:
            contract_code = _run_contract_gate(repo, feature_id, slice_id)
        # DDD-2 degrade-LOUD: an INDETERMINATE gate (no usable interpreter on
        # this machine, or -- pytest-regression -- a regression-test-file that
        # could not be run) is NOT a refusal -- record the honest
        # SliceCommitIndeterminate (never a fabricated SliceCommitVerified) and
        # let the slice chain progress, distinct from both the verified mint and
        # a genuine refusal. A runnable-but-failing gate returns its own
        # non-zero code and refuses.
        if contract_code == _GATE_INDETERMINATE_EXIT_CODE:
            if is_pytest_regression:
                return _record_indeterminate_outcome(
                    repo,
                    args,
                    feature_id,
                    slice_ids,
                    reason="pytest_regression_file_unrunnable",
                    diagnostic=(
                        f"the declared --regression-test-file "
                        f"{args.regression_test_file!r} could not be run on "
                        "the committed tree (missing or uncollectible) -- "
                        "recorded an honest SliceCommitIndeterminate "
                        "(unverified here), never a fabricated pass"
                    ),
                )
            return _record_indeterminate_outcome(repo, args, feature_id, slice_ids)
        if contract_code != 0:
            if is_pytest_regression:
                _emit_with_human_surface(
                    {
                        "event": "SliceCommitRefused",
                        "refused_half": "E2",
                        "slice_ids": slice_ids,
                        "commit": args.commit,
                        "failed_slice": slice_id,
                        "regression_test_file": args.regression_test_file,
                        "contract_gate_exit_code": contract_code,
                        "error": (
                            f"slice {slice_id} failed the E2 behavioral "
                            f"attestation -- {args.regression_test_file} did "
                            f"not pass on the committed tree (exit "
                            f"{contract_code})"
                        ),
                        "how": (
                            f"run `pytest {args.regression_test_file} -q` "
                            "locally, fix the regression, then re-commit via "
                            "`des commit-slice`"
                        ),
                    }
                )
                return 1
            _emit_with_human_surface(
                {
                    "event": "SliceCommitRefused",
                    "refused_half": "E2",
                    "slice_ids": slice_ids,
                    "commit": args.commit,
                    "failed_slice": slice_id,
                    "contract_gate_exit_code": contract_code,
                    "error": (
                        f"slice {slice_id} failed the feature-scoped contract "
                        f"gate (exit {contract_code})"
                    ),
                    "how": (
                        f"inspect the failure with `run_contract_gate --repo .` "
                        f"(feature {feature_id}, slice {slice_id}), green the "
                        "failing feature-scoped acceptance test(s), then "
                        "re-commit via `des commit-slice`"
                    ),
                }
            )
            return 1

    # E3 -- the examine-verdict DoD gate (evolution-plan P1.2, hard-wired into
    # the verify-then-record path too, not only `des commit-slice`). EXAMINE is
    # the true Definition of DONE: green tests verify the CODE, EXAMINE (Vera)
    # verifies the running SYSTEM through the real surface and attaches the
    # observed artifact -- the two diverge (isolated-green != assembled-green).
    # `check_examine_verdict` is a NO-OP unless ARMED (a charter dir exists under
    # `docs/product/expectations/{feature_id}/`, or the opt-in env); when armed,
    # EVERY entering slice must carry a fresh PASS ExamineVerdict whose
    # charter_seal still matches the charter's CURRENT bytes, else the slice is
    # refused fail-closed and NO SliceCommitVerified is recorded. A
    # behavior-preserving prefactoring/refactoring slice carries no charter ->
    # unarmed -> green-to-green suffices (it goes through a separate path anyway).
    # This closes the bypass where a slice committed via `git commit` + `des
    # verify-slice-commit` skipped the examine gate that only `des commit-slice`
    # enforced (Ale 2026-07-05: "without evidence the slice is not implemented").
    from des.cli.commit_slice import check_examine_verdict

    for slice_id in slice_ids:
        examine_rejection = check_examine_verdict(repo, feature_id, slice_id)
        if examine_rejection is not None:
            exit_code = examine_rejection.pop("exit_code")
            examine_rejection["refused_half"] = "E3"
            examine_rejection.setdefault(
                "error",
                f"{examine_rejection.get('what', '')} -- "
                f"FIX: {examine_rejection.get('how', '')}",
            )
            _emit_with_human_surface(examine_rejection)
            assert isinstance(exit_code, int)
            return exit_code

    # E1, E2 and E3 all cleared -- record one SliceCommitVerified per slice.
    # (#51) the --slice-id override path carries the transparent
    # attested_via marker so the audit shows the trailer was bypassed;
    # the normal trailer path carries no such field (byte-unchanged).
    attested_via = "slice-id-override" if used_override else None
    _append_slice_commit_verified(
        repo, feature_id, slice_ids, attested_via=attested_via
    )
    verified_payload: dict[str, object] = {
        "event": "SliceCommitVerified",
        "slice_ids": slice_ids,
        "commit": args.commit,
        "commit_sha": commit_sha,
    }
    if attested_via is not None:
        verified_payload["attested_via"] = attested_via
    _emit_with_human_surface(verified_payload)
    return 0


def _record_indeterminate_outcome(
    repo: Path,
    args: argparse.Namespace,
    feature_id: str,
    slice_ids: list[str],
    *,
    reason: str = "contract_gate_interpreter_unavailable",
    diagnostic: str = (
        "the feature-scoped contract gate could not resolve a usable "
        "interpreter on this machine -- recorded an honest "
        "SliceCommitIndeterminate (unverified here), never a fabricated pass"
    ),
) -> int:
    """Mint the honest INDETERMINATE outcome for the listed slices (DDD-2).

    The E2 gate degraded LOUD INDETERMINATE -- either the feature-scoped
    contract gate found no usable interpreter (the default `reason` /
    `diagnostic`), or (#13) a `--at-kind pytest-regression` slice declared a
    `--regression-test-file` that could not be run on the committed tree
    (missing / uncollectible -- the caller passes an accurate `reason` /
    `diagnostic` for that case). Either way the exit gate records one
    `SliceCommitIndeterminate` per slice -- never a fabricated
    `SliceCommitVerified` (no-silent-pass) and never a bare refusal that
    wedges the chain -- and emits the honest event so the operator sees the
    gate could not verify here. Returns the dedicated INDETERMINATE exit code
    (distinct from 0 verified, 1 refused, 2 malformed).
    """
    _append_slice_commit_indeterminate(repo, feature_id, slice_ids, reason)
    _emit_with_human_surface(
        {
            "event": "SliceCommitIndeterminate",
            "slice_ids": slice_ids,
            "commit": args.commit,
            "error": diagnostic,
        }
    )
    return _GATE_INDETERMINATE_EXIT_CODE


def main(argv: list[str] | None = None) -> int:
    """Verify a slice commit -- and, under `--feature-id`, record it.

    With `--feature-id`: the atomic verify-then-record exit gate (DDD-3) --
    E1 then E2 then one ledger record IFF both clear. Without `--feature-id`:
    the legacy E1-only completeness check (classic-mode callers).
    """
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

    # M9 / F3: a HEAD raced off the pinned SHA fails closed before any verdict.
    raced = _commit_head_raced(repo, args.expected_head)
    if raced is not None:
        _emit_with_human_surface(raced)
        return 1

    if args.feature_id:
        return _run_verify_then_record(repo, args)
    return _run_legacy_completeness(repo, args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
