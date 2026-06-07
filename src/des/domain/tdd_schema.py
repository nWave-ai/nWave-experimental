"""
TDD Schema Loader - Single Source of Truth for TDD Rules.

Loads TDD phase definitions, validation rules, and skip prefixes from
nWave/templates/step-tdd-cycle-schema.json. Provides cached access to avoid
repeated file I/O.

Dual-canon support (ADR-025, 2026-05-07):
- ``canonical_phases`` (v5, 3-phase: RED/GREEN/COMMIT) is the canonical list
  per ADR-025. RED absorbs PREPARE+RED_ACCEPTANCE+RED_UNIT. This is the
  default returned by ``tdd_phases`` (2026-05-18 flip — F1+F2+F3 closes
  doc-impl drift identified in RCA RC-A).
- ``legacy_phases`` (v4, 5-phase: PREPARE/RED_ACCEPTANCE/RED_UNIT/GREEN/COMMIT)
  is preserved for backward-compat audit-log replay of pre-2026-05-07
  commits. Callers reach the legacy list explicitly via
  ``phases_for("4.0")`` or the ``legacy_phases`` field.

Design Principles:
- Single Responsibility: Only loads and parses TDD schema
- Dependency Injection: Schema path can be overridden for testing
- Immutability: Schema data is frozen after load
- Caching: Schema loaded once per process lifetime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from des.domain.json_schema_loader import JsonSchemaLoader


# Module-level constants exposing both canons explicitly.
# ADR-025 (2026-05-07): canonical TDD cycle is 3-phase. Legacy 5-phase
# preserved for backward-compat audit-log replay.
LEGACY_PHASES: tuple[str, ...] = (
    "PREPARE",
    "RED_ACCEPTANCE",
    "RED_UNIT",
    "GREEN",
    "COMMIT",
)
"""5-phase TDD cycle (v4, ADR-024 era). Kept for audit-log replay of
pre-2026-05-07 commits and for the JSON schema's active ``valid_tdd_phases``
list (which still drives the default loader path)."""

CANONICAL_PHASES: tuple[str, ...] = ("RED", "GREEN", "COMMIT")
"""3-phase TDD cycle (v5, ADR-025, 2026-05-07). RED absorbs
PREPARE+RED_ACCEPTANCE+RED_UNIT via the fail-for-right-reason gate; GREEN +
COMMIT semantics unchanged from v4."""


class TDDSchemaProtocol(Protocol):
    """Protocol defining the TDD schema interface.

    Used for type hints and to enable testing with mock implementations.
    """

    @property
    def tdd_phases(self) -> tuple[str, ...]:
        """Ordered tuple of active TDD phase names.

        Returns CANONICAL_PHASES (3-phase v5, ADR-025) by default;
        ``schema_version='4.0'`` dispatch routes legacy callers via the
        ``legacy_phases`` property / ``phases_for("4.0")``.
        """
        ...

    @property
    def valid_statuses(self) -> tuple[str, ...]:
        """Valid phase execution statuses (e.g., EXECUTED, SKIPPED, ...)."""
        ...

    @property
    def valid_skip_prefixes(self) -> tuple[str, ...]:
        """Skip reason prefixes that allow commit."""
        ...

    @property
    def blocking_skip_prefixes(self) -> tuple[str, ...]:
        """Skip reason prefixes that block commit."""
        ...

    @property
    def terminal_phases(self) -> tuple[str, ...]:
        """Phases that must complete with PASS outcome (cannot FAIL)."""
        ...


@dataclass(frozen=True)
class TDDSchema:
    """Immutable container for TDD schema data.

    Dual-canon (ADR-025, 2026-05-07; default flip 2026-05-18):
    - ``tdd_phases`` / ``canonical_phases`` = 3-phase v5 (RED, GREEN, COMMIT)
      — default active list returned by the getter.
    - ``legacy_phases`` = 5-phase v4 (PREPARE/RED_ACCEPTANCE/RED_UNIT/GREEN/
      COMMIT) — preserved for audit-log replay; reached via
      ``phases_for("4.0")`` dispatch.

    All tuple fields are frozen to prevent mutation after construction.
    """

    tdd_phases: tuple[str, ...] = field(default_factory=tuple)
    valid_statuses: tuple[str, ...] = field(default_factory=tuple)
    valid_skip_prefixes: tuple[str, ...] = field(default_factory=tuple)
    blocking_skip_prefixes: tuple[str, ...] = field(default_factory=tuple)
    terminal_phases: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "4.0"
    total_phases: int = 5
    canonical_phases: tuple[str, ...] = CANONICAL_PHASES
    legacy_phases: tuple[str, ...] = LEGACY_PHASES

    def phases_for(self, schema_version: str) -> tuple[str, ...]:
        """Return phase list for the requested schema version.

        - ``"5.0"`` → canonical 3-phase (RED, GREEN, COMMIT).
        - any other version (default, ``"4.0"``, ``"3.0"``, etc.) → legacy
          5-phase, preserving prior behaviour.
        """
        if schema_version == "5.0":
            return self.canonical_phases
        return self.legacy_phases


class TDDSchemaLoader(JsonSchemaLoader[TDDSchema]):
    """Loads TDD schema from step-tdd-cycle-schema.json.

    Scaffolding (path-resolution, caching, clear_cache) lives in the shared
    ``JsonSchemaLoader`` base; this subclass supplies only the bundled schema
    filename and the ``_parse_schema`` step (plus the focused extract helpers).

    Usage:
        loader = TDDSchemaLoader()
        schema = loader.load()
        print(schema.tdd_phases)  # ('RED', 'GREEN', 'COMMIT')
    """

    SCHEMA_FILENAME = "step-tdd-cycle-schema.json"

    def _parse_schema(self, raw_data: dict) -> TDDSchema:
        """Parse raw JSON into TDDSchema dataclass.

        Extracts:
        - tdd_phases from tdd_cycle.phase_execution_log[].phase_name
        - valid_statuses from phase_validation_rules.valid_statuses
        - valid_skip_prefixes from phase_validation_rules.skip_validation.valid_prefixes
          where allows_commit=True
        - blocking_skip_prefixes from same where allows_commit=False
        - terminal_phases from phase_validation_rules.terminal_phases.phases
        """
        tdd_phases = self._extract_tdd_phases(raw_data)
        valid_statuses = self._extract_valid_statuses(raw_data)
        valid_skip_prefixes, blocking_skip_prefixes = self._extract_skip_prefixes(
            raw_data
        )
        terminal_phases = self._extract_terminal_phases(raw_data)
        schema_version = raw_data.get("schema_version", "3.0")
        total_phases = raw_data.get("phase_validation_rules", {}).get("total_phases", 7)

        return TDDSchema(
            tdd_phases=tdd_phases,
            valid_statuses=valid_statuses,
            valid_skip_prefixes=valid_skip_prefixes,
            blocking_skip_prefixes=blocking_skip_prefixes,
            terminal_phases=terminal_phases,
            schema_version=schema_version,
            total_phases=total_phases,
        )

    def _extract_tdd_phases(self, raw_data: dict) -> tuple[str, ...]:
        """Extract ordered TDD phase names from schema.

        ADR-025 (2026-05-07; default flip 2026-05-18): the active getter
        returns CANONICAL_PHASES (3-phase v5) by default. The JSON file's
        ``tdd_cycle.phase_execution_log`` still records the legacy 5-phase
        list for audit-log replay; that path is reached via
        ``phases_for("4.0")`` or the ``legacy_phases`` field, NOT the
        default ``tdd_phases`` getter.
        """
        return CANONICAL_PHASES

    def _extract_valid_statuses(self, raw_data: dict) -> tuple[str, ...]:
        """Extract valid phase statuses from schema."""
        statuses = raw_data.get("phase_validation_rules", {}).get("valid_statuses", [])
        return tuple(statuses)

    def _extract_skip_prefixes(
        self, raw_data: dict
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Extract skip prefixes, separating those that allow vs block commit.

        Returns:
            Tuple of (valid_prefixes, blocking_prefixes)
        """
        skip_rules = (
            raw_data.get("phase_validation_rules", {})
            .get("skip_validation", {})
            .get("valid_prefixes", {})
        )

        valid_prefixes = []
        blocking_prefixes = []

        for prefix, config in skip_rules.items():
            if config.get("allows_commit", False):
                valid_prefixes.append(prefix)
            else:
                blocking_prefixes.append(prefix)

        return tuple(valid_prefixes), tuple(blocking_prefixes)

    def _extract_terminal_phases(self, raw_data: dict) -> tuple[str, ...]:
        """Extract terminal phases that must complete with PASS outcome.

        Terminal phases represent successful completion and cannot have FAIL outcome.
        Example: COMMIT phase must always PASS, as FAIL indicates incomplete work.
        """
        terminal_config = raw_data.get("phase_validation_rules", {}).get(
            "terminal_phases", {}
        )
        phases = terminal_config.get("phases", [])
        return tuple(phases)


def resolve_schema_or_default(schema: TDDSchema | None) -> TDDSchema:
    """Return ``schema`` if non-None, else load the default via TDDSchemaLoader.

    Shared helper for constructor injection patterns where ``schema=None``
    means "use the default loader". Extracted 2026-05-03 (RPP L3) — both
    ``Validator.__init__`` and ``ValidationErrorDetector.__init__`` had
    identical 5-line resolution logic.
    """
    if schema is None:
        return TDDSchemaLoader().load()
    return schema
