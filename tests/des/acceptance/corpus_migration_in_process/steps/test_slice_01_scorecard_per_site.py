"""Step definitions: the migration scorecard --per-site contract.

f-test-corpus-migration-in-process slice-01 (DESIGN DDD-5 EXTEND the scorecard:
file-level = gradient tracker; --per-site = the un-gameable DONE contract).

Layer 3 (in-process composition acceptance). The scorecard content facet is driven
IN-PROCESS via main(argv) with stdout captured; the ONE @walking_skeleton scenario
proves the installed script is wired end-to-end (the terminal-wiring facet) --- and
is THE single legitimate subprocess fork in this feature's own AT corpus.

  # @walking_skeleton: the subprocess fork below lives EXCLUSIVELY in the
  # @walking_skeleton wiring step (when_run_installed_script_end_to_end). It is the
  # one legitimate subprocess-e2e survivor per the per-site classification rule this
  # feature ships (ADR-TEST-003); no non-WS scenario in this file reaches it.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD at_corpus_migration_scorecard
.main has signature main() (no argv) and no --per-site flag, so driving the future
main(argv) shape raises inside the call and emits no per-site JSON --- every
observable RED-fails for the right reason. Collection imports only the present
composition.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when

from .domain_types import WsWiringOutcome


if TYPE_CHECKING:
    from .composition import CorpusMigrationComposition


scenarios("../slice-01-scorecard-per-site.feature")


_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCORECARD_PATH = _REPO_ROOT / "scripts" / "at_corpus_migration_scorecard.py"


# --- Given -------------------------------------------------------------------


@given("the maintainer can drive the migration scorecard in-process")
def given_scorecard(composition: CorpusMigrationComposition, tmp_path: Path) -> None:
    composition.given_corpus(tmp_path)


# --- When --------------------------------------------------------------------


@when("the maintainer runs the scorecard in per-site mode in-process")
def when_per_site(composition: CorpusMigrationComposition) -> None:
    composition.drive_scorecard_per_site()


@when("the maintainer runs the scorecard in file-level mode in-process")
def when_file_level(composition: CorpusMigrationComposition) -> None:
    composition.drive_scorecard_file_level()


@when(
    "the maintainer runs the installed scorecard script with the per-site mode end-to-end"
)
def when_run_installed_script_end_to_end(
    composition: CorpusMigrationComposition,
) -> None:
    # @walking_skeleton: the ONE legitimate subprocess fork --- proves the installed
    # scorecard script reaches a real terminal with the new --per-site mode wired.
    # At HEAD --per-site is unknown -> argparse exit 2 -> the named RED.
    proc = subprocess.run(
        [sys.executable, str(_SCORECARD_PATH), "--per-site", "--json"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        check=False,
    )
    captured = f"{proc.stdout}\n{proc.stderr}"
    composition._ws_wiring = WsWiringOutcome(
        script_wired=proc.returncode == 0 and "per_site_non_ws_count" in proc.stdout,
        exit_code=proc.returncode,
        emitted_per_site_json="per_site_non_ws_count" in proc.stdout,
        captured_output=captured,
        diagnostic=f"returncode={proc.returncode}",
    )


# --- Then: per-site content ---------------------------------------------------


@then("the scorecard reports a per-site non-walking-skeleton spawn-site count")
def then_per_site_count(composition: CorpusMigrationComposition) -> None:
    assert composition.scorecard().per_site_non_ws_count is not None, (
        "the scorecard --per-site mode must report a per-scenario non-WS spawn-site "
        "count (the un-gameable DONE number) --- but at HEAD main() has no argv and "
        f"no --per-site flag, so no per-site count is emitted. {composition.diag()}"
    )


@then("the scorecard per-site mode is recognized")
def then_per_site_recognized(composition: CorpusMigrationComposition) -> None:
    assert composition.scorecard().per_site_mode_available, (
        "the scorecard must RECOGNISE the --per-site flag on main(argv) --- but at "
        f"HEAD it is an unknown argument. {composition.diag()}"
    )


@then("the scorecard did not fork an interpreter for the per-site count")
def then_per_site_no_fork(composition: CorpusMigrationComposition) -> None:
    assert not composition.scorecard().forked_interpreter, (
        "the scorecard content facet must be driven IN-PROCESS via main(argv), no "
        f"interpreter fork. {composition.diag()}"
    )


@then("the per-site JSON output carries the per-site count field")
def then_json_count_field(composition: CorpusMigrationComposition) -> None:
    assert "per_site_non_ws_count" in composition.scorecard().json_fields, (
        "OPEN QUESTION 4: the --per-site JSON must carry `per_site_non_ws_count` "
        f"(the per-batch gate's DONE number) --- absent at HEAD. {composition.diag()}"
    )


@then("the per-site JSON output carries the per-scenario records field")
def then_json_by_scenario_field(composition: CorpusMigrationComposition) -> None:
    assert "by_scenario" in composition.scorecard().json_fields, (
        "OPEN QUESTION 4: the --per-site JSON must carry `by_scenario` (the "
        "per-scenario {file, scenario, tags, spawn_line, decision} records that "
        f"prove the mixed-file forks are counted) --- absent at HEAD. {composition.diag()}"
    )


@then("the per-site JSON output carries the per-directory heat-map field")
def then_json_by_dir_field(composition: CorpusMigrationComposition) -> None:
    assert "by_dir" in composition.scorecard().json_fields, (
        "OPEN QUESTION 4: the --per-site JSON must carry `by_dir` (the per-directory "
        f"heat-map the per-batch gate drains, DDD-3) --- absent at HEAD. {composition.diag()}"
    )


@then("the per-site JSON output carries the done field")
def then_json_done_field(composition: CorpusMigrationComposition) -> None:
    assert "done" in composition.scorecard().json_fields, (
        "OPEN QUESTION 4: the --per-site JSON must carry `done` (per_site_non_ws_count "
        f"== 0) --- absent at HEAD. {composition.diag()}"
    )


@then("the scorecard still emits its file-level gradient split")
def then_file_level_split(composition: CorpusMigrationComposition) -> None:
    assert composition.scorecard().file_level_mode_works, (
        "the file-level gradient tracker (pure/mixed split) must SURVIVE the "
        "--per-site extension --- but at HEAD main(argv) does not exist, so driving "
        f"main(['--json']) raises inside the call. {composition.diag()}"
    )


@then("the scorecard reports the phase done only when the per-site count is zero")
def then_done_iff_zero(composition: CorpusMigrationComposition) -> None:
    s = composition.scorecard()
    assert s.per_site_non_ws_count is not None and s.done == (
        s.per_site_non_ws_count == 0
    ), (
        "the scorecard --per-site DONE flag must be exactly `per_site_non_ws_count "
        "== 0` --- but at HEAD no per-site count is emitted, so the DONE contract is "
        f"unobservable. {composition.diag()}"
    )


# --- Then: @walking_skeleton terminal-wiring ----------------------------------


@then("the installed scorecard script exits successfully")
def then_script_exits_ok(composition: CorpusMigrationComposition) -> None:
    assert (
        composition._ws_wiring is not None and composition._ws_wiring.exit_code == 0
    ), (
        "the installed scorecard script must exit 0 under `--per-site --json` "
        "(proving the new mode is wired end-to-end) --- but at HEAD --per-site is "
        f"unknown, so argparse exits 2. {composition._ws_wiring}"
    )


@then("the installed scorecard script emits the per-site count on its terminal output")
def then_script_emits_count(composition: CorpusMigrationComposition) -> None:
    assert (
        composition._ws_wiring is not None
        and composition._ws_wiring.emitted_per_site_json
    ), (
        "the installed scorecard script must emit `per_site_non_ws_count` on its "
        f"terminal output (the wired contract) --- absent at HEAD. {composition._ws_wiring}"
    )
