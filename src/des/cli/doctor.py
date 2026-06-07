"""des doctor CLI -- per-target-language language-adapter gap report.

F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-01 walking-skeleton floor.

Reads the SSOT port catalog at ``nWave/data/language-adapter-ports.yaml``,
queries the canonical plugin-discovery substrate (PyPI entry-points group
``nwave.lang.adapter`` per ADR-031 Option C), and emits a JSON envelope on
stdout reporting per-port coverage for the requested target language.

Slice-01 contract (walking-skeleton floor): for ANY target language reports
``shape: "gaps"`` because no per-language plugins are registered yet (the
LanguageAdapterPlugin ABC ships in slice-02; the first Python reference
plugin ships in slice-05a). The ``missing_ports`` list enumerates every
LANGUAGE_BOUND port from the catalog.

Slice-03 will introduce ``shape: "ready"`` (every LANGUAGE_BOUND port has a
plugin) and ``shape: "unknown"`` (target language not in the catalog's
supported-languages set).

JSON envelope shape (slice-01 floor):

    {
      "target_language": "<language>",
      "shape": "gaps",
      "covered_ports": [...],
      "missing_ports": [...],
      "registered_plugins": [...]
    }

Exit-code contract (slice-01 floor):

* ``0`` -- report emitted successfully (informational; slice-04 raises to
  non-zero install-time when --target= is set)
* ``2`` -- malformed invocation (missing --target-language)
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import entry_points
from pathlib import Path

from des._internal import subset_parser


_REPO_ROOT = Path(__file__).resolve().parents[3]

_CATALOG_PATH = _REPO_ROOT / "nWave" / "data" / "language-adapter-ports.yaml"

_ENTRY_POINT_GROUP = "nwave.lang.adapter"


def _resolve_target_language(raw: str) -> str:
    """Normalise the operator-supplied target-language identifier.

    Slice-01 floor: lower-cases + strips. Slice-03 introduces alias resolution
    (e.g., ``ts`` -> ``typescript``, ``TSX`` -> ``typescript``) and validates
    against the catalog's supported-languages set; slice-01 stays lenient and
    reports GAPS for any input.
    """
    return raw.strip().lower()


def _load_catalog() -> dict:
    """Load + parse the SSOT port catalog YAML, or return an empty dict.

    Uses the stdlib-only ``subset_parser`` (per DES-bundle hygiene contract:
    no ``pyyaml`` import inside ``src/des/``). The catalog YAML shape
    (top-level scalars, string lists, list-of-dicts with folded-block
    ``summary`` + nested string lists) is fully covered by the subset.
    """
    if not _CATALOG_PATH.is_file():
        return {}
    document = subset_parser.load_file(_CATALOG_PATH)
    return document if isinstance(document, dict) else {}


def _enumerate_language_bound_ports(catalog: dict) -> list[str]:
    """Return the sorted list of LANGUAGE_BOUND port-ids from the catalog."""
    ports = catalog.get("ports") or []
    bound: list[str] = []
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        if entry.get("classification") == "LANGUAGE_BOUND":
            port_id = entry.get("port-id")
            if isinstance(port_id, str):
                bound.append(port_id)
    return sorted(bound)


def _discover_registered_plugins() -> list[str]:
    """Query the canonical plugin-discovery substrate (entry-points group).

    Slice-01 floor: returns the entry-point NAMES registered in the
    ``nwave.lang.adapter`` group. With no plugins registered (slice-01 reality)
    returns an empty list. Slice-02 ships the LanguageAdapterPlugin ABC,
    slice-05a registers the first Python adapter.
    """
    eps = entry_points(group=_ENTRY_POINT_GROUP)
    return sorted(ep.name for ep in eps)


def _build_report(target_language: str) -> dict:
    """Compose the JSON envelope per the slice-01 contract."""
    catalog = _load_catalog()
    language_bound_ports = _enumerate_language_bound_ports(catalog)
    registered_plugins = _discover_registered_plugins()

    # Slice-01 floor: no plugins registered => every LANGUAGE_BOUND port is
    # missing for any target language. covered_ports is empty.
    covered_ports: list[str] = []
    missing_ports: list[str] = list(language_bound_ports)

    return {
        "target_language": target_language,
        "shape": "gaps",
        "covered_ports": covered_ports,
        "missing_ports": missing_ports,
        "registered_plugins": registered_plugins,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- emit the per-target-language gap JSON report."""
    parser = argparse.ArgumentParser(
        prog="des doctor",
        description=(
            "Report language-adapter coverage gaps for a target language "
            "(F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE)."
        ),
    )
    parser.add_argument(
        "--target-language",
        required=True,
        help="Target-language identifier (e.g., python, typescript, go).",
    )
    args = parser.parse_args(argv)

    target_language = _resolve_target_language(args.target_language)
    report = _build_report(target_language)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
