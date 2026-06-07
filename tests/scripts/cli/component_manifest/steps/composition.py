"""Composition root for the fix-design-component-manifest acceptance set.

F-DESIGN-COMPONENT-MANIFEST (Mandate-12 criteria 2-3, Pillar 3). Wires the
PRODUCTION manifest surfaces -- the ``validate_component_manifest`` CLI and the
``resolve_manifest_state()`` resolver -- against a tmp_path feature project.
Business logic (build a manifest of a given shape, invoke the CLI, classify)
lives here as the single source of truth; step bodies delegate to
``ComponentManifestComposition`` methods and never inline logic.

Layer 3 (subprocess / FS acceptance): the validation CLI and the resolver are
the driving ports; the only driven port is the real filesystem (tmp_path repo +
the framework schema). Sad paths are example-based (Mandate 11); the
@property-tagged shape coverage is realised as Scenario Outline rows, not a
Hypothesis @given (Mandate 9 -- this is layer 3).

RED-scaffold note: ``scripts/cli/validate_component_manifest.py``,
``scripts/cli/resolve_manifest_state.py`` and
``nWave/schemas/component-manifest.schema.json`` are RED scaffolds on master
(slices 01-03 implement them). The CLI entry points raise ``AssertionError`` so
every scenario is RED (missing functionality), not BROKEN (import error) -- the
imports below resolve cleanly because the scaffold modules exist (Mandate 7).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    FeatureId,
    MalformedShape,
    ManifestState,
    NotApplicableReason,
    SutReference,
)


# Repo root -- the four-level-up parent of this file
# (tests/scripts/cli/component_manifest/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The production schema the validation CLI checks manifests against.
_SCHEMA_PATH = _REPO_ROOT / "nWave" / "schemas" / "component-manifest.schema.json"

# A real, grep-stable symbol in a real repo file -- used as a grounded sut:.
_GROUNDED_SUT = SutReference(
    "scripts/cli/validate_component_manifest.py::validate_manifest"
)
# A symbol that does NOT exist in the cited (real) file -- an ungrounded sut:.
_UNGROUNDED_SUT = SutReference(
    "scripts/cli/validate_component_manifest.py::_symbol_that_was_never_written"
)


def _domain_item(entry_id: str, sut: str) -> str:
    """One well-formed unbounded-input-domains list item (every required key)."""
    return textwrap.dedent(
        f"""\
          - id: {entry_id}
            sut: {sut}
            domain: >
              The validate_component_manifest CLI accepts arbitrary YAML --
              an unbounded input domain not finite-enumerable.
            why-unbounded: "arbitrary YAML document shapes"
            canonical-category: C6
            declared-at: design
        """
    )


def _valid_entry(sut: str = str(_GROUNDED_SUT)) -> str:
    """A well-formed unbounded-input-domains key with one grounded entry."""
    return "unbounded-input-domains:\n" + _domain_item("arbitrary-yaml-input", sut)


def _valid_entries_many(sut: str = str(_GROUNDED_SUT)) -> str:
    """A well-formed unbounded-input-domains key with TWO distinct-id entries.

    Witnesses the n=many cardinality of the load-bearing array: a per-item
    $ref-iteration bug or an id-uniqueness regression would surface here
    where the single-entry n=1 fixture cannot see it.
    """
    return (
        "unbounded-input-domains:\n"
        + _domain_item("arbitrary-yaml-input", sut)
        + _domain_item("arbitrary-cli-argv", sut)
    )


@dataclass(frozen=True)
class CliResult:
    """Observable result of one validate_component_manifest invocation."""

    exit_code: int
    stdout: str
    stderr: str


class ComponentManifestComposition:
    """Production-wired composition root for the component-manifest surfaces.

    Builds component-manifest.yaml fixtures of a requested shape under a
    tmp_path feature directory, then drives the real validation CLI / resolver.
    """

    def __init__(self, feature_root: Path) -> None:
        self.feature_root = feature_root
        self.feature_id: FeatureId = FeatureId("acceptance-fixture-feature")

    # --- Given: provision the feature design directory -----------------------

    @property
    def design_dir(self) -> Path:
        """The docs/feature/{id}/design/ directory holding the manifest."""
        return self.feature_root / "design"

    @property
    def manifest_path(self) -> Path:
        return self.design_dir / "component-manifest.yaml"

    @property
    def feature_delta_path(self) -> Path:
        """The feature-delta.md -- home of the not-applicable prose marker."""
        return self.feature_root / "feature-delta.md"

    def create_feature_dir(self, feature_id: FeatureId) -> None:
        """Create an empty tmp_path feature directory (no manifest yet)."""
        self.feature_id = feature_id
        self.design_dir.mkdir(parents=True, exist_ok=True)

    def write_valid_manifest(self) -> None:
        """Write a present, schema-valid manifest with one grounded entry."""
        self.manifest_path.write_text(
            f'schema-version: "1.0"\nfeature-id: {self.feature_id}\n' + _valid_entry(),
            encoding="utf-8",
        )

    def write_manifest_with_every_required_key(self) -> None:
        """Write a manifest exercising every required key + every optional block.

        The unbounded-input-domains array carries TWO distinct-id entries so
        this fixture also witnesses the n=many cardinality of the feature's
        load-bearing collection (per-item $ref iteration, id-uniqueness).
        """
        body = (
            f'schema-version: "1.0"\nfeature-id: {self.feature_id}\n'
            + _valid_entries_many()
            + textwrap.dedent(
                """\
                typed-error-set:
                  - port: scripts/cli/validate_component_manifest.py::main
                    errors: [ManifestStale, ManifestMalformed]
                port-invariants:
                  - port: scripts/cli/validate_component_manifest.py::main
                    invariant: exit code is always one of 0, 1, 2
                """
            )
        )
        self.manifest_path.write_text(body, encoding="utf-8")

    def write_malformed_manifest(self, shape: MalformedShape) -> None:
        """Write a schema-invalid manifest exhibiting one malformed shape (C6)."""
        body = _MALFORMED_BODY[shape](self.feature_id)
        self.manifest_path.write_text(body, encoding="utf-8")

    def write_manifest_with_sut(self, grounded: bool) -> None:
        """Write a schema-valid manifest whose sut: symbol is/ is not grounded."""
        sut = _GROUNDED_SUT if grounded else _UNGROUNDED_SUT
        self.manifest_path.write_text(
            f'schema-version: "1.0"\nfeature-id: {self.feature_id}\n'
            + _valid_entry(str(sut)),
            encoding="utf-8",
        )

    def write_manifest_declared_at_distill(self) -> None:
        """Write a manifest whose entry has the forbidden declared-at: distill."""
        body = (
            f'schema-version: "1.0"\nfeature-id: {self.feature_id}\n'
            + _valid_entry().replace("declared-at: design", "declared-at: distill")
        )
        self.manifest_path.write_text(body, encoding="utf-8")

    def write_empty_manifest_with_rationale(self) -> None:
        """Write a present, schema-valid honestly-empty manifest (state B)."""
        self.manifest_path.write_text(
            f'schema-version: "1.0"\nfeature-id: {self.feature_id}\n'
            "unbounded-input-domains: []\n"
            "unbounded-input-domains-empty-rationale: "
            '"this component has no unbounded input domain"\n',
            encoding="utf-8",
        )

    def write_not_applicable_marker(self, reason: NotApplicableReason) -> None:
        """Write a `component-manifest: not-applicable` marker into the delta.

        No manifest file is written -- the marker lives in the feature-delta
        prose, carrying the reason enum and a one-line rationale.
        """
        self.feature_delta_path.write_text(
            "# Feature delta -- acceptance fixture\n\n"
            f"component-manifest: not-applicable\n"
            f"component-manifest-reason: {reason.value}\n"
            "component-manifest-rationale: "
            '"design wave predates the component-manifest artifact"\n',
            encoding="utf-8",
        )

    # --- When: drive the production CLI / resolver ---------------------------

    def run_validate_cli(self) -> CliResult:
        """Invoke the production validate_component_manifest CLI as a subprocess.

        Layer-3 wiring proof: spawns ``python -m scripts.cli.validate_component_manifest``
        exactly as a DESIGN-exit reviewer or downstream gate would.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.validate_component_manifest",
                str(self.manifest_path),
            ],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return CliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def resolve_state(self) -> ManifestState:
        """Classify the fixture feature's manifest via the production resolver."""
        from scripts.cli.resolve_manifest_state import resolve_manifest_state

        resolved = resolve_manifest_state(self.design_dir)
        return ManifestState(resolved.value)

    # --- Universe snapshot (Mandate 8) ---------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observable names the surfaces affect.

        Port-exposed only: the CLI exit code, the manifest file's presence, and
        the resolved state. No internal struct fields.
        """
        return {
            "manifest.present": self.manifest_path.is_file(),
            "feature_delta.present": self.feature_delta_path.is_file(),
        }


def _body_missing_unbounded_key(feature_id: str) -> str:
    return f'schema-version: "1.0"\nfeature-id: {feature_id}\n'


def _body_empty_without_rationale(feature_id: str) -> str:
    return (
        f'schema-version: "1.0"\nfeature-id: {feature_id}\n'
        "unbounded-input-domains: []\n"
    )


def _body_unknown_schema_version(feature_id: str) -> str:
    return f'schema-version: "9.9"\nfeature-id: {feature_id}\n' + _valid_entry()


def _body_not_a_mapping(feature_id: str) -> str:
    return "- this manifest is a yaml sequence, not a mapping\n"


def _body_missing_schema_version(feature_id: str) -> str:
    return f"feature-id: {feature_id}\n" + _valid_entry()


# MalformedShape -> the YAML body builder producing that schema-invalid shape.
_MALFORMED_BODY = {
    MalformedShape.MISSING_UNBOUNDED_KEY: _body_missing_unbounded_key,
    MalformedShape.EMPTY_WITHOUT_RATIONALE: _body_empty_without_rationale,
    MalformedShape.UNKNOWN_SCHEMA_VERSION: _body_unknown_schema_version,
    MalformedShape.NOT_A_MAPPING: _body_not_a_mapping,
    MalformedShape.MISSING_SCHEMA_VERSION: _body_missing_schema_version,
}
