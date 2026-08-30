"""The touched-file commit gate selects real tests, and is actually WIRED.

Guards ``scripts/hooks/pytest_touched_files.py``, the pre-commit gate that
replaced marker-based selection after the 2026-08-22 census measured the local
safety net at 78 of 6548 tests with NO tier covered
(``F-LOCAL-GATE-COVERAGE-1-2-PERCENT``).

Two properties are asserted, and the second is the one that rots: a gate that
exists but is not wired into ``.pre-commit-config.yaml`` at the ``pre-commit``
stage protects nothing (catalogued != wired).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = PROJECT_ROOT / "scripts" / "hooks" / "pytest_touched_files.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("pytest_touched_files", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def test_package_init_yields_no_module_name(gate):
    """``des`` as a bare package name matches every test file's text.

    Keying on it silently degenerates the selector into a full-suite run, which
    is exactly the box-saturating behaviour this gate exists to avoid.
    """
    assert gate.module_names("src/des/__init__.py") == set()


def test_source_file_resolves_to_both_import_spellings(gate):
    assert gate.module_names("src/des/application/capacity_snapshot.py") == {
        "des.application.capacity_snapshot",
        "src.des.application.capacity_snapshot",
    }


def test_touching_a_source_file_selects_the_test_that_references_it(gate):
    runnable, _deferred, uncovered = gate.select(
        ["src/des/application/capacity_snapshot.py"], PROJECT_ROOT
    )
    assert "tests/des/unit/application/test_capacity_snapshot.py" in runnable
    assert uncovered == []


def test_touching_a_test_file_always_runs_it(gate):
    target = "tests/des/unit/application/test_capacity_snapshot.py"
    runnable, _deferred, _uncovered = gate.select([target], PROJECT_ROOT)
    assert runnable == [target]


def test_docker_and_compile_tiers_are_deferred_not_run(gate):
    """The exclusion must be visible in ``deferred``, never silently dropped.

    The probe must be a COLLECTIBLE e2e file. An earlier version of this test
    took ``sorted(...)[0]``, which is ``tests/des/e2e/__init__.py`` -- not a
    file pytest collects, so the selector correctly expands it to its whole
    subtree instead of returning it. Asserting on a non-collectible probe made
    the test assert the selector's OLD, defective behaviour.
    """
    e2e_files = sorted(
        rel
        for rel in (
            p.relative_to(PROJECT_ROOT).as_posix()
            for p in (PROJECT_ROOT / "tests").rglob("*.py")
            if "/e2e/" in p.as_posix() and "__pycache__" not in p.parts
        )
        if gate.is_collectible(rel)
    )
    assert e2e_files, "no e2e test files found -- the exclusion rule would be vacuous"
    runnable, deferred, _uncovered = gate.select([e2e_files[0]], PROJECT_ROOT)
    assert runnable == []
    assert deferred == [e2e_files[0]]


def test_prose_only_paths_select_nothing_and_are_not_reported_uncovered(gate):
    runnable, deferred, uncovered = gate.select(
        ["docs/product/backlog.md"], PROJECT_ROOT
    )
    assert (runnable, deferred, uncovered) == ([], [], [])


def test_an_unmapped_path_is_declared_uncovered_out_loud(gate):
    _runnable, _deferred, uncovered = gate.select(
        ["some/unknown/place/thing.conf"], PROJECT_ROOT
    )
    assert any("some/unknown/place/thing.conf" in entry for entry in uncovered)


def test_the_gate_is_wired_at_the_precommit_stage():
    config = (PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: pytest-touched-files" in config, (
        "the touched-file gate is not registered in .pre-commit-config.yaml"
    )
    block = config.split("id: pytest-touched-files", 1)[1].split("- id:", 1)[0]
    assert "pytest_touched_files.py" in block
    assert "stages: [pre-commit]" in block, (
        "the gate must run at the pre-commit stage — a manual/pre-push-only "
        "stage is how pytest-quick-tiers became a gate that never fires"
    )


# --- the third state: expected-red ------------------------------------------
#
# A two-state gate rejected the mainline DISTILL commit (2026-08-23,
# D-GATE-NO-EXPECTED-RED: an oracle authored before its implementation cannot
# be COLLECTED, and the gate scored that as failure). These tests pin the
# DISCRIMINATION, which is the whole point: exempting every test that fails to
# import would be a sieve, strictly worse than the defect it replaced.

_MISSING = "ModuleNotFoundError: No module named 'des.cli.update'"
_ORACLE = "tests/des/unit/cli/test_probe.py"


def _contract(tmp_path, *, route="RED_TO_GREEN", targets=("src/des/cli/update.py",)):
    contracts = tmp_path / "docs" / "delivery-contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    (contracts / "probe.json").write_text(
        json.dumps(
            {
                "delivery-id": "probe-id",
                "delivery-route": route,
                "acceptance-tests": {"locator": _ORACLE},
                "targets": {t: {} for t in targets},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _collect(returncode, output):
    return lambda _rel_path: (returncode, output)


def _closure_contract(
    root: Path,
    *,
    name: str = "closure.json",
    route: str = "RED_TO_GREEN",
    locator: str = _ORACLE,
    supporting: list[str] | None = None,
    targets: dict[str, dict[str, str]] | None = None,
    include_supporting: bool = True,
    schema_version: str | None = None,
    raw: str | None = None,
) -> str:
    rel_path = f"docs/delivery-contracts/{name}"
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is None:
        acceptance = {"locator": locator}
        if include_supporting:
            acceptance["supporting-locators"] = supporting or []
        raw = json.dumps(
            {
                "schema-version": schema_version
                or ("1.4" if include_supporting else "1.3"),
                "delivery-route": route,
                "acceptance-tests": acceptance,
                "targets": targets or {"src/present.py": {"decision": "EXTEND"}},
            }
        )
    path.write_text(raw, encoding="utf-8")
    return rel_path


def _private_constructor_index(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("GIT_INDEX_FILE", str(root / "nwave-delivery-P5.index"))


def _present_extend_target(root: Path) -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "present.py").write_text("present = True\n")


def _present_test_files(root: Path, *paths: str) -> None:
    for rel_path in paths:
        path = root / rel_path.split("::", 1)[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_present(): assert True\n")


def test_declared_oracle_of_an_open_contract_is_expected_red(gate, tmp_path):
    """The falsifier: the mainline DISTILL commit must pass."""
    root = _contract(tmp_path)
    kept, expected_red = gate.partition_expected_red(
        [_ORACLE], root, _collect(2, _MISSING)
    )
    assert kept == []
    assert [path for path, _reason in expected_red] == [_ORACLE]
    assert "probe-id" in expected_red[0][1]


def test_closure_constructor_exempts_exact_red_oracle_and_support(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    support = "tests/des/unit/cli/test_probe_support.py"
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE, support)
    contract = _closure_contract(
        tmp_path,
        supporting=[support],
        targets={"src/present.py": {"decision": "EXTEND"}},
    )

    assert gate._closure_authority_expected_red(
        [contract, _ORACLE, support], tmp_path
    ) == [(_ORACLE, _ORACLE), (support, support)]


def test_closure_authority_accepts_v13_without_supporting_locators(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE)
    contract = _closure_contract(tmp_path, include_supporting=False)

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == [
        (_ORACLE, _ORACLE)
    ]


def test_closure_authority_normalizes_pytest_selectors_before_touched_match(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    selector = _ORACLE + "::test_x"
    support = "tests/des/unit/cli/test_probe_support.py"
    _present_test_files(tmp_path, selector, support)
    contract = _closure_contract(tmp_path, locator=selector, supporting=[support])

    assert gate._closure_authority_expected_red(
        [contract, _ORACLE, support], tmp_path
    ) == [
        (_ORACLE, selector),
        (support, support),
    ]


def test_closure_authority_refuses_duplicate_selector_normalized_ownership(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    selector = _ORACLE + "::test_one"
    duplicate = _ORACLE
    _present_test_files(tmp_path, selector)
    contract = _closure_contract(tmp_path, locator=selector, supporting=[duplicate])

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == []


@pytest.mark.parametrize(
    "targets",
    (
        {"src/present.py": {"decision": "CREATE_NEW"}},
        {"src/present.py": {}},
        {"src/present.py": []},
        {"src/missing.py": {"decision": "EXTEND"}},
    ),
)
def test_closure_authority_requires_existing_extend_targets(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch, targets: dict[str, object]
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE)
    contract = _closure_contract(tmp_path, targets=targets)  # type: ignore[arg-type]

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == []


def test_closure_authority_rejects_present_invalid_supporting_locators(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE)
    contract = _closure_contract(
        tmp_path,
        raw=json.dumps(
            {
                "schema-version": "1.4",
                "delivery-route": "RED_TO_GREEN",
                "acceptance-tests": {
                    "locator": _ORACLE,
                    "supporting-locators": "not-a-list",
                },
                "targets": {"src/present.py": {"decision": "EXTEND"}},
            }
        ),
    )

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == []


def test_closure_authority_rejects_v14_without_supporting_locators(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE)
    contract = _closure_contract(
        tmp_path,
        include_supporting=False,
        schema_version="1.4",
    )

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == []


@pytest.mark.parametrize("supporting", ([], [_ORACLE + "::test_support"]))
def test_closure_authority_rejects_empty_or_selector_supporting_locators(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch, supporting: list[str]
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    _present_test_files(tmp_path, _ORACLE)
    contract = _closure_contract(tmp_path, supporting=supporting)

    assert gate._closure_authority_expected_red([contract, _ORACLE], tmp_path) == []


def test_closure_authority_prints_each_exemption_and_runs_other_touched_tests(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    oracle = tmp_path / _ORACLE
    control_rel = "tests/des/unit/cli/test_control.py"
    control = tmp_path / control_rel
    oracle.parent.mkdir(parents=True)
    oracle.write_text("def test_oracle(): assert False\n")
    control.write_text("def test_control(): assert True\n")
    contract = _closure_contract(tmp_path, include_supporting=False)
    commands: list[list[str]] = []
    monkeypatch.setattr(gate, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda command, **_kwargs: (
            commands.append(command) or SimpleNamespace(returncode=0)
        ),
    )

    assert gate.main([contract, _ORACLE, control_rel]) == 0

    assert "EXPECTED-RED CLOSURE AUTHORITY: " + _ORACLE in capsys.readouterr().err
    assert commands and control_rel in commands[0]
    assert _ORACLE not in commands[0]


@pytest.mark.parametrize(
    "kind",
    (
        "normal-index",
        "malformed",
        "green-to-green",
        "unrelated-test",
        "conflict",
    ),
)
def test_closure_authority_exemption_fails_closed_outside_one_exact_context(
    gate, tmp_path, monkeypatch: pytest.MonkeyPatch, kind: str
):
    _private_constructor_index(monkeypatch, tmp_path)
    _present_extend_target(tmp_path)
    support = "tests/des/unit/cli/test_probe_support.py"
    _present_test_files(tmp_path, _ORACLE, support)
    contract = _closure_contract(tmp_path, supporting=[support])
    touched = [contract, _ORACLE, support]
    if kind == "normal-index":
        monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / ".git/index"))
    elif kind == "malformed":
        _closure_contract(tmp_path, raw="{not json")
    elif kind == "green-to-green":
        _closure_contract(tmp_path, route="GREEN_TO_GREEN")
    elif kind == "unrelated-test":
        touched = [contract, "tests/des/unit/cli/test_unrelated.py"]
    else:
        conflicting = _closure_contract(tmp_path, name="conflict.json", locator=support)
        touched.append(conflicting)

    assert gate._closure_authority_expected_red(touched, tmp_path) == []


def test_an_undeclared_file_with_the_same_import_error_still_blocks(gate, tmp_path):
    """Counter-proof 1, the load-bearing one: no blanket import-error amnesty."""
    root = _contract(tmp_path)
    kept, expected_red = gate.partition_expected_red(
        ["tests/des/unit/cli/test_not_an_oracle.py"], root, _collect(2, _MISSING)
    )
    assert kept == ["tests/des/unit/cli/test_not_an_oracle.py"]
    assert expected_red == []


def test_an_oracle_that_collects_is_never_exempt(gate, tmp_path):
    """Counter-proof 2: a declared oracle red for an UNDECLARED reason blocks.

    Collection succeeding is the discriminator. The file goes into the normal
    run, so an assertion failure inside it still rejects the commit.
    """
    root = _contract(tmp_path)
    kept, expected_red = gate.partition_expected_red([_ORACLE], root, _collect(0, ""))
    assert kept == [_ORACLE]
    assert expected_red == []


def test_an_oracle_missing_an_undeclared_module_still_blocks(gate, tmp_path):
    """The REASON is checked, not assumed: a typo'd import is not a contract."""
    root = _contract(tmp_path)
    kept, _expected_red = gate.partition_expected_red(
        [_ORACLE], root, _collect(2, "ModuleNotFoundError: No module named 'requests'")
    )
    assert kept == [_ORACLE]


