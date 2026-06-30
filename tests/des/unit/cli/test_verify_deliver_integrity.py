"""Unit tests for verify_deliver_integrity CLI: atdd_pure ledger-based verdict."""

import subprocess
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_deliver_integrity import (
    _find_at_completion_ledger,
    main,
)


# f-finalize-verify-single-spine slice-01: TestExtractStepIds + TestParseExecutionLog
# were removed -- they pinned `_extract_step_ids` / `_parse_execution_log`, the
# classic-only roadmap/execution-log helpers deleted with the classic finalize leg.
# The surviving classes exercise the atdd_pure ledger-based verdict, the only spine.


class TestMainArgvParameter:
    """Tests for main() accepting optional argv parameter (step 01-02)."""

    def test_main_accepts_argv_parameter_for_nonexistent_path(self):
        """main(argv=[path]) accepts the explicit argv (no sys.argv patching).

        DDD-7 (slice-03 mode-resolution SSOT): a nonexistent project dir has no
        `.nwave/config.yaml`, which now resolves to atdd_pure. Under atdd_pure the
        verifier targets the AT-completion ledger; the absent telemetry dir is an
        INTEGRITY VIOLATION -> exit 1 (was exit 2 under the prior classic default,
        which short-circuited on the missing roadmap). The argv-acceptance contract
        this test pins (main accepts an explicit argv list) is unchanged.
        """
        result = main(argv=["/tmp/nonexistent_nwave_test_dir"])
        assert result == 1

    def test_main_sys_argv_fallback_preserved(self, monkeypatch):
        """main() with no args falls back to sys.argv; nonexistent path returns 1.

        DDD-7: nonexistent dir -> no config -> atdd_pure -> ledger missing ->
        INTEGRITY VIOLATION exit 1 (was exit 2 under the prior classic default).
        The sys.argv-fallback contract this test pins is unchanged.
        """
        monkeypatch.setattr(sys, "argv", ["prog", "/tmp/nonexistent_nwave_test_dir"])
        result = main()
        assert result == 1


def _write_atdd_pure_config(project_dir: Path) -> None:
    """Write a minimal .nwave/config.yaml selecting atdd_pure mode."""
    nwave_dir = project_dir / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "config.yaml").write_text("workflow:\n  mode: atdd_pure\n")


def _make_git_work_tree(project_dir: Path) -> None:
    """Make ``project_dir`` a real git work-tree with one trailer-less commit.

    gate-trailer-read-git-port-extract slice-01 flipped `_shipped_slices` from
    a silent `return frozenset()` on git-absence to a LOUD cannot-evaluate
    refusal (exit 4). A reconciliation-demanding ledger (a `SliceCommitVerified`
    record) in a NON-git tmp_path therefore now refuses LOUD before reaching the
    feature-end check -- which masks the ledger-targeting guard this test
    exercises. The single commit carries NO `Slice-Id:` trailer, so
    `_shipped_slices` reads the (real, readable) history as an empty shipped set:
    reconciliation is skipped and the verifier proceeds to the feature-end-cycle
    check on the targeted feature -- the exact discriminating path the
    ledger-targeting false-PASS guard pins.
    """
    run = lambda *a: subprocess.run(  # noqa: E731 -- terse local git driver
        ["git", *a], cwd=project_dir, check=True, capture_output=True, text=True
    )
    run("init", "-q")
    run("config", "user.email", "t@t.com")
    run("config", "user.name", "T")
    (project_dir / "README.md").write_text("ledger-targeting guard\n")
    run("add", "-A")
    run("commit", "-q", "-m", "base commit (no Slice-Id trailer)")


def _complete_feature_end_ledger(project_dir: Path, feature_id: str) -> None:
    """Write a ledger whose feature-end cycle ran (every U4-required record).

    The U4-required record set is seeded structurally via the shared helper
    (`tests/des/_helpers/feature_end_seeding.seed_required_feature_end_records`
    + its `_RECORD_WRITERS` registry) -- the F-FROZENSET-EXTENSION-FIXTURE-
    CASCADE detector neutralises the historical pain of adding each new
    required record (env-e2e, walking-skeleton, both coverage-map touchpoints)
    in lockstep across 6 fixture sites. The arch test
    `tests/des/unit/test_required_record_writer_registry.py` keeps the
    helper registry in sync with the production frozenset.
    """
    from tests.des._helpers.feature_end_seeding import (
        seed_required_feature_end_records,
    )

    ledger = AtCompletionLedger(feature_id, project_dir)
    seed_required_feature_end_records(ledger, verdict_hash="abc123")


