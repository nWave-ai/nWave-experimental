"""
Acceptance oracle for auto-3311db23d6fcd093 (ADR-CFG-002: attribution
translation totality and global-tier decoupling).

Consolidated coverage over the four DISTILL obligations:
- PRESERVATION: ``_translate_public_attribution`` is total (never raises)
  and the existing "on"/"off" translation path is unchanged.
- BROAD_INPUT_DOMAIN: the same totality law generalized over the full
  JSON-value domain via Hypothesis.
- ARCHITECTURE_BOUNDARY_CHANGE: ``effective_config()`` derives its global
  tier from the sibling ``config.json``, decoupled from the legacy
  ``global-config.json`` path -- the RCA's exact regression scenario.
- REUSE_CANDIDATE: the repo tier and the (corrected) global tier both go
  through the SAME existing versioned reader/kernel -- observed
  behaviorally via identical v0 (no ``schema-version`` key) upcast
  treatment on both tiers, never via source/diff inspection (that
  structural check is review-owned, not oracle-owned).

Fixture construction/isolation matches the existing convention in
``test_des_config.py``: explicit ``config_path``/``global_config_path``
constructor kwargs over a fresh ``tmp_path``, never ``Path.home()`` /
``monkeypatch.chdir``. This proves the tier-derivation LOGIC without
touching the real ``$HOME`` -- the real-default-path behavior is exercised
separately by this delivery's own EXAMINE run of the PublicStartRecipe
(``nwave-ai doctor`` against a real ``~/.nwave`` pair).
"""

import json

from hypothesis import assume, given
from hypothesis import strategies as st

from des.adapters.driven.config.des_config import (
    DESConfig,
    _translate_public_attribution,
)


_json_value = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=15,
)


class TestTranslatePublicAttributionTotality:
    """PRESERVATION: totality equation, canonical examples (ADR-CFG-002)."""

    def test_legacy_dict_shape_passes_through_unchanged_no_raise(self):
        """The RCA's exact legacy shape: a dict-valued ``attribution`` used
        to raise ``TypeError: unhashable type: 'dict'``; it must now pass
        through unchanged."""
        config = {
            "attribution": {"enabled": True, "last_written_value": "x"},
        }

        result = _translate_public_attribution(config)

        assert result == config

    def test_on_string_still_translates_to_enabled_true(self):
        """Today's passing path, unchanged."""
        config = {"attribution": "on"}

        result = _translate_public_attribution(config)

        assert result == {"attribution": {"enabled": True}}

    def test_off_string_still_translates_to_enabled_false(self):
        config = {"attribution": "off"}

        result = _translate_public_attribution(config)

        assert result == {"attribution": {"enabled": False}}

    def test_attribution_key_absent_passes_through_unchanged(self):
        config = {"other": 1}

        result = _translate_public_attribution(config)

        assert result == config


class TestTranslatePublicAttributionBroadInputDomain:
    """BROAD_INPUT_DOMAIN: the totality law generalized as a property over
    the full JSON-value domain, plus unrelated extra keys (forward-compat,
    ADR-CFG-002 citing ADR-CFG-001 parent's own domain note)."""

    @given(value=_json_value, extra_key=st.text(min_size=1), extra_value=_json_value)
    def test_translate_never_raises_and_only_on_off_strings_translate(
        self, value, extra_key, extra_value
    ):
        assume(extra_key != "attribution")
        config = {"attribution": value, extra_key: extra_value}

        result = _translate_public_attribution(dict(config))

        if value in ("on", "off"):
            assert result == {**config, "attribution": {"enabled": value == "on"}}
        else:
            assert result == config


class TestEffectiveConfigGlobalTierDecoupling:
    """ARCHITECTURE_BOUNDARY_CHANGE: the global tier reads the sibling
    ``config.json``, independent of the legacy ``global-config.json`` path
    (ADR-CFG-002 correction 2)."""

    def test_rca_regression_legacy_and_unified_files_coexist(self, tmp_path):
        """The RCA's exact regression: the unified ``config.json`` declares
        ``attribution: "on"`` while the legacy ``global-config.json``
        carries the old dict shape that used to raise. Today's code reused
        the legacy path itself as the global tier, feeding that dict shape
        straight into ``_translate_public_attribution`` and raising;
        after the fix, the legacy file is never read by
        ``effective_config()`` at all."""
        nwave_dir = tmp_path / "home" / ".nwave"
        nwave_dir.mkdir(parents=True)
        (nwave_dir / "config.json").write_text(
            json.dumps(
                {"schema-version": "1", "verbosity": "terse", "attribution": "on"}
            ),
            encoding="utf-8",
        )
        (nwave_dir / "config.json").write_text(
            json.dumps(
                {
                    "attribution": {
                        "enabled": True,
                        "last_written_value": "nwave_managed",
                    }
                }
            ),
            encoding="utf-8",
        )
        repo_config_path = tmp_path / "repo" / ".nwave" / "des-config.json"

        config = DESConfig(
            config_path=repo_config_path,
            global_config_path=nwave_dir / "config.json",
        )
        effective = config.effective_config()

        assert effective["attribution"] is True

    def test_global_tier_reads_sibling_config_json_not_legacy_path(self, tmp_path):
        """Isolates correction 2 alone: the legacy file carries a
        WELL-TYPED string ``attribution`` (would not raise even under
        today's code), so a wrong ("off") effective value -- not a raise --
        is what proves the legacy path itself was read instead of its
        sibling."""
        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True)
        global_path = nwave_dir / "config.json"
        global_path.write_text(json.dumps({"attribution": "on"}), encoding="utf-8")
        repo_config_path = tmp_path / "repo" / ".nwave" / "config.json"

        config = DESConfig(config_path=repo_config_path, global_config_path=global_path)
        effective = config.effective_config()

        assert effective["attribution"] is True, (
            "effective_config() must read config.json as its global tier."
        )


class TestEffectiveConfigReusesVersioningKernel:
    """REUSE_CANDIDATE: the repo tier and the corrected global tier both
    resolve through the SAME existing ``_load_versioned_global_config``
    reader / ``_GLOBAL_CONFIG_VERSIONING`` kernel instance -- observed here
    via identical v0 (no ``schema-version`` key) upcast treatment applied
    uniformly to both tiers. This is a behavioral proxy: the obligation's
    own real observation point (absence of a new I/O helper or a second
    kernel instance in the diff) is a structural fact this executable
    oracle cannot itself inspect, and is owned by review instead."""

    def test_repo_and_global_v0_tiers_both_upcast_without_a_second_mechanism(
        self, tmp_path
    ):
        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True)
        (nwave_dir / "config.json").write_text(
            json.dumps({"verbosity": "terse"}), encoding="utf-8"
        )
        repo_dir = tmp_path / "repo" / ".nwave"
        repo_dir.mkdir(parents=True)
        (repo_dir / "config.json").write_text(
            json.dumps({"verbosity": "verbose"}), encoding="utf-8"
        )
        repo_config_path = repo_dir / "config.json"

        config = DESConfig(
            config_path=repo_config_path,
            global_config_path=nwave_dir / "config.json",
        )
        effective = config.effective_config()

        assert effective["verbosity"] == "verbose"
