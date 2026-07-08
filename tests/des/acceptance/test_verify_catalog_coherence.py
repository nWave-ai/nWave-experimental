"""Acceptance tests -- `des verify-catalog-coherence` (DISTILL, slice-01).

Charter: docs/product/expectations/verify-catalog-coherence/
         des-verify-catalog-coherence-reports-registry-catalog-drift.md
Feature-delta: docs/feature/verify-catalog-coherence/feature-delta.md

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/cli/verify_catalog_coherence.py:main(argv: list[str] | None) -> int`
compares three sets under `--repo-root`:
  (a) CLI registry subcommand names   (src/des/cli/__main__.py `_REGISTRY`)
  (b) catalog gate_ids                (nWave/gates/_catalog.yaml `gates[].gate_id`)
  (c) per-gate `.yaml` files          (nWave/gates/*.yaml minus `_catalog.yaml`/`_schema.yaml`)
Exit 0 when all three coherent. Exit non-zero naming each drifting id + the
HOW to fix when they diverge. Degrade-LOUD (non-zero + diagnostic, never a
traceback) on a malformed/missing catalog. Emits a self-explaining JSON
verdict (event/verdict/reason/how) to stdout.

Active-RED scaffolding (P1-P4, `nw-distill-red-scaffolding`): the module is
absent today, so the import happens INSIDE a helper called from each test
body (hidden-import), never at module top -- collection stays green
(COLLECT >= 1) and the absence surfaces as a semantic AssertionError
(MISSING_FUNCTIONALITY) at runtime, never a collection ImportError (BROKEN).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3): keep the absent module out of collection
# scope; the absence surfaces as a runtime AssertionError inside a test body.
# ---------------------------------------------------------------------------


def _import_verify_catalog_coherence():
    try:
        from des.cli.verify_catalog_coherence import main
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: src/des/cli/verify_catalog_coherence.py "
            f"does not exist yet ({exc}). Implement "
            "`main(argv: list[str] | None = None) -> int` per the DESIGN "
            "contract (feature-delta [REF] Code-Design) before this AT can "
            "pass."
        ) from exc
    return main


# ---------------------------------------------------------------------------
# Throwaway repo-tree builders -- mirror the real layout minimally so COHERENT
# and DRIFTED variants can be constructed under tmp_path.
# ---------------------------------------------------------------------------

_MAIN_PY_TEMPLATE = '''"""Throwaway CLI registry mirror (verify-catalog-coherence AT fixture)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _SubcommandRow:
    name: str
    module_path: str
    function_name: str


