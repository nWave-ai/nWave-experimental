"""Laws the noise-floor analyser must satisfy, not examples of it working.

The instrument decides whether any cost or speed claim in the mission is
attributable to a change or to run-to-run variance. Its first version reported
"noise floor is zero" from five FAILED runs, so the properties below are chosen
for what they would have CAUGHT, not for coverage:

* totality of `classify` -- the defect entered through a case that fell out of
  the classification instead of into an outcome;
* a present `0` is data, an absent field is not -- the literal `if r[key]` bug;
* permutation invariance and scale equivariance of `spread` -- a spread is a
  function of the multiset, and a RATIO is dimensionless, so neither may move
  when the order or the unit does.

Run: uv run pytest -q test_analyse_properties.py
"""

from __future__ import annotations

import json

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from scripts.analysis.paired_spread import (
    AGGREGATE_MODEL_USAGE,
    MIN_USABLE,
    ROOT_PAYLOAD_ONLY,
    TOP_LEVEL_ONLY,
    Failed,
    Indeterminate,
    Spread,
    Unreadable,
    Usable,
    classify,
    spread,
)


_SETTINGS = settings(max_examples=300, deadline=None)


def _payload(**over) -> str:
    base = {
        # Required since the duplicate-artifact finding: without it a run cannot
        # be told apart from a copy of itself, so `classify` calls it Unreadable.
        "session_id": "sess-" + str(abs(hash(str(over))) % 10**8),
        "is_error": False,
        "total_cost_usd": 1.5,
        "num_turns": 7,
        "duration_ms": 12000,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_creation_input_tokens": 30,
            "cache_read_input_tokens": 40,
        },
    }
    base.update(over)
    return json.dumps(base)


# --- classify ----------------------------------------------------------------


@_SETTINGS
@given(raw=st.text(max_size=200))
def test_classify_is_total_over_arbitrary_input(raw: str) -> None:
    """Totality: no input escapes as an exception, every one lands in a case.

    Over arbitrary text, not a curated list: the defect this file exists for was
    triggered by a shape nobody had listed.
    """
    outcome = classify("probe", raw)

    assert isinstance(outcome, Usable | Failed | Unreadable)


@_SETTINGS
@given(
    err=st.booleans(),
    cost=st.floats(min_value=0, max_value=100, allow_nan=False),
    tokens=st.integers(min_value=0, max_value=10_000),
)
def test_a_failed_run_is_never_usable(err: bool, cost: float, tokens: int) -> None:
    """An is_error run is Failed whatever else it carries.

    The refuted alternative: a runtime that sets is_error AND reports plausible
    numbers. Those numbers must not reach the aggregate.
    """
    raw = _payload(
        is_error=err,
        total_cost_usd=cost,
        usage={
            "input_tokens": tokens,
            "output_tokens": tokens,
            "cache_creation_input_tokens": tokens,
            "cache_read_input_tokens": tokens,
        },
    )

    outcome = classify("probe", raw)

    if err:
        assert isinstance(outcome, Failed)
    else:
        assert not isinstance(outcome, Failed) or cost == 0


@_SETTINGS
@given(
    zeroed=st.sampled_from(["input_tokens", "output_tokens", "cache_read_input_tokens"])
)
def test_a_present_zero_is_data_not_absence(zeroed: str) -> None:
    """The literal first defect: `if r[key]` treated a real 0 as missing.

    A run that genuinely cost money and genuinely emitted zero of ONE category
    is a data point, and dropping it biases every spread computed afterwards.
    """
    usage = {
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_creation_input_tokens": 30,
        "cache_read_input_tokens": 40,
    }
    usage[zeroed] = 0

    outcome = classify("probe", _payload(usage=usage))

    assert isinstance(outcome, Usable)
    assert (
        outcome.tokens[
            {
                "input_tokens": "in",
                "output_tokens": "out",
                "cache_read_input_tokens": "cr",
            }[zeroed]
        ]
        == 0
    )


