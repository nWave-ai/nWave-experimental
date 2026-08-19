"""Unit/acceptance tests for `compile_delivery_contract`
(`des compile-contract`'s pure core, ADR-SSOT-002 Section 4/4b item 1).

The primary acceptance evidence is `test_skeleton_passes_every_existing_dispatch_validator`:
it feeds the compiled skeleton directly into the SAME `des dispatch`
validators a real dispatch call runs (declared-import resolution, EXTEND
citation, verification-command resolution, whole-suite scope) and asserts
every one reports zero findings -- "passes by construction", not by luck.

`test_real_k4_run13_brief_compiles_a_correct_skeleton` replays the exact
scenario the compiler was built for (K4 run-13, maintenance-windows) against
a clean base-revision scratch copy built from the real brief's real base
commit -- skipped when that fixture repository is not present on this
machine (it is an external, temporary K4 harness output, never a checked-in
dependency of this repository).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.application.compile_contract import (
    Blocked,
    CompileContractInputs,
    Compiled,
    compile_delivery_contract,
)
from des.cli._declared_import_refusal import all_missing_declared_imports
from des.cli._verification_command_refusal import all_missing_verification_paths
from des.cli._whole_suite_scope_refusal import missing_whole_suite_scope_finding
from des.cli.dispatch import _extend_targets_missing_citation
from des.domain.contract_placeholder_resolver import PLACEHOLDER


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")


_SYNTHETIC_TARGET_MODULE = '''\
"""A tiny stand-in production module, shaped like the K4 fixture."""
from thirdpartylib import Helper


class Widget:
    def existing_method(self):
        return None
'''

_SYNTHETIC_BRIEF = """\
# Architecture Brief

## Widget gains a color

### Reuse survey

