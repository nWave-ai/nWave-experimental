"""Step definitions -- slice-04: base-branch + scoped-path override flags.

F-DESIGN-REUSE-FIRST-GATE-CLI slice-04 (configurability polish). DDD-7.

slice-02 ships the real git-diff core with conventional defaults (trunk =
master, scope = src/). slice-04 makes both overridable: the architect may
measure the feature against a non-default trunk (``--base-branch``) and may
scope which part of the tree counts as feature code (``--scoped-path``). A
component introduced outside the scoped source tree is not a feature component
and does not require a Reuse Analysis row.

These step bindings reuse the slice-02 composition harness verbatim:
``ReuseFirstFixture.init_repository`` already renames the branch on re-init (the
divergence Given), ``run_check_on_range`` already accepts ``base_branch`` /
``scoped_path`` overrides, and ``commit_new_component`` already accepts the
``AddedPathKind.OUTSIDE_TREE`` (tools) out-of-scope builder. No new harness
methods are required for slice-04 -- only these bindings + the feature.

Layer 3, @real-io, example-based (Mandate 9 v2 OR-reduction). The base-branch x
scoped-path space is a finite decision table -> Scenario Outline parametrize
density, not ``@given``.

Step-text reuse vs S1 (per-module re-declaration): pytest-bdd 8 resolves step
definitions PER TEST MODULE. Importing the slice-02 step functions does NOT
work -- importing the slice-02 module re-executes its module-level
``scenarios(...)`` call at slice-04 import time (the
``CONFIG_STACK`` is empty outside a live collection, and even inside a run the
re-execution contaminates slice-04's per-module step/scenario closure). The
codebase's own working precedent (slice-03) therefore RE-DECLARES the shared
Background Given + shared Thens locally with its own fixtures. slice-04 follows
that precedent: the Background Given literal
``a feature whose source tree is tracked in a repository`` and the verdict Then
literal are the SAME text as slice-02's, but they live in a DIFFERENT module,
so there is no within-module double-registration (the S1 gate measures
within-module / within-feature-scope uniqueness; per-module re-declaration of a
shared concept is the accepted pattern here). The count Then uses a
plural-tolerant ``parsers.re`` (mirroring slice-03) so it covers BOTH the
singular ``one NEW component`` (Outline 1) and the plural
``<component_count> NEW components`` (Outline 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CheckResult, ReuseFirstFixture
from .domain_types import (
    ADDED_PATH_KIND_BY_PHRASE,
    COMPONENT_COUNT_BY_PHRASE,
    EXIT_CODE_BY_VERDICT,
    VERDICT_BY_OUTCOME_PHRASE,
    BaseBranch,
    FeatureId,
    ScopedPath,
)


scenarios("../slice-04-base-branch-scoped-path-flags.feature")


# The canonical NEW class the slice-04 scenarios commit + (sometimes) name.
_NEW_COMPONENT = "WidgetService"


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> ReuseFirstFixture:
    """Production-wired composition root over a real tmp_path git repository."""
    return ReuseFirstFixture(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result across When -> Then steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose source tree is tracked in a repository")
def given_repository_tracked(composition: ReuseFirstFixture) -> None:
    composition.create_feature(FeatureId("reuse-first-cli-demo"))
    composition.init_repository(BaseBranch("master"))


# --- Given -----------------------------------------------------------------


@given(parsers.parse('the feature\'s commits diverge from the base branch "{base}"'))
def given_diverge_from_base(composition: ReuseFirstFixture, base: str) -> None:
    composition.init_repository(BaseBranch(base))


@given("the feature's commits add a NEW component named in its Reuse Analysis section")
def given_commit_and_name_component(composition: ReuseFirstFixture) -> None:
    composition.commit_new_component(_NEW_COMPONENT, ADDED_PATH_KIND_BY_PHRASE["src"])
    composition.write_reuse_analysis(naming=_NEW_COMPONENT)


@given(parsers.parse('the feature\'s commits add a NEW component under "{added_path}"'))
def given_commit_component_under_path(
    composition: ReuseFirstFixture, added_path: str
) -> None:
    composition.commit_new_component(
        _NEW_COMPONENT, ADDED_PATH_KIND_BY_PHRASE[added_path]
    )


@given("the feature does not name that NEW component in its Reuse Analysis section")
def given_reuse_analysis_omits_component(composition: ReuseFirstFixture) -> None:
    composition.write_reuse_analysis(naming=None)


# --- When ------------------------------------------------------------------


@when(
    parsers.parse(
        'the architect runs the reuse-first check against base branch "{base}"'
    )
)
def when_run_against_base(
    composition: ReuseFirstFixture, result_box: dict[str, object], base: str
) -> None:
    result_box["result"] = composition.run_check_on_range(base_branch=BaseBranch(base))


@when(
    parsers.parse('the architect runs the reuse-first check scoped to "{scoped_path}"')
)
def when_run_scoped(
    composition: ReuseFirstFixture, result_box: dict[str, object], scoped_path: str
) -> None:
    result_box["result"] = composition.run_check_on_range(
        scoped_path=ScopedPath(scoped_path)
    )


# --- Then ------------------------------------------------------------------
#
# Re-declared locally (per-module resolution; same literals as slice-02 but a
# different module -> no within-module double-registration). The count Then is
# plural-tolerant via parsers.re so it covers BOTH the singular (Outline 1
# "one NEW component") and the plural (Outline 2 "<component_count> NEW
# components").


@then(
    parsers.parse("the feature's commit range {verdict_phrase} the reuse-first check")
)
def then_commit_range_verdict(
    result_box: dict[str, object], verdict_phrase: str
) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected_verdict = VERDICT_BY_OUTCOME_PHRASE[verdict_phrase]
    assert result.verdict is expected_verdict, (
        f"expected verdict {expected_verdict.value}, got {result.verdict.value} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r})"
    )
    expected_exit = EXIT_CODE_BY_VERDICT[expected_verdict]
    assert result.exit_code == expected_exit, (
        f"expected exit code {expected_exit} for verdict "
        f"{expected_verdict.value}, got {result.exit_code}"
    )


@then(
    parsers.re(r"the reuse-first check reports (?P<count_phrase>\w+) NEW components?")
)
def then_reports_count(result_box: dict[str, object], count_phrase: str) -> None:
    result = result_box["result"]
    assert isinstance(result, CheckResult)
    expected = COMPONENT_COUNT_BY_PHRASE[count_phrase]
    assert result.new_component_count == expected, (
        f"expected {expected} NEW component(s), got {result.new_component_count} "
        f"(exit_code={result.exit_code}, stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}) -- the base-branch / scoped-path override "
        f"detector did not report the expected commit-range component cardinality"
    )
