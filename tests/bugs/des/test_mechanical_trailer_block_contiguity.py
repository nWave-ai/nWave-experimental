"""Regression -- five independent commit-message call sites each append a
mechanical trailer with their own unconditional ``\\n\\n`` (blank-line)
separator, without ever checking whether the message ALREADY ends in a
trailer-shaped line. Chained in real ``des commit-slice`` order they compose
into a message where every append inserts its OWN blank line between the
previous trailer and its own, so only the LAST trailer survives as a real git
trailer -- the rest are invisible to any structural trailer parser (git's own
``git interpret-trailers --parse`` included), because standard git trailer
semantics recognise only the trailing CONTIGUOUS block of ``Key: value``
lines.

The five sites (RCA, empirically confirmed before authoring this test):

  1. ``src/des/cli/commit_slice.py:2344`` -- ``Slice-Id:`` stamp, inline in
     ``main()`` (``message = f"{args.message.rstrip()}\\n\\nSlice-Id: ..."``).
     Not extracted into a callable unit -- no product function exists at
     this granularity to invoke directly, so this ONE site is exercised via
     a literal, line-cited replica of the current formula rather than a
     product call (documented exception; every other site below calls the
     real product function).
  2. ``src/des/cli/commit_slice.py:2126`` (``_ensure_reviewed_by``) --
     ``Reviewed-by:`` stamp from the AT-review ledger. Exercised here via the
     REAL function, fed a REAL ``ATReviewVerdict`` record written through the
     REAL producer (``des.cli.at_review_verdict.record_at_review_verdict``,
     the exact function ``des record-at-review-verdict`` calls) -- no mock,
     no hand-rolled ledger line.
  3. ``src/des/domain/commit_attribution/attribution_trailer.py:43``
     (``apply_attribution_trailer``) -- ``Co-Authored-By:`` stamp. Exercised
     via the REAL pure function with ``enabled=True`` (the boolean precondition
     ``des.application.commit_message_attribution.attribute_commit_message``
     resolves from repo/global config before delegating to this same function
     at commit_slice.py:2365 -- config/activation resolution is a separate
     concern from the trailer-contiguity bug under test here).
  4. ``src/des/cli/commit_slice.py:1821`` (``_commit_with_placeholder``) --
     ``Gate-Scope:`` stamp. Exercised via the REAL function against a real
     temp git repository; the final message is read back with ``git log``
     (the message git itself actually stored), never hand-assembled.
  5. ``src/des/cli/commit.py:109`` (``_with_step_id_trailer``) -- the
     ``des commit`` sibling of site 1, same unconditional-``\\n\\n`` shape;
     covered by a direct call in ``test_step_id_trailer_shares_the_same_contiguity_defect``
     below (it IS a standalone, directly callable, real product function).

Oracle (GDP-8 witness corollary -- never a bare ``in`` substring check): TWO
independent structural axes must agree.

  * Axis A -- ``_last_contiguous_trailer_block``, a pure-Python re-
    implementation of git's own trailer-block rule (walk up from the end of
    the message, collect the trailing run of ``Key: value``-shaped lines,
    stop at the first blank line or non-matching line).
  * Axis B -- the REAL ``git interpret-trailers --parse`` binary, run as a
    subprocess against the exact same message text.

Both axes were independently confirmed, by hand, against the real ``git``
binary on this machine BEFORE this file was authored (see the three probe
transcripts in the authoring session): the 4-trailer chained message parses to
ONLY ``{"Gate-Scope": [...]}`` on both axes -- ``Slice-Id``, ``Reviewed-by``
and ``Co-Authored-By`` are invisible to both. That is the diagnosed defect this
file pins as a failing (RED) assertion.

No production code is modified by this file. The planned fix (a shared
``append_mechanical_trailer`` helper used by all five sites) is NOT
implemented here and NOT imported -- every assertion below runs against
TODAY's real code paths, so failures are genuine ``AssertionError``s on
observed behaviour, never import/collection errors.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from des.cli.at_review_verdict import record_at_review_verdict
from des.cli.commit import _with_step_id_trailer
from des.cli.commit_slice import _commit_with_placeholder, _ensure_reviewed_by
from des.domain.commit_attribution.attribution_trailer import (
    apply_attribution_trailer,
)
from des.domain.slice_id_trailer import extract_slice_ids


_FEATURE_ID = "trailer-contiguity-fix-at"
_SLICE_ID = "slice-01"
_GATE_SCOPE_PLACEHOLDER = (
    "0" * 68
)  # any fixed-width placeholder; value is irrelevant here

# Mirrors the FIX PREVISTO's own decision predicate verbatim -- a trailer-
# shaped line is any ``Key: value`` line where Key starts with a letter and
# contains only letters/digits/hyphens. Used ONLY as the axis-A parser's
# line-matcher; never as a bare substring/`in` check on the message.
_TRAILER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*):\s*(.*)$")


def _require_git() -> None:
    if shutil.which("git") is None:
        pytest.skip("git is unavailable; the trailer-contiguity oracle needs it")


def _init_git_repo(path: Path) -> None:
    """A minimal real git repository -- one initial commit, ready to receive
    a second commit via the REAL ``_commit_with_placeholder`` site."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(
        ["git", "add", ".gitkeep"], cwd=str(path), capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


