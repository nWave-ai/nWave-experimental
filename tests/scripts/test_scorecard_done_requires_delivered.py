"""M1 regression pin (adversarial audit 2026-06-19): the flow-v2 closure
scorecard must NOT credit a feature DONE on a FeatureEnd record alone — it must
ALSO require every ratified slice attested (delivered >= planned_slices).

Root defect the audit found: `done` was `feature_end and modules_wired and
(planned_slices is not None)`, ignoring the computed `delivered` count. So
features with FeatureEnd records but 0/N or partial SliceCommitVerified (e.g.
f-design-wave-migration 0/3) were falsely DONE — overstating the epic 12/14 vs
honest 8/14. This pins the corrected contract so the metric cannot silently
re-overstate.

Pure stdlib + monkeypatch of the three IO helpers (ledger/registry readers) —
we test the DONE decision logic in isolation, given controlled inputs.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SCORECARD = (
    Path(__file__).resolve().parents[2] / "scripts" / "flow_v2_closure_scorecard.py"
)


def _load_scorecard():
    spec = importlib.util.spec_from_file_location("_scorecard_under_test", _SCORECARD)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def scorecard():
    return _load_scorecard()


def _patch_io(mod, monkeypatch, *, delivered: int) -> None:
    """Force feature_end=present, modules_wired=true, delivered=<delivered>."""
    monkeypatch.setattr(mod, "_has_feature_end_record", lambda fid: True)
    monkeypatch.setattr(mod, "_module_wired", lambda *a, **k: True)
    monkeypatch.setattr(mod, "_slice_commits_verified", lambda fid: delivered)


@pytest.mark.parametrize("delivered", [0, 1, 2])
def test_feature_end_but_slices_unattested_is_not_done(
    scorecard, monkeypatch, delivered
):
    """delivered < planned (with a FeatureEnd record + wired) MUST be NOT done."""
    _patch_io(scorecard, monkeypatch, delivered=delivered)
    feat = {"id": "synthetic", "dir": None, "planned_slices": 3, "wired_modules": []}
    result = scorecard.assess(feat, subs=set())
    assert result["done"] is False, (
        f"M1 regression: a feature with FeatureEnd + wired but only {delivered}/3 "
        f"slices attested was credited DONE — done must require delivered>=planned."
    )
    assert result["phase"] != "DONE"


def test_all_slices_attested_is_done(scorecard, monkeypatch):
    """delivered >= planned (with FeatureEnd + wired) IS done — the fix must not
    over-correct into never-done."""
    _patch_io(scorecard, monkeypatch, delivered=3)
    feat = {"id": "synthetic", "dir": None, "planned_slices": 3, "wired_modules": []}
    result = scorecard.assess(feat, subs=set())
    assert result["done"] is True
    assert result["phase"] == "DONE"


# --- M3 regression pins (adversarial audit 2026-06-19) --------------------
# The defect: feature_end was `_ledger_has(fid, "FeatureEnd")` — a SUBSTRING
# match anywhere in the feature's ledger corpus, so a reviewer's findings_summary
# prose ("f-wave STAYS DONE ... FeatureEnd 63dc27bf intact") false-credited the
# feature DONE before its real feature-end ran. The honest check matches the
# EVENT-TYPE field on a single ledger RECORD scoped to the feature_id.


def _ledger_with(mod, monkeypatch, tmp_path: Path, line: str) -> None:
    """Point `_ledger_files` at a single tmp ledger file holding `line`."""
    f = tmp_path / "synthetic.jsonl"
    f.write_text(line + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_ledger_files", lambda: [f])


def test_prose_mention_of_featureend_does_not_credit(scorecard, monkeypatch, tmp_path):
    """A reviewer ATReviewVerdict whose prose mentions 'FeatureEnd' must NOT
    count as a feature-end attestation (the exact M3 false-credit case)."""
    prose = (
        '{"event":"ATReviewVerdict","feature_id":"synthetic",'
        '"findings_summary":["f-wave STAYS DONE, FeatureEnd 63dc27bf intact"],'
        '"verdict":"APPROVED"}'
    )
    _ledger_with(scorecard, monkeypatch, tmp_path, prose)
    assert scorecard._has_feature_end_record("synthetic") is False, (
        "M3 regression: a prose mention of 'FeatureEnd' in a reviewer's "
        "findings_summary must NOT credit a feature-end record."
    )


def test_real_featureend_event_record_credits(scorecard, monkeypatch, tmp_path):
    """A genuine record with event=FeatureEndReviewVerdict for this feature_id
    on one line MUST credit (the fix must not over-correct into never-attested)."""
    real = (
        '{"event":"FeatureEndReviewVerdict","feature_id":"synthetic",'
        '"verdict":"APPROVED","verdict_hash":"deadbeef"}'
    )
    _ledger_with(scorecard, monkeypatch, tmp_path, real)
    assert scorecard._has_feature_end_record("synthetic") is True


def test_featureend_event_for_other_feature_does_not_credit(
    scorecard, monkeypatch, tmp_path
):
    """A real FeatureEnd event for a DIFFERENT feature_id must NOT credit this
    feature (the event token alone is not enough — it must be scoped)."""
    other = (
        '{"event":"FeatureEndReviewVerdict","feature_id":"some-other-feature",'
        '"verdict":"APPROVED"}'
    )
    _ledger_with(scorecard, monkeypatch, tmp_path, other)
    assert scorecard._has_feature_end_record("synthetic") is False
