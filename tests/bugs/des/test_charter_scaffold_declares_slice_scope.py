"""Regression AT (fix-charter-scaffold-placeholder-scope, slice-01).

The defect (feature-delta DD-1..DD-3): `des charter-scaffold --seed-mode
slice-plan` copies the charter template's `ID:` line verbatim into every
scaffold it writes -- `Spec rows: <R...>`, the template's own literal
placeholder -- even though the tool already knows the feature-id and read the
Slice Plan row to decide the row was OBSERVABLE. `_fill_intent_section`
(`src/des/cli/charter_scaffold.py`) only ever replaces the `## Intent` body;
the `ID:` line above it is never touched.

`resolve_slice_charter` (`src/des/domain/expectation_charter_mapping.py:153`)
accepts `Spec rows:` only as comma-separated `slice-NN` values. Fed the
scaffold's own output, it returns `CharterMappingState.INDETERMINATE` with
detail "maps `Spec rows:` to '<R...> ', not comma-separated `slice-NN`
values" -- the tool produces a charter its own sibling reader cannot resolve.

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`): NOT a
missing-module RED -- both `des.cli.charter_scaffold` and
`des.domain.expectation_charter_mapping` are already shipped. This is a
BEHAVIOURAL RED: each test drives the real, already-shipped
`des.cli.charter_scaffold.main(argv)` end to end, then feeds the produced
charter into the real, already-shipped
`des.domain.expectation_charter_mapping.resolve_slice_charter`, and asserts
the DESIRED (not-yet-true) outcome -- `ARMED` for the slice the charter was
generated for. The CURRENT implementation's actual outcome (`INDETERMINATE`)
makes the assertion raise a plain `AssertionError` -- fail for the right
reason, never a collection/import error.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` (the producer)
composed with `des.domain.expectation_charter_mapping.resolve_slice_charter`
(the consumer) -- both real, both invoked IN-PROCESS against a `tmp_path`
fixture repo (composition-root driving ports -- Mandate 16, driving-port-only
boundary). No subprocess fork; no direct-domain reach into
`_scaffold_slice`/`_fill_intent_section` internals.

Obligation map (feature-delta DoD + the t=0 charter's negative oracles,
`docs/product/expectations/fix-charter-scaffold-placeholder-scope/
a-scaffolded-charter-declares-which-slice-it-covers.md`):

  1. The fix                -> test_scaffolded_charter_resolves_armed_for_its_own_slice
  2. Not one hardcoded id   -> test_two_slices_yield_two_charters_with_distinct_resolvable_scope
  3. No clobber             -> test_rerun_never_clobbers_a_hand_filled_charter
  4. No dodging by refusing -> test_two_slices_yield_two_charters_with_distinct_resolvable_scope
                                (verdict/created-count assertions)
  5. Success must not lie   -> test_accepted_verdict_never_coexists_with_an_unresolved_placeholder_token
                                (NEGATIVE assertion)
  6. Delimiter spacing      -> test_scaffolded_id_line_keeps_canonical_spacing_around_spec_rows_delimiter
                                (`_fill_spec_rows_field`'s `_SPEC_ROWS_FIELD_RE` substitution
                                swallows the ID line's trailing space before the `·` that
                                follows the scope field -- a FORMATTING defect in the producer,
                                not a resolution failure)
  7. Template ships a value
     its own reader rejects  -> SPLIT (O4, 2026-07-30) into
                                test_shipped_template_worked_examples_parse_under_the_readers_grammar
                                (worked examples must parse) and
                                test_shipped_template_fence_placeholder_is_recognisably_unfilled
                                (NEGATIVE -- the fence placeholder must NOT parse; the original
                                single test conflated the two and was itself satisfied by the
                                silent-wrong commit b7f63c54e that turned the fence's `<R…>` into
                                the concrete, parseable `slice-01`)

Obligation map -- feature-delta amendment (2026-07-30, DD-1..DD-3, human-granted
forward-only for the two feature-level scope tokens):

  O1. Producer refuses a duplicate
      slice-id, LOUD             -> test_duplicate_slice_id_in_slice_plan_refuses_loud_and_writes_zero_charters
                                     (converse -- distinct ids still scaffold -- already pinned by
                                     obligation 2/4's test above; not duplicated)
  O2. Non-slice seed modes stamp
      their OWN identifier        -> test_non_slice_seed_modes_stamp_their_own_identifier_never_a_slice_id
  O3. Reader admits those tokens
      as deliberate feature-level
      scope; slice-scoped charter
      takes PRECEDENCE over a
      feature-level sibling; two
      feature-level charters
      sharing one token stay
      ambiguous; refusal for
      every other token is
      unchanged                   -> test_feature_level_scope_token_resolves_deliberate_not_indeterminate,
                                     test_slice_scoped_charter_takes_precedence_over_a_sibling_feature_level_charter,
                                     test_two_feature_level_charters_sharing_the_same_scope_token_are_genuinely_ambiguous,
                                     test_non_first_class_scope_tokens_still_refuse_indeterminate

      (deliberately does NOT pin a new `CharterMappingState` member --
      `src/des/cli/dispatch.py:1988`'s `C_REVIEWER_AUDIT` branch is the
      ONLY production caller and its `else` would refuse a new state with
      a LYING "no charter maps this slice" message; see the precedence
      test's docstring)
  O4. Correct the AT that caused
      O2's defect                 -> see obligation 7 above (SPLIT) plus the two new
                                     parametrize cases on
                                     test_accepted_verdict_never_coexists_with_an_unresolved_placeholder_token
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from des.cli.validate_feature_delta import VERDICT_ACCEPTED
from des.domain.expectation_charter_mapping import (
    _SLICE_ID_PATTERN,
    _SPEC_ROWS_PATTERN,
    CharterMappingState,
    resolve_slice_charter,
)


FEATURE_ID = "charter-scope-fix"

#: The shipped template `des charter-scaffold` copies -- the SAME file
#: `_seed_repo` mirrors byte-faithfully into the fixture repo (`TEMPLATE_SKELETON`
#: below is the "Template" fence's content only; this path is the real file on
#: disk, used by obligation 7 to scan ALL three `Spec rows:` occurrences --
#: the fence AND both worked examples).
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "nWave"
    / "templates"
    / "expectation-charter.md"
)

#: The real, shipped `nWave/templates/expectation-charter.md` "Template"
#: skeleton (byte-faithful copy), seeded into the fixture repo at the
#: repo-root-relative path the tool reads it from. Its `ID:` line carries the
#: literal placeholder (`Spec rows: <R...>`) this defect is about -- copying
#: it verbatim is exactly the bug.
TEMPLATE_SKELETON = """# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""

