"""Component-manifest validation CLI.

F-DESIGN-COMPONENT-MANIFEST slices 01-02. Parses a ``component-manifest.yaml``,
validates it against ``nWave/schemas/component-manifest.schema.json`` (Draft
2020-12), and grounds every ``sut:`` symbol against its cited file.

Exit-code contract (the SSOT both downstream gates rely on -- §5 of the
feature-delta):

* ``0`` -- manifest present, schema-valid, every ``sut:`` symbol RESOLVED as
  DEFINED in its cited file -- a module-level or class-level ``def``/
  ``async def``/``class``, or a module-level assignment/``AnnAssign`` target
  (a dotted ``Class.method`` citation resolves the attribute inside the
  class body). This is the PROPERTY (the symbol is defined there), never the
  DESIGNATION (the characters merely occur somewhere in the file -- a
  comment, docstring, string literal, import, or call does not ground).
* ``1`` -- a ``sut:`` citation's file is missing, or the file parses but does
  not DEFINE the symbol (ManifestStale)
* ``2`` -- manifest schema-invalid / malformed / unknown forward-incompatible
  ``schema-version``
* ``3`` -- a ``sut:`` citation could not be RESOLVED at all -- the cited file
  is not Python source, or it does not parse. No tier ever looked at it, so
  this state is distinct from both grounded (0) and stale (1); it must never
  silently collapse into either (GDP-6/GDP-8 arity corollary).

Invocable as ``python -m scripts.cli.validate_component_manifest <path>``.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Literal, NamedTuple

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "nWave" / "schemas"
_SCHEMA_PATH = _SCHEMA_DIR / "component-manifest.schema.json"
_CODE_DESIGN_SCHEMA_PATH = _SCHEMA_DIR / "code-design-manifest.schema.json"


_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Distinct exit code for "could not be resolved at all" -- see the module
#: docstring's exit-code contract. Kept apart from 2 (schema-invalid), which
#: names a different failure class entirely.
_EXIT_COULD_NOT_RESOLVE = 3


#: The three-state grounding outcome (GDP-8 arity corollary). ``"grounded"``
#: -- the symbol is DEFINED in the cited file (the property). ``"stale"`` --
#: the cited file exists and parses, but genuinely does not define the
#: symbol, or the file itself is missing. ``"incapacity"`` -- the cited file
#: could not be resolved as parseable Python source; no tier ever looked, so
#: this must never collapse into ``"grounded"`` (a silent pass) or
#: ``"stale"`` (a false accusation).
_GroundingState = Literal["grounded", "stale", "incapacity"]


class _GroundingOutcome(NamedTuple):
    state: _GroundingState
    diagnostic: str | None


def _defines_name(node: ast.AST, name: str) -> bool:
    """Whether one statement-level AST node DEFINES ``name``. Pure."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    return False


