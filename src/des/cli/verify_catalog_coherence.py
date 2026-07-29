"""des verify-catalog-coherence -- registry <-> catalog <-> per-gate-file drift.

Charter: docs/product/expectations/verify-catalog-coherence/
         des-verify-catalog-coherence-reports-registry-catalog-drift.md
Feature-delta: docs/feature/verify-catalog-coherence/feature-delta.md

A subcommand added to the CLI registry (`src/des/cli/__main__.py` `_REGISTRY`)
but not reconciled into the gate catalog (`nWave/gates/_catalog.yaml`) + its
per-gate contract file (`nWave/gates/<id>.yaml`) is a drift class the
build-tier catalog suite (`tests/build/d4_phase_1_catalog_files/`) catches
only in a full run. This module is the FAST (<1s) explicit/CI/feature-end
check for the same drift: it compares three sets --

  (a) CLI registry subcommand names   (`_SubcommandRow.name` in `_REGISTRY`)
  (b) catalog gate_ids                (`nWave/gates/_catalog.yaml` gates[].gate_id)
  (c) per-gate `.yaml` files          (`nWave/gates/*.yaml` minus meta files)

-- and on any mismatch reports each drifting id + the concrete HOW to fix it
(add the missing catalog row / per-gate file / registry row). Exit 0 when the
three sets are coherent.

Filesystem + regex only (GDP-7 agnostic): the registry is parsed as TEXT from
`<repo_root>/src/des/cli/__main__.py` -- never imported -- so this module can
evaluate an arbitrary `--repo-root` (including throwaway fixture trees) without
executing that tree's Python. Degrade-LOUD (GDP-6) on THREE surfaces, never a
traceback and never a silent pass: (1) a missing/unreadable nWave-dev CLI
registry (`--repo-root` is not an nWave-dev checkout), (2) a missing/unreadable
`nWave/gates/` directory (same cause), and (3) a missing/malformed
`_catalog.yaml`. All three raise a `CoherenceInputUnavailableError` (subclass
`CatalogMalformedError` for surface 3) that `main()` renders as a single
human-readable guidance line plus an `indeterminate` JSON verdict with a
non-zero exit.

Stdlib-only (no ``import yaml``) per the DES-bundle contract (F-D-09,
`tests/build/acceptance/plugin/steps/test_des_bundle_steps.py::des_no_external_deps`):
a bundled `des` module MUST NOT depend on PyYAML. `_catalog.yaml`'s `gate_id`
entries are parsed with a line-oriented regex instead (mirroring `gate_g.py`'s
stdlib-only manifest `row-id` parsing) -- sufficient for this gate's known
block-list shape and enough to detect a structurally malformed catalog
(missing `gates:` block / unparseable entries) without a real YAML parser.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument


_SUBCOMMAND_ROW_NAME_RE = re.compile(r'_SubcommandRow\(\s*"([^"]+)"')
_GATES_BLOCK_MARKER_RE = re.compile(r"^gates:\s*$", re.MULTILINE)
_GATE_ID_ENTRY_RE = re.compile(
    r'^\s*-\s*gate_id:\s*"?([a-z0-9][a-z0-9-]*)"?\s*$', re.MULTILINE
)
_META_CATALOG_FILES = frozenset({"_catalog.yaml", "_schema.yaml"})


class CoherenceInputUnavailableError(Exception):
    """An input needed to evaluate catalog coherence is missing or unreadable
    -- typically because `--repo-root` is not an nWave-dev checkout at all
    (no CLI registry, no `nWave/gates/` directory). `CatalogMalformedError`
    is the more specific subclass for a present-but-malformed catalog file.
    """


class CatalogMalformedError(CoherenceInputUnavailableError):
    """`nWave/gates/_catalog.yaml` is missing, unreadable, or fails to parse."""


@dataclass(frozen=True)
class CoherenceResult:
    """The three sets plus the four per-kind drift lists.

    Per feature-delta [REF] Code-Design: registry-not-in-catalog,
    catalog-not-in-registry, catalog-without-per-gate-file,
    per-gate-without-catalog-entry.
    """

    registry_names: frozenset[str]
    catalog_gate_ids: frozenset[str]
    per_gate_stems: frozenset[str]
    registry_not_in_catalog: tuple[str, ...]
    catalog_not_in_registry: tuple[str, ...]
    catalog_without_per_gate_file: tuple[str, ...]
    per_gate_without_catalog_entry: tuple[str, ...]

    @property
    def coherent(self) -> bool:
        return not (
            self.registry_not_in_catalog
            or self.catalog_not_in_registry
            or self.catalog_without_per_gate_file
            or self.per_gate_without_catalog_entry
        )

    @property
    def drifting_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    *self.registry_not_in_catalog,
                    *self.catalog_not_in_registry,
                    *self.catalog_without_per_gate_file,
                    *self.per_gate_without_catalog_entry,
                }
            )
        )


def _parse_registry_names(repo_root: Path) -> frozenset[str]:
    """Regex-parse `_SubcommandRow("<name>", ...)` occurrences (no import).

    Raises `CoherenceInputUnavailableError` when the nWave-dev CLI registry
    module can't be read -- the common case being `repo_root` is not an
    nWave-dev checkout at all (bare dir, unrelated project, missing path).
    """
    main_py = repo_root / "src" / "des" / "cli" / "__main__.py"
    try:
        text = main_py.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoherenceInputUnavailableError(
            "cannot read the nWave-dev CLI registry module -- this "
            "repo_root does not look like an nWave-dev checkout"
        ) from exc
    return frozenset(_SUBCOMMAND_ROW_NAME_RE.findall(text))


def _parse_catalog_gate_ids(repo_root: Path) -> frozenset[str]:
    """Stdlib-only line-oriented parse of `_catalog.yaml` `gate_id` entries.

    Raises `CatalogMalformedError` when the file is unreadable, has no
    top-level `gates:` block, or yields zero `- gate_id: <id>` entries under
    it -- the structural signals a real YAML parser would surface as a parse
    failure, reached here without depending on PyYAML (DES-bundle contract).
    """
    catalog_path = repo_root / "nWave" / "gates" / "_catalog.yaml"
    try:
        raw = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogMalformedError(
            f"cannot read catalog file {catalog_path}: {exc}"
        ) from exc
    if not _GATES_BLOCK_MARKER_RE.search(raw):
        raise CatalogMalformedError(
            f"{catalog_path} has no top-level 'gates:' block -- malformed catalog"
        )
    gate_ids = frozenset(_GATE_ID_ENTRY_RE.findall(raw))
    if not gate_ids:
        raise CatalogMalformedError(
            f"{catalog_path} declares a 'gates:' block but no gate_id entries "
            "could be parsed from it -- malformed catalog"
        )
    return gate_ids


def _parse_per_gate_stems(repo_root: Path) -> frozenset[str]:
    """Raises `CoherenceInputUnavailableError` when `nWave/gates/` is missing
    or not a directory -- symmetric with `_parse_registry_names` above, same
    root cause (`repo_root` is not an nWave-dev checkout)."""
    gates_dir = repo_root / "nWave" / "gates"
    if not gates_dir.is_dir():
        raise CoherenceInputUnavailableError(
            "cannot read the nWave gate catalog directory -- this repo_root "
            "does not look like an nWave-dev checkout"
        )
    return frozenset(
        p.stem for p in gates_dir.glob("*.yaml") if p.name not in _META_CATALOG_FILES
    )


def compute_catalog_coherence(repo_root: Path) -> CoherenceResult:
    """Pure comparison of the registry/catalog/per-gate-file sets under repo_root.

    Raises `CoherenceInputUnavailableError` if the nWave-dev CLI registry or
    the `nWave/gates/` directory can't be read (repo_root is not an
    nWave-dev checkout), or its `CatalogMalformedError` subclass if
    `_catalog.yaml` specifically is missing, unreadable, or fails to parse --
    callers degrade this LOUD, never silently.
    """
    registry_names = _parse_registry_names(repo_root)
    catalog_gate_ids = _parse_catalog_gate_ids(repo_root)
    per_gate_stems = _parse_per_gate_stems(repo_root)

    return CoherenceResult(
        registry_names=registry_names,
        catalog_gate_ids=catalog_gate_ids,
        per_gate_stems=per_gate_stems,
        registry_not_in_catalog=tuple(sorted(registry_names - catalog_gate_ids)),
        catalog_not_in_registry=tuple(sorted(catalog_gate_ids - registry_names)),
        catalog_without_per_gate_file=tuple(sorted(catalog_gate_ids - per_gate_stems)),
        per_gate_without_catalog_entry=tuple(sorted(per_gate_stems - catalog_gate_ids)),
    )


def _render_how(result: CoherenceResult) -> list[str]:
    how: list[str] = []
    for gate_id in result.registry_not_in_catalog:
        how.append(
            f"'{gate_id}' is in the CLI registry but missing from the catalog: "
            f"add a gate_id: {gate_id} row to nWave/gates/_catalog.yaml "
            f"and create the per-gate file nWave/gates/{gate_id}.yaml."
        )
    for gate_id in result.catalog_not_in_registry:
        how.append(
            f"'{gate_id}' is in nWave/gates/_catalog.yaml but missing from the "
            "CLI registry: add a "
            f'_SubcommandRow("{gate_id}", ...) row to '
            "src/des/cli/__main__.py _REGISTRY."
        )
    for gate_id in result.catalog_without_per_gate_file:
        how.append(
            f"'{gate_id}' has a nWave/gates/_catalog.yaml row but no per-gate "
            f"file: create nWave/gates/{gate_id}.yaml (GateContractFull shape, "
            "mirroring an existing per-gate file)."
        )
    for gate_id in result.per_gate_without_catalog_entry:
        how.append(
            f"'{gate_id}' has a per-gate file nWave/gates/{gate_id}.yaml but no "
            "catalog row: add a gate_id: "
            f"{gate_id} row to nWave/gates/_catalog.yaml."
        )
    return how


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-catalog-coherence",
        description=(
            "Compare the CLI registry, gate catalog, and per-gate files; "
            "report drift with a HOW to reconcile."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-root",
        type=str,
        default=".",
        help=(
            "Repo root holding src/des/cli/__main__.py and nWave/gates/ (default: cwd)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    try:
        result = compute_catalog_coherence(repo_root)
    except CoherenceInputUnavailableError as exc:
        how = [
            "point --repo-root at a real nWave-dev checkout (it must hold "
            "the nWave-dev CLI registry module and an nWave/gates/ catalog "
            "directory); if you believe you are already inside one, fix or "
            "restore nWave/gates/_catalog.yaml so it parses as valid YAML "
            "with a top-level 'gates' list."
        ]
        print(
            f"verify-catalog-coherence: {exc} -- this check only evaluates "
            "an nWave-dev checkout. " + how[0],
            file=sys.stderr,
        )
        verdict = {
            "event": "CatalogCoherenceChecked",
            "verdict": "indeterminate",
            "reason": f"cannot evaluate catalog coherence: {exc}",
            "how": how,
            "drifting_ids": [],
        }
        print(json.dumps(verdict))
        return 1

    if result.coherent:
        verdict = {
            "event": "CatalogCoherenceChecked",
            "verdict": "coherent",
            "reason": (
                f"registry ({len(result.registry_names)}), catalog "
                f"({len(result.catalog_gate_ids)}), and per-gate files "
                f"({len(result.per_gate_stems)}) counts match with no drift."
            ),
            "how": [],
            "drifting_ids": [],
        }
        print(json.dumps(verdict))
        return 0

    verdict = {
        "event": "CatalogCoherenceChecked",
        "verdict": "drifted",
        "reason": (
            f"{len(result.drifting_ids)} drifting id(s) across registry/"
            "catalog/per-gate-files."
        ),
        "how": _render_how(result),
        "drifting_ids": list(result.drifting_ids),
    }
    print(json.dumps(verdict))
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
