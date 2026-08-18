"""`unseal` must reject a malformed reviewer verdict before mapping it back to
a session, not after.

Four reviewer attempts on the paired run produced incompatible rankings; one
observed failure was a criteria array instead of the required keyed object.
The base `unseal` maps whatever JSON it is given straight through -- these
tests go RED against that and GREEN once malformed verdicts are refused with
a WHAT/WHY/HOW before any mapping happens, while valid verdicts still flow
through the existing unknown/unscored conservation check untouched.

The criteria count is read from `br._CRITERIA_KEYS` (itself sourced from
`scripts.analysis.k4.quality_rubric.CRITERIA_KEYS`), never hardcoded here --
the rubric grew from 12 to 18 criteria in the fix that added this note
(ADR-SSOT-002 Section 1a coverage), and this file must not need editing the
next time it grows again.

Run: uv run pytest -q tests/scripts/analysis/test_blind_review_verdict_shape.py
"""

from __future__ import annotations

import json

import pytest

from scripts.analysis import blind_review as br


_N = len(br._CRITERIA_KEYS)


def _valid_verdict(**over):
    criteria = {
        str(n): {"score": 1, "evidence": f"criterion {n}"} for n in range(1, _N + 1)
    }
    verdict = {
        "criteria": criteria,
        "total": _N,
        "blocking_quality_findings": [],
        "summary": "fine",
    }
    verdict.update(over)
    return verdict


def test_valid_verdict_has_no_problems():
    assert br.validate_verdict_shape({"opaque1": _valid_verdict()}) == []


@pytest.mark.parametrize(
    "mutate,label",
    [
        (lambda v: v["criteria"].pop("7"), "missing-criterion-key"),
        (
            lambda v: v.__setitem__(
                "criteria", [v["criteria"][str(n)] for n in range(1, _N + 1)]
            ),
            "criteria-as-array-not-keyed-object",
        ),
        (lambda v: v.pop("criteria"), "criteria-key-missing-entirely"),
        (
            lambda v: (
                v.update({str(n): v["criteria"][str(n)] for n in range(1, _N + 1)})
                or v.pop("criteria")
            ),
            "criteria-flattened-to-top-level",
        ),
        (lambda v: v["criteria"]["3"].update(score="2"), "score-as-string"),
        (lambda v: v["criteria"]["3"].update(score=True), "score-as-bool"),
        (lambda v: v["criteria"]["3"].update(score=3), "score-out-of-range"),
        (lambda v: v["criteria"]["5"].pop("evidence"), "criterion-missing-evidence"),
        (
            lambda v: v["criteria"]["5"].update(unexpected="x"),
            "criterion-extra-key",
        ),
        (lambda v: v.__setitem__("total", 999), "total-does-not-match-sum"),
        (lambda v: v.__setitem__("total", True), "total-as-bool"),
        (
            lambda v: v.__setitem__("blocking_quality_findings", {"a": "b"}),
            "findings-as-dict",
        ),
        (
            lambda v: v.__setitem__("blocking_quality_findings", [1, 2]),
            "findings-with-non-strings",
        ),
        (lambda v: v.__setitem__("summary", 42), "summary-as-int"),
        (lambda v: v.__setitem__("extra_top_key", "x"), "unexpected-top-level-key"),
    ],
)
def test_malformed_verdict_is_rejected(mutate, label):
    verdict = _valid_verdict()
    mutate(verdict)

    problems = br.validate_verdict_shape({"opaque1": verdict})

    assert problems, f"{label} should have been rejected"
    assert all("opaque1" in p for p in problems)


def test_whole_verdict_not_an_object_is_rejected():
    problems = br.validate_verdict_shape({"opaque1": ["not", "an", "object"]})
    assert problems


def test_unseal_refuses_malformed_verdict_before_mapping(tmp_path):
    sealed = tmp_path / "map.json"
    sealed.write_text(
        json.dumps({"salt": "s", "opaque_to_session": {"opaque1": "sess-1"}})
    )
    broken = _valid_verdict()
    broken["criteria"]["3"]["score"] = "high"
    scored = tmp_path / "scored.json"
    scored.write_text(json.dumps({"opaque1": broken}))
    out = tmp_path / "out.json"

    code = br.unseal(sealed, scored, out)

    assert code == 1
    assert not out.exists()


def test_unseal_accepts_valid_verdict_and_maps_it(tmp_path):
    sealed = tmp_path / "map.json"
    sealed.write_text(
        json.dumps({"salt": "s", "opaque_to_session": {"opaque1": "sess-1"}})
    )
    scored = tmp_path / "scored.json"
    scored.write_text(json.dumps({"opaque1": _valid_verdict()}))
    out = tmp_path / "out.json"

    code = br.unseal(sealed, scored, out)

    assert code == 0
    written = json.loads(out.read_text())
    assert set(written) == {"sess-1"}
    assert written["sess-1"]["total"] == _N
