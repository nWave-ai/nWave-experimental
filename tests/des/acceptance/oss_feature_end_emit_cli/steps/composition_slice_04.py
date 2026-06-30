"""Composition root for slice-04 -- the cycle's REAL coverage-map verify leg.

slice-04 of oss-feature-end-emit-cli (option (b) RATIFIED, Ale 2026-06-03;
OQ-3=(i)). Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised
through the PRODUCTION single entry point -- the real ``des feature-end run``
subcommand over the ``des.cli.__main__`` dispatcher as a subprocess (Layer 3
subprocess, the SAME driving surface as slice-03). The composition NEVER imports
the cycle use-case / the ported verify core and calls them at the step boundary;
the only entry is the real subprocess through the dispatcher, exactly as an
operator (or the SubagentStop hook shim) invokes it (DDD-7 -- one use-case, two
thin driving adapters).

WHAT THIS COMPOSITION STAGES (option (b), RM-1-HONEST)
------------------------------------------------------
slice-04 extends the cycle with a REAL coverage-map verify leg (the §5.3 verify
core PORTED into ``src/des/application/coverage_map_verify_service``, run
in-process after the env-e2e leg). The composition reuses slice-03's passing
gate environment (a real installable feature whose walking-skeleton + env-e2e
gates reach PASS) and ADDS the coverage-map artifact the new leg verifies:

  * ``stage_signed_coverage_map`` -- writes a coverage-map.md whose ``## Signoff``
    block carries a GENUINE ``reviewed-content-digest``: the fixture builder
    computes the REAL §5.3 canonical digest over the body and records it (a
    minted constant / ``_pending_`` cannot equal the real canonicalization), and
    attests every omission-class-id from ``nWave/data/omission-classes.json``.
    The ported verify core PASSES -> the cycle emits both
    ``CoverageMapVerifiedAt{Distill,Deliver}Exit`` records (RM-1: emitted ONLY
    after a REAL pass).
  * ``stage_unsigned_coverage_map`` -- writes a coverage-map.md whose
    ``## Signoff`` block carries the producer's ``_pending_`` digest (the only
    thing the automated producer renders; no human signed). The ported verify
    core REFUSES (``SignoffMissing``) -> the cycle fail-closes
    (``FeatureEndCycleRefused`` exit 2) -> NEITHER coverage-map record is minted.

DIVERGENCE PAIR (anti-theater, load-bearing): the signed/unsigned pair pins the
real behaviour. A stub that ALWAYS emits the 2 records cannot pass the unsigned
scenario (it would mint records for an unsigned map); a stub that NEVER emits
them cannot pass the signed scenario. Only a cycle that RUNS the real verify and
emits iff it passes satisfies BOTH -- the closed-world discriminator a future
masked impl cannot vacuously satisfy.

WHY THE FIXTURE COMPUTES THE DIGEST IN-HARNESS (not a hardcoded hex)
-------------------------------------------------------------------
The honest signed digest is a function of the coverage-map BODY under the §5.3
canonicalization. The fixture builder records the genuine digest it computes
over the body it just wrote, via ``_compute_canonical_digest`` imported from the
sibling ``signed_coverage_map`` module (the §5.3 7-step canonicalization is
single-sourced there -- the same builder that writes the honest-signed fixture).
This keeps the fixture HONEST (the recorded digest genuinely matches the body)
WITHOUT hardcoding a magic hex that silently rots when the body changes. The
harness is test infrastructure (staging a genuinely-signed artifact), NOT the
SUT: the SUT is the cycle, driven only through the real subprocess. This mirrors
how slice-03 staged a real installable feature (``STAGE THE ENVIRONMENT, never
inject the verdict``).

OBSERVABLE READ-BACK (substrate verification, NOT a second SUT)
--------------------------------------------------------------
After the cycle runs, the coverage-map records and the full feature-end record
set are read back through the production ``AtCompletionLedger`` reader (the SAME
audit substrate ``des verify-integrity`` consumes). A coverage-map record
present means the cycle's REAL verify leg actually PASSED (it appends on a real
pass, RM-1) -- the anti-theater proof. The post-cycle ledger is then fed to the
real ``des verify-integrity`` consumer: on the signed PASS it must now report the
feature FULLY reconciled (all 6 records present), closing the slice-03
partial-done boundary. This read-back is allowed (Mandate-13): it verifies the
observable SUBSTRATE the done-gate reads, it is not the SUT.

LAYER-3 example-only (Mandate 9/11): real subprocess + real ledger + real git
tree + real reviewer signing key -- no PBT machinery. The only things the test
sets are the signing-key env var (an external/non-deterministic port per the
Architecture of Reference), the staged passing gate workspace, and the signed /
unsigned coverage-map artifact (environment SETUP -- what makes the REAL verify
pass or refuse, never the verdict itself).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker, seed_feature_delta_git_repo

from .domain_types_slice_04 import (
    CoverageMapDefect,
    CoverageMapRecord,
    CycleOutcome,
    FeatureId,
)
from .signed_coverage_map import (
    _compute_canonical_digest,
    write_signed_coverage_map,
)


# THIS file lives at
# tests/des/acceptance/oss_feature_end_emit_cli/steps/composition_slice_04.py ->
# 5 parents up is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]

_FEATURE_ID = FeatureId("oss-feature-end-cycle-demo")

_REVIEWER_AGENT = "nw-software-crafter-reviewer"
_DEEP_REVIEW_VERDICT = "APPROVED"


def _load_omission_class_ids() -> list[str]:
    """Read the omission-class ids the signoff must attest from the Layer-1 SSOT.

    The ported verify core asserts the `## Signoff` block's
    `omission-classes-attested:` list covers every class-id present in
    ``nWave/data/omission-classes.json`` (cardinality-agnostic). The honest
    signed fixture attests exactly that set -- read from the SSOT so the fixture
    stays in lock-step when the class list grows (no hardcoded id list to rot).
    """
    import json  # stdlib: the omission-classes SSOT is JSON (option E)

    document = json.loads(
        (_REPO_ROOT / "nWave" / "data" / "omission-classes.json").read_text(
            encoding="utf-8"
        )
    )
    return [entry["id"] for entry in document["omission-classes"]]


@dataclass
class IntegrityVerdict:
    """The observable result of `des verify-integrity` over the post-cycle ledger."""

    exit_code: int
    missing_records: frozenset[str]


@dataclass(frozen=True)
class CycleResult:
    """The observable result of one `des feature-end run` invocation (slice-04).

    Universe entries are port-exposed only (Mandate 8): the command outcome
    (succeeded / refused, derived from the exit code), the set of coverage-map
    records read back from the completion ledger, and whether the refusal (when
    refused) carried the cycle's own structured fail-closed marker
    (`refused_by_cycle`) versus a vacuous dispatcher miss -- never an internal
    use-case struct.
    """

    outcome: CycleOutcome
    exit_code: int
    coverage_map_records: frozenset[str]
    refused_by_cycle: bool


class FeatureEndCoverageMapComposition:
    """Production-wired composition root for the cycle's REAL coverage-map leg.

    The driving port is the real `des feature-end run` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code, the coverage-map records the cycle's REAL verify leg appends to
    the AT-completion ledger on a genuine pass, the cycle's fail-closed marker on
    refusal, and the post-cycle `des verify-integrity` full-reconciliation
    verdict.

    The composition stages the passing gate ENVIRONMENT (reused from slice-03)
    PLUS the coverage-map artifact (signed or unsigned) -- the cycle's REAL
    verify leg derives its own verdict from that artifact. There is no injected
    coverage-map verdict: the laundering seam is absent by construction.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        # Env-parity (F21/RCA-#68): the `des` subprocess runs with
        # cwd=project_root (the per-test tmp workspace). Mark it a developer
        # checkout so the runtime-freshness gate AUTOSKIPS instead of the
        # customer-install REFUSAL (exit 78) -- the honest fix, NOT a
        # NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._project_root)
        self._stage_passing_gates()

    # --- environment SETUP: the passing gate workspace (reused from slice-03) -

    def _stage_passing_gates(self) -> None:
        """Stage a real installable feature whose REAL walking-skeleton + env-e2e
        gates reach PASS (the slice-03 passing shape), so the cycle reaches the
        coverage-map leg. The coverage-map artifact (the slice-04 subject) is
        staged separately by ``stage_signed_coverage_map`` /
        ``stage_unsigned_coverage_map``.
        """
        self._write_feature_delta_with_e2e_block()
        self._write_passing_env_e2e_test()
        self._write_installable_project()
        self._write_walking_skeleton_manifest()

    # --- environment SETUP: the coverage-map artifact (the slice-04 subject) -

    def stage_signed_coverage_map(self) -> None:
        """Stage a GENUINELY human-signed coverage-map the REAL verify leg PASSES.

        Writes ``docs/feature/{id}/distill/coverage-map.md`` whose ``## Signoff``
        block carries a REAL ``reviewed-content-digest`` -- the shared fixture
        builder computes the genuine §5.3 canonical digest over the body and
        records it (NOT ``_pending_``, NOT a minted constant), and attests every
        omission-class-id from the Layer-1 SSOT. The ported verify core's
        structural + digest + attestation checks all pass -> the cycle emits both
        coverage-map records on a REAL pass. Delegates to the SHARED
        ``write_signed_coverage_map`` so slice-03's amended scenario-1 and
        slice-04 stage the byte-identical genuinely-signed artifact from ONE §5.3
        reproduction (DRY).
        """
        write_signed_coverage_map(self._feature_dir, str(self._feature_id))

    def stage_coverage_map_with_defect(self, defect: CoverageMapDefect) -> None:
        """Stage a coverage-map carrying ONE materially-distinct verify-core defect.

        The Mandate-12 typed-parameter template behind the Scenario-Outline
        refusal family: ONE staging entry point keyed by the typed
        ``CoverageMapDefect`` enum stages every refusal cause, so a single parsed
        Given step (over the enum) covers all five rows -- no per-defect staging
        method, no per-defect literal Given decorator. The cycle's REAL ported
        verify core derives the refusal from the staged artifact; the verdict is
        the core's, never injected. Each defect maps to a distinct refusal cause:

          UNSIGNED              -> `_pending_` digest        -> SignoffMissing
          STALE_DIGEST          -> hex != canonical digest   -> SignoffStale
          MISSING_SIGNOFF_BLOCK -> no `## Signoff` section    -> structural / missing-digest
          ATTESTATION_GAP       -> signed map, 1 class unattested -> attestation-incomplete
          MALFORMED             -> non-UTF-8 bytes on disk    -> MalformedInput

        On every defect the cycle fail-closes (FeatureEndCycleRefused) and mints
        NEITHER coverage-map record (the anti-laundering invariant).
        """
        self._write_coverage_map(defect=defect)

    # --- driving-port invocation (the SUT) -----------------------------------

    def run_cycle(self) -> CycleResult:
        """Invoke the REAL `des feature-end run` subcommand over the dispatcher.

        The cycle runs the gates (PASS, staged), then runs the REAL coverage-map
        verify leg in-process against the staged coverage-map, and (on a real
        verify pass) appends both coverage-map records before sign+emit. No
        verdict is injected -- the verdict is the ported verify core's, derived
        from the staged artifact.
        """
        # The WS gate computes its applicability from `git diff --diff-filter=A
        # master...HEAD` (ADR-098). Stage a real repo whose delta adds NO new
        # installable -> WS NOT_APPLICABLE -> the cycle proceeds to the coverage-map
        # leg (this slice's SUT). The empty `.git/` freshness marker is not a valid
        # repo, so without this the git diff fails -> INDETERMINATE -> REFUSE.
        seed_feature_delta_git_repo(self._project_root, ships_new_installable=False)
        completed = self._dispatch(
            [
                "feature-end",
                "run",
                "--repo",
                str(self._project_root),
                "--feature-id",
                str(self._feature_id),
                "--feature-dir",
                str(self._feature_dir),
                "--reviewer-agent-id",
                _REVIEWER_AGENT,
                "--verdict",
                _DEEP_REVIEW_VERDICT,
            ]
        )
        outcome = (
            CycleOutcome.SUCCEEDED
            if completed.returncode == 0
            else CycleOutcome.REFUSED
        )
        return CycleResult(
            outcome=outcome,
            exit_code=completed.returncode,
            coverage_map_records=self.ledger_coverage_map_records(),
            refused_by_cycle=_carries_cycle_refusal(completed.stdout, completed.stderr),
        )

    # --- observable read-back (ledger SUBSTRATE, NOT the SUT) ----------------

    def ledger_coverage_map_records(self) -> frozenset[str]:
        """The coverage-map touchpoint records the cycle's REAL verify leg appended.

        Read back through the production ``AtCompletionLedger`` reader (the same
        set ``des verify-integrity`` reads). A record present means the cycle's
        REAL coverage-map verify PASSED (it appends on a real pass, RM-1) -- the
        anti-theater proof that the cycle did not mint a record for an unsigned
        map.
        """
        return self._ledger().coverage_map_touchpoint_events(
            feature_id=str(self._feature_id)
        )

    def verify_integrity(self) -> IntegrityVerdict:
        """Feed the post-cycle ledger to the REAL `des verify-integrity` consumer.

        On the signed PASS, integrity MUST now report the feature FULLY
        reconciled (exit 0, no missing records) -- the slice-03 partial-done
        boundary (the 2 coverage-map records missing) is closed by slice-04.
        Returns the integrity exit code + the set of records it reports missing.
        """
        completed = self._dispatch(
            [
                "verify-integrity",
                "--repo",
                str(self._project_root),
                "--feature-id",
                str(self._feature_id),
            ]
        )
        return IntegrityVerdict(
            exit_code=completed.returncode,
            missing_records=_extract_missing_records(completed.stdout),
        )

    # --- typed expectations (Mandate-12 typed-parameter accessors) -----------

    @staticmethod
    def expected_coverage_map_records() -> frozenset[str]:
        """The 2 coverage-map records a genuine human-signed PASS MUST emit."""
        return frozenset(
            {CoverageMapRecord.DISTILL_EXIT.value, CoverageMapRecord.DELIVER_EXIT.value}
        )

    # --- workspace staging helpers (environment, not assertion) --------------

    def _write_coverage_map(self, *, defect: CoverageMapDefect) -> None:
        """Write the coverage-map.md under distill/ carrying exactly one defect.

        ``defect=<CoverageMapDefect>`` writes a map carrying exactly one
        verify-core refusal cause. The bytes are written non-UTF-8 only for the
        MALFORMED defect; every other case is valid UTF-8 differing only in the
        `## Signoff` block (digest / attestation / block-presence) so the
        divergence is genuinely in the SIGNATURE, not the document shape. The
        genuinely-SIGNED (passing) artifact is staged separately by
        ``stage_signed_coverage_map`` via the shared ``write_signed_coverage_map``
        builder.
        """
        distill_dir = self._feature_dir / "distill"
        distill_dir.mkdir(parents=True, exist_ok=True)
        target = distill_dir / "coverage-map.md"

        if defect is CoverageMapDefect.MALFORMED:
            # Non-UTF-8 bytes on disk -> the verify core's read classifies it
            # MalformedInput (exit 2). Written as raw bytes, not text.
            target.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
            return

        full_attestation = "\n".join(f"  - {cid}" for cid in _load_omission_class_ids())

        if defect is CoverageMapDefect.UNSIGNED:
            # The producer's `_pending_` placeholder (no human signed) ->
            # SignoffMissing (the digest-line regex rejects `_pending_`).
            body = self._coverage_map_body("_pending_", full_attestation)
        elif defect is CoverageMapDefect.STALE_DIGEST:
            # Well-formed lowercase hex that is NOT the §5.3 canonical digest ->
            # the verify core recomputes, finds a mismatch, refuses SignoffStale.
            stale = hashlib.sha256(b"a-stale-hand-edited-digest").hexdigest()
            body = self._coverage_map_body(stale, full_attestation)
        elif defect is CoverageMapDefect.MISSING_SIGNOFF_BLOCK:
            # The `## Signoff` section is absent entirely -> the verify core's
            # structural / missing-digest gate refuses (no signoff to verify).
            body = self._coverage_map_body_without_signoff()
        elif defect is CoverageMapDefect.ATTESTATION_GAP:
            # A genuinely digest-matched signoff that OMITS one required
            # omission-class-id -> the verify core's attestation gate refuses
            # (the digest matches, but the human did not attest every class).
            partial = "\n".join(f"  - {cid}" for cid in _load_omission_class_ids()[:-1])
            digest = _compute_canonical_digest(
                self._coverage_map_body("_pending_", partial)
            )
            body = self._coverage_map_body(digest, partial)
        else:  # pragma: no cover - exhaustive over the enum
            raise ValueError(f"unhandled coverage-map defect: {defect!r}")

        target.write_text(body, encoding="utf-8")

    def _coverage_map_body(self, digest: str, attested_block: str) -> str:
        """Render the coverage-map body with the given signoff digest + attestation.

        The 4 signed sections are FIXED (digest-invariant); only the ``## Signoff``
        block's ``reviewed-content-digest`` + attestation list vary. The signed
        body is rendered twice -- once with ``_pending_`` to compute the genuine
        §5.3 digest over the fixed signed sections, once with that digest recorded.
        """
        return self._signed_sections() + (
            "## Signoff\n"
            "- name: Ale\n"
            "- date: 2026-06-03\n"
            f"- reviewed-content-digest: {digest}\n"
            "- role: human-signer\n"
            "- omission-classes-attested:\n"
            f"{attested_block}\n"
        )

    def _coverage_map_body_without_signoff(self) -> str:
        """Render a structurally-incomplete coverage-map with NO ``## Signoff``.

        The four signed sections are present + ordered, but the mandatory
        ``## Signoff`` section is absent -> the verify core's structural /
        missing-digest gate refuses (there is no signoff to verify).
        """
        return self._signed_sections().rstrip("\n") + "\n"

    def _signed_sections(self) -> str:
        """The four FIXED §5.1 signed sections (everything before ``## Signoff``)."""
        return (
            f"# Coverage Map -- {self._feature_id}\n"
            "\n"
            "## Feature surface declared\n"
            "- the-feature-end-cycle-runs-the-real-coverage-map-verify\n"
            "\n"
            "## NOT covered -- and why\n"
            "_all declared surface is covered_\n"
            "\n"
            "## Known residues carried forward\n"
            "_none_\n"
            "\n"
            "## Negative-space completeness statement\n"
            "Every manifest domain is covered or listed as uncovered on its "
            "dimension row.\n"
            "\n"
        )

    def _write_feature_delta_with_e2e_block(self) -> None:
        feature_dir = self._feature_dir
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "feature-delta.md").write_text(
            "# Feature Delta -- oss-feature-end-cycle-demo\n\n"
            "## Environmental E2E\n\n"
            "- test: tests/test_cycle_demo_e2e.py\n",
            encoding="utf-8",
        )

    def _write_passing_env_e2e_test(self) -> None:
        tests_dir = self._feature_root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_cycle_demo_e2e.py").write_text(
            "def test_installed_artifact_importable() -> None:\n"
            "    import cycle_demo\n\n"
            "    assert cycle_demo.OK is True\n",
            encoding="utf-8",
        )

    def _write_installable_project(self) -> None:
        feature_root = self._feature_root
        feature_root.mkdir(parents=True, exist_ok=True)
        (feature_root / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools>=61"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "cycle-demo"\n'
            'version = "0.0.1"\n\n'
            "[tool.setuptools]\n"
            'py-modules = ["cycle_demo"]\n',
            encoding="utf-8",
        )
        (feature_root / "cycle_demo.py").write_text("OK = True\n", encoding="utf-8")

    def _write_walking_skeleton_manifest(self) -> None:
        feature_dir = self._feature_dir
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "walking-skeleton.json").write_text(
            json.dumps(
                {
                    "feature_id": str(self._feature_id),
                    "feature_root": str(self._feature_root),
                    "entry_points": [],
                }
            ),
            encoding="utf-8",
        )

    @property
    def _feature_dir(self) -> Path:
        return self._project_root / "docs" / "feature" / str(self._feature_id)

    @property
    def _feature_root(self) -> Path:
        return self._project_root / "src" / "cycle_demo_project"

    # --- subprocess plumbing -------------------------------------------------

    def _ledger(self) -> AtCompletionLedger:
        return AtCompletionLedger(self._feature_id, self._project_root)

    def _dispatch(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point."""
        # Keyless post-demotion (oss-review-verdict-demotion S4): scrub any
        # ambient signing key so the cycle's sign-leg runs entirely keyless.
        # Restored in `finally` -- shared-process safe.
        prior_key = os.environ.pop("NWAVE_REVIEWER_SIGNING_KEY", None)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                list(argv), cwd=str(self._project_root)
            )
        finally:
            if prior_key is not None:
                os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = prior_key
        return subprocess.CompletedProcess(argv, exit_code, stdout, stderr)


def _carries_cycle_refusal(stdout: str, stderr: str) -> bool:
    """Whether the refusal came from the CYCLE's own fail-closed check.

    The production cycle emits a structured ``{"event": "FeatureEndCycleRefused",
    ...}`` payload when the REAL coverage-map verify leg REFUSES (the same shape
    slice-03's gate-fail refusal carries) -- a real fail-closed refusal, NOT a
    dispatcher miss. An unknown-verb dispatcher error emits NO such payload, so
    this returns False and the unsigned scenario stays RED until the real cycle
    runs the real verify, reads its REAL refusal, and fail-closes with its own
    marker. This is the discriminator that closes the vacuous-refusal trap.
    """
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("event") == "FeatureEndCycleRefused":
                return True
    return False


def _extract_missing_records(stdout: str) -> frozenset[str]:
    """Pull the `missing_records` set off the integrity verdict's stdout.

    ``des verify-integrity`` emits a structured ``{"event":
    "FeatureEndCycleIncomplete", "missing_records": [...]}`` verdict when
    records are absent. Returns the named missing set (empty when the feature
    reconciled -- the slice-04 signed-PASS expectation).
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        missing = payload.get("missing_records")
        if isinstance(missing, list):
            return frozenset(str(record) for record in missing)
    return frozenset()


# --- §5.3 canonicalization -------------------------------------------------
#
# The §5.3 7-step canonicalization (select signed sections + normalize +
# sha256) is single-sourced in the sibling ``signed_coverage_map`` module --
# the same builder writes the GENUINE digest into the honest-signed fixture, so
# the fixture's digest matches its body by construction. ``_compute_canonical_digest``
# is imported (test infrastructure staging a genuinely-signed artifact, not the SUT).


__all__ = [
    "CycleResult",
    "FeatureEndCoverageMapComposition",
    "IntegrityVerdict",
]
