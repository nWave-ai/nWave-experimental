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


_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "nWave"
    / "schemas"
    / "component-manifest.schema.json"
)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _check_sut_grounding(document: object) -> int:
    """Grep-verify every sut: symbol in unbounded-input-domains entries.

    Each sut: value has the form ``path::symbol``. The path is resolved
    relative to the repo root; the symbol must appear as a substring in that
    file's text.  Returns 1 if any symbol is not found, 0 otherwise.
    """
    if not isinstance(document, dict):
        return 0
    entries = document.get("unbounded-input-domains") or []
    for entry in entries:
        sut = entry.get("sut", "")
        if "::" not in sut:
            continue
        rel_path, symbol = sut.split("::", 1)
        candidate = _REPO_ROOT / rel_path
        if not candidate.is_file():
            print(
                f"component-manifest is stale: {sut!r} -- file not found: {rel_path}",
                file=sys.stderr,
            )
            return 1
        if symbol not in candidate.read_text(encoding="utf-8"):
            print(
                f"component-manifest is stale: symbol {symbol!r} not found in {rel_path}",
                file=sys.stderr,
            )
            return 1
    return 0


def validate_manifest(manifest_path: Path) -> int:
    """Validate one component-manifest.yaml; return the process exit code.

    Returns 0 when the manifest is schema-valid and every sut: symbol is
    grep-findable, 1 when a sut: symbol is stale, 2 when the manifest is
    malformed or schema-invalid.
    """
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: error.path)
    if errors:
        for error in errors:
            print(f"component-manifest is malformed: {error.message}", file=sys.stderr)
        return 2

    return _check_sut_grounding(document)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- validate the manifest at argv[0]."""
    args = sys.argv[1:] if argv is None else argv
    return validate_manifest(Path(args[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
