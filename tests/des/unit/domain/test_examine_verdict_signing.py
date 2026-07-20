"""Regression: charter_seal must ignore the examiner's own Session-log append.

Bug (recurring friction): ``des record-examine-verdict`` seals the charter's
bytes at exam time (``charter_seal``). ``nw-user-examiner`` then appends
exactly one row to the SAME charter's ``## Session log (append-only)`` table
as its normal LOG + REPORT step -- AFTER the verdict is recorded. Today
``charter_seal`` hashes the charter's FULL bytes, so that append changes the
seal -- the examiner's own audit-trail row voids its own PASS verdict, and
``des commit-slice`` spuriously refuses with ``ExamineVerdictStale`` even
though nothing about the charter's SUBSTANCE (intent/oracle/start-recipe)
changed.

Fix (crafter's job, NOT this file): ``charter_seal`` must hash only the
charter's SUBSTANCE -- everything BEFORE the append-only ``## Session log``
section -- never the session-log rows themselves. A genuine edit to the
substance must still change the seal (the verdict must still go stale).

RED today: appending a session-log row changes ``charter_seal`` output, so
the "seal unchanged after append" assertions below fail for the right
reason (real ``AssertionError``, not a collection/import error).

CONTRACT_SHAPE: pure-function
Universe: charter_seal(bytes) -> str (hex digest); check_examine_verdict
return value (None == cleared, dict == refusal).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.commit_slice import check_examine_verdict
from des.cli.record_examine_verdict import record_examine_verdict
from des.domain.examine_verdict_signing import charter_seal


_CHARTER_SUBSTANCE = """# A visitor completes checkout
ID: EXP-checkout-1 · Spec rows: R1 · Persona: a visitor buying a ticket

## Intent
A visitor completes checkout and sees an order confirmation.

## Preconditions
`npm run dev` → app at http://localhost:3000. Seed: one event, seats available.

## Charter
Explore checkout via the browser to verify the confirmation appears.

## Expected observations (oracle)
- A confirmation banner appears after checkout completes.
- Negative: the banner must NOT appear before checkout is submitted.
"""

_SESSION_LOG_HEADER = (
    "\n## Session log (append-only)\n"
    "| date | examiner | verdict | observations |\n"
    "|------|----------|---------|--------------|\n"
)

_SESSION_LOG_ROW = (
    "| 2026-07-08 | nw-user-examiner | PASS | Checkout confirmed, banner shown. |\n"
)


def _charter_text(*extra_session_log_rows: str) -> str:
    """A well-formed charter: substance + Session-log header + N logged rows."""
    return _CHARTER_SUBSTANCE + _SESSION_LOG_HEADER + "".join(extra_session_log_rows)


def test_charter_seal_unchanged_after_examiner_appends_session_log_row():
    """Appending the examiner's Session-log row must NOT change the seal."""
    before_bytes = _charter_text().encode("utf-8")
    after_bytes = _charter_text(_SESSION_LOG_ROW).encode("utf-8")

    assert charter_seal(before_bytes) == charter_seal(after_bytes)


def test_charter_seal_unchanged_across_multiple_session_log_appends():
    """A second (later) examiner's append must also leave the seal unchanged."""
    before_bytes = _charter_text(_SESSION_LOG_ROW).encode("utf-8")
    second_row = (
        "| 2026-07-09 | nw-user-examiner | PASS | Re-verified after a rebase. |\n"
    )
    after_bytes = _charter_text(_SESSION_LOG_ROW, second_row).encode("utf-8")

    assert charter_seal(before_bytes) == charter_seal(after_bytes)


def test_charter_seal_still_changes_when_substance_is_edited():
    """Negative-AT: a real edit to the charter's SUBSTANCE must still stale the seal.

    The fix must not blanket-ignore all post-record changes -- only the
    append-only Session-log section is exempt. Editing the Intent/Preconditions/
    Charter/Expected-observations body must still change the seal so a genuine
    post-record charter edit still voids the recorded verdict.
    """
    original_bytes = _charter_text().encode("utf-8")
    edited_substance = _CHARTER_SUBSTANCE.replace(
        "A visitor completes checkout and sees an order confirmation.",
        "A visitor completes checkout and sees an order confirmation AND a receipt email.",
    )
    edited_bytes = (edited_substance + _SESSION_LOG_HEADER).encode("utf-8")

    assert charter_seal(original_bytes) != charter_seal(edited_bytes)


