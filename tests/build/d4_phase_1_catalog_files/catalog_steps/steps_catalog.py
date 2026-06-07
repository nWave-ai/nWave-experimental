"""Step bindings for D4 Phase 1 slice-01 catalog files.

Per Mandate-12: step bodies ≤2 statements, no control flow, all delegating
to composition root. Per Mandate-13: drives via composition methods that
wrap yaml.safe_load + jsonschema.validate + _REGISTRY tuple — never
internal field introspection of domain/application modules.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when


@given("the gate catalog YAML loader is available")
def given_loader(composition) -> None:
    assert composition is not None


@given(parsers.parse('the catalog file at "{path}"'))
def given_catalog(composition, path: str) -> None:
    composition.load_catalog()


@given(parsers.parse('the schema file at "{path}"'))
def given_schema(composition, path: str) -> None:
    composition.load_schema()


@given(parsers.parse('the gate catalog loaded from "{path}"'))
def given_catalog_loaded(composition, path: str) -> None:
    composition.load_catalog()


@given("the production _REGISTRY loaded from `src.des.cli.__main__`")
def given_registry(composition) -> None:
    composition.load_registry()


@given(parsers.parse('the catalog entry for gate_id "{gate_id}"'))
def given_catalog_entry(composition, gate_id: str) -> None:
    composition.load_catalog()
    # entry retrieved via composition.find_gate in @then


@when("the catalog is validated against the schema")
def when_validate(composition) -> None:
    composition.validate()


@when("the row counts are compared")
def when_compare_counts(composition) -> None:
    # No-op; @then steps read both side counts via composition
    pass


@when("the entry's module and entry_function are read")
def when_read_entry(composition) -> None:
    pass  # @then steps read via composition.find_gate


@then("validation succeeds with zero errors")
def then_no_errors(composition) -> None:
    assert composition.validation_errors == [], (
        f"Validation errors: {composition.validation_errors}"
    )


@then("both contain exactly 22 entries")
def then_both_21(composition) -> None:
    assert len(composition.catalog_gate_ids) == 22, (
        f"Catalog has {len(composition.catalog_gate_ids)} entries, expected 22"
    )
    assert len(composition.registry_names) == 22, (
        f"_REGISTRY has {len(composition.registry_names)} entries, expected 22"
    )


@then("every gate_id in the catalog is also a SubcommandRow.name in _REGISTRY")
def then_catalog_subset(composition) -> None:
    extra = set(composition.catalog_gate_ids) - set(composition.registry_names)
    assert not extra, f"Catalog has gates not in _REGISTRY: {extra}"


@then("every SubcommandRow.name in _REGISTRY is also a gate_id in the catalog")
def then_registry_subset(composition) -> None:
    missing = set(composition.registry_names) - set(composition.catalog_gate_ids)
    assert not missing, f"_REGISTRY has names not in catalog: {missing}"


@then(parsers.parse('the module equals "{expected}"'))
def then_module_equals(composition, expected: str) -> None:
    entry = composition.find_gate("carpaccio-slice-gate")
    assert entry["module"] == expected, (
        f"module = {entry['module']!r}, expected {expected!r}"
    )


@then(parsers.parse('the entry_function equals "{expected}"'))
def then_entry_function_equals(composition, expected: str) -> None:
    entry = composition.find_gate("carpaccio-slice-gate")
    assert entry["entry_function"] == expected, (
        f"entry_function = {entry['entry_function']!r}, expected {expected!r}"
    )


@then(parsers.parse("the language_neutral_contract equals {expected_str}"))
def then_lnc_equals(composition, expected_str: str) -> None:
    entry = composition.find_gate("carpaccio-slice-gate")
    expected = expected_str.lower() == "true"
    assert entry["language_neutral_contract"] is expected, (
        f"language_neutral_contract = {entry['language_neutral_contract']!r}, "
        f"expected {expected!r}"
    )
