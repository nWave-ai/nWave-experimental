"""AT-review verdict producer (ADR-029 D5 -- PRODUCER half; amended by
declared-facts-reachable-recorded slice-01, DD-1/DD-2).

After the acceptance-designer reviewer judges a slice's AT set, the atdd_pure
DISTILL step records the outcome as an ``ATReviewVerdict`` record appended to
the AT-completion ledger ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``.
DD-1 both-outcomes write: BOTH ``APPROVED`` and ``NEEDS_REVISION`` append a
record -- a rejection leaves a mechanically-readable trace instead of
collapsing into "never reviewed" (F3). The control-flow half of D5 is
UNCHANGED: NEEDS_REVISION still loops the slice back to the
acceptance-designer; only the prior SILENCE on that path is removed.

``carpaccio_slice_gate.py`` is the CONSUMER (assertion 5) that reads this record
at the DELIVER entry gate; this module is the PRODUCER that writes it. The
record carries the veto-relevant fields (reviewer_agent_id, slice_id, verdict,
at_ids, at_content_hash, timestamp) and the content seal (at_content_hash is a
SHA-256 over sorted scenario bodies) -- ``at_content_hash``'s semantics are
verdict-neutral: the content hash of the AT set AS REVIEWED, not "what was
approved". No ``hmac_sha256`` field is written; key absence is a non-event
(OSS threat model: key holder and would-be forger are the same person --
keyed signing adds friction without adding a guarantee).

Stdlib-only (no third-party imports) so the module is bundle-safe.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Literal

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.runner import at_discovery, cargo_runner
from des.cli._identity_args import meaningful_identity
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.carpaccio_format import GateError
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.verify_charter_filled import charter_missing_sections
from des.domain.expectation_charter_mapping import (
    CharterMappingState,
    resolve_slice_charter,
)
from des.domain.repo_path_resolver import (
    feature_delta_path,
)
from des.domain.repo_path_resolver import (
    resolve_repo_root as _resolve_repo_root,
)


__all__ = [
    "main",
    "record_at_review_verdict",
    "record_review_outcome",
]

_SCHEMA_VERSION = "1.0.0"
_EVENT = "ATReviewVerdict"
_APPROVED = "APPROVED"
_NEEDS_REVISION = "NEEDS_REVISION"
_BLOCKED_BY_ROBUSTNESS_GATE = "robustness-density-gate"

# Slice-05 wiring (feature-fix-robustness-pbt-density-gate, slice-05 AT1):
# the verdict producer consults the robustness density gate CLI at DISTILL
# exit. When both --robustness-declaration AND --robustness-at-scope are
# supplied AND the verdict is APPROVED, the producer invokes
# scripts.cli.check_robustness_density as a subprocess; a non-zero gate exit
# blocks the APPROVED ledger write and surfaces the gate's stdout diagnostic
# (e.g. RobustnessCoverageMiss / RobustnessPBTShallow) on this producer's
# stderr. The producer remains backward-compatible: omitting both flags keeps
# the slice-01..04 invocation shape unchanged (existing callers untouched).
_ROBUSTNESS_GATE_MODULE = "scripts.cli.check_robustness_density"


def record_at_review_verdict(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    verdict: str,
    reviewer_agent_id: str,
    at_ids: list[str],
    at_content_hash: str,
    timestamp: str,
    findings_summary: list[object],
    blocked_by: str | None = None,
) -> None:
    """Append a keyless ATReviewVerdict record to the AT-completion ledger.

    Writes a single JSONL line to ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl``
    carrying the record fields (event, schema_version, slice_id, verdict,
    reviewer_agent_id, at_ids, at_content_hash, timestamp, findings_summary).
    No ``hmac_sha256`` field is written; key absence is a non-event.
    Earlier ledger records are never altered (append-only).

    ``blocked_by`` (DD-2, declared-facts-reachable-recorded slice-01): when a
    downstream gate blocked an otherwise-APPROVED call and the caller
    downgraded ``verdict`` to ``NEEDS_REVISION`` on its own authority, the
    blocking gate's identity is sealed alongside the record. Omitted
    (``None``, the default) for every ordinary APPROVED/NEEDS_REVISION call so
    the record shape is unchanged there.
    """
    record: dict[str, object] = {
        "event": _EVENT,
        "schema_version": _SCHEMA_VERSION,
        "slice_id": slice_id,
        "verdict": verdict,
        "reviewer_agent_id": reviewer_agent_id,
        "at_ids": list(at_ids),
        "at_content_hash": at_content_hash,
        "timestamp": timestamp,
        "findings_summary": list(findings_summary),
    }
    if blocked_by is not None:
        record["blocked_by"] = blocked_by

    # F-13 closure: append through the M7 `AtCompletionLedger` API rather than
    # a hand-written JSONL line. The M7 critical section assigns the monotonic
    # `seq` + `record_hash` every gate-event record carries, so the verdict
    # record shares ONE uniform schema with the rest of the ledger -- the M8
    # carpaccio-order read (`AtCompletionLedger.read_records`) no longer
    # rejects a verdict record interleaved among gate events. The producer's
    # own `timestamp` is preserved (the critical section honours a timestamp
    # already present); the ledger adds only `seq` + `feature_id` + `record_hash`.
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo_root)
    verdict_fields = {
        key: value for key, value in record.items() if key not in ("slice_id", "event")
    }
    ledger.append_review_verdict(slice_id=slice_id, verdict_fields=verdict_fields)


def _consult_robustness_gate(
    repo_root: Path,
    declaration_path: Path,
    at_scope_dir: Path,
) -> tuple[int, str]:
    """Invoke ``check_robustness_density`` as a subprocess; return (exit_code, stdout).

    Slice-05 AT1 wiring (feature-fix-robustness-pbt-density-gate). Runs the
    gate CLI from ``repo_root`` so the namespace package resolution mirrors
    ``run_gate_against_staged_scope`` in the slice's composition root. The
    gate's exit code is the wiring observable; its stdout carries the
    discriminating diagnostic token (e.g. ``RobustnessCoverageMiss``) that
    the verdict producer forwards on its own stderr.
    """
    from des.runtime.interpreter import des_spawn

    completed = des_spawn(
        None,
        _ROBUSTNESS_GATE_MODULE,
        "--declaration",
        str(declaration_path),
        "--at-scope",
        str(at_scope_dir),
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout or ""


def record_review_outcome(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    verdict: str,
    reviewer_agent_id: str,
    at_ids: list[str],
    at_content_hash: str,
    timestamp: str,
    findings_summary: list[object],
    robustness_declaration: Path | None = None,
    robustness_at_scope: Path | None = None,
) -> str:
    """Record a reviewer outcome; return the verdict actually written.

    DD-1 both-outcomes write (declared-facts-reachable-recorded slice-01,
    amending ADR-029 D5's producer half): appends exactly one keyless
    ``ATReviewVerdict`` record for EVERY call, regardless of ``verdict`` --
    bounded-change contract-shape, never zero records, never two. A
    ``NEEDS_REVISION`` verdict is sealed onto the ledger just like an
    ``APPROVED`` one, so a rejection leaves a mechanically-readable trace
    instead of collapsing into "never reviewed" (F3). The control-flow half of
    D5 is UNCHANGED: NEEDS_REVISION still loops the slice back to the
    acceptance-designer -- only the SILENCE on that path is removed.

    Return value: the ``verdict`` string that was actually sealed onto the
    ledger record. This is normally ``verdict`` itself, EXCEPT when the
    robustness-density-gate blocks an otherwise-APPROVED call (DD-2, see
    below) -- there the return value is ``"NEEDS_REVISION"`` even though the
    caller asked for ``"APPROVED"``. Callers that need a human-facing verdict
    (PASS/DEGRADED badge, "recorded"/"skipped" text) MUST key off this return
    value, never off "was something written" -- both outcomes now write, so a
    boolean write-happened signal can no longer stand in for "was it
    approved".

    Slice-05 wiring (AT1), extended by DD-2: when both ``robustness_declaration``
    AND ``robustness_at_scope`` are supplied AND the verdict is APPROVED, the
    producer FIRST consults the robustness density gate CLI. A non-zero gate
    exit BLOCKS the APPROVED write and instead records ``NEEDS_REVISION`` with
    ``blocked_by="robustness-density-gate"`` -- never silence -- while still
    writing the gate's stdout diagnostic to this process's stderr. Existing
    call sites that omit both robustness args keep the slice-01..04 behavior
    verbatim (never consult the gate).
    """
    recorded_verdict = verdict
    blocked_by: str | None = None

    if (
        verdict == _APPROVED
        and robustness_declaration is not None
        and robustness_at_scope is not None
    ):
        gate_exit, gate_stdout = _consult_robustness_gate(
            repo_root, robustness_declaration, robustness_at_scope
        )
        if gate_exit != 0:
            sys.stderr.write(gate_stdout)
            recorded_verdict = _NEEDS_REVISION
            blocked_by = _BLOCKED_BY_ROBUSTNESS_GATE

    record_at_review_verdict(
        repo_root=repo_root,
        feature_id=feature_id,
        slice_id=slice_id,
        verdict=recorded_verdict,
        reviewer_agent_id=reviewer_agent_id,
        at_ids=at_ids,
        at_content_hash=at_content_hash,
        timestamp=timestamp,
        findings_summary=findings_summary,
        blocked_by=blocked_by,
    )
    return recorded_verdict


# ---------------------------------------------------------------------------
# CLI -- friction-fix F-02
# ---------------------------------------------------------------------------
#
# docs/analysis/atdd-pure-dogfooding-friction-2026-05-20.md F-02: the producer
# exposed only library functions, so an operator recording an ATReviewVerdict
# had to hand-script the ``at_ids`` + ``at_content_hash`` derivation against
# ``carpaccio_slice_gate`` internals. This CLI computes those itself by reusing
# the gate's scenario parser, keeping the producer and consumer derivations DRY.


# ---------------------------------------------------------------------------
# rust-regression AT-discovery mode (B-1 bugfix, sister-reported gap) -- the
# Rust mirror of pytest-regression's "one test_* function = one AT", for a
# bugfix's Rust `.rs` regression-test file. Reuses the SHARED scan primitives
# (fix-runner-scope-discover-dedup slice-04) -- cargo_runner's own
# regex and at_discovery.strip_line_comments, by object identity -- rather
# than an independent, byte-identical copy.
# ---------------------------------------------------------------------------


def _malformed_rust_regression_file(detail: str) -> GateError:
    return GateError(
        2,
        {
            "event": "MalformedInput",
            "cause": "the rust regression-test file",
            "error": detail,
        },
    )


def _count_rust_regression_ats(regression_test_file: Path) -> list[str]:
    """AT ids for ``at_kind="rust-regression"`` -- the Rust mirror of
    ``count_pytest_regression_ats``'s module-level ``test_*`` counting.

    Line/regex scan (no Rust parser, no Python ``ast`` on ``.rs`` source) for
    test-attributed function names -- the Rust community idiom (descriptive
    names, not ``test_``-prefixed). Reuses ``cargo_runner._RUST_TEST_FN_RE``
    and ``at_discovery.strip_line_comments`` by object identity
    (fix-runner-scope-discover-dedup slice-04) instead of an independent
    copy of the same pattern/idiom. Raises ``GateError`` exit 2
    (``MalformedInput``, ``cause="the rust regression-test file"``) when the
    file cannot be read or has zero matching functions -- never a
    silently-empty ``at_ids`` list.
    """
    try:
        source = regression_test_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _malformed_rust_regression_file(
            f"cannot read/decode {regression_test_file}: {exc}"
        ) from exc
    at_ids = cargo_runner._RUST_TEST_FN_RE.findall(
        at_discovery.strip_line_comments(source)
    )
    if not at_ids:
        raise _malformed_rust_regression_file(
            f"zero matching test functions found in {regression_test_file}"
        )
    return at_ids


def _rust_regression_content_hash(regression_test_file: Path) -> str:
    """Content-seal for ``at_kind="rust-regression"`` -- sha256 over the raw
    ``.rs`` source bytes, the Rust mirror of ``pytest_regression_content_hash``.
    """
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise _malformed_rust_regression_file(
            f"cannot read {regression_test_file}: {exc}"
        ) from exc
    return hashlib.sha256(source).hexdigest()


def _slice_at_derivation(
    repo_root: Path,
    feature_id: str,
    slice_id: str,
    at_kind: Literal["gherkin", "pytest-regression", "rust-regression"] = "gherkin",
    regression_test_file: Path | None = None,
    *,
    allow_empty_gherkin_scenarios: bool = False,
) -> tuple[list[str], str]:
    """Derive ``(at_ids, at_content_hash)`` for ``slice_id`` (ADR-001 producer mirror).

    ``at_kind="gherkin"`` (default) reuses ``carpaccio_slice_gate``'s ``.feature``
    resolution + parsing + the consumer's ``_at_content_hash`` so the producer
    signs exactly what the gate will later verify. ``carpaccio_slice_gate`` is
    stdlib-only at import time (``yaml`` is imported lazily), so this import
    keeps the bundle safe.

    ``at_kind="pytest-regression"`` (ADR-001, fix-pre-push-hook-dual-installer-
    collision) mirrors the consumer-side derivation in ``carpaccio_format``:
    NET-NEW-counted ``test_*`` functions (bugfix at-review-seal-coherence --
    ``count_net_new_pytest_regression_ats``, the SAME function the gate's own
    assertion-1/assertion-5 checks call, so a regression file SHARED across
    slices can never seal an ``at_ids`` set the gate later disagrees with) for
    ``at_ids`` + a sha256 over the regression file's raw source text for the
    content hash.

    ``at_kind="rust-regression"`` (B-1 bugfix) mirrors ``pytest-regression`` for
    a Rust ``.rs`` regression-test file: ``#[test]``-attributed function names
    for ``at_ids`` + a sha256 over the raw source bytes for the content hash.

    Raises ``ValueError`` (a programming-contract violation, never a
    ``GateError``) when ``at_kind`` is ``"pytest-regression"`` or
    ``"rust-regression"`` and ``regression_test_file=None`` -- only the CLI's
    own arg-parsing can mis-wire this combination.

    ``at_kind="gherkin"`` with ZERO scenarios tagged ``@{slice_id}`` (bugfix
    at-review-seal-coherence, GDP-6): raises the gate's own
    ``_no_scenarios_rejection`` -- the SAME self-explaining ``GateError`` the
    gate's assertion-1 raises for this exact condition -- rather than sealing
    a silent ``sha256("")`` as if an empty AT set were a legitimately-reviewed
    one. ``allow_empty_gherkin_scenarios=True`` (keyword-only) suppresses this
    refusal for callers whose approval authority is a DIFFERENT gate entirely
    (e.g. ``main()`` sets it when ``--robustness-declaration`` +
    ``--robustness-at-scope`` are both supplied -- the robustness density
    gate, not carpaccio scenario tagging, is that call shape's authority; see
    ``record_review_outcome``'s own ``robustness_declaration``/
    ``robustness_at_scope`` gating).
    """
    if (
        at_kind in ("pytest-regression", "rust-regression")
        and regression_test_file is None
    ):
        raise ValueError(
            f"_slice_at_derivation: at_kind={at_kind!r} requires regression_test_file"
        )
    if at_kind == "pytest-regression":
        assert regression_test_file is not None  # guarded above
        from des.cli import carpaccio_format

        at_count = carpaccio_format.count_net_new_pytest_regression_ats(
            regression_test_file,
            repo=repo_root,
            feature_id=feature_id,
            entering_slice=slice_id,
        )
        at_ids = [f"AT-{n}" for n in range(1, at_count + 1)]
        at_content_hash = carpaccio_format.pytest_regression_content_hash(
            regression_test_file
        )
        return at_ids, at_content_hash
    if at_kind == "rust-regression":
        assert regression_test_file is not None  # guarded above
        at_ids = _count_rust_regression_ats(regression_test_file)
        at_content_hash = _rust_regression_content_hash(regression_test_file)
        return at_ids, at_content_hash

    from des.cli import carpaccio_format, carpaccio_slice_gate

    scenarios = carpaccio_slice_gate.parse_scenarios(
        carpaccio_format.read_feature_files(repo_root, feature_id)
    )
    slice_scenarios = [s for s in scenarios if slice_id in s.slice_tags]
    if not slice_scenarios and not allow_empty_gherkin_scenarios:
        raise carpaccio_format._no_scenarios_rejection(repo_root, feature_id, slice_id)
    at_ids = [f"AT-{n}" for n in range(1, len(slice_scenarios) + 1)]
    at_content_hash = carpaccio_slice_gate._at_content_hash(slice_scenarios)
    return at_ids, at_content_hash


def _refuse_unresolvable_feature_slice(
    feature_id: str, slice_id: str, error: str, *, how: str | None = None
) -> GateError:
    """Build the refusal GateError for an unresolvable feature/slice.

    Exit 2, ``ATReviewVerdictRefused`` / ``unresolvable-feature-slice`` --
    self-explaining what/why/how, naming BOTH admissible resolution routes
    (bugfix fix-at-review-verdict-charter-form, slice-01): a feature-delta
    + Slice Plan row, OR an expectation charter (the ``atdd_pure`` bugfix
    lane's own evidence artifact, which never produces a feature-delta).
    Never a bare non-zero exit. ``how`` overrides the default two-route
    message with a more specific remediation naming the PRODUCING TOOL for
    the exact defect diagnosed (round 2: a charter that maps a different
    slice, or one that is present but not yet FILLED).
    """
    return GateError(
        2,
        {
            "event": "ATReviewVerdictRefused",
            "reason": "unresolvable-feature-slice",
            "error": error,
            "how": how
            if how is not None
            else (
                f"resolve {feature_id}/{slice_id} through ONE of two routes "
                "before recording an AT-review verdict: (1) author the "
                f"feature-delta + Slice Plan row at docs/feature/{feature_id}/"
                "feature-delta.md, OR (2) for an atdd_pure bugfix lane (which "
                "never produces a feature-delta), author an expectation "
                f"charter with `des charter-scaffold --feature-id {feature_id} "
                "--seed-mode bug-observable --observable \"<the bug's "
                'observable behaviour>"` -- written under '
                f"docs/product/expectations/{feature_id}/"
            ),
        },
    )


def _refuse_charter_unmapped(
    feature_id: str, slice_id: str, detail: str | None
) -> GateError:
    """FLAG 1 refusal: expectation charter(s) exist under the feature's
    ``docs/product/expectations/`` directory, but none maps ``slice_id`` --
    neither a matching ``slice-NN`` token nor a feature-level scope token.
    """
    return _refuse_unresolvable_feature_slice(
        feature_id,
        slice_id,
        f"docs/product/expectations/{feature_id}/ carries expectation "
        f"charter(s), but none maps {slice_id!r} -- {detail}",
        how=(
            f"edit the mapped charter's ID line so its `Spec rows:` field "
            f"names {slice_id!r} (comma-separated for multiple slices), or "
            f"re-run with the --slice-id the charter actually maps"
        ),
    )


def _refuse_charter_unfilled(
    feature_id: str, slice_id: str, charter_path: Path, missing_sections: list[str]
) -> GateError:
    """FLAG 2 refusal: a charter maps ``slice_id`` but is still a scaffold --
    residual placeholder markers or a missing oracle/preconditions body --
    never adopted practice regardless of the file merely existing.
    """
    return _refuse_unresolvable_feature_slice(
        feature_id,
        slice_id,
        f"expectation charter {charter_path} maps {feature_id}/{slice_id} "
        f"but is not yet FILLED -- {'; '.join(missing_sections)}",
        how=(
            f"verify with `des verify-charter-filled --charter "
            f"{charter_path}` and fill in the sections it names before "
            "recording an AT-review verdict for a charter-only slice"
        ),
    )


def _verify_expectation_charter_arms_slice(
    repo_root: Path, feature_id: str, slice_id: str
) -> None:
    """Refuse unless an expectation charter both MAPS ``slice_id`` (a
    matching ``slice-NN`` token, or a feature-level charter which by
    construction maps ANY slice) and is genuinely FILLED (round 2 of this
    bugfix, after Vera's real-CLI EXAMINE flagged both holes in round 1's
    bare-presence check).

    Routes through ``expectation_charter_mapping.resolve_slice_charter`` --
    the SAME ARMED/UNMAPPED/UNARMED/INDETERMINATE resolution the
    ``commit_slice`` EXAMINE-arming gate already uses -- rather than
    ``has_expectation_charter``'s bare presence check (round 1), which
    accepted ANY ``--slice-id`` once ANY ``*.md`` existed (FLAG 1) and armed
    on an unfilled scaffold (FLAG 2). FILLED-ness reuses
    ``verify_charter_filled.charter_missing_sections`` -- the same
    judgment ``des verify-charter-filled`` renders -- rather than
    re-deriving it. Returns (accepts) only on ``ARMED`` + zero missing
    sections; raises :class:`GateError` (exit 2) on every other outcome.

    ``has_expectation_charter`` itself is UNCHANGED and still the correct,
    weaker, pure-presence semantics for its OTHER caller (the bugfix-lane
    evidence-floor check in ``verify_readiness_pre_dispatch``) -- that
    invariant is untouched by this function.
    """
    mapping = resolve_slice_charter(repo_root, feature_id, slice_id)

    if mapping.state == CharterMappingState.ARMED:
        assert mapping.charter_path is not None  # ARMED always carries a path
        content = mapping.charter_path.read_text(encoding="utf-8")
        missing_sections = charter_missing_sections(content)
        if missing_sections:
            raise _refuse_charter_unfilled(
                feature_id, slice_id, mapping.charter_path, missing_sections
            )
        return

    if mapping.state == CharterMappingState.UNMAPPED:
        raise _refuse_charter_unmapped(feature_id, slice_id, mapping.detail)

    if mapping.state == CharterMappingState.INDETERMINATE:
        raise _refuse_unresolvable_feature_slice(
            feature_id,
            slice_id,
            f"expectation charter mapping for {feature_id}/{slice_id} is "
            f"indeterminate -- {mapping.detail}",
        )

    raise _refuse_unresolvable_feature_slice(
        feature_id,
        slice_id,
        f"no feature-delta at docs/feature/{feature_id}/feature-delta.md "
        f"and no expectation charter at docs/product/expectations/"
        f"{feature_id}/ -- cannot certify a review for a feature/slice "
        "that does not exist",
    )


def _verify_feature_slice_exists(
    repo_root: Path, feature_id: str, slice_id: str
) -> None:
    """Refuse an APPROVED verdict for a feature/slice that does not exist.

    Raises :class:`GateError` (exit 2) when
    ``docs/feature/{feature_id}/feature-delta.md`` is absent AND no
    expectation charter both MAPS ``slice_id`` and is FILLED (see
    ``_verify_expectation_charter_arms_slice``), OR the feature-delta exists
    but ``slice_id`` is not a row in its ``[REF] Slice Plan`` table.

    The expectation-charter form (bugfix fix-at-review-verdict-charter-form)
    is an ADDITIONAL acceptance path consulted ONLY when the feature-delta
    file itself is absent -- an ``atdd_pure`` bugfix lane produces a
    charter, never a feature-delta, so the whole bugfix class was otherwise
    structurally unreachable through this CLI. It is never a bypass: when a
    feature-delta EXISTS, resolution proceeds exactly as before this fix --
    same Slice Plan parse, same refusals. Reuses
    ``carpaccio_format.parse_slice_plan`` -- the same tolerant Slice Plan
    parser the carpaccio entry/exit gates use -- rather than hand-rolling a
    parallel parser (bugfix fix-review-verdict-existence-check, slice-01).
    """
    from des.cli import carpaccio_format

    delta_path = feature_delta_path(repo_root, feature_id)
    if not delta_path.is_file():
        _verify_expectation_charter_arms_slice(repo_root, feature_id, slice_id)
        return

    feature_delta_text = delta_path.read_text(encoding="utf-8")
    try:
        slice_plan = carpaccio_format.parse_slice_plan(feature_delta_text)
    except GateError as parse_error:
        raise _refuse_unresolvable_feature_slice(
            feature_id,
            slice_id,
            f"docs/feature/{feature_id}/feature-delta.md has no valid "
            f"'[REF] Slice Plan' section: {parse_error.payload.get('error')}",
        ) from parse_error

    if slice_plan.row_for(slice_id) is None:
        raise _refuse_unresolvable_feature_slice(
            feature_id,
            slice_id,
            f"{slice_id!r} is not a row in docs/feature/{feature_id}/"
            "feature-delta.md's '[REF] Slice Plan' table",
        )


# ---------------------------------------------------------------------------
# meaningless-identity guard (bugfix fix-at-review-verdict-surface, slice-01)
# ---------------------------------------------------------------------------
#
# RCA Defect 2/3 (docs/feature/fix-at-review-verdict-surface/deliver/rca.md):
# `--reviewer-agent-id`, `--feature-id`, `--slice-id` accepted ANY string
# argparse's `required=True` was satisfied by -- a placeholder token
# (`<id>`, the literal text this codebase's OWN remediation strings print),
# an empty string, or whitespace -- and sealed it verbatim into the
# AT-completion truth-ledger as if it named a real reviewer/feature/slice.
#
# `meaningful_identity` (shared, `des.cli._identity_args`, extracted from
# `commit_slice.py`) already collapses blank/whitespace to `None`. A literal
# `<id>` is neither blank nor whitespace, so `meaningful_identity` alone does
# not catch it -- this module additionally treats an angle-bracket
# placeholder SHAPE as meaningless too, pinning on MEANING rather than
# enumerating every possible junk string.

_PLACEHOLDER_SHAPE_RE = re.compile(r"^<.+>$")


def _meaningful_identity_arg(raw: str) -> str | None:
    """argparse ``type=`` for this module's three identity-bearing flags.

    Applies the shared :func:`meaningful_identity` normalizer (blank/
    whitespace-only collapses to ``None``), then ALSO collapses an
    angle-bracket placeholder token (e.g. ``<id>``, ``<placeholder>``) to
    ``None`` -- a value that LOOKS like a fillable slot is not a real
    identity either.
    """
    value = meaningful_identity(raw)
    if value is None:
        return None
    if _PLACEHOLDER_SHAPE_RE.match(value):
        return None
    return value


def _refuse_meaningless_identity(field: str) -> GateError:
    """Build the refusal GateError for an identity-bearing CLI arg that is
    present (argparse-wise) but names no real thing.

    Exit 2, ``ATReviewVerdictRefused`` / ``meaningless-identity`` -- fires
    BEFORE any ledger write and before the feature/slice existence check, so
    an empty ``--feature-id`` can never reach (and spuriously pass) the
    pathlib empty-path-segment collapse (RCA Defect 3).
    """
    return GateError(
        2,
        {
            "event": "ATReviewVerdictRefused",
            "reason": "meaningless-identity",
            "error": (
                f"--{field} names no real thing -- blank, whitespace-only, "
                "and placeholder tokens (e.g. <id>) are treated as absent, "
                "not as a real identity"
            ),
            "how": f"supply a real --{field}, not a placeholder or blank value",
        },
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="at_review_verdict",
        description=(
            "Record an AT-review verdict (ADR-029 D5 producer, DD-1 "
            "both-outcomes write). A keyless ATReviewVerdict record is "
            "appended to the AT-completion ledger for EVERY verdict -- "
            "APPROVED and NEEDS_REVISION both write; NEEDS_REVISION still "
            "loops the slice back to the acceptance-designer."
        ),
    )
    parser.add_argument("--feature-id", required=True, type=_meaningful_identity_arg)
    parser.add_argument("--slice-id", required=True, type=_meaningful_identity_arg)
    parser.add_argument(
        "--verdict", required=True, choices=["APPROVED", "NEEDS_REVISION"]
    )
    parser.add_argument(
        "--reviewer-agent-id", required=True, type=_meaningful_identity_arg
    )
    parser.add_argument("--findings", nargs="*", default=[])
    add_repo_root_argument(parser, "--repo-root", default=None)
    parser.add_argument(
        "--robustness-declaration",
        default=None,
        help=(
            "Optional path to a robustness unbounded-domains.yaml projection. "
            "When supplied alongside --robustness-at-scope, the producer "
            "consults check_robustness_density at DISTILL exit; a non-zero "
            "gate exit blocks the APPROVED ledger write and surfaces the "
            "gate's stdout diagnostic on this producer's stderr."
        ),
    )
    parser.add_argument(
        "--robustness-at-scope",
        default=None,
        help=(
            "Optional path to the staged AT-scope directory the robustness "
            "gate walks. Required alongside --robustness-declaration to "
            "activate the slice-05 gate-consultation wiring."
        ),
    )
    parser.add_argument(
        "--at-kind",
        choices=["gherkin", "pytest-regression", "rust-regression"],
        default="gherkin",
        help=(
            "AT-discovery mode (ADR-001, fix-pre-push-hook-dual-installer-"
            "collision; 'rust-regression' added B-1). 'gherkin' (default) "
            "derives (at_ids, at_content_hash) from .feature Scenario blocks "
            "-- existing callers see byte-identical behavior. "
            "'pytest-regression' AST-counts module-level test_* functions in "
            "--regression-test-file. 'rust-regression' regex-counts #[test] "
            "functions in a .rs --regression-test-file."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        default=None,
        help=(
            "Repo-relative path to a plain-pytest or Rust regression-test "
            "file. Required iff --at-kind is pytest-regression or "
            "rust-regression."
        ),
    )
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Record an AT-review verdict from the command line.

    Computes ``at_ids`` + ``at_content_hash`` itself from the entering slice's
    scenarios -- the operator supplies only the feature id, slice id, verdict
    and reviewer id. A keyless record is appended to the ledger for EVERY
    verdict (DD-1 both-outcomes write) -- both a feature/slice existence
    refusal (any verdict) and a malformed-input refusal fire before that
    write. Returns 0 on success.
    """
    args = _parse_args(argv)
    repo_root = _resolve_repo_root(args.repo_root)
    at_kind = args.at_kind
    regression_test_file = (
        (repo_root / args.regression_test_file) if args.regression_test_file else None
    )
    try:
        # Meaningless-identity guard (bugfix fix-at-review-verdict-surface,
        # slice-01): `_meaningful_identity_arg` has already collapsed a
        # blank/whitespace/placeholder `--feature-id` / `--slice-id` /
        # `--reviewer-agent-id` to `None` at the parse boundary -- refuse
        # BEFORE any ledger write, and before the feature/slice existence
        # check below (so an empty `--feature-id` never reaches, and can
        # never spuriously pass, the pathlib empty-path-segment collapse).
        if args.feature_id is None:
            raise _refuse_meaningless_identity("feature-id")
        if args.slice_id is None:
            raise _refuse_meaningless_identity("slice-id")
        if args.reviewer_agent_id is None:
            raise _refuse_meaningless_identity("reviewer-agent-id")
        if (
            at_kind in ("pytest-regression", "rust-regression")
            and regression_test_file is None
        ):
            # Only the CLI's own arg-parsing can mis-wire this combination
            # (ADR-001 DD-7; extended B-1 for rust-regression):
            # `_slice_at_derivation` raises `ValueError` on it (a
            # programming-contract violation), so the CLI shell enforces it
            # itself as a `GateError` diagnostic before that function is ever
            # called with `regression_test_file=None`.
            raise GateError(
                2,
                {
                    "event": "MalformedInput",
                    "cause": "the regression-test file",
                    "error": (f"--at-kind={at_kind} requires --regression-test-file"),
                },
            )
        at_ids, at_content_hash = _slice_at_derivation(
            repo_root,
            args.feature_id,
            args.slice_id,
            at_kind=at_kind,
            regression_test_file=regression_test_file,
            # slice-05 robustness-density-gate wiring (fix-robustness-pbt-
            # density-gate): when BOTH robustness flags are supplied, the
            # robustness gate -- consulted below in `record_review_outcome`
            # -- is THIS call shape's approval authority, not carpaccio
            # scenario tagging. An empty gherkin scenario set must not
            # preempt that gate's own (more specific) refusal.
            allow_empty_gherkin_scenarios=(
                args.robustness_declaration is not None
                and args.robustness_at_scope is not None
            ),
        )
        # Existence pre-check (bugfix fix-review-verdict-existence-check,
        # slice-01; extended to NEEDS_REVISION by DD-1,
        # declared-facts-reachable-recorded slice-01): refuse ANY verdict for
        # an imaginary feature/slice BEFORE any ledger write. Originally
        # APPROVED-only because NEEDS_REVISION wrote nothing -- now that
        # NEEDS_REVISION writes a ledger record too (DD-1 both-outcomes), an
        # unguarded NEEDS_REVISION for a non-existent feature/slice would
        # append a record for a thing that does not exist.
        #
        # Ordered AFTER the at-kind checks and `_slice_at_derivation`, not
        # before: those answer "is this invocation well-formed at all", a
        # question that must keep its own (more specific) diagnostic. Hoisting
        # the existence guard above them made a malformed --at-kind on a
        # not-yet-authored feature report `unresolvable-feature-slice`,
        # MASKING the at-kind diagnostic the caller actually needed. The guard
        # still precedes every ledger write, which is the property it exists
        # to hold -- being last among the refusals costs nothing, because all
        # of them refuse before `record_review_outcome` is ever reached.
        _verify_feature_slice_exists(repo_root, args.feature_id, args.slice_id)
    except GateError as gate_error:
        error_line = json.dumps(gate_error.payload, sort_keys=True) + "\n"
        sys.stdout.write(error_line)
        sys.stderr.write(error_line)
        print_human_summary(
            Verdict.FAIL,
            f"AT-review verdict CLI refused: {gate_error.payload.get('error')}",
        )
        return gate_error.exit_code
    timestamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    robustness_declaration = (
        Path(args.robustness_declaration) if args.robustness_declaration else None
    )
    robustness_at_scope = (
        Path(args.robustness_at_scope) if args.robustness_at_scope else None
    )
    recorded_verdict = record_review_outcome(
        repo_root=repo_root,
        feature_id=args.feature_id,
        slice_id=args.slice_id,
        verdict=args.verdict,
        reviewer_agent_id=args.reviewer_agent_id,
        at_ids=at_ids,
        at_content_hash=at_content_hash,
        timestamp=timestamp,
        findings_summary=list(args.findings),
        robustness_declaration=robustness_declaration,
        robustness_at_scope=robustness_at_scope,
    )
    # DD-1 (declared-facts-reachable-recorded slice-01): both outcomes now
    # write a ledger record (bounded-change: exactly one per call), so
    # `verdict_written` is unconditionally True -- it stopped being a proxy
    # for "was it approved" the moment NEEDS_REVISION started writing too.
    # Every human/JSON-facing signal below keys on `recorded_verdict` (the
    # verdict `record_review_outcome` actually sealed onto the ledger),
    # never on "did we write".
    approved = recorded_verdict == _APPROVED
    outcome = "recorded" if approved else f"recorded ({recorded_verdict})"
    event_line = (
        json.dumps(
            {
                "event": "ATReviewVerdictCLI",
                "feature_id": args.feature_id,
                "slice_id": args.slice_id,
                "verdict": args.verdict,
                "verdict_written": True,
                "outcome": outcome,
            },
            sort_keys=True,
        )
        + "\n"
    )
    # Pre-existing machine-readable contract keeps the JSON event on stdout
    # (no breaking change for existing CI / hook consumers); the slice-02
    # surface co-emits it on stderr alongside a colored human-readable line.
    # Verdict mapping per slice-02, re-keyed on `recorded_verdict` by DD-1: an
    # APPROVED record -> ✅ PASS; a NEEDS_REVISION record (requested directly,
    # OR DD-2's robustness-gate block downgrading an APPROVED request) ->
    # ⚠️ DEGRADED. NEVER PASS merely because a ledger write happened.
    sys.stdout.write(event_line)
    sys.stderr.write(event_line)
    human_verdict = Verdict.PASS if approved else Verdict.DEGRADED
    summary = (
        f"AT-review {args.verdict} recorded for {args.feature_id}/{args.slice_id}"
        if approved
        else (
            f"AT-review {args.verdict} -- {args.feature_id}/{args.slice_id} "
            f"needs revision ({recorded_verdict} recorded)"
        )
    )
    print_human_summary(human_verdict, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
