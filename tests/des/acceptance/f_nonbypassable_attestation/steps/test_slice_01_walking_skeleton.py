"""pytest-bdd binding for f-nonbypassable-attestation slice-01 (walking skeleton).

Driving surface (Mandate-13, Layer-3 composition): the REAL done-gate entry point
``verify_deliver_integrity.main``. Step bodies delegate to the composition root
(composition_nonbypassable.py); no business logic in step bodies (Mandate-12).

S1: the done-gate driving verbs ("declares the feature done", "clears the
feature", "refuses with a definite failure") live ONCE in conftest.py (the
pytest-bdd shared-step SSOT) -- one function object, one registration, no shadow.
Only the slice-01-UNIQUE steps live below. The `attestation` fixture is in conftest.

Active-RED scaffold (atdd_pure -- NOT @skip): the "full-suite leg unrun" scenario
is RED until DELIVER adds FullSuiteLegRan to the `required` set in both SSOTs +
emits it from run_feature_end_cycle. Failures are semantic AssertionErrors.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, scenarios, then, when

from .composition_nonbypassable import AttestationComposition


# S1: the shared done-gate verbs ("declares the feature done" / "clears the
# feature" / "refuses with a definite failure") live ONCE in conftest.py (the
# pytest-bdd shared-step SSOT). Only the slice-01-UNIQUE steps live below.


scenarios("../slice-01-walking-skeleton.feature")


# --- Given (slice-01 unique) -----------------------------------------------


@given("a project where the feature-end cycle never ran")
def given_no_cycle(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_no_feature_end_records()


@given("a project whose feature-end ledger carries every required record")
def given_complete(attestation: AttestationComposition, tmp_path: Path) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_complete_feature_end_records()


@given("a project whose ledger carries every required record except the full-suite leg")
def given_complete_except_full_suite(
    attestation: AttestationComposition, tmp_path: Path
) -> None:
    attestation.use_project_root(tmp_path)
    attestation.given_feature_end_records_except_full_suite()


# --- Then (slice-01 unique cause-discriminators) ---------------------------


@then("the refusal names the missing feature-end cycle")
def then_names_missing_cycle(attestation: AttestationComposition) -> None:
    attestation.then_cause_names("FeatureEndReviewVerdict")


@then("the refusal names the missing full-suite leg")
def then_names_missing_full_suite(attestation: AttestationComposition) -> None:
    attestation.then_cause_names("FullSuiteLegRan")


# --- CT-2: terminal auto-fire backstop -------------------------------------


@when("the developer declares the feature done on the terminal action")
def when_declare_done_terminal(attestation: AttestationComposition) -> None:
    attestation.when_done_declared_via_terminal_backstop()


@then("the terminal action auto-fired the done-gate")
def then_terminal_auto_fired(attestation: AttestationComposition) -> None:
    attestation.then_terminal_backstop_auto_fired()