def test_a_syntax_error_in_an_oracle_still_blocks(gate, tmp_path):
    root = _contract(tmp_path)
    kept, _expected_red = gate.partition_expected_red(
        [_ORACLE], root, _collect(2, "E   SyntaxError: invalid syntax")
    )
    assert kept == [_ORACLE]


def test_a_contract_whose_targets_all_exist_grants_no_exemption(gate, tmp_path):
    """Conjunct 2: the work landed, so the oracle owes GREEN."""
    root = _contract(tmp_path, targets=("docs/delivery-contracts/probe.json",))
    assert gate.declared_red_oracles(root) == {}


def test_a_green_to_green_contract_grants_no_exemption(gate, tmp_path):
    """Conjunct 1: only RED_TO_GREEN authors an oracle ahead of its code."""
    root = _contract(tmp_path, route="GREEN_TO_GREEN")
    assert gate.declared_red_oracles(root) == {}


def test_an_unreadable_contract_fails_closed(gate, tmp_path):
    contracts = tmp_path / "docs" / "delivery-contracts"
    contracts.mkdir(parents=True)
    (contracts / "broken.json").write_text("{not json", encoding="utf-8")
    assert gate.declared_red_oracles(tmp_path) == {}


def test_the_real_g2_oracle_is_recognised_from_the_real_contract(gate):
    """Not a fixture: the property holds on the repository's own contracts."""
    declared = gate.declared_red_oracles(PROJECT_ROOT)
    entry = declared.get("tests/des/unit/cli/test_update.py")
    if entry is None:
        pytest.skip("auto-0d64ca2e4b7ded7d has landed; its targets now exist")
    delivery_id, absent_modules = entry
    assert delivery_id == "auto-0d64ca2e4b7ded7d"
    assert "des.cli.update" in absent_modules
