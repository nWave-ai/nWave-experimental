"""Unit tests -- HeuristicImpactedTestSelectorAdapter's real narrowing.

BUGFIX regression suite for
[[impacted-test-selector-selects-everything-and-its-premise-is-false]]: the
selector used to unconditionally return the whole repo, regardless of what
(if anything) changed. These pin the real heuristic (same-feature-directory
tests + importers of the changed module) and the GDP-8 arity corollary
(``narrowed`` must be a state DISTINCT from "the fallback happens to be
everything").

Pure filesystem fixtures -- no real git, no real pytest subprocess -- fast by
construction, never whole-tree.
"""

from __future__ import annotations

from des.adapters.driven.refactor.tsunami_impacted_test_selector_adapter import (
    HeuristicImpactedTestSelectorAdapter,
)


def test_no_changed_paths_is_reported_as_could_not_narrow_not_as_a_scope(tmp_path):
    """Given no changed paths (the drain's pre-agent baseline call), When
    selecting, Then the fallback is the whole repo AND ``narrowed`` says so
    honestly -- never indistinguishable from a real narrowing to everything.
    """
    adapter = HeuristicImpactedTestSelectorAdapter()

    selection = adapter.select(tmp_path, ())

    assert selection.targets == (str(tmp_path),)
    assert selection.narrowed is False


def test_a_change_touching_one_module_narrows_to_its_feature_directory_not_the_whole_tree(
    tmp_path,
):
    """The negative oracle: a change scoped to ONE module must not make the
    selector collect the entire test tree. Build a repo with many UNRELATED
    test directories plus one real match, and assert the selection is the
    narrow directory, never the repo root.
    """
    tests_root = tmp_path / "tests"
    relevant_dir = tests_root / "des" / "refactor"
    relevant_dir.mkdir(parents=True)
    (relevant_dir / "test_thing.py").write_text(
        "from des.adapters.driven.refactor.tsunami_impacted_test_selector_adapter "
        "import HeuristicImpactedTestSelectorAdapter\n"
        "def test_it():\n    assert HeuristicImpactedTestSelectorAdapter()\n"
    )
    # A large number of UNRELATED test directories -- if the selector fell
    # back to the whole tree, these would all be "selected" too.
    for i in range(20):
        unrelated_dir = tests_root / "unrelated" / f"area_{i}"
        unrelated_dir.mkdir(parents=True)
        (unrelated_dir / "test_noise.py").write_text(
            f"def test_noise_{i}():\n    assert True\n"
        )

    changed_paths = (
        "src/des/adapters/driven/refactor/tsunami_impacted_test_selector_adapter.py",
    )
    adapter = HeuristicImpactedTestSelectorAdapter()

    selection = adapter.select(tmp_path, changed_paths)

    assert selection.narrowed is True, "a real importer match must narrow"
    assert selection.targets == (str(relevant_dir),)
    assert selection.targets != (str(tmp_path),), (
        "a change scoped to one module must never collect the whole tree"
    )
    for i in range(20):
        assert f"area_{i}" not in selection.targets[0], (
            "unrelated test areas must not leak into the narrowed target"
        )


def test_same_feature_directory_name_is_found_even_without_an_import_match(tmp_path):
    """Given a changed file whose own tests never literally import its dotted
    module path (e.g. exercised only via a CLI subprocess), the same-feature-
    directory-name rule still narrows to the co-located feature tests.
    """
    tests_root = tmp_path / "tests"
    feature_dir = tests_root / "des" / "refactor"
    feature_dir.mkdir(parents=True)
    (feature_dir / "test_walking_skeleton.py").write_text(
        "def test_walking_skeleton():\n    assert True\n"
    )
    other_dir = tests_root / "des" / "unrelated_feature"
    other_dir.mkdir(parents=True)
    (other_dir / "test_other.py").write_text("def test_other():\n    assert True\n")

    adapter = HeuristicImpactedTestSelectorAdapter()

    selection = adapter.select(
        tmp_path, ("src/des/adapters/driven/refactor/some_other_file.py",)
    )

    assert selection.narrowed is True
    assert selection.targets == (str(feature_dir),)


def test_a_change_with_no_candidate_falls_back_honestly_to_the_whole_repo(tmp_path):
    """A changed path with no matching feature directory and no importer
    anywhere: the heuristic genuinely found nothing, so it falls back to the
    whole repo -- but declares ``narrowed=False``, never pretending it
    restricted anything.
    """
    (tmp_path / "tests").mkdir()
    adapter = HeuristicImpactedTestSelectorAdapter()

    selection = adapter.select(tmp_path, ("src/des/nonexistent/orphan_module.py",))

    assert selection.targets == (str(tmp_path),)
    assert selection.narrowed is False