def _symbol_is_defined(tree: ast.Module, symbol: str) -> bool:
    """Whether ``symbol`` is DEFINED in ``tree`` -- the property, not the
    designation. A bare name is checked at module level; a dotted
    ``Class.method`` citation is resolved by looking inside that class's
    body only."""
    if "." in symbol:
        class_name, _, member_name = symbol.partition(".")
        class_node = next(
            (
                node
                for node in ast.iter_child_nodes(tree)
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        if class_node is None:
            return False
        return any(_defines_name(node, member_name) for node in class_node.body)
    return any(_defines_name(node, symbol) for node in ast.iter_child_nodes(tree))


def _stale_diagnostic(
    *, manifest_path: Path, sut: str, rel_path: str, symbol: str, cause: str
) -> str:
    return (
        f"manifest is stale: {sut!r} in {manifest_path} -- {cause}. "
        f"WHY: the manifest gate grounds every 'sut:' citation on the "
        f"PROPERTY that {symbol!r} is DEFINED in the cited file -- not "
        f"merely mentioned -- so the manifest cannot silently drift from "
        f"the code it describes; the path was resolved relative to "
        f"{_REPO_ROOT} as {rel_path!r}. "
        f"HOW: fix the 'sut:' citation in {manifest_path} to name a symbol "
        f"actually defined in {rel_path} (a def/async def/class, or a "
        f"module-level assignment target -- a dotted 'Class.method' form "
        f"resolves inside that class body), or correct {rel_path} if the "
        f"path itself is wrong."
    )


def _incapacity_diagnostic(
    *, manifest_path: Path, sut: str, rel_path: str, symbol: str, reason: str
) -> str:
    return (
        f"manifest could not be verified: {sut!r} in {manifest_path} -- "
        f"{reason}. "
        f"WHY: the manifest gate can only resolve a 'sut:' citation for "
        f"Python source it can parse; {symbol!r} was resolved relative to "
        f"{_REPO_ROOT} as {rel_path!r}, and no tier could analyze that "
        f"file, so it is neither confirmed grounded nor proven stale. "
        f"HOW: if {rel_path} is intentionally non-Python, cite a Python "
        f"symbol this gate can resolve instead; if it is Python but "
        f"currently unparseable, fix the syntax error so the file parses."
    )


def _ground_sut(sut: str, *, manifest_path: Path) -> _GroundingOutcome:
    """Resolve one ``path::symbol`` sut: reference to a three-state outcome.

    Grounds the symbol on the PROPERTY that the cited file DEFINES it --
    never the DESIGNATION that the characters merely occur in the file (a
    comment, docstring, string literal, import, or call does not ground).
    """
    if "::" not in sut:
        return _GroundingOutcome("grounded", None)
    rel_path, symbol = sut.split("::", 1)
    candidate = _REPO_ROOT / rel_path
    if not candidate.is_file():
        return _GroundingOutcome(
            "stale",
            _stale_diagnostic(
                manifest_path=manifest_path,
                sut=sut,
                rel_path=rel_path,
                symbol=symbol,
                cause=f"file not found at {candidate}",
            ),
        )
    if candidate.suffix != ".py":
        return _GroundingOutcome(
            "incapacity",
            _incapacity_diagnostic(
                manifest_path=manifest_path,
                sut=sut,
                rel_path=rel_path,
                symbol=symbol,
                reason=(
                    f"{rel_path} is not a Python file (.py); this gate can "
                    "only resolve DEFINED-symbol grounding for Python source"
                ),
            ),
        )
    try:
        tree = ast.parse(candidate.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return _GroundingOutcome(
            "incapacity",
            _incapacity_diagnostic(
                manifest_path=manifest_path,
                sut=sut,
                rel_path=rel_path,
                symbol=symbol,
                reason=f"{rel_path} does not parse as Python: {exc}",
            ),
        )
    if _symbol_is_defined(tree, symbol):
        return _GroundingOutcome("grounded", None)
    return _GroundingOutcome(
        "stale",
        _stale_diagnostic(
            manifest_path=manifest_path,
            sut=sut,
            rel_path=rel_path,
            symbol=symbol,
            cause=(
                f"no module-level or class-level definition of {symbol!r} "
                f"found in {rel_path} (checked def/async def/class and "
                "module-level assignment targets)"
            ),
        ),
    )


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


def _check_sut_grounding(document: object, *, manifest_path: Path) -> int:
    """Resolve every sut: symbol the manifest declares to its three-state outcome.

    Returns 1 if any symbol is stale (missing file or not defined there), 3
    if any symbol could not be resolved at all (see the module docstring's
    exit-code contract), 0 when every symbol is grounded.
    """
    if not isinstance(document, dict):
        return 0
    for sut in _iter_sut_values(document):
        outcome = _ground_sut(sut, manifest_path=manifest_path)
        if outcome.state == "grounded":
            continue
        print(outcome.diagnostic, file=sys.stderr)
        return 1 if outcome.state == "stale" else _EXIT_COULD_NOT_RESOLVE
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


def _missing_manifest_diagnostic(manifest_path: Path) -> str:
    """WHAT/WHY/HOW diagnostic for a manifest path that does not exist.

    Names (1) the missing path as given, (2) WHY the manifest gate needs it,
    (3) a concrete remediation, and (4) the current directory the CLI
    actually used to interpret a relative path -- the real cause of this bug
    class is almost always resolution against the wrong worktree, and prior
    to this fix no message said so. The directory is named as the "current
    directory", not a "repo root" -- nothing here verifies it is actually a
    repository root, only that it is the cwd the path was resolved against.

    HOW names no "producing tool" for the manifest itself -- there is none.
    The component manifest is HAND-AUTHORED by the architect during the
    DESIGN wave; the HOW instead names the schema it must satisfy and the
    real command that verifies it once written (GDP-4/GDP-8 authoring
    corollary -- a HOW must never gesture at a tool with no referent).
    """
    resolved_root = Path.cwd()
    return (
        f"manifest not found: {manifest_path} -- resolved relative to the "
        f"current directory {resolved_root}. WHY: the design wave's manifest "
        "gate needs this file to validate the unbounded-input-domain rows. "
        "HOW: the component manifest is HAND-AUTHORED by the architect "
        "during the DESIGN wave -- there is no generator for it. Author it "
        "against nWave/schemas/component-manifest.schema.json, then verify "
        "it with `python -m scripts.cli.validate_component_manifest "
        f"{manifest_path}`; or, if the file already exists elsewhere, check "
        "you are running from the intended repo root (this path is "
        "resolved relative to the current working directory)."
    )


def validate_manifest(manifest_path: Path) -> int:
    """Validate one manifest.yaml; return the process exit code.

    Returns 0 when the manifest is schema-valid and every sut: symbol is
    resolved as DEFINED in its cited file, 1 when the path is missing or a
    sut: symbol is stale, 2 when the manifest is malformed or schema-invalid,
    3 when a sut: citation could not be resolved at all (see the module
    docstring's exit-code contract).
    """
    if not manifest_path.is_file():
        print(_missing_manifest_diagnostic(manifest_path), file=sys.stderr)
        return 1
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    validator = _validator_for(document)
    errors = sorted(validator.iter_errors(document), key=lambda error: str(error.path))
    if errors:
        for error in errors:
            print(f"manifest is malformed: {error.message}", file=sys.stderr)
        return 2

    return _check_sut_grounding(document, manifest_path=manifest_path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- validate the manifest at argv[0]."""
    args = sys.argv[1:] if argv is None else argv
    return validate_manifest(Path(args[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
