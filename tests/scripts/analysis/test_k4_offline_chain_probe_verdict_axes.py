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

SCOPE NOTE (2026-09-06). `uncomputed_axes` is no longer what decides the
verdict stage: with an inert delivery both arms are rejected, so no axis
can carry a number and a criterion demanding one would be a claim about
the fixture. The stage now decides on `unevaluated_arms` -- did every arm
produce an outcome at all -- and still REPORTS what this function finds.
Both defects above remain live and are still pinned here.
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


class TestUnevaluatedArms:
    """What the verdict stage decides on: did every arm produce an outcome?

    The two shapes below were both MEASURED on this box on 2026-09-06, an hour
    apart, which is why this discriminator is not hypothetical. With the nWave
    arm timing a `des` command it could not run, the report read
    `nwave=NOT_RUN`. With both arms running the same agent invocation it read
    `nwave=DELIVERED_REJECTED / control=DELIVERED_REJECTED` -- the chain having
    produced a finding, which is the probe working.
    """

    @staticmethod
    def _report(**arms):
        return {"verdict": "NOT_ADMITTED", "deliveries": [{"pair": 1, **arms}]}

    def test_both_arms_rejected_is_the_chain_working(self):
        report = self._report(nwave="DELIVERED_REJECTED", control="DELIVERED_REJECTED")

        assert probe.unevaluated_arms(report) == []

    def test_an_arm_that_never_ran_is_named(self):
        report = self._report(nwave="NOT_RUN", control="DELIVERED_REJECTED")

        named = probe.unevaluated_arms(report)

        assert named == ["pair-1/nwave=NOT_RUN"]

    def test_an_unscored_arm_is_named_too(self):
        """`UNSCORED` is the other half of `admission_verdict.UNEVALUATED`."""
        report = self._report(nwave="DELIVERED_ACCEPTED", control="UNSCORED")

        assert probe.unevaluated_arms(report) == ["pair-1/control=UNSCORED"]

    def test_a_delivered_nothing_arm_is_a_finding_not_a_chain_defect(self):
        """`NO_DELIVERY` is deliberately outside `UNEVALUATED`: the arm ran."""
        report = self._report(nwave="NO_DELIVERY", control="DELIVERED_REJECTED")

        assert probe.unevaluated_arms(report) == []

    def test_an_absent_deliveries_block_is_not_a_pass(self):
        """An absent measurement is not a passing one."""
        assert probe.unevaluated_arms({"verdict": "ADMIT"}) == ["deliveries(absent)"]
        assert probe.unevaluated_arms({"deliveries": []}) == ["deliveries(absent)"]

    def test_the_vocabulary_comes_from_the_verdict_module_not_from_here(self):
        """Guards the guard: a renamed outcome must break here, not go silent."""
        assert {item.value for item in av.UNEVALUATED} == {"NOT_RUN", "UNSCORED"}

    def test_the_real_emitter_carries_the_block_this_reads(self):
        result = av.Admission(
            verdict=av.Verdict.INDETERMINATE,
            pairs=(),
            axes={name: av.ratio_axis(name, ()) for name in av.BOUNDS},
            quality=av.quality_axis(()),
            valid_pairs=0,
            reasons=(),
        )

        computed = json.loads(json.dumps(av._as_dict(result)))

        assert "deliveries" in computed


class TestTheProbeStatesWhatItDoesNotCover:
    """An all-PASS run must not read as "everything was measured".

    The probe exists so nobody spends a paid campaign on a false reading, and
    the shape that would produce one is a green chain that is silent about the
    three things it cannot reach. Each is named, printed beside the greens and
    carried in the machine record.
    """

    def test_the_ratio_axes_are_declared_uncovered(self):
        assert any("ratio axes" in line for line in probe.NOT_COVERED)
        assert any("INDETERMINATE" in line for line in probe.NOT_COVERED)

    def test_the_step_loop_is_declared_uncovered_and_points_at_its_own_proof(self):
        named = [line for line in probe.NOT_COVERED if "step loop" in line]

        assert named
        assert "test_k4_inert_replay_drives_the_real_runner" in named[0]

    def test_the_judgment_layer_is_declared_uncovered(self):
        assert any("judgment layer" in line for line in probe.NOT_COVERED)

    def test_none_of_the_statements_is_empty(self):
        """Guards the guard: a blank entry would print a reassuring nothing."""
        assert probe.NOT_COVERED
        assert all(line.strip() for line in probe.NOT_COVERED)
