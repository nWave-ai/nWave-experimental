"""Composition root for f-design-wave-migration slice-02 Gherkin ATs.

TWO driving surfaces (honest shapes, mirroring the original plain-pytest AT-3/4
vs AT-6 split):
  * AT-3 / AT-4 — the filesystem read of the REAL shipped nw-distill skill
    (Mandate-13 prose-surface case). Row 7c carries the total-feature AT-volume
    soft-gate; asserted on DISCRIMINATING multi-word phrases windowed around the
    ``/nw-discuss`` anchor (the only place in the skill proposing the split).
  * AT-6 — the REAL ``DESConfig`` port (a production config port — the one
    permitted ``des.adapters.*`` import, exactly as the original AT-6 drove it).
    Instantiate it against a temp config dir and read the NEW
    ``rigor_feature_total_at_advisory_threshold`` @property; the distinct-locus
    (C3 / DD-3) is witnessed at the PORT.

GREEN-not-active-RED: format conversion of PASSING behaviour — row 7c + the
DESConfig @property already ship. Each oracle stays GENUINE (mutation-verified):
perturbing row 7c's prose reds AT-3/4; removing/renaming the @property or
collapsing it onto carpaccio_slice_max reds AT-6.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.adapters.driven.config.des_config import DESConfig

from .._skill_source import read_distill
from .domain_types_design_wave_migration import (
    NW_DISCUSS_WAVE,
    THRESHOLD_KEY,
)


class TotalAtAdvisoryComposition:
    """SUT = the shipped nw-distill skill (AT-3/4) + the REAL DESConfig port
    (AT-6), each driven through its own surface."""

    def __init__(self) -> None:
        self._distill: str = ""
        self._cfg: DESConfig | None = None
        self._threshold: int | None = None

    # --- When: prose surface (AT-3 / AT-4) ---------------------------------

    def when_the_shipped_distill_skill_is_read(self) -> None:
        """Drive the prose port: read the REAL shipped nw-distill skill."""
        self._distill = read_distill()

    def _row_7c_window(self) -> str:
        """Prose window around row 7c's total-AT advisory (±700 chars).

        Row 7c is the ONLY place in nw-distill proposing /nw-discuss to split a
        feature whose total AT count is over the advisory threshold; anchoring on
        that wave name scopes the assertions to row 7c's own prose.
        """
        idx = self._distill.find(NW_DISCUSS_WAVE)
        if idx == -1:
            return ""
        return self._distill[max(0, idx - 700) : idx + 700]

    # --- When: DESConfig port surface (AT-6) -------------------------------

    def when_a_config_carries_threshold_in_rigor(
        self, tmp_path: Path, sentinel: int
    ) -> None:
        """Drive the REAL DESConfig port: write a sentinel into the rigor block
        of a temp des-config.json and instantiate DESConfig against it."""
        config_dir = tmp_path / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "des-config.json").write_text(
            json.dumps({"rigor": {THRESHOLD_KEY: sentinel}}),
            encoding="utf-8",
        )
        self._cfg = DESConfig(cwd=tmp_path)

    def when_a_config_carries_threshold_and_decoy_slice_max(
        self, tmp_path: Path, sentinel: int, decoy: int
    ) -> None:
        """Drive the REAL DESConfig port with BOTH the rigor threshold key AND a
        decoy carpaccio_slice_max, so the distinct-locus oracle can prove the two
        thresholds never collapse onto one knob (C3 / DD-3)."""
        config_dir = tmp_path / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "des-config.json").write_text(
            json.dumps(
                {"rigor": {THRESHOLD_KEY: sentinel}, "carpaccio_slice_max": decoy}
            ),
            encoding="utf-8",
        )
        self._cfg = DESConfig(cwd=tmp_path)

    def when_no_rigor_config_is_present(self, tmp_path: Path) -> None:
        """Drive the REAL DESConfig port against an empty config dir (no
        project/global rigor config) so the @property's own default supplies the
        threshold (DD-3 fallback)."""
        self._cfg = DESConfig(
            config_path=tmp_path / "absent-des-config.json",
            global_config_path=tmp_path / "absent-global-config.json",
        )

    # --- Then: prose surface (AT-3 / AT-4) ---------------------------------

    def then_total_at_trigger_exists(self) -> None:
        """AT-3: row 7c exists — nw-distill carries a §Prior Wave Reading advisory
        that PROPOSEs /nw-discuss when the total-feature AT count is over the
        advisory threshold (brief §2 Total-AT trigger + §3b trigger (b))."""
        assert NW_DISCUSS_WAVE in self._distill, (
            "nw-distill must carry row 7c: a §Prior Wave Reading sub-step that, "
            "when the total-feature AT count is over the advisory threshold, "
            "PROPOSEs /nw-discuss (elephant-carpaccio split) — brief §2 Total-AT "
            "trigger + §3b trigger (b). /nw-discuss appears nowhere else."
        )

    def then_advisory_keyed_on_total_at_volume(self) -> None:
        """AT-3: row 7c's advisory is keyed on the TOTAL-feature AT volume
        crossing the advisory threshold (brief §3b Observe/Compare)."""
        window = self._row_7c_window().lower()
        assert "total" in window, (
            "row 7c must key its advisory off the TOTAL-feature AT volume "
            "(brief §3b Observe) — distinct from the per-slice carpaccio ceiling"
        )
        assert THRESHOLD_KEY in window or "advisory threshold" in window, (
            "row 7c must Compare the total-AT count against the "
            "feature_total_at_advisory_threshold (brief §3b Compare; DD-3 knob)"
        )

    def then_advisory_silent_at_or_under_threshold(self) -> None:
        """AT-4: row 7c's negative branch — at or under the advisory threshold,
        the advisory stays SILENT (brief §2; §3b Branch). No false advisory on a
        right-sized feature."""
        window = self._row_7c_window().lower()
        assert "over" in window, (
            "row 7c must express the OVER-threshold branch that fires the "
            "advisory (brief §3b Branch: 'over -> propose /nw-discuss')"
        )
        assert "silent" in window, (
            "row 7c must state its at-or-under branch is SILENT (brief §2 "
            "'at-or-under -> silent') so a right-sized feature gets NO false "
            "advisory (AT-4)"
        )

    # --- Then: DESConfig port surface (AT-6) -------------------------------

    def _read_threshold(self) -> int:
        assert self._cfg is not None, "config not driven yet"
        assert hasattr(self._cfg, "rigor_feature_total_at_advisory_threshold"), (
            "DESConfig must expose a rigor_feature_total_at_advisory_threshold "
            "@property (brief §5 form; DD-3) — the advisory threshold is a "
            "rigor-cascaded knob, not a hard-wired literal (AT-6)"
        )
        value = self._cfg.rigor_feature_total_at_advisory_threshold
        self._threshold = value
        return value

    def then_threshold_reads_rigor_cascade(self, sentinel: int) -> None:
        """AT-6: the @property reads the value from the des-config.json `rigor.`
        cascade (project -> global -> @property default), mirroring
        rigor_tdd_phases."""
        assert self._read_threshold() == sentinel, (
            "rigor_feature_total_at_advisory_threshold must read the value from "
            "the des-config.json `rigor.feature_total_at_advisory_threshold` "
            "cascade (project -> global -> @property default) — AT-6"
        )

    def then_threshold_defaults_to_positive_int(self) -> None:
        """AT-6: with no project/global rigor config, the threshold falls back to
        the @property's own positive-integer default (DD-3 fallback)."""
        value = self._read_threshold()
        assert isinstance(value, int) and value > 0, (
            "rigor_feature_total_at_advisory_threshold must default to a positive "
            "integer ceiling supplied by the @property fallback when no rigor "
            "config is present (DD-3: default lives in the @property) — AT-6"
        )

    def then_threshold_distinct_from_carpaccio_slice_max(self, sentinel: int) -> None:
        """AT-6 / C3: the advisory threshold is a DISTINCT locus from
        carpaccio_slice_max — the two thresholds never collapse onto one knob.
        The @property reads its OWN rigor key, and DESConfig exposes no
        carpaccio_slice_max property (that ceiling lives in config.yaml
        atdd_pure., the carpaccio_format.py locus)."""
        assert self._read_threshold() == sentinel, (
            "the advisory threshold must read its OWN rigor key, not collapse "
            "onto carpaccio_slice_max — C3 two-thresholds-never-collapse (AT-6)"
        )
        assert self._cfg is not None
        assert not hasattr(self._cfg, "carpaccio_slice_max"), (
            "DESConfig must NOT expose carpaccio_slice_max — that ceiling lives in "
            "config.yaml `atdd_pure.` (carpaccio_format.py locus), structurally "
            "distinct from the rigor-cascaded advisory threshold (C3 / DD-3)"
        )