VALUE_STATEMENT_1 = "A visitor books a seat and receives a confirmation"
VALUE_STATEMENT_2 = "A visitor cancels a booking before the show starts"

SINGLE_SLICE_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT_1} | pending |  | only observable slice |
"""

TWO_SLICE_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT_1} | pending |  | first observable slice |
| slice-02 | {VALUE_STATEMENT_2} | pending |  | second observable slice |
"""

#: O1 fixture data (2026-07-30) -- the SAME slice id ('slice-01') declared
#: TWICE with two DIFFERENT Value statements. Distinct statements guarantee
#: distinct kebab-slugs, so today's (unfixed) scaffolder happily writes two
#: separate files -- exactly the measured baseline the dispatch cites.
VALUE_STATEMENT_DUP_A = "A shopper adds a coupon code at checkout"
VALUE_STATEMENT_DUP_B = "A shopper removes a coupon code at checkout"

DUPLICATE_SLICE_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT_DUP_A} | pending |  | first duplicate |
| slice-01 | {VALUE_STATEMENT_DUP_B} | pending |  | second duplicate |
"""

#: O2/O3/O4 fixture data (2026-07-30) -- the non-slice `--seed-mode` inputs.
#: Named module-level so every test that drives one of these two seed modes
#: (O2, O3, the extended obligation-5 negative test) shares the SAME literal
#: text, rather than each re-declaring its own snippet.
BUG_OBSERVABLE_TEXT = "the export button does nothing"
BROWNFIELD_AREA_TEXT = "the legacy export pipeline"


def _seed_repo(repo_root: Path) -> None:
    """Seed the one repo-root-relative asset the tool reads regardless of
    scenario: the expectation-charter template."""
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        TEMPLATE_SKELETON, encoding="utf-8"
    )


def _write_feature_delta(repo_root: Path, feature_id: str, content: str) -> Path:
    delta_dir = repo_root / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    path = delta_dir / "feature-delta.md"
    path.write_text(content, encoding="utf-8")
    return path


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _spec_rows_value(content: str) -> str:
    """Test-local parser (mirrors, but does not import, the production
    `_SPEC_ROWS_PATTERN`) -- the raw text of the `ID:` line's `Spec rows:`
    field, up to the next `·` separator or end of line."""
    for line in content.splitlines():
        if line.startswith("ID:"):
            match = re.search(r"Spec rows:\s*([^·\n]+)", line)
            if match:
                return match.group(1).strip()
    return ""


def _invoke(
    repo_root: Path,
    capsys,
    feature_id: str = FEATURE_ID,
    extra_args: list[str] | None = None,
) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()`, stdout
    captured and parsed as the `--format json` contract token.

    `extra_args` appends CLI flags after the base quartet (e.g.
    `--seed-mode bug-observable --observable "..."`) -- extended (O2/O3/O4,
    2026-07-30) so every seed mode drives through this SAME helper, never a
    parallel invocation path."""
    from des.cli.charter_scaffold import main

    argv = [
        "--feature-id",
        feature_id,
        "--repo-root",
        str(repo_root),
        "--format",
        "json",
    ]
    if extra_args:
        argv.extend(extra_args)
    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


# ===========================================================================
# Obligation 1 -- the fix itself.
# ===========================================================================


def test_scaffolded_charter_resolves_armed_for_its_own_slice(
    tmp_path: Path, capsys
) -> None:
    """A charter scaffolded for slice-01 must resolve `ARMED` when the
    downstream scope resolver (`resolve_slice_charter`) is asked "which
    charter covers slice-01" -- not `INDETERMINATE`. The scaffolder already
    knows the answer (it read the Slice Plan row); it must write it down in a
    form its own sibling reader accepts."""
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SINGLE_SLICE_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)
    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert len(payload["created"]) == 1

    mapping = resolve_slice_charter(tmp_path, FEATURE_ID, "slice-01")

    assert mapping.state == CharterMappingState.ARMED, (
        "expected slice-01 to resolve ARMED against its own freshly-"
        f"scaffolded charter, got state={mapping.state!r} "
        f"detail={mapping.detail!r} -- the scaffold writes 'Spec rows: "
        "<R...>' verbatim from the template instead of the slice it was "
        "actually generated for"
    )

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    created_path = expectations_dir / payload["created"][0]
    assert mapping.charter_path == created_path

    content = created_path.read_text(encoding="utf-8")
    assert _spec_rows_value(content) == "slice-01", (
        f"scaffolded charter's 'Spec rows:' field is {_spec_rows_value(content)!r}, "
        "expected the literal 'slice-01' grammar `resolve_slice_charter` accepts"
    )