def _commit_change_with_placeholder(repo: Path, message: str) -> str:
    """Stage a fresh file, then run the REAL site-4 function
    (``_commit_with_placeholder``); return the message git actually stored
    (read back via ``git log``, never hand-assembled)."""
    change_file = repo / "change.txt"
    change_file.write_text("content")
    subprocess.run(
        ["git", "add", "change.txt"], cwd=str(repo), capture_output=True, check=True
    )
    _commit_with_placeholder(repo, message, no_verify=True)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _last_contiguous_trailer_block(message: str) -> dict[str, list[str]]:
    """Axis A -- pure-Python re-implementation of git's trailer-block rule.

    Walks UP from the end of *message*, skipping trailing blank lines, then
    collects the trailing run of consecutive non-blank lines. If EVERY line in
    that run matches ``Key: value`` shape, that run is the trailer block
    (returned as ``{key: [values...]}`` in original order); the moment a line
    fails to match, or a blank line is hit, collection stops -- exactly the
    "last CONTIGUOUS block" rule the diagnosed bug violates.
    """
    lines = message.rstrip("\n").split("\n")
    end = len(lines)
    while end > 0 and lines[end - 1].strip() == "":
        end -= 1
    start = end
    collected: list[re.Match[str]] = []
    while start > 0:
        line = lines[start - 1]
        if line.strip() == "":
            break
        match = _TRAILER_LINE_RE.match(line)
        if not match:
            break
        collected.append(match)
        start -= 1
    result: dict[str, list[str]] = {}
    for match in reversed(collected):
        result.setdefault(match.group(1), []).append(match.group(2).strip())
    return result


def _git_interpret_trailers(message: str) -> dict[str, list[str]]:
    """Axis B -- the REAL ``git interpret-trailers --parse`` binary."""
    result = subprocess.run(
        ["git", "interpret-trailers", "--parse"],
        input=message,
        text=True,
        capture_output=True,
        check=True,
    )
    parsed: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        parsed.setdefault(key.strip(), []).append(value.strip())
    return parsed


def _seed_approved_review_verdict(repo: Path) -> None:
    """Write a REAL ``ATReviewVerdict`` record through the REAL producer --
    the exact function ``des record-at-review-verdict --verdict APPROVED``
    invokes -- so ``_ensure_reviewed_by`` (site 2) resolves a genuine
    ``record_hash`` rather than finding no verdict and omitting the trailer.
    """
    record_at_review_verdict(
        repo_root=repo,
        feature_id=_FEATURE_ID,
        slice_id=_SLICE_ID,
        verdict="APPROVED",
        reviewer_agent_id="test-reviewer",
        at_ids=["AT1"],
        at_content_hash="deadbeef",
        timestamp="2026-07-31T00:00:00Z",
        findings_summary=[],
    )


