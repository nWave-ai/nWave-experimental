"""Shared step vocabulary for the reverify-E1-via-scoped-wrapper ATs.

Mandate-12: every step body is <=2 statements and delegates to a
``ReverifyE1WrapperComposition`` service method -- no business logic, no
control flow. The DSL emerges from typed parameters: a single ``Given``
decorator with an int parser covers all cross-feature-collision cardinalities
(C3 0/1/N), and a single typed-verdict ``Then`` covers all three CLI verdicts.

Pillar 1: scenario titles + step phrases speak the domain
("an operator re-verifies the slice", "the wrapper refuses without a
feature scope") -- never argv tokens, never JSON keys.

Layer 3 (subprocess / real-git acceptance): example-based, no PBT machinery
(Mandate 9/11). The SSOT-scoping property (slice-01 AT-(a)) lives in the
specifications module as a layer-2 PBT (in-process, pure function).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import ReverifyE1WrapperComposition
from .domain_types import ReverifyE1Outcome, WrapperOutcome, WrapperVerdict


pytestmark = pytest.mark.acceptance


def _verdict(token: str) -> WrapperVerdict:
    """Coerce a Gherkin verdict token to the typed enum value."""
    return WrapperVerdict(token)


def _outcome(token: str) -> ReverifyE1Outcome:
    """Coerce a Gherkin reverify-outcome token to the typed enum value."""
    return ReverifyE1Outcome(token)


# -- Given -----------------------------------------------------------------


@given(
    parsers.parse("a repository with {n_features:d} features sharing the slice tag"),
    target_fixture="seeded_features",
)
def given_repo_with_n_features_sharing_slice(
    composition: ReverifyE1WrapperComposition, n_features: int
):
    """Build a real repo where ``n_features`` distinct features tag @slice-NN.

    One decorator, one parser, every cardinality (1, 2, 5) -- the integer is
    the DSL parameter. Composition owns all git construction.
    """
    return composition.given_features_sharing_slice(n_features)


# -- When ------------------------------------------------------------------


@when(
    parsers.parse('the operator checks completeness for feature "{feature_id}"'),
    target_fixture="wrapper_outcome",
)
def when_check_completeness_for_feature(
    composition: ReverifyE1WrapperComposition, feature_id: str
) -> WrapperOutcome:
    """Subprocess-drive the wrapper CLI with the named feature scope."""
    return composition.invoke_wrapper(feature_id=feature_id)


@when(
    "the operator checks completeness without a feature scope",
    target_fixture="wrapper_outcome",
)
def when_check_completeness_without_feature(
    composition: ReverifyE1WrapperComposition,
) -> WrapperOutcome:
    """Subprocess-drive the wrapper CLI with ``--feature-id`` omitted.

    Reproduces the regression vector (residuality pass 2): the wrapper MUST
    refuse argv without ``--feature-id`` -- otherwise a future contributor
    could silently re-instantiate the global-scope defect this feature closes.
    """
    return composition.invoke_wrapper(omit_feature_id=True)


@when(
    parsers.parse("the operator checks completeness against an unreadable repository"),
    target_fixture="wrapper_outcome",
)
def when_check_completeness_against_unreadable_repo(
    composition: ReverifyE1WrapperComposition,
    tmp_path,
) -> WrapperOutcome:
    """Subprocess-drive the wrapper CLI against a non-git directory."""
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    return composition.invoke_wrapper(
        repo_override=not_a_repo, commit_override="deadbeef"
    )


@when("the operator re-verifies the slice", target_fixture="reverify_outcome")
def when_operator_reverifies(
    composition: ReverifyE1WrapperComposition,
    capsys: pytest.CaptureFixture[str],
) -> ReverifyE1Outcome:
    """Drive the production reverify CLI; capture the typed E1 outcome."""
    return composition.invoke_reverify(capsys)


# -- Then ------------------------------------------------------------------


@then(parsers.parse('the completeness verdict is "{verdict_token}"'))
def then_verdict_is(wrapper_outcome: WrapperOutcome, verdict_token: str) -> None:
    """Assert the typed wrapper verdict matches the named enum value."""
    expected = _verdict(verdict_token)
    assert wrapper_outcome.verdict is expected, (
        f"verdict {wrapper_outcome.verdict.value!r} != {verdict_token!r}; "
        f"exit={wrapper_outcome.exit_code} stdout={wrapper_outcome.raw_stdout!r} "
        f"stderr={wrapper_outcome.raw_stderr!r}"
    )


@then("the verdict payload names exactly the primary feature's slice file")
def then_payload_names_primary_only(
    composition: ReverifyE1WrapperComposition, wrapper_outcome: WrapperOutcome
) -> None:
    """The complete-verdict payload's ``slice_id`` matches the primary's slice.

    Implicitly asserts feature-scoping: collider .features were NOT walked
    into the verdict's universe (otherwise a delete in collider[k] would
    surface as ``missing`` here).
    """
    primary = composition.features[0]
    assert wrapper_outcome.payload.get("slice_id") == "slice-01"
    assert wrapper_outcome.missing == [], (
        f"feature-scoped E1 leaked collider files into missing: "
        f"{wrapper_outcome.missing!r}; primary={primary.feature_file_rel!r}"
    )


@then(parsers.parse("the reverify outcome is {outcome_token}"))
def then_reverify_outcome_is(
    reverify_outcome: ReverifyE1Outcome, outcome_token: str
) -> None:
    """Assert the typed reverify outcome matches the named enum value."""
    expected = _outcome(outcome_token)
    assert reverify_outcome is expected, (
        f"reverify outcome {reverify_outcome.value!r} != {outcome_token!r}"
    )