# ===========================================================================
# Obligations 2 + 4 -- not one hardcoded id, and no dodging by refusing.
# ===========================================================================


def test_two_slices_yield_two_charters_with_distinct_resolvable_scope(
    tmp_path: Path, capsys
) -> None:
    """A feature with TWO observable slices must yield two charters that
    resolve to two DIFFERENT slice references -- never the same value
    stamped twice. A "fix" that hardcodes a single slice id (e.g. always
    'slice-01') into every scaffold must be caught here: the second slice
    would then fail to resolve ARMED, or both charters would collide on the
    same slice.

    Also pins obligation 4: the fix must not achieve compliance by making
    the scaffolder refuse to scaffold, or by returning an empty `created`
    list -- a normal two-slice feature still yields `verdict: accepted` with
    2 created charters.
    """
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, TWO_SLICE_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    # Obligation 4 -- no dodging by refusing.
    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert len(payload["created"]) == 2

    mapping_1 = resolve_slice_charter(tmp_path, FEATURE_ID, "slice-01")
    mapping_2 = resolve_slice_charter(tmp_path, FEATURE_ID, "slice-02")

    assert mapping_1.state == CharterMappingState.ARMED, (
        f"slice-01 did not resolve ARMED: state={mapping_1.state!r} "
        f"detail={mapping_1.detail!r}"
    )
    assert mapping_2.state == CharterMappingState.ARMED, (
        f"slice-02 did not resolve ARMED: state={mapping_2.state!r} "
        f"detail={mapping_2.detail!r}"
    )

    # Obligation 2 (negative) -- never the same value repeated twice.
    assert mapping_1.charter_path != mapping_2.charter_path, (
        "slice-01 and slice-02 resolved to the SAME charter file "
        f"({mapping_1.charter_path!r}) -- the scope was stamped with one "
        "hardcoded slice id instead of the slice each charter was actually "
        "generated for"
    )

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    assert mapping_1.charter_path == expectations_dir / next(
        f for f in payload["created"] if f == mapping_1.charter_path.name
    )
    content_1 = mapping_1.charter_path.read_text(encoding="utf-8")
    content_2 = mapping_2.charter_path.read_text(encoding="utf-8")
    assert _spec_rows_value(content_1) == "slice-01"
    assert _spec_rows_value(content_2) == "slice-02"


# ===========================================================================
# Obligation 3 -- no clobber of a hand-filled charter.
# ===========================================================================


def test_rerun_never_clobbers_a_hand_filled_charter(tmp_path: Path, capsys) -> None:
    """Re-running `des charter-scaffold` over a feature whose charter a human
    already filled must leave that file byte-identical -- the tool documents
    itself as idempotent, and the scope fix must not change that."""
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, TWO_SLICE_FEATURE_DELTA)

    first_exit, first_payload = _invoke(tmp_path, capsys)
    assert first_exit == 0
    assert len(first_payload["created"]) == 2

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    hand_filled_path = expectations_dir / first_payload["created"][0]
    hand_filled_content = (
        "# A human-authored charter\n"
        "ID: EXP-charter-scope-fix-1 · Spec rows: slice-01 · "
        "Persona: a visitor booking a seat\n\n"
        "## Intent\nHand-filled by a human PO; must survive any re-run.\n"
    )
    hand_filled_path.write_text(hand_filled_content, encoding="utf-8")

    second_exit, second_payload = _invoke(tmp_path, capsys)

    assert second_exit == 0
    assert second_payload["created"] == [], (
        "a second run created NEW files instead of treating both existing "
        f"scaffolds as idempotent skips: {second_payload['created']!r}"
    )
    assert hand_filled_path.read_text(encoding="utf-8") == hand_filled_content, (
        "re-running des charter-scaffold over a feature with a hand-filled "
        "charter rewrote/clobbered that file"
    )