# ---------------------------------------------------------------------------
# 1. Main RED scenario -- the real 4-site chain, real order, real functions
#    (bar the one documented Slice-Id inline-formula exception).
# ---------------------------------------------------------------------------


def test_full_trailer_chain_produces_one_contiguous_git_parseable_block(
    tmp_path: Path,
) -> None:
    """BUG observable: chaining the four real append sites in `des
    commit-slice`'s real order (Slice-Id -> Reviewed-by -> Co-Authored-By ->
    Gate-Scope) must leave ALL FOUR trailers structurally visible as ONE
    contiguous trailer block -- both to a from-scratch pure-Python trailer-
    block parser (axis A) AND to the real ``git interpret-trailers --parse``
    binary (axis B). Today only the LAST-appended trailer (``Gate-Scope``)
    survives on either axis; the other three are swallowed by the blank lines
    each site inserts unconditionally.
    """
    _require_git()
    repo = tmp_path
    _init_git_repo(repo)
    _seed_approved_review_verdict(repo)

    subject = "fix(scope): subject line"
    first_paragraph = "First prose paragraph explaining the change."
    second_paragraph = (
        "Second prose paragraph, still explaining context, with its own detail."
    )
    message = f"{subject}\n\n{first_paragraph}\n\n{second_paragraph}"

    # --- site 1 (Slice-Id, commit_slice.py:2344) -- documented exception: no
    # extracted function exists; this line is a literal, line-cited replica
    # of the current inline formula, exercised identically to what main()
    # does today.
    message = f"{message.rstrip()}\n\nSlice-Id: {_SLICE_ID}"

    # --- site 2 (Reviewed-by, commit_slice.py:2126 / `_ensure_reviewed_by`) --
    # REAL function, REAL ledger record.
    message = _ensure_reviewed_by(
        repo, message, extract_slice_ids(message), _FEATURE_ID
    )
    assert "Reviewed-by:" in message, (
        "precondition failed: _ensure_reviewed_by did not stamp a Reviewed-by "
        "trailer at all -- the seeded APPROVED verdict record was not found; "
        "fix the fixture before trusting the rest of this test"
    )

    # --- site 3 (Co-Authored-By, attribution_trailer.py:43) -- REAL function.
    message = apply_attribution_trailer(message, enabled=True)
    assert "Co-Authored-By:" in message, (
        "precondition failed: apply_attribution_trailer(enabled=True) did not "
        "append the attribution trailer -- fix the fixture before trusting "
        "the rest of this test"
    )

    # --- site 4 (Gate-Scope, commit_slice.py:1821 / `_commit_with_placeholder`)
    # -- REAL function, real git commit; message read back from git itself.
    final_message = _commit_change_with_placeholder(repo, message)

    axis_a = _last_contiguous_trailer_block(final_message)
    axis_b = _git_interpret_trailers(final_message)

    expected_keys = {"Slice-Id", "Reviewed-by", "Co-Authored-By", "Gate-Scope"}

    assert expected_keys <= axis_a.keys(), (
        f"axis A (pure-Python last-contiguous-trailer-block parser) is "
        f"missing {sorted(expected_keys - axis_a.keys())} -- got block "
        f"{axis_a!r}. WHY: each of the four append sites inserts its own "
        f"unconditional blank-line separator, so only the LAST trailer forms "
        f"a contiguous run with nothing after it. Full message:\n{final_message}"
    )
    assert expected_keys <= axis_b.keys(), (
        f"axis B (real `git interpret-trailers --parse`) is missing "
        f"{sorted(expected_keys - axis_b.keys())} -- got block {axis_b!r}. "
        f"Same root cause as axis A, confirmed independently by git itself. "
        f"Full message:\n{final_message}"
    )

    # The prose body must never be rewritten, and its OWN interior blank line
    # (between the two paragraphs) must survive byte-identical -- never
    # collapsed, never duplicated -- through all four appends.
    assert f"{first_paragraph}\n\n{second_paragraph}" in final_message


