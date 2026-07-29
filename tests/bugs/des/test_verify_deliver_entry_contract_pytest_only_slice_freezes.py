"""Regression: a pytest-only-authored slice must freeze at DELIVER entry.

DEFECT (agnostic-at-discovery-ssot-repair, gap 1 -- the HIGHEST-severity of six
extension-keyed AT-discovery sites measured in this tree): `_slice_without_at_module`
(`src/des/cli/verify_deliver_entry_contract.py`) resolves a Slice-Plan row's
authored AT module through `_authored_slice_tags`, which imports ONLY
`feature_at_files.feature_tag_files` -- the Gherkin `.feature`-file resolver.
A slice whose ATs are pytest-authored (no `.feature` file anywhere) is
therefore reported as having NO authored AT module and the contract-freeze
gate FAILS, even though a genuine, tag-bound, active-RED pytest AT exists on
disk. This is worse than the already-fixed `carpaccio_slice_gate` defect
(ADR-AAD-001): it is the contract-FREEZE gate, the FIRST gate at DELIVER
entry, upstream of carpaccio -- a feature whose slices are ALL pytest-authored
can never even reach carpaccio.

The fix composes the EXISTING agnostic resolvers this repo already ships
(`feature_at_files.feature_tagged_test_files` /
`feature_at_files.resolve_test_file_attribution`, the SAME pair
`slice_at_completeness.feature_files_for_slice` already unions with the
Gherkin path) into `_authored_slice_tags` -- no new discovery mechanism, per
ADR-AAD-001's own "reuse, do not invent" precedent.

Driving surface (Mandate 16): the REAL `des verify-deliver-entry-contract`
gate, driven in-process via `tests/common/in_process_cli.run_cli_in_process`
-- the same fixture shape
`test_verify_deliver_entry_contract_rejection_names_repair_tool.py` already
establishes for this gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker


_FEATURE_ID = "f-pytest-only-slice-freeze-fixture"

_SLICE_PLAN = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|-------|-----------------|--------|------------|---------------|\n"
    "| slice-01 | A thin DELIVER-IN vertical. | pending | "
    "@walking-skeleton @driving_port | ~4 ATs. |\n"
)
_ARCH_TESTS = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\n"
    "| ID | Contract | SUT | Verdict | Consumed-by |\n"
    "|----|----------|-----|---------|-------------|\n"
    "| CT-1 | a contract is frozen | x::main | FAIL | DISTILL |\n"
)
_ADR_REFS = "## Wave: DESIGN / [REF] ADR Refs\n\n- slice-01: ADR-FLOW-004\n"
_REUSE_ANALYSIS = (
    "## Reuse Analysis\n\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|--------------------|------|---------|----------|---------------|\n"
    "| gate | x.py | none | CREATE_NEW | new gate. |\n"
)


def _write_feature_delta(repo_root: Path) -> None:
    feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    sections = [_ARCH_TESTS, _ADR_REFS, _SLICE_PLAN, _REUSE_ANALYSIS]
    header = f"# Feature Delta: {_FEATURE_ID}\n\n"
    (feature_dir / "feature-delta.md").write_text(
        header + "\n".join(sections) + "\n", encoding="utf-8"
    )


def _write_slice_01_pytest_at_module(repo_root: Path) -> None:
    """A pytest-collectible test file head-tagged `@feature-{id} @slice-01` --
    NO `.feature` file exists anywhere under `repo_root`."""
    at_dir = repo_root / "tests" / "acceptance" / _FEATURE_ID.replace("-", "_")
    at_dir.mkdir(parents=True, exist_ok=True)
    (at_dir / "test_slice_01_walking_skeleton.py").write_text(
        f"# @feature-{_FEATURE_ID} @slice-01\n"
        "def test_the_thin_vertical_is_exercised():\n"
        "    assert True\n",
        encoding="utf-8",
    )


def _run_freeze_gate(repo_root: Path) -> dict[str, object]:
    _exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-deliver-entry-contract",
            "--feature-id",
            _FEATURE_ID,
            "--repo-root",
            str(repo_root),
            "--format=json",
        ],
        cwd=repo_root,
    )
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        return json.loads(line)
    raise AssertionError(
        f"no JSON verdict envelope on stdout -- stdout={stdout!r} stderr={stderr!r}"
    )


def test_pytest_only_authored_slice_freezes(tmp_path: Path) -> None:
    """POSITIVE AT (active-RED today): a feature-delta whose ONE planned slice
    is backed EXCLUSIVELY by a pytest AT module (no `.feature` file anywhere)
    must PASS the contract-freeze gate -- the TESTS-half of the contract is
    genuinely complete, just not Gherkin-shaped.

    ACTIVE-RED today: `_authored_slice_tags` scans only `.feature` files, so
    `slice-01` is reported unbacked and the gate FAILS with
    'no .feature carrying both @feature-... and @slice-01' even though the
    pytest AT genuinely exists and is tag-bound.
    """
    _write_feature_delta(tmp_path)
    _write_slice_01_pytest_at_module(tmp_path)
    seed_dev_checkout_marker(tmp_path)

    envelope = _run_freeze_gate(tmp_path)

    assert envelope["verdict"] == "pass", (
        f"a feature-delta whose one planned slice is backed by a genuine "
        f"pytest AT module (no .feature file) must PASS -- got "
        f"verdict={envelope['verdict']!r}, diagnostic={envelope['diagnostic']!r}"
    )
    assert str(envelope["diagnostic"]) == "", (
        f"a PASS carries an empty diagnostic -- got "
        f"diagnostic={envelope['diagnostic']!r}"
    )


@pytest.mark.negative_at
def test_pytest_only_slice_with_no_at_module_still_fails(tmp_path: Path) -> None:
    """NEGATIVE AT (invariance pin -- green today, stays green after the fix):
    a feature-delta whose planned slice has NO authored AT module at all
    (neither Gherkin NOR pytest) must still FAIL. The fix widens WHAT counts
    as an authored AT module; it must never widen into accepting NOTHING."""
    _write_feature_delta(tmp_path)
    # No AT module of any kind written.
    seed_dev_checkout_marker(tmp_path)

    envelope = _run_freeze_gate(tmp_path)

    assert envelope["verdict"] == "fail", (
        f"a genuinely-unbacked slice must still FAIL after the fix -- got "
        f"verdict={envelope['verdict']!r}, diagnostic={envelope['diagnostic']!r}"
    )
    assert "slice-01" in str(envelope["diagnostic"])