# ===========================================================================
# Obligation 5 -- success must not lie (NEGATIVE assertion).
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "feature_delta_content,extra_args,expected_created_count,expected_spec_rows",
    [
        pytest.param(SINGLE_SLICE_FEATURE_DELTA, [], 1, None, id="single_slice"),
        pytest.param(TWO_SLICE_FEATURE_DELTA, [], 2, None, id="two_slices"),
        # O4 (2026-07-30): the same negative oracle, extended to the two
        # non-slice seed modes -- neither reads a Slice Plan, so
        # `feature_delta_content` is None (no feature-delta written at all).
        pytest.param(
            None,
            [
                "--seed-mode",
                "bug-observable",
                "--observable",
                BUG_OBSERVABLE_TEXT,
            ],
            1,
            "bug-observable",
            id="bug_observable",
        ),
        pytest.param(
            None,
            [
                "--seed-mode",
                "brownfield-discovery",
                "--area",
                BROWNFIELD_AREA_TEXT,
            ],
            1,
            "brownfield-discovery",
            id="brownfield_discovery",
        ),
    ],
)
def test_accepted_verdict_never_coexists_with_an_unresolved_placeholder_token(
    tmp_path: Path,
    capsys,
    feature_delta_content: str | None,
    extra_args: list[str],
    expected_created_count: int,
    expected_spec_rows: str | None,
) -> None:
    """Negative oracle (the t=0 charter's own words): no created charter may
    carry an unresolved `<...>` token in its scope field while the
    scaffolder's own JSON reports `verdict: accepted` -- a claimed success
    must never coexist with an unusable header, for a single-slice feature,
    a multi-slice one, OR either non-slice seed mode (O4, 2026-07-30).

    The two ORIGINAL slice-plan cases are UNCHANGED. The two NEW non-slice
    cases add the check that actually protects the user: `expected_spec_rows`
    pins the scaffolder's OWN identifier, not merely "not empty and no angle
    brackets" -- the angle-bracket check alone is exactly the loophole O2's
    defect slipped through (the template's fence default, 'slice-01', is
    non-empty and carries no `<...>` token, so it silently passed the
    original oracle while still being a fabricated claim)."""
    _seed_repo(tmp_path)
    if feature_delta_content is not None:
        _write_feature_delta(tmp_path, FEATURE_ID, feature_delta_content)

    exit_code, payload = _invoke(tmp_path, capsys, extra_args=extra_args)

    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert len(payload["created"]) == expected_created_count

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    for filename in payload["created"]:
        content = (expectations_dir / filename).read_text(encoding="utf-8")
        spec_rows_value = _spec_rows_value(content)
        assert spec_rows_value, f"{filename}: no 'Spec rows:' field found at all"
        assert not re.search(r"<[^>]*>", spec_rows_value), (
            f"{filename}: 'Spec rows:' field still carries an unresolved "
            f"placeholder token ({spec_rows_value!r}) while the scaffolder "
            "reported 'verdict': 'accepted' -- a claimed success must never "
            "coexist with an unusable header"
        )
        if expected_spec_rows is not None:
            assert spec_rows_value == expected_spec_rows, (
                f"{filename}: 'Spec rows:' field is {spec_rows_value!r} "
                "while 'verdict': 'accepted' -- a claimed success must "
                f"carry the scaffolder's own identifier "
                f"({expected_spec_rows!r}), never the template's untouched "
                "default"
            )


# ===========================================================================
# Obligation 6 -- the fix eats a whitespace (delimiter-spacing FORMATTING
# defect, not a resolution failure -- `resolve_slice_charter` still parses
# the produced line fine; this pins the ID line's own cosmetic contract).
# ===========================================================================


def _delimiter_spacing_around_spec_rows(id_line: str) -> tuple[str, str]:
    """The whitespace run immediately BEFORE and AFTER the `·` delimiter that
    follows the `Spec rows:` field on one `ID:` line. Test-local, string-only
    (deliberately NOT the production `_SPEC_ROWS_FIELD_RE` -- that regex IS
    the defect under test; re-using it here would make the test tautological).

    Locates the substring starting at the `Spec rows:` marker, then the
    first `·` after it, and returns `(pre, post)` -- the space/tab run
    immediately touching that delimiter on each side. Deliberately scoped to
    ONLY that one delimiter (not the whole line) -- the persona/ID
    placeholders either side are out of scope for this obligation.
    """
    marker = "Spec rows:"
    start = id_line.index(marker)
    delim_idx = id_line.index("·", start)

    pre_end = delim_idx
    pre_start = pre_end
    while pre_start > start and id_line[pre_start - 1] in " \t":
        pre_start -= 1
    pre = id_line[pre_start:pre_end]

    post_start = delim_idx + 1
    post_end = post_start
    while post_end < len(id_line) and id_line[post_end] in " \t":
        post_end += 1
    post = id_line[post_start:post_end]

    return pre, post


