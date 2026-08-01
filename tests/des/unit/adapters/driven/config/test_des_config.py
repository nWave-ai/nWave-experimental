"""
Unit tests for DESConfig configuration loader.

Tests DESConfig behavior from driving port perspective (public interface):
- Configuration loading from JSON file at .nwave/des-config.json
- Default value fallback when file missing/invalid (defaults to True)
- audit_logging_enabled setting access
- Environment variable override (DES_AUDIT_LOGGING_ENABLED)
- Rigor configuration properties (profile, models, phases, flags)
- Housekeeping configuration properties (enabled, retention, staleness, size)

Test Budget: 20 behaviors x 2 = 40 max. Actual: 20 tests (4 parametrized).
"""

import json
from pathlib import Path

import pytest


class TestDESConfigLoadsValidConfiguration:
    """Test DESConfig loads configuration from valid JSON file."""

    @pytest.mark.parametrize(
        "audit_value,expected",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_loads_audit_logging_enabled_from_config(
        self, tmp_path, audit_value, expected
    ):
        """DESConfig loads audit_logging_enabled from valid JSON config file."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": audit_value}), encoding="utf-8"
        )

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(config_path=config_file)

        assert config.audit_logging_enabled is expected


class TestDESConfigDefaultsToTrue:
    """Test DESConfig defaults to audit_logging_enabled=True."""

    def test_defaults_to_true_when_config_file_missing(self, tmp_path):
        """DESConfig defaults to audit_logging_enabled=True when config file missing."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(config_path=config_file)

        assert config.audit_logging_enabled is True

    @pytest.mark.parametrize(
        "file_content",
        [
            "not valid json {{{",
            json.dumps({"some_other_setting": "value"}),
            b"\xff\xfe not valid utf-8 at all",
        ],
        ids=["invalid_json", "key_absent", "invalid_utf8"],
    )
    def test_defaults_to_true_when_config_unusable(self, tmp_path, file_content):
        """DESConfig defaults to audit_logging_enabled=True when JSON invalid,
        key absent, or the file is not valid UTF-8 (regression: UnicodeDecodeError
        used to propagate uncaught instead of falling back to the documented
        empty-dict default -- techdebt.md
        incomplete-exception-handler-des-config-py-108-115)."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(file_content, bytes):
            config_file.write_bytes(file_content)
        else:
            config_file.write_text(file_content, encoding="utf-8")

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(config_path=config_file)

        assert config.audit_logging_enabled is True


class TestDESConfigUsesNwavePath:
    """Test DESConfig uses .nwave/des-config.json as default path."""

    def test_resolves_config_from_cwd_nwave_directory(self, tmp_path):
        """DESConfig resolves config from cwd/.nwave/des-config.json by default."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": True}), encoding="utf-8"
        )

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(cwd=tmp_path)

        assert config.audit_logging_enabled is True

    def test_does_not_create_config_file_when_missing(self, tmp_path):
        """DESConfig does NOT auto-create config file when missing."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        _ = DESConfig(config_path=config_file)

        assert not config_file.exists()


class TestDESConfigEnvVarOverride:
    """Test DES_AUDIT_LOGGING_ENABLED env var overrides config file."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
        ],
        ids=["true", "1", "yes", "false", "0", "no"],
    )
    def test_env_var_overrides_config_file(
        self, tmp_path, monkeypatch, env_value, expected
    ):
        """DES_AUDIT_LOGGING_ENABLED env var takes priority over config file."""
        # Arrange: config file says False, but env var overrides
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": False}), encoding="utf-8"
        )
        monkeypatch.setenv("DES_AUDIT_LOGGING_ENABLED", env_value)

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(config_path=config_file)

        assert config.audit_logging_enabled is expected

    def test_env_var_absent_falls_through_to_config(self, tmp_path, monkeypatch):
        """When env var is absent, config file value is used."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": True}), encoding="utf-8"
        )
        monkeypatch.delenv("DES_AUDIT_LOGGING_ENABLED", raising=False)

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(config_path=config_file)

        assert config.audit_logging_enabled is True


class TestDESConfigRigorDefaults:
    """Test DESConfig rigor properties default to 'standard' profile values."""

    def test_no_rigor_key_defaults_to_standard(self, tmp_path):
        """All rigor properties return standard defaults when no rigor key in config."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"audit_logging_enabled": True}), encoding="utf-8"
        )

        from des.adapters.driven.config.des_config import DESConfig

        # Isolate from real ~/.nwave/global-config.json
        nonexistent_global = tmp_path / "no-global-config.json"
        cfg = DESConfig(config_path=config_file, global_config_path=nonexistent_global)

        assert cfg.rigor_profile == "standard"
        assert cfg.rigor_agent_model == "sonnet"
        assert cfg.rigor_reviewer_model == "haiku"
        assert cfg.rigor_review_enabled is True
        assert cfg.rigor_double_review is False
        assert cfg.rigor_refactor_pass is True
        # F6 sweep (2026-05-18): default rigor_tdd_phases follows ADR-025
        # canonical (RED/GREEN/COMMIT). Legacy 5-phase only via explicit
        # rigor.tdd_phases override (see TestDESConfigRigorExplicitProfiles).
        assert cfg.rigor_tdd_phases == ("RED", "GREEN", "COMMIT")

    def test_missing_config_file_defaults_to_standard(self, tmp_path):
        """All rigor properties return standard defaults when config file missing."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        # Isolate from real ~/.nwave/global-config.json
        nonexistent_global = tmp_path / "no-global-config.json"
        cfg = DESConfig(config_path=config_file, global_config_path=nonexistent_global)

        assert cfg.rigor_profile == "standard"
        assert cfg.rigor_agent_model == "sonnet"
        # F6 sweep (2026-05-18): default rigor_tdd_phases follows ADR-025
        # canonical (RED/GREEN/COMMIT).
        assert cfg.rigor_tdd_phases == ("RED", "GREEN", "COMMIT")

    def test_partial_rigor_fills_missing_with_standard_defaults(self, tmp_path):
        """Missing rigor sub-keys get standard defaults."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"rigor": {"profile": "custom"}}), encoding="utf-8"
        )

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.rigor_profile == "custom"
        assert cfg.rigor_agent_model == "sonnet"
        assert cfg.rigor_reviewer_model == "haiku"
        assert cfg.rigor_review_enabled is True


