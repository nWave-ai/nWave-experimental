"""Step definitions for step 03-02 — seeded production registry.

Per Mandate 5: invokes the real `nwave-ai outcomes check` console
subcommand via subprocess. Reads the in-repo production registry at
docs/product/outcomes/registry.yaml (not a sandbox copy) — the whole
point of this scenario is that the seed is real and the CLI resolves
verdicts against it.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../test_seed_registry.feature")


_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PRODUCTION_REGISTRY = _PROJECT_ROOT / "docs" / "product" / "outcomes" / "registry.yaml"
_EXPECTED_OUTCOME_IDS = (
    "OUT-E1",
    "OUT-E2",
    "OUT-E3",
    "OUT-E4",
    "OUT-E5",
    "OUT-FORMAT",
)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("the production registry at docs/product/outcomes/registry.yaml")
def _production_registry_exists() -> None:
    assert _PRODUCTION_REGISTRY.exists(), (
        f"production registry missing at {_PRODUCTION_REGISTRY}"
    )


@given("the registry contains all 6 seeded outcomes")
def _registry_contains_six_outcomes() -> None:
    import yaml

    data = yaml.safe_load(_PRODUCTION_REGISTRY.read_text(encoding="utf-8"))
    actual_ids = tuple(o["id"] for o in data.get("outcomes", []))
    for expected in _EXPECTED_OUTCOME_IDS:
        assert expected in actual_ids, (
            f"expected {expected} in registry; got {actual_ids}"
        )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        "the author runs check against the production registry with input "
        'shape "{input_shape}" and output shape "{output_shape}" and '
        'keywords "{keywords}"'
    )
)
def _run_check_against_production(
    run_cli,
    state: dict,
    input_shape: str,
    output_shape: str,
    keywords: str,
) -> None:
    state["check_result"] = run_cli(
        "outcomes",
        "--registry",
        str(_PRODUCTION_REGISTRY),
        "check",
        "--input-shape",
        input_shape,
        "--output-shape",
        output_shape,
        "--keywords",
        keywords,
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("the CLI check exit code is {code:d}"))
def _check_exit_code(state: dict, code: int) -> None:
    result = state["check_result"]
    assert result.exit_code == code, (
        f"expected exit {code}, got {result.exit_code}\n"
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


@then(parsers.parse('stdout contains "{needle}"'))
def _stdout_contains(state: dict, needle: str) -> None:
    result = state["check_result"]
    assert needle in result.stdout, (
        f"expected {needle!r} in stdout; got stdout={result.stdout!r}"
    )
