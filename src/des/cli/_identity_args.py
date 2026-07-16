"""Shared identity-argument primitive for the DES CLI surface.

``meaningful_identity`` is the canonical ``argparse`` ``type=`` normalizer
for any identity-bearing CLI argument (``--repo``, ``--feature-id``,
``--slice-id``, ``--reviewer-agent-id``, ...): a value that is PRESENT
(argparse-wise) but MEANINGLESS -- blank or whitespace-only, however the
nothing is spelled -- is normalized to ``None`` at the parse boundary, so a
downstream ``is not None`` guard cannot be fooled by a value that LOOKS
present and names nothing.

Extracted verbatim from ``commit_slice.py`` (2026-07-14, bugfix
fix-at-review-verdict-surface slice-01, RCA
``docs/feature/fix-at-review-verdict-surface/deliver/rca.md``) so a sibling
CLI (``at_review_verdict.py``) can reuse the identical primitive instead of
re-deriving it -- one definition, two consumers. Behaviour is byte-identical
to the original ``commit_slice.py:_meaningful_or_absent``; only the module
changed.
"""

from __future__ import annotations


def meaningful_identity(raw: str) -> str | None:
    """argparse ``type=``: a PRESENT-but-MEANINGLESS value IS an absent one.

    THE BUG CLASS THIS CLOSES (2026-07-14, found by an independent examiner):
    ``--feature-id ""`` walked straight past a ``if args.feature_id is not
    None`` refusal -- **an empty string is not None**. Every downstream gate
    then scoped itself to a feature literally named ``""``, matched nothing,
    verified nothing, and reported success: the run printed "nothing was
    verified, so this is not a pass" and in the same breath wrote
    ``SliceCommitted{verified: true}``, exit 0, commit landed, with a
    ``Gate-Scope`` digest that was the sha256 of the EMPTY STRING.

    The lesson generalizes past the empty string, so the FIX does too. The
    question a guard must ask is NOT "was a value supplied?" (identity --
    ``is None``) but **"do I have a value I can actually scope a gate to?"**
    (meaning). Empty, whitespace-only -- however the nothing is spelled -- it
    is nothing, and it is normalized to ``None`` HERE, at the parse boundary,
    so a meaningless identity cannot enter the program at all. The refusal
    downstream then fires on ``is None`` and cannot be escaped by an argument.

    A guard a flag can switch off is not a guard. Anything identity-bearing
    (``--feature-id``, ``--slice-id``, ``--repo``) gets this normalizer;
    ``is not None`` on a raw string that could arrive blank is the same bug
    wearing a different flag name.
    """
    stripped = raw.strip()
    return stripped or None
