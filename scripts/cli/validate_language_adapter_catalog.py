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
from typing import TYPE_CHECKING, cast

import yaml
from jsonschema import Draft202012Validator

from des.testarch.capabilities import build_registry
from des.testarch.discovery import (
    DiscoveryResolutionError,
    resolve_and_probe_realized_surface,
)
from des.testarch.port_realization_discovery import (
    PortRealizationProbeError,
    resolve_and_probe_port_realization_with_detail,
)
from des.testarch.rules.registry_conformance import (
    detect_per_plugin_capability_conformance,
)


if TYPE_CHECKING:
    from des.ports.language_adapter_plugin import LanguageAdapterPlugin
    from des.testarch.port_realization_discovery import (
        PortRealizationGapDetail,
        PortRealizationUnknownPortNote,
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


CATALOG_GATE_INDETERMINATE = 3
"""Exit lane: catalog path unreadable/unparseable -- DISTINCT loud signal (GDP-6).

Reuses the same lane number `run_conformance_gate` / `run_port_realization_gate`
already use for "the input is unresolvable" -- never colliding with the 0
conformant / 1 witness-gap / 2 malformed-schema lanes above.
"""

_CATALOG_GATE_INDETERMINATE_PREFIX = "language-adapter-catalog is indeterminate"


def validate_catalog(catalog_path: Path) -> int:
    """Validate one language-adapter-ports.yaml; return the process exit code."""
    try:
        raw_text = catalog_path.read_text(encoding="utf-8")
        document = yaml.safe_load(raw_text)
    except (OSError, yaml.YAMLError) as failure:
        print(
            f"{_CATALOG_GATE_INDETERMINATE_PREFIX}: cannot read catalog "
            f"{catalog_path!s}: {failure}",
            file=sys.stderr,
        )
        return CATALOG_GATE_INDETERMINATE
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

    if discovery_source is None and not realized_by_plugin:
        print(
            f"{_CONFORMANCE_GATE_LOUD_PREFIX}: 0 plugins probed via the live "
            f"nwave.lang.adapter entry-points discovery -- cannot certify "
            f"conformance on nothing. Is the interpreter/entry-points "
            f"correct? Expected >=1 plugin from pyproject "
            f'[project.entry-points."nwave.lang.adapter"]. Re-check with: '
            f"python -m scripts.cli.validate_language_adapter_catalog "
            f"--check-conformance",
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


# --- slice-03: port-realization gate mode (declared-True-but-stub-backed) --
#
# language-port-realization-gate, slice-03 (DELIVER, A_GREEN). The
# ``--check-port-realization`` mode composes slice-02's composition root
# (``des.testarch.port_realization_discovery``) over one of 3 discovery-source
# shapes (DDD-D6, mirrors ``run_conformance_gate``'s parameter shape). Exit
# lanes reuse the existing 0/1/3 contract, discriminated from
# ``--check-conformance`` by the stderr message prefix.

PORT_REALIZATION_GATE_CONFORMANT = 0
"""Exit lane: no declared-covered port is stub-backed."""

PORT_REALIZATION_GATE_GAP = 1
"""Exit lane: >=1 declared-True-but-stub-backed port (the gap lane)."""

PORT_REALIZATION_GATE_INDETERMINATE = 3
"""Exit lane: discovery target unresolvable -- DISTINCT loud signal (GDP-6)."""

_PORT_REALIZATION_GAP_PREFIX = (
    "language-adapter port-realization gate: registered-but-stub-backed"
)
_PORT_REALIZATION_LOUD_PREFIX = (
    "language-adapter port-realization gate is indeterminate"
)

_CHECK_PORT_REALIZATION_FLAG = "--check-port-realization"

# HOW -- the Protocol each stub-backed port must implement (GDP-3/4: the
# FAIL-LOUD block names the exact interface to implement).
_PORT_REALIZATION_PROTOCOL_BY_PORT = {
    "run_contract_gate": "ContractGatePort",
    "verify_environmental_e2e": "EnvironmentalE2EPort",
    "check_robustness_density": "RobustnessDensityPort",
}


def _load_entry_point_plugin(entry_point: EntryPoint) -> LanguageAdapterPlugin:
    """Resolve one ``EntryPoint`` target, naming it in any resolution failure.

    The raw stdlib exception (e.g. ``ModuleNotFoundError: No module named
    'not'`` for target ``not.a.module:Nope``) does not repeat the full
    dotted target the caller named -- re-raise as ``PortRealizationProbeError``
    with ``entry_point.value`` embedded so a degrade-LOUD diagnostic can
    always name the unresolvable target (GDP-3/6, T8), not just the
    top-level package fragment stdlib reports.
    """
    try:
        return cast("LanguageAdapterPlugin", entry_point.load()())
    except (ImportError, AttributeError, TypeError) as exc:
        raise PortRealizationProbeError(
            f"cannot resolve target {entry_point.value!r}: {exc}"
        ) from exc


def _resolve_port_realization_plugins(
    discovery_source: Iterable[LanguageAdapterPlugin] | Iterable[EntryPoint] | None,
) -> list[LanguageAdapterPlugin] | None:
    """Coerce the 3 discovery-source shapes into resolved plugin instances.

    ``None`` is passed straight through -- the composition root reads the live
    registry itself. An iterable of already-resolved ``LanguageAdapterPlugin``
    instances is used directly (mirrors
    ``resolve_and_probe_port_realization_with_detail``'s own ``plugins``
    parameter, T2-T4). An iterable of raw ``EntryPoint`` is resolved here
    (``.load()`` + instantiate, T5, T7/T8's ``--plugin`` flag) -- a genuine
    resolution failure propagates to the caller, which maps it onto the
    INDETERMINATE lane.
    """
    if discovery_source is None:
        return None
    materialized = list(discovery_source)
    if materialized and isinstance(materialized[0], EntryPoint):
        return [
            _load_entry_point_plugin(entry_point)
            for entry_point in cast("list[EntryPoint]", materialized)
        ]
    return cast("list[LanguageAdapterPlugin]", materialized)


def _parse_plugin_flags(args: list[str]) -> tuple[EntryPoint, ...] | None:
    """Parse repeatable ``--plugin <module>:<Class>`` flags (T7/T8).

    Returns ``None`` when no ``--plugin`` flag is present -- the caller falls
    back to reading the live registry (``discovery_source=None``, unchanged
    T1/T1b behaviour). Each present ``--plugin <target>`` becomes an
    ``EntryPoint`` whose ``value`` IS the ``module:Class`` target string,
    resolved via the SAME ``.load()`` mechanism the raw-``EntryPoint``
    discovery-source shape already uses (T5) -- an unresolvable target
    degrades to the same INDETERMINATE lane, never a raw traceback.
    """
    targets = [
        args[index + 1]
        for index in range(len(args))
        if args[index] == "--plugin" and index + 1 < len(args)
    ]
    if not targets:
        return None
    return tuple(
        EntryPoint(name=target, value=target, group="nwave.lang.adapter")
        for target in targets
    )


def _display_path(file_path: str) -> str:
    """Repo-relative display form of an ``inspect``-sourced absolute path."""
    try:
        return str(Path(file_path).resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return file_path


def _print_port_realization_gap(
    violation: object, detail: PortRealizationGapDetail | None
) -> None:
    """FAIL-LOUD one block per gap (GDP-3/4): WHAT/WHY/HOW, never bare."""
    header = (
        f"{_PORT_REALIZATION_GAP_PREFIX} port {violation.port!r} on plugin "
        f"{violation.plugin_id!r}"
    )
    if detail is None:
        print(header, file=sys.stderr)
        return
    protocol_name = _PORT_REALIZATION_PROTOCOL_BY_PORT.get(violation.port, "<unknown>")
    file_display = _display_path(detail.file_path)
    print(
        f"{header}: method `{detail.method_name}` is a stub "
        f"({file_display}:{detail.line_number}). Implement `{protocol_name}` in "
        f"{file_display}. Re-check with: python -m "
        f"scripts.cli.validate_language_adapter_catalog {_CHECK_PORT_REALIZATION_FLAG}",
        file=sys.stderr,
    )


_PORT_REALIZATION_NOTE_PREFIX = (
    "language-adapter port-realization gate: note (out-of-catalog, not-probed)"
)


def _print_unknown_port_note(note: PortRealizationUnknownPortNote) -> None:
    """Visibly note a declared-covered port outside the 3-port probe catalog.

    Not a gap (the port is genuinely out of this gate's scope, e.g.
    ``nwave-lang-rust``'s legacy ``"test-runner"`` port) -- but silence is
    also wrong (Vera examine finding #2, GDP-6): a maintainer must be able
    to tell "verified nothing to report" from "silently ignored a declared
    port".
    """
    print(
        f"{_PORT_REALIZATION_NOTE_PREFIX}: plugin {note.plugin_id!r} declares "
        f"port {note.port!r}, outside this gate's known port catalog.",
        file=sys.stderr,
    )


def run_port_realization_gate(
    discovery_source: Iterable[LanguageAdapterPlugin]
    | Iterable[EntryPoint]
    | None = None,
) -> int:
    """Run the ``--check-port-realization`` gate; return the process exit code.

    Composes slice-02's composition root
    (``resolve_and_probe_port_realization_with_detail`` /
    ``PortRealizationProbeError``) over one of 3 discovery-source shapes
    (DDD-D6, mirrors ``run_conformance_gate``):

    * ``None`` -- read the live ``nwave.lang.adapter`` registry.
    * an iterable of ``LanguageAdapterPlugin`` instances -- AST-stub-probed
      directly.
    * an iterable of ``EntryPoint`` -- resolved (``.load()`` + instantiate)
      then AST-stub-probed.

    Exit lanes: ``0`` CONFORMANT (no declared-covered port is stub-backed --
    a truthful, non-silent summary is printed naming the outcome and the
    count of plugins probed, Vera examine finding #1) / ``1`` GAP (>=1
    declared-True-but-stub-backed port -- one FAIL-LOUD block per offender
    naming WHAT the port+stub method @file:line, the Protocol to implement,
    the adapter file, and the re-check command) / ``3`` INDETERMINATE (an
    unresolvable discovery target -- a resolution failure or
    ``PortRealizationProbeError``). Never a raw traceback, never a silent
    CONFORMANT on a resolution failure (GDP-6). Any declared-covered port
    outside the known 3-port catalog is visibly noted, never silently
    skipped (Vera examine finding #2).
    """
    try:
        plugins = _resolve_port_realization_plugins(discovery_source)
        verdict, details, unknown_port_notes, plugin_count = (
            resolve_and_probe_port_realization_with_detail(plugins)
        )
    except (
        PortRealizationProbeError,
        ImportError,
        AttributeError,
        TypeError,
    ) as failure:
        print(f"{_PORT_REALIZATION_LOUD_PREFIX}: {failure}", file=sys.stderr)
        return PORT_REALIZATION_GATE_INDETERMINATE

    for note in unknown_port_notes:
        _print_unknown_port_note(note)

    if discovery_source is None and plugin_count == 0:
        print(
            f"{_PORT_REALIZATION_LOUD_PREFIX}: 0 plugins probed via the live "
            f"nwave.lang.adapter entry-points discovery -- cannot certify "
            f"port-realization on nothing. Is the interpreter/entry-points "
            f"correct? Expected >=1 plugin from pyproject "
            f'[project.entry-points."nwave.lang.adapter"]. Re-check with: '
            f"python -m scripts.cli.validate_language_adapter_catalog "
            f"{_CHECK_PORT_REALIZATION_FLAG}",
            file=sys.stderr,
        )
        return PORT_REALIZATION_GATE_INDETERMINATE

    if not verdict.flagged:
        print(
            f"language-adapter port-realization gate: conformant -- "
            f"{plugin_count} plugin(s) probed, 0 gap(s) found."
        )
        return PORT_REALIZATION_GATE_CONFORMANT

    details_by_offender = {(d.plugin_id, d.port): d for d in details}
    for violation in verdict.violations:
        detail = details_by_offender.get((violation.plugin_id, violation.port))
        _print_port_realization_gap(violation, detail)
    return PORT_REALIZATION_GATE_GAP


def main(argv: list[str] | None = None) -> int:
    """CLI entry point -- validate the catalog at argv[0], or run a gate mode."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: python -m scripts.cli.validate_language_adapter_catalog "
            "[--check-conformance] "
            "[--check-port-realization [--plugin <module>:<Class> ...]] "
            "<catalog.yaml>\n"
            "exit lanes: 0 conformant / 1 gap / 3 indeterminate (loud, never silent)",
            file=sys.stderr,
        )
        return 2
    if args[0] == "--check-conformance":
        return run_conformance_gate()
    if args[0] == _CHECK_PORT_REALIZATION_FLAG:
        discovery_source = _parse_plugin_flags(args[1:])
        return run_port_realization_gate(discovery_source)
    return validate_catalog(Path(args[0]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
