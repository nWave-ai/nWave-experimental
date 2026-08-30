"""The offline probe's verdict stage must read the axes the verdict EMITS.

Two defects live here, and the second is worth more than the first.

1. SHAPE. `admission_verdict._as_dict` emits `axes` as a mapping
   name -> row. The probe read a top-level `ratios` LIST and keyed it by an
   `axis` field that no row carries, so `.get("ratios", [])` returned `[]`
   on every real document and all three axes read as absent.

2. FALSE GREEN. `ratio_axis` returns `ratio=None` / `INDETERMINATE`
   whenever no pair carries a computable ratio, and that row is still
   emitted under `axes`. A presence-only check finds three rows, declares
   the verdict computed "with every axis carrying a number", and passes on
   a chain that measured nothing. Presence is not a measurement.

These assertions run against documents produced by `admission_verdict`
itself wherever the shape is the thing under test, so a change to the
emitted document fails HERE rather than silently re-opening defect 1.
"""

from __future__ import annotations

import json

from scripts.analysis.k4 import admission_verdict as av
from scripts.analysis.k4 import offline_chain_probe as probe


def _row(ratio, status="within"):
    return {
        "bound": 1.5,
        "ratio": ratio,
        "status": status,
        "counted_pairs": [1],
        "excluded_pairs": [],
        "per_pair": [],
    }


def _document(**ratios):
    return {"verdict": "ADMIT", "axes": {n: _row(r) for n, r in ratios.items()}}


class TestAxesOf:
    def test_reads_the_mapping_the_verdict_actually_emits(self):
        computed = _document(cost=1.2, tokens=1.3, wall=2.6)

        axes = probe.axes_of(computed)

        assert sorted(axes) == ["cost", "tokens", "wall"]
        assert axes["wall"]["ratio"] == 2.6

    def test_the_old_ratios_list_shape_is_not_what_is_emitted(self):
        """Defect 1, pinned: keying a `ratios` list yields nothing."""
        computed = _document(cost=1.2, tokens=1.3, wall=2.6)

        assert "ratios" not in computed
        assert probe.uncomputed_axes(probe.axes_of(computed)) == []

    def test_a_non_mapping_axes_field_yields_no_axes_rather_than_a_crash(self):
        assert probe.axes_of({"axes": [{"axis": "cost"}]}) == {}
        assert probe.axes_of({}) == {}


class TestUncomputedAxes:
    def test_all_three_numeric_is_the_only_computed_case(self):
        assert (
            probe.uncomputed_axes(
                probe.axes_of(_document(cost=1.2, tokens=1.3, wall=2.6))
            )
            == []
        )

    def test_an_absent_axis_is_reported(self):
        uncomputed = probe.uncomputed_axes(probe.axes_of(_document(cost=1.2)))

        assert [u.split("(")[0] for u in uncomputed] == ["tokens", "wall"]
        assert all("absent" in u for u in uncomputed)

    def test_a_present_axis_with_a_null_ratio_is_reported_as_uncomputed(self):
        """Defect 2 -- the false green this check exists to intercept."""
        computed = {
            "verdict": "INDETERMINATE",
            "axes": {
                "cost": _row(None, "indeterminate"),
                "tokens": _row(None, "indeterminate"),
                "wall": _row(None, "indeterminate"),
            },
        }

        assert sorted(probe.axes_of(computed)) == ["cost", "tokens", "wall"]

        uncomputed = probe.uncomputed_axes(probe.axes_of(computed))

        assert [u.split("(")[0] for u in uncomputed] == ["cost", "tokens", "wall"]
        assert all("ratio=None" in u for u in uncomputed)

    def test_a_bool_ratio_is_not_a_measurement(self):
        """`isinstance(True, int)` is True in Python; a truth value is not a
        ratio, and letting one through would be the same green by accident."""
        assert probe.uncomputed_axes(
            probe.axes_of(_document(cost=True, tokens=1.3, wall=2.6))
        ) == ["cost(ratio=True)"]

    def test_quality_is_not_demanded_as_a_ratio(self):
        """`quality` has no bound and no ratio by design (`QualityAxis`);
        demanding a number from it would be a category error."""
        assert "quality" not in probe.RATIO_AXES
        assert "quality" not in av.BOUNDS


class TestAgainstTheRealEmittedDocument:
    def test_an_empty_campaign_emits_three_null_ratio_axes_not_zero_axes(self):
        """The exact substrate of defect 2, produced by the real emitter:
        with no pairs, every axis is PRESENT and every ratio is None."""
        result = av.Admission(
            verdict=av.Verdict.INDETERMINATE,
            pairs=(),
            axes={name: av.ratio_axis(name, ()) for name in av.BOUNDS},
            quality=av.quality_axis(()),
            valid_pairs=0,
            reasons=(),
        )

        computed = json.loads(json.dumps(av._as_dict(result)))

        assert sorted(computed["axes"]) == ["cost", "tokens", "wall"]
        assert all(row["ratio"] is None for row in computed["axes"].values())

        uncomputed = probe.uncomputed_axes(probe.axes_of(computed))

        assert [u.split("(")[0] for u in uncomputed] == ["cost", "tokens", "wall"]
