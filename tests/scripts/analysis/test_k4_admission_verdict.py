"""Falsifiers for the mechanized K4 admission verdict.

Two of them are the point of the whole module, and both are stated as a
DIVERGENCE from the verdict as it is computed by hand today:

* `test_camp6_wall_diverges_from_the_hand_aggregate` -- on camp6's own recorded
  numbers the hand aggregate for wall is `1.24x`, comfortably inside the `1.5x`
  bound, and the correct answer is `2.81x`, a breach. The two disagree in SIGN,
  not in the fourth decimal, and the reason is entirely trap (a): two of the
  three pairs saw the nWave arm deliver nothing, so their favourable ratios
  measure an abort. The naive computation is not described here, it is EXECUTED
  (`hand_aggregate` below), so this stays a live falsifier rather than a story
  about one that used to fail.

* `test_one_valid_pair_is_indeterminate_never_admit` -- trap (b). A campaign
  whose every computable ratio sits inside its bound must still refuse to say
  ADMIT off a single pair. One point is an anecdote; a verdict that rounds it
  to PASS is exactly the shortcut this module exists to remove.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.k4 import admission_verdict as av
from scripts.analysis.k4 import quality_rubric


# --- fixture construction ----------------------------------------------------


def _criteria(total: int) -> dict[str, dict]:
    """A well-formed 17-criterion object summing to `total` (0..34)."""
    keys = sorted(quality_rubric.CRITERIA_KEYS, key=int)
    assert 0 <= total <= 2 * len(keys)
    scores = []
    left = total
    for _ in keys:
        take = min(2, left)
        scores.append(take)
        left -= take
    return {
        key: {"score": score, "evidence": "fixture"}
        for key, score in zip(keys, scores, strict=True)
    }


def _rubric_verdict(total: int, blocking: int) -> dict:
    return {
        "criteria": _criteria(total),
        "total": total,
        "blocking_quality_findings": [f"blocker {n + 1}" for n in range(blocking)],
        "summary": "fixture",
    }


def _payload(session: str, cost: float, tokens: int, wall_s: float) -> str:
    """The shape `paired_spread.classify` actually reads, `modelUsage` included
    so the token scope is the nested-inclusive one and not the scope that once
    let a 1.2881x ratio pass."""
    return json.dumps(
        {
            "session_id": session,
            "is_error": False,
            "total_cost_usd": cost,
            "num_turns": 30,
            "duration_ms": round(wall_s * 1000),
            "modelUsage": {
                "model-a": {
                    "inputTokens": tokens,
                    "outputTokens": 0,
                    "cacheCreationInputTokens": 0,
                    "cacheReadInputTokens": 0,
                }
            },
        }
    )


def _failed_payload(session: str) -> str:
    return json.dumps({"session_id": session, "is_error": True})


def build_campaign(tmp_path: Path, rows: list[dict]) -> tuple[Path, dict, dict]:
    """`rows[i]` describes pair i+1: per arm a measurement or `None` for a run
    that never produced one, plus the acceptance owner's delivery record."""
    campaign = tmp_path / "campaign"
    verdicts: dict[str, dict] = {}
    rubric: dict[str, dict] = {}
    for index, row in enumerate(rows, start=1):
        pair_dir = campaign / f"pair-{index}"
        pair_dir.mkdir(parents=True)
        for arm in ("nwave", "control"):
            session = f"sess-{index}-{arm}"
            spec = row[arm]
            if spec.get("ran", True):
                text = _payload(session, spec["cost"], spec["tokens"], spec["wall_s"])
            else:
                text = _failed_payload(session)
            (pair_dir / f"{arm}.json").write_text(text, encoding="utf-8")
            if "delivered" in spec:
                verdicts[session] = {
                    "delivered": spec["delivered"],
                    "accepted": spec.get("accepted", False),
                    "evidence": spec.get("evidence", "fixture"),
                    "scorer": "fixture",
                }
            if "rubric" in spec:
                rubric[session] = _rubric_verdict(*spec["rubric"])
    return campaign, verdicts, rubric