class TestDESConfigRigorExplicitProfiles:
    """Test DESConfig rigor properties with explicit profile configurations."""

    def test_lean_profile_values(self, tmp_path):
        """Lean profile config returns lean values for all rigor properties."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "rigor": {
                        "profile": "lean",
                        "agent_model": "haiku",
                        "reviewer_model": "haiku",
                        "tdd_phases": ["GREEN", "COMMIT"],
                        "review_enabled": False,
                        "double_review": False,
                        "refactor_pass": False,
                    }
                }
            ),
            encoding="utf-8",
        )

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.rigor_profile == "lean"
        assert cfg.rigor_agent_model == "haiku"
        assert cfg.rigor_reviewer_model == "haiku"
        assert cfg.rigor_tdd_phases == ("GREEN", "COMMIT")
        assert cfg.rigor_review_enabled is False
        assert cfg.rigor_double_review is False
        assert cfg.rigor_refactor_pass is False

    def test_exhaustive_profile_values(self, tmp_path):
        """Exhaustive profile config returns exhaustive values for all rigor properties."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "rigor": {
                        "profile": "exhaustive",
                        "agent_model": "opus",
                        "reviewer_model": "opus",
                        "tdd_phases": [
                            "PREPARE",
                            "RED_ACCEPTANCE",
                            "RED_UNIT",
                            "GREEN",
                            "COMMIT",
                        ],
                        "review_enabled": True,
                        "double_review": True,
                        "refactor_pass": True,
                    }
                }
            ),
            encoding="utf-8",
        )

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.rigor_profile == "exhaustive"
        assert cfg.rigor_agent_model == "opus"
        assert cfg.rigor_reviewer_model == "opus"
        assert cfg.rigor_tdd_phases == (
            "PREPARE",
            "RED_ACCEPTANCE",
            "RED_UNIT",
            "GREEN",
            "COMMIT",
        )
        assert cfg.rigor_review_enabled is True
        assert cfg.rigor_double_review is True
        assert cfg.rigor_refactor_pass is True

    def test_rigor_tdd_phases_returns_tuple_not_list(self, tmp_path):
        """rigor_tdd_phases always returns a tuple even when config has a list."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"rigor": {"tdd_phases": ["GREEN", "COMMIT"]}}),
            encoding="utf-8",
        )

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert isinstance(cfg.rigor_tdd_phases, tuple)
        assert cfg.rigor_tdd_phases == ("GREEN", "COMMIT")


class TestDESConfigHousekeepingDefaults:
    """Test DESConfig housekeeping properties return correct defaults when config absent."""

    def test_housekeeping_enabled_defaults_to_true_when_config_missing(self, tmp_path):
        """housekeeping_enabled returns True when no config file present."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.housekeeping_enabled is True

    def test_housekeeping_audit_retention_days_defaults_to_7(self, tmp_path):
        """housekeeping_audit_retention_days returns 7 when no housekeeping key in config."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.housekeeping_audit_retention_days == 7

    def test_housekeeping_signal_staleness_hours_defaults_to_4(self, tmp_path):
        """housekeeping_signal_staleness_hours returns 4 when no housekeeping key in config."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.housekeeping_signal_staleness_hours == 4

    def test_housekeeping_skill_log_max_bytes_defaults_to_1mb(self, tmp_path):
        """housekeeping_skill_log_max_bytes returns 1_048_576 when no housekeeping key in config."""
        config_file = tmp_path / ".nwave" / "des-config.json"

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        assert cfg.housekeeping_skill_log_max_bytes == 1_048_576


