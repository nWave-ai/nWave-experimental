"""Step bindings for D4 Phase 2 slice-01 atdd_pure flavor."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when


@given("the workflow flavor YAML loader is available")
def given_loader(flavor_comp) -> None:
    assert flavor_comp is not None


@given(parsers.parse('the flavor file at "{path}"'))
def given_flavor(flavor_comp, path: str) -> None:
    flavor_comp.load_flavor()


@given(parsers.parse('the flavor schema at "{path}"'))
def given_schema(flavor_comp, path: str) -> None:
    flavor_comp.load_schema()


@given(parsers.parse('the gate catalog at "{path}"'))
def given_catalog(flavor_comp, path: str) -> None:
    flavor_comp.load_catalog()


@when("the flavor is validated against the schema")
def when_validate(flavor_comp) -> None:
    flavor_comp.validate()


@when("the gate references are extracted from lifecycle_events")
def when_extract(flavor_comp) -> None:
    pass  # @then reads via composition.referenced_gate_ids


@when("the dispatch.pre composition is read")
def when_read_dispatch(flavor_comp) -> None:
    pass  # @then reads via composition.dispatch_pre_composition()


@then("validation succeeds with zero errors")
def then_valid(flavor_comp) -> None:
    assert flavor_comp.validation_errors == [], (
        f"Validation errors: {flavor_comp.validation_errors}"
    )


@then("every referenced gate_id matches a catalog entry")
def then_refs_match(flavor_comp) -> None:
    missing = flavor_comp.referenced_gate_ids - flavor_comp.catalog_gate_ids
    assert not missing, f"Flavor references gates not in catalog: {missing}"


@then(parsers.parse('the composition contains the gate "{gate_id}"'))
def then_contains_gate(flavor_comp, gate_id: str) -> None:
    ids = [g["gate_id"] for g in flavor_comp.dispatch_pre_composition()]
    assert gate_id in ids, f"dispatch.pre composition: {ids}"


@then(parsers.parse('the gate carries on_failure equal to "{expected}"'))
def then_on_failure(flavor_comp, expected: str) -> None:
    carpaccio = next(
        g
        for g in flavor_comp.dispatch_pre_composition()
        if g["gate_id"] == "carpaccio-slice-gate"
    )
    assert carpaccio["on_failure"] == expected, (
        f"carpaccio-slice-gate on_failure = {carpaccio['on_failure']!r}"
    )


@then("the gate args reference feature_id and entering_slice placeholders")
def then_args_placeholders(flavor_comp) -> None:
    carpaccio = next(
        g
        for g in flavor_comp.dispatch_pre_composition()
        if g["gate_id"] == "carpaccio-slice-gate"
    )
    args = carpaccio["args"]
    assert args["feature_id"] == "{feature_id}", f"args={args}"
    assert args["entering_slice"] == "{slice_id}", f"args={args}"
