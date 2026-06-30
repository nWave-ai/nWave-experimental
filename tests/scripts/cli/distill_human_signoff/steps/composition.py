"""Composition root for the fix-distill-human-signoff acceptance set.

F-DISTILL-HUMAN-SIGNOFF (Mandate-12 criteria 2-3, Pillar 3). Wires the
PRODUCTION coverage-map surface -- the ``derive_coverage_map`` CLI (slice-01)
and, for downstream slices, the ``verify_coverage_map`` CLI -- against a
tmp_path feature project carrying a real ``component-manifest.yaml`` (the
substrate from F-DESIGN-COMPONENT-MANIFEST slices 01-03).

Business logic (write a manifest of a given shape, author a .feature file
carrying specific @covers: tags, invoke the CLI, capture the rendered
coverage-map) lives here as the single source of truth; step bodies delegate
to ``HumanSignoffComposition`` methods and never inline logic.

Layer 3 (subprocess / FS acceptance): the ``derive_coverage_map`` CLI is the
driving port; the only driven ports are the real filesystem (tmp_path repo +
the framework schema). Sad paths are example-based (Mandate 11); the
@property-tagged parser-edge coverage is realised as Scenario Outline rows,
not a Hypothesis @given (Mandate 9 -- this is layer 3; closed finite parser-
edge domain).

RED-scaffold note: ``scripts/cli/derive_coverage_map.py`` is a RED scaffold
on master (slice-01 implements it). The CLI entry point raises
``AssertionError`` so every scenario is RED (missing functionality), not
BROKEN (import error) -- the import below resolves cleanly because the
scaffold module exists (Mandate 7).
"""

from __future__ import annotations

import ast as _ast
import hashlib
import json as _json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    CAP,
    COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT,
    COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT,
    LEDGER_EVENT_COVERAGE_MAP_SIGNED_OFF,
    LEDGER_WRITER_FUNCTION,
    LEDGER_WRITER_MODULE,
    MANDATORY_SECTIONS_IN_ORDER,
    TRAILER_KEY,
    CallGraphLayer,
    CapAndNotApplicableState,
    CoverageDimension,
    FeatureId,
    ManifestDomainId,
    OmissionClassListShape,
    ParserEdgeShape,
    SignedSection,
    StalenessCause,
    Touchpoint,
    UnsignedState,
    VerifyTamperOrInput,
)


# Repo root -- the four-level-up parent of this file
# (tests/scripts/cli/distill_human_signoff/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]


# A grounded sut: symbol the manifest entries reference (real CLI file).
_GROUNDED_SUT = "scripts/cli/derive_coverage_map.py::main"


# Dimension -> canonical_category mapping (slice-01 AT2 routes a domain to its
# dimension row via the canonical-category enum on the manifest entry; this
# table is the SSOT for that routing).
_CANONICAL_CATEGORY_BY_DIMENSION: dict[CoverageDimension, str] = {
    CoverageDimension.ENVIRONMENTAL: "C7",  # SFDIPOT-style env/interruption
    CoverageDimension.BEHAVIOURAL: "C2",  # state/transition behaviour
    CoverageDimension.PROCESS: "C5",  # mode-flag / decision-table
    CoverageDimension.OTHER: "C6",  # negative & robustness fallback
}


def _domain_item(
    entry_id: str, canonical_category: str, sut: str = _GROUNDED_SUT
) -> str:
    """One well-formed unbounded-input-domains list item (every required key).

    Mirrors the F-DESIGN-COMPONENT-MANIFEST entry shape so the substrate's
    schema validator (Draft 2020-12) accepts the manifest.
    """
    return textwrap.dedent(
        f"""\
          - id: {entry_id}
            sut: {sut}
            domain: >
              The derive_coverage_map CLI scans arbitrary feature trees --
              an unbounded input domain not finite-enumerable.
            why-unbounded: "arbitrary feature-tree shapes"
            canonical-category: {canonical_category}
            declared-at: design
        """
    )


def _manifest_yaml(domain_ids_by_dimension: dict[CoverageDimension, str]) -> str:
    """Render a well-formed component-manifest.yaml with one entry per dimension."""
    entries = "".join(
        _domain_item(domain_id, _CANONICAL_CATEGORY_BY_DIMENSION[dimension])
        for dimension, domain_id in domain_ids_by_dimension.items()
    )
    return (
        "schema-version: 2026-05-22\n"
        "feature-id: fix-distill-human-signoff\n"
        "declared-at: design\n"
        "unbounded-input-domains:\n" + entries
    )


