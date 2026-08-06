"""Regression: `des run-contract-gate --feature-id` (`_mode_feature_scoped`)
must clear a pytest-only feature, not vacuously refuse it.

DEFECT (agnostic-at-discovery-ssot-repair, gap 2): `_mode_feature_scoped`
resolves a feature's AT scope through `_feature_tag_files` -- the Gherkin
`.feature`-file resolver -- ONLY. When a feature owns zero `.feature` files it
immediately refuses `FeatureScopeMalformed reason="zero-collected"`
("no .feature file resolves ... the scoped contract gate would pass
vacuously"), even when the feature's ATs are genuinely delivered as
head-comment-tagged pytest files on disk.

This is not merely the direct `des run-contract-gate --feature-id` escape
hatch (itself still a live, documented HOW-routing target,
`run_contract_gate.py:2792`): it is also the E2 leg `des commit-slice
--feature-id` subprocess-invokes (`verify_slice_commit_completeness.
_run_contract_gate`) for any commit where `--at-kind` was not explicitly
declared. That caller's own inference helper
(`_infer_pytest_regression_at_kind`) only recognizes the NARROWER
path-naming-CONVENTION taxonomy (`tests/**/{feature_dir}/test_{slice}_*.py`)
-- a pytest AT delivered via the head-comment-tag convention at an arbitrary
path (the SAME convention ADR-AAD-001 and gap 1 of this repair already trust
as first-class) falls through to the gherkin default and hits this exact
refusal.

The fix composes the SAME agnostic resolvers ADR-AAD-001 established
(`feature_at_files.feature_tagged_test_files` /
`resolve_test_file_attribution` / `is_pytest_collectible`) as a PYTEST arm,
parallel to the existing Gherkin arm, instead of inventing a new discovery
mechanism -- no cargo-style carve-out was ever added for the plain-pytest
case, unlike the cargo run-facet (`run_contract_gate.py:2973-2989`), which
already has one.

Driving surface: `_mode_feature_scoped(repo, feature_id, entering_slice)`
called directly, in-process -- the SAME driving pattern
`test_collector_marker_filter_target_agnostic.py` already establishes for
this exact function (no subprocess, no git repo required -- `_mode_
feature_scoped` degrades gracefully with no committed HEAD).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.run_contract_gate import _mode_feature_scoped


def _last_json_event_on_stdout(stdout_text: str) -> dict[str, object]:
    """Parse the LAST single-line JSON object `_mode_feature_scoped` printed."""
    events: list[dict[str, object]] = []
    for line in stdout_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    if not events:
        raise AssertionError(f"no JSON event found on stdout: {stdout_text!r}")
    return events[-1]


def _write_pytest_only_at(
    project_dir: Path, feature_id: str, slice_id: str, *, rel_dir: str
) -> None:
    """A pytest-collectible AT head-tagged for `feature_id`/`slice_id`, at an
    ARBITRARY path that does NOT satisfy the path-naming-convention taxonomy
    (`test_{slice_us}_*.py` under `{feature_dir}/`) -- proving resolution
    comes from the head-tag, not the filename convention.
    """
    scope_dir = project_dir / rel_dir
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "__init__.py").write_text("", encoding="utf-8")
    (scope_dir / "test_login_flow.py").write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        "def test_login_flow_behaviour():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )


def _write_shared_multi_slice_at(
    project_dir: Path,
    feature_id: str,
    slice_ids: tuple[str, ...],
    *,
    rel_dir: str,
) -> None:
    """A single pytest-collectible AT file head-tagged with SEVERAL
    `@slice-NN` lines in one head-comment block. Every qualifying tag must
    contribute to `collected_slice_tags`, not only the first-declared one.
    """
    scope_dir = project_dir / rel_dir
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "__init__.py").write_text("", encoding="utf-8")
    header = f"# @feature-{feature_id}\n" + "".join(
        f"# @{slice_id}\n" for slice_id in slice_ids
    )
    (scope_dir / "test_shared_slices.py").write_text(
        header + "def test_shared_behaviour():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )


def test_pytest_only_feature_clears_instead_of_vacuous_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE (active-RED today): a feature delivered EXCLUSIVELY via a
    head-tagged pytest AT (no `.feature` file anywhere, no glob-convention
    filename) must clear the feature-scoped M-1/M-8 floor -- not refuse
    `zero-collected` for a reason unrelated to the operator's code.
    """
    feature_id = "gap2-pytest-only-feature-probe"
    entering_slice = "slice-01"
    project_dir = tmp_path / "pytest_only_repo"
    project_dir.mkdir(parents=True)
    _write_pytest_only_at(
        project_dir,
        feature_id,
        entering_slice,
        rel_dir=f"tests/acceptance/{feature_id.replace('-', '_')}",
    )

    exit_code = _mode_feature_scoped(project_dir, feature_id, entering_slice)
    event = _last_json_event_on_stdout(capsys.readouterr().out)

    assert exit_code == 0 and event.get("event") == "FeatureScopeCleared", (
        "a feature delivered exclusively via a head-tagged pytest AT must "
        f"clear the M-1/M-8 floor -- got exit {exit_code}, event {event!r}"
    )
    assert event.get("reason") not in {"zero-collected", "empty-intersection"}, (
        f"must never carry a vacuous-refusal reason on a genuine clear: {event!r}"
    )
    assert event.get("collected_node_ids") == 1, (
        f"expected exactly 1 real collected node-id -- got {event!r}"
    )


