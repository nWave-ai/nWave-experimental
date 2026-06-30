"""Component-manifest validation CLI.

F-DESIGN-COMPONENT-MANIFEST slices 01-02. Parses a ``component-manifest.yaml``,
validates it against ``nWave/schemas/component-manifest.schema.json`` (Draft
2020-12), and grounds every ``sut:`` symbol against its cited file.

Exit-code contract (the SSOT both downstream gates rely on -- §5 of the
feature-delta):

* ``0`` -- manifest present, schema-valid, every ``sut:`` symbol grep-findable
* ``1`` -- a ``sut:`` symbol is not grep-findable in its cited file (ManifestStale)
* ``2`` -- manifest schema-invalid / malformed / unknown forward-incompatible
  ``schema-version``

Invocable as ``python -m scripts.cli.validate_component_manifest <path>``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "nWave" / "schemas"
_SCHEMA_PATH = _SCHEMA_DIR / "component-manifest.schema.json"
_CODE_DESIGN_SCHEMA_PATH = _SCHEMA_DIR / "code-design-manifest.schema.json"


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _ground_sut(sut: str) -> str | None:
    """Grep-verify one ``path::symbol`` sut: reference; return a diagnostic or None.

    The path is resolved relative to the repo root; the symbol must appear as a
    substring in that file's text. Returns ``None`` when grounded, else a
    human-readable staleness diagnostic.
    """
    if "::" not in sut:
        return None
    rel_path, symbol = sut.split("::", 1)
    candidate = _REPO_ROOT / rel_path
    if not candidate.is_file():
        return f"manifest is stale: {sut!r} -- file not found: {rel_path}"
    if symbol not in candidate.read_text(encoding="utf-8"):
        return f"manifest is stale: symbol {symbol!r} not found in {rel_path}"
    return None


def _iter_sut_values(document: dict) -> list[str]:
    """Collect every ``sut:`` reference the validator grounds.

    Widened (review MEDIUM-1) to span the component-manifest
    ``unbounded-input-domains`` AND, for a code-design manifest, the
    ``example-tables[].sut`` rows plus the absorbed ``component-manifest:``
    sub-tree's ``unbounded-input-domains``.
    """
    suts: list[str] = []
    domains = document.get("unbounded-input-domains") or []
    absorbed = document.get("component-manifest")
    if isinstance(absorbed, dict):
        domains = [*domains, *(absorbed.get("unbounded-input-domains") or [])]
    for entry in domains:
        if isinstance(entry, dict) and entry.get("sut"):
            suts.append(entry["sut"])
    for row in document.get("example-tables") or []:
        if isinstance(row, dict) and row.get("sut"):
            suts.append(row["sut"])
    return suts


def _check_sut_grounding(document: object) -> int:
    """Grep-verify every sut: symbol the manifest declares.

    Returns 1 if any symbol is not grep-findable in its cited file, 0 otherwise.
    """
    if not isinstance(document, dict):
        return 0
    for sut in _iter_sut_values(document):
        diagnostic = _ground_sut(sut)
        if diagnostic is not None:
            print(diagnostic, file=sys.stderr)
            return 1
    return 0


def _is_code_design_manifest(document: object) -> bool:
    """A code-design manifest declares ``example-tables:`` or absorbs the component
    manifest as a ``component-manifest:`` sub-object (the broad ADR-FLOW-003 shape)."""
    return isinstance(document, dict) and (
        "example-tables" in document or "component-manifest" in document
    )


def _validator_for(document: object) -> Draft202012Validator:
    """The schema validator for the manifest shape (broad code-design vs component).

    A code-design manifest is validated against the broad schema, which absorbs
    the component-manifest schema by ``$ref``; the registry resolves that external
    ``$id`` to the local component-manifest schema file.
    """
    if _is_code_design_manifest(document):
        schema = json.loads(_CODE_DESIGN_SCHEMA_PATH.read_text(encoding="utf-8"))
        component_schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        registry = Registry().with_resource(
            uri=component_schema["$id"],
            resource=Resource.from_contents(component_schema),
        )
        return Draft202012Validator(schema, registry=registry)
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_manifest(manifest_path: Path) -> int:
    """Validate one manifest.yaml; return the process exit code.

    Returns 0 when the manifest is schema-valid and every sut: symbol is
    grep-findable, 1 when a sut: symbol is stale, 2 when the manifest is
    malformed or schema-invalid.
    """
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    validator = _validator_for(document)
    errors = sorted(validator.iter_errors(document), key=lambda error: str(error.path))
    if errors:
        for error in errors:
            print(f"manifest is malformed: {error.message}", file=sys.stderr)
        return 2

    return _check_sut_grounding(document)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- validate the manifest at argv[0]."""
    args = sys.argv[1:] if argv is None else argv
    return validate_manifest(Path(args[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