@_SETTINGS
@given(missing=st.sampled_from(["total_cost_usd", "num_turns", "duration_ms"]))
def test_a_half_populated_run_is_unreadable_not_usable(missing: str) -> None:
    """Absent is not zero. A missing field makes the record a reader problem,
    never a silent 0 folded into the median."""
    payload = json.loads(_payload())
    del payload[missing]

    outcome = classify("probe", json.dumps(payload))

    assert isinstance(outcome, Unreadable)


# --- spread ------------------------------------------------------------------

_VALUES = st.lists(
    st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=MIN_USABLE,
    max_size=25,
)


@_SETTINGS
@given(values=_VALUES, seed=st.randoms(use_true_random=False))
def test_spread_is_invariant_under_permutation(values: list[float], seed) -> None:
    """A spread is a function of the MULTISET. Order carries no information.

    This is what catches an implementation that reached for values[0] or
    values[-1] as a stand-in for min or max.
    """
    shuffled = list(values)
    seed.shuffle(shuffled)

    a, b = spread("m", values), spread("m", shuffled)

    assert isinstance(a, Spread) and isinstance(b, Spread)
    assert (a.lo, a.median, a.hi) == (b.lo, b.median, b.hi)
    assert a.ratio == b.ratio


@_SETTINGS
@given(values=_VALUES, k=st.floats(min_value=0.001, max_value=1000, allow_nan=False))
def test_ratio_and_cv_are_scale_invariant(values: list[float], k: float) -> None:
    """A ratio is dimensionless and CV is normalised: changing the UNIT must not
    change either. Seconds or milliseconds, dollars or cents — same answer.

    The strongest law here. It fails for a ratio taken against the mean, for a
    CV computed with the sample rather than the population deviation applied
    inconsistently, and for any accidental additive offset.
    """
    scaled = [v * k for v in values]
    assume(min(scaled) > 0)

    a, b = spread("m", values), spread("m", scaled)

    assert isinstance(a, Spread) and isinstance(b, Spread)
    assert a.ratio == b.ratio or abs(a.ratio - b.ratio) < 1e-6 * max(1.0, a.ratio)
    assert abs(a.cv_percent - b.cv_percent) < 1e-6 * max(1.0, a.cv_percent)


@_SETTINGS
@given(values=_VALUES)
def test_the_ratio_is_never_below_one_and_brackets_the_median(
    values: list[float],
) -> None:
    """Ordering law: lo <= median <= hi, so a ratio below 1 is unrepresentable."""
    result = spread("m", values)

    assert isinstance(result, Spread)
    assert result.lo <= result.median <= result.hi
    assert result.ratio >= 1.0


@_SETTINGS
@given(
    values=st.lists(
        st.floats(min_value=0.01, max_value=1e6, allow_nan=False),
        max_size=MIN_USABLE - 1,
    )
)
def test_too_few_values_always_refuse(values: list[float]) -> None:
    """Below the floor the answer is a refusal VALUE, never a number.

    Returned rather than printed or raised: a caller cannot skip past it, which
    is the whole reason `spread` is total.
    """
    assert isinstance(spread("m", values), Indeterminate)


@_SETTINGS
@given(
    rest=st.lists(
        st.floats(min_value=0.01, max_value=1e6, allow_nan=False),
        min_size=MIN_USABLE - 1,
        max_size=10,
    )
)
def test_a_zero_minimum_refuses_instead_of_returning_infinity(
    rest: list[float],
) -> None:
    """max/min against 0 is undefined, not "very large". Returning inf here
    would print a headline ratio nobody could act on."""
    assert isinstance(spread("m", [0.0, *rest]), Indeterminate)


# --- modelUsage: nested-inclusive aggregation ---------------------------------

