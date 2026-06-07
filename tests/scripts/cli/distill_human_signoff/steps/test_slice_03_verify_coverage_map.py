"""Step definitions -- slice-03: verify_coverage_map gate CLI.

F-DISTILL-HUMAN-SIGNOFF slice-03. Layer 3 (subprocess / FS acceptance): the
``verify_coverage_map verify`` CLI is the driving port; the only driven
ports are the real filesystem (tmp_path) and the §5.3 golden-fixture data
under ``nWave/data/coverage-map-digest-fixtures/``. Example-based sad paths
(Mandate 11) -- the AT3 Scenario Outline enumerates the §5.3 G3 widened
section set's tamper rows + the malformed-input + the §5.3 G4 cross-tree
canonicalization conformance probe.

Step bodies delegate to ``HumanSignoffComposition`` -- a typed lookup plus
a composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the manifest + recorded signoff-digest sidecar are unchanged by
verification (verify is a pure-function read over the live coverage-map)
via ``assert_state_delta`` over a port-exposed universe (Mandate 8).

This slice is RED-for-the-right-reason against the slice-03 production
``verify_coverage_map`` scaffold -- the CLI raises ``AssertionError`` on
every invocation (Mandate 7). The DELIVER loop adds the real
canonicalization + signoff-block parsing + verdict logic; the present
scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import HumanSignoffComposition
from .domain_types import (
    EXIT_CODE_BY_VERDICT,
    TAMPER_OR_INPUT_BY_PHRASE,
    VERIFY_VERDICT_BY_PHRASE,
    AntiOmissionVerdict,
    CoverageMapVerdict,
    FeatureId,
    SignedSection,
    VerifyTamperOrInput,
)


scenarios("../slice-03-verify-coverage-map.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> HumanSignoffComposition:
    """Production-wired composition root over a tmp_path feature project."""
    return HumanSignoffComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + scenario-derived state across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has produced a component manifest")
def given_design_wave_produced_manifest(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))
    result_box["domain_ids"] = (
        composition.write_manifest_with_one_domain_per_dimension()
    )


@given("a coverage map has been authored and signed by a human")
def given_coverage_map_signed(composition: HumanSignoffComposition) -> None:
    composition.sign_coverage_map()


# --- Given ------------------------------------------------------------------


@given("the acceptance designer has removed a mandatory section from the coverage map")
def given_designer_removed_section(composition: HumanSignoffComposition) -> None:
    composition.remove_mandatory_section(SignedSection.KNOWN_RESIDUES)


def _stage_tamper_or_input(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    phrase: str,
) -> None:
    """Shared body for the six AT3 outline Given-step bindings.

    Mandate-12 criterion 3: step bodies are ≤2 statements ending in a
    composition call. This helper is shared across six distinct ``@given``
    decorators (one per outline equivalence class) so the .feature line is
    matched literally by pytest-bdd (no greedy ``parsers.parse`` placeholder
    that would silently swallow the Background line too).
    """
    choice: VerifyTamperOrInput = TAMPER_OR_INPUT_BY_PHRASE[phrase]
    result_box["tamper_or_input"] = choice
    result_box["golden_raw_path"] = composition.stage_tamper_or_input(choice)


@given(
    "the acceptance designer has edited the feature surface declared section after signoff"
)
def given_tamper_feature_surface(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the acceptance designer has edited the feature surface declared section after signoff",
    )


@given("the acceptance designer has edited the not covered table after signoff")
def given_tamper_not_covered(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the acceptance designer has edited the not covered table after signoff",
    )


@given(
    "the acceptance designer has edited the known residues carried forward section after signoff"
)
def given_tamper_known_residues(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the acceptance designer has edited the known residues carried forward section after signoff",
    )


@given(
    "the acceptance designer has edited the negative space completeness statement after signoff"
)
def given_tamper_negative_space(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the acceptance designer has edited the negative space completeness statement after signoff",
    )


@given("the manifest or coverage map cannot be parsed")
def given_malformed_input(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the manifest or coverage map cannot be parsed",
    )


@given(
    "the canonical content of a golden fixture is digested by the local implementation"
)
def given_golden_fixture(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    _stage_tamper_or_input(
        composition,
        result_box,
        "the canonical content of a golden fixture is digested by the local implementation",
    )


# --- When -------------------------------------------------------------------


@when("the reviewer verifies the coverage map")
def when_verify(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    choice = result_box.get("tamper_or_input")
    before = composition.capture_slice03_universe()
    if choice is VerifyTamperOrInput.GOLDEN_FIXTURE_CONFORMANCE:
        raw_path = result_box["golden_raw_path"]
        result_box["result"] = composition.run_verify_digest_golden_fixture(raw_path)
    else:
        result_box["result"] = composition.run_verify_coverage_map()
    after = composition.capture_slice03_universe()
    # Verify is a pure-function read: NO file in the universe transitions.
    # The CLI may emit verdict bytes to stdout/stderr but MUST NOT mutate
    # the manifest, the signed coverage-map body, the signoff-digest
    # sidecar, the feature-delta, or the attestation/signoff sidecars.
    # State-delta universe is port-exposed file-presence names only (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "manifest.present",
            "coverage_map.present",
            "feature_delta.present",
            "attestation.present",
            "signoff.present",
            "signoff_digest.present",
        },
        expected={
            "manifest.present": unchanged(),
            "coverage_map.present": unchanged(),
            "feature_delta.present": unchanged(),
            "attestation.present": unchanged(),
            "signoff.present": unchanged(),
            "signoff_digest.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then("the verify gate accepts the coverage map")
def then_gate_accepts(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
        f"expected exit 0 (accepted); got {result.exit_code}: {result.stderr}"
    )


@then("the verify gate refuses for a structurally incomplete coverage map")
def then_gate_refuses_structural(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    token = AntiOmissionVerdict.STRUCTURAL_INCOMPLETE.value
    assert result.exit_code == 1, (
        f"expected exit 1 ({token}); got {result.exit_code}: {result.stderr}"
    )
    assert composition.stderr_contains_refusal_token(token, result), (
        f"refusal token {token!r} missing from stderr\n--\n{result.stderr}"
    )


@then(parsers.parse("the verify gate responds with {verdict_phrase}"))
def then_gate_responds_with(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    verdict_phrase: str,
) -> None:
    # parsers.parse is bound to the literal "the verify gate responds with"
    # prefix here -- it does NOT swallow Background/Given lines because the
    # fixed prefix scopes the match (unlike the bare {placeholder} pattern
    # that caused the slice-03 v1 KeyError trap).
    verdict = VERIFY_VERDICT_BY_PHRASE[verdict_phrase]
    result = result_box["result"]
    choice = result_box.get("tamper_or_input")

    if choice is VerifyTamperOrInput.GOLDEN_FIXTURE_CONFORMANCE:
        # AT3 row f -- §5.3 G4 cross-tree canonicalization conformance.
        # The verify CLI's digest-golden-fixture subcommand reads the
        # raw input, runs the §5.3 canonicalization locally, and prints
        # the lowercase hex digest. The test compares it byte-for-byte
        # against the committed expected-digest sibling file -- a drift
        # in either tree's local canonicalization fails the test on the
        # drifting commit (Earned-Trust applied to the L1 digest seam).
        assert result.exit_code == EXIT_CODE_BY_VERDICT[CoverageMapVerdict.RENDERED], (
            f"expected exit 0 (golden fixture digest produced); "
            f"got {result.exit_code}: {result.stderr}"
        )
        raw_path = result_box["golden_raw_path"]
        expected_digest = composition.read_expected_digest_for_fixture(raw_path)
        produced_digest = result.stdout.strip()
        assert produced_digest == expected_digest, (
            f"local canonicalization produced digest {produced_digest!r}; "
            f"committed golden expected {expected_digest!r}\n"
            f"-- a drift in §5.3 canonicalization breaks the cross-tree "
            f"reviewed-content-digest contract (G4)"
        )
        return

    if isinstance(verdict, CoverageMapVerdict):
        # The malformed-input row uses CoverageMapVerdict.MALFORMED.
        assert result.exit_code == EXIT_CODE_BY_VERDICT[verdict], (
            f"expected exit {EXIT_CODE_BY_VERDICT[verdict]} ({verdict.value}); "
            f"got {result.exit_code}: {result.stderr}"
        )
        return

    # Refusal rows (tamper -> SignoffStale, exit 1 + token on stderr).
    assert result.exit_code == 1, (
        f"expected exit 1 ({verdict.value}); got {result.exit_code}: {result.stderr}"
    )
    assert composition.stderr_contains_refusal_token(verdict.value, result), (
        f"refusal token {verdict.value!r} missing from stderr\n--\n{result.stderr}"
    )