def test_record_then_examiner_append_does_not_stale_the_recorded_verdict(
    tmp_path: Path,
):
    """End-to-end: record a PASS verdict, then append a session-log row the
    way ``nw-user-examiner`` does -- the commit-time gate must still clear
    (``check_examine_verdict`` returns ``None``), never ``ExamineVerdictStale``.
    """
    repo = tmp_path
    feature_id = "checkout-flow"
    slice_id = "slice-01"
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True)
    charter_path = charter_dir / "visitor-completes-checkout.md"
    charter_path.write_text(_charter_text(), encoding="utf-8")

    record_examine_verdict(
        repo=repo,
        feature_id=feature_id,
        slice_id=slice_id,
        charter_path=charter_path,
        verdict="PASS",
        observations="Checkout confirmed end to end.",
        examiner="nw-user-examiner",
        timestamp="2026-07-08T12:00:00Z",
    )

    # The examiner's normal LOG + REPORT step: append exactly one row to the
    # SAME charter's Session log, after the verdict was recorded.
    charter_path.write_text(_charter_text(_SESSION_LOG_ROW), encoding="utf-8")

    refusal = check_examine_verdict(repo, feature_id, slice_id)

    assert refusal is None


# Real-world charters do NOT all use the exact ``## Session log (append-only)``
# heading the scaffold emits -- 35 of 200 checked-in charters (2026-07-20) use a
# variant (``## Session Log`` capital-L, ``## Session log`` without the
# ``(append-only)`` suffix). A literal-string exclusion silently fails for those,
# so the examiner's own append still stales a genuine PASS -- the exact
# F-EXAMINE-SESSION-LOG-APPEND-INVALIDATES-CHARTER-SEAL symptom, still live.
_SESSION_LOG_HEADING_VARIANTS = (
    "## Session log (append-only)",  # canonical (scaffold/template)
    "## Session Log",  # capital-L, no suffix (real charters)
    "## Session log",  # lowercase, no suffix (real charters)
    "## Session Log (append-only)",  # capital-L WITH suffix
)


@pytest.mark.parametrize("heading", _SESSION_LOG_HEADING_VARIANTS)
def test_charter_seal_unchanged_after_append_across_heading_variants(heading: str):
    """The append exemption must hold for every real Session-log heading spelling.

    The exclusion keys on the heading text; if it hard-matches one exact string,
    a case/suffix variant is not excluded and the examiner's own row stales the
    seal. All spellings that appear in real charters must be exempted.
    """
    header = (
        f"\n{heading}\n"
        "| date | examiner | verdict | observations |\n"
        "|------|----------|---------|--------------|\n"
    )
    before_bytes = (_CHARTER_SUBSTANCE + header).encode("utf-8")
    after_bytes = (_CHARTER_SUBSTANCE + header + _SESSION_LOG_ROW).encode("utf-8")

    assert charter_seal(before_bytes) == charter_seal(after_bytes)


@pytest.mark.parametrize("heading", _SESSION_LOG_HEADING_VARIANTS)
def test_charter_seal_still_stales_on_substance_edit_across_heading_variants(
    heading: str,
):
    """Tolerating heading variants must NOT weaken the tamper-evidence: a real
    edit to the SUBSTANCE (before the Session-log heading) still stales the seal.
    """
    header = f"\n{heading}\n| date | examiner | verdict | observations |\n"
    original_bytes = (_CHARTER_SUBSTANCE + header).encode("utf-8")
    edited_substance = _CHARTER_SUBSTANCE.replace(
        "A visitor completes checkout and sees an order confirmation.",
        "A visitor completes checkout and sees an order confirmation AND a receipt.",
    )
    edited_bytes = (edited_substance + header).encode("utf-8")

    assert charter_seal(original_bytes) != charter_seal(edited_bytes)
