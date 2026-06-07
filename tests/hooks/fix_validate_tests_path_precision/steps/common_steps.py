"""Shared step vocabulary for the fix-validate-tests-path-precision suite.

Mandate-12 (SSOT via Types + Services + DSL): the slice's three scenarios
share ONE step vocabulary. Each decorator below is a parameterized template
over typed parameters (from ``domain_types.py``).

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call, and contains no control flow. Business
logic lives in ``composition.py`` and the production helper, never here.

Mandate 10 shared-vocabulary contract: the slice test binding imports ``*``
from this module and calls ``scenarios(...)`` on its own ``.feature`` file.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import ScopeResolverComposition
from .domain_types import StagedFilePath


@pytest.fixture
def composition(tmp_path) -> ScopeResolverComposition:
    """The composition root, fresh per scenario, bound to a pytest tmp_path."""
    comp = ScopeResolverComposition()
    comp.use_workspace(tmp_path)
    try:
        yield comp
    finally:
        comp.teardown()


# --- Background --------------------------------------------------------------


@given("the pre-commit test-scope resolver is loaded as the driving port")
def given_resolver_loaded(composition: ScopeResolverComposition) -> None:
    composition.load_driving_port()


# --- Given: staged-file declaration ------------------------------------------


@given(parsers.parse('the staged file list is exactly "{path}"'))
def given_single_staged_file(composition: ScopeResolverComposition, path: str) -> None:
    composition.stage_files([StagedFilePath(path)])


# --- Given: directory-existence declaration ----------------------------------


@given(parsers.parse('the directory "{relative_path}" exists on disk'))
def given_directory_exists(
    composition: ScopeResolverComposition, relative_path: str
) -> None:
    composition.ensure_directory_exists(relative_path)


@given(parsers.parse('the directories "{path_a}" and "{path_b}" both exist on disk'))
def given_two_directories_exist(
    composition: ScopeResolverComposition, path_a: str, path_b: str
) -> None:
    composition.ensure_directory_exists(path_a)
    composition.ensure_directory_exists(path_b)


# --- When: invoke the driving port -------------------------------------------


@when("the resolver computes the targeted test directories")
def when_resolve(composition: ScopeResolverComposition) -> None:
    composition.resolve_targeted_test_dirs()


# --- Then: scope-shape assertions --------------------------------------------


@then(parsers.parse('the resulting scope contains "{expected_dir}"'))
def then_scope_contains(
    composition: ScopeResolverComposition, expected_dir: str
) -> None:
    assert expected_dir in composition.scope_as_list(), (
        f"expected {expected_dir!r} in scope, got {composition.scope_as_list()!r}"
    )


@then(parsers.parse('the resulting scope does not contain "{forbidden_dir}"'))
def then_scope_excludes(
    composition: ScopeResolverComposition, forbidden_dir: str
) -> None:
    assert forbidden_dir not in composition.scope_as_list(), (
        f"expected {forbidden_dir!r} absent from scope, "
        f"got {composition.scope_as_list()!r}"
    )


@then(parsers.parse('the resulting scope contains exactly "{expected_dir}"'))
def then_scope_is_exactly(
    composition: ScopeResolverComposition, expected_dir: str
) -> None:
    assert composition.scope_as_list() == [expected_dir], (
        f"expected scope == [{expected_dir!r}], got {composition.scope_as_list()!r}"
    )
