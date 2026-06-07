"""Shared step definitions for the fix-carpaccio-distill-authoring-ergonomics AT set.

S1 (step-text uniqueness): every step decorator literal is declared exactly ONCE,
here, and re-used across the three slice test modules via ``from .steps_shared
import *``. No slice module re-declares a step body -- there is one function
object per (step_type, literal), so pytest-bdd's global registry never shadows.

Mandate-12 criterion 3: each step body is a single typed lookup plus a single
composition call (Given), a single composition call (When), or a single
assertion over a port-exposed observable (Then). No business logic inline.

Mandate-8: the When steps assert the gate/pre-check read-only contract via
assert_state_delta over a port-exposed filesystem universe (all entries
unchanged -- neither CLI mutates a repository file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, then, when
from tests.common.state_delta import assert_state_delta, unchanged

from .domain_types import GateVerdict, HumanVerdictClass


if TYPE_CHECKING:
    from .composition import CarpaccioErgonomicsComposition, CliResult


_FILESYSTEM_UNIVERSE = {
    "feature_delta.bytes",
    "ledger.bytes",
    "config.bytes",
    "feature_files.bytes",
}


# --- Given -------------------------------------------------------------------


@given("a repository for an atdd_pure feature")
def given_a_repository(composition: CarpaccioErgonomicsComposition) -> None:
    composition.create_repo()


@given(parsers.parse("the feature carries {feature_phrase}"))
def given_the_feature_carries(
    composition: CarpaccioErgonomicsComposition, feature_phrase: str
) -> None:
    composition.provision_by_phrase(feature_phrase)


@given("the entering slice has a recorded approved AT-review verdict")
def given_an_approved_at_review_verdict(
    composition: CarpaccioErgonomicsComposition,
) -> None:
    composition.provision_approved_at_review_record()


@given("the shared format checks are available as one reusable place")
def given_shared_format_checks_available(
    composition: CarpaccioErgonomicsComposition, result_box: dict[str, object]
) -> None:
    result_box["shared_format_available"] = composition.shared_format_checks_available()


@given(parsers.parse("the feature's scenario files carry {feature_phrase}"))
def given_the_features_scenario_files_carry(
    composition: CarpaccioErgonomicsComposition, feature_phrase: str
) -> None:
    composition.provision_by_phrase(feature_phrase)


@given(
    "the feature also carries an over-ceiling slice with the coupled escape satisfied"
)
def given_the_feature_also_carries_a_coupled_over_ceiling_slice() -> None:
    # Provisioned together with the un-coupled slice by the OVER_CEILING_PAIR
    # builder in the preceding Given -- this step documents the second half of
    # the pair in the narrative without re-provisioning (no-op composition call).
    pass


# --- When --------------------------------------------------------------------


@when("the operator runs the carpaccio slice gate for the entering slice")
def when_the_operator_runs_the_gate(
    composition: CarpaccioErgonomicsComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_gate()
    assert_state_delta(
        before,
        composition.capture_universe(),
        universe=_FILESYSTEM_UNIVERSE,
        expected={slot: unchanged() for slot in _FILESYSTEM_UNIVERSE},
    )


@when("the operator runs the carpaccio pre-check for the feature")
def when_the_operator_runs_the_precheck(
    composition: CarpaccioErgonomicsComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_precheck()
    assert_state_delta(
        before,
        composition.capture_universe(),
        universe=_FILESYSTEM_UNIVERSE,
        expected={slot: unchanged() for slot in _FILESYSTEM_UNIVERSE},
    )


# --- Then --------------------------------------------------------------------


@then("the slice is cleared to enter implementation")
def then_the_slice_is_cleared(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.gate_verdict == GateVerdict.CLEARED, (
        f"expected exit 0 (cleared), got exit {result.exit_code}: {result.combined_text}"
    )


@then("the operator sees a success line naming the coupled-AT-group escape")
def then_success_line_names_coupled_escape(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.human_verdict_class == HumanVerdictClass.PASS_CLASS and (
        "coupl" in result.human_summary_text.lower()
    ), (
        "expected a PASS-class human line naming the coupled escape, got: "
        f"{result.human_summary_text!r}"
    )


@then("the operator does not see a refusal on the cleared slice")
def then_operator_does_not_see_a_refusal(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.human_verdict_class != HumanVerdictClass.FAIL_CLASS, (
        f"expected no refusal on a cleared slice, got: {result.human_summary_text!r}"
    )


@then("the gate records that the coupled slice was accepted")
def then_gate_records_coupled_accepted(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.has_event("CoupledSliceAccepted"), (
        f"expected a CoupledSliceAccepted event, got: {result.combined_text}"
    )


@then("the slice is refused as exceeding the carpaccio ceiling")
def then_slice_refused_as_oversized(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.gate_verdict == GateVerdict.SLICE_TOO_LARGE and result.has_event(
        "CARPACCIO_SLICE_TOO_LARGE"
    ), (
        f"expected exit 44 CARPACCIO_SLICE_TOO_LARGE, got exit {result.exit_code}: "
        f"{result.combined_text}"
    )


@then("the gate writes no file in the repository")
def then_the_gate_writes_no_file() -> None:
    # The read-only contract is asserted by the When-step assert_state_delta
    # (every filesystem-universe slot unchanged). This Then documents the
    # observable outcome in the narrative; the mechanical guard is the delta.
    pass


# --- Then (slice-03 pre-check diagnostics) -----------------------------------


@then("the pre-check reports that no scenario file is bound to the feature")
def then_precheck_reports_missing_binding(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "no scenario file" in result.combined_text.lower() or (
        "no-scenarios" in result.combined_text.lower()
        or (
            "missing" in result.combined_text.lower()
            and "bind" in result.combined_text.lower()
        )
    ), f"expected a missing-binding diagnostic, got: {result.combined_text!r}"


@then("the pre-check names the expected feature-binding tag")
def then_precheck_names_expected_tag(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "@feature-demo-feature" in result.combined_text, (
        "expected the pre-check to name the expected @feature-{id} tag, got: "
        f"{result.combined_text!r}"
    )


@then("the pre-check warns about the hyphen-versus-underscore legacy directory")
def then_precheck_warns_hyphen_underscore(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "demo_feature" in result.combined_text or (
        "underscore" in result.combined_text.lower()
        or "hyphen" in result.combined_text.lower()
    ), f"expected a hyphen/underscore legacy-dir note, got: {result.combined_text!r}"


@then("the pre-check reports the slice over the ceiling as lacking the coupled escape")
def then_precheck_reports_lacking_escape(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "slice-01" in result.combined_text and (
        "coupled" in result.combined_text.lower()
        or "ceiling" in result.combined_text.lower()
    ), (
        "expected slice-01 flagged as over-ceiling lacking the coupled escape, got: "
        f"{result.combined_text!r}"
    )


@then(
    "the pre-check reports the other over-ceiling slice as having the coupled escape satisfied"
)
def then_precheck_reports_escape_satisfied(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "slice-02" in result.combined_text and (
        "coupled" in result.combined_text.lower()
    ), (
        "expected slice-02 reported as having the coupled escape satisfied, got: "
        f"{result.combined_text!r}"
    )


@then("the pre-check reports the missing feature-binding tag")
def then_precheck_reports_missing_binding_tag(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "@feature-demo-feature" in result.combined_text or (
        "binding" in result.combined_text.lower()
    ), f"expected the missing feature-binding diagnostic, got: {result.combined_text!r}"


@then("the pre-check reports the slice-tag mismatch")
def then_precheck_reports_tag_mismatch(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "slice-99" in result.combined_text and (
        "mismatch" in result.combined_text.lower()
        or "no matching" in result.combined_text.lower()
        or "plan row" in result.combined_text.lower()
    ), f"expected the @slice-99 tag-mismatch diagnostic, got: {result.combined_text!r}"


@then("the pre-check reports the over-ceiling slice")
def then_precheck_reports_over_ceiling(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert "ceiling" in result.combined_text.lower() and (
        "slice-01" in result.combined_text
    ), (
        "expected the over-ceiling diagnostic for slice-01, got: "
        f"{result.combined_text!r}"
    )


@then("the pre-check reports an advisory verdict that violations were found")
def then_precheck_reports_advisory_verdict(result_box: dict[str, object]) -> None:
    result: CliResult = result_box["result"]  # type: ignore[assignment]
    assert result.exit_code != 0 and (
        result.human_verdict_class
        in (HumanVerdictClass.DEGRADED_CLASS, HumanVerdictClass.FAIL_CLASS)
    ), (
        "expected a non-zero advisory verdict, got exit "
        f"{result.exit_code}: {result.human_summary_text!r}"
    )


@then("the pre-check reports violations without recording any verdict")
def then_precheck_records_no_verdict(
    composition: CarpaccioErgonomicsComposition, result_box: dict[str, object]
) -> None:
    # The pre-check is read-only (Principle 12): it must NOT append a verdict to
    # the AT-completion ledger. The When-step state-delta already proves no file
    # is written; this Then additionally asserts no ATReviewVerdict was emitted
    # to the ledger path by the pre-check run.
    assert not composition.ledger_path.exists() or (
        "ATReviewVerdict" not in composition.ledger_path.read_text(encoding="utf-8")
    ), "the pre-check must not record an AT-review verdict"