class TestDESConfigHousekeepingReadsCustomValues:
    """Test DESConfig housekeeping properties read from 'housekeeping' key in config."""

    @pytest.mark.parametrize(
        "field,config_value,expected",
        [
            ("enabled", False, False),
            ("audit_retention_days", 14, 14),
            ("signal_staleness_hours", 8, 8),
            ("skill_log_max_bytes", 2097152, 2097152),
        ],
        ids=[
            "enabled",
            "audit_retention_days",
            "signal_staleness_hours",
            "skill_log_max_bytes",
        ],
    )
    def test_reads_custom_housekeeping_values_from_config(
        self, tmp_path, field, config_value, expected
    ):
        """DESConfig reads each housekeeping property from 'housekeeping' config key."""
        config_file = tmp_path / ".nwave" / "des-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps({"housekeeping": {field: config_value}}), encoding="utf-8"
        )

        from des.adapters.driven.config.des_config import DESConfig

        cfg = DESConfig(config_path=config_file)

        prop_name = f"housekeeping_{field}"
        assert getattr(cfg, prop_name) == expected


class TestDESConfigEnabledForRepoRelativeCwd:
    """Regression AT -- `DESConfig._nearest_marker`'s ascend-loop never fires
    when `cwd` is passed as a RELATIVE path (`Path(".")`), the shape produced
    by the single most natural real-world CLI invocation (`--repo .` /
    `--repo-dir .`).

    Site under test (`src/des/adapters/driven/config/des_config.py`,
    `DESConfig._nearest_marker`):

        current = self._config_path.parent.parent
        while current not in (home, current.parent):
            ...
            current = current.parent

    `self._config_path` is built from the constructor's `cwd` argument
    WITHOUT ever calling `.resolve()` (`__init__`: `config_path =
    effective_cwd / ".nwave" / "des-config.json"`). `Path(".").parent ==
    Path(".")` -- pathlib's own behaviour for the trivial relative path --
    so for `cwd=Path(".")` the ascend-loop's exit condition (`current ==
    current.parent`) is already true on the FIRST check: `candidate.exists()`
    never runs even once, and `_nearest_marker` returns `None` even when
    `.nwave/local-config.json` genuinely exists at the resolved repo root.
    `enabled_for_repo` then silently returns `None` instead of the marker's
    declared value, so `resolve_activation(None, "opt-in")` treats a
    genuinely-activated repo as inactive.

    Reproduced live (2026-07-30): `DESConfig(cwd=Path(".")).enabled_for_repo`
    -> `None` in a directory with a real `.nwave/local-config.json` declaring
    `enabled_for_repo: true`; `DESConfig(cwd=Path(".").resolve())
    .enabled_for_repo` -> `True`, same directory, only difference is
    resolving to absolute first. End-to-end: `des commit --repo-dir .` /
    `des commit-slice --repo .` land commits with NO attribution trailer even
    when attribution is enabled and the repo is genuinely activated.

    RED before the fix: both tests below observe `enabled_for_repo is None`
    against a marker that declares `True`. GREEN after: `_nearest_marker`
    (or the constructor) resolves `cwd`/`current` to absolute before the
    ascend-loop runs, matching what an absolute `cwd` already returns today.
    """

    @staticmethod
    def _write_local_config(root: Path, *, enabled_for_repo: bool) -> None:
        config_dir = root / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "local-config.json").write_text(
            json.dumps({"enabled_for_repo": enabled_for_repo}), encoding="utf-8"
        )

    @pytest.mark.negative_at
    def test_enabled_for_repo_resolves_relative_cwd_to_absolute(
        self, tmp_path, monkeypatch
    ):
        """`DESConfig(cwd=Path("."))` (a RELATIVE cwd, exactly what `--repo .`
        produces) must find the SAME marker an absolute `cwd` finds -- the
        trivial `Path(".").parent == Path(".")` self-loop must not
        short-circuit the ascend-loop before it ever inspects the repo root."""
        self._write_local_config(tmp_path, enabled_for_repo=True)
        monkeypatch.chdir(tmp_path)

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(cwd=Path())

        assert config.enabled_for_repo is True, (
            "DESConfig._nearest_marker's ascend-loop (des_config.py, "
            "`current = self._config_path.parent.parent` / `while current "
            "not in (home, current.parent)`) must resolve a RELATIVE cwd to "
            "absolute before walking up -- Path('.').parent == Path('.') "
            "self-loops the exit check on the very first iteration for the "
            "un-resolved relative case, so candidate.exists() never runs "
            "even though .nwave/local-config.json genuinely declares "
            "enabled_for_repo=True at the resolved repo root. Observed "
            f"enabled_for_repo={config.enabled_for_repo!r}. Fix: resolve "
            "cwd/current to absolute early in _nearest_marker (or the "
            "constructor) before the ascend-loop runs."
        )

    def test_enabled_for_repo_resolves_relative_subdirectory_cwd_walk_up(
        self, tmp_path, monkeypatch
    ):
        """A relative `cwd` pointing at a SUBDIRECTORY (`Path("sub")`) with
        the marker one level up must still be found by the ascend-loop
        itself -- not just the trivial `Path(".")` case above."""
        project_root = tmp_path / "project_root"
        subdir = project_root / "sub"
        subdir.mkdir(parents=True)
        self._write_local_config(project_root, enabled_for_repo=True)
        monkeypatch.chdir(project_root)

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(cwd=Path("sub"))

        assert config.enabled_for_repo is True, (
            "DESConfig._nearest_marker's ascend-loop must walk up from a "
            "RELATIVE subdirectory cwd (Path('sub')) to find "
            ".nwave/local-config.json one level up at the resolved project "
            "root, exactly as it does for an absolute subdirectory cwd. "
            f"Observed enabled_for_repo={config.enabled_for_repo!r}, "
            "expected True (the project root's declared marker value)."
        )

    def test_enabled_for_repo_absolute_cwd_still_works(self, tmp_path, monkeypatch):
        """Non-regression pin: an ABSOLUTE `cwd` must keep resolving exactly
        as it does today -- unaffected by the relative-cwd fix, proving the
        fix does not merely shift the bug onto the already-working case."""
        self._write_local_config(tmp_path, enabled_for_repo=True)
        monkeypatch.chdir(tmp_path)

        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(cwd=tmp_path.resolve())

        assert config.enabled_for_repo is True