_TOKEN_FIELD = {
    "in": "inputTokens",
    "out": "outputTokens",
    "cc": "cacheCreationInputTokens",
    "cr": "cacheReadInputTokens",
}


def _model_record(inp: int, out: int, cc: int, cr: int) -> dict:
    return {
        "inputTokens": inp,
        "outputTokens": out,
        "cacheCreationInputTokens": cc,
        "cacheReadInputTokens": cr,
    }


@_SETTINGS
@given(
    models=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.fixed_dictionaries(
            {
                "inputTokens": st.integers(min_value=0, max_value=10_000),
                "outputTokens": st.integers(min_value=0, max_value=10_000),
                "cacheCreationInputTokens": st.integers(min_value=0, max_value=10_000),
                "cacheReadInputTokens": st.integers(min_value=0, max_value=10_000),
            }
        ),
        min_size=1,
        max_size=6,
    )
)
def test_aggregation_law_equals_componentwise_sum_across_models(models: dict) -> None:
    """The law: aggregate tokens == the component-wise sum over an arbitrary,
    non-empty, valid `modelUsage` map. Order and model count must not matter,
    only the per-category sum -- this is the exact computation the K4 defect
    skipped by reading top-level `usage` instead."""
    outcome = classify("probe", _payload(modelUsage=models))

    assert isinstance(outcome, Usable)
    assert outcome.token_scope == AGGREGATE_MODEL_USAGE
    assert outcome.tokens == {
        k: sum(m[field] for m in models.values()) for k, field in _TOKEN_FIELD.items()
    }


def test_classify_labels_wall_scope_as_root_payload_only() -> None:
    """`classify` never claims more than the root payload measures: `wall_s` is
    `duration_ms` from THIS artifact alone, so its scope must say so honestly
    rather than let a reader assume it accounts for dispatched subagents too."""
    outcome = classify("probe", _payload())

    assert isinstance(outcome, Usable)
    assert outcome.wall_scope == ROOT_PAYLOAD_ONLY


def test_absent_model_usage_preserves_legacy_top_level_scope() -> None:
    """No `modelUsage` key at all: fall back to the pre-existing top-level
    `usage` reading, but label the scope explicitly rather than calling it a
    total -- the exact honesty gap the K4 defect exploited."""
    outcome = classify("probe", _payload())

    assert isinstance(outcome, Usable)
    assert outcome.token_scope == TOP_LEVEL_ONLY
    assert outcome.tokens == {"in": 10, "out": 20, "cc": 30, "cr": 40}


def test_empty_model_usage_dict_falls_back_to_legacy_top_level() -> None:
    """`modelUsage: {}` carries no model to sum, so it must fall back exactly
    like an absent key -- not be treated as a present-but-empty aggregate."""
    outcome = classify("probe", _payload(modelUsage={}))

    assert isinstance(outcome, Usable)
    assert outcome.token_scope == TOP_LEVEL_ONLY


@_SETTINGS
@given(
    bad_value=st.one_of(
        st.booleans(),
        st.text(),
        st.floats(allow_nan=False),
        st.integers(max_value=-1),
        st.none(),
    )
)
def test_malformed_model_token_value_fails_closed_unreadable(bad_value) -> None:
    """bool / non-int / negative / null in a required category must never fall
    back silently to top-level `usage` -- that silent fallback is exactly how
    a broken capture could still report a plausible-looking number."""
    models = {"m": _model_record(1, 1, 1, 1)}
    models["m"]["inputTokens"] = bad_value

    outcome = classify("probe", _payload(modelUsage=models))

    assert isinstance(outcome, Unreadable)


@_SETTINGS
@given(missing_field=st.sampled_from(list(_TOKEN_FIELD.values())))
def test_missing_model_token_category_fails_closed_unreadable(
    missing_field: str,
) -> None:
    """A model record missing a required category is malformed, not a model
    that legitimately used zero of it -- those two are indistinguishable only
    if the reader is willing to fail closed instead of guessing 0."""
    record = _model_record(1, 1, 1, 1)
    del record[missing_field]

    outcome = classify("probe", _payload(modelUsage={"m": record}))

    assert isinstance(outcome, Unreadable)