#: camp6, 2026-08-20/21. The PER-PAIR RATIOS and the campaign aggregates are the
#: recorded ones (roadmap, "K4 paired campaign camp6 -- measured outcome"):
#: cost 0.44/0.62/1.31 agg 0.78, tokens 0.18/0.36/0.81 agg 0.45, wall
#: 0.65/0.86/2.81 agg 1.24, rubric 9/24, 8/25, 21/23 with 4/0, 5/1, 1/1
#: blockers, and "p1/p2 nWave did NOT deliver". The ABSOLUTE seconds and dollars
#: below are a reconstruction chosen to reproduce those recorded ratios and
#: aggregates exactly -- the campaign's own payloads were destroyed by the /tmp
#: wipe that `campaign_archive.py` now exists to prevent, so the recorded ratios
#: are the surviving evidence and this fixture is honest about being derived
#: from them rather than from the payloads.
CAMP6 = [
    {
        "nwave": {
            "cost": 3.63132,
            "tokens": 3_420_000,
            "wall_s": 650.0,
            "delivered": False,
            "evidence": "spec-only package, ATs cannot import",
            "rubric": (9, 4),
        },
        "control": {
            "cost": 8.253,
            "tokens": 19_000_000,
            "wall_s": 1000.0,
            "delivered": True,
            "accepted": True,
            "rubric": (24, 0),
        },
    },
    {
        "nwave": {
            "cost": 5.11686,
            "tokens": 6_840_000,
            "wall_s": 860.0,
            "delivered": False,
            "evidence": "contract carries <ATD: fill> placeholders",
            "rubric": (8, 5),
        },
        "control": {
            "cost": 8.253,
            "tokens": 19_000_000,
            "wall_s": 1000.0,
            "delivered": True,
            "accepted": True,
            "rubric": (25, 1),
        },
    },
    {
        "nwave": {
            "cost": 10.19966,
            "tokens": 15_390_000,
            "wall_s": 1736.018,
            "delivered": True,
            "accepted": True,
            "evidence": "commit 64b24ba7",
            "rubric": (21, 1),
        },
        "control": {
            "cost": 7.786,
            "tokens": 19_000_000,
            "wall_s": 617.8,
            "delivered": True,
            "accepted": True,
            "rubric": (23, 1),
        },
    },
]


def hand_aggregate(pairs: tuple[av.PairRecord, ...], axis: str) -> float:
    """The shortcut this module replaces, executed rather than described.

    Sum both arms over EVERY pair and divide. It has no idea that a pair whose
    nWave arm produced nothing contributes an abort's cost, not a delivery's.
    """
    getter = {
        "cost": lambda run: run.cost,
        "tokens": lambda run: float(run.tokens),
        "wall": lambda run: run.wall_s,
    }[axis]
    return sum(getter(p.nwave) for p in pairs) / sum(getter(p.control) for p in pairs)


@pytest.fixture
def camp6(tmp_path):
    campaign, verdicts, rubric = build_campaign(tmp_path, CAMP6)
    return av.read_campaign(campaign, verdicts, rubric)


# --- trap (a): a ratio against a non-delivery is a division by an absence ----


def test_camp6_wall_diverges_from_the_hand_aggregate(camp6):
    assert hand_aggregate(camp6, "wall") == pytest.approx(1.24, abs=0.005)
    assert hand_aggregate(camp6, "wall") <= av.WALL_BOUND  # the hand verdict reads PASS

    axis = av.ratio_axis("wall", camp6)
    assert list(axis.counted) == [3]
    assert axis.ratio == pytest.approx(2.81, abs=0.005)
    assert axis.status is av.Status.BREACH
    assert [i for i, _ in axis.excluded] == [1, 2]


def test_camp6_cost_and_tokens_lose_their_asterisk(camp6):
    assert hand_aggregate(camp6, "cost") == pytest.approx(0.78, abs=0.005)
    assert hand_aggregate(camp6, "tokens") == pytest.approx(0.45, abs=0.005)

    cost = av.ratio_axis("cost", camp6)
    tokens = av.ratio_axis("tokens", camp6)
    assert cost.ratio == pytest.approx(1.31, abs=0.005)
    assert tokens.ratio == pytest.approx(0.81, abs=0.005)
    # Inside their bounds, but on ONE pair: the recorded verdict wrote "PASS*"
    # with a footnote. The asterisk is the third state, so it is a state here.
    assert cost.status is av.Status.INDETERMINATE
    assert tokens.status is av.Status.INDETERMINATE


