"""Regression AT (pytest-regression, active-RED): bugfix #63.

`des commit-slice` prints two LOUD notices whose HOW line ends
`--reviewer-agent-id <id>` -- an opaque placeholder a maintainer cannot act
on (GDP-3/4: the HOW must be self-explaining / actionable). Both loci live in
``src/des/cli/commit_slice.py``:

  * ``_notify_feature_end_unmissable`` (~line 173-181) -- the
    ``FeatureEndPending`` WHAT/WHY/HOW notice printed to stdout when the last
    declared Slice-Plan slice of a feature ships.
  * the AT-review WARNING inside ``_ensure_reviewed_by`` (~line 785) --
    printed to stderr when no APPROVED ``ATReviewVerdict`` ledger record is
    found for a slice being committed.

Charter (value-side observable): ``docs/product/expectations/
fix-feature-end-notice-actionable-how/
a-maintainer-can-act-on-the-printed-next-step-command.md`` -- the printed
"run this next" instruction is actionable: no bare unexplained placeholder,
a maintainer can fill any placeholder without reading source or guessing.

PLANNED FIX (message-text only, no behaviour change): keep the ``<id>``
placeholder -- the reviewer-agent id is genuinely session-specific, not
pre-fillable -- but annotate WHAT the maintainer must substitute (the agent
id of the reviewer that performed / will perform the feature-end review; any
stable non-empty reviewer id), turning a bare ``<id>`` into an actionable
HOW, in BOTH notices. Both notices stay best-effort-LOUD (never raise).

GAP FOUND BY VERA'S EXAMINE (this extension): the ``<id>`` fix alone is
INCOMPLETE. Notice 2's HOW (``_ensure_reviewed_by``, ~line 787) prints a
SECOND, un-related placeholder verbatim: ``--feature-id <feature>``. Unlike
``<id>``, the feature id is NOT session-specific-unknown -- it is the
``feature_id`` argument, known at print time (notice 1's HOW already proves
this: it fills ``--feature-id {feature_id}`` literally, line 178-179). The
charter requires EVERY placeholder in EVERY notice to be actionable, not
just ``<id>``. The correct fix FILLS ``<feature>`` with the real id (making
it disappear, fully copy-pasteable) rather than annotating it -- ``<id>``
stays a placeholder (explained); ``<feature>`` must not exist at all.

Driving surface: the two REAL production helpers are called directly
(``_notify_feature_end_unmissable``, ``_ensure_reviewed_by``) against a real
tmp-filesystem fixture (a ``[REF] Slice Plan`` feature-delta + a real
``SliceCommitVerified`` AT-completion-ledger record, minted through the SAME
production writer ``des commit-slice`` itself uses). No git work-tree is
required -- neither helper touches git (verified against
``AtCompletionLedger`` + ``verify_deliver_integrity`` readers, pure
filesystem). This targets the message TEXT of two internal notice-printing
helpers directly per dispatch instruction (mirrors the established unit-test
precedent already living in this directory, e.g.
``test_deliver_finalize_unmissable.py`` for the sibling notice).

RED reason (current tree): both notices' HOW line ends with a bare
``--reviewer-agent-id <id>`` and carry ZERO explanatory text anywhere in the
printed message -- ``_how_explains_reviewer_id_placeholder`` returns False
for both. GREEN once the crafter adds a plain-language explanation per the
PLANNED FIX above.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import (
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
)
from des.cli.commit_slice import _ensure_reviewed_by, _notify_feature_end_unmissable


# ---------------------------------------------------------------------------
# Oracle: what "the placeholder is explained" means, mechanically.
# ---------------------------------------------------------------------------

#: The bare, unexplained placeholder pattern BOTH loci print today -- pinned
#: verbatim from ``src/des/cli/commit_slice.py`` (the RED baseline).
_BARE_PLACEHOLDER = "--reviewer-agent-id <id>"

#: Phrases the PLANNED FIX is expected to introduce when it annotates the
#: placeholder -- drawn directly from the defect's own fix wording: "the
#: agent id of the reviewer that performed / will perform the feature-end
#: review; any stable non-empty reviewer id". NONE of these phrases occur in
#: the current bare text of either notice (both pinned verbatim above), so
#: their absence IS the RED condition; ANY ONE present is accepted GREEN
#: evidence -- the crafter has latitude on exact phrasing. "reviewer" alone
#: is deliberately excluded as a marker: it already occurs today as a
#: substring of the `--reviewer-agent-id` flag name / surrounding prose, so
#: it cannot discriminate "explained" from "bare".
_EXPLANATION_MARKERS: tuple[str, ...] = (
    "substitut",
    "any stable",
    "non-empty",
    "identif",
    "who performed",
    "will perform",
    "the agent id of",
)


def _how_explains_reviewer_id_placeholder(printed_text: str) -> bool:
    """True iff `printed_text` explains the `--reviewer-agent-id <id>` placeholder.

    Structural oracle for the charter's "no bare unexplained placeholder"
    negative observation: the `<id>` token must still be present (the fix
    KEEPS the placeholder -- it is genuinely session-specific) AND at least
    one explanation marker must accompany it somewhere in the printed
    message.
    """
    if "<id>" not in printed_text:
        return False
    lowered = printed_text.lower()
    return any(marker in lowered for marker in _EXPLANATION_MARKERS)


def _contains_bare_unexplained_placeholder(printed_text: str) -> bool:
    """True iff `printed_text` still carries the exact bare-today anti-pattern."""
    return (
        _BARE_PLACEHOLDER in printed_text
        and not _how_explains_reviewer_id_placeholder(printed_text)
    )


#: Generalized placeholder oracle (Vera's gap): the charter requires EVERY
#: `<...>`-shaped placeholder in EVERY notice to be actionable, not just
#: `<id>`. `<id>` is the ONLY tolerated bare token -- the reviewer-agent id
#: is genuinely session-specific, unknowable at print time. Any OTHER bare
#: `<...>` token (e.g. `<feature>`, whose value -- the `feature_id`
#: argument -- IS known at print time) is a defect: it must be FILLED with
#: the real value, not annotated, so it disappears from the printed text.
_PLACEHOLDER_TOKEN_RE = re.compile(r"<[^<>\s]+>")

_TOLERATED_BARE_PLACEHOLDERS: frozenset[str] = frozenset({"<id>"})


def _bare_placeholder_tokens(printed_text: str) -> frozenset[str]:
    """Every `<...>`-shaped token appearing verbatim in `printed_text`."""
    return frozenset(_PLACEHOLDER_TOKEN_RE.findall(printed_text))


def _has_only_tolerated_placeholders(printed_text: str) -> bool:
    """True iff `printed_text` carries no bare placeholder except `<id>`,
    and `<id>` (if present) carries its explanation.

    Structural oracle for the charter's full "every placeholder is
    actionable" requirement -- broader than
    `_how_explains_reviewer_id_placeholder`, which only ever checked `<id>`.
    A notice that annotates `<id>` perfectly but still prints a second,
    un-filled `<feature>` (or any other bare token) fails this oracle.
    """
    tokens = _bare_placeholder_tokens(printed_text)
    if not tokens <= _TOLERATED_BARE_PLACEHOLDERS:
        return False
    return not (
        "<id>" in tokens and not _how_explains_reviewer_id_placeholder(printed_text)
    )


# ---------------------------------------------------------------------------
# Fixture builders (pure filesystem -- neither helper under test touches git).
# ---------------------------------------------------------------------------


def _write_slice_plan(repo: Path, feature_id: str, slice_id: str) -> None:
    """A minimal well-formed `[REF] Slice Plan` declaring one observable slice.

    Read by `_declared_slice_plan_slice_ids` (via `_notify_feature_end_
    unmissable` -> `_last_declared_slice_shipped`) -- the SAME feature-delta
    parser `des commit-slice` itself reuses, no hand-rolled table format.
    """
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        "# Feature Delta\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {slice_id} | a maintainer can act on the printed notice | "
        "shipped | | |\n",
        encoding="utf-8",
    )


def _seed_slice_shipped(repo: Path, feature_id: str, slice_id: str) -> None:
    """Mint a real `SliceCommitVerified` ledger record for `slice_id`.

    The SAME production writer (`AtCompletionLedger.append_gate_event`) `des
    commit-slice` itself calls after a verified commit -- mirrors the proven
    precedent `tests/des/acceptance/des_e2_contract_gate_degrade_loud/steps/
    composition.py:seed_predecessor_verified_record`. Makes
    `_last_declared_slice_shipped` (read by `_notify_feature_end_unmissable`)
    return True without running a real `git commit`.
    """
    ledger = AtCompletionLedger(feature_id=feature_id, project_root=repo)
    ledger.append_gate_event(SLICE_COMMIT_VERIFIED, slice_id)


def _feature_end_notice_text(
    repo: Path, feature_id: str, capsys: pytest.CaptureFixture[str]
) -> str:
    """Drive the REAL `_notify_feature_end_unmissable` and capture its stdout."""
    _notify_feature_end_unmissable(repo, feature_id)
    return capsys.readouterr().out


def _at_review_warning_text(
    repo: Path,
    feature_id: str,
    slice_id: str,
    capsys: pytest.CaptureFixture[str],
    *,
    message: str = "fix: land the slice",
) -> tuple[str, str]:
    """Drive the REAL `_ensure_reviewed_by` and capture (stderr, returned message).

    No APPROVED `ATReviewVerdict` record exists for `slice_id` on a fresh tmp
    repo (no ledger at all) -- the WARNING-and-omit branch fires, mirroring
    the real "AT-review was never recorded" case.
    """
    returned = _ensure_reviewed_by(repo, message, [slice_id], feature_id)
    stderr_text = capsys.readouterr().err
    return stderr_text, returned


# ---------------------------------------------------------------------------
# Notice 1: FeatureEndPending (WHAT/WHY/HOW, stdout).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "feature_id",
    ["fix-feature-end-notice-actionable-how", "another-feature-63-notice"],
)
def test_feature_end_notice_explains_reviewer_agent_id_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], feature_id: str
) -> None:
    """RED reason: the FeatureEndPending HOW line ends `--reviewer-agent-id
    <id>` with zero explanatory text anywhere in the printed notice."""
    slice_id = "slice-01"
    _write_slice_plan(tmp_path, feature_id, slice_id)
    _seed_slice_shipped(tmp_path, feature_id, slice_id)

    printed = _feature_end_notice_text(tmp_path, feature_id, capsys)

    # Positive: the WHAT/WHY/HOW triple structure survives the message-text
    # fix (best-effort-LOUD notice shape is unaffected by the wording change).
    assert "WHAT:" in printed
    assert "WHY:" in printed
    assert "HOW:" in printed
    assert "<id>" in printed  # placeholder retained -- genuinely session-specific

    assert _how_explains_reviewer_id_placeholder(printed), (
        "the FeatureEndPending HOW line prints a bare, unexplained "
        "`--reviewer-agent-id <id>` -- a maintainer cannot tell what to "
        f"substitute without reading source. Printed:\n{printed}"
    )


def test_feature_end_notice_never_raises_on_ledger_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive: best-effort-LOUD is preserved -- a ledger-append failure is
    caught and printed as a WARNING, never propagated. The commit already
    succeeded by the time this notice step runs; it must never crash or
    block it, message-text fix notwithstanding.
    """
    feature_id = "fix-feature-end-notice-never-raises"
    slice_id = "slice-01"
    _write_slice_plan(tmp_path, feature_id, slice_id)
    _seed_slice_shipped(tmp_path, feature_id, slice_id)

    def _boom(self: AtCompletionLedger, *args: object, **kwargs: object) -> None:
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(AtCompletionLedger, "append_gate_event", _boom)

    _notify_feature_end_unmissable(tmp_path, feature_id)  # must not raise

    printed = capsys.readouterr().out
    assert "WARNING" in printed


