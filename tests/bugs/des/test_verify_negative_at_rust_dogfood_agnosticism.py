"""Regression (GDP-7 agnosticism, backlog #42): ``des verify-negative-at``
degrades on a non-Python repo instead of detecting the negative AT.

Found empirically by sister Tsunami's Rust dogfood, hit 4x across cycles --
the maintainer substituted manual evidence because the gate always errored.
Confirmed by reading ``src/des/cli/verify_negative_at.py`` (tsunami
``atoms_in_file`` cross-check) and by direct execution against a synthetic
``.rs`` fixture (see reproduction below).

Two gaps, one root cause each:

(A) LANGUAGE DISPATCH -- ``_scan_file`` (:227-230) routes every non-
    ``.feature`` file to ``_scan_pytest_file`` (:146), which unconditionally
    ``ast.parse``s it (:149) -- Python-only. A ``.rs`` file is not valid
    Python, so the SyntaxError is caught and reported as
    ``NegativeAtIndeterminate`` ("it must be valid Python") -- a graceful
    exit code, but a WRONG one: the negative AT that visibly exists in the
    Rust source (by name, the only discriminator this gate uses) is never
    found. Empirically reproduced pre-fix:

        $ python -c "...ast.parse of a .rs file with a #[test] fn..."
        {"event": "NegativeAtIndeterminate",
         "what": "cannot parse .../negative_at_test.rs",
         "why": "invalid syntax (negative_at_test.rs, line 3)",
         "how": "fix the file (it must be valid Python) and re-run."}
        EXIT CODE: 2

(B) NAME-TOKEN COVERAGE -- ``_PYTEST_NEGATIVE_NAME_TOKENS`` (:68) is missing
    the Rust-idiom compound verbs sister observed across 6 cycles:
    ``_still_errors``, ``_still_requires``, ``_still_flags`` /
    ``still_flags_`` (name-initial form), and ``_negative_control``.
    ``_refuses_`` is already present. Empirically confirmed pre-fix:
    ``_is_negative_pytest_name("adr_section_..._still_errors")`` -> False.

The fix (crafter's job, NOT this file): (A) detect the negative AT by NAME
via a language-neutral text scan for non-``.py``/``.feature`` files (or
degrade LOUD naming the unsupported language -- never an unhandled
ast.parse crash); (B) extend the token set with the compound Rust-idiom
verbs above. Both gaps are language-agnostic by construction: the fix must
not special-case ``.rs``, only stop assuming ``.py``.

Driving surface: T1/T4 drive ``main()`` -- the real ``des verify-negative-at``
CLI entry point, exactly as ``--test-file <x.rs>`` would. T2/T3 drive
``_is_negative_pytest_name`` directly -- the language-neutral name
discriminator the fix must extend; mirrors the established
``tests/bugs/des/test_cargo_scope_nomatch_is_indeterminate.py`` precedent of
testing a gate's own production discriminator function directly for a
targeted bugfix regression, and matches this gate's existing unit-level
convention (``tests/des/unit/cli/test_verify_negative_at.py`` drives
``main()`` only; no acceptance-layer Gherkin exists for this CLI gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_negative_at import _is_negative_pytest_name, main


_RUST_EXISTING_TOKEN_FIXTURE = """\
#[test]
fn seat_booking_rejects_invalid_input() {
    let result = validate_seat("bad");
    assert!(result.is_err());
}

#[test]
fn resolves_id() {
    let result = parse_adr("ADR-001");
    assert!(result.is_ok());
}
"""

_RUST_COMPOUND_GAP_FIXTURE = """\
#[test]
fn adr_section_negative_no_derivable_id_still_errors() {
    let result = adr_section("bad");
    assert!(result.is_err());
}

