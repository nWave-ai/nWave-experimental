"""verify-deliver-entry-contract — the DELIVER-entry contract-freeze gate.

f-deliver-entry-contract-freeze slice-01/slice-02 (ADR-FLOW-004, feature-delta
DDD-1..DDD-5). At the FIRST DELIVER gate-IN it asserts the contract (TESTS +
FEATURE-DELTA SSOT, ADR-FLOW-002 D8) is STRUCTURALLY complete, and on PASS writes
ONE ``ContractFrozen`` ledger record — the frozen baseline per-slice gate-INs
re-verify against (feature-level granularity, CT-7).

slice-02 (CT-5/CT-7): once a ``ContractFrozen`` baseline exists, every subsequent
per-slice gate-IN RE-VERIFIES the LIVE feature-delta against that frozen baseline
instead of re-freezing. The one post-freeze mutation ADR-FLOW-002 D8 permits — a
Slice-Plan row status-flip to "shipped" — re-earns the freeze (PASS); any other
mutation (a locked section body edited, a Slice-Plan row added) is drift and HALTs
(FAIL). A re-verify NEVER mints a second baseline (the feature-level freeze holds).

Structural-completeness check (DDD-1), composing EXISTING checks in-process
(F-D-09-clean — stdlib + ``des.*`` ONLY, never ``from scripts.*`` / ``from
tests.*``):

* (1a) feature-delta wave-heading TYPE tokens valid + the 5-column Slice Plan —
  REUSE ``validate_feature_delta_content`` + ``validate_slice_plan_content``
  (``des.cli.validate_feature_delta``), in-process.
* (1b) the named locked ``[REF]`` sections are PRESENT — the NEW
  ``locked_sections_present`` check (review HIGH-2: genuinely-new GREEN work, the
  source validator does NOT check section presence).
* (2) every planned Slice-Plan row has an authored AT module — REUSE
  ``feature_tag_files`` (the ``@feature-{id}`` + ``@slice-NN`` resolution).

Emits a §17 ``GateVerdict`` token on JSON-stdout (ADR-GV-001, the five existing
verdicts; NO sixth, NO sequencer, NO engine — OSS hook-only):

* **PASS** — locked sections present + valid + every planned slice has an AT
  module → write ``ContractFrozen``.
* **FAIL** — a locked section missing/malformed OR a planned-slice-with-no-AT-
  module. The diagnostic NAMES the offender. No freeze.
* **INDETERMINATE** — the feature-delta is unreadable/undecodable (the gate
  cannot read the contract). Degrade-LOUD (Invariant 2 / DDD-5): a refusal-to-
  decide, never a false freeze.

Target-machine agnostic (Invariant 4): Python + filesystem only — NO git, NO
``grep`` binary, NO ``import yaml``. Runs on any Python 3.10+ target. Reachable as
the registered ``des verify-deliver-entry-contract`` subcommand via the thin
:func:`main` driver below; the verdict, not the process exit code, carries the
gate outcome (asymmetric authority — a PASS is "the contract is structurally
present and frozen", never "the contract is right").
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.feature_at_files import (
    feature_tag_files,
    feature_tagged_test_files,
    is_pytest_collectible,
    resolve_test_file_attribution,
)
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.validate_feature_delta import (
    LOCKED_REF_SECTIONS,
    VERDICT_ACCEPTED,
    RefSection,
    WaveOutputContract,
    missing_registry_sections,
    validate_feature_delta_content,
    validate_slice_plan_content,
)
from des.domain.gate_outcome import GateVerdict
from des.domain.repo_path_resolver import feature_delta_path
from des.domain.slice_id_trailer import SLICE_ROW_ID_RE, SLICE_TAG_RE
from des.runtime.interpreter import InterpreterUnavailable, python_for


_OUTCOME_GATE_NAME = "verify-deliver-entry-contract"


#: A ``| slice-NN |`` first cell in the Slice Plan table — the planned slice ids
#: whose authored AT module the gate must resolve (DDD-1 step 2). Imported
#: from the domain SSOT (fix-slice-id-grammar-drift-ssot) so a letter-suffixed
#: `| slice-04a |` row is matched identically to a plain `| slice-NN |` row.
_SLICE_ROW_ID = SLICE_ROW_ID_RE

#: A ``@slice-NN`` scenario tag in a resolved ``.feature`` AT module. Imported
#: from the domain SSOT (fix-slice-id-grammar-drift-ssot).
_SLICE_TAG = SLICE_TAG_RE

#: The code-design manifest filename the freeze gate folds when present (slice-03 /
#: ADR-FLOW-004 DDD-5; mirrors gate_g.py:80 ``_MANIFEST_FILENAME``). DESIGN is
#: optional (ADR-FLOW-002 D2): a feature MAY ship one alongside its feature-delta.
_MANIFEST_FILENAME = "code-design.manifest.yaml"

#: The dev-checkout repo root, derived from THIS module's own location
#: (src/des/cli/verify_deliver_entry_contract.py -> parents[3]). The manifest
#: validator lives under scripts/cli/** (absent from the installed ``des``
#: package), so the fold invokes it as a SUBPROCESS rooted here (F-D-09: NEVER
#: ``from scripts.* import``). When this root carries no ``scripts/`` tree (the
#: installed-package target), the fold degrades LOUD to INDETERMINATE.
_DEV_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The manifest-validator module the fold drives as a subprocess (F-D-09).
_MANIFEST_VALIDATOR_MODULE = "scripts.cli.validate_component_manifest"

#: The DELIVER-entry locked-section contract, expressed as a registry-backed
#: ``WaveOutputContract`` over the four ``LOCKED_REF_SECTIONS`` (all mandatory,
#: none greenfield-degradable). The section-presence check migrated off the
#: hard-coded ``locked_sections_present`` to the registry-backed
#: ``missing_registry_sections`` reader (WD-2 ADD-not-mutate / DA-3), reading THIS
#: contract — NOT the 1-entry ``deliver.yaml`` ``output_contract`` (which would
#: shrink the named set to ``Slice Plan`` only). The migration is byte-stable:
#: ``missing_registry_sections`` over an all-mandatory contract returns exactly
#: what ``locked_sections_present`` returned, so the FAIL diagnostic still names
#: all four locked sections and the PASS/FAIL/INDETERMINATE verdict map is
#: unchanged.
_DELIVER_LOCKED_CONTRACT = WaveOutputContract(
    wave="deliver",
    ref_sections=tuple(
        RefSection(id=name, grade="mandatory") for name in LOCKED_REF_SECTIONS
    ),
)


@dataclass(frozen=True)
class FreezeOutcome:
    """The §17 verdict envelope the contract-freeze gate emits (the boundary DTO).

    ``verdict``    — the §17 ``GateVerdict`` (one of the five, no sixth).
    ``diagnostic`` — names the offender on FAIL / the unreadable contract on
                     INDETERMINATE; empty on PASS.
    """

    verdict: GateVerdict
    diagnostic: str


def evaluate_contract_freeze(feature_id: str, repo_root: Path) -> FreezeOutcome:
    """Evaluate the DELIVER-entry structural-completeness check for ``feature_id``.

    The check order is load-bearing: the feature-delta-readable probe runs FIRST
    so an unreadable contract degrades LOUD to INDETERMINATE before any structural
    verdict; then the locked-section + slice-plan + heading + AT-module-per-slice
    checks project onto PASS / FAIL.
    """
    delta_path = feature_delta_path(repo_root, feature_id)
    content = _read(delta_path)
    if content is None:
        return _indeterminate(feature_id, delta_path)

    return _evaluate_structural(content, feature_id, repo_root)


def evaluate_contract_reverify(
    feature_id: str, repo_root: Path, baseline: str
) -> FreezeOutcome:
    """Re-verify the LIVE feature-delta against the FROZEN baseline (slice-02 / CT-5).

    Once a ``ContractFrozen`` baseline exists, every subsequent per-slice DELIVER
    gate-IN RE-VERIFIES instead of re-freezing (R1). The contract first re-earns
    the slice-01 structural verdict (an unreadable / structurally-broken live
    delta degrades the same way); then the live delta is DIFFED against the frozen
    baseline. ADR-FLOW-002 D8 permits EXACTLY ONE post-freeze mutation — a
    Slice-Plan row status-flip to "shipped"; the diff is therefore taken over the
    STATUS-NORMALISED projection of both texts, so a status-flip (or an unchanged
    re-verify) re-earns the freeze (OUT=IN -> PASS) while ANY other structural
    mutation — a locked section body edited, a Slice-Plan row added — survives the
    normalisation as drift and HALTs (FAIL, the gate names the mutation).
    """
    delta_path = feature_delta_path(repo_root, feature_id)
    content = _read(delta_path)
    if content is None:
        return _indeterminate(feature_id, delta_path)

    structural = _evaluate_structural(content, feature_id, repo_root)
    if structural.verdict is not GateVerdict.PASS:
        return structural

    if _normalise_for_drift(content) != _normalise_for_drift(baseline):
        return _failed(
            f"the live feature-delta for {feature_id!r} has DRIFTED from the frozen "
            f"baseline beyond the permitted Slice-Plan status-flip (ADR-FLOW-002 D8): "
            f"a locked [REF] section body was edited or a Slice-Plan row was added "
            f"after the freeze. The feature-level freeze cannot re-open the "
            f"ratification window per-slice — HALT."
        )

    return FreezeOutcome(verdict=GateVerdict.PASS, diagnostic="")


def _evaluate_structural(
    content: str, feature_id: str, repo_root: Path
) -> FreezeOutcome:
    """The slice-01 structural-completeness projection over a readable delta."""
    heading_result = validate_feature_delta_content(content)
    if not heading_result.is_valid:
        first = heading_result.offenders[0]
        return _failed(
            f"the feature-delta for {feature_id!r} has a malformed wave heading at "
            f"line {first.line}: {first.heading} — {first.reason}."
        )

    missing_sections = missing_registry_sections(content, _DELIVER_LOCKED_CONTRACT)
    if missing_sections:
        return _failed(
            f"the feature-delta for {feature_id!r} is MISSING locked section(s) "
            f"{missing_sections!r} — every named [REF] section "
            f"(Architecture & Contract Tests / ADR Refs / Reuse Analysis / Slice "
            f"Plan) must be present for the contract to freeze. Run `des "
            f"feature-delta-doctor docs/feature/{feature_id}/feature-delta.md` for "
            f"a one-pass report of every missing/malformed section."
        )

    slice_plan = validate_slice_plan_content(content)
    if slice_plan.verdict != VERDICT_ACCEPTED:
        return _failed(
            f"the feature-delta for {feature_id!r} has a malformed Slice Plan "
            f"({slice_plan.verdict}): {slice_plan.detail}."
        )

    unbacked = _slice_without_at_module(content, feature_id, repo_root)
    if unbacked is not None:
        return _failed(
            f"the planned Slice-Plan row {unbacked!r} has NO authored AT module "
            f"(no .feature carrying both @feature-{feature_id} and @{unbacked}) — "
            f"the TESTS-half of the contract is incomplete; the contract cannot "
            f"freeze."
        )

    return _fold_code_design_manifest(feature_id, repo_root)


# -- check primitives ---------------------------------------------------------


def _slice_without_at_module(
    content: str, feature_id: str, repo_root: Path
) -> str | None:
    """The first planned slice with no authored AT module, or None when all backed.

    A planned ``slice-NN`` row (the first cell of a Slice-Plan table row) must bind
    to an authored AT module -- a ``.feature`` file carrying both the file-level
    ``@feature-{feature_id}`` tag and a ``@slice-NN`` scenario tag (DDD-1 step 2;
    the ``feature_tag_files`` resolution), OR a pytest file head-comment-tagged
    the SAME pair (``_authored_slice_tags``, agnostic-at-discovery-ssot-repair).
    """
    authored = _authored_slice_tags(feature_id, repo_root)
    for line in content.splitlines():
        match = _SLICE_ROW_ID.match(line.strip())
        if match is not None and match.group(1) not in authored:
            return match.group(1)
    return None


def _authored_slice_tags(feature_id: str, repo_root: Path) -> frozenset[str]:
    """Every ``@slice-NN`` tag appearing in an authored AT module for the feature.

    AT-kind agnostic (agnostic-at-discovery-ssot-repair, gap 1): a slice
    backed EXCLUSIVELY by a pytest AT (no ``.feature`` file anywhere) must not
    be reported unbacked. Composes the SAME two resolvers
    ``slice_at_completeness.feature_files_for_slice`` already unions with the
    Gherkin path -- ``feature_tagged_test_files`` (the ``@feature-{id}``
    head-tag scan) + ``resolve_test_file_attribution`` (the ``@slice-NN``
    sub-tag parse) -- filtered to pytest-collectible filenames so a doc/ADR
    that merely mentions the tag convention is never counted (the
    F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND AT-D1 guard, reused via
    ``is_pytest_collectible``). No new discovery mechanism invented.
    """
    tags: set[str] = set()
    for path in feature_tag_files(repo_root, feature_id):
        tags.update(
            _SLICE_TAG.findall(path.read_text(encoding="utf-8", errors="replace"))
        )
    for test_path in feature_tagged_test_files(repo_root, feature_id):
        if not is_pytest_collectible(test_path):
            continue
        tags.update(resolve_test_file_attribution(test_path).slice_ids)
    return frozenset(tags)


# -- code-design manifest validity fold (slice-03 / ADR-FLOW-004 DDD-5) --------


def _fold_code_design_manifest(feature_id: str, repo_root: Path) -> FreezeOutcome:
    """Fold a shipped code-design manifest's VALIDITY into the freeze (slice-03).

    DESIGN is optional (ADR-FLOW-002 D2): a feature MAY ship a
    ``code-design.manifest.yaml`` next to its feature-delta. When it does, the
    manifest's validity (schema-valid AND every ``sut:`` symbol grep-findable) is
    folded into the structural verdict (ADR-FLOW-004 DDD-5):

    * manifest ABSENT  -> NO re-block (a consciously-skipped optional wave is never
      refused over absence; the structural check already passed -> PASS).
    * manifest PRESENT + VALID (validator exit 0) -> the fold CONTRIBUTES, the
      contract still freezes -> PASS.
    * manifest PRESENT + INVALID (validator exit 1 stale ``sut:`` / exit 2 bad
      schema) -> FAIL, the diagnostic naming the manifest defect.

    The validator lives under ``scripts/cli/**`` (absent from the installed ``des``
    package), so the fold drives it as a SUBPROCESS (F-D-09: NEVER ``from scripts.*
    import``) rooted at the dev checkout. On a target where that tree is absent or
    the subprocess cannot run, the fold degrades LOUD to INDETERMINATE — a
    refusal-to-decide, never a silent false freeze (Invariant 2 / DDD-5).
    """
    manifest_path = repo_root / "docs" / "feature" / feature_id / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        return FreezeOutcome(verdict=GateVerdict.PASS, diagnostic="")

    exit_code, detail = _run_manifest_validator(manifest_path)
    if exit_code is None:
        return FreezeOutcome(
            verdict=GateVerdict.INDETERMINATE,
            diagnostic=(
                f"the code-design manifest for {feature_id!r} ({manifest_path}) "
                f"could not be validated — the manifest validator is unreachable on "
                f"this machine ({detail}). Degrading LOUD to INDETERMINATE "
                f"(Invariant 2 / DDD-5): a refusal-to-decide, never a false freeze."
            ),
        )
    if exit_code != 0:
        return _failed(
            f"the code-design manifest for {feature_id!r} ({manifest_path}) is "
            f"INVALID (validator exit {exit_code}): {detail} — an invalid manifest "
            f"(stale sut symbol or bad schema) FAILs the DELIVER-entry freeze "
            f"(ADR-FLOW-004 DDD-5). Repair it: update the manifest's `sut:` symbol "
            f"(or fix the schema per the detail above), then re-run `python -m "
            f"scripts.cli.validate_component_manifest {manifest_path}` to confirm "
            f"before re-driving this gate."
        )

    return FreezeOutcome(verdict=GateVerdict.PASS, diagnostic="")


def _run_manifest_validator(manifest_path: Path) -> tuple[int | None, str]:
    """Drive the manifest validator subprocess (F-D-09); return (exit_code, detail).

    ``exit_code`` is ``None`` when the subprocess could not run at all (validator
    tree absent / no usable interpreter / spawn error) — the INDETERMINATE degrade
    key. Otherwise it is the validator's process exit code (0 valid / 1 stale sut /
    2 schema-invalid) and ``detail`` carries the validator's own diagnostic output.

    The interpreter is resolved through ``des.runtime.interpreter.python_for`` (the
    canonical spawn boundary, F-21) rather than trusting ``sys.executable`` inline.
    ``python_for(None)`` returns the running interpreter — the no-capability case
    (the validator needs *a* Python with the dev-checkout deps, not the pytest
    capability). An ``InterpreterUnavailable`` at the boundary degrades LOUD to the
    same INDETERMINATE (validator-unreachable) signal as an absent scripts tree.
    """
    if not (_DEV_REPO_ROOT / "scripts" / "cli").is_dir():
        return None, f"no scripts/cli tree under {_DEV_REPO_ROOT}"
    try:
        interpreter = python_for(None)
    except InterpreterUnavailable as exc:
        return None, f"no usable interpreter for the manifest validator: {exc}"
    try:
        completed = subprocess.run(
            [interpreter, "-m", _MANIFEST_VALIDATOR_MODULE, str(manifest_path)],
            cwd=str(_DEV_REPO_ROOT),
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return None, f"validator subprocess failed to launch: {exc}"
    detail = (completed.stdout + completed.stderr).strip() or "(no validator output)"
    return completed.returncode, detail


# -- post-freeze drift normalisation (slice-02) -------------------------------


def _normalise_for_drift(content: str) -> str:
    """Project a feature-delta onto its drift-comparable form (the status-flip mask).

    ADR-FLOW-002 D8 permits EXACTLY ONE post-freeze mutation: a Slice-Plan row
    status-flip to "shipped". The drift diff must therefore be BLIND to the
    third (Status) cell of a ``| slice-NN | ... |`` Slice-Plan row but sensitive
    to every other byte. Each Slice-Plan row is rewritten with its Status cell
    blanked; every other line passes through verbatim. So a status-flip
    normalises to the baseline (re-earn PASS) while an edited section body or an
    added Slice-Plan row survives the mask as drift (HALT).
    """
    return "\n".join(_mask_status_cell(line) for line in content.splitlines())


def _mask_status_cell(line: str) -> str:
    """Blank the Status cell of a Slice-Plan row; pass every other line verbatim."""
    if _SLICE_ROW_ID.match(line.strip()) is None:
        return line
    cells = line.split("|")
    # A Slice-Plan row splits to ['', ' slice-NN ', ' value ', ' status ', ...];
    # index 3 is the Status cell (D8 status-flip column). Blank it in place.
    if len(cells) > 3:
        cells[3] = ""
    return "|".join(cells)


# -- verdict constructors -----------------------------------------------------


def _failed(diagnostic: str) -> FreezeOutcome:
    """A FAIL outcome naming the offender (a confirmable structural defect)."""
    return FreezeOutcome(verdict=GateVerdict.FAIL, diagnostic=diagnostic)


def _indeterminate(feature_id: str, delta_path: Path) -> FreezeOutcome:
    """An INDETERMINATE outcome — the feature-delta is unreadable (degrade-LOUD)."""
    diagnostic = (
        f"the feature-delta for {feature_id!r} is unreadable ({delta_path}) — the "
        f"gate must read the contract to attest it and cannot. Degrading LOUD to "
        f"INDETERMINATE (Invariant 2 / DDD-5): a refusal-to-decide, never a false "
        f"freeze."
    )
    return FreezeOutcome(verdict=GateVerdict.INDETERMINATE, diagnostic=diagnostic)


# -- filesystem helper --------------------------------------------------------


def _read(path: Path) -> str | None:
    """Read a file's text, or None when it is absent / undecodable (the unreadable
    case the INDETERMINATE degrade keys on)."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return None


# -- thin CLI driver (the registered `des verify-deliver-entry-contract`) ------


def main(argv: list[str] | None = None) -> int:
    """Drive the contract-freeze check → write ContractFrozen on PASS → print verdict.

    Emits one JSON line ``{"verdict": <token>, "diagnostic": <str>}`` on stdout
    (the verdict token is the §17 ``GateVerdict.value``). On PASS, ONE
    ``ContractFrozen`` record is appended to the feature's ``AtCompletionLedger``
    (the frozen baseline; CT-1 / CT-7). The exit code carries the outcome but the
    verdict token is the observable contract.
    """
    args = _build_parser().parse_args(argv)
    ledger = AtCompletionLedger(args.feature_id, args.repo_root)
    baseline = _frozen_baseline(ledger)

    if baseline is not None:
        # A ContractFrozen baseline already exists -> per-slice RE-VERIFY (R1).
        # Feature-level freeze (CT-7): a re-verify re-earns the freeze, it NEVER
        # mints a second baseline, so no append_contract_frozen here.
        outcome = evaluate_contract_reverify(args.feature_id, args.repo_root, baseline)
    else:
        # First DELIVER gate-IN -> fresh freeze; snapshot the status-normalised
        # baseline so per-slice re-verifies can diff against it (slice-02 / CT-5).
        outcome = evaluate_contract_freeze(args.feature_id, args.repo_root)
        if outcome.verdict is GateVerdict.PASS:
            ledger.append_contract_frozen(baseline=_live_baseline(args))

    ledger.append_gate_event(
        "GateOutcomeRecorded",
        "",
        feature_id=args.feature_id,
        gate=_OUTCOME_GATE_NAME,
        outcome=outcome.verdict,
    )
    print(
        json.dumps({"verdict": outcome.verdict.value, "diagnostic": outcome.diagnostic})
    )
    return _EXIT_BY_VERDICT.get(outcome.verdict, 1)


def _frozen_baseline(ledger: AtCompletionLedger) -> str | None:
    """The ``frozen_baseline`` snapshot of the existing ContractFrozen record, or None.

    Returns ``None`` when no ContractFrozen record exists yet (first gate-IN ->
    fresh freeze) — read under the M7 fail-closed integrity contract.
    """
    records = ledger.read_records(event_type="ContractFrozen")
    if not records:
        return None
    baseline = records[0].get("frozen_baseline")
    return str(baseline) if baseline is not None else ""


def _live_baseline(args: argparse.Namespace) -> str:
    """The current feature-delta text frozen as the baseline (empty if unreadable)."""
    delta_path = feature_delta_path(args.repo_root, args.feature_id)
    return _read(delta_path) or ""


_EXIT_BY_VERDICT: dict[GateVerdict, int] = {
    GateVerdict.PASS: 0,
    GateVerdict.FAIL: 1,
    GateVerdict.INDETERMINATE: 4,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-deliver-entry-contract",
        description=(
            "DELIVER-entry contract-freeze gate: at the first DELIVER gate-IN, "
            "assert the contract is structurally complete (locked sections present "
            "+ valid Slice Plan + an authored AT module per planned slice) and "
            "write a ContractFrozen ledger record on PASS; emit a §17 GateVerdict."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="The feature id whose DELIVER-entry contract is checked.",
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        required=True,
        type=Path,
        help="The repo root holding docs/feature/<id>/feature-delta.md + tests/.",
    )
    parser.add_argument(
        "--format",
        default="json",
        choices=("json",),
        help="Output format (json — the structured verdict envelope).",
    )
    return parser


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