def test_not_delivered_and_delivered_badly_are_never_averaged_together(tmp_path):
    rows = [
        {
            "nwave": {"cost": 1.0, "tokens": 10, "wall_s": 10.0, "delivered": False},
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
            },
        },
        {
            "nwave": {
                "cost": 4.0,
                "tokens": 40,
                "wall_s": 40.0,
                "delivered": True,
                "accepted": False,
            },
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
            },
        },
    ]
    pairs = av.read_campaign(*build_campaign(tmp_path, rows))
    assert pairs[0].nwave.delivery is av.Delivery.NO_DELIVERY
    assert pairs[1].nwave.delivery is av.Delivery.DELIVERED_REJECTED

    axis = av.ratio_axis("cost", pairs)
    # A rejected outcome is not a successful comparable delivery. Neither it
    # nor the absent one can be used to manufacture a resource ratio.
    assert list(axis.counted) == []
    assert axis.status is av.Status.INDETERMINATE
    assert "accepted" in axis.excluded[0][1]


def test_a_missing_delivered_field_is_unscored_never_assumed_delivered(tmp_path):
    rows = [
        {
            "nwave": {"cost": 1.0, "tokens": 10, "wall_s": 10.0},
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
            },
        }
    ]
    pairs = av.read_campaign(*build_campaign(tmp_path, rows))
    assert pairs[0].nwave.delivery is av.Delivery.UNSCORED


# --- trap (b): one pair is an anecdote, and the third state must survive -----


def _one_valid_pair_rows() -> list[dict]:
    """Two pairs lost to a CONTROL-side run failure -- nothing about the nWave
    arm's own quality -- and one clean pair with every ratio inside its bound."""
    clean_nwave = {
        "cost": 1.1,
        "tokens": 11,
        "wall_s": 15.0,
        "delivered": True,
        "accepted": True,
        "rubric": (34, 0),
    }
    clean_control = {
        "cost": 1.0,
        "tokens": 10,
        "wall_s": 10.0,
        "delivered": True,
        "accepted": True,
        "rubric": (34, 0),
    }
    dead_control = {"ran": False}
    return [
        {"nwave": dict(clean_nwave), "control": dead_control},
        {"nwave": dict(clean_nwave), "control": dead_control},
        {"nwave": dict(clean_nwave), "control": dict(clean_control)},
    ]


def test_one_valid_pair_is_indeterminate_never_admit(tmp_path):
    pairs = av.read_campaign(*build_campaign(tmp_path, _one_valid_pair_rows()))
    result = av.decide(pairs)

    assert result.valid_pairs == 1
    for name in ("cost", "tokens", "wall"):
        axis = result.axes[name]
        assert axis.ratio is not None and axis.ratio <= axis.bound
        assert axis.status is av.Status.INDETERMINATE, name
    assert result.quality.gate is av.Status.BREACH
    assert result.quality.ordering is av.Status.INDETERMINATE
    assert result.verdict is av.Verdict.NOT_ADMITTED
    assert any("quality" in reason.lower() for reason in result.reasons)


def test_minimum_valid_pairs_rejects_wall_drift_above_one_point_five(tmp_path):
    """A 1.6x wall is a finding even with otherwise equal, valid arms."""
    nwave = {
        "cost": 1.0,
        "tokens": 10,
        "wall_s": 16.0,
        "delivered": True,
        "accepted": True,
        "rubric": (34, 0),
    }
    control = {
        "cost": 1.0,
        "tokens": 10,
        "wall_s": 10.0,
        "delivered": True,
        "accepted": True,
        "rubric": (34, 0),
    }
    rows = [
        {"nwave": dict(nwave), "control": dict(control)}
        for _ in range(av.MIN_VALID_PAIRS)
    ]

    result = av.decide(av.read_campaign(*build_campaign(tmp_path, rows)))

    assert result.valid_pairs == av.MIN_VALID_PAIRS
    assert result.axes["cost"].status is av.Status.WITHIN
    assert result.axes["tokens"].status is av.Status.WITHIN
    assert result.axes["wall"].ratio == pytest.approx(1.6)
    assert result.axes["wall"].status is av.Status.BREACH
    assert result.verdict is av.Verdict.NOT_ADMITTED