# ---------------------------------------------------------------------------
# 2. Sibling-branch pin -- a single mechanical trailer after a plain prose
#    body (no pre-existing trailer) must NOT regress: exactly one blank line
#    separator, exactly one trailer key. PASSES today; must keep passing
#    after the fix lands.
# ---------------------------------------------------------------------------


def test_single_mechanical_trailer_after_prose_body_stays_correctly_separated(
    tmp_path: Path,
) -> None:
    """Neighbouring-branch pin: a message with NO pre-existing trailer must
    keep getting exactly one blank line before the newly appended mechanical
    trailer -- the fix's contiguity rule must never regress this case."""
    _require_git()
    repo = tmp_path
    _init_git_repo(repo)

    subject = "fix(scope): subject line"
    body = "Body prose paragraph explaining the change, no trailers at all."
    message = f"{subject}\n\n{body}"

    final_message = _commit_change_with_placeholder(repo, message)

    lines = final_message.rstrip("\n").split("\n")
    gate_scope_idx = next(
        index for index, line in enumerate(lines) if line.startswith("Gate-Scope:")
    )
    assert lines[gate_scope_idx - 1] == "", (
        "the mechanical trailer must remain separated from prose body by "
        "exactly one blank line when no trailer was already present"
    )
    assert lines[gate_scope_idx - 2] == body

    axis_a = _last_contiguous_trailer_block(final_message)
    axis_b = _git_interpret_trailers(final_message)
    assert set(axis_a) == {"Gate-Scope"}
    assert set(axis_b) == {"Gate-Scope"}


# ---------------------------------------------------------------------------
# 3. Declared edge-case behaviour -- a prose line that coincidentally LOOKS
#    like a trailer (`Nota: qualcosa`) must be treated, once fixed, exactly
#    per the FIX PREVISTO's own regex predicate: single-newline merge. This
#    is a KNOWN, ACCEPTED heuristic limitation (the predicate cannot
#    distinguish real trailers from coincidental prose) -- explicitly pinned
#    here rather than left undefined.
# ---------------------------------------------------------------------------


def test_appending_after_a_trailer_lookalike_prose_line_merges_per_declared_heuristic(
    tmp_path: Path,
) -> None:
    """BUG observable (declared future behaviour, explicit not implicit):
    once the shared helper's regex predicate (``^[A-Za-z][A-Za-z0-9-]*:\\s``)
    is applied, a prose line that happens to match it (e.g. ``Nota: qualcosa
    da tenere presente.``) is indistinguishable from a real trailer, so the
    newly appended mechanical trailer joins it with a SINGLE newline -- no
    blank line -- and the resulting contiguous block legitimately contains
    BOTH the coincidental prose key (``Nota``) and the appended trailer key
    (``Gate-Scope``). This is confirmed against the REAL git binary (probed
    by hand before authoring this test): git's own `interpret-trailers
    --parse` treats that exact two-line tail identically. Today's code
    inserts a blank line unconditionally, so this assertion fails now --
    the declared future contract, pinned in advance.
    """
    _require_git()
    repo = tmp_path
    _init_git_repo(repo)

    subject = "fix(scope): subject line"
    body_first = "Body prose paragraph explaining the change."
    lookalike_line = "Nota: qualcosa da tenere presente."
    message = f"{subject}\n\n{body_first}\n\n{lookalike_line}"

    final_message = _commit_change_with_placeholder(repo, message)

    lines = final_message.rstrip("\n").split("\n")
    gate_scope_idx = next(
        index for index, line in enumerate(lines) if line.startswith("Gate-Scope:")
    )
    assert lines[gate_scope_idx - 1] == lookalike_line, (
        "declared heuristic behaviour: once the last non-blank line matches "
        "the trailer-shape regex, the mechanical trailer must join it with a "
        "single newline (no blank line) -- even though this particular line "
        "is coincidental prose, not a real trailer. Got:\n" + final_message
    )

    axis_a = _last_contiguous_trailer_block(final_message)
    axis_b = _git_interpret_trailers(final_message)
    assert axis_a.get("Nota") == ["qualcosa da tenere presente."]
    assert "Gate-Scope" in axis_a
    assert axis_b.get("Nota") == ["qualcosa da tenere presente."]
    assert "Gate-Scope" in axis_b


