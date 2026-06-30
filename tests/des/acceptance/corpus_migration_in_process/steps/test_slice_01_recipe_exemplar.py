"""Step definitions: the in-process conversion recipe exemplar + @requires_external.

f-test-corpus-migration-in-process slice-01 (DESIGN DDD-2 edge-drive in-process
recipe; never the leaf; preserve ZOMBIES + DDD-6 / ADR-TEST-004 the one
@walking_skeleton subprocess survives; @requires_external degrades-LOUD-skip).

Layer 3 (in-process composition acceptance). Example-only (Mandate 9/11). Sad paths
(ZOMBIES preservation, build-incapable degrade-LOUD-skip) enumerated explicitly
(Mandate 11). The recipe-conformance surface and the @requires_external resolver
are driven through the REAL production module IN-PROCESS (reached by getattr at
runtime); step bodies delegate to CorpusMigrationComposition (Mandate-12).

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD the recipe-conformance
surface (recipe_conformant / drives_edge / zombies_preserved) and the
requires_external_skip_decision resolver are ABSENT, so every observable RED-fails
for the right reason. Collection imports only present names (DESIGN P1).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest_bdd import given, scenarios, then, when


if TYPE_CHECKING:
    from .composition import CorpusMigrationComposition


scenarios("../slice-01-recipe-exemplar.feature")


# --- Given -------------------------------------------------------------------


@given("the maintainer has a synthetic acceptance corpus the classifier can scan")
def given_corpus(composition: CorpusMigrationComposition, tmp_path: Path) -> None:
    composition.given_corpus(tmp_path)


@given("the corpus has one exemplar migrated to drive the edge in-process")
def given_migrated_exemplar(composition: CorpusMigrationComposition) -> None:
    composition.arm_migrated_exemplar()


@given("the maintainer can drive the requires-external skip resolver in-process")
def given_skip_resolver(composition: CorpusMigrationComposition) -> None:
    pass


# --- When --------------------------------------------------------------------


@when("the maintainer classifies each spawn-site in-process")
def when_classify(composition: CorpusMigrationComposition) -> None:
    composition.classify_spawn_sites()


@when(
    "the maintainer resolves the requires-external skip decision for a build-incapable sandbox"
)
def when_resolve_skip(composition: CorpusMigrationComposition) -> None:
    composition.drive_requires_external_skip(build_capable=False)


# --- Then: recipe conformance -------------------------------------------------


@then("the migrated exemplar reports zero non-walking-skeleton spawn-sites")
def then_zero_spawn_sites(composition: CorpusMigrationComposition) -> None:
    c = composition.classification()
    assert c.resolution_available and len(c.migrate_sites) == 0, (
        "the migrated exemplar must report ZERO non-WS spawn-sites under the per-site "
        "classifier (the recipe's output satisfies the DONE contract) --- but at HEAD "
        "no per-site resolution surface exists, so zero-with-resolution is "
        f"unobservable. {composition.diag()}"
    )


@then("the classifier surfaced a per-site resolution for the migrated exemplar")
def then_resolution_available(composition: CorpusMigrationComposition) -> None:
    assert composition.classification().resolution_available, (
        "the per-site classifier must surface a per-site resolution at all --- but at "
        f"HEAD only the file-level short-circuit exists. {composition.diag()}"
    )


@then("the classifier confirms the migrated exemplar drives the production edge")
def then_drives_edge(composition: CorpusMigrationComposition) -> None:
    assert composition.classification().drives_edge, (
        "the recipe-conformance surface must confirm the migrated exemplar drives the "
        "production EDGE, not an isolated leaf (C13/C14) --- but at HEAD no "
        f"recipe-conformance surface exists. {composition.diag()}"
    )


@then("the exemplar drives a wired production edge symbol rather than an isolated leaf")
def then_edge_is_wired(composition: CorpusMigrationComposition) -> None:
    # The wiring lever (check_unwired_entry, Phase-1) is the mechanical witness that
    # the driven symbol is a real EDGE (has callers/readers), not an isolated leaf.
    assert composition.edge_is_wired() and composition.classification().drives_edge, (
        "the migrated exemplar must drive a WIRED production edge (the wiring lever "
        "confirms callers/readers) AND the per-site report must bind that edge-drive "
        "into its recipe-conformance verdict --- but at HEAD the recipe-conformance "
        f"surface is absent. {composition.diag()}"
    )


@then("the classifier confirms the migrated exemplar preserves its error-path scenario")
def then_zombies_preserved(composition: CorpusMigrationComposition) -> None:
    assert composition.classification().zombies_preserved, (
        "the recipe-conformance surface must confirm the migrated exemplar preserves "
        "its sad-path (ZOMBIES) scenario 1:1 (DDD-2 step 6) --- but at HEAD no "
        f"recipe-conformance surface exists. {composition.diag()}"
    )


# --- Then: @requires_external degrade-LOUD-skip (resolves OPEN QUESTION 2) -----


@then("the build scenario is skipped rather than failed")
def then_skipped(composition: CorpusMigrationComposition) -> None:
    d = composition.skip_decision()
    assert d.resolver_available and d.skipped, (
        "a @walking_skeleton @requires_external build scenario must be SKIPPED (not "
        "failed) in a build-incapable sandbox --- but at HEAD no degrade-LOUD-skip "
        f"resolver exists. {composition.diag()}"
    )


@then("the skip carries a loud structured reason naming the missing capability")
def then_loud_reason(composition: CorpusMigrationComposition) -> None:
    assert composition.skip_decision().loud_reason, (
        "the @requires_external skip must carry a LOUD structured reason naming the "
        "missing build capability (never a silent skip) --- but at HEAD no resolver "
        f"surfaces a reason. {composition.diag()}"
    )


@then("the build scenario is not silently passed")
def then_not_silent_pass(composition: CorpusMigrationComposition) -> None:
    d = composition.skip_decision()
    assert d.resolver_available and not d.silent_pass, (
        "the @requires_external scenario must NEVER be silently passed (minted GREEN) "
        f"--- the resolver must exist and refuse a silent pass. {composition.diag()}"
    )


@then("the build scenario is not hard-blocked")
def then_not_hard_blocked(composition: CorpusMigrationComposition) -> None:
    d = composition.skip_decision()
    assert d.resolver_available and not d.hard_blocked, (
        "the @requires_external scenario must NOT hard-block a build-incapable sandbox "
        f"(it is a skip, not a failure) --- the resolver must exist. {composition.diag()}"
    )