def test_wall_bound_is_inclusive_at_one_point_five(tmp_path):
    rows = [
        {
            "nwave": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 15.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            },
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            },
        }
        for _ in range(av.MIN_VALID_PAIRS)
    ]

    result = av.decide(av.read_campaign(*build_campaign(tmp_path, rows)))

    assert result.axes["wall"].ratio == pytest.approx(1.5)
    assert result.axes["wall"].status is av.Status.WITHIN
    assert result.verdict is av.Verdict.ADMIT


def test_a_higher_total_cannot_hide_a_zero_triggered_pbt_criterion(tmp_path):
    rows = [
        {
            "nwave": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            },
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (17, 0),
            },
        }
        for _ in range(av.MIN_VALID_PAIRS)
    ]
    campaign, verdicts, rubric = build_campaign(tmp_path, rows)
    for session, record in rubric.items():
        if session.endswith("-nwave"):
            record["criteria"]["12"]["score"] = 0
            record["total"] = 32
        else:
            for criterion in record["criteria"].values():
                criterion["score"] = 1
            record["total"] = len(quality_rubric.CRITERIA_KEYS)

    result = av.decide(av.read_campaign(campaign, verdicts, rubric))

    assert result.verdict is av.Verdict.NOT_ADMITTED
    pbt = [row for row in result.quality.criteria if row.criterion == "12"]
    assert all(row.nwave_score == 0 and row.control_score == 1 for row in pbt)
    assert all(row.status is av.Status.BREACH for row in pbt)


def test_equal_zero_on_an_always_required_item_never_admits(tmp_path):
    rows = [
        {
            arm: {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            }
            for arm in ("nwave", "control")
        }
        for _ in range(av.MIN_VALID_PAIRS)
    ]
    campaign, verdicts, rubric = build_campaign(tmp_path, rows)
    for record in rubric.values():
        record["criteria"]["4"]["score"] = 0
        record["total"] = 32

    result = av.decide(av.read_campaign(campaign, verdicts, rubric))

    assert result.verdict is av.Verdict.NOT_ADMITTED
    always_required = [row for row in result.quality.criteria if row.criterion == "4"]
    assert all(row.nwave_score == row.control_score == 0 for row in always_required)
    assert all(row.status is av.Status.BREACH for row in always_required)


def test_nwave_blocking_finding_vetoes_even_when_control_has_one_too(tmp_path):
    rows = [
        {
            arm: {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 1),
            }
            for arm in ("nwave", "control")
        }
        for _ in range(av.MIN_VALID_PAIRS)
    ]

    result = av.decide(av.read_campaign(*build_campaign(tmp_path, rows)))

    assert result.quality.blocking is av.Status.BREACH
    assert result.verdict is av.Verdict.NOT_ADMITTED


@pytest.mark.parametrize("score,evidence", [(True, "fixture"), (3, "fixture"), (1, "")])
def test_malformed_criterion_facts_are_indeterminate_when_read_directly(
    tmp_path, score, evidence
):
    rows = [
        {
            arm: {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            }
            for arm in ("nwave", "control")
        }
    ]
    campaign, verdicts, rubric = build_campaign(tmp_path, rows)
    rubric["sess-1-nwave"]["criteria"]["1"] = {
        "score": score,
        "evidence": evidence,
    }

    (pair,) = av.read_campaign(campaign, verdicts, rubric)

    assert pair.nwave.rubric_scores is None
    assert av.quality_axis((pair,)).ordering is av.Status.INDETERMINATE


def test_control_rejected_outcome_vetoes_otherwise_perfect_pairs(tmp_path):
    rows = [
        {
            "nwave": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
                "rubric": (34, 0),
            },
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": False,
                "rubric": (34, 0),
            },
        }
        for _ in range(av.MIN_VALID_PAIRS)
    ]

    result = av.decide(av.read_campaign(*build_campaign(tmp_path, rows)))

    assert result.valid_pairs == 0
    assert result.quality.gate is av.Status.BREACH
    assert result.verdict is av.Verdict.NOT_ADMITTED