@dataclass(frozen=True)
class CliResult:
    """Observable result of one derive_coverage_map invocation."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass
class HumanSignoffComposition:
    """Production-wired composition root for slice-01.

    feature_root is a tmp_path subdirectory acting as ``docs/feature/{id}/``.
    The composition root creates the directory layout, writes the manifest +
    scenario fixtures, and invokes the real CLI as a subprocess.
    """

    feature_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) -- port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observables this composition exposes.

        Universe entries are port-exposed names, never internal struct fields:
        the manifest file presence, the coverage-map file presence + bytes
        digest, the feature-delta presence.
        """
        manifest_path = self.feature_root / "design" / "component-manifest.yaml"
        coverage_map_path = self.feature_root / "distill" / "coverage-map.md"
        feature_delta_path = self.feature_root / "feature-delta.md"
        return {
            "manifest.present": manifest_path.is_file(),
            "coverage_map.present": coverage_map_path.is_file(),
            "feature_delta.present": feature_delta_path.is_file(),
        }

    # ------------------------------------------------------------------
    # Feature-tree authoring (Given-step delegates).
    # ------------------------------------------------------------------

    def create_feature_dir(self, feature_id: FeatureId) -> None:
        """Author the ``docs/feature/{id}/`` skeleton: design/ + distill/."""
        (self.feature_root / "design").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "distill").mkdir(parents=True, exist_ok=True)
        (self.feature_root / "feature-delta.md").write_text(
            f"# {feature_id} -- acceptance fixture feature\n",
            encoding="utf-8",
        )

    def write_manifest_with_one_domain_per_dimension(
        self,
    ) -> dict[CoverageDimension, ManifestDomainId]:
        """Author a manifest with one domain per dimension (4 domains total).

        Returns the {dimension -> domain-id} mapping so the caller can decide
        which domains to cover with @covers: tags and which to leave uncovered.
        """
        domain_ids = {
            CoverageDimension.ENVIRONMENTAL: ManifestDomainId("env-arbitrary-tree"),
            CoverageDimension.BEHAVIOURAL: ManifestDomainId("behav-state-transitions"),
            CoverageDimension.PROCESS: ManifestDomainId("proc-mode-flag-cartesian"),
            CoverageDimension.OTHER: ManifestDomainId("other-robustness-input"),
        }
        manifest_path = self.feature_root / "design" / "component-manifest.yaml"
        manifest_path.write_text(
            _manifest_yaml({d: str(domain_ids[d]) for d in domain_ids}),
            encoding="utf-8",
        )
        return domain_ids

    def write_scenario_covering_all_domains(
        self, domain_ids: dict[CoverageDimension, ManifestDomainId]
    ) -> None:
        """Write a .feature whose Scenario tag line carries @covers: for every domain."""
        feature_dir = self.feature_root / "acceptance"
        feature_dir.mkdir(exist_ok=True)
        covers_tags = " ".join(f"@covers:{did}" for did in domain_ids.values())
        feature_dir.joinpath("fully-covered.feature").write_text(
            "Feature: Every manifest domain is exercised by a tagged scenario\n"
            "\n"
            f"  {covers_tags}\n"
            "  Scenario: Each domain has a witnessing scenario\n"
            "    Given fixture state\n"
            "    When the system runs\n"
            "    Then nothing is left uncovered\n",
            encoding="utf-8",
        )

    def write_scenario_covering_subset(
        self,
        domain_ids: dict[CoverageDimension, ManifestDomainId],
        leave_uncovered: CoverageDimension,
    ) -> None:
        """Write a .feature whose tags cover every domain EXCEPT one dimension's."""
        feature_dir = self.feature_root / "acceptance"
        feature_dir.mkdir(exist_ok=True)
        covers_tags = " ".join(
            f"@covers:{did}"
            for dim, did in domain_ids.items()
            if dim != leave_uncovered
        )
        feature_dir.joinpath("partial-cover.feature").write_text(
            "Feature: One dimension is deliberately left uncovered\n"
            "\n"
            f"  {covers_tags}\n"
            "  Scenario: All-but-one domain has a witnessing scenario\n"
            "    Given fixture state\n"
            "    When the system runs\n"
            "    Then exactly one dimension is left uncovered\n",
            encoding="utf-8",
        )

    def write_parser_edge_fixture(
        self,
        edge: ParserEdgeShape,
        domain_ids: dict[CoverageDimension, ManifestDomainId],
    ) -> None:
        """Author the .feature shape that witnesses one parser-edge equivalence class.

        Each edge is one of the five §4.1b parser-contract bullets.
        """
        feature_dir = self.feature_root / "acceptance"
        feature_dir.mkdir(exist_ok=True)
        env = str(domain_ids[CoverageDimension.ENVIRONMENTAL])
        behav = str(domain_ids[CoverageDimension.BEHAVIOURAL])
        if edge is ParserEdgeShape.MULTI_TAG_ONE_LINE:
            body = (
                "Feature: Two covers tags share one tag line\n"
                "\n"
                f"  @covers:{env} @covers:{behav}\n"
                "  Scenario: Two domains on one tag line\n"
                "    Given fixture state\n"
                "    When the system runs\n"
                "    Then both domains count as covered\n"
            )
        elif edge is ParserEdgeShape.OUTLINE_COVERS_ONCE:
            body = (
                "Feature: A scenario outline covers its domain once\n"
                "\n"
                f"  @covers:{env}\n"
                "  Scenario Outline: One domain across three example rows\n"
                "    Given <input>\n"
                "    When the system runs\n"
                "    Then <outcome>\n"
                "\n"
                "    Examples:\n"
                "      | input | outcome |\n"
                "      | a     | A       |\n"
                "      | b     | B       |\n"
                "      | c     | C       |\n"
            )
        elif edge is ParserEdgeShape.FEATURE_LINE_IGNORED:
            body = (
                f"@covers:{env}\n"
                "Feature: A covers tag on the Feature line is ignored\n"
                "\n"
                "  Scenario: No tag on the Scenario tag line\n"
                "    Given fixture state\n"
                "    When the system runs\n"
                "    Then no domain is counted as covered\n"
            )
        elif edge is ParserEdgeShape.NO_TAG_EMPTY:
            body = (
                "Feature: No covers tag anywhere\n"
                "\n"
                "  Scenario: A scenario with zero covers tags\n"
                "    Given fixture state\n"
                "    When the system runs\n"
                "    Then no domain is counted as covered\n"
            )
        elif edge is ParserEdgeShape.MALFORMED_DOMAIN_ID:
            body = (
                "Feature: A covers tag names an identifier that violates the schema pattern\n"
                "\n"
                "  @covers:Env_Arbitrary_Tree\n"  # uppercase + underscore violates ^[a-z0-9-]+$
                "  Scenario: A malformed identifier under the covers prefix\n"
                "    Given fixture state\n"
                "    When the system runs\n"
                "    Then the renderer refuses fail-closed\n"
            )
        else:  # pragma: no cover -- enum is exhaustive
            raise ValueError(f"unknown parser-edge: {edge!r}")
        feature_dir.joinpath(f"parser-edge-{edge.value}.feature").write_text(
            body, encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegate).
    # ------------------------------------------------------------------

    def run_derive_coverage_map(self) -> CliResult:
        """Invoke the derive_coverage_map CLI as a subprocess (the driving port).

        Subprocess, not in-process: this is layer-3 wiring-proof for the CLI
        (consistent with the F-DESIGN-COMPONENT-MANIFEST infrastructure-policy
        row that pins the validation CLI to subprocess invocation).
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.derive_coverage_map",
                "--feature-root",
                str(self.feature_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # ------------------------------------------------------------------
    # Then-step observables (rendered-document inspection).
    # ------------------------------------------------------------------

    def read_coverage_map(self) -> str:
        """Return the rendered coverage-map Markdown body."""
        return (self.feature_root / "distill" / "coverage-map.md").read_text(
            encoding="utf-8"
        )

    def coverage_map_path(self) -> Path:
        return self.feature_root / "distill" / "coverage-map.md"

    # ==================================================================
    # SLICE-02 composition methods (anti-omission + not-applicable + CAP).
    # ==================================================================
    #
    # Slice-02 extends ``derive_coverage_map`` with three refusal modes:
    #
    # 1. OmissionDetected -- the designer authored a not-covered attestation
    #    file (``docs/feature/{id}/distill/not-covered-attestation.md``) that
    #    drops a manifest domain. The producer reads this file as the
    #    designer's SSOT for "what is not covered" and compares against
    #    (manifest \\ @covers:-tagged).
    #
    # 2. CoverageMapOverCap -- the (manifest \\ @covers:-tagged) set has more
    #    than CAP entries. A coverage-map a human cannot evaluate in one
    #    sitting is itself a defect signal; the producer refuses to render.
    #
    # 3. SignoffMissing -- the manifest carries a ``not-applicable:`` marker
    #    (§4.2 fail-functional branch); the producer expects a signoff file
    #    carrying the ``manifest-not-applicable-attested:`` line. If absent,
    #    the producer refuses (no two-gate bypass).

    def attestation_path(self) -> Path:
        """The designer's not-covered attestation file (slice-02 input)."""
        return self.feature_root / "distill" / "not-covered-attestation.md"

    def signoff_path(self) -> Path:
        """The human-authored signoff file (slice-02 input -- §4.2 branch)."""
        return self.feature_root / "distill" / "signoff.md"

    # ------------------------------------------------------------------
    # Slice-02 universe (extends slice-01's with the two new inputs).
    # ------------------------------------------------------------------

    def capture_slice02_universe(self) -> dict[str, object]:
        """Snapshot the slice-02 port-exposed observables.

        Extends ``capture_universe`` with the two new input-file presences
        (designer's attestation, human signoff) -- universe entries are
        port-exposed file-presence names, never internal struct fields.
        """
        base = self.capture_universe()
        base["attestation.present"] = self.attestation_path().is_file()
        base["signoff.present"] = self.signoff_path().is_file()
        return base

    # ------------------------------------------------------------------
    # Slice-02 Given-step delegates.
    # ------------------------------------------------------------------

    def author_attestation_dropping_domain(
        self,
        domain_ids: dict[CoverageDimension, ManifestDomainId],
        dropped_dimension: CoverageDimension,
    ) -> None:
        """Author a not-covered attestation that silently drops a domain.

        The renderer reads ``not-covered-attestation.md`` as the designer's
        SSOT for "what is not covered". If the file is present AND a manifest
        domain is missing from (covered ∪ attested), the renderer refuses with
        ``OmissionDetected``.
        """
        # The attestation lists EVERY uncovered domain EXCEPT the dropped one
        # -- a manifest domain neither covered (no @covers: tag) nor listed
        # here is the omission the renderer must refuse to ship.
        listed = [
            str(did) for dim, did in domain_ids.items() if dim != dropped_dimension
        ]
        body = "# Designer's not-covered attestation\n\n"
        if listed:
            body += "Not covered (designer-attested):\n"
            for did in sorted(listed):
                body += f"- {did}\n"
        else:
            body += "Not covered (designer-attested): none\n"
        self.attestation_path().parent.mkdir(parents=True, exist_ok=True)
        self.attestation_path().write_text(body, encoding="utf-8")

    def stage_over_cap_manifest(self, uncovered_count: int) -> None:
        """Write a manifest with ``uncovered_count`` uncovered domains.

        Replaces the slice-01 four-domain manifest with one that has
        ``uncovered_count`` entries -- all uncovered (no .feature files exist)
        -- so the (manifest \\ covered) cardinality exceeds CAP.
        """
        # Build N domain entries; cycle through dimensions to keep them
        # well-typed in the manifest. None of them are covered (no .feature
        # file is authored here), so (manifest \\ covered) = N.
        dimensions = list(CoverageDimension)
        entries = {}
        for i in range(uncovered_count):
            dim = dimensions[i % len(dimensions)]
            domain_id = f"over-cap-domain-{i:02d}"
            entries[domain_id] = _CANONICAL_CATEGORY_BY_DIMENSION[dim]
        manifest_path = self.feature_root / "design" / "component-manifest.yaml"
        body = (
            "schema-version: 2026-05-22\n"
            "feature-id: fix-distill-human-signoff\n"
            "declared-at: design\n"
            "unbounded-input-domains:\n"
            + "".join(_domain_item(did, cat) for did, cat in entries.items())
        )
        manifest_path.write_text(body, encoding="utf-8")

    def stage_not_applicable_manifest(self) -> None:
        """Replace the slice-01 manifest with the §4.2 not-applicable marker.

        Empty ``unbounded-input-domains:`` list + ``not-applicable:`` field --
        the F-DESIGN-COMPONENT-MANIFEST resolver folds this into
        ``ManifestState.B`` (with marker). The renderer must require the
        human signoff to carry the ``manifest-not-applicable-attested:`` line.
        """
        manifest_path = self.feature_root / "design" / "component-manifest.yaml"
        manifest_path.write_text(
            "schema-version: 2026-05-22\n"
            "feature-id: fix-distill-human-signoff\n"
            "declared-at: design\n"
            "not-applicable: this feature has no unbounded-input-domain surface\n"
            "unbounded-input-domains: []\n",
            encoding="utf-8",
        )

    def author_signoff_with_attestation(self) -> None:
        """Author a signoff file carrying the manifest-not-applicable-attested line."""
        self.signoff_path().parent.mkdir(parents=True, exist_ok=True)
        self.signoff_path().write_text(
            "# Signoff\n"
            "\n"
            "- name: test-acceptance-designer\n"
            "- date: 2026-05-23\n"
            "- role: acceptance-designer\n"
            "- manifest-not-applicable-attested: yes\n",
            encoding="utf-8",
        )

    def author_signoff_without_attestation(self) -> None:
        """Author a signoff file MISSING the manifest-not-applicable-attested line.

        Exercises the §4.2 keystone -- the producer must NOT accept a
        not-applicable manifest unless the human has explicitly attested. No
        attestation line = ``SignoffMissing`` refusal (neither brick nor
        bypass).
        """
        self.signoff_path().parent.mkdir(parents=True, exist_ok=True)
        self.signoff_path().write_text(
            "# Signoff\n"
            "\n"
            "- name: test-acceptance-designer\n"
            "- date: 2026-05-23\n"
            "- role: acceptance-designer\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Slice-02 AT3 outline router.
    # ------------------------------------------------------------------

    def stage_cap_and_not_applicable_state(
        self,
        state: CapAndNotApplicableState,
        domain_ids: dict[CoverageDimension, ManifestDomainId],
    ) -> None:
        """Stage the precondition for one AT3 outline row.

        Routes each Scenario Outline row to its precondition author:
        OVER_CAP rewrites the manifest with CAP+1 uncovered entries;
        NOT_APPLICABLE_* rewrites the manifest with the marker + authors a
        signoff with / without the attestation line. The slice-01 Background
        manifest (four-domain) is overwritten in every case.
        """
        if state is CapAndNotApplicableState.OVER_CAP:
            self.stage_over_cap_manifest(uncovered_count=CAP + 1)
        elif state is CapAndNotApplicableState.NOT_APPLICABLE_ATTESTED:
            self.stage_not_applicable_manifest()
            self.author_signoff_with_attestation()
        elif state is CapAndNotApplicableState.NOT_APPLICABLE_NOT_ATTESTED:
            self.stage_not_applicable_manifest()
            self.author_signoff_without_attestation()
        else:  # pragma: no cover -- enum is exhaustive
            raise ValueError(f"unknown CapAndNotApplicableState: {state!r}")

    # ------------------------------------------------------------------
    # Slice-02 Then-step observables (refusal-token capture).
    # ------------------------------------------------------------------

    def stderr_contains_refusal_token(self, token: str, result: CliResult) -> bool:
        """Return True iff the named refusal token appears on stderr.

        The exit code is the gate; the token is the structured cause-of-
        refusal SSOT (earned-trust: the named token must accompany the exit
        code so a future reader sees WHY the renderer refused).
        """
        return token in result.stderr

    # ==================================================================
    # SLICE-03 composition methods -- verify_coverage_map gate CLI.
    # ==================================================================
    #
    # Slice-03 adds a SECOND driving-port CLI -- ``verify_coverage_map`` --
    # that consumes the slice-01/02 output (a rendered + signed coverage-map)
    # and emits a verdict:
    #
    #   * exit 0 -- accepted (structure OK, digest matches, mandatory rows in
    #     order, signoff block present + readable).
    #   * exit 1 + ``StructuralIncomplete`` -- a mandatory section missing or
    #     the four dimension rows out of order.
    #   * exit 1 + ``SignoffStale`` -- a signed section's body was edited
    #     after the digest was recorded (G3 widened section set: tampering
    #     ANY of the four signed sections moves the digest).
    #   * exit 2 + ``MalformedInput`` -- the manifest, coverage-map, or
    #     ledger cannot be parsed (distinct from the exit-1 verdicts).
    #
    # The slice-03 ATs ALSO carry the §5.3 cross-tree canonicalization
    # conformance probe (AT3 row f / G4): the verify CLI exposes a
    # ``digest-golden-fixture`` subcommand that reads a golden raw input from
    # ``nWave/data/coverage-map-digest-fixtures/`` and emits the lowercase
    # hex digest the local canonicalization produces. The expected digest is
    # committed alongside the input in the same fixtures dir.

    def coverage_map_signoff_path(self) -> Path:
        """The signed coverage-map (slice-03 input)."""
        return self.feature_root / "distill" / "coverage-map.md"

    def signoff_digest_path(self) -> Path:
        """The recorded canonical-content digest captured at signoff time.

        Slice-03 stores the §5.3 digest as a sidecar file so the verify CLI
        can compare ``recompute(canonical_content) == sidecar_digest``. The
        signing operation (``sign_coverage_map`` below) computes the digest
        once and writes both the body + the sidecar.
        """
        return self.feature_root / "distill" / "coverage-map.signoff.digest"

    def golden_fixtures_root(self) -> Path:
        """Repo-relative path to the §5.3 G4 golden conformance fixtures."""
        return _REPO_ROOT / "nWave" / "data" / "coverage-map-digest-fixtures"

    # ------------------------------------------------------------------
    # Slice-03 universe (extends slice-02 with the signoff-digest sidecar).
    # ------------------------------------------------------------------

    def capture_slice03_universe(self) -> dict[str, object]:
        """Snapshot the slice-03 port-exposed observables.

        Extends ``capture_slice02_universe`` with the signoff-digest sidecar
        (the canonical-content digest captured at signoff time, persisted
        as a file so the verify CLI can compare against it). All entries
        are file-presence flags -- universe entries are port-exposed names
        only, never internal struct fields (Mandate 8).
        """
        base = self.capture_slice02_universe()
        base["signoff_digest.present"] = self.signoff_digest_path().is_file()
        return base

    # ------------------------------------------------------------------
    # Slice-03 Given-step delegates -- sign + tamper + remove + stage.
    # ------------------------------------------------------------------

    def sign_coverage_map(self) -> None:
        """Render + sign a coverage-map: emit body + ``## Signoff`` + digest.

        The slice-03 Background ("a coverage map has been authored and
        signed by a human") is satisfied here:
          1. Render a minimal four-signed-section coverage-map body.
          2. Compute the §5.3 canonical-content digest over the four signed
             sections (excluding ``## Signoff``).
          3. Append a ``## Signoff`` block carrying name/date/digest.
          4. Persist the recorded digest as a sidecar so the verify CLI can
             re-compute the live canonical content and compare.

        The verify CLI under test (slice-03) MUST reproduce the same
        canonicalization algorithm and digest. This composition method is
        intentionally a simple reference impl so the test reads as the
        contract a verifying CLI must honour.
        """
        body = self._render_signed_coverage_map_body()
        digest = self._compute_canonical_digest(body)
        attested_block = self._render_omission_classes_attested_block()
        signoff_block = (
            "\n## Signoff\n"
            "\n"
            "- name: test-human-signer\n"
            "- date: 2026-05-23\n"
            f"- reviewed-content-digest: {digest}\n"
            "- role: human-signer\n" + attested_block
        )
        coverage_path = self.coverage_map_signoff_path()
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_path.write_text(body + signoff_block, encoding="utf-8")
        self.signoff_digest_path().write_text(digest + "\n", encoding="utf-8")

    def tamper_signed_section(self, section: SignedSection) -> None:
        """Mutate one signed section's body AFTER signoff.

        The recorded digest sidecar stays put (the human's record); the
        live coverage-map body diverges from what the digest covered. The
        verify CLI must recompute the digest over the live body and refuse
        with ``SignoffStale`` when it no longer matches.

        This is the G3 widened-section-set probe: a tamper in ANY of the
        four §5.3 signed sections (NOT just ``## Feature surface declared``
        and ``## NOT covered -- and why``) must move the digest. The four
        tamper outline rows witness one section each.
        """
        coverage_path = self.coverage_map_signoff_path()
        body = coverage_path.read_text(encoding="utf-8")
        section_heading = section.value
        # Insert a tampered line directly under the section heading -- the
        # heading itself stays put so the structural check still passes;
        # only the digest-covered body content changes.
        sentinel = "\nTAMPERED-AFTER-SIGNOFF-CONTENT\n"
        replaced = body.replace(section_heading + "\n", section_heading + sentinel, 1)
        if replaced == body:
            raise ValueError(
                f"tamper failed: section heading {section_heading!r} not found "
                f"in coverage-map body -- sign_coverage_map() must emit it first"
            )
        coverage_path.write_text(replaced, encoding="utf-8")

    def remove_mandatory_section(self, section: SignedSection) -> None:
        """Delete one mandatory section heading from the signed coverage-map.

        Exercises slice-03 AT2 ``StructuralIncomplete`` -- a coverage-map
        missing a §5.1 mandatory section (or carrying them out of order)
        fails the structural check before the digest is even recomputed.
        """
        coverage_path = self.coverage_map_signoff_path()
        body = coverage_path.read_text(encoding="utf-8")
        section_heading = section.value
        # Drop the heading line entirely; preserve everything else so the
        # failure mode is "section missing", not "file unparseable".
        lines = body.splitlines(keepends=True)
        kept = [line for line in lines if line.rstrip("\n") != section_heading]
        if len(kept) == len(lines):
            raise ValueError(
                f"remove failed: section heading {section_heading!r} not found "
                f"in coverage-map body -- sign_coverage_map() must emit it first"
            )
        coverage_path.write_text("".join(kept), encoding="utf-8")

    def stage_malformed_input(self) -> None:
        """Replace the signed coverage-map with bytes that cannot be parsed.

        Exercises slice-03 AT3 row e -- a coverage-map (or manifest, or
        ledger) the verify CLI cannot even tokenise must refuse with
        ``MalformedInput`` (exit 2), distinct from the exit-1 refusals.
        """
        coverage_path = self.coverage_map_signoff_path()
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        # Byte sequence that is not valid Markdown structure for the L1
        # §5.1 section layout AND is not valid UTF-8-safe content for the
        # signoff block parser -- the CLI must classify as MalformedInput.
        coverage_path.write_bytes(b"\x00\x01\x02 not-a-coverage-map \xff\xfe")

    def stage_golden_fixture_pair(self) -> tuple[Path, Path]:
        """Author one §5.3 G4 golden conformance fixture pair on disk.

        Returns ``(raw_input_path, expected_digest_path)``. The raw input is
        a minimal canonical coverage-map body; the expected digest is the
        lowercase hex SHA256 the §5.3 canonicalization produces over it.
        The DISTILL composition computes both deterministically so any
        future verify-CLI implementation can be probed against the same
        pair (Earned-Trust: the cross-tree contract is mechanically
        probed, not trusted).

        This composition method seeds the fixtures dir on first call -- the
        slice-03 GREEN cycle may add more pairs; DISTILL ships the floor.
        """
        fixtures_dir = self.golden_fixtures_root()
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        raw_input = self._render_signed_coverage_map_body()
        expected_digest = self._compute_canonical_digest(raw_input)
        raw_path = fixtures_dir / "fixture-01-minimal-signed.coverage-map.md"
        digest_path = fixtures_dir / "fixture-01-minimal-signed.expected-digest"
        raw_path.write_text(raw_input, encoding="utf-8")
        digest_path.write_text(expected_digest + "\n", encoding="utf-8")
        return raw_path, digest_path

    # ------------------------------------------------------------------
    # Slice-03 driving-port invocation (When-step delegate).
    # ------------------------------------------------------------------

    def run_verify_coverage_map(self) -> CliResult:
        """Invoke the verify_coverage_map verify CLI as a subprocess.

        The driving port for slice-03. Subprocess (layer-3 wiring-proof)
        consistent with slice-01/02's invocation of derive_coverage_map --
        same scripts/cli/ spine-gate sibling pattern.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.verify_coverage_map",
                "verify",
                "--feature-root",
                str(self.feature_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def run_verify_digest_golden_fixture(self, raw_input_path: Path) -> CliResult:
        """Invoke verify_coverage_map digest-golden-fixture <raw>.

        Slice-03 AT3 row f (G4 cross-tree canonicalization conformance):
        the verify CLI's subcommand reads the golden raw input, runs the
        §5.3 canonicalization locally, and prints the lowercase hex digest
        on stdout. The test compares it byte-for-byte against the
        committed expected-digest file -- a drift in either tree's local
        canonicalization fails the test on the drifting commit.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.verify_coverage_map",
                "digest-golden-fixture",
                "--input",
                str(raw_input_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # ------------------------------------------------------------------
    # Slice-03 AT3 outline router.
    # ------------------------------------------------------------------

    def stage_tamper_or_input(self, choice: VerifyTamperOrInput) -> Path | None:
        """Stage the precondition for one AT3 outline row.

        Each row maps to one tamper/malformed/golden-fixture preparation.
        Returns the raw-input fixture path for the golden-fixture row (the
        Then-step uses it to invoke ``run_verify_digest_golden_fixture``);
        returns ``None`` for the tamper/malformed rows (the Then-step uses
        ``run_verify_coverage_map`` over the staged feature-root).
        """
        if choice is VerifyTamperOrInput.TAMPER_FEATURE_SURFACE:
            self.tamper_signed_section(SignedSection.FEATURE_SURFACE_DECLARED)
            return None
        if choice is VerifyTamperOrInput.TAMPER_NOT_COVERED:
            self.tamper_signed_section(SignedSection.NOT_COVERED_TABLE)
            return None
        if choice is VerifyTamperOrInput.TAMPER_KNOWN_RESIDUES:
            self.tamper_signed_section(SignedSection.KNOWN_RESIDUES)
            return None
        if choice is VerifyTamperOrInput.TAMPER_NEGATIVE_SPACE:
            self.tamper_signed_section(SignedSection.NEGATIVE_SPACE)
            return None
        if choice is VerifyTamperOrInput.MALFORMED_INPUT:
            self.stage_malformed_input()
            return None
        if choice is VerifyTamperOrInput.GOLDEN_FIXTURE_CONFORMANCE:
            raw_path, _ = self.stage_golden_fixture_pair()
            return raw_path
        # pragma: no cover -- enum is exhaustive
        raise ValueError(f"unknown VerifyTamperOrInput: {choice!r}")

    # ------------------------------------------------------------------
    # Slice-03 Then-step observables -- structural inspection.
    # ------------------------------------------------------------------

    def coverage_map_has_section_in_order(self, sections: tuple[str, ...]) -> bool:
        """Return True iff every section appears in order in the live map."""
        body = self.coverage_map_signoff_path().read_text(encoding="utf-8")
        last_index = -1
        for heading in sections:
            idx = body.find(heading)
            if idx < 0 or idx <= last_index:
                return False
            last_index = idx
        return True

    def read_expected_digest_for_fixture(self, raw_path: Path) -> str:
        """Return the committed expected digest for a §5.3 G4 golden fixture."""
        raw_path.with_suffix("").with_suffix(".expected-digest")
        # NOTE: with_suffix logic does not chain reliably for ``.coverage-map.md``
        # tails; compute the sibling explicitly instead.
        sibling = raw_path.parent / (
            raw_path.name.removesuffix(".coverage-map.md") + ".expected-digest"
        )
        return sibling.read_text(encoding="utf-8").strip()

    # ------------------------------------------------------------------
    # Slice-03 internal helpers -- canonicalization + body rendering.
    # ------------------------------------------------------------------
    #
    # The §5.3 canonicalization algorithm is a 7-step ordered sequence. The
    # composition root carries a minimal reference impl so the verify CLI
    # under test can be probed against it (cross-tree G4 conformance). The
    # CLI under test must match this algorithm step-for-step OR be wrong.

    def _render_signed_coverage_map_body(self) -> str:
        """Return a minimal four-signed-section coverage-map body (no signoff).

        The body carries the four §5.1 mandatory signed sections in fixed
        L1 order. Used both by ``sign_coverage_map`` (to stage the signed
        baseline that slice-03 verifies) and by ``stage_golden_fixture_pair``
        (the raw input for the §5.3 G4 cross-tree conformance probe).
        """
        return (
            "# Coverage Map -- acceptance-fixture-feature\n"
            "\n"
            "## Feature surface declared\n"
            "- domain-fixture: minimal-signed-baseline\n"
            "\n"
            "## NOT covered -- and why\n"
            "| Dimension     | What is NOT covered | Why accepted | Residue? owner+bound |\n"
            "|---------------|--------------------|--------------|----------------------|\n"
            "| environmental | none               | n/a          | no                   |\n"
            "| behavioural   | none               | n/a          | no                   |\n"
            "| process       | none               | n/a          | no                   |\n"
            "| other         | none               | n/a          | no                   |\n"
            "\n"
            "## Known residues carried forward\n"
            "none\n"
            "\n"
            "## Negative-space completeness statement\n"
            "The four dimension rows above jointly exhaust the declared surface.\n"
        )

    def _compute_canonical_digest(self, body: str) -> str:
        """§5.3 canonicalization: select signed sections + normalize + sha256.

        Minimal reference implementation of the §5.3 7-step algorithm:
          1. Select the four signed sections (exclude ``## Signoff``).
          2. Normalize line endings to LF.
          3. Strip trailing whitespace on every line.
          4. Collapse blank-line runs to a single blank line; strip leading
             and trailing blank lines.
          5. Sort domain lines under ``## Feature surface declared``
             byte-wise ascending; dimension rows in ``## NOT covered``
             stay in fixed L1 order; residue lines + negative-space prose
             stay verbatim (after steps 2-4 normalization).
          6. Encode UTF-8 (no BOM).
          7. SHA256, lowercase hex.

        The implementation is intentionally compact -- it is the SSOT of
        what the verify CLI must reproduce. Drift in the CLI fails the
        slice-03 AT3 golden-fixture row (G4 cross-tree probe).
        """
        # Step 1 -- section selection.
        selected = self._select_signed_sections(body)
        # Step 2 -- LF normalization.
        selected = selected.replace("\r\n", "\n").replace("\r", "\n")
        # Step 3 -- strip trailing whitespace per line.
        selected = "\n".join(line.rstrip(" \t") for line in selected.split("\n"))
        # Step 4 -- collapse blank runs; strip leading/trailing blank lines.
        lines = selected.split("\n")
        collapsed: list[str] = []
        prev_blank = False
        for line in lines:
            if line == "":
                if not prev_blank:
                    collapsed.append(line)
                prev_blank = True
            else:
                collapsed.append(line)
                prev_blank = False
        while collapsed and collapsed[0] == "":
            collapsed.pop(0)
        while collapsed and collapsed[-1] == "":
            collapsed.pop()
        selected = "\n".join(collapsed)
        # Step 5 -- sort feature-surface domain lines byte-wise ascending.
        selected = self._sort_feature_surface_lines(selected)
        # Step 6 + 7 -- encode UTF-8 + sha256.
        return hashlib.sha256(selected.encode("utf-8")).hexdigest()

    def _select_signed_sections(self, body: str) -> str:
        """Return the four signed sections concatenated in L1 order.

        Excludes ``## Signoff`` (cannot digest the field carrying the
        digest). Headings of unknown sections are dropped silently.
        """
        # Split on top-level ``## `` headings while preserving heading text.
        chunks: dict[str, str] = {}
        current_heading: str | None = None
        buffer: list[str] = []
        for line in body.split("\n"):
            if line.startswith("## "):
                if current_heading is not None:
                    chunks[current_heading] = "\n".join(buffer)
                current_heading = line.rstrip()
                buffer = [current_heading]
            else:
                buffer.append(line)
        if current_heading is not None:
            chunks[current_heading] = "\n".join(buffer)
        signed = MANDATORY_SECTIONS_IN_ORDER[:-1]  # exclude ## Signoff
        return "\n".join(chunks.get(heading, "") for heading in signed)

    def _sort_feature_surface_lines(self, selected: str) -> str:
        """Sort domain bullet lines under ``## Feature surface declared``."""
        out_lines: list[str] = []
        in_feature_surface = False
        feature_surface_bullets: list[str] = []
        for line in selected.split("\n"):
            if line.startswith("## Feature surface declared"):
                in_feature_surface = True
                out_lines.append(line)
                continue
            if line.startswith("## ") and in_feature_surface:
                # Flush sorted bullets before the next section heading.
                out_lines.extend(sorted(feature_surface_bullets))
                feature_surface_bullets = []
                in_feature_surface = False
                out_lines.append(line)
                continue
            if in_feature_surface and line.startswith("- "):
                feature_surface_bullets.append(line)
            else:
                out_lines.append(line)
        if in_feature_surface and feature_surface_bullets:
            out_lines.extend(sorted(feature_surface_bullets))
        return "\n".join(out_lines)

    # ==================================================================
    # SLICE-04 composition methods -- signature contract triple.
    # ==================================================================
    #
    # Slice-04 binds the three signoff surfaces (block / trailer / ledger
    # record) to one identity -- the §5.3 canonical-content digest the
    # ``## Signoff`` block carries. Three driving ports:
    #
    #   * ``verify_coverage_map emit-trailer --feature-root <path>`` --
    #     subprocess CLI that prints the re-derived
    #     ``Coverage-Map-Signed-Off-By: <name> <date>`` trailer on stdout.
    #     AT1 happy-path uses this projection; AT1 sad-path stages a
    #     diverging hand-edited trailer and asserts ``TrailerMismatch``
    #     exit 1 from ``verify``.
    #   * The deterministic engine function
    #     ``src/des/adapters/driven/ledger/coverage_map_signoff_writer.write_coverage_map_signed_off``
    #     (called from AT2 via composition; AT3 scans its call-graph).
    #   * The AT-completion ledger JSONL file at
    #     ``{feature_root}/../../../.nwave/telemetry/atdd-pure/{feature_id}.jsonl``
    #     -- AT2 reads the appended ``CoverageMapSignedOff`` record back.
    #
    # AT3 is a STATIC AST check on the repository's source tree -- no
    # subprocess invocation. The composition exposes
    # ``static_call_graph_scan(layer)`` returning the offending caller
    # modules per layer (empty set = pass).

    # ------------------------------------------------------------------
    # Slice-04 universe (extends slice-03 with trailer + ledger observables).
    # ------------------------------------------------------------------

    def capture_slice04_universe(self) -> dict[str, object]:
        """Snapshot the slice-04 port-exposed observables.

        Extends ``capture_slice03_universe`` with the commit-trailer file
        presence and the count of ``CoverageMapSignedOff`` records on the
        AT-completion ledger. Universe entries are port-exposed observable
        names -- never internal struct fields (Mandate 8).
        """
        base = self.capture_slice03_universe()
        base["commit_trailer.present"] = self.commit_trailer_path().is_file()
        base["ledger.signed_off_record_count"] = (
            self._count_signed_off_records_on_ledger()
        )
        return base

    # ------------------------------------------------------------------
    # Slice-04 Given-step delegates -- author commit trailer (matching or diverging).
    # ------------------------------------------------------------------

    def commit_trailer_path(self) -> Path:
        """The mock commit-message file carrying the trailer the test asserts against.

        Slice-04 AT1 happy-path writes the trailer mechanically derived from
        the ``## Signoff`` block; AT1 sad-path writes a HAND-EDITED divergent
        trailer that the verify gate must refuse with ``TrailerMismatch``.
        """
        return self.feature_root / "distill" / "commit-trailer.txt"

    def write_commit_trailer_matching_signoff_block(self) -> None:
        """Author a commit trailer line whose value re-derives from the block.

        Reads the ``## Signoff`` block from the signed coverage-map, extracts
        ``name`` + ``date``, composes the trailer with the
        ``Coverage-Map-Signed-Off-By:`` key, and writes it to the mock
        commit-trailer file. The verify gate's ``emit-trailer`` subcommand
        MUST produce a byte-identical value (slice-04 AT1 happy path).
        """
        coverage_path = self.coverage_map_signoff_path()
        body = coverage_path.read_text(encoding="utf-8")
        signer_name, signer_date = self._extract_signoff_name_and_date(body)
        trailer_value = f"{signer_name} {signer_date}"
        self._write_commit_trailer(trailer_value)

    def write_commit_trailer_hand_edited_away_from_block(self) -> None:
        """Author a commit trailer line whose value DIVERGES from the block.

        Slice-04 AT1 sad-path: a human (or LLM) authors the trailer
        independently of the ``## Signoff`` block, claiming a different signer
        identity. The verify gate re-derives the trailer from the block,
        compares, and refuses with ``TrailerMismatch`` exit 1 -- the trailer
        is a mechanical PROJECTION (§6.1), never an independent claim.
        """
        diverging_value = "hand-edited-signer 1970-01-01"
        self._write_commit_trailer(diverging_value)

    def _write_commit_trailer(self, trailer_value: str) -> None:
        """Write the ``Coverage-Map-Signed-Off-By: <value>`` trailer to disk."""
        trailer_path = self.commit_trailer_path()
        trailer_path.parent.mkdir(parents=True, exist_ok=True)
        trailer_path.write_text(
            f"{TRAILER_KEY}: {trailer_value}\n",
            encoding="utf-8",
        )

    def _extract_signoff_name_and_date(self, body: str) -> tuple[str, str]:
        """Parse the ``- name:`` and ``- date:`` lines from the ``## Signoff`` block.

        Returns ``(signer_name, signer_date)`` -- the two fields the trailer
        projection re-derives. The reference impl scans the body line-by-line
        for the two markers; the verify CLI's ``emit-trailer`` subcommand
        MUST agree on the parse (cross-tree contract probed by AT1).
        """
        signer_name: str | None = None
        signer_date: str | None = None
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- name:"):
                signer_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- date:"):
                signer_date = stripped.split(":", 1)[1].strip()
        if signer_name is None or signer_date is None:
            raise ValueError(
                "## Signoff block is missing `- name:` or `- date:` -- "
                "sign_coverage_map() must emit both before the trailer is derived"
            )
        return signer_name, signer_date

    # ------------------------------------------------------------------
    # Slice-04 driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_emit_trailer(self) -> CliResult:
        """Invoke ``verify_coverage_map emit-trailer`` as a subprocess.

        Layer-3 wiring proof for the slice-04 trailer projection. Stdout
        carries the re-derived trailer line; AT1 compares it against the
        committed commit-trailer file.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.verify_coverage_map",
                "emit-trailer",
                "--feature-root",
                str(self.feature_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # ------------------------------------------------------------------
    # Slice-04 Then-step observables -- trailer match + ledger record.
    # ------------------------------------------------------------------

    def trailer_matches_commit_trailer(self, result: CliResult) -> bool:
        """Return True iff the CLI's emitted trailer matches the on-disk trailer.

        Byte-for-byte comparison after stripping trailing whitespace --
        the §6.1 mechanical-projection contract leaves no room for
        equivalent-but-distinct strings.
        """
        on_disk = self.commit_trailer_path().read_text(encoding="utf-8").rstrip()
        emitted = result.stdout.rstrip()
        return on_disk == emitted

    def ledger_has_one_signed_off_record_with_matching_digest(self) -> bool:
        """Return True iff exactly one ``CoverageMapSignedOff`` record exists
        on the ledger AND its ``reviewed_content_digest`` field matches the
        recorded ``## Signoff`` block digest.

        Slice-04 AT1 closes the block <-> trailer <-> ledger triple: the
        ledger record carries the same canonical-content digest the block
        carries, so a future reader can prove the three surfaces agree on
        one identity.
        """
        records = self._read_ledger_signed_off_records()
        if len(records) != 1:
            return False
        recorded_digest = self._recorded_signoff_digest()
        return records[0].get("reviewed_content_digest") == recorded_digest

    def ledger_signed_off_record_count_unchanged(
        self, before_count: int, after_count: int
    ) -> bool:
        """Slice-04 AT1 sad-path: the ledger must NOT gain a new record on refusal.

        A ``TrailerMismatch`` refusal at verify time means the signature
        triple is inconsistent -- the engine must not persist a
        ``CoverageMapSignedOff`` for an inconsistent signature.
        """
        return before_count == after_count

    def _recorded_signoff_digest(self) -> str | None:
        """Return the digest the human recorded in the ``## Signoff`` block."""
        body = self.coverage_map_signoff_path().read_text(encoding="utf-8")
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- reviewed-content-digest:"):
                return stripped.split(":", 1)[1].strip()
        return None

    def _ledger_path(self) -> Path:
        """The per-feature AT-completion ledger JSONL file the engine writes."""
        # The ledger lives under {project_root}/.nwave/telemetry/atdd-pure/.
        # ``feature_root`` is a tmp_path subdirectory acting as the
        # ``docs/feature/{id}/`` slot; the project_root is its grand-grandparent
        # (tmp_path/feature -> tmp_path is the synthesized project root).
        project_root = self.feature_root.parent
        return (
            project_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / "fix-distill-human-signoff.jsonl"
        )

    def _read_ledger_signed_off_records(self) -> list[dict[str, object]]:
        """Return all ``CoverageMapSignedOff`` records from the ledger.

        Empty list if the ledger file is absent (slice-04 happy-path WHEN-step
        snapshot before invocation).
        """
        path = self._ledger_path()
        if not path.is_file():
            return []
        records: list[dict[str, object]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                record = _json.loads(raw)
            except _json.JSONDecodeError:
                continue
            if record.get("event") == LEDGER_EVENT_COVERAGE_MAP_SIGNED_OFF:
                records.append(record)
        return records

    def _count_signed_off_records_on_ledger(self) -> int:
        """Cardinality of ``CoverageMapSignedOff`` records on the ledger."""
        return len(self._read_ledger_signed_off_records())

    # ------------------------------------------------------------------
    # Slice-04 AT3 -- static call-graph scan (G5 two-layer architecture-test).
    # ------------------------------------------------------------------

    def static_call_graph_scan(self, layer: CallGraphLayer) -> tuple[str, ...]:
        """Return the offending caller modules for one G5 layer (empty = pass).

        Layer DENYLIST (a): scan every module under ``src/`` + ``scripts/`` +
        ``nWave/agents/`` for AST patterns indicating LLM-agent dispatch
        (``Agent(...)`` / ``subagent_type=...`` / ``claude -p ...``) that
        reach the ledger writer's dotted name. A non-empty result fails AT3.

        Layer ALLOWLIST (b): scan every module under ``src/`` + ``scripts/``
        for direct call-sites resolving to the ledger writer; any caller
        whose dotted module path is NOT in ``_ENGINE_CALLER_ALLOWLIST``
        fails AT3.

        Returns the dotted module names of the offenders (empty tuple = pass).
        """
        if layer is CallGraphLayer.DENYLIST:
            return self._scan_denylist_dispatch_paths()
        if layer is CallGraphLayer.ALLOWLIST:
            return self._scan_allowlist_non_engine_callers()
        # pragma: no cover -- enum is exhaustive
        raise ValueError(f"unknown CallGraphLayer: {layer!r}")

    def _scan_denylist_dispatch_paths(self) -> tuple[str, ...]:
        """Find LLM-agent dispatch sites that import / call the ledger writer.

        Walks the AST of every ``.py`` file under ``src/`` and ``scripts/``;
        flags a file where (a) the ledger writer module is imported AND
        (b) the same file contains an LLM-agent dispatch marker
        (``Agent(`` / ``subagent_type=`` / ``claude -p``).
        """
        offenders: list[str] = []
        dispatch_markers = ("Agent(", "subagent_type=", "claude -p")
        for source_file in self._iter_dispatch_scan_roots():
            try:
                source = source_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if LEDGER_WRITER_MODULE not in source:
                continue
            if any(marker in source for marker in dispatch_markers):
                offenders.append(self._dotted_module(source_file))
        return tuple(offenders)

    def _scan_allowlist_non_engine_callers(self) -> tuple[str, ...]:
        """Find call-sites resolving to the ledger writer outside the allowlist.

        The allowlist itself lives in
        ``src.des.adapters.driven.ledger.coverage_map_signoff_writer._ENGINE_CALLER_ALLOWLIST``;
        AT3 (b) asserts every caller's dotted module path is in that set.
        """
        from src.des.adapters.driven.ledger.coverage_map_signoff_writer import (
            _ENGINE_CALLER_ALLOWLIST,
        )

        offenders: list[str] = []
        for source_file in self._iter_dispatch_scan_roots():
            try:
                source = source_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if LEDGER_WRITER_FUNCTION not in source:
                continue
            try:
                tree = _ast.parse(source)
            except SyntaxError:
                continue
            calls_writer = False
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call):
                    func = node.func
                    if (
                        isinstance(func, _ast.Attribute)
                        and func.attr == LEDGER_WRITER_FUNCTION
                    ) or (
                        isinstance(func, _ast.Name)
                        and func.id == LEDGER_WRITER_FUNCTION
                    ):
                        calls_writer = True
                        break
            if not calls_writer:
                continue
            dotted = self._dotted_module(source_file)
            # The writer module itself is implicitly permitted (self-reference).
            if dotted == LEDGER_WRITER_MODULE:
                continue
            if dotted not in _ENGINE_CALLER_ALLOWLIST:
                offenders.append(dotted)
        return tuple(offenders)

    def _iter_dispatch_scan_roots(self):
        """Yield every ``.py`` file under the scan-root directories."""
        scan_roots = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")
        for root in scan_roots:
            if not root.is_dir():
                continue
            yield from root.rglob("*.py")

    def _dotted_module(self, source_file: Path) -> str:
        """Convert a repo-relative path to its dotted import name."""
        rel = source_file.relative_to(_REPO_ROOT).with_suffix("")
        return ".".join(rel.parts)

    # ==================================================================
    # SLICE-05 composition methods -- omission-class attestation.
    # ==================================================================
    #
    # Slice-05 wires the cardinality-agnostic `omission-classes-attested:`
    # list in the `## Signoff` block against the imported Layer-1 list at
    # `nWave/data/omission-classes.json`. The verify gate reads the list at
    # verify time and asserts the signoff covers every class-id present
    # (N classes, not a hard-coded 6). An empty or unparseable file is
    # MalformedInput exit 2 (RC-G1 non-empty floor, §4.1a).
    #
    # The composition root authors a per-test substitute omission-classes
    # file under `tmp_path` and passes it to the verify CLI via the
    # `--omission-classes-json` flag. The substitute carries one of the
    # `OmissionClassListShape` shapes (FIVE/SEVEN/EMPTY/UNPARSEABLE).

    # ------------------------------------------------------------------
    # Slice-05 paths + universe.
    # ------------------------------------------------------------------

    def omission_classes_json_path(self) -> Path:
        """Per-test substitute `omission-classes.json` under the feature root.

        The verify CLI's `--omission-classes-json` flag points at this file.
        Lives under the synthesized project root so the cleanup is
        tmp_path-scoped (no pollution of the real `nWave/data/`).
        """
        return self.feature_root.parent / "omission-classes.json"

    # ------------------------------------------------------------------
    # Slice-05 imported-list authoring (Given-step delegates).
    # ------------------------------------------------------------------

    def write_omission_classes_json(self, shape: OmissionClassListShape) -> None:
        """Author a substitute omission-classes file of the requested shape.

        Routes the AT3 outline row to its file body: FIVE_CLASSES /
        SEVEN_CLASSES probe G8 cardinality-agnostic; EMPTY / UNPARSEABLE
        probe the RC-G1 non-empty floor.
        """
        self._write_substitute_omission_classes(shape)

    def write_omission_classes_json_with_edited_class_content(self) -> None:
        """Author a 6-class substitute whose ONE class has edited content.

        AT2 happy-path: the class list is read from the imported file as
        data (not hard-coded in code). Editing one class's title /
        description must propagate to the attestation surface without
        any CLI code change.
        """
        edited_classes = self._six_canonical_class_ids()
        # Edit the FIRST class's description -- a content change that is
        # observable in the file but does NOT change the class-id set.
        self._write_substitute_omission_classes_from_ids(
            edited_classes, title_suffix=" -- edited content marker"
        )

    def write_signoff_with_omitted_class(self) -> None:
        """Re-sign the coverage-map with one attested class-id dropped.

        AT1 sad-path: the `## Signoff` block's `omission-classes-attested:`
        list MISSES one class-id present in the substitute
        omission-classes.json. The verify gate must refuse with
        `SignoffMissing` exit 1 -- a signoff that omits an attested
        omission class is not a valid signoff.
        """
        attested = self._read_attested_class_ids_from_substitute()
        if not attested:
            raise ValueError(
                "write_signoff_with_omitted_class: substitute omission-classes "
                "json is empty -- author one with at least 1 class before "
                "dropping any from the signoff"
            )
        self._re_sign_with_attested_class_ids(attested[1:])

    # ------------------------------------------------------------------
    # Slice-05 driving-port invocation (When-step delegate).
    # ------------------------------------------------------------------

    def run_verify_with_substitute_omission_classes(self) -> CliResult:
        """Invoke `verify_coverage_map verify --omission-classes-json <substitute>`.

        Slice-05 driving port. Subprocess (layer-3 wiring-proof) as in
        slices 03/04; the only new flag is the `--omission-classes-json`
        path pointing at the per-test substitute.
        """
        return self._run_verify_with_omission_classes_flag(
            self.omission_classes_json_path()
        )

    # ------------------------------------------------------------------
    # Slice-05 Then-step observables.
    # ------------------------------------------------------------------

    def verify_gate_accepts(self, result: CliResult) -> bool:
        """Return True iff the verify gate accepted the coverage map (exit 0)."""
        return result.exit_code == 0

    def verify_gate_refuses_with_signoff_missing(self, result: CliResult) -> bool:
        """Return True iff the gate refused with SignoffMissing exit 1."""
        return result.exit_code == 1 and "SignoffMissing" in result.stderr

    def verify_gate_refuses_with_malformed_input(self, result: CliResult) -> bool:
        """Return True iff the gate refused with MalformedInput exit 2."""
        return result.exit_code == 2 and "MalformedInput" in result.stderr

    # ------------------------------------------------------------------
    # Slice-05 internal helpers -- substitute YAML authoring + re-signing.
    # ------------------------------------------------------------------

    def _six_canonical_class_ids(self) -> tuple[str, ...]:
        """The six baseline class-ids from `nWave/data/omission-classes.json`.

        Reading the real file would couple the test to the import; this
        constant is the contract slice-05 attests against. Five / seven
        variants slice / extend this list.
        """
        return (
            "environmental-domain-dropped",
            "behavioural-state-or-transition-dropped",
            "process-mode-or-flag-combination-dropped",
            "negative-or-robustness-domain-dropped",
            "residue-was-not-carried-forward",
            "not-applicable-marker-without-attestation",
        )

    def _class_ids_for_shape(
        self, shape: OmissionClassListShape
    ) -> tuple[str, ...] | None:
        """Return the class-id set for a given shape, or None if unparseable."""
        six = self._six_canonical_class_ids()
        if shape is OmissionClassListShape.FIVE_CLASSES:
            return six[:5]
        if shape is OmissionClassListShape.SEVEN_CLASSES:
            return (*six, "synthesis-of-multi-domain-interaction-dropped")
        if shape is OmissionClassListShape.EMPTY:
            return ()
        if shape is OmissionClassListShape.UNPARSEABLE:
            return None
        # pragma: no cover -- enum is exhaustive
        raise ValueError(f"unknown OmissionClassListShape: {shape!r}")

    def _write_substitute_omission_classes(self, shape: OmissionClassListShape) -> None:
        """Author the substitute omission-classes.json for one shape."""
        path = self.omission_classes_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        class_ids = self._class_ids_for_shape(shape)
        if class_ids is None:
            # UNPARSEABLE -- not a valid JSON document.
            path.write_bytes(b"\x00\x01\x02 not-json \xff\xfe :::not-a-document")
            self._re_sign_with_attested_class_ids(())
            return
        self._write_substitute_omission_classes_from_ids(class_ids)

    def _write_substitute_omission_classes_from_ids(
        self,
        class_ids: tuple[str, ...],
        title_suffix: str = "",
    ) -> None:
        """Render the substitute JSON carrying the given class-ids in order."""
        import json

        path = self.omission_classes_json_path()
        # Empty list -- explicit `[]` so the JSON is parseable but yields
        # zero class-ids (RC-G1 non-empty floor probe).
        document = {
            "schema-version": "2026-05-24",
            "omission-classes": [
                {
                    "id": class_id,
                    "title": f"{class_id}{title_suffix}",
                    "description": f"{class_id} description",
                }
                for class_id in class_ids
            ],
        }
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        # The signoff must re-attest the substitute's class-ids -- re-sign
        # the coverage-map so the attested list matches the substitute.
        self._re_sign_with_attested_class_ids(class_ids)

    def _read_attested_class_ids_from_substitute(self) -> tuple[str, ...]:
        """Return the class-ids the substitute omission-classes.json declares."""
        import json

        path = self.omission_classes_json_path()
        document = json.loads(path.read_text(encoding="utf-8"))
        return tuple(entry["id"] for entry in document["omission-classes"])

    def _re_sign_with_attested_class_ids(self, attested_ids: tuple[str, ...]) -> None:
        """Re-render + re-sign the coverage-map with the given attested set.

        Mirrors `sign_coverage_map` but injects the caller-supplied attested
        class-id list (rather than the default-from-the-real-file list).
        This is the AT1 sad-path lever: pass `attested[1:]` to drop the
        first class-id and trigger the SignoffMissing refusal.
        """
        body = self._render_signed_coverage_map_body()
        digest = self._compute_canonical_digest(body)
        attested_block = self._format_omission_classes_attested_block(attested_ids)
        signoff_block = (
            "\n## Signoff\n"
            "\n"
            "- name: test-human-signer\n"
            "- date: 2026-05-23\n"
            f"- reviewed-content-digest: {digest}\n"
            "- role: human-signer\n" + attested_block
        )
        coverage_path = self.coverage_map_signoff_path()
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_path.write_text(body + signoff_block, encoding="utf-8")
        self.signoff_digest_path().write_text(digest + "\n", encoding="utf-8")

    def _render_omission_classes_attested_block(self) -> str:
        """Render the default-attested block from the real omission-classes.json.

        Used by `sign_coverage_map` (the slice-01/02/03/04 happy-path entry
        point) to keep the slice-03/04 ATs passing now that the verify gate
        checks the omission-class attestation. Reads the canonical six-class
        baseline so the signoff covers every class-id the real import names.
        """
        return self._format_omission_classes_attested_block(
            self._six_canonical_class_ids()
        )

    def _format_omission_classes_attested_block(
        self, class_ids: tuple[str, ...]
    ) -> str:
        """Format `- omission-classes-attested:` block for the given ids."""
        if not class_ids:
            return "- omission-classes-attested: []\n"
        lines = ["- omission-classes-attested:"]
        for class_id in class_ids:
            lines.append(f"  - {class_id}")
        return "\n".join(lines) + "\n"

    def _run_verify_with_omission_classes_flag(
        self, omission_classes_path: Path
    ) -> CliResult:
        """Invoke verify with `--omission-classes-json <path>`."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.verify_coverage_map",
                "verify",
                "--feature-root",
                str(self.feature_root),
                "--omission-classes-json",
                str(omission_classes_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    # ==================================================================
    # SLICE-06 composition methods -- both-touchpoint wiring.
    # ==================================================================
    #
    # Slice-06 wires `verify_coverage_map verify --touchpoint <name>` at the
    # DISTILL-exit and DELIVER-exit handoffs. Each successful invocation
    # appends a heartbeat record to the AT-completion ledger
    # (`CoverageMapVerifiedAtDistillExit` / `CoverageMapVerifiedAtDeliverExit`);
    # the U4 SubagentStop enforcer (and its verify_deliver_integrity CLI
    # mirror) is the consumer that turns a missing heartbeat into a feature-
    # end block. Hook-only architecture (Ale 2026-05-24 standing).

    # ------------------------------------------------------------------
    # Slice-06 Given-step delegates -- DISTILL-exit unsigned-state staging.
    # ------------------------------------------------------------------

    def stage_distill_exit_unsigned_state(self, state: UnsignedState) -> None:
        """Stage the precondition for one slice-06 AT1 outline row.

        Each row leaves the coverage-map in one untrustworthy equivalence
        class the DISTILL-exit verify gate must refuse:
          - ABSENT: no coverage-map.md on disk.
          - UNSIGNED: a body authored but with NO `## Signoff` block.
          - STRUCTURAL_INCOMPLETE: a signed map missing a mandatory section.
        """
        if state is UnsignedState.ABSENT:
            # Do nothing -- the slice-01 Background did NOT call sign_coverage_map,
            # so distill/coverage-map.md is absent on disk.
            return
        if state is UnsignedState.UNSIGNED:
            self._write_unsigned_coverage_map()
            return
        if state is UnsignedState.STRUCTURAL_INCOMPLETE:
            self.sign_coverage_map()
            self.remove_mandatory_section(SignedSection.NEGATIVE_SPACE)
            return
        # pragma: no cover -- enum is exhaustive
        raise ValueError(f"unknown UnsignedState: {state!r}")

    # ------------------------------------------------------------------
    # Slice-06 Given-step delegates -- DELIVER-exit staleness-cause staging.
    # ------------------------------------------------------------------

    def stage_deliver_exit_staleness_cause(
        self,
        cause: StalenessCause,
        domain_ids: dict[CoverageDimension, ManifestDomainId],
    ) -> None:
        """Stage the precondition for one slice-06 AT2 outline row.

        Each row mutates the post-signoff state in one G2 two-sensor way:
          - BODY_EDIT: tampers a signed section so the §5.3 digest no longer
            matches -- the DELIVER-exit gate refuses with `SignoffStale`.
          - AT_DROP: removes an `@covers:` tag from the `.feature` file so a
            manifest domain that was tag-covered is no longer covered -- the
            coverage-map body is untouched (digest holds) but the anti-omission
            re-run at DELIVER-exit fails with `OmissionDetected`.
        """
        if cause is StalenessCause.BODY_EDIT:
            self.tamper_signed_section(SignedSection.NOT_COVERED_TABLE)
            return
        if cause is StalenessCause.AT_DROP:
            self._drop_acceptance_scenario_with_covers_tag(domain_ids)
            return
        # pragma: no cover -- enum is exhaustive
        raise ValueError(f"unknown StalenessCause: {cause!r}")

    def assert_coverage_map_body_unchanged_since_signoff(self) -> None:
        """No-op assertion -- the happy-path Given leaves the body untouched.

        This step is documentation: a passing Then proves the digest still
        matches (no body edit happened between sign-off and DELIVER-exit).
        """
        return

    def assert_no_covers_tag_dropped_since_signoff(self) -> None:
        """No-op assertion -- the happy-path Given leaves the `.feature` tags intact.

        This step is documentation: a passing Then proves the anti-omission
        re-run at DELIVER-exit still sees every manifest domain covered.
        """
        return

    # ------------------------------------------------------------------
    # Slice-06 driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_distill_to_deliver_handoff(self) -> CliResult:
        """Invoke `verify_coverage_map verify --touchpoint distill_exit`.

        The DISTILL-exit driving port. On exit 0 the gate appends a
        `CoverageMapVerifiedAtDistillExit` heartbeat to the AT-completion
        ledger; on refusal no heartbeat is written.
        """
        return self._run_verify_with_touchpoint(Touchpoint.DISTILL_EXIT)

    def run_deliver_to_feature_end_handoff(self) -> CliResult:
        """Invoke `verify_coverage_map verify --touchpoint deliver_exit`.

        The DELIVER-exit driving port. On exit 0 the gate appends a
        `CoverageMapVerifiedAtDeliverExit` heartbeat to the AT-completion
        ledger; on refusal no heartbeat is written.
        """
        return self._run_verify_with_touchpoint(Touchpoint.DELIVER_EXIT)

    # ------------------------------------------------------------------
    # Slice-06 Then-step observables -- handoff verdict + heartbeat presence.
    # ------------------------------------------------------------------

    def handoff_blocked(self, result: CliResult) -> bool:
        """Return True iff the touchpoint handoff was blocked (non-zero exit)."""
        return result.exit_code != 0

    def handoff_blocked_with_named_refusal(self, result: CliResult) -> bool:
        """Return True iff the gate refused with a named refusal token + exit 1 or 2.

        Tightens `handoff_blocked` -- a non-zero exit MUST carry one of the
        DISTILL-exit refusal tokens (SignoffMissing / StructuralIncomplete /
        MalformedInput); a bare exit-2 from argparse (unrecognised flag) does
        NOT count as a proper handoff refusal.
        """
        if result.exit_code not in (1, 2):
            return False
        named_tokens = ("SignoffMissing", "StructuralIncomplete", "MalformedInput")
        return any(token in result.stderr for token in named_tokens)

    def verify_gate_refuses_with_signoff_stale(self, result: CliResult) -> bool:
        """Return True iff the gate refused with SignoffStale exit 1."""
        return result.exit_code == 1 and "SignoffStale" in result.stderr

    def verify_gate_refuses_with_omission_detected(self, result: CliResult) -> bool:
        """Return True iff the gate refused with OmissionDetected exit 1."""
        return result.exit_code == 1 and "OmissionDetected" in result.stderr

    def distill_exit_heartbeat_present(self) -> bool:
        """Return True iff a CoverageMapVerifiedAtDistillExit record is on the ledger."""
        return (
            self._touchpoint_heartbeat_count(COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT) >= 1
        )

    def distill_exit_heartbeat_absent(self) -> bool:
        """Return True iff no CoverageMapVerifiedAtDistillExit record is on the ledger."""
        return (
            self._touchpoint_heartbeat_count(COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT) == 0
        )

    def deliver_exit_heartbeat_present(self) -> bool:
        """Return True iff a CoverageMapVerifiedAtDeliverExit record is on the ledger."""
        return (
            self._touchpoint_heartbeat_count(COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT) >= 1
        )

    def deliver_exit_heartbeat_absent(self) -> bool:
        """Return True iff no CoverageMapVerifiedAtDeliverExit record is on the ledger."""
        return (
            self._touchpoint_heartbeat_count(COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT) == 0
        )

    # ------------------------------------------------------------------
    # Slice-06 internal helpers.
    # ------------------------------------------------------------------

    def _run_verify_with_touchpoint(self, touchpoint: Touchpoint) -> CliResult:
        """Invoke `verify_coverage_map verify --touchpoint <name>` as subprocess.

        Subprocess (layer-3 wiring-proof) as in slices 03/04/05; the new flag
        routes the verify path through the per-touchpoint heartbeat emission.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.verify_coverage_map",
                "verify",
                "--feature-root",
                str(self.feature_root),
                "--touchpoint",
                touchpoint.value,
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def _touchpoint_heartbeat_count(self, event_name: str) -> int:
        """Count touchpoint-heartbeat records of the given event name on the ledger."""
        path = self._ledger_path()
        if not path.is_file():
            return 0
        count = 0
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                record = _json.loads(raw)
            except _json.JSONDecodeError:
                continue
            if record.get("event") == event_name:
                count += 1
        return count

    def _write_unsigned_coverage_map(self) -> None:
        """Author a coverage-map body with NO `## Signoff` block (UNSIGNED state).

        Mirrors the slice-03 minimal four-signed-section body but omits the
        `## Signoff` block entirely -- the DISTILL-exit verify gate must
        refuse a coverage-map without a signoff (the human attestation
        is the load-bearing artefact, §2).
        """
        body = self._render_signed_coverage_map_body()
        coverage_path = self.coverage_map_signoff_path()
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_path.write_text(body, encoding="utf-8")

    def _drop_acceptance_scenario_with_covers_tag(
        self, domain_ids: dict[CoverageDimension, ManifestDomainId]
    ) -> None:
        """Re-author the `.feature` so one manifest domain loses its `@covers:` tag.

        AT2 G2 second sensor: the coverage-map BODY stays put (digest holds);
        the change is in the `.feature` `@covers:` tag population. The
        anti-omission re-run at DELIVER-exit MUST detect that a manifest
        domain that was tag-covered is no longer covered -> `OmissionDetected`.
        """
        # Drop the BEHAVIOURAL dimension's domain coverage -- delete the
        # fully-covered scenario file (authored by write_scenario_covering_all_domains
        # in the slice-06 Given) and re-author a partial-cover scenario file in
        # its place that leaves BEHAVIOURAL uncovered.
        feature_dir = self.feature_root / "acceptance"
        fully_covered_path = feature_dir / "fully-covered.feature"
        if fully_covered_path.is_file():
            fully_covered_path.unlink()
        self.write_scenario_covering_subset(
            domain_ids, leave_uncovered=CoverageDimension.BEHAVIOURAL
        )