`Widget` (`pkg/widget.py:5`) already exposes `existing_method`
(`pkg/widget.py:6`), reused unchanged. `Helper` (`pkg/widget.py:2`) is
already imported and reused for validation.

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: color validation reuses `Helper`.
2. **REPRESENTATION_CHANGE** -- law: the API representation gains `color`.
"""


def _build_repo(tmp_path: Path, *, with_sibling_tests_dir: bool = True) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.py").write_text(
        _SYNTHETIC_TARGET_MODULE, encoding="utf-8"
    )
    if with_sibling_tests_dir:
        (repo_root / "pkg" / "tests").mkdir()
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `pytest --noinput`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def _inputs(repo_root: Path, **overrides: object) -> CompileContractInputs:
    fields: dict[str, object] = {
        "repo_root": repo_root,
        "delivery_id": "widget-color",
        "brief_text": _SYNTHETIC_BRIEF,
        "delivery_route": "RED_TO_GREEN",
        "paradigm": "object_oriented",
        "examine": True,
        "budget_token_limit": 2_000_000,
        "budget_wall_clock_minutes": 30,
    }
    fields.update(overrides)
    return CompileContractInputs(**fields)  # type: ignore[arg-type]


def test_compiles_targets_from_citations(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert set(result.contract["targets"]) == {"pkg/widget.py"}
    target = result.contract["targets"]["pkg/widget.py"]
    assert target["decision"] == "EXTEND"
    assert "pkg/widget.py:5" in target["overlap"]


def test_compiles_obligations_from_bold_labels(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert result.contract["obligations"] == [
        "REUSE_CANDIDATE",
        "REPRESENTATION_CHANGE",
    ]


def test_independent_review_defaults_false_without_boundary_change(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert result.contract["applicability"]["independent-review"] is False


def test_independent_review_true_with_architecture_boundary_change(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    brief = _SYNTHETIC_BRIEF + "3. **ARCHITECTURE_BOUNDARY_CHANGE** -- law: X.\n"
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert result.contract["applicability"]["independent-review"] is True


def test_semantic_fields_are_left_as_placeholders(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert result.contract["outcome"] == PLACEHOLDER
    target = result.contract["targets"]["pkg/widget.py"]
    assert target["justification"] == PLACEHOLDER
    assert target["boundary"]["failure-behavior"] == PLACEHOLDER


def test_independent_review_override_wins_over_obligations_proxy(
    tmp_path: Path,
) -> None:
    """Seeded fact (ADR-SSOT-002 Section 4c) always wins: an explicit
    `independent_review=False` overrides the obligations-based proxy even
    when ARCHITECTURE_BOUNDARY_CHANGE is present, and vice versa."""
    repo_root = _build_repo(tmp_path)
    brief = _SYNTHETIC_BRIEF + "3. **ARCHITECTURE_BOUNDARY_CHANGE** -- law: X.\n"
    result = compile_delivery_contract(
        _inputs(repo_root, brief_text=brief, independent_review=False)
    )
    assert isinstance(result, Compiled)
    assert result.contract["applicability"]["independent-review"] is False

    result2 = compile_delivery_contract(_inputs(repo_root, independent_review=True))
    assert isinstance(result2, Compiled)
    assert result2.contract["applicability"]["independent-review"] is True


def test_oracle_locator_derived_from_sibling_tests_dir(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path, with_sibling_tests_dir=True)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert (
        result.contract["acceptance-tests"]["locator"]
        == "pkg/tests/test_widget_color.py"
    )


def test_oracle_locator_falls_back_to_repository_root_tests_dir(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path, with_sibling_tests_dir=False)
    (repo_root / "tests").mkdir()
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert (
        result.contract["acceptance-tests"]["locator"] == "tests/test_widget_color.py"
    )


def test_no_discoverable_test_dir_blocks_instead_of_guessing(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path, with_sibling_tests_dir=False)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Blocked)
    assert "test-directory convention" in result.what


def test_no_citation_blocks_instead_of_guessing(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(
        _inputs(repo_root, brief_text="No citations at all in this brief.")
    )
    assert isinstance(result, Blocked)
    assert "citation" in result.what


def test_no_obligation_token_blocks_instead_of_guessing(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    brief = "See `pkg/widget.py:5` but no obligation is bold-labeled."
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "obligation" in result.what


def test_skeleton_passes_every_existing_dispatch_validator(tmp_path: Path) -> None:
    """The compiled skeleton passes BY CONSTRUCTION: every one of the
    existing `des dispatch` content validators reports zero findings when
    run directly against it, without ever calling `des dispatch` itself
    (which additionally requires the oracle file to physically exist --
    ATD's own later act, out of this compiler's scope)."""
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    contract = result.contract

    assert _extend_targets_missing_citation(contract) == []
    assert all_missing_declared_imports(repo_root, contract) == []
    assert all_missing_verification_paths(repo_root, contract) == []
    assert missing_whole_suite_scope_finding(repo_root, contract) is None


_K4_ROOT = Path("/tmp/nwave-k4-8c4ecb83b/k4-root")
_K4_BRIEF = _K4_ROOT / "docs" / "product" / "architecture" / "brief.md"


@pytest.mark.skipif(
    not _K4_BRIEF.is_file(),
    reason="external K4 run-13 harness fixture not present on this machine",
)
def test_real_k4_run13_brief_compiles_a_correct_skeleton(tmp_path: Path) -> None:
    """Replays the real ADR-SSOT-002 K4 run-13 (maintenance-windows) brief
    against a CLEAN base-revision copy (the live K4 harness worktree is
    read-only and, separately, already carries an in-progress
    implementation from a prior run -- this test builds its own clean
    scratch base from that same repository's committed HEAD, never writing
    into it)."""
    scratch = tmp_path / "k4-clean-base"
    (scratch / "hc" / "api" / "management" / "commands").mkdir(parents=True)
    (scratch / "hc" / "api" / "tests").mkdir(parents=True)
    for relative in (
        "hc/api/models.py",
        "hc/api/views.py",
        "hc/api/management/commands/sendalerts.py",
    ):
        content = subprocess.run(
            ["git", "-C", str(_K4_ROOT), "show", f"HEAD:{relative}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        (scratch / relative).write_text(content, encoding="utf-8")
    (scratch / "CLAUDE.md").write_text(
        "- Run the subject's own tests: "
        "`k4-fixture-venv/bin/python manage.py test hc.api --noinput`\n",
        encoding="utf-8",
    )
    venv_python = scratch / "k4-fixture-venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    _init_repo(scratch)

    brief_text = _K4_BRIEF.read_text(encoding="utf-8")
    result = compile_delivery_contract(
        CompileContractInputs(
            repo_root=scratch,
            delivery_id="k4-maintenance-windows",
            brief_text=brief_text,
            delivery_route="RED_TO_GREEN",
            paradigm="object_oriented",
            examine=True,
            budget_token_limit=2_000_000,
            budget_wall_clock_minutes=30,
        )
    )
    assert isinstance(result, Compiled)
    contract = result.contract

    assert set(contract["targets"]) == {
        "hc/api/models.py",
        "hc/api/views.py",
        "hc/api/management/commands/sendalerts.py",
    }
    assert contract["obligations"] == [
        "REUSE_CANDIDATE",
        "REPRESENTATION_CHANGE",
        "INVALID_STATE",
        "PRESERVATION",
        "ARCHITECTURE_BOUNDARY_CHANGE",
    ]
    assert contract["applicability"]["independent-review"] is True
    # First-cited target is hc/api/models.py -- the oracle locator convention
    # resolves to that target's own sibling hc/api/tests/ directory.
    assert (
        contract["acceptance-tests"]["locator"]
        == "hc/api/tests/test_k4_maintenance_windows.py"
    )
    # The base-revision-absent `MaintenanceWindow`/`MaintenanceWindowSpec`
    # symbols the brief introduces as NEW production code are correctly
    # never invented into declared-imports at clean base.
    for target in contract["targets"].values():
        assert "MaintenanceWindow" not in target["declared-imports"]
        assert "MaintenanceWindowSpec" not in target["declared-imports"]

    assert _extend_targets_missing_citation(contract) == []
    assert all_missing_declared_imports(scratch, contract) == []
    assert all_missing_verification_paths(scratch, contract) == []
    assert missing_whole_suite_scope_finding(scratch, contract) is None