def test_indeterminate_reaches_the_exit_code(tmp_path):
    campaign, verdicts, rubric = build_campaign(tmp_path, _one_valid_pair_rows())
    (tmp_path / "verdicts.json").write_text(json.dumps(verdicts), encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
    code = av.main(
        [
            "--campaign",
            str(campaign),
            "--verdicts",
            str(tmp_path / "verdicts.json"),
            "--rubric",
            str(tmp_path / "rubric.json"),
        ]
    )
    assert code == 2  # 0 ADMIT, 1 NOT_ADMITTED, 2 INDETERMINATE


def test_a_breach_on_one_pair_still_refuses_admission(camp6):
    """Insufficient sample cannot manufacture an admission, and it cannot erase
    an observed breach either: admission is the claim being established."""
    result = av.decide(camp6)
    assert result.verdict is av.Verdict.NOT_ADMITTED
    assert result.valid_pairs == 1
    assert any(reason.startswith("wall") for reason in result.reasons)


# --- an absence of evaluation is not a breach (camp7, 2026-08-23) ------------
#
# camp7's real archive: one pair, both arms ran and produced payloads, and the
# acceptance record for each carried NO `delivered` field at all -- so both
# arms resolved UNSCORED, zero pairs were valid, and the quality GATE read
# BREACH for the sole reason that nothing had ever scored them. The verdict
# came out NOT_ADMITTED: a flat refusal of the nWave arm off a campaign in
# which no comparison was ever computed. Never-evaluated is the third state,
# not the negative one.
#
# The narrowing matters as much as the guard: `test_a_breach_on_one_pair_
# still_refuses_admission` above (camp6, one valid pair, wall 2.81x) must keep
# refusing, and so must a campaign whose arms DID run and delivered nothing --
# NO_DELIVERY is an established outcome, UNSCORED is the lack of one.


def _unscored_pair_rows() -> list[dict]:
    """camp7's shape: both arms produced a measurement, neither was scored."""
    arm = {"cost": 1.0, "tokens": 10, "wall_s": 10.0}
    return [{"nwave": dict(arm), "control": dict(arm)}]


def test_zero_valid_pairs_of_never_evaluated_arms_is_indeterminate(tmp_path):
    """The camp7 falsifier: a campaign nothing ever scored cannot yield a
    refusal, because a refusal is a finding and no finding was made."""
    pairs = av.read_campaign(*build_campaign(tmp_path, _unscored_pair_rows()))
    result = av.decide(pairs)

    assert result.valid_pairs == 0
    assert pairs[0].nwave.delivery is av.Delivery.UNSCORED
    assert result.verdict is av.Verdict.INDETERMINATE
    assert any("sample" in reason.lower() for reason in result.reasons)
    # No reason is LABELLED a breach. The quality axis still quotes its own
    # `gate=BREACH` inside the detail -- that is the axis reporting what it
    # saw; what changed is that the DECISION no longer reads it as a finding.
    assert not any(": BREACH (" in reason for reason in result.reasons)
    assert any("never evaluated" in reason for reason in result.reasons)


def test_never_evaluated_indeterminate_reaches_the_exit_code(tmp_path):
    campaign, verdicts, rubric = build_campaign(tmp_path, _unscored_pair_rows())
    (tmp_path / "verdicts.json").write_text(json.dumps(verdicts), encoding="utf-8")
    (tmp_path / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
    code = av.main(
        [
            "--campaign",
            str(campaign),
            "--verdicts",
            str(tmp_path / "verdicts.json"),
            "--rubric",
            str(tmp_path / "rubric.json"),
        ]
    )
    assert code == 2  # INDETERMINATE, not 1 NOT_ADMITTED


def test_zero_valid_pairs_of_arms_that_delivered_nothing_is_still_refused(tmp_path):
    """The guard is limited to arms never evaluated. An arm that RAN and
    delivered nothing was evaluated -- the gate fails on an observed outcome,
    and zero valid pairs must not launder that into "cannot tell"."""
    rows = [
        {
            "nwave": {"cost": 1.0, "tokens": 10, "wall_s": 10.0, "delivered": False},
            "control": {
                "cost": 1.0,
                "tokens": 10,
                "wall_s": 10.0,
                "delivered": True,
                "accepted": True,
            },
        }
    ]
    pairs = av.read_campaign(*build_campaign(tmp_path, rows))
    result = av.decide(pairs)

    assert result.valid_pairs == 0
    assert pairs[0].nwave.delivery is av.Delivery.NO_DELIVERY
    assert result.verdict is av.Verdict.NOT_ADMITTED
    assert any("BREACH" in reason for reason in result.reasons)


# --- the quality axis, which is not a number ---------------------------------


def test_quality_carries_no_threshold_constant():
    assert set(av.BOUNDS) == {"cost", "tokens", "wall"}
    assert "quality" not in av.BOUNDS


def test_quality_is_an_ordering_a_gate_and_a_quotation(camp6):
    quality = av.quality_axis(camp6)

    # GATE: two nWave arms never delivered, so the accepted-outcome gate fails
    # and names the state of each -- not a score, a state.
    assert quality.gate is av.Status.BREACH
    assert dict(quality.gate_detail) == {1: "NO_DELIVERY", 2: "NO_DELIVERY"}

    # ORDERING: every criterion is compared independently, never summed.
    assert len(quality.criteria) == 3 * len(quality_rubric.CRITERIA_KEYS)
    assert any(row.status is av.Status.BREACH for row in quality.criteria)
    assert quality.ordering is av.Status.BREACH

    # REPORTED JUDGMENT: the reviewer's blocking findings are carried verbatim.
    assert len([r for r in quality.reported if r[1] == "nwave"]) == 10
    assert all(isinstance(text, str) for _, _, text in quality.reported)


def test_quality_ordering_keeps_criterion_evidence(camp6):
    quality = av.quality_axis(camp6)
    row = next(
        row for row in quality.criteria if row.pair == 3 and row.criterion == "12"
    )
    assert row.nwave_evidence == row.control_evidence == "fixture"


# --- the two ways a report can be well-formed and wrong ----------------------


def test_arm_roles_are_never_guessed():
    with pytest.raises(av.ArmResolutionError):
        av.resolve_roles({"armx", "army"})
    assert av.resolve_roles({"treatment", "control"}) == {
        "treatment": "nwave",
        "control": "control",
    }


def test_top_level_token_scope_is_refused_not_counted(tmp_path):
    campaign = tmp_path / "campaign"
    (campaign / "pair-1").mkdir(parents=True)
    for arm in ("nwave", "control"):
        (campaign / "pair-1" / f"{arm}.json").write_text(
            json.dumps(
                {
                    "session_id": f"s-{arm}",
                    "is_error": False,
                    "total_cost_usd": 1.0,
                    "num_turns": 1,
                    "duration_ms": 1000,
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 1,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
    verdicts = {
        f"s-{arm}": {"delivered": True, "accepted": True}
        for arm in ("nwave", "control")
    }
    pairs = av.read_campaign(campaign, verdicts, {})
    axis = av.ratio_axis("tokens", pairs)
    assert axis.status is av.Status.INDETERMINATE
    assert "1.6921" in axis.excluded[0][1]


def test_every_bound_has_a_priority_entry():
    """A bound with no entry in `PRIORITY` is computed and never read.

    This is the structural guard, and it matters more than the repair that
    prompted it. `decide` iterates `PRIORITY`, not `BOUNDS`, so an axis that
    carries a threshold but no priority entry can BREACH in silence: the axis
    object is built, its status is set, and nothing ever looks at it. That was
    `cost`'s exact state until 2026-08-23 -- `COST_BOUND = 1.5` from the day
    the bounds landed, no `"cost"` in `PRIORITY`, and a measured 2.14x on
    `preflight-20260823-rex` that the verdict could not name.

    Asserting the SET equality (not merely that `cost` is present) is what
    makes the defect class unrepresentable rather than repaired once: adding a
    fourth bound without a priority entry now fails here, and so does an
    orphan priority entry naming an axis `ratio_axis` cannot compute.
    `quality` is subtracted because it is the one axis with no threshold at
    all -- see `QualityAxis`, which is a gate plus an ordering plus a
    quotation, never a ratio.
    """
    assert set(av.PRIORITY) - {"quality"} == set(av.BOUNDS)
    assert "quality" in av.PRIORITY
