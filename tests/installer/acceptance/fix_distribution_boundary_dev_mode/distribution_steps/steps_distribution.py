"""Step bindings for the distribution boundary carpaccio slice.

Per Mandate-12: step bodies ≤2 statements, no control flow, all delegating
to the composition root. Per Mandate-13: drive via `find_git_root`
function entry point on real tmp_path filesystem, never internal field
introspection.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, then, when


@given("the distribution boundary resolver `find_git_root` is loaded")
def given_resolver_loaded(composition) -> None:
    assert composition is not None


@given("a tmp directory containing a `.git/` subdirectory")
def given_tmp_with_git(composition, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    composition.stage_start_path(tmp_path)


@given(
    "a tmp directory containing a `.git/` subdirectory and a nested "
    "subdirectory `child/grandchild/`"
)
def given_tmp_with_git_and_nested(composition, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    grandchild = tmp_path / "child" / "grandchild"
    grandchild.mkdir(parents=True)
    composition.stage_start_path(grandchild)


@given("a tmp directory with NO `.git/` directory anywhere in its tree")
def given_tmp_no_git(composition, tmp_path: Path) -> None:
    # tmp_path is created clean by pytest; no .git/ added.
    composition.stage_start_path(tmp_path)


@when("the resolver walks parents from inside that tmp directory")
def when_resolve_from_tmp(composition) -> None:
    composition.resolve()


@when("the resolver walks parents from the `child/grandchild/` subdirectory")
def when_resolve_from_grandchild(composition) -> None:
    composition.resolve()


@then("the resolver returns the tmp directory absolute path")
def then_returns_tmp_path(composition, tmp_path: Path) -> None:
    assert composition.result == str(tmp_path.resolve()), (
        f"Expected {tmp_path.resolve()!r}, got {composition.result!r}"
    )


@then("the resolver returns the tmp directory absolute path (not the grandchild)")
def then_returns_tmp_not_grandchild(composition, tmp_path: Path) -> None:
    assert composition.result == str(tmp_path.resolve()), (
        f"Expected {tmp_path.resolve()!r}, got {composition.result!r}"
    )


@then("the resolver returns None")
def then_returns_none(composition) -> None:
    assert composition.result is None, (
        f"Expected None for customer (no .git/), got {composition.result!r}"
    )


@then(
    "the customer install fail-closed behavior is preserved (resolver returns no path)"
)
def then_customer_preserved(composition) -> None:
    # Regression-pin: resolver returns None for no-.git/ case.
    assert composition.result is None