@_SETTINGS
@given(bad=st.one_of(st.text(), st.integers(), st.lists(st.integers())))
def test_model_usage_wrong_type_fails_closed_unreadable(bad) -> None:
    """`modelUsage` present but not an object (string/number/list) is a reader
    problem, not an invitation to quietly read top-level `usage` instead."""
    payload = json.loads(_payload())
    payload["modelUsage"] = bad

    outcome = classify("probe", json.dumps(payload))

    assert isinstance(outcome, Unreadable)


def test_non_dict_model_record_fails_closed_unreadable() -> None:
    """One model entry that isn't itself an object is malformed, even when its
    siblings in the same `modelUsage` map are well-formed."""
    outcome = classify("probe", _payload(modelUsage={"m": "not-a-record"}))

    assert isinstance(outcome, Unreadable)


def test_k4_false_pass_cannot_return_control_and_nwave_totals() -> None:
    """Regression for the exact K4 defect (`a3f1f4cdf`): top-level `usage`
    totals (control 18,799,230, nWave 24,214,598, ratio 1.2881x) falsely
    PASSed a <=1.5x gate while the nested-inclusive `modelUsage` totals
    (control 19,397,533, nWave 32,822,225, ratio 1.6921x) FAIL it.

    The per-category split below is fixture-minimal and invented -- the real
    transcripts are not needed -- but every TOTAL reproduced here is the exact
    documented K4 number, so this false PASS cannot silently return.
    """
    control = _payload(
        usage={
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_creation_input_tokens": 300,
            "cache_read_input_tokens": 18_798_630,
        },
        modelUsage={
            "primary": _model_record(100, 200, 300, 18_798_630),
            "nested-subagent": _model_record(0, 0, 0, 598_303),
        },
    )
    nwave = _payload(
        usage={
            "input_tokens": 1000,
            "output_tokens": 2000,
            "cache_creation_input_tokens": 3000,
            "cache_read_input_tokens": 24_208_598,
        },
        modelUsage={
            "primary": _model_record(1000, 2000, 3000, 24_208_598),
            "nested-subagent": _model_record(0, 0, 0, 8_607_627),
        },
    )

    control_outcome = classify("control", control)
    nwave_outcome = classify("nwave", nwave)

    assert isinstance(control_outcome, Usable)
    assert isinstance(nwave_outcome, Usable)
    assert control_outcome.token_scope == AGGREGATE_MODEL_USAGE
    assert nwave_outcome.token_scope == AGGREGATE_MODEL_USAGE
    control_total = sum(control_outcome.tokens.values())
    nwave_total = sum(nwave_outcome.tokens.values())
    assert control_total == 19_397_533
    assert nwave_total == 32_822_225
    assert nwave_total / control_total > 1.5  # true ratio 1.6921x -- FAILs

    # The false-PASS path this fixes: strip modelUsage, read top-level only.
    stale_control = json.loads(control)
    del stale_control["modelUsage"]
    stale_nwave = json.loads(nwave)
    del stale_nwave["modelUsage"]
    stale_control_outcome = classify("control", json.dumps(stale_control))
    stale_nwave_outcome = classify("nwave", json.dumps(stale_nwave))

    assert isinstance(stale_control_outcome, Usable)
    assert isinstance(stale_nwave_outcome, Usable)
    assert stale_control_outcome.token_scope == TOP_LEVEL_ONLY
    stale_control_total = sum(stale_control_outcome.tokens.values())
    stale_nwave_total = sum(stale_nwave_outcome.tokens.values())
    assert stale_control_total == 18_799_230
    assert stale_nwave_total == 24_214_598
    assert stale_nwave_total / stale_control_total < 1.5  # the false PASS
