"""Carpaccio slice gate CLI -- the ATDD-pure DELIVER entry gate.

ADR-028 D2-bis (carpaccio assertions 1-4) + ADR-029 D5 (assertion 5, the
AT-review gate). Runs as a DES ``entry_gate`` before ``A_GREEN_ATS``: a slice
reaches implementation only when BOTH halves clear -- the carpaccio
decomposition check (the slice is a thin enough vertical) AND the AT-review
check (the slice's acceptance tests were reviewed and approved).

F-11 (atdd-pure-dogfooding-friction-2026-05-20.md): this gate is an importable
``des.cli`` module so it SHIPS with the ``des`` package and is invokable
layout-independently as a module -- the same shape U2
(``des.cli.verify_slice_commit_completeness``) uses, run as a subprocess by the
U1 hook. The legacy ``scripts/cli/carpaccio_slice_gate.py`` path survives as a
thin shim that re-exports this module.

Modelled on ``cohort_classifier.py``: single-file core CLI, single-line JSON
output, explicit exit codes, pure-function -- the gate reads the feature-delta
+ ``.feature`` files + the AT-completion ledger and returns a verdict (exit
code + JSON); it performs NO filesystem mutation.

NOTE (evolution-plan P1.2, User-Examiner spine wiring): this module's
assertion 5 (``check_at_review``) is the DISTILL-exit AT-review gate -- it is
NOT the per-slice C_REVIEWER_AUDIT / EXAMINE clearing route. The commit-time
examine-verdict gate that REPLACES the per-slice code-reading review lives at
the per-slice COMMIT chokepoint instead: see
``des.cli.commit_slice.check_examine_verdict`` + the ``ATDDPurePhase.EXAMINE``
value-alias in ``des.domain.atdd_pure_phases``. Neither module imports the
other; this note exists only so a reader does not conflate the two gates.

Exit codes:
    0  -- the slice is cleared to enter implementation
    1  -- the feature-delta or its ``[REF] Slice Plan`` section is absent
    2  -- malformed input (the slice-plan table OR a ``.feature`` slice tag);
          the emitted JSON ``cause`` field names which input to repair
    44 -- CARPACCIO_SLICE_TOO_LARGE: oversized / coverage / ordering violation
    45 -- AT_REVIEW_NOT_APPROVED: assertion 5 failed (one of four closed reasons)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    _predecessor_slice,
    _slice_number,
)

# Mechanical-seal alternative to the LLM AT-review verdict (evolution-plan
# P1.1, pytest-regression mode only): the RED-observed seal predicates live in
# their P0 SSOT modules; the gate imports them so seal-path/content-hash and
# negative-AT semantics can never drift from `des verify-red-green` /
# `des verify-negative-at`.
from des.cli.carpaccio_format import (
    GateError,
    Scenario,
    SlicePlan,
    _at_review_rejection,
    _feature_tag_files,
    _lane_profile_for_slice,
    _read_feature_files,
    _resolve_slice_max,
    _slice_scenarios,
    check_carpaccio,
    count_net_new_pytest_regression_ats,
    count_pytest_regression_ats,
    parse_scenarios,
    parse_slice_plan,
    pytest_regression_content_hash,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.verify_negative_at import _scan_file as _scan_negative_at_file
from des.cli.verify_red_green import _content_sha as _red_seal_content_sha
from des.cli.verify_red_green import _seal_path as _red_green_seal_path
from des.domain.at_review_signing import (
    canonical_at_review_json,
)
from des.domain.lane_profile import GuardKind
from des.domain.repo_path_resolver import (
    feature_delta_path as _feature_delta_path,
)
from des.domain.repo_path_resolver import (
    resolve_repo_root as _repo_root,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from des.ports.driven_ports.commit_diff_port import CommitDiffPort


# Re-export the format predicates the gate composes with so existing importers
# of ``carpaccio_slice_gate`` (and the gate's own ``main``) resolve them here
# one-directionally (ADR-001: carpaccio_slice_gate -> carpaccio_format, never
# the reverse). The names below are the gate's public/shared surface.
__all__ = [
    "GateError",
    "Scenario",
    "SlicePlan",
    "_feature_tag_files",
    "canonical_at_review_json",
    "check_at_review",
    "check_carpaccio",
    "count_pytest_regression_ats",
    "main",
    "parse_scenarios",
    "parse_slice_plan",
    "pytest_regression_content_hash",
]


# ---------------------------------------------------------------------------
# fix-mandate-9-v2-rollout slice-01 — detector + catalog reader (A_GREEN_ATS)
# ---------------------------------------------------------------------------
#
# Three new public surfaces ship in slice-01 per spike v2 §7 walking-skeleton-
# first ordering: a stdlib reader of the `slice_kinds:` catalog vocabulary, a
# structured-event detector for `@real-io` tag-vs-composition mismatch, and a
# retro-audit artifact scaffold (the 5-column markdown table lives at
# `docs/architecture/at-real-io-audit-2026-05-27.md`, slice-01 ships the
# header row; slice-03 populates the body rows).


# Mock/stub adapter constructor name prefixes — used by the slice-01 detector
# as a closed-vocabulary heuristic for the "@real-io vs mock-only composition"
# mismatch case. The full Adapter Criticality table is project-local and lands
# in slice-03 per `feature-delta.md` "NOT in slice-01 scope". This minimal
# vocabulary covers the slice-01 detector contract per DD-4.
_MOCK_ADAPTER_NAME_PREFIXES: tuple[str, ...] = ("Mock", "Stub", "Fake", "InMemory")


@dataclass(frozen=True)
class MandateNineTagMismatchEvent:
    """Structured detector event per DD-4 contract.

    DD-4 stderr-event shape:
        {"event": "MandateNineTagMismatch", "scenario_file": ...,
         "scenario_line": ..., "tag_asserted": ..., "composition_evidence": [...],
         "verdict_recommendation": ..., "severity": "WARNING"}

    The dataclass surface a step body asserts against carries the three
    composition-readable fields (event_name, is_mismatch, severity); the full
    DD-4 payload is also serialized to stderr as a single JSON object so
    downstream tooling (audit doc populator, log scrapers) consumes the
    structured event uniformly with the rest of the carpaccio gate emissions.
    """

    event_name: str
    is_mismatch: bool
    severity: str


def read_slice_kinds_from_catalog(repo_root: Path) -> tuple[str, ...]:
    """Read the `slice_kinds:` vocabulary from `nWave/framework-catalog.yaml`.

    Returns the tuple of registered `id` values in catalog order. Stdlib-only
    scan per F-11 (the gate ships as a `des.cli` module and the DES bundle
    scan forbids `import yaml` in bundled modules), parsing exactly the
    two-level block-mapping shape the catalog uses:

        slice_kinds:
          - id: walking_skeleton
            description: ...
          - id: coupled
            description: ...

    Comment lines + blank lines inside the block are skipped; the block ends
    at the first non-indented non-comment line.
    """
    catalog_path = repo_root / "nWave" / "framework-catalog.yaml"
    text = catalog_path.read_text(encoding="utf-8")
    return _scan_slice_kind_ids(text)


def _scan_slice_kind_ids(text: str) -> tuple[str, ...]:
    """Stdlib parser for the `slice_kinds:` block of `framework-catalog.yaml`.

    Returns the ordered tuple of `id:` values nested under the `slice_kinds:`
    top-level key. Deliberately narrow: parses exactly the one block shape
    the catalog ships, not arbitrary YAML.
    """
    ids: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            in_block = stripped == "slice_kinds:"
            continue
        if not in_block:
            continue
        if stripped.startswith("- id:"):
            ids.append(stripped[len("- id:") :].strip())
    return tuple(ids)


def detect_mandate_nine_tag_mismatch(
    *,
    scenario_tag: str,
    composition_evidence: tuple[str, ...],
    scenario_file: str,
    scenario_line: int,
) -> MandateNineTagMismatchEvent:
    """Detect Mandate 9 v2 tag-vs-composition inconsistency.

    Non-blocking warning when a scenario carries `@real-io` but its composition
    root constructs only mock/stub adapters. Per Sentinel residuality probe 4
    (spike v2 §DD-1), the detector consumes the pre-resolved composition
    evidence tuple (adapter constructor names harvested from step-body +
    fixture-factory AST scan) — it does NOT do its own AST walk. Module-level
    imports are excluded by the upstream harvester (slice-02 surface).

    Emits the DD-4 structured JSON event on stderr when a mismatch is
    detected. Exit code is unaffected (the gate stays exit 0); slice-03
    promotes the warning to BLOCKING once F-AT-REAL-IO-TAG-MECHANICAL-AUDIT
    closes.
    """
    is_mismatch = _is_real_io_mock_only_mismatch(scenario_tag, composition_evidence)
    severity = "WARNING"
    event = MandateNineTagMismatchEvent(
        event_name="MandateNineTagMismatch",
        is_mismatch=is_mismatch,
        severity=severity,
    )
    if is_mismatch:
        _emit_tag_mismatch_event(
            scenario_file=scenario_file,
            scenario_line=scenario_line,
            tag_asserted=scenario_tag,
            composition_evidence=composition_evidence,
            severity=severity,
        )
    return event


# ---------------------------------------------------------------------------
# fix-mandate-9-v2-rollout slice-03 — BLOCKING-mode detector
# ---------------------------------------------------------------------------
#
# Slice-03 promotes the MandateNineTagMismatch warning from non-blocking
# (severity=WARNING, exit code unaffected) to BLOCKING (severity=BLOCKING,
# raises GateError with exit_code=44 on mismatch). The function reuses
# `_is_real_io_mock_only_mismatch` (predicate from slice-01) so the
# mismatch semantics are byte-equivalent across modes; only the action on
# mismatch differs (warning stderr emission vs hard gate error).


def detect_mandate_nine_tag_mismatch_blocking(
    *,
    scenario_tag: str,
    composition_evidence: tuple[str, ...],
    scenario_file: str,
    scenario_line: int,
    blocking_mode: bool,
) -> MandateNineTagMismatchEvent:
    """Detect Mandate 9 v2 tag-vs-composition inconsistency in BLOCKING mode.

    When `blocking_mode=True` AND the (scenario_tag, composition_evidence)
    pair satisfies `_is_real_io_mock_only_mismatch(...)`, raises
    `GateError(exit_code=44, payload=...)` with the DD-4 structured payload
    and severity="BLOCKING". The carpaccio gate's main() catches and emits
    the payload on stdout+stderr before returning exit code 44.

    When `blocking_mode=False` OR no mismatch is detected, delegates to
    `detect_mandate_nine_tag_mismatch` (the non-blocking warning path) and
    returns its event — preserves byte-equivalence with slice-01 semantics
    so the warning-only mode survives the promotion.
    """
    if blocking_mode and _is_real_io_mock_only_mismatch(
        scenario_tag, composition_evidence
    ):
        raise GateError(
            44,
            {
                "event": "MandateNineTagMismatch",
                "severity": "BLOCKING",
                "scenario_file": scenario_file,
                "scenario_line": scenario_line,
                "tag_asserted": scenario_tag,
                "composition_evidence": list(composition_evidence),
                "verdict_recommendation": ("re-tag @in-memory or wire real adapter"),
            },
        )
    return detect_mandate_nine_tag_mismatch(
        scenario_tag=scenario_tag,
        composition_evidence=composition_evidence,
        scenario_file=scenario_file,
        scenario_line=scenario_line,
    )


def _is_real_io_mock_only_mismatch(
    scenario_tag: str, composition_evidence: tuple[str, ...]
) -> bool:
    """Predicate: scenario tagged `@real-io` but composition is mock-only.

    Mismatch holds when the asserted tag is `@real-io` AND the composition
    evidence is non-empty AND every adapter constructor name matches a mock-
    family prefix. An empty evidence tuple is NOT a mismatch (no claim made
    by the composition; the detector stays silent rather than emit a noisy
    warning on harvest miss).
    """
    if scenario_tag != "@real-io":
        return False
    if not composition_evidence:
        return False
    return all(_is_mock_adapter_name(name) for name in composition_evidence)


def _is_mock_adapter_name(name: str) -> bool:
    """Predicate: adapter constructor `name` starts with a mock-family prefix."""
    return any(name.startswith(prefix) for prefix in _MOCK_ADAPTER_NAME_PREFIXES)


def _emit_tag_mismatch_event(
    *,
    scenario_file: str,
    scenario_line: int,
    tag_asserted: str,
    composition_evidence: tuple[str, ...],
    severity: str,
) -> None:
    """Emit the DD-4 structured JSON event to stderr (single line)."""
    payload = {
        "event": "MandateNineTagMismatch",
        "scenario_file": scenario_file,
        "scenario_line": scenario_line,
        "tag_asserted": tag_asserted,
        "composition_evidence": list(composition_evidence),
        "verdict_recommendation": "re-tag @in-memory or wire real adapter",
        "severity": severity,
    }
    sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")


# ``canonical_at_review_json`` lives in the ``des.domain.at_review_signing``
# SSOT (ADR-029 D5, AD-05) and is re-exported (``__all__``) so existing
# importers of this CONSUMER gate keep resolving it.


# ---------------------------------------------------------------------------
# Repo / path resolution
# ---------------------------------------------------------------------------


def _ledger_path(repo: Path, feature_id: str) -> Path:
    return repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"


# ---------------------------------------------------------------------------
# Assertion 5 -- the AT-review gate (ADR-029 D5)
# ---------------------------------------------------------------------------


def _latest_verdict_record(
    ledger_path: Path, slice_id: str
) -> dict[str, object] | None:
    """Select the latest ATReviewVerdict record for the entering slice."""
    if not ledger_path.is_file():
        return None
    latest: dict[str, object] | None = None
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("event") != "ATReviewVerdict":
            continue
        if record.get("slice_id") != slice_id:
            continue
        latest = record
    return latest


_AT_REVIEW_REJECTED_EXIT = 45

# Attestation labels for the SliceCleared ``at_evidence`` field
# (pytest-regression mode only -- the gherkin payload stays byte-identical).
_AT_EVIDENCE_REVIEWER_VERDICT = "reviewer-verdict"
_AT_EVIDENCE_MECHANICAL_SEAL = "mechanical-seal"

# Green-to-Green Seal attestation labels (D8, f-prefactoring-dispatch-clears-
# honestly slice-02): a prefactoring (0-AT, behavior-preserving) has no
# RED->GREEN seal analog, so its evidence is the 3 REUSED green-to-green facts
# (green-before, green-after, no-test-file-in-diff) instead. DISTINCT from the
# COMMIT-verified label so an honest ledger never conflates a provisional
# ENTRY acceptance (substance verified later, at COMMIT) with a genuine
# COMMIT-time verification.
_AT_EVIDENCE_GREEN_TO_GREEN = "green-to-green-verified"
_AT_EVIDENCE_GREEN_TO_GREEN_PENDING = "green-to-green-pending"

_MECHANICAL_OR_VERDICT_HOW = (
    "satisfy assertion 5 by EITHER (a) minting an APPROVED ATReviewVerdict "
    "for this slice in the AT-completion ledger, OR (b) recording the "
    "mechanical pair: `des verify-red-green --record-red --test-file "
    "<regression-test-file>` (the RED seal must match the CURRENT file "
    "content) AND a negative AT in that same file so `des verify-negative-at "
    "--test-file <regression-test-file> --all-critical` passes."
)


def check_at_review(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    scenarios: list[Scenario],
    at_kind: Literal["gherkin", "pytest-regression"] = "gherkin",
    regression_test_file: Path | None = None,
    *,
    plan: SlicePlan | None = None,
    commit_sha: str | None = None,
    commit_diff_port: CommitDiffPort | None = None,
) -> str | None:
    """Run assertion 5 (ADR-029 D5). Raises ``GateError`` exit 45 on failure.

    Green-to-Green Seal (D7-D12, ADD-not-mutate, keyword-only, all default
    ``None``): ``plan``, ``commit_sha``, ``commit_diff_port`` thread the
    lane-exemption evidence through the SAME seam both production callers use
    (``carpaccio_slice_gate.main`` at ENTRY, ``verify_commit_trailers.
    _audit_slice`` at COMMIT). Every existing caller (both production sites
    and the pre-existing test caller) stays byte-identical -- none passes
    these new kwargs. When ``plan`` is given AND the entering slice's Slice-
    Plan row resolves (via the shared ``_lane_profile_for_slice`` helper) to a
    lane whose ``guard_kind`` is ``GREEN_TO_GREEN``, the legacy ledger-record
    check is BYPASSED entirely in favor of :func:`_check_green_to_green` --
    see that function's docstring for the 3-fact substance-evidence.

    Record-presence is the whole control: an absent or non-APPROVED record
    refuses the slice fail-closed. No signing key is resolved -- the veto is
    the presence of a well-formed APPROVED record that binds the AT set and
    content seal. A stray ``hmac_sha256`` field on a pre-existing record is
    tolerated-and-ignored (upgrade compatibility, D-tolerate-old).

    F-03 (atdd-pure-dogfooding-friction-2026-05-20.md): an entering slice
    that maps to ZERO ``@slice-NN`` scenarios is rejected loud (reason
    ``no-scenarios-for-slice``), never cleared vacuously on an empty AT set.

    ``at_kind="gherkin"`` (default) preserves byte-identical behavior for
    every existing caller and returns ``None``. ``at_kind="pytest-regression"``
    (ADR-001, fix-pre-push-hook-dual-installer-collision) REUSES the
    record-presence / APPROVED / stale-AT-set / stale-content-hash control
    flow UNCHANGED -- only the AT-count + content-hash SOURCE differs:
    AST-counted ``test_*`` functions + a sha256 over the regression file's
    raw source text, in place of the Gherkin scenario count +
    ``_at_content_hash``.

    Mechanical-seal alternative (evolution-plan P1.1, ADD-not-mutate,
    pytest-regression mode ONLY): assertion 5 is satisfied by EITHER the
    legacy ``ATReviewVerdict`` (checked first, unchanged) OR the mechanical
    pair -- a fresh ``RedObserved`` seal for the regression file (P0.2,
    ``des verify-red-green --record-red``; stale/tampered content voids it,
    the same staleness semantics as the verdict path) AND the negative-AT
    mandate satisfied for that file (P0.3, ``--all-critical`` semantics).
    Returns the attestation that cleared the slice (``"reviewer-verdict"`` /
    ``"mechanical-seal"``) so the ledger distinguishes the two. When BOTH
    fail, the verdict path's rejection is re-raised fail-closed with its
    ``how`` naming both remedies.
    """
    if plan is not None:
        lane_profile = _lane_profile_for_slice(plan, entering_slice)
        if (
            lane_profile is not None
            and lane_profile.guard_kind is GuardKind.GREEN_TO_GREEN
        ):
            return _check_green_to_green(
                repo, feature_id, entering_slice, commit_sha, commit_diff_port
            )
    if at_kind == "pytest-regression" and regression_test_file is None:
        raise ValueError(
            "check_at_review: at_kind='pytest-regression' requires regression_test_file"
        )
    if at_kind != "pytest-regression":
        _check_verdict_record(
            repo, feature_id, entering_slice, scenarios, at_kind, regression_test_file
        )
        return None
    assert regression_test_file is not None  # guarded above
    try:
        _check_verdict_record(
            repo, feature_id, entering_slice, scenarios, at_kind, regression_test_file
        )
    except GateError as rejection:
        if rejection.exit_code != _AT_REVIEW_REJECTED_EXIT:
            raise  # malformed-input diagnostics (exit 2) propagate untouched
        if _mechanical_seal_satisfied(repo, regression_test_file):
            return _AT_EVIDENCE_MECHANICAL_SEAL
        raise _with_mechanical_remedy(rejection) from None
    return _AT_EVIDENCE_REVIEWER_VERDICT


def _check_green_to_green(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    commit_sha: str | None,
    commit_diff_port: CommitDiffPort | None,
) -> str:
    """The Green-to-Green Seal (D7-D12): the honest evidence for a 0-AT
    behavior-preserving prefactoring.

    A prefactoring has no RED->GREEN seal analog -- the honest substance-
    evidence a commit-time gate can check is 3 REUSED facts:

    1. green-before -- the predecessor slice's own `SliceCommitVerified`
       ledger record already attests its full suite was green (D9). `slice-01`
       has no predecessor and passes this fact vacuously.
    2. green-after -- the entering slice ITSELF carries a `SliceCommitVerified`
       record (D9) -- reusing the commit gate's own full-suite run.
    3. no-test-file-in-diff -- the commit's diff touches no test path (D10,
       anti-gaming): a "prefactoring" that also weakens/adds a test is a
       disguised behavior change.

    At ENTRY (``commit_sha=None``) the commit does not exist yet -- no diff to
    read, no commit-time ledger record to expect yet -- so the lane clears
    IMMEDIATELY with the PENDING label (D8): the lane's `at_requirement` is
    EXEMPT, so entry never blocks on it; substance is verified at COMMIT,
    where the evidence genuinely exists.

    At COMMIT (``commit_sha`` given) all 3 facts are checked, in order; a
    `commit_diff_port` degrading to ``Indeterminate`` (git absent, ANY
    reason) surfaces `GateError(7, ATReviewIndeterminate)` -- fail-closed,
    NEVER a silent pass.
    """
    if commit_sha is None:
        return _AT_EVIDENCE_GREEN_TO_GREEN_PENDING
    ledger = AtCompletionLedger(feature_id, repo)
    verified = ledger.verified_slices()
    try:
        entering_number = _slice_number(entering_slice)
    except ValueError as exc:
        # D5 (friction #10 parity): `_SLICE_ID_RE` accepts a letter-suffixed
        # slice id (`slice-02b`) as VALID throughout the rest of the carpaccio
        # machinery, but `_slice_number`'s bare `int(...)` cannot parse one.
        # A COMMIT-time green-to-green consultation for such an id must refuse
        # cleanly (GateError), never let the raw ValueError escape uncaught.
        raise _at_review_rejection("malformed-slice-id", entering_slice) from exc
    if entering_number > 1:
        predecessor = _predecessor_slice(entering_slice)
        if predecessor not in verified:
            raise _at_review_rejection("green-before-absent", entering_slice)
    if entering_slice not in verified:
        raise _at_review_rejection("green-after-red", entering_slice)
    assert commit_diff_port is not None  # the CLI/hook seam always supplies one
    changed_paths = commit_diff_port.changed_paths(repo, commit_sha)
    if isinstance(changed_paths, Indeterminate):
        raise GateError(
            7,
            {
                "event": "ATReviewIndeterminate",
                "slice_id": entering_slice,
                "reason": changed_paths.reason,
                "error": (
                    f"green-to-green seal for slice {entering_slice} is "
                    f"INDETERMINATE: {changed_paths.reason}"
                ),
            },
        )
    if any(_is_test_path(path) for path in changed_paths):
        raise _at_review_rejection("test-file-in-diff", entering_slice)
    return _AT_EVIDENCE_GREEN_TO_GREEN


def _is_test_path(path: str) -> bool:
    """True when ``path`` is a test file (a ``tests/`` segment or ``test_*``/``*_test``)."""
    parts = path.split("/")
    if "tests" in parts or "test" in parts:
        return True
    name = parts[-1] if parts else path
    return name.startswith("test_") or name.endswith(("_test.py", "_test.ts"))


def _check_verdict_record(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    scenarios: list[Scenario],
    at_kind: Literal["gherkin", "pytest-regression"],
    regression_test_file: Path | None,
) -> None:
    """The legacy ``ATReviewVerdict`` record check -- extracted verbatim.

    Byte-identical to the pre-P1.1 ``check_at_review`` body: record presence,
    APPROVED verdict, AT-set match, content-seal match. Raises the closed
    ``ATReviewGateRejected`` reasons (exit 45) exactly as before.
    """
    record = _latest_verdict_record(_ledger_path(repo, feature_id), entering_slice)
    if record is None:
        raise _at_review_rejection("absent", entering_slice)

    if record.get("verdict") != "APPROVED":
        raise _at_review_rejection("not-approved", entering_slice)

    if at_kind == "pytest-regression":
        assert regression_test_file is not None  # guarded by check_at_review
        at_count = count_net_new_pytest_regression_ats(
            regression_test_file,
            repo=repo,
            feature_id=feature_id,
            entering_slice=entering_slice,
        )
        expected_hash = pytest_regression_content_hash(regression_test_file)
    else:
        slice_scenarios = _slice_scenarios(scenarios, entering_slice)
        at_count = len(slice_scenarios)
        expected_hash = _at_content_hash(slice_scenarios)

    expected_ids = {f"AT-{n}" for n in range(1, at_count + 1)}
    record_ids = record.get("at_ids")
    if not isinstance(record_ids, list) or set(record_ids) != expected_ids:
        raise _at_review_rejection("stale-at-set", entering_slice)

    if record.get("at_content_hash") != expected_hash:
        raise _at_review_rejection("stale-at-content", entering_slice)


def _mechanical_seal_satisfied(repo: Path, regression_test_file: Path) -> bool:
    """The P0 mechanical pair: fresh RED seal AND negative-AT satisfied.

    Fail-closed on every degraded input (seal absent, unreadable, malformed,
    content-stale, no witnessed failure; regression file unanalyzable or
    carrying zero negative ATs) -- a ``False`` here falls back to the verdict
    path's rejection, never a silent clear.
    """
    if not _red_seal_fresh(repo, regression_test_file):
        return False
    return _negative_at_satisfied(regression_test_file)


def _red_seal_fresh(repo: Path, regression_test_file: Path) -> bool:
    """A ``RedObserved`` seal (P0.2) exists and matches the CURRENT content.

    Reuses ``verify_red_green``'s own seal-path + content-sha helpers over
    RESOLVED paths (the seal producer resolves both) so the slug and the hash
    can never diverge from the producer. Freshness = the recorded
    ``content_sha256`` equals the file's current sha256 (any post-RED edit
    voids the evidence -- the same tamper semantics as the verdict path) AND
    the seal witnessed >=1 failing test (a seal without a witnessed RED
    proves nothing and never clears).
    """
    try:
        seal = _red_green_seal_path(repo.resolve(), regression_test_file.resolve())
    except ValueError:
        return False  # the regression file is not under the repo root
    if not seal.is_file():
        return False
    try:
        record = json.loads(seal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, dict):
        return False
    outcomes = record.get("outcomes")
    if not isinstance(outcomes, dict) or "fail" not in outcomes.values():
        return False
    try:
        current_sha = _red_seal_content_sha(regression_test_file)
    except OSError:
        return False
    return record.get("content_sha256") == current_sha


def _negative_at_satisfied(regression_test_file: Path) -> bool:
    """The negative-AT mandate (P0.3) holds for the regression file.

    ``--all-critical`` semantics: the whole file is one critical scope,
    satisfied by >=1 negative AT anywhere within it (the ``verify_negative_at``
    convention: ``@pytest.mark.negative_at`` or a ``_not_``/``_never_``/
    ``_rejects_``/``_refuses_``/``_fails_`` name token). Delegates to the
    P0.3 SSOT scanner; its degrade-loud output is suppressed here because an
    unanalyzable file is simply NOT satisfied (fail-closed) and the gate's
    stdout must stay a single JSON verdict line.
    """

    with contextlib.redirect_stdout(io.StringIO()):
        scan = _scan_negative_at_file(regression_test_file)
    if isinstance(scan, int):
        return False  # unanalyzable -> fail-closed, never a silent pass
    return bool(scan.negative_cases())


def _with_mechanical_remedy(rejection: GateError) -> GateError:
    """Extend an assertion-5 rejection's remediation to name BOTH remedies.

    ADD-not-mutate: the payload's existing fields (event, slice_id, reason,
    error) are untouched; only the what/why/how-mandated ``how`` is added so
    the operator learns the mechanical-seal remedy exists alongside the
    reviewer verdict.
    """
    payload = dict(rejection.payload)
    payload["how"] = _MECHANICAL_OR_VERDICT_HOW
    return GateError(rejection.exit_code, payload)


def _at_content_hash(slice_scenarios: list[Scenario]) -> str:
    """SHA-256 over the sorted concatenation of normalized scenario bodies."""
    bodies = sorted(s.normalized_body for s in slice_scenarios)
    return hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CLI shell
# ---------------------------------------------------------------------------


_CLEAR_CLASS_EVENTS = frozenset(
    {"SliceCleared", "CoupledSliceAccepted", "LaneAtExemptionAccepted"}
)


def _emit(payload: dict[str, object]) -> None:
    """Emit the verdict on BOTH stdout and stderr plus a human-readable line.

    The pre-existing machine-readable contract keeps the JSON event on stdout
    (no breaking change for existing pre-commit / CI / hook consumers); the
    slice-02 surface co-emits the event on stderr alongside a short colored
    human-readable verdict line so a single channel carries both surfaces.

    Verdict mapping: clear-class events (``SliceCleared``,
    ``CoupledSliceAccepted``) → ✅ PASS (exit 0, the slice IS cleared); every
    other event (``CARPACCIO_SLICE_TOO_LARGE``, ``SlicePlanSectionMissing``,
    ``AT_REVIEW_NOT_APPROVED``, malformed-input verdicts) → ❌ FAIL.
    ``CoupledSliceAccepted`` clears via the coupled-AT-group escape (assertion 5
    already passed before ``_emit`` runs); the machine JSON event is unchanged
    so hooks/CI can still branch on the distinct event name.
    """
    line = json.dumps(payload, sort_keys=True) + "\n"
    sys.stdout.write(line)
    sys.stderr.write(line)
    event = payload.get("event")
    verdict = Verdict.PASS if event in _CLEAR_CLASS_EVENTS else Verdict.FAIL
    slice_id = payload.get("slice_id") or payload.get("entering_slice")
    feature_id = payload.get("feature_id")
    if event == "SliceCleared":
        summary = (
            f"carpaccio slice {slice_id} cleared"
            if slice_id
            else "carpaccio slice cleared"
        )
    elif event == "CoupledSliceAccepted":
        summary = (
            f"carpaccio slice {slice_id} cleared via coupled-AT-group escape"
            if slice_id
            else "carpaccio slice cleared via coupled-AT-group escape"
        )
    elif event == "LaneAtExemptionAccepted":
        lane = payload.get("lane")
        summary = (
            f"carpaccio slice {slice_id} cleared via the {lane} lane exemption"
            if slice_id
            else "carpaccio slice cleared via the lane exemption"
        )
    else:
        error = payload.get("error")
        head = (
            f"carpaccio gate refused ({event})" if event else "carpaccio gate refused"
        )
        summary = (
            f"{head}: {error}"
            if isinstance(error, str) and error
            else f"{head} for feature {feature_id}"
            if feature_id
            else head
        )
    print_human_summary(verdict, summary)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="des carpaccio-slice-gate",
        description=(
            "ATDD-pure DELIVER entry gate: carpaccio decomposition (ADR-028 "
            "D2-bis) + AT-review (ADR-029 D5)."
        ),
        epilog=(
            "Exit codes: 0 cleared | 1 missing slice plan | 2 malformed input "
            "| 44 oversized slice | 45 AT-review not approved."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--entering-slice", required=True)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument(
        "--enforce-sad-path-floor",
        action="store_true",
        help=(
            "Co-emit the ZOMBIES-zero sad-path floor verdict "
            "(at-in-process-port-default slice-03): FLAG a slice with zero @error "
            "acceptance tests. Off by default -- existing callers see byte-identical "
            "output."
        ),
    )
    parser.add_argument(
        "--at-kind",
        choices=["gherkin", "pytest-regression"],
        default="gherkin",
        help=(
            "AT-discovery mode (ADR-001, fix-pre-push-hook-dual-installer-"
            "collision). 'gherkin' (default) discovers ATs from .feature "
            "Scenario blocks -- existing callers see byte-identical behavior. "
            "'pytest-regression' AST-counts module-level test_* functions in "
            "--regression-test-file."
        ),
    )
    parser.add_argument(
        "--regression-test-file",
        default=None,
        help=(
            "Repo-relative path to a plain-pytest regression-test file. "
            "Required iff --at-kind=pytest-regression."
        ),
    )
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def _emit_sad_path_floor(repo: Path, feature_id: str, entering_slice: str) -> None:
    """Co-emit the ZOMBIES-zero sad-path floor verdict (at-in-process-port-default).

    Runs the shared sad-path floor over the entering slice's ``@error`` AT count.
    A slice with zero error-path ATs is FLAGGED with the structured event
    ``SadPathFloorFlagged`` co-emitted on stderr (the gate's existing dual-channel
    pattern) -- this never alters the existing clear/refuse exit codes; it is an
    additive non-vacuity floor. A slice carrying >=1 error-path AT is silent.
    """
    from des.cli.axis_b_levers import check_sad_path_floor, count_error_path_scenarios

    error_path_count, total_count = count_error_path_scenarios(
        repo, feature_id, entering_slice
    )
    lever = check_sad_path_floor(error_path_count, total_count)
    if not lever.flagged:
        return
    payload = {
        "event": lever.structured_event,
        "feature_id": feature_id,
        "slice_id": entering_slice,
        "target": lever.target,
        "remediation": lever.remediation,
    }
    sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Carpaccio slice gate entry point.

    Pure-function contract (ADR-028 D2-bis): reads the feature-delta, the
    slice's ``.feature`` files, and the AT-completion ledger -- writes nothing.
    """
    args = _parse_args(argv)
    repo = _repo_root(args.repo_root)
    feature_id = args.feature_id
    entering_slice = args.entering_slice
    at_kind = args.at_kind
    regression_test_file = (
        (repo / args.regression_test_file) if args.regression_test_file else None
    )

    if getattr(args, "enforce_sad_path_floor", False):
        _emit_sad_path_floor(repo, feature_id, entering_slice)

    try:
        if at_kind == "pytest-regression" and regression_test_file is None:
            # Only the CLI's own arg-parsing can mis-wire this combination
            # (ADR-001 DD-7): `check_carpaccio`/`check_at_review` raise
            # `ValueError` on it (a programming-contract violation), so the
            # CLI shell enforces it itself as a `GateError` diagnostic before
            # either function is ever called with `regression_test_file=None`.
            raise GateError(
                2,
                {
                    "event": "MalformedInput",
                    "cause": "the pytest regression-test file",
                    "error": (
                        "--at-kind=pytest-regression requires --regression-test-file"
                    ),
                },
            )
        delta_path = _feature_delta_path(repo, feature_id)
        if not delta_path.is_file():
            raise GateError(
                1,
                {
                    "event": "SlicePlanSectionMissing",
                    "error": (
                        f"feature-delta not found: docs/feature/{feature_id}/"
                        "feature-delta.md"
                    ),
                },
            )
        plan = parse_slice_plan(delta_path.read_text(encoding="utf-8"))
        scenarios = parse_scenarios(_read_feature_files(repo, feature_id))
        slice_max, slice_max_source = _resolve_slice_max(repo)
        coupled_event = check_carpaccio(
            plan,
            scenarios,
            entering_slice,
            slice_max,
            at_kind=at_kind,
            regression_test_file=regression_test_file,
            repo=repo,
            feature_id=feature_id,
            slice_max_source=slice_max_source,
        )
        at_evidence = check_at_review(
            repo,
            feature_id,
            entering_slice,
            scenarios,
            at_kind=at_kind,
            regression_test_file=regression_test_file,
            plan=plan,
        )
    except GateError as gate_error:
        _emit(gate_error.payload)
        return gate_error.exit_code

    payload: dict[str, object] = {
        "event": coupled_event["event"] if coupled_event else "SliceCleared",
        "slice_id": entering_slice,
        "feature_id": feature_id,
    }
    if coupled_event:
        payload.update(coupled_event)
    if at_evidence is not None:
        # pytest-regression mode only: the ledger distinguishes WHICH
        # attestation cleared assertion 5 (reviewer-verdict | mechanical-seal).
        # The gherkin payload stays byte-identical (at_evidence is None there).
        payload["at_evidence"] = at_evidence
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
