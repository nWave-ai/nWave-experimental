"""Step bindings for D4 Phase 1 slice-02 per-gate files validation.

Per Mandate-12 + Mandate-13: composition-root pattern, no internal field
introspection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest import GATES_DIR


# Excluded "underscore-prefixed" meta files from per-gate enumeration.
_META_FILES = {"_catalog.yaml", "_schema.yaml"}


class PerGateComposition:
    def __init__(self) -> None:
        self._per_gate_files: list[Path] | None = None
        self._catalog_ids: list[str] | None = None
        self._schema: dict | None = None
        self._validation_errors: list[str] = []
        self._language_bound: list[str] = []

    def load_files(self) -> None:
        self._per_gate_files = sorted(
            p for p in GATES_DIR.glob("*.yaml") if p.name not in _META_FILES
        )

    def load_catalog(self) -> None:
        import yaml

        catalog = yaml.safe_load((GATES_DIR / "_catalog.yaml").read_text())
        self._catalog_ids = [g["gate_id"] for g in catalog["gates"]]

    def load_schema(self) -> None:
        import yaml

        self._schema = yaml.safe_load((GATES_DIR / "_schema.yaml").read_text())

    def validate_all(self) -> None:
        import jsonschema
        import yaml

        full_schema = {
            "$defs": self._schema["$defs"],
            **self._schema["$defs"]["GateContractFull"],
        }
        for f in self._per_gate_files:
            entry = yaml.safe_load(f.read_text())
            try:
                jsonschema.validate(instance=entry, schema=full_schema)
            except jsonschema.ValidationError as exc:
                self._validation_errors.append(f"{f.name}: {exc.message}")

    def enumerate_language_bound(self) -> None:
        import yaml

        self._language_bound = []
        for f in self._per_gate_files:
            entry = yaml.safe_load(f.read_text())
            if entry["language_neutral_contract"] is False:
                self._language_bound.append(entry["gate_id"])

    @property
    def file_count(self) -> int:
        return len(self._per_gate_files or [])

    @property
    def file_stems(self) -> list[str]:
        return [f.stem for f in (self._per_gate_files or [])]

    @property
    def catalog_ids(self) -> list[str]:
        return self._catalog_ids or []

    @property
    def validation_errors(self) -> list[str]:
        return self._validation_errors

    @property
    def language_bound(self) -> list[str]:
        return sorted(self._language_bound)

    def file_internal_gate_id(self, stem: str) -> str:
        import yaml

        path = GATES_DIR / f"{stem}.yaml"
        entry = yaml.safe_load(path.read_text())
        return entry["gate_id"]


@pytest.fixture
def per_gate_comp() -> PerGateComposition:
    return PerGateComposition()


@given(parsers.parse('the per-gate file directory at "{path}"'))
def given_dir(per_gate_comp, path: str) -> None:
    per_gate_comp.load_files()
    per_gate_comp.load_schema()


@given(parsers.parse('the gate catalog loaded from "{path}"'))
def given_catalog_loaded_s2(per_gate_comp, path: str) -> None:
    per_gate_comp.load_catalog()


@given(parsers.parse('the per-gate files loaded from "{path}"'))
def given_per_gate_files(per_gate_comp, path: str) -> None:
    per_gate_comp.load_files()


@when("each per-gate file is loaded and validated")
def when_validate_all(per_gate_comp) -> None:
    per_gate_comp.validate_all()


@when("the filenames are compared to catalog gate_ids")
def when_compare_names(per_gate_comp) -> None:
    pass  # @then reads


@when("language_neutral_contract:false entries are enumerated")
def when_enumerate_bound(per_gate_comp) -> None:
    per_gate_comp.enumerate_language_bound()


# Count re-baseline 28 -> 30 (2026-06-15, f-declarative-gate-composition slice-01
# + retroactive wave-clear catalog reconcile): per-gate files for the two new
# subcommands verify-discuss-review + wave-clear (each 1:1 with its catalog entry).
# Count re-baseline 30 -> 33 (2026-06-16, f-coherence-and-attestation slice-06):
# per-gate files for gate-g + self-attest + verify-test-runner (each 1:1 catalog).
# Count 33 -> 34 (2026-06-16, f-nonbypassable-attestation slice-05): per-gate file
# for verify-wave-dispatch (1:1 with its catalog entry).
# Count 34 -> 35 (2026-06-16, f-spine-runs-tests-not-git-hooks slice-01): per-gate
# Count 35 -> 36 (2026-06-17, f-wave-contract-coherence slice-02): adds verify-wave-contract-coherence
# file for run-slice-ats (the slice-scoped EXECUTOR), 1:1 with its catalog entry.
# Count 36 -> 38 (2026-06-18, f-design-devops-review-gate slice-01): per-gate files
# for the DESIGN review-verdict pair (record/verify-design-review), 1:1 with catalog.
# Count 38 -> 40 (2026-06-19, f-design-devops-review-gate slice-02): per-gate files
# for the DEVOPS review-verdict pair (record/verify-devops-review), 1:1 with catalog.
# Count 40 -> 41 (2026-06-19, f-deliver-entry-contract-freeze slice-01): per-gate file
# for the DELIVER-entry contract-freeze gate (verify-deliver-entry-contract).
# Count 41 -> 42 (2026-06-20, f-attest-bundled-slice slice-01): per-gate file for the
# bundled-slice attestation command (attest-bundled-slice), 1:1 with its catalog entry.
# Count 43 -> 51 (2026-07-03, evolution-plan P0.1-P0.5): five per-gate files for
# the evidence-by-execution gate family, 1:1 with catalog + _REGISTRY.
# Count 51 -> 52 (2026-07-06, feature-delta-doctor-and-ssot slice-01, WS-2 / M2):
# per-gate file for feature-delta-doctor, 1:1 with its catalog entry.
# Count 53 -> 54 (2026-07-08, fix-flavor-scaffold-catalog-reconciliation): flavor-scaffold was in _REGISTRY without its catalog row + per-gate file; reconciled 1:1. Prior 52 -> 53 (2026-07-07, des-dispatch-ssot-renderer Fase-2):
# per-gate file for dispatch, 1:1 with its catalog entry.
# Count 54 -> 55 (2026-07-08, verify-catalog-coherence slice-01): per-gate file
# for verify-catalog-coherence, 1:1 with its catalog entry.
# Count 55 -> 56 (2026-07-08, check-contract-shape-declarations slice-01):
# per-gate file for check-contract-shape, 1:1 with its catalog entry.
# Count 56 -> 57 (2026-07-09, charter-scaffold slice-01): per-gate file for
# charter-scaffold, 1:1 with its catalog entry.
@then("exactly 57 per-gate files exist (one per catalog entry)")
def then_per_gate_file_count(per_gate_comp) -> None:
    assert per_gate_comp.file_count == 57, (
        f"Found {per_gate_comp.file_count} per-gate files, expected 57"
    )


@then("every per-gate file validates against the GateContractFull schema")
def then_all_valid(per_gate_comp) -> None:
    assert per_gate_comp.validation_errors == [], (
        f"Validation errors: {per_gate_comp.validation_errors}"
    )


@then("every catalog gate_id has a corresponding per-gate file with matching name")
def then_catalog_to_files(per_gate_comp) -> None:
    missing = set(per_gate_comp.catalog_ids) - set(per_gate_comp.file_stems)
    assert not missing, f"Catalog ids missing per-gate file: {missing}"


@then("every per-gate file's internal gate_id field equals its filename stem")
def then_internal_matches_stem(per_gate_comp) -> None:
    mismatches = []
    for stem in per_gate_comp.file_stems:
        internal = per_gate_comp.file_internal_gate_id(stem)
        if internal != stem:
            mismatches.append(f"{stem}.yaml internal gate_id={internal}")
    assert not mismatches, f"Filename/gate_id mismatches: {mismatches}"


@then("exactly 2 gates are language-bound")
def then_count_2_bound(per_gate_comp) -> None:
    assert len(per_gate_comp.language_bound) == 2, (
        f"language_bound count={len(per_gate_comp.language_bound)}, expected 2; "
        f"found: {per_gate_comp.language_bound}"
    )


@then(parsers.parse('the language-bound set equals "{expected_csv}"'))
def then_bound_set_equals(per_gate_comp, expected_csv: str) -> None:
    expected = sorted(s.strip() for s in expected_csv.split(","))
    assert per_gate_comp.language_bound == expected, (
        f"language_bound={per_gate_comp.language_bound}, expected={expected}"
    )


scenarios("../slice-02-per-gate-files.feature")
