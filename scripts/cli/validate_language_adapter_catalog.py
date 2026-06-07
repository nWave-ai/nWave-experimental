"""Language-adapter port-catalog validation CLI.

F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-01. Parses
``nWave/data/language-adapter-ports.yaml``, validates it against
``nWave/schemas/language-adapter-ports.schema.json`` (Draft 2020-12), and
grounds every ``witnesses:`` path against the repo tree.

Exit-code contract (slice-01 floor -- per feature-delta §exit-codes):

* ``0`` -- catalog present, schema-valid, every witness path resolves on disk
* ``1`` -- a witness path is not findable on disk (CitedPathNotFound)
* ``2`` -- catalog schema-invalid / malformed / unknown forward-incompatible
  ``schema-version``

Stdout (slice-01 floor): on exit 0 emits one line per port summarising
``port-id [classification]``. The slice-01 AT pins that the three Nova-audited
LANGUAGE_BOUND CLIs appear (``run_contract_gate``, ``verify_environmental_e2e``,
``check_robustness_density``).

Invocable as
``python -m scripts.cli.validate_language_adapter_catalog <path>``.

slice-03 (language-adapter-registry-self-enforcement) EXTENDS this CLI in-place with a
``--check-conformance`` mode (DDD-D2 -- one CLI, no sibling validator). The mode runs the
live-registry conformance gate: it resolve-and-probes the registered ``nwave.lang.adapter``
plugins (C2 ``resolve_and_probe_realized_surface``) and cross-checks each plugin's realized
surface against the registered-capability obligation set (C1
``detect_per_plugin_capability_conformance``). Exit lanes (additive, orthogonal to the
existing 0/1/2 catalog lanes):

* ``0`` -- every discovered plugin realizes every required capability (CONFORMANT). Over
  the LIVE registry this is DEFERRED to slice-05a; at HEAD the inert ``_conformance_fixture``
  keeps the live gate on lane ``1``.
* ``1`` -- at least one registered-but-unrealized ``(plugin, capability)`` pair (a real
  coverage gap). Shares the generic RED/gap lane with the catalog modes, discriminated by
  the stderr message prefix.
* ``3`` -- INDETERMINATE / loud: the discovery surface is unresolvable (a registered entry
  point whose target cannot be imported). A DISTINCT loud lane (DDD-D5), never a silent
  green and never a fabricated empty discovery set.

RED scaffold (Mandate-7 / ADR-025): ``run_conformance_gate`` raises ``AssertionError`` (the
RED token) until A_GREEN implements it. The composition root (the slice-03 acceptance
service + the CLI ``main`` mode dispatch) drives this gate-runner; the live ``entry_points``
read is supplied to it as a parameter (DDD-D6) so the gate-runner is parameterized over its
discovery source.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from des.testarch.capabilities import build_registry
from des.testarch.discovery import (
    DiscoveryResolutionError,
    resolve_and_probe_realized_surface,
)
from des.testarch.rules.registry_conformance import (
    detect_per_plugin_capability_conformance,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCHEMA_PATH = _REPO_ROOT / "nWave" / "schemas" / "language-adapter-ports.schema.json"


def _check_witness_grounding(document: object) -> int:
    """Grep-verify every witnesses: path in port entries.

    Each witness is a repo-relative path that MUST exist on disk. Returns 1 if
    any path is missing, 0 otherwise.
    """
    if not isinstance(document, dict):
        return 0
    ports = document.get("ports") or []
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        witnesses = entry.get("witnesses") or []
        for rel_path in witnesses:
            candidate = _REPO_ROOT / rel_path
            if not candidate.exists():
                print(
                    f"language-adapter-catalog is stale: witness path "
                    f"{rel_path!r} not found on disk",
                    file=sys.stderr,
                )
                return 1
    return 0


def _emit_summary(document: object) -> None:
    """Emit one summary line per port to stdout (operator-facing)."""
    if not isinstance(document, dict):
        return
    ports = document.get("ports") or []
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        port_id = entry.get("port-id", "<unknown>")
        classification = entry.get("classification", "<unknown>")
        print(f"{port_id} [{classification}]")


def validate_catalog(catalog_path: Path) -> int:
    """Validate one language-adapter-ports.yaml; return the process exit code."""
    document = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(
                f"language-adapter-catalog is malformed: {error.message}",
                file=sys.stderr,
            )
        return 2

    grounding = _check_witness_grounding(document)
    if grounding != 0:
        return grounding

    _emit_summary(document)
    return 0


# --- slice-03: live-registry conformance gate mode (C3) ---------------------
#
# RED SCAFFOLD (Mandate-7 / ADR-025). The ``--check-conformance`` mode runs the
# live-registry conformance gate: resolve-and-probe the registered ``nwave.lang.adapter``
# plugins (C2) + cross-check against the registered-capability obligation set (C1), then
# map the verdict / discovery failure onto the exit-code contract below.

CONFORMANCE_GATE_CONFORMANT = 0
"""Exit lane: every discovered plugin realizes every required capability."""

CONFORMANCE_GATE_GAP = 1
"""Exit lane: >=1 registered-but-unrealized (plugin, capability) pair (the gap lane)."""

CONFORMANCE_GATE_INDETERMINATE = 3
"""Exit lane: discovery surface unresolvable -- DISTINCT loud signal (DDD-D5)."""

_CONFORMANCE_GATE_GAP_PREFIX = (
    "language-adapter conformance gate: registered-but-unrealized"
)
_CONFORMANCE_GATE_LOUD_PREFIX = "language-adapter conformance gate is indeterminate"


def run_conformance_gate(
    discovery_source: Iterable[EntryPoint] | Mapping[str, frozenset[str]] | None = None,
) -> int:
    """Run the live-registry conformance gate; return the process exit code.

    Resolve-and-probes the registered plugins (C2
    ``resolve_and_probe_realized_surface``) and cross-checks each plugin's realized
    surface against the registered-capability obligation set (C1
    ``detect_per_plugin_capability_conformance``). ``discovery_source`` is the
    discovery source (DDD-D6), one of three shapes:

    * ``None`` -- read the real live registry
      (``entry_points(group="nwave.lang.adapter")``) and resolve-and-probe it.
    * an iterable of ``EntryPoint`` -- the injected raw registry to resolve-and-probe
      (the unresolvable corpus drives the exit-3 loud lane).
    * a ``Mapping[str, frozenset[str]]`` -- a PRE-RESOLVED discovery RESULT
      (the clean corpus): already-probed ``{plugin_id: realized}``; used directly,
      no ``.load()`` (DDD-D6 composition-root distinction).

    Exit lanes: ``0`` CONFORMANT / ``1`` registered-but-unrealized gap (stderr
    discriminated by ``_CONFORMANCE_GATE_GAP_PREFIX``) / ``3`` INDETERMINATE loud
    (discovery unresolvable -- a ``DiscoveryResolutionError``, stderr
    ``_CONFORMANCE_GATE_LOUD_PREFIX``). Never silent green on resolution failure (DDD-D5).
    """
    required = frozenset(
        capability.value for capability in build_registry().required_capabilities()
    )
    try:
        realized_by_plugin = _resolve_discovery(required, discovery_source)
    except DiscoveryResolutionError as failure:
        print(
            f"{_CONFORMANCE_GATE_LOUD_PREFIX}: {failure}",
            file=sys.stderr,
        )
        return CONFORMANCE_GATE_INDETERMINATE

    verdict = detect_per_plugin_capability_conformance(required, realized_by_plugin)
    if verdict.flagged:
        for violation in verdict.violations:
            print(
                f"{_CONFORMANCE_GATE_GAP_PREFIX} capability "
                f"{violation.capability!r} on plugin {violation.plugin_id!r}",
                file=sys.stderr,
            )
        return CONFORMANCE_GATE_GAP
    return CONFORMANCE_GATE_CONFORMANT


def _resolve_discovery(
    required: frozenset[str],
    discovery_source: Iterable[EntryPoint] | Mapping[str, frozenset[str]] | None,
) -> Mapping[str, frozenset[str]]:
    """Coerce the three discovery-source shapes to a ``{plugin_id: realized}`` map.

    A ``Mapping`` is a pre-resolved discovery RESULT (used directly); ``None`` reads
    the live registry; any other iterable is a raw ``EntryPoint`` source to
    resolve-and-probe via C2.
    """
    if isinstance(discovery_source, Mapping):
        return discovery_source
    entry_points_source = (
        entry_points(group="nwave.lang.adapter")
        if discovery_source is None
        else discovery_source
    )
    return resolve_and_probe_realized_surface(required, entry_points_source)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- validate the catalog at argv[0], or run a gate mode."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: python -m scripts.cli.validate_language_adapter_catalog "
            "[--check-conformance] <catalog.yaml>",
            file=sys.stderr,
        )
        return 2
    if args[0] == "--check-conformance":
        return run_conformance_gate()
    return validate_catalog(Path(args[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
