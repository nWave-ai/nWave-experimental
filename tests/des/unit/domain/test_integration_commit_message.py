"""The integrated commit's message is a construction, checked against `.gitlint`."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from des.domain.integration_commit_message import (
    DEFAULT_CONVENTIONAL_TYPES,
    DEFAULT_TYPE,
    CommitMessageRule,
    IntegrationFacts,
    compose_integration_message,
    derive_scope,
)


REPO_GITLINT = Path(__file__).parents[4] / ".gitlint"

#: The exact authority locator measured on run 17 (2026-09-05). With its
#: `authority ` prefix it is one body line of 156 characters -- over the
#: declared 120 -- and it stopped the run after every turn had been paid.
RUN_17_LOCATOR = (
    "typed:tests/bugs/des/test_graphify_callers_of_answers_the_real_call_sites.py"
    "::test_callers_of_reports_the_real_call_sites_and_a_verified_empty_set"
)

#: The characters a locator is built from: a path, a `::` selector seam, and
#: the `#` heading seam of a document locator. No whitespace, no backslash --
#: which is what makes the continuation marker unambiguous inside one.
LOCATOR_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/#:"
)


def rejoin(lines):
    """The DOCUMENTED reconstruction of a continued body line.

    A line ending in ` \\` continues on the next: drop the marker, drop the
    next line's indent, concatenate. Written out here rather than imported, so
    a fact is read back through the rule the message declares and not through
    the producer's own code.
    """
    joined: list[str] = []
    for line in lines:
        if joined and joined[-1].endswith(" \\"):
            joined[-1] = joined[-1][:-2] + line.lstrip()
        else:
            joined.append(line)
    return joined


def gitlint_executable():
    """The real `gitlint` CI runs, or a LOUD failure naming how to get it."""
    resolved = shutil.which(
        "gitlint", path=str(Path(sys.executable).parent)
    ) or shutil.which("gitlint")
    if resolved is None:
        pytest.fail(
            "WHAT: gitlint is not resolvable from this interpreter. WHY: this "
            "test's whole claim is that the REAL checker CI runs accepts the "
            "composed message, and an equivalence argument is not that "
            "evidence. HOW: run `uv sync`, which installs the declared "
            "`gitlint-core` dev dependency next to this interpreter."
        )
    return resolved


def facts(request="Deliver the requested value", observations=None, authorities=None):
    return IntegrationFacts(
        request,
        ("the value is observable",) if observations is None else observations,
        ("docs/product/architecture/brief.md#Value",)
        if authorities is None
        else authorities,
    )


def compose(paths=("src/des/a.py",), rule=None, **kwargs):
    rule = rule or CommitMessageRule()
    return compose_integration_message(facts(**kwargs), "0" * 40, tuple(paths), rule)


@pytest.mark.parametrize(
    "paths,scope",
    [
        (("src/des/a.py", "tests/des/unit/b.py"), "des"),
        (("src/des/a.py",), "des"),
        (("docs/analysis/x.md",), "docs"),
        # A layout segment names no domain, so `src/` and `tests/` never win.
        (("src/product/a.py", "tests/acceptance/b.py"), None),
        # No directory component contributes no scope at all.
        (("README.md",), None),
        (("src/a.py",), None),
        ((), None),
    ],
)
def test_the_scope_is_the_one_segment_every_changed_path_agrees_on(paths, scope):
    assert derive_scope(paths) == scope


def test_a_git_quoted_path_names_no_scope():
    # `git diff-tree --name-only` QUOTES a path outside the configured encoding
    # unless asked for NUL separation.  The runner asks for `-z` so this form
    # never reaches here; the property is asserted so the reason stays visible.
    assert derive_scope(('"src/des/citt\\303\\240.py"',)) is None
    assert derive_scope(("src/des/citt\u00e0.py",)) == "des"


def test_the_subject_is_the_requests_first_line_in_this_repositorys_case():
    assert (
        compose(request="Deliver the requested value\nignored\n").splitlines()[0]
        == f"{DEFAULT_TYPE}(des): deliver the requested value"
    )


def test_an_acronym_the_request_capitalised_survives_the_case_normalisation():
    assert (
        compose(request="API parity is observable")
        .splitlines()[0]
        .endswith("API parity is observable")
    )


def test_a_subject_over_the_declared_limit_is_cut_at_a_word_boundary():
    rule = CommitMessageRule()
    subject = compose(request="deliver " + "value " * 40, rule=rule).splitlines()[0]

    assert len(subject) <= rule.title_max_length
    assert subject.endswith("value")
    assert rule.defect(compose(request="deliver " + "value " * 40)) is None


@pytest.mark.parametrize(
    "request_text",
    ["", "   \n\n", "!!! ???", "123 456", "."],
)
def test_a_request_yielding_no_usable_subject_still_composes_a_conforming_one(
    request_text,
):
    rule = CommitMessageRule()
    assert rule.defect(compose(request=request_text, rule=rule)) is None


def test_the_body_carries_every_observation_in_order_then_the_identity():
    message = compose(observations=("first value", "second value"))
    paragraphs = message.split("\n\n")

    assert paragraphs[1:3] == ["first value", "second value"]
    assert paragraphs[3].splitlines() == [
        "expected-old " + "0" * 40,
        "authority docs/product/architecture/brief.md#Value",
    ]


def test_an_observation_the_subject_already_states_is_not_repeated_in_the_body():
    # GDP-0: the line that cannot overflow is the line that is never emitted.
    request = "the value is observable"
    message = compose(request=request, observations=(request, "a second value"))

    assert message.splitlines()[0] == f"{DEFAULT_TYPE}(des): {request}"
    assert message.count(request) == 1
    assert "a second value" in message


def test_a_truncated_subject_keeps_the_observation_it_could_not_carry():
    request = "deliver " + "value " * 40
    message = compose(request=request, observations=(request,))
    subject, _, body = message.partition("\n\n")

    assert len(subject) < len(" ".join(request.split()))
    assert " ".join(request.split()) in " ".join(body.split())


def test_a_long_observation_wraps_and_every_line_fits_the_declared_width():
    locator = "docs/" + "segment/" * 20 + "brief.md#Value"
    message = compose(
        observations=("word " * 60,),
        authorities=(locator,),
    )

    assert all(len(line) <= 120 for line in message.splitlines())
    assert f"authority {locator}" in rejoin(message.splitlines())


def test_the_locator_that_stopped_run_17_composes_a_conforming_message():
    # Measured 2026-09-05: this one line was 156 characters and the run
    # answered IntegrationMessageNonConforming after every turn was paid.
    rule = CommitMessageRule()
    assert len(f"authority {RUN_17_LOCATOR}") == 156

    message = compose(authorities=(RUN_17_LOCATOR,), rule=rule)

    assert rule.defect(message) is None
    assert all(len(line) <= 120 for line in message.splitlines())
    assert f"authority {RUN_17_LOCATOR}" in rejoin(message.splitlines())


def test_a_typed_locator_breaks_at_its_own_seam_not_inside_the_path():
    message = compose(authorities=(RUN_17_LOCATOR,)).splitlines()

    assert (
        "authority typed:tests/bugs/des/"
        "test_graphify_callers_of_answers_the_real_call_sites.py \\"
    ) in message
    assert (
        "    ::test_callers_of_reports_the_real_call_sites_and_a_verified_empty_set"
    ) in message


def test_a_thousand_character_fact_with_no_seam_still_composes_conforming():
    # The residual the previous design refused: one fact-bearing token longer
    # than the declared width, with no natural boundary to break at.
    rule = CommitMessageRule()
    locator = "docs/" + "x" * 1000 + ".md#Value"

    message = compose(authorities=(locator,), rule=rule)

    assert rule.defect(message) is None
    assert all(len(line) <= 120 for line in message.splitlines())
    assert f"authority {locator}" in rejoin(message.splitlines())


def test_an_observation_carrying_an_unbreakable_token_composes_conforming():
    rule = CommitMessageRule()
    token = "src/" + "segment/" * 40 + "module.py"

    message = compose(observations=(f"the oracle at {token} passes",), rule=rule)

    assert rule.defect(message) is None
    assert token in " ".join(rejoin(message.splitlines()))


@st.composite
def sized_locator_text(draw, low, high):
    """Text of a length drawn UNIFORMLY over [low, high].

    `st.text(max_size=...)` concentrates on short strings, and a short locator
    fits the declared width on its own -- a generator that mostly draws those
    cannot discriminate the wrapping from the flat concatenation it replaced.
    The length is therefore drawn first, so most cases are genuinely over the
    declared 120 and the property has something to falsify.
    """
    size = draw(st.integers(min_value=low, max_value=high))
    return draw(st.text(alphabet=LOCATOR_ALPHABET, min_size=size, max_size=size))


@st.composite
def locators(draw):
    path = draw(sized_locator_text(1, 1000))
    selector = draw(sized_locator_text(0, 1000))
    return f"typed:{path}::{selector}" if selector else path


@given(first=locators(), second=locators())
@settings(max_examples=300, deadline=None)
def test_no_fact_of_any_length_makes_the_composed_message_nonconforming(first, second):
    # The property the flat concatenation could not hold: composition, not
    # refusal, is what keeps the message conforming for EVERY fact.
    rule = CommitMessageRule()

    message = compose(authorities=(first, second), rule=rule)

    assert rule.defect(message) is None
    recovered = rejoin(message.splitlines())
    assert f"authority {first}" in recovered
    assert f"authority {second}" in recovered


@pytest.mark.parametrize(
    "locator",
    [
        RUN_17_LOCATOR,
        "docs/product/architecture/brief.md#Value",
        "docs/" + "x" * 1000 + ".md#Value",
        "typed:" + "a" * 300 + "::" + "b" * 300,
        "typed:tests/des/acceptance/owned.py::" + "selector_" * 30,
    ],
)
def test_the_real_gitlint_accepts_the_message_composed_for_this_fact(tmp_path, locator):
    # Not an equivalence argument: the checker CI runs is executed here.
    rule = CommitMessageRule.declared(REPO_GITLINT.read_text(encoding="utf-8"))
    message = compose(authorities=(locator,), observations=("word " * 60,), rule=rule)
    candidate = tmp_path / "COMMIT_EDITMSG"
    candidate.write_text(message + "\n", encoding="utf-8")

    completed = subprocess.run(
        [gitlint_executable(), "--msg-filename", str(candidate)],
        cwd=str(REPO_GITLINT.parent),
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("title_max_length", [1, 4, 6])
def test_a_degenerate_declared_title_length_empties_the_subject_not_its_tail(
    title_max_length,
):
    # A budget of `title_max_length - len(prefix)` goes NEGATIVE here, and a
    # negative slice cuts from the END: without the clamp the subject silently
    # became the TAIL of the Request, a fact the composer never chose to carry.
    rule = CommitMessageRule(title_max_length=title_max_length)
    request = "deliver the requested value"

    subject = compose(request=request, rule=rule).splitlines()[0]

    assert subject == f"{DEFAULT_TYPE}: "
    assert not any(word in subject for word in request.split())
    # And the family is the DECLARED rule, repaired in `.gitlint`, never a fact.
    defect = rule.defect(compose(request=request, rule=rule))
    assert defect is not None and ".gitlint" in defect.how


@pytest.mark.parametrize(
    "locator,line",
    [
        ("docs/brief.md#Value ", "authority docs/brief.md#Value"),
        ("  docs/brief.md#Value  ", "authority docs/brief.md#Value"),
        # A tab is not deleted, it is COLLAPSED like any whitespace run: the
        # identity on every real locator, and never a hard tab in a body line.
        ("docs/brief.md\t#Value", "authority docs/brief.md #Value"),
    ],
)
def test_whitespace_inside_a_fact_never_reaches_an_identity_line(locator, line):
    # Emitted verbatim, a locator carrying a tab or a trailing space put a hard
    # tab or a ragged line into a commit body CI would then reject.
    rule = CommitMessageRule()

    message = compose(authorities=(locator,), rule=rule)

    assert rule.defect(message) is None
    assert all(row == row.rstrip() for row in message.splitlines()), message
    assert "\t" not in message, message
    assert line in message.splitlines(), message


def test_a_whitespace_bearing_expected_old_emits_no_ragged_identity_line():
    rule = CommitMessageRule()

    message = compose_integration_message(facts(), " ", (), rule)

    assert rule.defect(message) is None
    assert "expected-old" in message
    assert all(line == line.rstrip() for line in message.splitlines()), message


@pytest.mark.parametrize("width", [1, 2])
def test_a_declared_width_too_narrow_to_continue_names_the_declared_limit(width):
    # The ONE way the body-length branch stays reachable: not a fact of any
    # length, but a declared width that cannot carry the marker plus one
    # character. That is a property of `.gitlint`, and its repair is there.
    rule = CommitMessageRule(body_max_line_length=width)

    defect = rule.defect(compose(rule=rule))

    assert defect is not None and "over the declared limit" in defect.why
    assert "[body-max-line-length]" in defect.how


def test_the_narrowest_representable_declared_width_still_composes_conforming():
    rule = CommitMessageRule(body_max_line_length=3)

    assert rule.defect(compose(rule=rule)) is None


def test_a_narrowed_type_vocabulary_is_read_and_refused_not_approved():
    # gitlint enforces CT1 against its own `types` list, so a `.gitlint` that
    # narrows the vocabulary without touching the regex must not be approved.
    rule = CommitMessageRule.declared(
        "[general]\ncontrib = contrib-title-conventional-commits\n"
        "[contrib-title-conventional-commits]\ntypes = fix,chore\n"
    )

    assert rule.conventional_types == ("fix", "chore")
    defect = rule.defect(compose(rule=rule))
    assert defect is not None and "fix, chore" in defect.why
    assert "[contrib-title-conventional-commits]" in defect.how


def test_enabling_the_contrib_rule_without_narrowing_it_admits_the_default_type():
    rule = CommitMessageRule.declared(
        "[general]\ncontrib = contrib-title-conventional-commits\n"
    )

    assert rule.conventional_types == DEFAULT_CONVENTIONAL_TYPES
    assert DEFAULT_TYPE in rule.conventional_types
    assert rule.defect(compose(rule=rule)) is None


def test_a_repository_declaring_no_vocabulary_has_none_enforced():
    assert CommitMessageRule().conventional_types == ()


@pytest.mark.parametrize(
    "message,fragment",
    [
        ("Integrate requested value", "does not match the declared title rule"),
        (f"{DEFAULT_TYPE}: " + "x" * 120, "over the declared limit of 100"),
        (f"{DEFAULT_TYPE}: value.", "ends with punctuation"),
        (f"{DEFAULT_TYPE}: value \nbody", "trailing whitespace"),
        (f"{DEFAULT_TYPE}: value\nbody", "no blank line separates"),
        (f"{DEFAULT_TYPE}: value\n\n" + "x" * 200, "over the declared limit of 120"),
        (f"{DEFAULT_TYPE}: value\n\nbody \n", "trailing whitespace"),
        (f"{DEFAULT_TYPE}: value\n\n\tbody", "hard tab"),
    ],
)
def test_the_declared_rule_names_the_one_violation_a_message_carries(message, fragment):
    defect = CommitMessageRule().defect(message)
    assert defect is not None and fragment in defect.why
    assert defect.how


def test_the_message_the_defect_was_measured_on_is_still_rejected():
    # The exact message commit 466708968 carries; the whole reason for this code.
    assert CommitMessageRule().defect("Integrate requested value") is not None


def test_this_repositorys_declared_rule_is_read_from_its_own_gitlint():
    rule = CommitMessageRule.declared(REPO_GITLINT.read_text(encoding="utf-8"))

    assert rule.title_max_length == 100 and rule.body_max_line_length == 120
    assert "feat|fix|docs" in rule.title_pattern
    assert rule.defect(compose(rule=rule)) is None


@pytest.mark.parametrize("text", ["", None, "not an ini {{{", "[general]\nignore = B6"])
def test_an_absent_or_unusable_config_degrades_to_the_documented_defaults(text):
    assert CommitMessageRule.declared(text) == CommitMessageRule()
