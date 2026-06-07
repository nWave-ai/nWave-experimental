"""Roadmap Schema Loader - Single Source of Truth for Roadmap Structure.

Loads roadmap validation rules from nWave/templates/roadmap-schema.json.
Provides cached access via frozen dataclass.

Mirrors tdd_schema.py pattern: frozen dataclass, lazy path resolution,
singleton loader with WSL-safe path handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from des.domain.json_schema_loader import JsonSchemaLoader


@dataclass(frozen=True)
class RoadmapSchema:
    """Immutable container for roadmap schema data."""

    schema_version: str = "1.0"
    required_roadmap_fields: tuple[str, ...] = field(default_factory=tuple)
    required_phase_fields: tuple[str, ...] = field(default_factory=tuple)
    required_step_fields: tuple[str, ...] = field(default_factory=tuple)
    phase_id_pattern: str = r"^\d{2}$"
    step_id_pattern: str = r"^\d{2}-\d{2}$"
    max_criteria_words: int = 30
    max_criteria_per_step: int = 5
    max_step_name_words: int = 10
    max_description_words: int = 50
    max_decomposition_ratio: float = 2.5
    valid_agents: tuple[str, ...] = field(default_factory=tuple)
    valid_deps_strategies: tuple[str, ...] = field(default_factory=tuple)
    valid_statuses: tuple[str, ...] = field(default_factory=tuple)


class RoadmapSchemaLoader(JsonSchemaLoader[RoadmapSchema]):
    """Loads schema from roadmap-schema.json. WSL-safe path resolution.

    Scaffolding (path-resolution, caching, clear_cache) lives in the shared
    ``JsonSchemaLoader`` base; this subclass supplies only the bundled schema
    filename and the ``_parse_schema`` step.
    """

    SCHEMA_FILENAME = "roadmap-schema.json"

    def _parse_schema(self, raw: dict) -> RoadmapSchema:
        required = raw.get("required_fields", {})
        constraints = raw.get("constraints", {})
        id_patterns = raw.get("id_patterns", {})

        return RoadmapSchema(
            schema_version=raw.get("schema_version", "1.0"),
            required_roadmap_fields=tuple(required.get("roadmap", [])),
            required_phase_fields=tuple(required.get("phase", [])),
            required_step_fields=tuple(required.get("step", [])),
            phase_id_pattern=id_patterns.get("phase_id", r"^\d{2}$"),
            step_id_pattern=id_patterns.get("step_id", r"^\d{2}-\d{2}$"),
            max_criteria_words=constraints.get("max_criteria_words", 30),
            max_criteria_per_step=constraints.get("max_criteria_per_step", 5),
            max_step_name_words=constraints.get("max_step_name_words", 10),
            max_description_words=constraints.get("max_description_words", 50),
            max_decomposition_ratio=constraints.get("max_decomposition_ratio", 2.5),
            valid_agents=tuple(raw.get("valid_agents", [])),
            valid_deps_strategies=tuple(raw.get("valid_deps_strategies", [])),
            valid_statuses=tuple(raw.get("valid_validation_statuses", [])),
        )