@pytest.mark.negative_at
def test_entering_slice_not_tagged_still_refuses_empty_intersection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE (invariance pin): a pytest-only feature whose AT files exist
    but carry NO `@<entering_slice>` tag must still refuse
    `empty-intersection` -- the M-8 floor must not be widened into accepting
    an unrelated slice's AT as coverage for the entering one."""
    feature_id = "gap2-pytest-only-wrong-slice-probe"
    project_dir = tmp_path / "pytest_only_wrong_slice_repo"
    project_dir.mkdir(parents=True)
    _write_pytest_only_at(
        project_dir,
        feature_id,
        "slice-02",
        rel_dir=f"tests/acceptance/{feature_id.replace('-', '_')}",
    )

    exit_code = _mode_feature_scoped(project_dir, feature_id, "slice-01")
    event = _last_json_event_on_stdout(capsys.readouterr().out)

    assert exit_code == 2 and event.get("reason") == "empty-intersection", (
        "a pytest-only feature with an AT for a DIFFERENT slice must still "
        f"refuse empty-intersection -- got exit {exit_code}, event {event!r}"
    )


@pytest.mark.negative_at
def test_genuinely_no_at_of_either_kind_still_refuses_zero_collected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE (invariance pin): a feature with NO `.feature` file AND NO
    head-tagged pytest file at all must still refuse `zero-collected` -- the
    fix widens WHAT counts as an authored AT; it must never widen into
    accepting NOTHING."""
    feature_id = "gap2-genuinely-empty-feature-probe"
    project_dir = tmp_path / "genuinely_empty_repo"
    project_dir.mkdir(parents=True)
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    exit_code = _mode_feature_scoped(project_dir, feature_id, "slice-01")
    event = _last_json_event_on_stdout(capsys.readouterr().out)

    assert exit_code == 2 and event.get("reason") == "zero-collected", (
        f"a genuinely-empty feature scope must still refuse -- got exit "
        f"{exit_code}, event {event!r}"
    )


def test_shared_multi_slice_at_file_contributes_only_qualifying_tags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE (fix-multi-slice-shared-at-file): a single pytest AT file
    head-tagged with SEVERAL `@slice-NN` lines, entered from a slice in the
    MIDDLE of the tagged range, must contribute EVERY qualifying tag to
    `collected_slice_tags` (not only the first-declared one) while a tag
    whose slice number EXCEEDS `entering_number` is excluded from
    `collected_slice_tags` -- even though the shared file's node is still
    kept because at least one OTHER tag on that same file qualifies.

    Concrete shape: the shared file is tagged `@slice-02`, `@slice-03`,
    `@slice-06`; a SEPARATE file (a distinct, realistic AT authored FOR
    slice-04 itself) is tagged `@slice-04` only -- the entering slice must
    itself own an AT somewhere in the feature for `_mode_feature_scoped`'s
    `empty-intersection` precondition to pass (M-8 floor: refuse when the
    entering slice has genuinely zero AT anywhere). Entering `slice-04`:
    `slice-02` and `slice-03` qualify (<= 4) on the shared file; `slice-06`
    does not (> 4); `slice-04` qualifies on its own dedicated file. Before
    the fix, `resolve_test_file_attribution.slice_id` (the `.search()`-based
    single match) resolved only the FIRST declared tag (`slice-02`) for the
    shared file, so this partial-qualification, multi-tag-contribution shape
    was never exercised by any existing fixture at the `_mode_feature_scoped`
    driving surface -- every prior fixture reaching
    `_narrow_to_shipped_entering_pytest` via this entry point carried
    exactly one `@slice-NN` tag per file.
    """
    feature_id = "gap2-shared-multi-slice-partial-qualification-probe"
    entering_slice = "slice-04"
    project_dir = tmp_path / "shared_multi_slice_repo"
    project_dir.mkdir(parents=True)
    rel_dir = f"tests/acceptance/{feature_id.replace('-', '_')}"
    _write_shared_multi_slice_at(
        project_dir,
        feature_id,
        ("slice-02", "slice-03", "slice-06"),
        rel_dir=rel_dir,
    )
    _write_pytest_only_at(project_dir, feature_id, "slice-04", rel_dir=rel_dir)

    exit_code = _mode_feature_scoped(project_dir, feature_id, entering_slice)
    event = _last_json_event_on_stdout(capsys.readouterr().out)

    assert exit_code == 0 and event.get("event") == "FeatureScopeCleared", (
        "a shared multi-slice AT file with at least one qualifying tag must "
        f"clear the feature scope -- got exit {exit_code}, event {event!r}"
    )
    assert event.get("collected_slice_tags") == [
        "slice-02",
        "slice-03",
        "slice-04",
    ], (
        "collected_slice_tags must carry EVERY qualifying tag off the "
        "shared file (slice-02 AND slice-03, both <= entering slice-04) "
        "plus the dedicated slice-04 file's own tag, and MUST exclude "
        f"slice-06 (> entering slice-04) -- got {event!r}"
    )
    assert event.get("collected_node_ids") == 2, (
        "both AT files' nodes must be KEPT: the shared file because "
        "slice-02/slice-03 qualify (even though slice-06 does not), and the "
        f"dedicated slice-04 file because its own tag qualifies -- got {event!r}"
    )
