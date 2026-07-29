"""Four-state manifest resolver.

F-DESIGN-COMPONENT-MANIFEST slice-03. The shared resolver the two downstream
gate features (``fix-robustness-pbt-density-gate``, ``fix-distill-human-signoff``)
import -- a single implementation, not a per-gate copy.

``resolve_manifest_state()`` classifies a feature's manifest into one of four
SHAPE states (§5 of the feature-delta). It classifies SHAPE ONLY -- it does NOT
run ``sut:`` grounding; grounding is the caller's separate mandatory
``validate_component_manifest`` call (residuality F6). Resolver-state-A is
necessary-not-sufficient.

* ``A`` -- present, schema-valid, ``unbounded-input-domains`` non-empty
* ``B`` -- present, schema-valid, ``unbounded-input-domains: []`` + rationale,
  OR absent-with-a-reviewer-vetoable ``component-manifest: not-applicable``
  marker carrying a ``reason:`` enum
* ``C`` -- file absent, no marker -- caller fails closed (exit 1)
* ``D`` -- present but schema-invalid / malformed -- caller fails closed (exit 2)

The resolver returns the STATE enum -- no error-name opinion. Each consuming
gate maps the state to its own prefixed identifier.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


# Expose ``src/`` so ``des`` resolves under a bare ``python3`` (this script
# runs outside the uv venv as a ``language: system`` hook / ad-hoc tool).
# Guarded: ``src/`` exists only in the dev repo -- in an installed layout
# ``des`` is already importable and this is a no-op.
_SRC = Path(__file__).resolve().parents[2] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from des.domain.repo_path_resolver import feature_delta_in_dir  # noqa: E402


_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "nWave"
    / "schemas"
    / "component-manifest.schema.json"
)

_NOT_APPLICABLE_MARKER = "component-manifest: not-applicable"


class ManifestState(str, Enum):
    """The four shape states of a feature's component-manifest (§5)."""

    A = "A"  # present, schema-valid, non-empty unbounded-input-domains
    B = "B"  # explicitly-empty (+ rationale) OR not-applicable marker (+ reason)
    C = "C"  # absent, no marker -- caller fails closed (exit 1)
    D = "D"  # present, schema-invalid / malformed -- caller fails closed (exit 2)


class NotApplicableReason(str, Enum):
    """The ``reason:`` enum a ``not-applicable`` marker MUST carry (V5).

    Distinguishes the legacy ramp (expected to shrink) from the steady-state
    escape (expected to be rare) -- the population-attractor telemetry signal.
    """

    LEGACY_PRE_ARTIFACT = "legacy-pre-artifact"
    GENUINELY_NO_SUT = "genuinely-no-sut"


def _has_not_applicable_marker(feature_design_dir: Path) -> bool:
    """Return True iff the feature-delta.md carries the not-applicable marker."""
    feature_delta = feature_delta_in_dir(feature_design_dir.parent)
    if not feature_delta.is_file():
        return False
    return _NOT_APPLICABLE_MARKER in feature_delta.read_text(encoding="utf-8")


def _is_schema_valid(document: object) -> bool:
    """Return True iff *document* validates against the component-manifest schema."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(document))
    return len(errors) == 0


def resolve_manifest_state(feature_design_dir: Path) -> ManifestState:
    """Classify a feature's manifest into a SHAPE state.

    ``feature_design_dir`` is the ``docs/feature/{id}/design/`` directory.
    The manifest is ``component-manifest.yaml`` inside that directory.
    The not-applicable marker lives in ``feature-delta.md`` one level up.

    The four-state classification is mutually exclusive and exhaustive:
    every possible design-dir path maps to exactly one terminal state.
    """
    manifest_path = feature_design_dir / "component-manifest.yaml"

    if not manifest_path.is_file():
        # Manifest absent: marker present -> B, no marker -> C (fail-closed).
        if _has_not_applicable_marker(feature_design_dir):
            return ManifestState.B
        return ManifestState.C

    # Manifest present -- try to parse.
    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return ManifestState.D

    # Schema validation.
    if not _is_schema_valid(document):
        return ManifestState.D

    # Schema-valid -- distinguish A (non-empty domains) from B (empty + rationale).
    domains = document.get("unbounded-input-domains") or []
    if domains:
        return ManifestState.A
    return ManifestState.B
