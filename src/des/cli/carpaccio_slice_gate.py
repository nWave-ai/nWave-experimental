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

Exit codes:
    0  -- the slice is cleared to enter implementation
    1  -- the feature-delta or its ``[REF] Slice Plan`` section is absent
    2  -- malformed input (the slice-plan table OR a ``.feature`` slice tag);
          the emitted JSON ``cause`` field names which input to repair
    44 -- CARPACCIO_SLICE_TOO_LARGE: oversized / coverage / ordering violation
    45 -- AT_REVIEW_NOT_APPROVED: assertion 5 failed (one of six closed reasons)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.cli.carpaccio_format import (
    GateError,
    Scenario,
    SlicePlan,
    _at_review_rejection,
    _config_slice_max,
    _feature_tag_files,
    _read_feature_files,
    _slice_scenarios,
    check_carpaccio,
    parse_scenarios,
    parse_slice_plan,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.at_review_signing import (
    canonical_at_review_json,
)
from des.domain.at_review_signing import (
    load_signing_key as _load_signing_key,
)
from des.domain.repo_path_resolver import (
    feature_delta_path as _feature_delta_path,
)
from des.domain.repo_path_resolver import (
    resolve_repo_root as _repo_root,
)


if TYPE_CHECKING:
    from pathlib import Path


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
    "main",
    "parse_scenarios",
    "parse_slice_plan",
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


# The signing-key precedence + the seven HMAC-signed fields +
# ``canonical_at_review_json`` now live in the ``des.domain.at_review_signing``
# SSOT (ADR-029 D5, AD-05). ``_load_signing_key`` (returning ``None`` for
# fail-closed) and ``canonical_at_review_json`` are imported from there and
# re-exported (``__all__``) so existing importers of this CONSUMER gate keep
# resolving them.


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


def check_at_review(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    scenarios: list[Scenario],
) -> None:
    """Run assertion 5 (ADR-029 D5). Raises ``GateError`` exit 45 on failure.

    Fail-closed: an unresolvable signing key refuses the slice (reason
    ``key-absent``) -- the gate never passes blind. F-03 (atdd-pure-dogfooding-
    friction-2026-05-20.md): an entering slice that maps to ZERO ``@slice-NN``
    scenarios is rejected loud (reason ``no-scenarios-for-slice``), never
    cleared vacuously on an empty AT set.
    """
    key = _load_signing_key(repo)
    if key is None:
        raise _at_review_rejection("key-absent", entering_slice)

    record = _latest_verdict_record(_ledger_path(repo, feature_id), entering_slice)
    if record is None:
        raise _at_review_rejection("absent", entering_slice)

    if record.get("verdict") != "APPROVED":
        raise _at_review_rejection("not-approved", entering_slice)

    if not _hmac_verifies(record, key):
        raise _at_review_rejection("hmac-mismatch", entering_slice)

    slice_scenarios = _slice_scenarios(scenarios, entering_slice)
    expected_ids = {f"AT-{n}" for n in range(1, len(slice_scenarios) + 1)}
    record_ids = record.get("at_ids")
    if not isinstance(record_ids, list) or set(record_ids) != expected_ids:
        raise _at_review_rejection("stale-at-set", entering_slice)

    expected_hash = _at_content_hash(slice_scenarios)
    if record.get("at_content_hash") != expected_hash:
        raise _at_review_rejection("stale-at-content", entering_slice)


def _hmac_verifies(record: dict[str, object], key: bytes) -> bool:
    """Constant-time-compare the record HMAC over the seven signed fields."""
    signature = record.get("hmac_sha256")
    if not isinstance(signature, str):
        return False
    try:
        expected = hmac.new(
            key, canonical_at_review_json(record), hashlib.sha256
        ).hexdigest()
    except KeyError:
        return False
    return hmac.compare_digest(expected, signature)


def _at_content_hash(slice_scenarios: list[Scenario]) -> str:
    """SHA-256 over the sorted concatenation of normalized scenario bodies."""
    bodies = sorted(s.normalized_body for s in slice_scenarios)
    return hashlib.sha256("".join(bodies).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# CLI shell
# ---------------------------------------------------------------------------


_CLEAR_CLASS_EVENTS = frozenset({"SliceCleared", "CoupledSliceAccepted"})


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
    return parser.parse_args(sys.argv[1:] if argv is None else list(argv))


def main(argv: list[str] | None = None) -> int:
    """Carpaccio slice gate entry point.

    Pure-function contract (ADR-028 D2-bis): reads the feature-delta, the
    slice's ``.feature`` files, and the AT-completion ledger -- writes nothing.
    """
    args = _parse_args(argv)
    repo = _repo_root(args.repo_root)
    feature_id = args.feature_id
    entering_slice = args.entering_slice

    try:
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
        slice_max = _config_slice_max(repo)
        coupled_event = check_carpaccio(plan, scenarios, entering_slice, slice_max)
        check_at_review(repo, feature_id, entering_slice, scenarios)
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
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