_REGISTRY: tuple[_SubcommandRow, ...] = (
{rows}
)
'''


def _write_registry(repo_root: Path, names: list[str]) -> None:
    cli_dir = repo_root / "src" / "des" / "cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f'    _SubcommandRow("{name}", "des.cli.{name.replace("-", "_")}", "main"),'
        for name in names
    )
    (cli_dir / "__main__.py").write_text(
        _MAIN_PY_TEMPLATE.format(rows=rows), encoding="utf-8"
    )


def _catalog_entry(gate_id: str) -> str:
    module = gate_id.replace("-", "_")
    return (
        f"  - gate_id: {gate_id}\n"
        f'    responsibility: "Throwaway fixture gate {gate_id}."\n'
        f"    module: des.cli.{module}\n"
        "    entry_function: main\n"
        "    language_neutral_contract: true"
    )


def _write_catalog(
    repo_root: Path, gate_ids: list[str], *, raw_text: str | None = None
) -> None:
    gates_dir = repo_root / "nWave" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = gates_dir / "_catalog.yaml"
    if raw_text is not None:
        catalog_path.write_text(raw_text, encoding="utf-8")
    else:
        entries = "\n".join(_catalog_entry(gid) for gid in gate_ids)
        catalog_path.write_text(
            f'version: "1.0.0"\n\ngates:\n{entries}\n', encoding="utf-8"
        )
    # Meta file that MUST be excluded from the per-gate-file set -- present
    # in every fixture so the coherent scenario also proves exclusion works.
    (gates_dir / "_schema.yaml").write_text(
        "# throwaway meta schema -- excluded from per-gate-file comparison\n",
        encoding="utf-8",
    )


def _write_per_gate_files(repo_root: Path, gate_ids: list[str]) -> None:
    gates_dir = repo_root / "nWave" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    for gid in gate_ids:
        module = gid.replace("-", "_")
        (gates_dir / f"{gid}.yaml").write_text(
            f"gate_id: {gid}\n"
            f'responsibility: "Throwaway fixture gate {gid}."\n'
            f"module: des.cli.{module}\n"
            "entry_function: main\n"
            "language_neutral_contract: true\n",
            encoding="utf-8",
        )


_BASE_IDS = ["gate-alpha", "gate-beta"]


def _build_coherent_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    _write_registry(repo_root, _BASE_IDS)
    _write_catalog(repo_root, _BASE_IDS)
    _write_per_gate_files(repo_root, _BASE_IDS)
    return repo_root


def _build_registry_not_in_catalog_repo(tmp_path: Path, drifting_id: str) -> Path:
    """Registry names a subcommand the catalog + per-gate files never got."""
    repo_root = tmp_path / "repo"
    _write_registry(repo_root, [*_BASE_IDS, drifting_id])
    _write_catalog(repo_root, _BASE_IDS)
    _write_per_gate_files(repo_root, _BASE_IDS)
    return repo_root


def _build_catalog_entry_without_per_gate_file_repo(
    tmp_path: Path, drifting_id: str
) -> Path:
    """Catalog (and registry) know the id; the per-gate `.yaml` was never authored."""
    repo_root = tmp_path / "repo"
    _write_registry(repo_root, [*_BASE_IDS, drifting_id])
    _write_catalog(repo_root, [*_BASE_IDS, drifting_id])
    _write_per_gate_files(repo_root, _BASE_IDS)  # drifting_id file deliberately absent
    return repo_root


def _build_malformed_catalog_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    _write_registry(repo_root, _BASE_IDS)
    _write_catalog(
        repo_root,
        _BASE_IDS,
        raw_text="gates: [this is: not, valid: yaml: at all\n",
    )
    _write_per_gate_files(repo_root, _BASE_IDS)
    return repo_root


def _how_text(verdict: dict) -> str:
    how = verdict.get("how", "")
    return " ".join(how) if isinstance(how, list) else str(how)


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE: coherent tree -> exit 0
# ---------------------------------------------------------------------------


def test_main_returns_zero_on_coherent_registry_catalog_and_gate_files(
    tmp_path, capsys
):
    main = _import_verify_catalog_coherence()
    repo_root = _build_coherent_repo(tmp_path)

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    assert exit_code == 0, (
        "expected exit 0 on a coherent registry/catalog/per-gate tree, got "
        f"{exit_code}: {captured.out}"
    )
    assert verdict["verdict"] == "coherent", verdict
    assert verdict.get("drifting_ids", []) == [], verdict


# ---------------------------------------------------------------------------
# Scenario 2 -- POSITIVE: registry entry missing from catalog -> non-zero + HOW
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("drifting_id", ["gate-gamma", "flavor-scaffold-new"])
def test_main_reports_registry_not_in_catalog_drift_and_how(
    tmp_path, capsys, drifting_id
):
    main = _import_verify_catalog_coherence()
    repo_root = _build_registry_not_in_catalog_repo(tmp_path, drifting_id)

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    assert exit_code != 0, (
        f"expected non-zero exit on registry->catalog drift, got 0: {captured.out}"
    )
    assert drifting_id in verdict.get("drifting_ids", []), verdict
    how_text = _how_text(verdict).lower()
    assert "catalog" in how_text, (
        f"HOW must name the missing-catalog-row fix: {verdict}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- POSITIVE: catalog entry with no per-gate file -> non-zero + HOW
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("drifting_id", ["gate-delta", "orphan-catalog-entry"])
def test_main_reports_catalog_entry_without_per_gate_file_drift_and_how(
    tmp_path, capsys, drifting_id
):
    main = _import_verify_catalog_coherence()
    repo_root = _build_catalog_entry_without_per_gate_file_repo(tmp_path, drifting_id)

    exit_code = main(["--repo-root", str(repo_root)])

    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    assert exit_code != 0, (
        f"expected non-zero exit on catalog->per-gate-file drift, got 0: {captured.out}"
    )
    assert drifting_id in verdict.get("drifting_ids", []), verdict
    how_text = _how_text(verdict).lower()
    assert ".yaml" in how_text or "per-gate" in how_text, (
        f"HOW must name the missing per-gate-file fix: {verdict}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- NEGATIVE AT: malformed catalog degrades LOUD, never silently
# passes and never crashes with a raw traceback.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_main_does_not_silently_pass_on_malformed_catalog(tmp_path, capsys):
    main = _import_verify_catalog_coherence()
    repo_root = _build_malformed_catalog_repo(tmp_path)

    try:
        exit_code = main(["--repo-root", str(repo_root)])
    except Exception as exc:
        pytest.fail(
            "degrade-LOUD violation: a malformed _catalog.yaml must return a "
            f"non-zero exit + diagnostic, not raise {type(exc).__name__}: {exc}"
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert exit_code != 0, (
        "degrade-LOUD violation: a malformed _catalog.yaml must NOT produce a "
        f"silent PASS (exit 0); got {exit_code}"
    )
    assert "Traceback" not in combined_output, (
        "degrade-LOUD violation: a malformed catalog crashed with a "
        f"traceback instead of a diagnostic verdict:\n{combined_output}"
    )
    assert combined_output.strip(), (
        "expected a non-empty diagnostic message on malformed catalog, got empty output"
    )