#[test]
fn resolves_id() {
    let result = parse_adr("ADR-001");
    assert!(result.is_ok());
}
"""


def _first_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out: dict[str, object] = json.loads(capsys.readouterr().out.splitlines()[0])
    return out


# --- POSITIVE (active-RED today) --------------------------------------------


def test_rust_file_with_existing_negative_token_is_detected_not_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gap (A) isolated: the negative test name already uses a RECOGNIZED
    token (``_rejects_``) -- if the language dispatch worked, this file
    would verify today. It doesn't: ``_scan_file`` routes ``.rs`` to the
    Python-only AST scanner, which chokes on Rust syntax and reports
    ``NegativeAtIndeterminate`` instead of finding the negative AT by name.

    Active-RED at HEAD: exit code is 2 (INDETERMINATE), not 0
    (NegativeAtVerified) -- the assertion below fails for the right reason
    (wrong verdict, not a missing feature elsewhere).
    """
    rust_file = tmp_path / "seat_booking_test.rs"
    rust_file.write_text(_RUST_EXISTING_TOKEN_FIXTURE)

    exit_code = main(["--test-file", str(rust_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on a .rs file whose negative test "
        f"is named with a recognized token, got exit={exit_code} "
        f"event={event!r} -- the .rs file must not be treated as Python"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


@pytest.mark.parametrize(
    "name",
    [
        "adr_section_negative_no_derivable_id_still_errors",
        "dead_module_still_requires_git",
        "still_flags_given_bad_input",
        "foo_negative_control",
    ],
)
def test_rust_idiom_compound_tokens_are_recognized_as_negative(name: str) -> None:
    """Gap (B) isolated: the Rust-idiom compound verbs sister observed
    across 6 dogfood cycles are absent from ``_PYTEST_NEGATIVE_NAME_TOKENS``.

    Active-RED at HEAD: none of these names are recognized as negative
    (``_is_negative_pytest_name`` returns False for all four).
    """
    assert _is_negative_pytest_name(name) is True, (
        f"{name!r} carries a Rust-idiom negative verb "
        f"(_still_errors/_still_requires/_still_flags/_negative_control) "
        f"that must be recognized as a negative AT by name"
    )


def test_rust_file_with_compound_gap_token_verifies_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Full compound regression: both gaps stacked on the exact fixture
    shape sister's dogfood produced (``adr_section_..._still_errors``).

    Active-RED at HEAD for TWO independent reasons: the .rs file is routed
    to the Python AST scanner (gap A) AND, even if it weren't, the name
    token isn't recognized yet (gap B). Fixing only one gap leaves this RED.
    """
    rust_file = tmp_path / "adr_section_test.rs"
    rust_file.write_text(_RUST_COMPOUND_GAP_FIXTURE)

    exit_code = main(["--test-file", str(rust_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on the sister-dogfood .rs fixture, "
        f"got exit={exit_code} event={event!r}"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


# --- NEGATIVE-AT (green now AND after -- guards the token expansion) -------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "name", ["resolves_id", "still_works", "parse_adr_still_valid"]
)
def test_positive_names_are_not_misclassified_by_the_expanded_tokens(
    name: str,
) -> None:
    """NEGATIVE proof: a purely positive test name must NOT be swept up by
    the new compound tokens -- guards against an over-broad bare ``still_``
    match (which would false-positive on e.g. ``still_works``).

    Must stay green before AND after the fix; a regression here means the
    token expansion was implemented as a bare substring instead of the
    conservative compound forms the fix requires.
    """
    assert _is_negative_pytest_name(name) is False


# --- Gap (C): TypeScript/JavaScript string-call idiom -----------------------
#
# Follow-up gap, caught live by Vera's examine (FAIL, real) after gaps (A)/(B)
# above were closed: ``_scan_generic_name_file`` (:246) finds test-declaration
# NAMES via ``_GENERIC_TEST_DECL_PATTERN`` (:87), a regex anchored on
# ``fn|func|function|def <identifier>`` -- a language-neutral IDENTIFIER
# scan. Idiomatic JS/TS tests do not declare the test name as an identifier;
# they pass it as a STRING LITERAL argument to ``test(...)``/``it(...)``/
# ``describe(...)``:
#
#     test('rejects invalid input', () => { ... });
#     it('never allows a bad token', () => { ... });
#
# The name (``rejects invalid input``) is space-separated words, not an
# ``fn foo()``-shaped declaration -- the current regex matches zero cases in
# such a file, so a critical scope built entirely of ``test('rejects ...')``
# assertions is reported ``NegativeAtRefused`` (no cases found at all, hence
# no negative AT) even though the negative AT visibly exists by name. The
# charter's Intent explicitly lists TypeScript as a supported language.
#
# Discovery note for the implementer (oracle only, NOT an implementation):
# ``_is_negative_pytest_name`` matches underscore-joined tokens
# (``_rejects_``, ``_not_``, ``_never_``) against an IDENTIFIER. A JS/TS
# string-call name is a space-separated phrase (``rejects invalid input``),
# so the fix needs a second, word-based negative-intent check for names
# harvested from ``test(...)``/``it(...)``/``describe(...)`` string
# arguments -- matching words like ``rejects``/``refuses``/``never``/
# ``does not``/``fails`` -- WITHOUT assuming the underscore-joined shape.
# The four fixtures below pin the words that must be recognized; the
# positive-only fixture pins what must NOT be (no bare ``still``/other
# over-broad match). The mechanism is the crafter's to build.
#
# Driving surface: main() end-to-end (T5-T8), same as the Rust gap (A)
# fixtures above -- there is no production JS/TS-string-call discriminator
# function yet to unit-drive directly (that is exactly the gap).

_TS_NEGATIVE_STRING_CALL_FIXTURE = """\
test('rejects invalid input', () => {
  const result = validateSeat('bad');
  expect(result.isErr()).toBe(true);
});

test('resolves the seat id', () => {
  const result = parseAdr('ADR-001');
  expect(result.isOk()).toBe(true);
});
"""

_JS_NEGATIVE_STRING_CALL_FIXTURE = """\
test('rejects an invalid seat', () => {
  const result = validateSeat('bad');
  expect(result.isErr()).toBe(true);
});

test('resolves the seat id', () => {
  const result = parseAdr('ADR-001');
  expect(result.isOk()).toBe(true);
});
"""

_TS_POSITIVE_ONLY_STRING_CALL_FIXTURE = """\
test('still works', () => {
  expect(check()).toBe(true);
});

it('returns ok', () => {
  expect(parse()).toBeDefined();
});
"""


def test_ts_file_with_negative_string_call_idiom_is_detected_not_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The negative test's NAME lives in a string argument to ``test(...)``,
    not in an identifier -- ``_GENERIC_TEST_DECL_PATTERN`` never matches it,
    so today the file scans to zero cases and the critical scope (armed by
    ``--all-critical``) is reported ``NegativeAtRefused`` for having no
    cases at all, let alone a negative one.

    Active-RED at HEAD: exit code is 1 (NegativeAtRefused), not 0
    (NegativeAtVerified) -- fails for the right reason (wrong verdict, the
    string-call name is simply invisible to the scanner today).
    """
    ts_file = tmp_path / "seat_booking.test.ts"
    ts_file.write_text(_TS_NEGATIVE_STRING_CALL_FIXTURE)

    exit_code = main(["--test-file", str(ts_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on a .ts file whose negative test "
        f"is named via the test('...') string-call idiom, got "
        f"exit={exit_code} event={event!r} -- the string argument must be "
        f"scanned for negative intent, not only bare identifiers"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


@pytest.mark.parametrize(
    "call, phrase",
    [
        ("test", "rejects an unsupported currency"),
        ("it", "does not allow a bad token"),
        ("it", "never accepts an empty payload"),
        ("test", "fails on malformed input"),
    ],
)
def test_ts_negative_idioms_recognized_via_string_call_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], call: str, phrase: str
) -> None:
    """Sweep of the JS/TS negative-intent words a real test suite would use
    (rejects / does not / never / fails), each as the string argument to
    ``test(...)``/``it(...)``.

    Active-RED at HEAD: none of these string-call names are recognized as
    negative today (the scanner finds zero cases in every fixture).
    """
    ts_file = tmp_path / "negative_idiom.test.ts"
    ts_file.write_text(
        f"{call}('{phrase}', () => {{\n  expect(check()).toBe(true);\n}});\n"
    )

    exit_code = main(["--test-file", str(ts_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) for {call}('{phrase}', ...), got "
        f"exit={exit_code} event={event!r}"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


def test_js_file_with_negative_string_call_idiom_is_detected_not_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """.js variant of the .ts case above -- proves the fix targets the
    JS/TS FAMILY (the string-call idiom is shared by both), not a
    ``.ts``-only special case.

    Active-RED at HEAD: same wrong verdict (NegativeAtRefused, exit 1) as
    the .ts fixture.
    """
    js_file = tmp_path / "seat_booking.test.js"
    js_file.write_text(_JS_NEGATIVE_STRING_CALL_FIXTURE)

    exit_code = main(["--test-file", str(js_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on a .js file with the same "
        f"string-call idiom, got exit={exit_code} event={event!r} -- the "
        f"fix must not be .ts-only"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


@pytest.mark.negative_at
def test_ts_positive_only_string_call_names_are_not_misclassified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: purely positive string-call names (``'still works'``,
    ``'returns ok'``) must NOT be swept up by the new word-based matcher --
    guards against an over-broad bare ``still``/``ok`` match.

    Must stay green before AND after the fix: pre-fix the file scans to
    zero cases (no negative AT to over-claim); post-fix it must scan two
    POSITIVE cases and still report no negative AT. Either way the critical
    scope (armed by --all-critical) has zero negative ATs, so the verdict
    stays NegativeAtRefused throughout -- a flip to NegativeAtVerified here
    would mean the fix false-positived on a positive name.
    """
    ts_file = tmp_path / "positive_only.test.ts"
    ts_file.write_text(_TS_POSITIVE_ONLY_STRING_CALL_FIXTURE)

    exit_code = main(["--test-file", str(ts_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 1, (
        f"expected NegativeAtRefused (1) -- no negative AT present -- got "
        f"exit={exit_code} event={event!r}; a flip to NegativeAtVerified "
        f"means a positive string-call name was misclassified as negative"
    )
    assert event["event"] == "NegativeAtRefused"


# --- Gap (D): Go/camelCase and PascalCase identifier idiom ------------------
#
# Follow-up gap, caught live by Vera's 2nd examine (FAIL, real) after gaps
# (A)/(B)/(C) above were closed: ``_GENERIC_TEST_DECL_PATTERN`` (:92) already
# matches Go's ``func <Identifier>`` declaration shape (``func`` is in the
# keyword alternation), so the identifier IS extracted -- e.g.
# ``func TestRejectsBadInput(t *testing.T) {}`` yields the name
# ``TestRejectsBadInput``. The gap is downstream: ``_name_signals_negative``
# (:171) splits a name on non-alphanumeric characters
# (``re.split(r"[^a-z0-9]+", lowered)``) to find word tokens -- but Go's
# idiomatic test name is PascalCase/camelCase with NO separators at all
# (``TestRejectsBadInput``), so the split yields exactly one token,
# ``testrejectsbadinput``, which is not itself in ``_NEGATIVE_INTENT_WORDS``.
# The negative verb (``rejects``) is present in the identifier but invisible
# to a splitter that only recognizes underscore/space/punctuation boundaries.
# Confirmed by direct read of ``_name_signals_negative`` and by the RED
# fixtures below (Go is not special-cased anywhere in the scanner -- the gap
# is the word-splitter, so any camelCase/PascalCase identifier in ANY
# non-.py/.feature language hits it, not Go alone; the TS function-name
# fixture at the end of this section is the cross-language proof).
#
# Discovery note for the implementer (oracle only, NOT an implementation):
# the fix must split camelCase/PascalCase identifiers into words BEFORE the
# negative-verb check (e.g. ``TestRejectsBadInput`` -> ``['test', 'rejects',
# 'bad', 'input']``), reusing the SAME shared negative-vocabulary this file
# already exercises via ``_name_signals_negative`` -- one SSOT, do not fork a
# third word list for camelCase. The positive-only guard fixture below
# (``TestStillWorks`` / ``TestReturnsOk`` -> no negative word among their
# split tokens) proves the split must not over-match either.

_GO_CAMELCASE_NEGATIVE_FIXTURE = """\
func TestRejectsBadInput(t *testing.T) {}
"""

_GO_POSITIVE_ONLY_CAMELCASE_FIXTURE = """\
func TestStillWorks(t *testing.T) {}

func TestReturnsOk(t *testing.T) {}
"""

_TS_CAMELCASE_FUNCTION_NAME_NEGATIVE_FIXTURE = """\
function rejectsInvalidInput() {
  return validateSeat('bad').isErr();
}

function resolvesTheSeatId() {
  return parseAdr('ADR-001').isOk();
}
"""


def test_go_camelcase_negative_identifier_is_detected_not_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The negative test's Go-idiomatic PascalCase name (``func
    TestRejectsBadInput``) already reaches ``_is_negative_pytest_name`` as an
    extracted identifier -- ``_GENERIC_TEST_DECL_PATTERN`` finds it fine.
    What fails is the word-split: no separators in ``TestRejectsBadInput``
    means the negative verb ``rejects`` is never isolated as its own token.

    Active-RED at HEAD: exit code is 1 (NegativeAtRefused, the sole case in
    this critical scope is not recognized as negative), not 0
    (NegativeAtVerified) -- fails for the right reason (wrong verdict, the
    verb is present but the splitter can't see it).
    """
    go_file = tmp_path / "negative_idiom_test.go"
    go_file.write_text(_GO_CAMELCASE_NEGATIVE_FIXTURE)

    exit_code = main(["--test-file", str(go_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on a .go file whose negative test "
        f"is named via Go's idiomatic PascalCase declaration "
        f"(func TestRejectsBadInput), got exit={exit_code} event={event!r} "
        f"-- camelCase/PascalCase identifiers must be split into words "
        f"before the negative-verb check"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


@pytest.mark.parametrize(
    "go_test_name",
    [
        "TestRejectsBadInput",
        "TestNeverAllowsEmpty",
        "TestFailsOnMalformed",
        "TestDoesNotAcceptNil",
    ],
)
def test_go_camelcase_negative_idioms_recognized_via_declaration_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], go_test_name: str
) -> None:
    """Sweep of the Go/PascalCase negative-intent idioms a real Go test
    suite would use (Rejects / NeverAllows / FailsOn / DoesNotAccept), each
    as a ``func <Name>(t *testing.T) {}`` declaration -- the ONLY test in
    its own critical scope, so recognition is all-or-nothing per fixture.

    Active-RED at HEAD: none of these PascalCase names are recognized as
    negative today (the word-splitter finds one unsplit token per name,
    which is not itself a member of the negative-word vocabulary).
    """
    go_file = tmp_path / "negative_idiom_test.go"
    go_file.write_text(f"func {go_test_name}(t *testing.T) {{}}\n")

    exit_code = main(["--test-file", str(go_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) for func {go_test_name}(...), got "
        f"exit={exit_code} event={event!r}"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1


@pytest.mark.negative_at
def test_go_camelcase_positive_only_names_are_not_misclassified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE proof: purely positive PascalCase names (``TestStillWorks``,
    ``TestReturnsOk``) must NOT be swept up by the camelCase split -- guards
    against an over-broad match once the word-split lands (e.g. a bare
    ``still``/``ok`` token misread as negative intent).

    Must stay green before AND after the fix: pre-fix neither name is
    recognized as negative (no split at all yet); post-fix the split
    (``['test','still','works']`` / ``['test','returns','ok']``) still
    contains no negative-vocabulary word, so the verdict stays
    NegativeAtRefused throughout -- a flip to NegativeAtVerified here would
    mean the split over-matched.
    """
    go_file = tmp_path / "positive_only_test.go"
    go_file.write_text(_GO_POSITIVE_ONLY_CAMELCASE_FIXTURE)

    exit_code = main(["--test-file", str(go_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 1, (
        f"expected NegativeAtRefused (1) -- no negative AT present -- got "
        f"exit={exit_code} event={event!r}; a flip to NegativeAtVerified "
        f"means a positive PascalCase name was misclassified as negative"
    )
    assert event["event"] == "NegativeAtRefused"


def test_ts_camelcase_function_name_negative_idiom_is_detected_not_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cross-language proof: the camelCase split gap is not Go-only. A TS/JS
    test can also name its negative case via a plain FUNCTION DECLARATION
    (``function rejectsInvalidInput() {}``) rather than the ``test('...')``
    string-call idiom already covered by Gap (C) -- ``_GENERIC_TEST_DECL_
    PATTERN`` matches the ``function`` keyword and extracts the lowerCamelCase
    identifier, which hits the exact same unsplit-word gap as Go's PascalCase.

    Active-RED at HEAD: exit code is 1 (NegativeAtRefused), not 0
    (NegativeAtVerified) -- same wrong verdict, same root cause as the Go
    fixtures above, different host language.
    """
    ts_file = tmp_path / "camelcase_function_name.test.ts"
    ts_file.write_text(_TS_CAMELCASE_FUNCTION_NAME_NEGATIVE_FIXTURE)

    exit_code = main(["--test-file", str(ts_file), "--all-critical"])

    event = _first_event(capsys)
    assert exit_code == 0, (
        f"expected NegativeAtVerified (0) on a .ts file whose negative test "
        f"is named via a camelCase FUNCTION declaration (not a string-call), "
        f"got exit={exit_code} event={event!r} -- proves the camelCase "
        f"split is language-neutral, not Go-only"
    )
    assert event["event"] == "NegativeAtVerified"
    assert event["negative_ats_found"] == 1
