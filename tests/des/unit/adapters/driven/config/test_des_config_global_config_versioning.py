"""Unit tests: DESConfig's ~/.nwave/global-config.json read through the
artifact-versioning kernel (F-ARTIFACT-VERSIONING-UPCASTING, slice 1).

Ale's correction (2026-08-20): "v0" is the EXACT shape of the current PUBLIC
nWave release, not an abstract placeholder -- the real migration this kernel
must serve is an existing user (e.g. Attila, updating every few days) going
from what they have on disk today to this trunk's shape. So the "legacy"
fixtures below are NOT invented; they are copied verbatim from the public
repo's own documentation of its real on-disk shape:

  Source: https://github.com/nWave-ai/nWave/blob/v3.21.0/docs/reference/global-config.md
  Repo: nWave-ai/nWave (public). Tag: v3.21.0 == latest PyPI `nwave-ai`
  release (verified via `curl https://pypi.org/pypi/nwave-ai/json`). Commit:
  1d0f13c79e9383c96a01b1a63e9a5bfd616c53d9 (tag dereferenced via
  `gh api repos/nWave-ai/nWave/git/refs/tags/v3.21.0`).

Both fixtures are that doc's own example JSON blocks, unmodified. Neither
contains a "schema-version" key (confirmed: the doc's full key inventory --
`activation`, `rigor`, `documentation`, `audit_logging_enabled`,
`audit_log_dir`, `update_check` -- has no version field at all), and neither
contains "attribution" or "blast_radius" (trunk-only keys added after
v3.21.0; a real v0 file never carries them, so their absent-key defaults
are exercised here too). Full census + property-by-property diff against
`v3.21.0`'s `des_config.py`: `docs/analysis/2026-08-20-artifact-versioning-census.md`.
"""

import json

from des.adapters.driven.config.des_config import (
    _GLOBAL_CONFIG_ARTIFACT_TYPE,
    _GLOBAL_CONFIG_VERSIONING,
    DESConfig,
)
from des.domain.artifact_versioning import SCHEMA_VERSION_KEY


#: v3.21.0 docs/reference/global-config.md, "Complete minimal example" block,
#: verbatim. No schema-version, no activation, no attribution key.
REAL_V0_MINIMAL_EXAMPLE = {
    "rigor": {"profile": "standard"},
    "documentation": {"density": "lean", "expansion_prompt": "ask"},
    "audit_logging_enabled": True,
    "update_check": {"frequency": "weekly"},
}

#: v3.21.0 docs/reference/global-config.md, `activation` section's own
#: example block, verbatim.
REAL_V0_ACTIVATION_EXAMPLE = {"activation": {"mode": "opt-in"}}


def test_effective_config_sources_follow_valid_fields_without_writing(tmp_path):
    global_path = tmp_path / "global.json"
    project_path = tmp_path / ".nwave" / "config.json"
    project_path.parent.mkdir()
    global_path.write_text(
        json.dumps({"enabled": True, "verbosity": "verbose", "attribution": "on"}),
        encoding="utf-8",
    )
    project_path.write_text(
        json.dumps({"enabled": False, "verbosity": 4, "attribution": "off"}),
        encoding="utf-8",
    )
    original_global = global_path.read_bytes()
    original_project = project_path.read_bytes()

    config = DESConfig(config_path=project_path, global_config_path=global_path)
    values, sources = config.effective_config_with_sources()

    assert values == {
        "enabled": False,
        "verbosity": "verbose",
        "attribution": False,
        "documents": {},
    }
    assert sources == {
        "enabled": "project",
        "verbosity": "global",
        "attribution": "project",
        "documents": "default",
    }
    assert config.effective_config() == values
    assert global_path.read_bytes() == original_global
    assert project_path.read_bytes() == original_project


class TestLegacyGlobalConfigIsUpcast:
    def test_real_v0_minimal_example_still_reads_correct_defaults(self, tmp_path):
        """The real v3.21.0 minimal file carries no `attribution` key -- the
        trunk-only property must still resolve to its documented safe
        default (False) after the kernel upcast, not crash or misread."""
        global_config = tmp_path / "config.json"
        global_config.write_text(json.dumps(REAL_V0_MINIMAL_EXAMPLE), encoding="utf-8")
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        assert config.attribution_enabled is False

    def test_real_v0_activation_example_still_reads_its_declared_mode(self, tmp_path):
        """The real v3.21.0 `activation` example reads identically post-upcast
        -- `activation.mode` is one of the few keys BOTH v3.21.0 and this
        trunk read the same way, so this is the positive (non-default) case."""
        global_config = tmp_path / "config.json"
        global_config.write_text(
            json.dumps(REAL_V0_ACTIVATION_EXAMPLE), encoding="utf-8"
        )
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        assert config.activation_mode == "opt-in"

    def test_real_v0_minimal_example_gets_current_schema_version_stamped(
        self, tmp_path
    ):
        global_config = tmp_path / "config.json"
        global_config.write_text(json.dumps(REAL_V0_MINIMAL_EXAMPLE), encoding="utf-8")
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        assert config._global_config_data[
            SCHEMA_VERSION_KEY
        ] == _GLOBAL_CONFIG_VERSIONING.current_version(_GLOBAL_CONFIG_ARTIFACT_TYPE)

    def test_real_v0_minimal_example_keys_survive_the_upcast_unchanged(self, tmp_path):
        """v1's only change is introducing schema-version -- every key a real
        v3.21.0 install wrote (even ones this trunk no longer reads, like
        `rigor`/`update_check`) must still be present afterwards, verbatim."""
        global_config = tmp_path / "config.json"
        global_config.write_text(json.dumps(REAL_V0_MINIMAL_EXAMPLE), encoding="utf-8")
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        for key, value in REAL_V0_MINIMAL_EXAMPLE.items():
            assert config._global_config_data[key] == value


class TestGlobalConfigUpcastIsIdempotent:
    def test_already_current_real_shaped_config_is_read_unchanged(self, tmp_path):
        current_version = _GLOBAL_CONFIG_VERSIONING.current_version(
            _GLOBAL_CONFIG_ARTIFACT_TYPE
        )
        already_current = {
            **REAL_V0_MINIMAL_EXAMPLE,
            SCHEMA_VERSION_KEY: current_version,
        }
        global_config = tmp_path / "config.json"
        global_config.write_text(json.dumps(already_current), encoding="utf-8")
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        assert config._global_config_data == already_current


class TestMissingGlobalConfigIsNotFabricated:
    def test_missing_global_config_file_stays_empty_no_stamped_version(self, tmp_path):
        global_config = tmp_path / "does-not-exist" / "config.json"
        project_config = tmp_path / ".nwave" / "config.json"

        config = DESConfig(config_path=project_config, global_config_path=global_config)

        assert config._global_config_data == {}