def test_scaffolded_id_line_keeps_canonical_spacing_around_spec_rows_delimiter(
    tmp_path: Path, capsys
) -> None:
    """`_fill_spec_rows_field`'s substitution replaces the ENTIRE
    `Spec rows:\\s*<value>` match (including the trailing space the value's
    `[^·\\n]+` capture swallows) with `Spec rows: <slice-id>` -- dropping the
    single space the template's own `ID:` line carries before the `·` that
    follows the scope field. Observed verbatim from the real producer:

        produced:  ID: EXP-<feature>-<n> · Spec rows: slice-01· Persona: <who>
        canonical: ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

    `resolve_slice_charter` still parses the produced line (it splits on `·`
    and strips) -- this is a FORMATTING defect in the producer's own output,
    not a resolution failure. Assert delimiter spacing only, not the whole
    line byte-for-byte -- a whole-line assertion would over-pin the
    persona/ID placeholders, which are out of scope here."""
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SINGLE_SLICE_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)
    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert len(payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    content = (expectations_dir / payload["created"][0]).read_text(encoding="utf-8")
    id_line = next(line for line in content.splitlines() if line.startswith("ID:"))

    pre, post = _delimiter_spacing_around_spec_rows(id_line)

    assert pre == " ", (
        f"ID line {id_line!r}: expected a single space before the '·' that "
        f"follows 'Spec rows:', got {pre!r} -- the scope substitution ate "
        "the template's own delimiter spacing"
    )
    assert post == " ", (
        f"ID line {id_line!r}: expected a single space after the '·' that "
        f"follows 'Spec rows:', got {post!r}"
    )


# ===========================================================================
# Obligation 7 -- SPLIT (O4, 2026-07-30). The original single test conflated
# two different properties -- a WORKED EXAMPLE must be valid; a PLACEHOLDER
# must be unmistakably UNFILLED, and therefore must NOT parse as a real
# scope -- and satisfying it the cheap way (turning the fence's `<R…>` into
# the concrete, parseable `slice-01`, commit b7f63c54e) is how the O2 defect
# was born: an unfilled charter stopped being recognisable as unfilled.
# ===========================================================================

#: Match any level-2 Markdown heading, INCLUDING the ones nested inside the
#: template's own fenced `markdown` blocks (e.g. the fenced skeleton's own
#: `## Intent` / `## Preconditions` / ... headings) -- deliberately not
#: fence-aware. `_spec_rows_occurrences_by_section` only ever needs the
#: NEAREST heading preceding each match, and every `Spec rows:` line in the
#: shipped template sits immediately after its own real section heading and
#: strictly before any fence-internal heading, so the nearest-preceding
#: heading is always the correct label regardless of fence nesting.
_H2_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _spec_rows_occurrences_by_section(content: str) -> list[tuple[str, str]]:
    """`[(nearest preceding '##' heading text, raw 'Spec rows:' value), ...]`
    in document order. Pure, test-local.

    Labels each `_SPEC_ROWS_PATTERN` match (imported from the production
    reader, never re-declared) with the section it lives in, so the
    '## Template' fence placeholder can be told apart from the
    '## Example (filled...)' worked examples -- the split this obligation
    needs."""
    headings = [
        (match.start(), match.group(1)) for match in _H2_HEADING_RE.finditer(content)
    ]
    occurrences: list[tuple[str, str]] = []
    for match in _SPEC_ROWS_PATTERN.finditer(content):
        enclosing = ""
        for pos, heading in headings:
            if pos <= match.start():
                enclosing = heading
            else:
                break
        occurrences.append((enclosing, match.group(1).strip()))
    return occurrences


def test_shipped_template_worked_examples_parse_under_the_readers_grammar() -> None:
    """Obligation 7a (O4 split). Every `Spec rows:` value inside a
    '## Example (filled...)' section of the shipped
    `nWave/templates/expectation-charter.md` -- the `## Template` fence is
    OUT OF SCOPE here, see obligation 7b below -- must resolve under the SAME
    grammar `resolve_slice_charter` (`des.domain.expectation_charter_mapping`)
    enforces: comma-separated `slice-NN` tokens, `_SLICE_ID_PATTERN.fullmatch`
    per token. Grammar is IMPORTED from the production module, never
    re-declared here.

    A worked example exists to be copied AS A VALID INSTANCE -- if the reader
    would reject it, a human copying it verbatim inherits an unusable
    charter. Both shipped worked examples ('slice-01, slice-02' and
    'slice-02') already satisfy this; this test's job is to keep it that way
    as the template evolves."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    occurrences = _spec_rows_occurrences_by_section(content)
    worked_example_values = [
        value for heading, value in occurrences if heading.startswith("Example")
    ]
    assert worked_example_values, (
        f"no '## Example (filled...)' 'Spec rows:' field found in {TEMPLATE_PATH}"
    )

    violations: list[str] = []
    for raw_value in worked_example_values:
        mapped_slices = [value.strip() for value in raw_value.split(",")]
        if not mapped_slices or any(
            not _SLICE_ID_PATTERN.fullmatch(value) for value in mapped_slices
        ):
            violations.append(raw_value)

    assert not violations, (
        f"{TEMPLATE_PATH} ships {len(violations)} worked-example 'Spec "
        f"rows:' value(s) its own reader (`resolve_slice_charter`) rejects: "
        f"{violations!r} -- a worked example must always parse, a human "
        "copies it as a VALID instance"
    )


@pytest.mark.negative_at
def test_shipped_template_fence_placeholder_is_recognisably_unfilled() -> None:
    """Obligation 7b (O4 split, NEGATIVE assertion). The `## Template`
    fence's own `Spec rows:` value is the FILL-ME-IN placeholder a fresh
    scaffold or a hand-copy starts from -- it must NOT parse under
    `resolve_slice_charter`'s grammar (`_SLICE_ID_PATTERN`, imported, never
    re-declared).

    Regression witness for the exact silent-wrong this feature exists to
    close: commit b7f63c54e turned this placeholder from `<R…>`
    (unparseable, visibly unfilled) into the concrete literal `slice-01`
    (parses fine, reads like a real claim) purely to satisfy the PRE-split
    version of this test -- after that commit, an unfilled charter read as a
    valid claim about slice-01, which is how the `_fill_spec_rows_field`
    guard (only rewrites when the identifier already matches `slice-NN`)
    left `bug-observable`/`brownfield-discovery` scaffolds carrying that same
    fabricated `slice-01` untouched (O2)."""
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    occurrences = _spec_rows_occurrences_by_section(content)
    fence_values = [value for heading, value in occurrences if heading == "Template"]
    assert fence_values, (
        f"no fence 'Spec rows:' field found under '## Template' in {TEMPLATE_PATH}"
    )

    fence_value = fence_values[0]
    mapped_slices = [value.strip() for value in fence_value.split(",")]
    is_valid_claim = bool(mapped_slices) and all(
        _SLICE_ID_PATTERN.fullmatch(value) for value in mapped_slices
    )

    assert not is_valid_claim, (
        f"{TEMPLATE_PATH}: the '## Template' fence's 'Spec rows:' value "
        f"{fence_value!r} PARSES under the reader's own slice-NN grammar -- "
        "an unfilled placeholder must be recognisably unfilled, never a "
        "valid-looking slice claim a human (or a scaffold) could ship by "
        "accident"
    )


# ===========================================================================
# Obligation O1 (feature-delta amendment, 2026-07-30) -- the producer
# refuses a duplicate slice-id, LOUD, before writing anything (GDP-1
# intercept early / GDP-4 cost on the system). The converse -- a Slice Plan
# with DISTINCT slice ids still scaffolds normally at exit 0 with verdict
# accepted -- is already pinned by
# test_two_slices_yield_two_charters_with_distinct_resolvable_scope above;
# not duplicated here (Mandate 12 SSOT).
# ===========================================================================


def test_duplicate_slice_id_in_slice_plan_refuses_loud_and_writes_zero_charters(
    tmp_path: Path, capsys
) -> None:
    """Measured today (HEAD b7f63c54e): a Slice Plan carrying 'slice-01'
    TWICE (two different Value statements) still scaffolds -- exit 0,
    verdict accepted, TWO charters created, both stamped
    'Spec rows: slice-01'. The SAME output makes the sibling reader refuse:
    `resolve_slice_charter(..., 'slice-01')` returns `indeterminate`,
    'mapped by multiple charters'. One tool must never mint what the other
    rejects: the PRODUCER must refuse FIRST -- a non-zero exit, a
    non-accepted verdict, and ZERO charters written to disk, not a partial
    scaffold plus a warning. The refusal detail must name the duplicated
    slice id and both competing Value statements (GDP-3 WHAT/WHY/HOW).

    Asserts the OBSERVABLE property only (verdict token != accepted,
    non-zero exit, zero files actually on disk) -- deliberately does NOT
    hardcode which module (the shared `validate_slice_plan_content` vs the
    scaffolder itself) implements the refusal, nor the new verdict token's
    literal spelling (it does not exist in production yet)."""
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, DUPLICATE_SLICE_FEATURE_DELTA)

    exit_code, payload = _invoke(tmp_path, capsys)

    assert exit_code != 0, (
        f"duplicate slice-01 rows: expected a non-zero exit, got 0 -- "
        f"payload={payload!r}"
    )
    assert payload["verdict"] != VERDICT_ACCEPTED, (
        f"duplicate slice-01 rows: expected a non-accepted verdict, got "
        f"{payload['verdict']!r}"
    )
    assert payload["created"] == [], (
        f"duplicate slice-01 rows: expected zero charters created, got "
        f"{payload['created']!r} -- a duplicate slice-id must never yield a "
        "partial scaffold"
    )

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    written = list(expectations_dir.glob("*.md")) if expectations_dir.is_dir() else []
    assert written == [], (
        f"duplicate slice-01 rows: {len(written)} charter file(s) actually "
        f"on disk despite the refusal: {written!r} -- the payload's "
        "'created' list must not lie about what was actually written"
    )

    assert "slice-01" in payload["detail"], (
        f"refusal detail does not name the duplicated slice id: {payload['detail']!r}"
    )
    assert VALUE_STATEMENT_DUP_A in payload["detail"], (
        f"refusal detail does not name the first competing Value statement: "
        f"{payload['detail']!r}"
    )
    assert VALUE_STATEMENT_DUP_B in payload["detail"], (
        f"refusal detail does not name the second competing Value "
        f"statement: {payload['detail']!r}"
    )


# ===========================================================================
# Obligation O2 (feature-delta amendment, 2026-07-30) -- the non-slice seed
# modes stamp their OWN identifier, never the slice-plan mode's grammar.
# ===========================================================================


@pytest.mark.parametrize(
    "extra_args,identifier",
    [
        pytest.param(
            [
                "--seed-mode",
                "bug-observable",
                "--observable",
                BUG_OBSERVABLE_TEXT,
            ],
            "bug-observable",
            id="bug_observable",
        ),
        pytest.param(
            [
                "--seed-mode",
                "brownfield-discovery",
                "--area",
                BROWNFIELD_AREA_TEXT,
            ],
            "brownfield-discovery",
            id="brownfield_discovery",
        ),
    ],
)
def test_non_slice_seed_modes_stamp_their_own_identifier_never_a_slice_id(
    tmp_path: Path, capsys, extra_args: list[str], identifier: str
) -> None:
    """Neither `--seed-mode` reads a Slice Plan and neither is slice-scoped,
    so a 'Spec rows: slice-01' claim on their output is FABRICATED. Measured
    today: both modes stamp 'slice-01' verbatim -- the template's own fence
    default, left untouched because `_fill_spec_rows_field`'s guard only
    rewrites when the identifier already matches the `slice-NN` grammar.
    Consequence measured separately (O3): with only this charter present,
    `resolve_slice_charter(..., 'slice-01')` returns `armed` -- a
    SILENT-WRONG false positive, the gate would arm the wrong charter and
    believe it succeeded.

    Required: the scope field always states the scope the producer actually
    knows -- its OWN `--seed-mode` identifier -- and never a `slice-NN`
    token it never resolved."""
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(tmp_path, capsys, extra_args=extra_args)

    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED
    assert len(payload["created"]) == 1

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    content = (expectations_dir / payload["created"][0]).read_text(encoding="utf-8")
    spec_rows_value = _spec_rows_value(content)

    assert spec_rows_value == identifier, (
        f"--seed-mode {identifier}: 'Spec rows:' field is "
        f"{spec_rows_value!r}, expected the scaffolder's own identifier "
        f"{identifier!r} -- neither seed mode reads a Slice Plan, so a "
        "slice-NN claim on its output is fabricated"
    )
    assert _SLICE_ID_PATTERN.fullmatch(spec_rows_value) is None, (
        f"--seed-mode {identifier}: 'Spec rows:' field {spec_rows_value!r} "
        "matches the slice-NN grammar -- this seed mode must NEVER emit a "
        "slice-NN token, it does not know which slice (if any) it covers"
    )


# ===========================================================================
# Obligation O3 (feature-delta amendment, 2026-07-30, human-granted
# forward-only decision) -- the reader admits 'bug-observable' /
# 'brownfield-discovery' as DELIBERATE feature-level scope, never
# indeterminate; a feature-level charter must not poison a sibling
# slice-scoped charter's resolution; the refusal for every other non-slice
# token is UNCHANGED.
# ===========================================================================


@pytest.mark.parametrize(
    "extra_args,identifier",
    [
        pytest.param(
            [
                "--seed-mode",
                "bug-observable",
                "--observable",
                BUG_OBSERVABLE_TEXT,
            ],
            "bug-observable",
            id="bug_observable",
        ),
        pytest.param(
            [
                "--seed-mode",
                "brownfield-discovery",
                "--area",
                BROWNFIELD_AREA_TEXT,
            ],
            "brownfield-discovery",
            id="brownfield_discovery",
        ),
    ],
)
def test_feature_level_scope_token_resolves_deliberate_not_indeterminate(
    tmp_path: Path, capsys, extra_args: list[str], identifier: str
) -> None:
    """Measured today: `resolve_slice_charter` returns `indeterminate` for a
    charter whose 'Spec rows:' is 'bug-observable' (same for
    'brownfield-discovery'), detail "...maps `Spec rows:` to
    '<identifier> ', not comma-separated `slice-NN` values" -- the SAME
    grammar mistake O2 is about, seen from the reader's side.

    Human decision (2026-07-30, granted, forward-only, recorded in the
    feature-delta): 'bug-observable' and 'brownfield-discovery' are
    FIRST-CLASS scope tokens meaning "deliberately not slice-scoped,
    feature-level". A well-formed feature-level charter must resolve
    `armed` for its own identifier -- it must read as a DELIBERATE scope,
    never as a malformed one."""
    _seed_repo(tmp_path)

    exit_code, payload = _invoke(tmp_path, capsys, extra_args=extra_args)
    assert exit_code == 0
    assert payload["verdict"] == VERDICT_ACCEPTED

    mapping = resolve_slice_charter(tmp_path, FEATURE_ID, identifier)

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    expected_path = expectations_dir / payload["created"][0]

    assert mapping.state == CharterMappingState.ARMED, (
        f"--seed-mode {identifier}: resolve_slice_charter(..., {identifier!r}) "
        f"returned state={mapping.state!r} detail={mapping.detail!r} -- a "
        "well-formed feature-level charter must read as a DELIBERATE scope, "
        "never a malformed one"
    )
    assert mapping.charter_path == expected_path


def test_slice_scoped_charter_takes_precedence_over_a_sibling_feature_level_charter(
    tmp_path: Path, capsys
) -> None:
    """PRECEDENCE (O3, refined per the traced `dispatch.py` consumer at
    `src/des/cli/dispatch.py:1988` -- the ONLY production caller of
    `resolve_slice_charter`): when a feature carries BOTH a feature-level
    charter (bug-observable / brownfield-discovery) and a slice-scoped
    charter naming the queried slice, the MORE SPECIFIC slice-scoped
    charter wins -- resolves `armed` to ITS OWN path, not merely 'some'
    charter. Non-poisoning is the CONSEQUENCE of this property, not the
    property itself, which is why this test asserts `charter_path`
    explicitly, not only `state`.

    Measured on the CURRENT (unfixed) build: a 'bug-observable' charter
    sitting beside a slice-01 charter carries the SAME fabricated
    'Spec rows: slice-01' (O2's defect), so BOTH charters map to 'slice-01'
    and `resolve_slice_charter(..., 'slice-01')` reports "mapped by
    multiple charters" -- indeterminate, poisoning the slice-scoped query
    entirely. Once O2 is fixed the poisoning would instead come from the
    grammar mismatch ('bug-observable' failing the slice-NN pattern) unless
    O3 is fixed alongside it -- either way, today's build fails this
    assertion for a real reason.

    Deliberately does NOT require a NEW `CharterMappingState` member to
    satisfy this: `dispatch.py`'s `C_REVIEWER_AUDIT` branch dispatches on
    exactly {INDETERMINATE, ARMED, UNARMED, else-assumed-UNMAPPED} and its
    `else` refuses with a message asserting "no charter maps this slice" --
    a NEW member would fall into that `else` and produce a LYING rejection
    for a slice that IS mapped. Precedence must be satisfiable by ARMED
    resolving to the more specific charter, full stop."""
    _seed_repo(tmp_path)
    _write_feature_delta(tmp_path, FEATURE_ID, SINGLE_SLICE_FEATURE_DELTA)

    slice_exit, slice_payload = _invoke(tmp_path, capsys)
    assert slice_exit == 0
    assert len(slice_payload["created"]) == 1

    bug_exit, bug_payload = _invoke(
        tmp_path,
        capsys,
        extra_args=[
            "--seed-mode",
            "bug-observable",
            "--observable",
            BUG_OBSERVABLE_TEXT,
        ],
    )
    assert bug_exit == 0
    assert len(bug_payload["created"]) == 1

    mapping = resolve_slice_charter(tmp_path, FEATURE_ID, "slice-01")

    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    slice_charter_path = expectations_dir / slice_payload["created"][0]

    assert mapping.state == CharterMappingState.ARMED, (
        "slice-01 did not resolve ARMED with a sibling feature-level "
        f"'bug-observable' charter present in the same directory: "
        f"state={mapping.state!r} detail={mapping.detail!r} -- a "
        "slice-scoped charter must take PRECEDENCE over a feature-level "
        "sibling, never be poisoned by it"
    )
    assert mapping.charter_path == slice_charter_path, (
        f"slice-01 resolved to {mapping.charter_path!r}, expected the "
        f"slice-scoped charter itself ({slice_charter_path!r}) -- "
        "precedence means the MORE SPECIFIC charter wins, not merely "
        "'some' charter resolving armed"
    )


def test_two_feature_level_charters_sharing_the_same_scope_token_are_genuinely_ambiguous(
    tmp_path: Path, capsys
) -> None:
    """The new first-class tokens must not create a NEW way to be silently
    ambiguous. Two feature-level charters CAN legitimately coexist in one
    feature (two different bugs, both scaffolded via `--seed-mode
    bug-observable`) -- but if BOTH carry the SAME 'Spec rows: bug-observable'
    scope token, a query for 'bug-observable' cannot tell which one is
    meant. This is the SAME shape of ambiguity O1 pins at the slice-plan
    producer's own duplicate-id check, seen here at the READER side for a
    feature-level token: two charters claiming the IDENTICAL scope must
    still resolve `indeterminate`, exactly like two slice-scoped charters
    claiming the same slice-NN already do (obligation O1's own converse)."""
    _seed_repo(tmp_path)

    first_exit, first_payload = _invoke(
        tmp_path,
        capsys,
        extra_args=[
            "--seed-mode",
            "bug-observable",
            "--observable",
            BUG_OBSERVABLE_TEXT,
        ],
    )
    assert first_exit == 0
    assert len(first_payload["created"]) == 1

    second_exit, second_payload = _invoke(
        tmp_path,
        capsys,
        extra_args=[
            "--seed-mode",
            "bug-observable",
            "--observable",
            "the import wizard hangs on step 3",
        ],
    )
    assert second_exit == 0
    assert len(second_payload["created"]) == 1
    assert second_payload["created"][0] != first_payload["created"][0], (
        "two DIFFERENT --observable texts must scaffold two DIFFERENT "
        "charter files, or this test does not actually exercise two "
        "distinct charters"
    )

    mapping = resolve_slice_charter(tmp_path, FEATURE_ID, "bug-observable")

    assert mapping.state == CharterMappingState.INDETERMINATE, (
        f"two feature-level 'bug-observable' charters present: "
        f"resolve_slice_charter(..., 'bug-observable') returned "
        f"state={mapping.state!r} detail={mapping.detail!r} -- two "
        "charters claiming the IDENTICAL scope token is genuinely "
        "ambiguous and must refuse, exactly like two slice-scoped "
        "charters mapping the same slice-NN already do"
    )


@pytest.mark.parametrize(
    "spec_rows_value",
    ["n/a", "human directive", "bugfix", "bug-report"],
)
def test_non_first_class_scope_tokens_still_refuse_indeterminate(
    tmp_path: Path, spec_rows_value: str
) -> None:
    """The forward-only decision widens acceptance to EXACTLY two tokens
    ('bug-observable', 'brownfield-discovery') -- every other
    historically-seen non-slice-NN value must keep refusing
    `indeterminate`, or the decision becomes a blanket loosening instead of
    a narrow one (the half that keeps it forward-only). This is a boundary
    PIN, not a defect-fix witness -- already true on the CURRENT build, and
    must stay true after O3 lands.

    Hand-authored charter (no scaffolder ever writes these values) --
    mirrors the hand-filled fixture style used by
    `test_rerun_never_clobbers_a_hand_filled_charter`."""
    expectations_dir = _expectations_dir(tmp_path, FEATURE_ID)
    expectations_dir.mkdir(parents=True, exist_ok=True)
    charter_path = expectations_dir / "hand-authored-charter.md"
    charter_path.write_text(
        "# A hand-authored charter\n"
        f"ID: EXP-{FEATURE_ID}-1 · Spec rows: {spec_rows_value} · "
        "Persona: a human PO\n\n"
        "## Intent\nHand-authored, not scaffolded.\n",
        encoding="utf-8",
    )

    mapping = resolve_slice_charter(tmp_path, FEATURE_ID, spec_rows_value)

    assert mapping.state == CharterMappingState.INDETERMINATE, (
        f"Spec rows: {spec_rows_value!r} resolved state={mapping.state!r} "
        "(expected indeterminate) -- only 'bug-observable' and "
        "'brownfield-discovery' are first-class feature-level scope "
        "tokens; every other non-slice-NN value must keep refusing"
    )
