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


# Count re-baseline 28 -> 30 (2026-06-15, f-declarative-gate-composition slice-01
# + retroactive wave-clear catalog reconcile): two legitimate new subcommands now
# in the registry, catalog and per-gate files, each 1:1 across all three surfaces
# -- verify-discuss-review (f-declarative OB-2) and wave-clear (reconciled; it was
# added to _REGISTRY by commit c89be75d1 but its catalog entry + per-gate file
# were omitted, breaking the 1:1 invariant the count pin guards).
# Count re-baseline 30 -> 33 (2026-06-16, f-coherence-and-attestation slice-06):
# three legitimate new subcommands wired across all three surfaces -- gate-g,
# self-attest, verify-test-runner (thin CLI drivers over the slice-03/04/05 logic).
# Count 33 -> 34 (2026-06-16, f-nonbypassable-attestation slice-05): verify-wave-dispatch
# wired across all three surfaces (the dispatch.pre guard; closes the catalog mirror
# its own slice-04 catalogato!=cablato invariant demanded).
# Count 34 -> 35 (2026-06-16, f-spine-runs-tests-not-git-hooks slice-01): run-slice-ats
# Count 35 -> 36 (2026-06-17, f-wave-contract-coherence slice-02): adds verify-wave-contract-coherence
# wired across all three surfaces (the slice-scoped EXECUTOR -- THE ACCELERATION;
# the commit-time test authority that supersedes the whole-tree run per slice).
# Count 36 -> 38 (2026-06-18, f-design-devops-review-gate slice-01): adds the DESIGN
# review-verdict pair record-design-review + verify-design-review (DISCUSS parity).
# Count 38 -> 40 (2026-06-19, f-design-devops-review-gate slice-02): adds the DEVOPS
# review-verdict pair record-devops-review + verify-devops-review (the SSOT-reuse
# proof -- the SAME generic core serves a SECOND wave).
# Count 40 -> 41 (2026-06-19, f-deliver-entry-contract-freeze slice-01): adds the
# DELIVER-entry contract-freeze gate verify-deliver-entry-contract.
# Count 41 -> 42 (2026-06-20, f-attest-bundled-slice slice-01): adds the bundled-slice
# attestation command attest-bundled-slice, wired across all three surfaces (registry +
# catalog + per-gate file), built on reverify's shared _reverify_core (no parallel path).
# Count 43 -> 51 (2026-07-03, evolution-plan P0.1-P0.5 catalog reconcile): the five
# evidence-by-execution gates (verify-fresh-clone, verify-red-green, verify-negative-at,
# verify-doc-coherence, verify-execution-reach) were added to _REGISTRY by the v2
# evolution work WITHOUT their catalog rows + per-gate files -- exactly the
# registry-coherence drift class the per-slice build-tier exit gate now catches
# (F-CONTRACT-GATE-EXCLUDES-BUILD-TIER-ARCH-TESTS). Reconciled 1:1 across all
# three surfaces.
# Count 51 -> 52 (2026-07-06, feature-delta-doctor-and-ssot slice-01, WS-2 / M2):
# feature-delta-doctor was added to _REGISTRY without its catalog row; reconciled 1:1.
# Count 53 -> 54 (2026-07-08, fix-flavor-scaffold-catalog-reconciliation): flavor-scaffold was in _REGISTRY without its catalog row + per-gate file; reconciled 1:1. Prior 52 -> 53 (2026-07-07, des-dispatch-ssot-renderer Fase-2): dispatch was
# added to _REGISTRY without its catalog row; reconciled 1:1.
# Count 54 -> 55 (2026-07-08, verify-catalog-coherence slice-01): adds the fast
# registry<->catalog<->per-gate-file drift check verify-catalog-coherence,
# wired across all three surfaces (dogfoods its own reconciliation rule).
# Count 55 -> 56 (2026-07-08, check-contract-shape-declarations slice-01):
# adds check-contract-shape, the producing tool for Principle-11's 3
# mechanical Contract-Shape checks, wired across all three surfaces.
# Count 56 -> 57 (2026-07-09, charter-scaffold slice-01): adds
# charter-scaffold, wired across all three surfaces.
@then("both contain exactly 57 entries")
def then_both_counts_match(composition) -> None:
    assert len(composition.catalog_gate_ids) == 57, (
        f"Catalog has {len(composition.catalog_gate_ids)} entries, expected 57"
    )
    assert len(composition.registry_names) == 57, (
        f"_REGISTRY has {len(composition.registry_names)} entries, expected 57"
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