# ---------------------------------------------------------------------------
# Notice 2: AT-review no-APPROVED-verdict WARNING (WHY/HOW, stderr).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slice_id", ["slice-01", "slice-02"])
def test_at_review_warning_explains_reviewer_agent_id_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], slice_id: str
) -> None:
    """RED reason: the no-APPROVED-verdict WARNING's HOW line ends
    `--reviewer-agent-id <id>` with zero explanatory text, AND (Vera's gap)
    carries a SECOND bare, unfilled `--feature-id <feature>` placeholder
    even though the real feature id is known at print time."""
    feature_id = "fix-feature-end-notice-actionable-how-review"
    original_message = "fix: land the slice"

    stderr_text, returned = _at_review_warning_text(
        tmp_path, feature_id, slice_id, capsys, message=original_message
    )

    # Positive: WHY/HOW structure + best-effort-LOUD preserved -- never
    # raises, the message is returned UNCHANGED (the trailer is OMITTED, not
    # fabricated), unaffected by the message-text fix.
    assert "WHY:" in stderr_text
    assert "HOW:" in stderr_text
    assert returned == original_message
    assert "<id>" in stderr_text  # placeholder retained -- genuinely session-specific

    assert _how_explains_reviewer_id_placeholder(stderr_text), (
        "the AT-review no-APPROVED-verdict WARNING prints a bare, "
        "unexplained `--reviewer-agent-id <id>` -- a maintainer cannot tell "
        f"what to substitute without reading source. Printed:\n{stderr_text}"
    )

    # Vera's gap (RED, new): the feature id is KNOWN at print time -- it is
    # the `feature_id` argument to `_ensure_reviewed_by` -- so the HOW line
    # must print the REAL feature id, not a bare `<feature>` placeholder.
    # Notice 1's HOW already proves this is fillable (it prints
    # `--feature-id {feature_id}` literally); notice 2 must match.
    assert f"--feature-id {feature_id}" in stderr_text, (
        "the AT-review WARNING's HOW line does not print the real feature "
        f"id ({feature_id!r}) in its `--feature-id` flag -- a maintainer "
        "cannot copy-paste the printed command as-is. Printed:\n"
        f"{stderr_text}"
    )
    assert "<feature>" not in stderr_text, (
        "the AT-review WARNING's HOW line still prints the bare, unfilled "
        "`<feature>` placeholder -- the feature id is known at print time "
        "(the `feature_id` argument) and must be filled in, not left "
        f"opaque. Printed:\n{stderr_text}"
    )


