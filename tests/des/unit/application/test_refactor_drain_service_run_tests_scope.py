"""Unit test -- RefactorDrainService._run_tests wires real changed_paths.

BUGFIX regression for
[[impacted-test-selector-selects-everything-and-its-premise-is-false]]: the
call used to always pass ``()`` to the selector, so even a correct selector
had nothing to narrow with. This pins the WIRING alone -- no real git worktree,
no real pytest subprocess, ``des_spawn`` is faked to write a canned envelope --
fast by construction, the narrow scope this bugfix itself is about.

FOLLOW-ON BUGFIX (same pile item, same day): the pre-agent baseline call
(``changed_paths=()``) used to still run the WHOLE repo through a real
pytest spawn -- honest per the selector's ``narrowed=False`` fallback, but
that whole-tree serial run measured over the drain's own 2700s spawn
timeout on the first live item, a hard crash. Since
``classify_green_to_green`` decides SAFE/UNSAFE from the AFTER run alone
(verified below with the actual domain function, not an assumption), the
baseline leg now never spawns pytest -- or even calls the selector -- at
all. Pinned here.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import des.application.refactor_drain_service as drain_module
from des.application.refactor_drain_service import RefactorDrainService
from des.domain.earned_verdict import TestRun
from des.domain.refactor.green_to_green import (
    GreenToGreenVerdict,
    classify_green_to_green,
)
from des.ports.driven_ports.impacted_test_selector_port import ImpactedTestSelection


class _SpySelector:
    """Records every ``select()`` call and returns a canned selection."""

    def __init__(self, selection: ImpactedTestSelection) -> None:
        self.calls: list[tuple[Path, tuple[str, ...]]] = []
        self._selection = selection

    def select(self, repo, changed_paths):
        self.calls.append((repo, changed_paths))
        return self._selection


def _fake_des_spawn_writing_green_envelope(_capability, *module_args, **kw):
    out_index = module_args.index("--out") + 1
    out_path = Path(module_args[out_index])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "schema": "nwave.test_result.v1",
                "runner": "pytest",
                "exit_code": 0,
                "collected": 1,
                "passed": 1,
                "failed": 0,
                "xfailed": 0,
                "xpassed": 0,
                "skipped": 0,
                "deselected": 0,
                "error": 0,
            }
        )
    )


def _make_service(selector) -> RefactorDrainService:
    return RefactorDrainService(
        git_worktree=Mock(),
        agent_invocation=Mock(),
        env_provision=Mock(),
        impacted_test_selector=selector,
        ledger=Mock(),
    )


def test_run_tests_passes_the_real_changed_paths_through_to_the_selector(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        drain_module, "des_spawn", _fake_des_spawn_writing_green_envelope
    )
    selection = ImpactedTestSelection(
        targets=(str(tmp_path / "narrow"),), narrowed=True
    )
    selector = _SpySelector(selection)
    service = _make_service(selector)
    changed_paths = ("src/des/adapters/driven/refactor/foo.py",)

    service._run_tests(tmp_path, changed_paths)

    assert selector.calls == [(tmp_path, changed_paths)], (
        "the real changed_paths must reach select(), never the empty tuple "
        "the pre-fix wiring always passed"
    )


def test_run_tests_uses_the_selectors_narrowed_target_not_the_worktree(
    tmp_path, monkeypatch
):
    captured_targets = []

    def _fake_spawn(_capability, *module_args, **kw):
        target_index = module_args.index("--target") + 1
        captured_targets.append(module_args[target_index])
        return _fake_des_spawn_writing_green_envelope(_capability, *module_args, **kw)

    monkeypatch.setattr(drain_module, "des_spawn", _fake_spawn)
    narrow_dir = str(tmp_path / "tests" / "des" / "refactor")
    selector = _SpySelector(ImpactedTestSelection(targets=(narrow_dir,), narrowed=True))
    service = _make_service(selector)

    service._run_tests(tmp_path, ("src/des/adapters/driven/refactor/foo.py",))

    assert captured_targets == [narrow_dir]
    assert captured_targets != [str(tmp_path)]


def test_the_pre_agent_baseline_call_never_spawns_pytest_at_all(tmp_path, monkeypatch):
    """FOLLOW-ON BUGFIX pin: ``changed_paths=()`` (the pre-agent baseline
    call) must not run a real pytest subprocess -- that whole-tree serial run
    is what exceeded the drain's own 2700s spawn timeout on the first live
    item. A spy on ``des_spawn`` proves it is never called.
    """
    spawn_calls = []
    monkeypatch.setattr(
        drain_module, "des_spawn", lambda *a, **kw: spawn_calls.append((a, kw))
    )
    selector = _SpySelector(
        ImpactedTestSelection(targets=(str(tmp_path),), narrowed=False)
    )
    service = _make_service(selector)

    result = service._run_tests(tmp_path)

    assert spawn_calls == [], (
        "the pre-agent baseline leg must never spawn a real pytest process"
    )
    assert selector.calls == [], (
        "there is nothing to narrow against yet -- the selector must not "
        "even be consulted for the baseline leg"
    )
    assert result.passed == 0
    assert result.failed == 0
    assert result.exit_code == 0


def test_the_baseline_placeholder_never_masks_a_real_after_failure(tmp_path):
    """The final verdict depends ONLY on the AFTER run, verified against the
    actual domain function (not assumed): a placeholder, all-zero baseline
    combined with a real, failing AFTER run must still classify UNSAFE.
    """
    baseline_placeholder = drain_module._UNOBSERVED_PLACEHOLDER_RUN
    failing_after = TestRun(runner="pytest", passed=3, failed=1, exit_code=1)

    outcome = classify_green_to_green(baseline_placeholder, failing_after)

    assert outcome.verdict == GreenToGreenVerdict.UNSAFE


def test_the_baseline_placeholder_does_not_block_a_real_after_success(tmp_path):
    """Symmetric to the above: a clean AFTER run still classifies SAFE even
    though the baseline was never actually observed."""
    baseline_placeholder = drain_module._UNOBSERVED_PLACEHOLDER_RUN
    clean_after = TestRun(runner="pytest", passed=5, failed=0, exit_code=0)

    outcome = classify_green_to_green(baseline_placeholder, clean_after)

    assert outcome.verdict == GreenToGreenVerdict.SAFE
