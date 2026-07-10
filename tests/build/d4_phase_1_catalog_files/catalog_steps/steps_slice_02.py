"""Step bindings for D4 Phase 1 slice-02 per-gate files validation.

Per Mandate-12 + Mandate-13: composition-root pattern, no internal field
introspection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from des.cli.verify_catalog_coherence import CoherenceResult, compute_catalog_coherence

from ..conftest import GATES_DIR, REPO_ROOT


# Excluded "underscore-prefixed" meta files from per-gate enumeration.
_META_FILES = {"_catalog.yaml", "_schema.yaml"}


class PerGateComposition:
    def __init__(self) -> None:
        self._per_gate_files: list[Path] | None = None
        self._catalog_ids: list[str] | None = None
        self._schema: dict | None = None
        self._validation_errors: list[str] = []
        self._language_bound: list[str] = []
        self._coherence_result: CoherenceResult | None = None

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

    def check_catalog_coherence(self) -> None:
        self._coherence_result = compute_catalog_coherence(REPO_ROOT)

    @property
    def coherence_result(self) -> CoherenceResult:
        assert self._coherence_result is not None
        return self._coherence_result

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


@then("catalog and per-gate files are coherent (no orphans either direction)")
def then_catalog_and_per_gate_coherent(per_gate_comp) -> None:
    per_gate_comp.check_catalog_coherence()
    result = per_gate_comp.coherence_result
    assert result.catalog_without_per_gate_file == (), (
        f"Catalog entries missing per-gate files: {result.catalog_without_per_gate_file}"
    )
    assert result.per_gate_without_catalog_entry == (), (
        f"Per-gate files missing catalog entries: {result.per_gate_without_catalog_entry}"
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