# ---------------------------------------------------------------------------
# Negative AT (GS-8): neither notice may ever regress back to the bare
# unexplained anti-pattern.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("notice_name", ["feature_end_pending", "at_review_warning"])
def test_notice_how_never_contains_bare_unexplained_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], notice_name: str
) -> None:
    """Negative AT: neither notice's HOW line may contain ANY bare,
    unexplained `<...>` placeholder -- generalized per Vera's gap.

    `<id>` is the ONLY tolerated bare token (the reviewer-agent id is
    genuinely session-specific, unknowable at print time), and even `<id>`
    must carry its explanation. Any OTHER bare `<...>` token (e.g.
    `<feature>`, whose value -- the `feature_id` argument -- IS known at
    print time) is a defect: the charter requires EVERY placeholder in
    EVERY notice to be actionable, not just `<id>`.

    RED now: notice 1 (feature_end_pending) already fills `<feature>` with
    the real id, so it passes the generalized check once `<id>` is
    explained. Notice 2 (at_review_warning) prints BOTH `<id>` (explainable)
    AND a bare, unfilled `<feature>` (`_bare_placeholder_tokens` returns
    `{"<feature>", "<id>"}`, which is NOT a subset of `{"<id>"}`) -- this is
    the exact gap Vera's examine caught: the prior AT only asserted on
    `<id>` and missed the second placeholder entirely. GREEN once the
    crafter fills `<feature>` with the real feature id in notice 2 (and
    keeps `<id>` explained in both notices).
    """
    feature_id = f"fix-feature-end-notice-{notice_name}"
    slice_id = "slice-01"

    if notice_name == "feature_end_pending":
        _write_slice_plan(tmp_path, feature_id, slice_id)
        _seed_slice_shipped(tmp_path, feature_id, slice_id)
        printed = _feature_end_notice_text(tmp_path, feature_id, capsys)
    else:
        printed, _ = _at_review_warning_text(
            tmp_path, feature_id, slice_id, capsys, message="fix: land it"
        )

    assert not _contains_bare_unexplained_placeholder(printed), (
        f"{notice_name} prints the bare, unexplained `{_BARE_PLACEHOLDER}` "
        f"pattern with no accompanying explanation. Printed:\n{printed}"
    )

    tokens = _bare_placeholder_tokens(printed)
    assert tokens <= _TOLERATED_BARE_PLACEHOLDERS, (
        f"{notice_name} prints bare `<...>` placeholder(s) other than the "
        f"tolerated `<id>`: {sorted(tokens - _TOLERATED_BARE_PLACEHOLDERS)!r} "
        "-- every placeholder in every notice must be actionable (either "
        "filled with a known value, or `<id>`, the one genuinely "
        f"session-specific token). Printed:\n{printed}"
    )
    assert _has_only_tolerated_placeholders(printed), (
        f"{notice_name} fails the full placeholder-actionability oracle: "
        "either a non-`<id>` bare token is present, or `<id>` is present "
        f"without its explanation. Printed:\n{printed}"
    )
