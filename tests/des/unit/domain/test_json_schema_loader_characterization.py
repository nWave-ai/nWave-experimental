"""Characterization tests pinning schema-loader scaffolding behavior.

Added to prove a behavior-preserving extraction of the duplicated
JSON-schema-loader scaffolding (path-resolution, caching, clear_cache)
shared between RoadmapSchemaLoader and TDDSchemaLoader into a common
``JsonSchemaLoader`` base. These tests assert the CURRENT (HEAD) behavior:

- both loaders resolve their bundled schema under nWave/templates/ in the
  dev/WSL repo context, with the correct filename per loader;
- the default-constructed loader loads the same schema content as before;
- the caching contract (load() returns the same cached instance until
  clear_cache()) holds for both loaders.

The fragile 3-context path-resolution moves VERBATIM during the extraction;
these tests are the parity net for that move.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.roadmap_schema import RoadmapSchema, RoadmapSchemaLoader
from des.domain.tdd_schema import TDDSchema, TDDSchemaLoader


class TestRoadmapLoaderCharacterization:
    def test_default_path_resolves_to_bundled_roadmap_schema(self):
        loader = RoadmapSchemaLoader()
        assert loader.schema_path.name == "roadmap-schema.json"
        assert loader.schema_path.parent.name == "templates"
        assert loader.schema_path.parent.parent.name == "nWave"
        assert loader.schema_path.exists()

    def test_load_returns_parsed_roadmap_schema(self):
        schema = RoadmapSchemaLoader().load()
        assert isinstance(schema, RoadmapSchema)
        assert schema.schema_version == "1.0"
        assert schema.required_roadmap_fields == (
            "project_id",
            "created_at",
            "total_steps",
            "phases",
        )
        assert schema.required_phase_fields == ("id", "name", "steps")
        assert schema.required_step_fields == ("id", "name", "criteria")
        assert schema.max_decomposition_ratio == 2.5
        assert schema.valid_deps_strategies == ("sequential", "parallel")
        assert schema.valid_statuses == ("pending", "approved", "rejected")

    def test_caching_and_clear_cache_contract(self):
        loader = RoadmapSchemaLoader()
        first = loader.load()
        assert loader.load() is first
        loader.clear_cache()
        second = loader.load()
        assert second is not first
        assert second == first

    def test_explicit_path_overrides_default_resolution(self, tmp_path: Path):
        custom = tmp_path / "roadmap-schema.json"
        custom.write_text("{}", encoding="utf-8")
        loader = RoadmapSchemaLoader(schema_path=custom)
        assert loader.schema_path == custom


class TestTddLoaderCharacterization:
    def test_default_path_resolves_to_bundled_tdd_schema(self):
        loader = TDDSchemaLoader()
        assert loader.schema_path.name == "step-tdd-cycle-schema.json"
        assert loader.schema_path.parent.name == "templates"
        assert loader.schema_path.parent.parent.name == "nWave"
        assert loader.schema_path.exists()

    def test_load_returns_parsed_tdd_schema(self):
        schema = TDDSchemaLoader().load()
        assert isinstance(schema, TDDSchema)
        assert schema.tdd_phases == ("RED", "GREEN", "COMMIT")
        assert schema.valid_statuses == (
            "NOT_EXECUTED",
            "IN_PROGRESS",
            "EXECUTED",
            "SKIPPED",
        )
        assert schema.valid_skip_prefixes == (
            "BLOCKED_BY_DEPENDENCY:",
            "NOT_APPLICABLE:",
            "APPROVED_SKIP:",
            "CHECKPOINT_PENDING:",
        )
        assert schema.blocking_skip_prefixes == ("DEFERRED:",)
        assert schema.terminal_phases == ("COMMIT",)
        assert schema.schema_version == "4.0"
        assert schema.total_phases == 5

    def test_caching_and_clear_cache_contract(self):
        loader = TDDSchemaLoader()
        first = loader.load()
        assert loader.load() is first
        loader.clear_cache()
        second = loader.load()
        assert second is not first
        assert second == first

    def test_explicit_path_overrides_default_resolution(self, tmp_path: Path):
        custom = tmp_path / "step-tdd-cycle-schema.json"
        loader = TDDSchemaLoader(schema_path=custom)
        assert loader.schema_path == custom
