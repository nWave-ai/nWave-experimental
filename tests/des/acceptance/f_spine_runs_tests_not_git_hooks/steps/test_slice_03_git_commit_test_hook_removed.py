"""pytest-bdd binding for f-spine-runs-tests-not-git-hooks slice-03.

The git pre-COMMIT test hook removal + the flagged-interim pre-push net. The SUT
is the shipped ``.pre-commit-config.yaml`` read as DATA (Mandate-13,
@contract-shape:pure-function): a config-shape assertion has no subprocess /
composition entry -- the "port" IS the real config at the repo root, read as the
shipped artifact (never an inline test string -- the protocol-driver prose-surface
case: assert a shipped artifact, not a self-fulfilling fixture). Step bodies
delegate to the shared composition root (composition.py:PreCommitConfigComposition);
no business logic in step bodies (Mandate-12). HERMETIC: reads the REPO_ROOT
config; no developer-home read.

Driving surface (Mandate-13): the shipped ``.pre-commit-config.yaml``. observable
= which hook ids fire at which git stage + the literal interim-marker phrase.

S1 (step-text uniqueness): this module's verbs ("the shipped pre-commit config",
the commit/push-stage inspections, the hook-presence/absence Thens) are UNIQUE to
slice-03 -- they do not recur in slice-01/02's modules (whose vocabulary is the
slice-AT executor). The parametrized Thens (`parsers.parse('the ... "{hook_id}"
... hook ...')`) are template steps -- the S1 tolerable-variant (pytest-bdd binds
via template+arg-extraction, not literal-string match).

Active-RED scaffold (atdd_pure -- NOT @skip): RED until slice-03's DELIVER removes
the `pytest-validation` pre-commit hook entry + adds the interim marker on the
pre-push full-suite. At HEAD `.pre-commit-config.yaml` STILL carries
`pytest-validation` at pre-commit AND carries NO interim marker -> semantic
AssertionErrors against the expected post-removal / marked state.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from .composition import PreCommitConfigComposition, precommit  # noqa: F401


scenarios("../slice-03-git-commit-test-hook-removed.feature")


# --- Given (slice-03) ------------------------------------------------------


@given("the shipped pre-commit config")
def given_shipped_config(precommit: PreCommitConfigComposition) -> None:
    precommit.load_shipped_config()


# --- When (slice-03) -------------------------------------------------------


@when("the commit-stage hooks are inspected")
def when_inspect_commit_stage(precommit: PreCommitConfigComposition) -> None:
    precommit.inspect_commit_stage()


@when("the push-stage hooks are inspected")
def when_inspect_push_stage(precommit: PreCommitConfigComposition) -> None:
    precommit.inspect_push_stage()


# --- Then (slice-03) -------------------------------------------------------


@then(parsers.parse('the pre-commit "{hook_id}" test hook is absent'))
def then_commit_hook_absent(
    precommit: PreCommitConfigComposition, hook_id: str
) -> None:
    precommit.then_commit_stage_hook_absent(hook_id)


@then(parsers.parse('the fast pre-commit "{hook_id}" hook is present'))
def then_fast_commit_hook_present(
    precommit: PreCommitConfigComposition, hook_id: str
) -> None:
    precommit.then_commit_stage_hook_present(hook_id)


@then(parsers.parse('the pre-push "{hook_id}" full-suite hook is present'))
def then_push_hook_present(precommit: PreCommitConfigComposition, hook_id: str) -> None:
    precommit.then_push_stage_hook_present(hook_id)


@then("the pre-push full-suite carries the explicit interim removal marker")
def then_interim_marker_present(precommit: PreCommitConfigComposition) -> None:
    precommit.then_interim_marker_present()
