"""Step definitions: the per-spawn-site classifier + enforcement gate, in-process.

f-test-corpus-migration-in-process slice-01 (DESIGN DDD-1 / ADR-TEST-003 per-site
tag-derived classification + DDD-4 EXTEND check_non_ws_spawn to per-site, scope
follows migration).

Layer 3 (in-process composition acceptance). Example-only, no PBT machinery
(Mandate 9/11): each scenario pins a single closed observable. The sad paths
(unparseable file, unrecognized language, un-migrated corpus) are enumerated
explicitly (Mandate 11).

The classifier + gate are driven through the REAL production entries
(scan_spawn_sites / check_non_ws_spawn) IN-PROCESS over synthetic tmp corpora ---
NO subprocess fork (this feature's own dog food). Step bodies delegate to
CorpusMigrationComposition; no inline business logic (Mandate-12 criterion 3).

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD scan_spawn_sites classifies
at FILE level and exposes no per-site classified_sites/per_site_verdict surface,
and check_non_ws_spawn has no migration_scope --- so every per-site observable is
empty and each Then RED-fails for the right reason. Collection imports ONLY the
present composition (which imports only present production entries), so the suite
COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when

from .domain_types import PerSiteVerdict


if TYPE_CHECKING:
    from .composition import CorpusMigrationComposition


scenarios("../slice-01-per-site-classification.feature")


# --- Given -------------------------------------------------------------------


@given("the maintainer has a synthetic acceptance corpus the classifier can scan")
def given_corpus(composition: CorpusMigrationComposition, tmp_path: Path) -> None:
    composition.given_corpus(tmp_path)


@given(
    "the corpus has a mixed file with a walking-skeleton fork and a plain "
    "non-walking-skeleton fork"
)
def given_mixed_plain_file(composition: CorpusMigrationComposition) -> None:
    composition.arm_mixed_plain_file()


@given(
    "the corpus has a mixed pytest-bdd feature whose shared step forks unconditionally"
)
def given_mixed_bdd(composition: CorpusMigrationComposition) -> None:
    composition.arm_mixed_bdd_feature()


@given(
    "the corpus has a pytest-bdd feature whose forking step is bound only to "
    "walking-skeleton scenarios"
)
def given_ws_only_bdd(composition: CorpusMigrationComposition) -> None:
    composition.arm_ws_only_bdd_feature()


@given("the corpus has a file that does not parse")
def given_unparseable(composition: CorpusMigrationComposition) -> None:
    composition.arm_unparseable_file()


@given("the corpus has a file with a non-walking-skeleton fork")
def given_non_ws_file(composition: CorpusMigrationComposition) -> None:
    composition.arm_non_ws_file()


@given(parsers.parse('the target project is written in "{language}"'))
def given_language(composition: CorpusMigrationComposition, language: str) -> None:
    composition.given_target_language(language)


@given(
    "the corpus has a migrated directory and an un-migrated directory each with a "
    "non-walking-skeleton fork"
)
def given_scoped_corpus(composition: CorpusMigrationComposition) -> None:
    # Armed inside the When (the scope-aware gate builds both subtrees).
    pass


# --- When --------------------------------------------------------------------


@when("the maintainer classifies each spawn-site in-process")
def when_classify(composition: CorpusMigrationComposition) -> None:
    composition.classify_spawn_sites()


@when(
    "the maintainer runs the enforcement gate scoped to the migrated directory in-process"
)
def when_scoped_gate(composition: CorpusMigrationComposition) -> None:
    composition.drive_scoped_gate()


# --- Then: per-site classification --------------------------------------------


@then("the non-walking-skeleton fork is classified as a migration target")
def then_non_ws_migrate(composition: CorpusMigrationComposition) -> None:
    assert composition.non_ws_fork_is_migrate(), (
        "the per-site classifier must classify a non-@walking_skeleton fork in a "
        "MIXED file as a MIGRATE target (ADR-TEST-003) --- but at HEAD the file-level "
        "short-circuit exempts the whole file and exposes no per-site classified_sites "
        f"surface, so no MIGRATE decision is produced. {composition.diag()}"
    )


@then("the non-walking-skeleton fork is not exempted as a kept walking-skeleton fork")
def then_non_ws_not_keep(composition: CorpusMigrationComposition) -> None:
    assert composition.non_ws_fork_not_keep(), (
        "the per-site classifier must NOT exempt a non-WS fork just because the file "
        "carries a WS scenario elsewhere (the 45-mixed-file / 155-fork blind spot) "
        f"--- but at HEAD no per-site resolution exists. {composition.diag()}"
    )


@then("the classifier did not fork an interpreter")
def then_classifier_no_fork(composition: CorpusMigrationComposition) -> None:
    assert not composition.classification().forked_interpreter, (
        "the per-site classifier must run IN-PROCESS (scan_spawn_sites), with no "
        f"interpreter fork. {composition.diag()}"
    )


@then("the classifier did not invoke git")
def then_classifier_no_git(composition: CorpusMigrationComposition) -> None:
    assert not composition.classification().git_invoked, (
        "the per-site classifier must NOT invoke git (the WS-tag lookup is a pure "
        f"filesystem read). {composition.diag()}"
    )


@then("the walking-skeleton fork is classified as kept")
def then_ws_keep(composition: CorpusMigrationComposition) -> None:
    assert composition.ws_fork_is_keep(), (
        "the per-site classifier must classify a fork whose enclosing scenario "
        "carries @walking_skeleton as KEEP (legitimate subprocess-e2e) --- but at "
        f"HEAD no per-site KEEP surface exists. {composition.diag()}"
    )


@then("the shared-step fork is classified as a migration target")
def then_shared_step_migrate(composition: CorpusMigrationComposition) -> None:
    assert composition.non_ws_fork_is_migrate(), (
        "OPEN QUESTION 1 resolution: an UNCONDITIONAL fork in a pytest-bdd step a "
        "non-WS scenario can reach is a MIGRATE target (the non-WS scenario must not "
        "reach a fork) --- but at HEAD no per-site / step->scenario resolution "
        f"exists. {composition.diag()}"
    )


@then("the shared-step fork is classified as kept")
def then_shared_step_keep(composition: CorpusMigrationComposition) -> None:
    assert composition.ws_fork_is_keep(), (
        "OPEN QUESTION 1 boundary: a fork whose step is bound EXCLUSIVELY to "
        "@walking_skeleton scenarios is KEEP (no non-WS scenario can reach it) --- "
        f"but at HEAD no per-site KEEP surface exists. {composition.diag()}"
    )


# --- Then: total-function degrade-LOUD verdicts -------------------------------


@then("the classifier reports the per-site verdict as indeterminate")
def then_verdict_indeterminate(composition: CorpusMigrationComposition) -> None:
    assert composition.classification().verdict is PerSiteVerdict.INDETERMINATE, (
        "the per-site classifier must report INDETERMINATE for an unparseable file "
        "(degrade-LOUD, never a silent drop) --- but at HEAD no per-site verdict "
        f"surface exists. {composition.diag()}"
    )


@then("the unparseable file is recorded rather than silently dropped")
def then_indeterminate_recorded(composition: CorpusMigrationComposition) -> None:
    c = composition.classification()
    assert c.resolution_available and c.indeterminate_sites, (
        "the per-site classifier must RECORD the unparseable file in its per-site "
        "indeterminate set (never silently drop it) --- but at HEAD no per-site "
        f"surface exists. {composition.diag()}"
    )


@then("the classifier reports the per-site verdict as not applicable")
def then_verdict_not_applicable(composition: CorpusMigrationComposition) -> None:
    assert composition.classification().verdict is PerSiteVerdict.NOT_APPLICABLE, (
        "the per-site classifier must report NOT_APPLICABLE for an unrecognized "
        "language (degrade-LOUD, no false flag) --- but at HEAD no per-site verdict "
        f"surface exists. {composition.diag()}"
    )


@then("the classifier raises no false migration flag on the unrecognized language")
def then_no_false_flag(composition: CorpusMigrationComposition) -> None:
    assert not composition.classification().migrate_sites, (
        "the per-site classifier must NEVER raise a false MIGRATE flag on an "
        f"unrecognized language (NOT_APPLICABLE, not a false positive). {composition.diag()}"
    )


# --- Then: scope-follows-migration gate ---------------------------------------


@then(
    "the enforcement gate flags the non-walking-skeleton fork in the migrated directory"
)
def then_flags_migrated(composition: CorpusMigrationComposition) -> None:
    assert composition.scoped().flags_in_migrated_dir, (
        "the scoped enforcement gate must FLAG a non-WS fork inside a MIGRATED "
        f"directory. {composition.diag()}"
    )


@then("the enforcement gate honours the migration scope")
def then_scope_honoured(composition: CorpusMigrationComposition) -> None:
    assert composition.scoped().scope_honoured, (
        "the enforcement gate must expose a migration-scope surface so its blocking "
        "scope follows the migrated directories (DDD-4 ordering caveat) --- but at "
        f"HEAD check_non_ws_spawn has no migration_scope parameter. {composition.diag()}"
    )


@then(
    "the enforcement gate does not flag the non-walking-skeleton fork in the "
    "un-migrated directory"
)
def then_no_hard_fail_unmigrated(composition: CorpusMigrationComposition) -> None:
    assert not composition.scoped().hard_fails_unmigrated_dir, (
        "the enforcement gate must NOT hard-fail a non-WS fork in an UN-migrated "
        "directory (tightening to per-site must follow migration, never precede it) "
        "--- but at HEAD the file-level gate over-flags the un-migrated subtree. "
        f"{composition.diag()}"
    )
