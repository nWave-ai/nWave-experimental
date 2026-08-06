"""Semantic laws of the installer's content-drift comparison.

`verify_directory_content` answers one question: which files under a source
directory do NOT have byte-identical counterparts under a target directory. The
P0 it guards (RCA fix-installer-silent-template-skip) is an installer that
reports "verified" while the installed tree has silently diverged.

These are properties, not examples, and the generator runs **inverted**: each
file's fate -- identical, mutated, or missing from the target -- is generated
FIRST, and the two directories are then built to realise it. The expected
drifted set is therefore known by construction and is not a second
implementation of the comparison the tests are meant to constrain.

What these laws do NOT establish: that the verifier calls this function, that
its verdict reaches the operator, or that the diagnostic names the file. Those
are composition and reporting claims, covered by
`test_validate_installation_error_reporting.py` at the `validate_installation`
boundary.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.install.install_nwave import verify_directory_content


#: Filenames a real template directory can hold, kept deliberately simple so
#: shrinking cannot erase the distinction the oracle depends on (two files must
#: stay distinguishable by name).
_NAMES = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=12
).map(lambda stem: f"{stem}.yaml")

#: Three fates, matching the three real states of an installed file.
_FATE = st.sampled_from(("identical", "mutated", "missing"))

_PLANS = st.dictionaries(_NAMES, _FATE, min_size=0, max_size=8)

_SETTINGS = settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _materialise(root: Path, plan: dict[str, str]) -> tuple[Path, Path, set[str]]:
    """Build a source/target pair realising ``plan``; return the expected drift.

    The expected drifted set comes from the plan, never from re-running the
    comparison.
    """
    source_dir = root / "source"
    target_dir = root / "target"
    source_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    expected_drift: set[str] = set()
    for name, fate in plan.items():
        content = f"# canonical {name}\n".encode()
        (source_dir / name).write_bytes(content)
        if fate == "identical":
            (target_dir / name).write_bytes(content)
        elif fate == "mutated":
            (target_dir / name).write_bytes(content + b"drift\n")
            expected_drift.add(name)
        else:  # missing: never written to the target at all
            expected_drift.add(name)
    return source_dir, target_dir, expected_drift


@_SETTINGS
@given(plan=_PLANS)
def test_every_source_file_is_either_matched_or_drifted(tmp_path_factory, plan):
    """Conservation: no source file is lost, duplicated, or invented."""
    root = tmp_path_factory.mktemp("conservation")
    source_dir, target_dir, _ = _materialise(root, plan)

    matched, drifted = verify_directory_content(source_dir, target_dir)

    assert matched + len(drifted) == len(plan)
    assert len(set(drifted)) == len(drifted), "a file was reported drifted twice"


@_SETTINGS
@given(plan=_PLANS)
def test_drifted_is_exactly_the_planned_divergence(tmp_path_factory, plan):
    """Decomposition: the whole agrees with the per-file fates it was built from.

    This is the law the P0 turned on. A target file that is MISSING must be
    reported as drifted, not silently treated as absent-and-therefore-fine --
    the existence-only check that shipped the bug is precisely the reading this
    property forbids.
    """
    root = tmp_path_factory.mktemp("decomposition")
    source_dir, target_dir, expected_drift = _materialise(root, plan)

    _, drifted = verify_directory_content(source_dir, target_dir)

    assert set(drifted) == expected_drift


@_SETTINGS
@given(plan=_PLANS)
def test_an_identical_target_reports_no_drift(tmp_path_factory, plan):
    """Oracle case: a faithful copy is clean, whatever the file population."""
    root = tmp_path_factory.mktemp("identity")
    identical_plan = dict.fromkeys(plan, "identical")
    source_dir, target_dir, _ = _materialise(root, identical_plan)

    matched, drifted = verify_directory_content(source_dir, target_dir)

    assert drifted == []
    assert matched == len(identical_plan)


@_SETTINGS
@given(plan=_PLANS, victim=_NAMES)
def test_mutating_one_target_file_moves_exactly_that_name_into_drift(
    tmp_path_factory, plan, victim
):
    """Metamorphic: one byte changed in the target moves one name, and only one.

    Run against an otherwise-clean install, so the observation isolates the
    effect of the mutation rather than the population's prior state.
    """
    root = tmp_path_factory.mktemp("metamorphic")
    clean_plan = dict.fromkeys({**plan, victim: "identical"}, "identical")
    source_dir, target_dir, _ = _materialise(root, clean_plan)

    before_matched, before_drifted = verify_directory_content(source_dir, target_dir)
    assert before_drifted == []

    (target_dir / victim).write_bytes(b"mutated after the clean install\n")
    after_matched, after_drifted = verify_directory_content(source_dir, target_dir)

    assert after_drifted == [victim]
    assert after_matched == before_matched - 1


@_SETTINGS
@given(plan=_PLANS, extra=_NAMES)
def test_a_target_only_file_is_not_reported(tmp_path_factory, plan, extra):
    """Scope: the comparison answers about SOURCE files, not target leftovers.

    A file present only in the target is out of scope here -- reporting it would
    make every stale leftover look like drift of something the installer ships.
    """
    root = tmp_path_factory.mktemp("scope")
    source_dir, target_dir, expected_drift = _materialise(root, plan)
    if extra not in plan:
        (target_dir / extra).write_bytes(b"leftover from an older install\n")

    matched, drifted = verify_directory_content(source_dir, target_dir)

    assert set(drifted) == expected_drift
    assert matched + len(drifted) == len(plan)