class TestLedgerTargetingByFeatureId:
    """Regression: F-DELIVER-INTEGRITY-LEDGER-TARGETING.

    `_find_at_completion_ledger` used `sorted(glob("*.jsonl"))[0]` -- it picked
    the alphabetically-first ledger in a multi-feature telemetry dir, NOT the
    feature under verification. Per-feature FINAL_INTEGRITY could verify a
    different already-shipped feature's ledger and PASS (a false-PASS).
    """

    def test_find_ledger_targets_named_feature_not_alphabetical_first(self, tmp_path):
        """With ≥2 ledgers, the targeted feature's ledger is selected exactly."""
        ledger_dir = tmp_path / ".nwave" / "telemetry" / "atdd-pure"
        ledger_dir.mkdir(parents=True)
        # Alphabetically-first ledger belongs to a DIFFERENT, unrelated feature.
        (ledger_dir / "aaa-other-feature.jsonl").write_text("")
        (ledger_dir / "zzz-target-feature.jsonl").write_text("")

        found = _find_at_completion_ledger(
            tmp_path, feature_id="zzz-target-feature", explicit=True
        )

        assert found is not None
        assert found.name == "zzz-target-feature.jsonl"

    def test_find_ledger_absent_named_feature_is_failure_not_fallthrough(
        self, tmp_path
    ):
        """A missing named ledger returns None -- never falls through to another."""
        ledger_dir = tmp_path / ".nwave" / "telemetry" / "atdd-pure"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / "aaa-other-feature.jsonl").write_text("")

        found = _find_at_completion_ledger(
            tmp_path, feature_id="missing-feature", explicit=True
        )

        assert found is None

    def test_verify_does_not_false_pass_on_wrong_feature_ledger(self, tmp_path, capsys):
        """The false-PASS reproduction.

        Two ledgers: the alphabetically-first ('aaa-shipped-feature') has a
        complete feature-end cycle; the target feature ('zzz-under-test') has
        an INCOMPLETE ledger (no refactor / no review). The verifier, told the
        target feature id, must verify zzz-under-test and FAIL (exit 1) -- not
        silently verify aaa-shipped-feature and PASS.
        """
        _write_atdd_pure_config(tmp_path)
        # git-present readable history (trailer-less) so the slice-01 silent->loud
        # flip does not refuse before the ledger-targeting guard runs; see
        # `_make_git_work_tree`. The guard under test is the wrong-feature
        # false-PASS, exercised on the git-present feature-end-incomplete path.
        _make_git_work_tree(tmp_path)
        # Alphabetically-first: a different, already-shipped feature -- complete.
        _complete_feature_end_ledger(tmp_path, "aaa-shipped-feature")
        # Target feature: ledger exists but feature-end cycle never ran.
        AtCompletionLedger("zzz-under-test", tmp_path).append_gate_event(
            "SliceCommitVerified", "01"
        )

        exit_code = main(argv=[str(tmp_path), "--feature-id", "zzz-under-test"])

        out = capsys.readouterr().out
        assert exit_code == 1, (
            "false-PASS: verifier picked the wrong feature's complete ledger"
        )
        assert "zzz-under-test" in out

    def test_verify_passes_on_correct_complete_target_ledger(self, tmp_path, capsys):
        """Positive: verifying the named feature with a complete ledger passes."""
        _write_atdd_pure_config(tmp_path)
        _complete_feature_end_ledger(tmp_path, "aaa-other-feature")
        _complete_feature_end_ledger(tmp_path, "zzz-under-test")

        exit_code = main(argv=[str(tmp_path), "--feature-id", "zzz-under-test"])

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "zzz-under-test.jsonl" in out