# ---------------------------------------------------------------------------
# 4. Idempotency pins -- an already-present trailer must never be duplicated.
#    Both PASS today; must keep passing after the fix.
# ---------------------------------------------------------------------------


def test_attribution_trailer_idempotent_when_sentinel_already_present() -> None:
    """`apply_attribution_trailer` (site 3) must return the message
    byte-identical when the sentinel is already present anywhere in it --
    never a duplicate `Co-Authored-By: nWave <nwave@nwave.ai>` line."""
    message = (
        "fix(scope): subject\n\nBody prose.\n\nCo-Authored-By: nWave <nwave@nwave.ai>"
    )
    result = apply_attribution_trailer(message, enabled=True)
    assert result == message
    assert result.count("Co-Authored-By: nWave <nwave@nwave.ai>") == 1


def test_reviewed_by_trailer_idempotent_when_already_present(tmp_path: Path) -> None:
    """`_ensure_reviewed_by` (site 2) must return the message byte-identical
    when a `Reviewed-by:` line is already present -- never a duplicate stamp,
    even if the ledger has no matching APPROVED record at all (the ledger is
    never even consulted on this branch)."""
    repo = tmp_path
    message = (
        "fix(scope): subject\n\nBody prose.\n\n"
        "Slice-Id: slice-01\n\nReviewed-by: existinghash (APPROVED)"
    )
    result = _ensure_reviewed_by(repo, message, ["slice-01"], _FEATURE_ID)
    assert result == message
    assert result.count("Reviewed-by:") == 1


def test_slice_id_extraction_recognizes_an_already_present_trailer() -> None:
    """`extract_slice_ids` (real function `main()` branches on at
    commit_slice.py:2332 -- `if not extract_slice_ids(args.message): ...
    else: preserve as-is`) must recognize an already-present `Slice-Id:`
    trailer as non-empty, so main()'s real branch preserves the message
    as-is rather than appending a second stamp."""
    message = "fix(scope): subject\n\nBody prose.\n\nSlice-Id: slice-01"
    assert extract_slice_ids(message) == ["slice-01"]


# ---------------------------------------------------------------------------
# 5. `des commit`'s sibling site (commit.py:109) shares the identical defect
#    shape -- covered directly since `_with_step_id_trailer` IS a standalone,
#    directly callable, real product function (no repo/ledger needed).
# ---------------------------------------------------------------------------


def test_step_id_trailer_shares_the_same_contiguity_defect() -> None:
    """BUG observable: `_with_step_id_trailer` (commit.py:109, the `des
    commit` sibling of site 1) also appends its `Step-Id:` trailer with an
    unconditional `\\n\\n`, so chaining it after an already-trailer-ending
    message breaks contiguity exactly like the other four sites."""
    message = "fix(scope): subject\n\nBody prose.\n\nSlice-Id: slice-01"
    result = _with_step_id_trailer(message, "02-03")

    axis_a = _last_contiguous_trailer_block(result)
    axis_b = _git_interpret_trailers(result) if shutil.which("git") else None

    assert {"Slice-Id", "Step-Id"} <= axis_a.keys(), (
        f"axis A: Slice-Id is swallowed by the blank line _with_step_id_trailer "
        f"unconditionally inserts before Step-Id. Got block {axis_a!r} for:\n"
        f"{result}"
    )
    if axis_b is not None:
        assert {"Slice-Id", "Step-Id"} <= axis_b.keys(), (
            f"axis B (real git): same defect, confirmed independently. Got "
            f"block {axis_b!r} for:\n{result}"
        )


def test_step_id_trailer_not_duplicated_when_already_present() -> None:
    """`_with_step_id_trailer` must return the message byte-identical when a
    `Step-Id:` trailer is already present -- never a duplicate stamp."""
    message = "fix(scope): subject\n\nBody prose.\n\nStep-Id: 02-03"
    result = _with_step_id_trailer(message, "02-03")
    assert result == message
