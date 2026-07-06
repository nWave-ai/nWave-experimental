"""Step definitions: a pytest test file binds to its feature via a head-comment tag.

carpaccio-pytest-at-comment-tag-binding slice-01
(EXP-carpaccio-pytest-at-comment-tag-binding-1). Layer 3 composition-root
acceptance (Mandate 13); example-only, no PBT machinery (Mandate 9/11).

Active-RED contract: ``feature_tagged_test_files`` is a ``__SCAFFOLD__`` raising
``AssertionError`` at HEAD (``src/des/application/feature_at_files.py``). Module
top imports ONLY the stable composition + domain types -- never the absent
resolver by name -- so collection succeeds; each scenario reds AT RUNTIME
inside ``composition.resolve()`` with a semantic ``AssertionError``
(MISSING_FUNCTIONALITY), never a collection/import error (BROKEN).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import DiscoveryResult, FeatureTaggedTestFilesComposition
from .domain_types import FeatureId


scenarios("../slice-01-pytest-head-tag-discovery.feature")


_FEATURE_ID = FeatureId("test-binding-1")

_TAGGED_CONTENT = f"""\
# @feature-{_FEATURE_ID}
def test_something():
    assert True
"""

_UNTAGGED_CONTENT = """\
def test_something_else():
    assert True
"""


@pytest.fixture
def composition(tmp_path: Path) -> FeatureTaggedTestFilesComposition:
    """Production-wired composition root over a tmp_path scratch repository."""
    return FeatureTaggedTestFilesComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def written_files() -> dict[str, Path]:
    """Carrier for the real paths the scratch-repo Given steps write."""
    return {}


@pytest.fixture
def result_box() -> dict[str, DiscoveryResult]:
    """Carrier for the resolver's observable result."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    parsers.parse(
        'a scratch repository containing a pytest test file head-tagged "{tag}"'
    )
)
def given_head_tagged_file(
    tag: str,
    composition: FeatureTaggedTestFilesComposition,
    written_files: dict[str, Path],
) -> None:
    assert tag == f"@feature-{_FEATURE_ID}", f"unexpected tag in scenario text: {tag!r}"
    written_files["tagged"] = composition.write_test_file(
        "tests/test_tagged.py", _TAGGED_CONTENT
    )


@given("the repository also contains an untagged pytest test file")
def given_also_untagged_file(
    composition: FeatureTaggedTestFilesComposition,
    written_files: dict[str, Path],
) -> None:
    written_files["untagged"] = composition.write_test_file(
        "tests/test_untagged.py", _UNTAGGED_CONTENT
    )


@given("a scratch repository containing an untagged pytest test file")
def given_only_untagged_file(
    composition: FeatureTaggedTestFilesComposition,
    written_files: dict[str, Path],
) -> None:
    written_files["untagged"] = composition.write_test_file(
        "tests/test_untagged.py", _UNTAGGED_CONTENT
    )


# --- When ----------------------------------------------------------------


@when("the maintainer resolves the feature's tagged test files")
def when_resolve(
    composition: FeatureTaggedTestFilesComposition,
    result_box: dict[str, DiscoveryResult],
) -> None:
    result_box["result"] = composition.resolve(_FEATURE_ID)


# --- Then ------------------------------------------------------------------


@then("the head-tagged test file is included in the resolved file set")
def then_included(
    result_box: dict[str, DiscoveryResult], written_files: dict[str, Path]
) -> None:
    result = result_box["result"]
    assert result.includes(written_files["tagged"]), (
        "the head-tagged test file must be resolved as bound to the feature, "
        f"got resolved_files={result.resolved_files!r}"
    )


@then("the untagged test file is excluded from the resolved file set")
def then_excluded(
    result_box: dict[str, DiscoveryResult], written_files: dict[str, Path]
) -> None:
    result = result_box["result"]
    assert result.excludes(written_files["untagged"]), (
        "the untagged test file must NOT be resolved as bound to the feature "
        f"(no over-matching), got resolved_files={result.resolved_files!r}"
    )


@then("the resolved file set is empty")
def then_empty(result_box: dict[str, DiscoveryResult]) -> None:
    result = result_box["result"]
    assert result.resolved_files == (), (
        "a repository with no head-tagged test file must resolve to an empty "
        f"set, got resolved_files={result.resolved_files!r}"
    )
