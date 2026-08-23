"""Unit/acceptance tests for `compile_delivery_contract`
(`des compile-contract`'s pure core, ADR-SSOT-002 Section 4/4b item 1).

The primary acceptance evidence is
`test_skeleton_satisfies_the_properties_the_deleted_validators_used_to_check`:
it checks the compiled skeleton directly against the SAME properties the
`des dispatch` EXTEND-citation/declared-import/verification-path validators
used to check before Ale's construction-over-file correction (2026-08-20,
"the contract has one writer -- `des fill-contract` is the constructor")
deleted them as Agda-proved vacuous
(``~/nwave-formal/2026-08-19-gates/report/2026-08-19-gate-analysis.md``) --
"passes by construction", not by luck, checked directly since no CLI
validator remains to assert against.

`test_real_k4_run13_brief_compiles_a_correct_skeleton` replays the exact
scenario the compiler was built for (K4 run-13, maintenance-windows) against
a clean base-revision scratch copy built from the real brief's real base
commit -- skipped when that fixture repository is not present on this
machine (it is an external, temporary K4 harness output, never a checked-in
dependency of this repository).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from des.application.compile_contract import (
    Blocked,
    CompileContractInputs,
    Compiled,
    binding_resolved_atoms,
    compile_delivery_contract,
    target_atoms_resolver,
)
from des.cli._whole_suite_scope_refusal import missing_whole_suite_scope_finding
from des.domain.architecture_brief_resolver import (
    PBT_FAMILY_SKILL,
    declared_imports_for_target,
)
from des.domain.contract_placeholder_resolver import PLACEHOLDER
from des.domain.declared_import_resolver import (
    is_name_bound_in_target_file,
    resolve_declared_import,
)
from des.domain.verification_command_resolver import missing_verification_paths


#: The SAME file:line-citation shape `_extend_targets_missing_citation`
#: (deleted from `des dispatch`) used to check -- kept here, test-only, as
#: a direct regression proof that the compiler's own `overlap` projection
#: always satisfies it, never as production code to resurrect.
_FILE_LINE_CITATION_RE = re.compile(r"[\w/.-]+\.\w+:\d+")


def _extend_targets_missing_citation(contract: dict) -> list[str]:
    return [
        target_path
        for target_path, target_plan in contract["targets"].items()
        if target_plan.get("decision") == "EXTEND"
        and not (
            _FILE_LINE_CITATION_RE.search(str(target_plan.get("overlap", "")))
            or _FILE_LINE_CITATION_RE.search(str(target_plan.get("justification", "")))
        )
    ]


def _all_missing_declared_imports(repo_root: Path, contract: dict) -> list[str]:
    return [
        reference
        for target_path, target_plan in contract["targets"].items()
        for reference in target_plan.get("declared-imports", [])
        if not is_name_bound_in_target_file(repo_root, target_path, reference)
        and not resolve_declared_import(repo_root, reference)
    ]


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


def test_compiles_no_cited_skills_when_the_brief_names_none(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert result.contract["cited-skills"] == []


def test_compiles_cited_skills_from_the_brief_grounded_against_installed_skills(
    tmp_path: Path,
) -> None:
    # Row 13 (K4 run 18): a brief citing `nw-pbt-python` by name must
    # become a mechanical `cited-skills` fact ATD can read, not silently
    # lost prose.
    repo_root = _build_repo(tmp_path)
    skill_dir = repo_root / "nWave" / "skills" / "nw-pbt-python"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# nw-pbt-python\n", encoding="utf-8")
    brief = _SYNTHETIC_BRIEF + "\nAuthor properties per `nw-pbt-python`.\n"

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Compiled)
    assert result.contract["cited-skills"] == ["nw-pbt-python"]


def _seed_skill(repo_root: Path, skill_name: str) -> None:
    skill_dir = repo_root / "nWave" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")


_GO_TARGET_MODULE = "package pkg\n\nfunc Existing() {}\n"

_GO_BRIEF = """\
# Architecture Brief

## Widget gains a color

### Reuse survey

`Existing` (`pkg/widget.go:3`) already exists, reused unchanged.
The oracle to author: `pkg/widget_test.go::TestWidgetColor`.

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: color validation reuses `Existing`.
2. **BROAD_INPUT_DOMAIN** -- law: color values need property coverage,
   author it per `nw-property-based-testing`.
"""


def _build_go_repo(tmp_path: Path) -> Path:
    # Row 13 follow-up (Ale, 2026-08-20): a simulated NON-Python subject,
    # to prove pbt-adapter resolution never defaults to Python.
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.go").write_text(_GO_TARGET_MODULE, encoding="utf-8")
    (repo_root / "pkg" / "tests").mkdir()
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def test_no_pbt_adapter_field_when_no_pbt_skill_is_cited(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert "pbt-adapter" not in result.contract


def test_compiles_pbt_adapter_resolved_from_python_targets_via_family_citation(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    _seed_skill(repo_root, PBT_FAMILY_SKILL)
    _seed_skill(repo_root, "nw-pbt-python")
    brief = _SYNTHETIC_BRIEF + f"\nAuthor properties per `{PBT_FAMILY_SKILL}`.\n"

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Compiled)
    assert result.contract["pbt-adapter"] == {
        "cited": PBT_FAMILY_SKILL,
        "resolved-variant": "nw-pbt-python",
        "status": "resolved",
        "reason": "target extension '.py' maps to 'nw-pbt-python'",
    }


def test_compiles_pbt_adapter_resolved_from_non_python_targets_via_family_citation(
    tmp_path: Path,
) -> None:
    # Ale: "nw-pbt-python e' troppo python-centric ... nWave e' language
    # agnostic" -- a Go subject must resolve nw-pbt-go, never nw-pbt-python.
    repo_root = _build_go_repo(tmp_path)
    _seed_skill(repo_root, PBT_FAMILY_SKILL)
    _seed_skill(repo_root, "nw-pbt-go")

    result = compile_delivery_contract(_inputs(repo_root, brief_text=_GO_BRIEF))

    assert isinstance(result, Compiled)
    assert result.contract["pbt-adapter"]["status"] == "resolved"
    assert result.contract["pbt-adapter"]["resolved-variant"] == "nw-pbt-go"


def test_compiles_pbt_adapter_discrepancy_when_cited_variant_disagrees_with_target(
    tmp_path: Path,
) -> None:
    repo_root = _build_go_repo(tmp_path)
    _seed_skill(repo_root, "nw-pbt-python")
    _seed_skill(repo_root, "nw-pbt-go")
    brief = _GO_BRIEF.replace(f"`{PBT_FAMILY_SKILL}`", "`nw-pbt-python`")

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Compiled)
    assert result.contract["pbt-adapter"]["cited"] == "nw-pbt-python"
    assert result.contract["pbt-adapter"]["status"] == "discrepancy"
    assert result.contract["pbt-adapter"]["resolved-variant"] == "nw-pbt-go"


def test_compiles_pbt_adapter_family_fallback_when_target_variant_not_installed(
    tmp_path: Path,
) -> None:
    # Ale, 2026-08-20 follow-up: an unavailable language-specific adapter
    # is never an error -- the field always carries a USABLE skill.
    repo_root = _build_go_repo(tmp_path)
    _seed_skill(repo_root, PBT_FAMILY_SKILL)  # nw-pbt-go deliberately absent

    result = compile_delivery_contract(_inputs(repo_root, brief_text=_GO_BRIEF))

    assert isinstance(result, Compiled)
    assert result.contract["pbt-adapter"]["status"] == "family-fallback"
    assert result.contract["pbt-adapter"]["resolved-variant"] == PBT_FAMILY_SKILL


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


# -- GREEN_TO_GREEN oracle binding -- SF friction report 2026-08-20, items
# 2a/2b/2c: a nonexistent Python oracle path was projected for a
# GREEN_TO_GREEN Go delivery, a documentary citation became a contract
# target, and the verification command dot-joined a Python-module label no
# `go test` invocation accepts.

_GO_GREEN_TARGET_MODULE = "package pkg\n\nfunc Existing() {}\n"
_GO_GREEN_ORACLE_MODULE = (
    'package pkg\n\nimport "testing"\n\nfunc TestExisting(t *testing.T) {}\n'
)

_GO_GREEN_BRIEF = """\
# Architecture Brief

## Widget gains a color

### Reuse survey

`Existing` (`pkg/widget.go:3`) already exists, reused unchanged. The
existing oracle already covers it (`pkg/widget_test.go:5`). See also
the formal spec (`docs/design.md:1`) for the color law.

### Delivery obligations (GREEN_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: color validation reuses `Existing`.
"""


def _build_go_green_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.go").write_text(
        _GO_GREEN_TARGET_MODULE, encoding="utf-8"
    )
    (repo_root / "pkg" / "widget_test.go").write_text(
        _GO_GREEN_ORACLE_MODULE, encoding="utf-8"
    )
    (repo_root / "docs").mkdir()
    (repo_root / "docs" / "design.md").write_text("# design\n", encoding="utf-8")
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def _green_inputs(repo_root: Path, **overrides: object) -> CompileContractInputs:
    fields: dict[str, object] = {
        "repo_root": repo_root,
        "delivery_id": "widget-color-go",
        "brief_text": _GO_GREEN_BRIEF,
        "delivery_route": "GREEN_TO_GREEN",
        "paradigm": "functional",
        "examine": True,
        "budget_token_limit": 2_000_000,
        "budget_wall_clock_minutes": 30,
    }
    fields.update(overrides)
    return CompileContractInputs(**fields)  # type: ignore[arg-type]


def test_green_to_green_binds_the_real_existing_oracle_never_a_python_guess(
    tmp_path: Path,
) -> None:
    repo_root = _build_go_green_repo(tmp_path)
    result = compile_delivery_contract(_green_inputs(repo_root))
    assert isinstance(result, Compiled)
    # (2a) the REAL, already-committed Go oracle -- never a projected,
    # nonexistent `pkg/tests/test_widget_color_go.py`.
    assert result.contract["acceptance-tests"]["locator"] == "pkg/widget_test.go"


def test_green_to_green_never_admits_a_documentary_citation_as_a_target(
    tmp_path: Path,
) -> None:
    repo_root = _build_go_green_repo(tmp_path)
    result = compile_delivery_contract(_green_inputs(repo_root))
    assert isinstance(result, Compiled)
    # (2b) the doc citation never becomes a target; neither does the
    # test/spec-shaped oracle citation (sister reproduction, 2026-08-20:
    # targets are production files only -- the test is the oracle binding).
    assert "docs/design.md" not in result.contract["targets"]
    assert set(result.contract["targets"]) == {"pkg/widget.go"}


def test_green_to_green_verification_command_never_python_dot_joins_a_go_oracle(
    tmp_path: Path,
) -> None:
    repo_root = _build_go_green_repo(tmp_path)
    result = compile_delivery_contract(_green_inputs(repo_root))
    assert isinstance(result, Compiled)
    # (2c) the raw Go path, never a `pkg.widget_test.go`-shaped Python
    # dotted-module token no `go test` invocation accepts.
    oracle_command = result.contract["verification-scope"]["commands"][0]
    assert oracle_command["arguments"] == ["test", "pkg/widget_test.go"]


def test_green_to_green_blocks_instead_of_projecting_an_unauthored_oracle(
    tmp_path: Path,
) -> None:
    # No test/spec-shaped file is cited at all -- GREEN_TO_GREEN must never
    # fall back to inventing one, unlike RED_TO_GREEN's own conventional
    # projection.
    repo_root = _build_go_green_repo(tmp_path)
    brief = (
        "`Existing` (`pkg/widget.go:3`) already exists, reused unchanged.\n\n"
        "1. **REUSE_CANDIDATE** -- law: color validation reuses `Existing`.\n"
    )
    result = compile_delivery_contract(_green_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "GREEN_TO_GREEN" in result.what
    assert "already-committed" in result.what


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


def test_skeleton_satisfies_the_properties_the_deleted_validators_used_to_check(
    tmp_path: Path,
) -> None:
    """The compiled skeleton passes BY CONSTRUCTION: every property the
    now-deleted `des dispatch` content validators used to check (EXTEND
    citation, declared-import resolution, verification-scope path
    existence) holds directly against it, without ever calling `des
    dispatch` itself (which additionally requires the oracle file to
    physically exist -- ATD's own later act, out of this compiler's
    scope). Whole-suite scope is the one sibling check this correction did
    NOT delete (a producer-correctness claim, not a type any caller can
    check -- Agda vacuity report, MERGE verdict) -- still run for real."""
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    contract = result.contract

    assert _extend_targets_missing_citation(contract) == []
    assert _all_missing_declared_imports(repo_root, contract) == []
    assert missing_verification_paths(repo_root, contract) == []
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
    assert _all_missing_declared_imports(scratch, contract) == []
    assert missing_verification_paths(scratch, contract) == []
    assert missing_whole_suite_scope_finding(scratch, contract) is None


# -- RED_TO_GREEN oracle binding on a non-Python subject -- SF friction
# report 2026-08-20, sister reproduction (Go subject, route RED_TO_GREEN,
# 12 valid file:line citations across 6 files): (a) every .go citation was
# promoted to a target, INCLUDING the test the brief explicitly cited as
# the oracle; (b) the explicit oracle citation was ignored and a
# nonexistent Python `tests/test_auto_<id>.py` path was synthesized for a
# Go repository; (c) verification commands invented `python -m pytest`
# despite the subject's own declared `go test ./...` whole-suite command.
# Violates the no-new-Python and language-native-oracle disciplines.

_GO_RED_ORACLE_FILE = "go-shell/drive/verified_checkpoint_live_test.go"
_GO_RED_ORACLE_CITATION = (
    "go-shell/drive/verified_checkpoint_live_test.go"
    "::TestVerifiedCheckpointLiveBoundary"
)
_GO_RED_PRODUCTION_FILES = (
    "go-shell/drive/drive.go",
    "go-shell/drive/checkpoint.go",
    "go-shell/drive/manifest.go",
    "go-shell/drive/verify.go",
    "go-shell/drive/journal.go",
)

_GO_RED_ORACLE_MODULE = (
    'package drive\n\nimport "testing"\n\n'
    "func TestVerifiedCheckpointLiveBoundary(t *testing.T) {}\n"
)


def _go_red_brief(*, cite_oracle: bool = True) -> str:
    lines = [
        "# Architecture Brief",
        "",
        "## Verified checkpoint goes live",
        "",
        "### Reuse survey",
        "",
    ]
    for path in _GO_RED_PRODUCTION_FILES:
        lines.append(f"`{path}:3` and `{path}:9` are insertion points.")
    if cite_oracle:
        lines += [
            "",
            f"The oracle sketch sits at `{_GO_RED_ORACLE_FILE}:12` and",
            f"`{_GO_RED_ORACLE_FILE}:30`, bound as",
            f"`{_GO_RED_ORACLE_CITATION}`.",
        ]
    lines += [
        "",
        "### Delivery obligations (RED_TO_GREEN)",
        "",
        "1. **PRESERVATION** -- law: existing checkpoints stay verifiable.",
    ]
    return "\n".join(lines) + "\n"


def _build_go_red_repo(tmp_path: Path, *, with_declared_suite: bool = True) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "go-shell" / "drive").mkdir(parents=True)
    for path in _GO_RED_PRODUCTION_FILES:
        (repo_root / path).write_text(
            "package drive\n\nfunc Existing() {}\n", encoding="utf-8"
        )
    (repo_root / _GO_RED_ORACLE_FILE).write_text(
        _GO_RED_ORACLE_MODULE, encoding="utf-8"
    )
    # A root tests/ dir exists (as on the sister subject) -- the defect was
    # precisely that its presence let RED_TO_GREEN synthesize a Python
    # `tests/test_<slug>.py` locator for a Go repository.
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / ".gitkeep").write_text("", encoding="utf-8")
    if with_declared_suite:
        (repo_root / "CLAUDE.md").write_text(
            "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
        )
    _init_repo(repo_root)
    return repo_root


def _go_red_inputs(repo_root: Path, **overrides: object) -> CompileContractInputs:
    fields: dict[str, object] = {
        "repo_root": repo_root,
        "delivery_id": "verified-checkpoint-live",
        "brief_text": _go_red_brief(),
        "delivery_route": "RED_TO_GREEN",
        "paradigm": "functional",
        "examine": True,
        "budget_token_limit": 2_000_000,
        "budget_wall_clock_minutes": 30,
    }
    fields.update(overrides)
    return CompileContractInputs(**fields)  # type: ignore[arg-type]


def test_red_to_green_test_shaped_citation_is_never_a_target(
    tmp_path: Path,
) -> None:
    # (a) the test the brief cites as the oracle is an oracle-binding
    # candidate, never one of the contract's own targets.
    repo_root = _build_go_red_repo(tmp_path)
    result = compile_delivery_contract(_go_red_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert set(result.contract["targets"]) == set(_GO_RED_PRODUCTION_FILES)
    assert _GO_RED_ORACLE_FILE not in result.contract["targets"]


def test_red_to_green_binds_the_explicitly_cited_oracle_selector(
    tmp_path: Path,
) -> None:
    # (b) the brief's explicit `path::TestName` oracle citation IS the
    # locator, selector preserved -- never a synthesized Python path.
    repo_root = _build_go_red_repo(tmp_path)
    result = compile_delivery_contract(_go_red_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert result.contract["acceptance-tests"]["locator"] == _GO_RED_ORACLE_CITATION


def test_red_to_green_verification_commands_are_language_native(
    tmp_path: Path,
) -> None:
    # (c) both commands derive from the subject's own declared whole-suite
    # command (`go test ./...`) -- never an invented `python -m pytest`.
    repo_root = _build_go_red_repo(tmp_path)
    result = compile_delivery_contract(_go_red_inputs(repo_root))
    assert isinstance(result, Compiled)
    commands = result.contract["verification-scope"]["commands"]
    oracle_command, whole_suite_command = commands
    assert oracle_command["executable"] == {"kind": "toolchain", "name": "go"}
    assert oracle_command["arguments"] == ["test", _GO_RED_ORACLE_FILE]
    assert whole_suite_command["executable"] == {"kind": "toolchain", "name": "go"}
    assert whole_suite_command["arguments"] == ["test", "./..."]
    assert "pytest" not in str(commands)
    assert "python" not in str(commands)


def test_red_to_green_non_python_without_cited_oracle_blocks(
    tmp_path: Path,
) -> None:
    # The `tests/test_<slug>.py` synthesis is a PYTHON convention -- for a
    # non-Python subject with no cited oracle the compiler refuses
    # (WHAT/WHY/HOW), never invents a wrong-language pytest path.
    repo_root = _build_go_red_repo(tmp_path)
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=_go_red_brief(cite_oracle=False))
    )
    assert isinstance(result, Blocked)
    assert "oracle" in result.what.lower()
    assert "::" in result.how  # the HOW teaches the path::Selector shape
    assert "test_" not in result.what  # no invented Python path leaks


def test_red_to_green_binds_a_bare_declared_oracle_target_locator(
    tmp_path: Path,
) -> None:
    # ADR-AUM-001 reproduction (2026-08-22): a RED_TO_GREEN oracle is
    # authored at a path that does not exist yet, so the authority cannot
    # cite it as `file:line` and may not have named the test function
    # either. Its bare declaration under this compiler's own typed
    # `Oracle target locator:` label IS the judgment call and binds.
    repo_root = _build_go_red_repo(tmp_path)
    brief = _go_red_brief(cite_oracle=False) + (
        f"\n   Oracle target locator: `{_GO_RED_ORACLE_FILE}` (CREATE_NEW).\n"
    )
    result = compile_delivery_contract(_go_red_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert result.contract["acceptance-tests"]["locator"] == _GO_RED_ORACLE_FILE
    assert _GO_RED_ORACLE_FILE not in result.contract["targets"]


def test_red_to_green_refusal_names_the_declaration_it_did_not_admit(
    tmp_path: Path,
) -> None:
    # GDP-3: a brief that DID declare an oracle, in a shape this compiler
    # refuses, must be told which declaration and why -- "the brief cites
    # no test/spec oracle" is a lying rejection when a declaration is
    # right there in the text.
    repo_root = _build_go_red_repo(tmp_path)
    brief = _go_red_brief(cite_oracle=False) + (
        "\n   Oracle target locator: `go-shell/drive/checkpoint.go` (EXTEND).\n"
    )
    result = compile_delivery_contract(_go_red_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "go-shell/drive/checkpoint.go" in result.what
    assert "test/spec-shaped" in result.what
    assert "Oracle target locator" in result.what


def test_red_to_green_non_python_refusal_names_the_non_python_targets(
    tmp_path: Path,
) -> None:
    # The operator cannot act on "non-Python subject" without knowing WHICH
    # target carries the non-Python extension (ADR-AUM-001: one asset
    # directory in a seven-row declared target table).
    repo_root = _build_go_red_repo(tmp_path)
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=_go_red_brief(cite_oracle=False))
    )
    assert isinstance(result, Blocked)
    for path in _GO_RED_PRODUCTION_FILES:
        assert path in result.what


def test_red_to_green_non_python_without_declared_whole_suite_blocks(
    tmp_path: Path,
) -> None:
    # No declared whole-suite command on a non-Python subject: the pytest
    # fallback would be a wrong-language invention -- refuse instead.
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=False)
    result = compile_delivery_contract(_go_red_inputs(repo_root))
    assert isinstance(result, Blocked)
    assert "whole-suite" in (result.what + result.why).lower()
    assert "pytest" not in result.what
    # The HOW's FIRST option is the authority-side declaration (ownership:
    # the authority already states the native argv); the CLAUDE.md
    # declaration is the second option, never the only one.
    assert "Verification command:" in result.how
    assert result.how.index("Verification command:") < result.how.index("CLAUDE.md")


# --- SF friction 2026-08-20 (verification-scope ownership): the cited
# authority (the sister's Slice 1 brief) already declared the exact native
# Go and Rust argv, yet `des compile-contract` exited nonzero pre-write
# demanding a duplicate `go test ./...` declaration in the subject's
# CLAUDE.md -- prose duplicated in the wrong place. A typed
# "Verification command: `<argv...>`" declaration in the authority now
# outranks the subject-CLAUDE.md fallback, same principle as the typed
# 'Oracle target locator:' declaration.


def _go_red_brief_with_verification_commands(*commands: str) -> str:
    lines = [_go_red_brief().rstrip()]
    lines += [f"Verification command: `{command}`" for command in commands]
    return "\n".join(lines) + "\n"


def test_authority_declared_verification_commands_carry_verbatim(
    tmp_path: Path,
) -> None:
    # Subject with NO CLAUDE.md whole-suite declaration: the authority's
    # own declared Go argv are carried, one command per declared line, in
    # order -- no Blocked, no re-scoping, no invented pytest.
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=False)
    brief = _go_red_brief_with_verification_commands(
        "go test ./go-shell/drive/", "go test ./..."
    )
    result = compile_delivery_contract(_go_red_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert result.contract["verification-scope"]["commands"] == [
        {
            "executable": {"kind": "toolchain", "name": "go"},
            "arguments": ["test", "./go-shell/drive/"],
        },
        {
            "executable": {"kind": "toolchain", "name": "go"},
            "arguments": ["test", "./..."],
        },
    ]


def test_authority_declaration_outranks_subject_claude_md(
    tmp_path: Path,
) -> None:
    # Both sources present: the authority's declaration WINS (precedence,
    # not merge) -- the CLAUDE.md-derived oracle/whole-suite pair is not
    # emitted alongside it.
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=True)
    brief = _go_red_brief_with_verification_commands("go test -count=1 ./...")
    result = compile_delivery_contract(_go_red_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert result.contract["verification-scope"]["commands"] == [
        {
            "executable": {"kind": "toolchain", "name": "go"},
            "arguments": ["test", "-count=1", "./..."],
        }
    ]


_RUST_ORACLE_FILE = "rust-shell/tests/verified_checkpoint_test.rs"
_RUST_ORACLE_CITATION = f"{_RUST_ORACLE_FILE}::verified_checkpoint_live"
_RUST_PRODUCTION_FILE = "rust-shell/src/verify.rs"


def test_authority_declared_rust_argv_carry_without_claude_md(
    tmp_path: Path,
) -> None:
    # The Rust half of the same SF counterexample: authority declares the
    # native cargo argv, subject has no CLAUDE.md -- the contract carries
    # the declared argv, never a Blocked.
    repo_root = tmp_path / "repo"
    (repo_root / "rust-shell" / "src").mkdir(parents=True)
    (repo_root / "rust-shell" / "tests").mkdir(parents=True)
    (repo_root / _RUST_PRODUCTION_FILE).write_text(
        "pub fn existing() {}\n", encoding="utf-8"
    )
    (repo_root / _RUST_ORACLE_FILE).write_text(
        "#[test]\nfn verified_checkpoint_live() {}\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    brief = "\n".join(
        [
            "# Architecture Brief",
            "",
            f"`{_RUST_PRODUCTION_FILE}:1` is the insertion point.",
            f"The oracle is bound as `{_RUST_ORACLE_CITATION}`.",
            "",
            "### Delivery obligations (RED_TO_GREEN)",
            "",
            "1. **PRESERVATION** -- law: existing checkpoints stay verifiable.",
            "",
            "Verification command: `cargo test --workspace`",
        ]
    )
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=brief, delivery_id="rust-checkpoint")
    )
    assert isinstance(result, Compiled)
    assert result.contract["verification-scope"]["commands"] == [
        {
            "executable": {"kind": "toolchain", "name": "cargo"},
            "arguments": ["test", "--workspace"],
        }
    ]
    assert result.contract["acceptance-tests"]["locator"] == _RUST_ORACLE_CITATION


def test_red_to_green_python_synthesis_and_pytest_fallback_unchanged(
    tmp_path: Path,
) -> None:
    # Regression pin: a Python subject with no cited oracle and no declared
    # whole-suite command keeps the historic behaviour -- synthesized
    # locator plus the direct pytest fallback command.
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.py").write_text(
        _SYNTHETIC_TARGET_MODULE, encoding="utf-8"
    )
    (repo_root / "pkg" / "tests").mkdir()
    _init_repo(repo_root)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    locator = result.contract["acceptance-tests"]["locator"]
    assert locator == "pkg/tests/test_widget_color.py"
    commands = result.contract["verification-scope"]["commands"]
    assert commands == [
        {
            "executable": {"kind": "toolchain", "name": "python"},
            "arguments": ["-m", "pytest", "-q", locator],
        }
    ]


def test_red_to_green_python_cited_oracle_wins_over_synthesis(
    tmp_path: Path,
) -> None:
    # Rule 2 is language-agnostic: an explicitly cited test/spec oracle
    # binds on a Python subject too, with or without a ::selector.
    repo_root = _build_repo(tmp_path)
    (repo_root / "pkg" / "tests" / "test_existing.py").write_text(
        "def test_existing():\n    pass\n", encoding="utf-8"
    )
    brief = _SYNTHETIC_BRIEF + (
        "\nThe oracle already sketched: `pkg/tests/test_existing.py:1`.\n"
    )
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert (
        result.contract["acceptance-tests"]["locator"] == "pkg/tests/test_existing.py"
    )
    assert "pkg/tests/test_existing.py" not in result.contract["targets"]


def test_red_to_green_word_boundary_keeps_production_files_as_targets(
    tmp_path: Path,
) -> None:
    # Review BLOCK 2026-08-20: substring test-shape discrimination made
    # `pkg/contest.go` and `pkg/latest_config.go` vanish from targets
    # (targets == {}) and bound `pkg/contest.go` as the oracle instead of
    # the brief's own explicit `::TestWidget` selector citation.
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    for name in ("contest.go", "latest_config.go"):
        (repo_root / "pkg" / name).write_text(
            "package pkg\n\nfunc Existing() {}\n", encoding="utf-8"
        )
    (repo_root / "pkg" / "widget_test.go").write_text(
        'package pkg\n\nimport "testing"\n\nfunc TestWidget(t *testing.T) {}\n',
        encoding="utf-8",
    )
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    brief = (
        "# Architecture Brief\n\n"
        "EXTEND `pkg/contest.go:12` and `pkg/latest_config.go:5`.\n\n"
        "The oracle is `pkg/widget_test.go::TestWidget`.\n\n"
        "1. **PRESERVATION** -- law: existing behaviour stays intact.\n"
    )
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=brief, delivery_id="widget-oracle")
    )
    assert isinstance(result, Compiled)
    assert set(result.contract["targets"]) == {
        "pkg/contest.go",
        "pkg/latest_config.go",
    }
    assert (
        result.contract["acceptance-tests"]["locator"]
        == "pkg/widget_test.go::TestWidget"
    )


#: Sanitized copy of the exact ADR-CFG-001 shape (auto-77a47f64fc2f70ec,
#: 2026-08-20) that produced two bare-name CREATE_NEW targets at repository
#: root AND ignored the brief's own typed target declaration, promoting two
#: explicitly out-of-scope files to EXTEND instead.
_TYPED_LOCATOR_BRIEF = """\
# ADR-CFG-001 (sanitized shape)

## Decision

Introduce one pure domain law reading both tiers through the existing
`ArtifactVersioningKernel` (`pkg/domain/artifact_versioning.py:106`), the
same kernel `DESConfig` already wires (`pkg/config/des_config.py:44`).
Wiring `DESConfig` is a follow-on adapter slice, out of this contract's
scope.

Legacy tiers today: global (`des_config.py:60`), per-repo
(`des_config.py:92`); idempotence matches the kernel's own guarantee
(`artifact_versioning.py:131`).

## Obligations for DISTILL (RED_TO_GREEN)

1. **REUSE_CANDIDATE**
   - Deferred here by design; verified by absence.
2. **CONTESTED_LAW**
   - Oracle target locator: `pkg/domain/config_merge.py::merge_config` (CREATE_NEW,
     single new pure function - no existing module owns this law).
3. **BROAD_INPUT_DOMAIN**
   - Oracle target locator: same `pkg/domain/config_merge.py::merge_config`.
"""


def _build_typed_locator_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg" / "domain").mkdir(parents=True)
    (repo_root / "pkg" / "config").mkdir(parents=True)
    (repo_root / "tests").mkdir()
    (repo_root / "pkg" / "domain" / "artifact_versioning.py").write_text(
        "class ArtifactVersioningKernel:\n    pass\n", encoding="utf-8"
    )
    (repo_root / "pkg" / "config" / "des_config.py").write_text(
        "class DESConfig:\n    pass\n", encoding="utf-8"
    )
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `pytest --noinput`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def test_typed_declared_locator_wins_over_prose_inferred_targets(
    tmp_path: Path,
) -> None:
    # ADR-CFG-001 reproduction: the declaration IS the target set -- the
    # declared CREATE_NEW file with its ::symbol binding, and NOTHING the
    # prose merely cites as evidence (both cited files are textually out
    # of this contract's scope).
    repo_root = _build_typed_locator_repo(tmp_path)
    result = compile_delivery_contract(
        _inputs(repo_root, brief_text=_TYPED_LOCATOR_BRIEF)
    )
    assert isinstance(result, Compiled)
    targets = result.contract["targets"]
    assert set(targets) == {"pkg/domain/config_merge.py"}
    target = targets["pkg/domain/config_merge.py"]
    assert target["decision"] == "CREATE_NEW"
    assert "pkg/domain/config_merge.py::merge_config" in target["overlap"]
    # Zero bare-name targets, zero undeclared EXTEND.
    assert all("/" in path for path in targets)
    assert all(plan["decision"] != "EXTEND" for plan in targets.values())


def test_bare_name_citations_fold_into_the_qualified_target_without_a_declaration(
    tmp_path: Path,
) -> None:
    # No typed declaration: inference survives, but a bare-name re-citation
    # of an already-qualified file merges as evidence, never a new target.
    repo_root = _build_repo(tmp_path)
    brief = _SYNTHETIC_BRIEF + "\nThe legacy note (`widget.py:99`) folds in.\n"
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    targets = result.contract["targets"]
    assert set(targets) == {"pkg/widget.py"}
    assert "pkg/widget.py:5" in targets["pkg/widget.py"]["overlap"]
    assert "widget.py:99" in targets["pkg/widget.py"]["overlap"]


def test_orphan_bare_name_citation_lands_in_dropped_citations_not_silence(
    tmp_path: Path,
) -> None:
    # Reviewer counterexample (GDP-6, 2026-08-20): an orphan bare-name
    # citation (zero qualified siblings sharing its basename) used to
    # VANISH from the compiled skeleton with no trace while the rest
    # compiled -- silent-wrong. It must surface in `dropped-citations`.
    repo_root = _build_repo(tmp_path)
    brief = _SYNTHETIC_BRIEF + "\nA helper note (`orphan_helper.py:12`) too.\n"
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    assert set(result.contract["targets"]) == {"pkg/widget.py"}
    dropped = result.contract["dropped-citations"]
    assert [entry["citation"] for entry in dropped] == ["orphan_helper.py:12"]
    assert all(entry["reason"] for entry in dropped)


def test_skeleton_omits_dropped_citations_when_nothing_was_dropped(
    tmp_path: Path,
) -> None:
    # The field is additive and OPTIONAL: a clean brief compiles the same
    # skeleton it always did, with no empty-list noise.
    repo_root = _build_repo(tmp_path)
    result = compile_delivery_contract(_inputs(repo_root))
    assert isinstance(result, Compiled)
    assert "dropped-citations" not in result.contract


def test_all_citations_collapsing_to_zero_targets_blocks_loud_naming_them(
    tmp_path: Path,
) -> None:
    # Every citation the brief carries is an orphan bare name: the target
    # set collapses to zero. That must be a LOUD Blocked whose WHAT names
    # the dropped citations -- never the lying "carries no file:line
    # citation" WHAT, and never a silent partial compile.
    repo_root = _build_repo(tmp_path)
    brief = """\
# Architecture Brief

## Orphans only

Change `orphan_helper.py:12` and `other_orphan.py:3`.

### Delivery obligations (RED_TO_GREEN)

1. **REPRESENTATION_CHANGE** -- law: representation gains a field.
"""
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "orphan_helper.py:12" in result.what
    assert "other_orphan.py:3" in result.what


def test_declared_extend_on_a_nonexistent_path_blocks_before_write(
    tmp_path: Path,
) -> None:
    # Reviewer counterexample 2 (2026-08-20): "Oracle target locator:
    # `path` (EXTEND)" with a path ABSENT from the base tree used to
    # compile unchecked -- reopening the class the deleted EXTEND-citation
    # validator guarded. Declared EXTEND => the path MUST exist.
    repo_root = _build_typed_locator_repo(tmp_path)
    brief = _TYPED_LOCATOR_BRIEF.replace(
        "`pkg/domain/config_merge.py::merge_config` (CREATE_NEW,",
        "`pkg/domain/config_merge.py::merge_config` (EXTEND,",
    )
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "pkg/domain/config_merge.py" in result.what
    assert "EXTEND" in result.what
    assert result.how  # HOW points at correcting the ADR/decision.


def test_declared_create_new_on_an_existing_path_blocks_before_write(
    tmp_path: Path,
) -> None:
    # Symmetric contradiction: declared CREATE_NEW on a path that ALREADY
    # exists in the base tree must block loud pre-write, never compile.
    repo_root = _build_typed_locator_repo(tmp_path)
    brief = _TYPED_LOCATOR_BRIEF.replace(
        "`pkg/domain/config_merge.py::merge_config` (CREATE_NEW,",
        "`pkg/domain/artifact_versioning.py::merge_config` (CREATE_NEW,",
    ).replace(
        "same `pkg/domain/config_merge.py::merge_config`",
        "same `pkg/domain/artifact_versioning.py::merge_config`",
    )
    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "pkg/domain/artifact_versioning.py" in result.what
    assert "CREATE_NEW" in result.what
    assert result.how


# --- SF friction 2026-08-21 (verification-authority DELEGATION): the
# sister's real Slice brief declares NO per-line "Verification command:"
# labels -- it delegates to an ADR heading whose fenced block carries the
# LITERAL clean-checkout script (assignments, command substitution, `!`
# negations, pipes -- an authority SCRIPT, never argv-splittable). The
# sister's own falsifier: `extract_declared_verification_commands` over
# that brief returns `[]`, so the campaign would stay Blocked. The typed
# "Verification authority locator: `<doc>#<anchor>`" line (same
# declarative family as 'Oracle target locator:') resolves that delegation
# BY-REFERENCE: the contract carries locator + content digest + verbatim
# lines, never an interpretation of them.


_ADR_RELATIVE_PATH = "docs/adrs/ADR-112-formal-drive-verification-substrate.md"
_ADR_HEADING = "D-112.14 — Test substrate and literal verification order"
_ADR_ANCHOR = "d-112.14-test-substrate-and-literal-verification-order"
_AUTHORITY_LOCATOR = f"{_ADR_RELATIVE_PATH}#{_ADR_ANCHOR}"

_LITERAL_SCRIPT_LINES = [
    'FORMAL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/formal.XXXXXX")"',
    'cp -R formal/agda/. "$FORMAL_TMP/"',
    '/usr/bin/agda --safe "$FORMAL_TMP/DriveLaws.agda"',
    "/usr/bin/java -cp tools/tla2tools.jar tlc2.TLC -deadlock formal/tla/Drive.tla",
    "cargo build --release --manifest-path rust-shell/Cargo.toml",
    "! nm -g rust-shell/target/release/libdrive.rlib | grep -w mock_checkpoint",
    '! rg -n "unsafe_bypass" rust-shell/src/',
    "cargo test --workspace --manifest-path rust-shell/Cargo.toml",
    "go test ./drive -count=1 -run '^TestVerifiedCheckpointLive$'",
    "go test ./... -count=1",
]


def _adr_document(*, with_heading: bool = True, with_fence: bool = True) -> str:
    lines = ["# ADR-112 — Formal drive verification substrate", ""]
    if with_heading:
        lines += [
            f"## {_ADR_HEADING}",
            "",
            "The `go test` commands run from `go-shell/`; the",
            "`cargo build --release` line is a precondition for the `nm`",
            "symbol check (release-build precondition).",
            "",
            "The exact clean-checkout verification order is:",
            "",
        ]
        if with_fence:
            lines += ["```text", *_LITERAL_SCRIPT_LINES, "```", ""]
    lines += ["## D-112.15 — A later decision", "", "More prose."]
    return "\n".join(lines) + "\n"


def _write_adr(repo_root: Path, content: str) -> None:
    path = repo_root / _ADR_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _go_red_brief_with_authority_locator(
    locator: str = _AUTHORITY_LOCATOR, *, extra_lines: tuple[str, ...] = ()
) -> str:
    lines = [
        _go_red_brief().rstrip(),
        "",
        "Verification scope is the ADR-112 D-112.14 order: the authority",
        "document owns the literal sequence; execute it verbatim.",
        f"Verification authority locator: `{locator}`",
        *extra_lines,
    ]
    return "\n".join(lines) + "\n"


def test_authority_locator_delegation_carries_the_block_by_reference(
    tmp_path: Path,
) -> None:
    import hashlib

    # No CLAUDE.md whole-suite declaration, no per-line labels: the
    # delegation alone resolves -- locator + digest + verbatim lines, and
    # the argv-shaped `commands` member is absent, never invented.
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=False)
    _write_adr(repo_root, _adr_document())
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=_go_red_brief_with_authority_locator())
    )
    assert isinstance(result, Compiled)
    scope = result.contract["verification-scope"]
    assert "commands" not in scope
    block = scope["literal-script-block"]
    assert block["locator"] == _AUTHORITY_LOCATOR
    assert block["lines"] == _LITERAL_SCRIPT_LINES
    assert (
        block["content-digest"]
        == "sha256:"
        + hashlib.sha256("\n".join(_LITERAL_SCRIPT_LINES).encode("utf-8")).hexdigest()
    )
    # The compiler never interpreted the script into argv shapes.
    assert "executable" not in str(scope)


def test_authority_locator_outranks_labels_and_subject_claude_md(
    tmp_path: Path,
) -> None:
    # All three sources present (locator delegation, per-line label,
    # CLAUDE.md whole-suite): the delegation is precedence 1 -- the
    # contract carries ONLY the literal-script-block (precedence, not
    # merge, same law as label-over-CLAUDE.md).
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=True)
    _write_adr(repo_root, _adr_document())
    brief = _go_red_brief_with_authority_locator(
        extra_lines=("Verification command: `go test ./...`",)
    )
    result = compile_delivery_contract(_go_red_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    scope = result.contract["verification-scope"]
    assert set(scope) == {"literal-script-block"}


@pytest.mark.parametrize(
    ("locator", "adr_content"),
    [
        pytest.param(_AUTHORITY_LOCATOR, None, id="doc-absent"),
        pytest.param(
            f"{_ADR_RELATIVE_PATH}#a-heading-that-does-not-exist",
            _adr_document(),
            id="heading-absent",
        ),
        pytest.param(
            _AUTHORITY_LOCATOR, _adr_document(with_fence=False), id="fence-absent"
        ),
        pytest.param(f"../outside.md#{_ADR_ANCHOR}", None, id="outside-repo"),
        pytest.param(_ADR_RELATIVE_PATH, _adr_document(), id="malformed-no-anchor"),
    ],
)
def test_unresolved_authority_reference_blocks_typed_pre_write(
    tmp_path: Path,
    locator: str,
    adr_content: str | None,
) -> None:
    # A DECLARED delegation that cannot be resolved is a typed refusal --
    # NEVER a silent fallback to the subject's CLAUDE.md (which here
    # declares a perfectly usable `go test ./...`).
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=True)
    if adr_content is not None:
        _write_adr(repo_root, adr_content)
    result = compile_delivery_contract(
        _go_red_inputs(
            repo_root, brief_text=_go_red_brief_with_authority_locator(locator)
        )
    )
    assert isinstance(result, Blocked)
    assert result.kind == "unresolved-authority-reference"
    assert locator in result.what
    assert result.why
    assert "Verification authority locator" in result.how


def test_label_and_claude_md_precedence_survive_without_a_delegation(
    tmp_path: Path,
) -> None:
    # Regression pin: a brief with NO delegation line still produces the
    # argv-shaped `commands` member exactly as before -- the new member is
    # additive, never a migration.
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=True)
    result = compile_delivery_contract(_go_red_inputs(repo_root))
    assert isinstance(result, Compiled)
    scope = result.contract["verification-scope"]
    assert set(scope) == {"commands"}
    assert len(scope["commands"]) == 2


def test_ambiguous_authority_reference_blocks_typed_naming_candidates(
    tmp_path: Path,
) -> None:
    # Sister ambiguous document 2026-08-21: a second heading whose
    # punctuation-only difference normalizes to the SAME anchor key.
    # First-match would silently bind one of the two -- the compiler must
    # refuse with the typed ambiguous class, naming both candidates.
    colliding = "D-11214 Test substrate and literal verification order"
    repo_root = _build_go_red_repo(tmp_path, with_declared_suite=False)
    content = _adr_document().replace(
        "## D-112.15 — A later decision",
        f"## {colliding}\n\n```text\nthe WRONG order\n```\n\n"
        "## D-112.15 — A later decision",
    )
    _write_adr(repo_root, content)
    result = compile_delivery_contract(
        _go_red_inputs(repo_root, brief_text=_go_red_brief_with_authority_locator())
    )
    assert isinstance(result, Blocked)
    assert result.kind == "ambiguous-authority-reference"
    assert _ADR_HEADING in result.what
    assert colliding in result.what
    assert colliding in result.how


# --- ADR-CFG-001 Amendment reproduction (2026-08-21, third same-producer
# incident): the authority declared its slice-2 target set in an explicit
# markdown "| Target | Decision | Why |" table (five rows), yet the
# compiler inferred targets from scattered prose citations instead --
# compiling two targets, one of them a file the SAME authority declared
# "REUSE as-is, no changes", and missing four of the five declared rows.
# GDP-0: the architect DECLARES, the compiler TRANSCRIBES -- when a
# declaration table is present it IS the target set; citation inference
# never applies to target selection.

_TARGET_TABLE_BRIEF = """\
# ADR-CFG-001 (sanitized amendment shape)

## Decision

One pure domain law already landed; the kernel
(`pkg/domain/artifact_versioning.py:10`) is REUSE as-is, no changes.
`pkg/config/des_config.py:44` already wires it.

## Amendment -- Slice 2: user surface wiring

### Slice 2 target set

| Target | Decision | Why |
|---|---|---|
| `pkg/config/des_config.py` | **EXTEND** | The I/O adapter boundary (`des_config.py:44-46`). |
| `tools/checks/config_ssot.py` | **CREATE_NEW** | Confirmed absent from the checks listing. |
| `tools/checks/__init__.py` | **EXTEND** | Registers the new check alongside the existing ones. |
| `scripts/docgen.py` | **EXTEND** | One new projection step in the existing generator. |
| `pkg/hooks/activation_gate.py` | **EXTEND** | Hook-side consumer of the merged enabled value. |

### Reuse survey (slice 2)

| Candidate | Location | Verdict |
|---|---|---|
| `merge_config` | `pkg/domain/config_merge.py` (slice 1, delivered) | REUSE as-is, unmodified. |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: `merge_config` is reused verbatim.
"""

_TABLE_EXTEND_TARGETS = (
    "pkg/config/des_config.py",
    "tools/checks/__init__.py",
    "scripts/docgen.py",
    "pkg/hooks/activation_gate.py",
)


def _build_table_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    for existing in (
        *_TABLE_EXTEND_TARGETS,
        "pkg/domain/artifact_versioning.py",
        "pkg/domain/config_merge.py",
    ):
        path = repo_root / existing
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# existing module\n", encoding="utf-8")
    (repo_root / "tests").mkdir()
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `pytest --noinput`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def _table_inputs(repo_root: Path, **overrides: object) -> CompileContractInputs:
    fields: dict[str, object] = {
        "brief_text": _TARGET_TABLE_BRIEF,
        "delivery_id": "config-ssot-slice-2",
    }
    fields.update(overrides)
    return _inputs(repo_root, **fields)


def test_declared_target_table_is_the_exact_target_set(tmp_path: Path) -> None:
    # The table's five rows -- and NOTHING else: not the REUSE-as-is
    # kernel the prose cites, not the reuse-survey file, no inferred
    # extras. Decisions transcribed per row.
    repo_root = _build_table_repo(tmp_path)
    result = compile_delivery_contract(_table_inputs(repo_root))
    assert isinstance(result, Compiled)
    targets = result.contract["targets"]
    assert set(targets) == {*_TABLE_EXTEND_TARGETS, "tools/checks/config_ssot.py"}
    assert targets["tools/checks/config_ssot.py"]["decision"] == "CREATE_NEW"
    for extend_path in _TABLE_EXTEND_TARGETS:
        assert targets[extend_path]["decision"] == "EXTEND"
    # The forbidden file citation inference used to promote to EXTEND:
    assert "pkg/domain/artifact_versioning.py" not in targets
    assert "pkg/domain/config_merge.py" not in targets
    # Schema floor: overlap is nonEmptyText for every declared target,
    # including rows with zero prose citations of their own.
    assert all(plan["overlap"] for plan in targets.values())
    # The out-of-set citation surfaces in dropped-citations, never silence.
    dropped = result.contract["dropped-citations"]
    assert any(
        "pkg/domain/artifact_versioning.py:10" in entry["citation"] for entry in dropped
    )
    assert all(entry["reason"] for entry in dropped)


def test_declared_target_table_outranks_a_stale_typed_locator_line(
    tmp_path: Path,
) -> None:
    # Incident 1 of the same day: a historical slice-1 typed locator line
    # left in the authority produced a single stale target. With a table
    # present, the table is the COMPLETE declared set -- the stale typed
    # declaration is surfaced as dropped evidence, never a target.
    repo_root = _build_table_repo(tmp_path)
    brief = _TARGET_TABLE_BRIEF + (
        "\nHistorical: Oracle target locator: "
        "`pkg/domain/config_merge.py::merge_config` (CREATE_NEW, slice 1).\n"
    )
    result = compile_delivery_contract(_table_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Compiled)
    targets = result.contract["targets"]
    assert "pkg/domain/config_merge.py" not in targets
    assert set(targets) == {*_TABLE_EXTEND_TARGETS, "tools/checks/config_ssot.py"}
    dropped = result.contract["dropped-citations"]
    assert any(
        "pkg/domain/config_merge.py::merge_config" in entry["citation"]
        for entry in dropped
    )


def test_two_declared_target_tables_block_loud(tmp_path: Path) -> None:
    # Two matching declaration tables are an ambiguity -- refused loud
    # with WHAT/WHY/HOW, never one silently picked.
    repo_root = _build_table_repo(tmp_path)
    second_table = (
        "\n### Another target set\n\n"
        "| Target | Decision | Why |\n"
        "|---|---|---|\n"
        "| `scripts/docgen.py` | **EXTEND** | Duplicate declaration. |\n"
    )
    result = compile_delivery_contract(
        _table_inputs(repo_root, brief_text=_TARGET_TABLE_BRIEF + second_table)
    )
    assert isinstance(result, Blocked)
    assert "2" in result.what
    assert "Decision" in result.what
    assert result.why
    assert result.how


def test_target_table_decision_outside_vocabulary_blocks_loud(
    tmp_path: Path,
) -> None:
    # A Decision cell outside EXTEND|CREATE_NEW cannot be transcribed --
    # refused loud, never guessed or skipped.
    repo_root = _build_table_repo(tmp_path)
    brief = _TARGET_TABLE_BRIEF.replace(
        "| `scripts/docgen.py` | **EXTEND** |", "| `scripts/docgen.py` | **REUSE** |"
    )
    result = compile_delivery_contract(_table_inputs(repo_root, brief_text=brief))
    assert isinstance(result, Blocked)
    assert "REUSE" in result.what
    assert "scripts/docgen.py" in result.what
    assert result.how


def test_target_table_rows_keep_the_existing_grounding_validation(
    tmp_path: Path,
) -> None:
    # The declaration is still GROUNDED against the base tree: a tabled
    # CREATE_NEW on a file that already exists blocks pre-write, exactly
    # as the typed-locator path already does.
    repo_root = _build_table_repo(tmp_path)
    (repo_root / "tools" / "checks" / "config_ssot.py").write_text(
        "# already exists\n", encoding="utf-8"
    )
    result = compile_delivery_contract(_table_inputs(repo_root))
    assert isinstance(result, Blocked)
    assert "tools/checks/config_ssot.py" in result.what
    assert "CREATE_NEW" in result.what
    assert result.how


# --- declared-imports provenance (Q-90/Q-91 acceptance law, 2026-08-21) -----
#
# SF mechanically falsified the whole-word TEXT grounding of non-Python
# declared-imports: a symbol occurring only in a COMMENT or a STRING
# LITERAL was admitted as existing. The law: a candidate is existing ONLY
# when it is among the target file's atoms resolved through the CodeFact
# port at binding-resolved provenance; any noisy/failed/unsupported
# resolution yields an honest empty admission. The decision reads the
# resolution ENVELOPE (confidence), never the payload's shape alone.

import json

from des.ports.code_fact_port import (
    Answered,
    CodeFactResult,
    Failed,
    TraceEntry,
    Unsupported,
)


_ONE_ROW_BRIEF = (
    "| Target | Existing | Decision |\n"
    "| --- | --- | --- |\n"
    "| `pkg/store.go` | `ExistingStore` | Extend with `FutureSnapshot` |\n"
)


def _seed_go_store(repo_root: Path, content: str) -> None:
    (repo_root / "pkg").mkdir(parents=True, exist_ok=True)
    (repo_root / "pkg" / "store.go").write_text(content, encoding="utf-8")


def _seed_graphify_out(repo_root: Path, relative: str, atoms: list[str]) -> None:
    """A minimal, FRESH graphify-out pair: the graph declares exactly
    ``atoms`` for ``relative``, and the manifest records the file's
    current mtime (the adapter's exact-equality freshness witness)."""
    out = repo_root / "graphify-out"
    out.mkdir()
    nodes = [
        {"id": f"n{index}", "label": atom, "source_file": relative}
        for index, atom in enumerate(atoms)
    ]
    (out / "graph.json").write_text(
        json.dumps({"nodes": nodes, "edges": []}), encoding="utf-8"
    )
    mtime = (repo_root / relative).stat().st_mtime
    (out / "manifest.json").write_text(
        json.dumps({relative: {"mtime": mtime}}), encoding="utf-8"
    )


def test_grounded_admission_excludes_a_comment_and_string_occurrence(
    tmp_path: Path,
) -> None:
    """The SF one-row canonical: `pkg/store.go` DECLARES only
    `ExistingStore` but mentions `FutureSnapshot` in a comment AND a
    string literal; the authority's one row cites both. Only the atom is
    admitted -- textual presence is not existence."""
    _seed_go_store(
        tmp_path,
        "package pkg\n\n"
        "// FutureSnapshot arrives with this delivery.\n"
        "type ExistingStore struct{}\n\n"
        'var doc = "FutureSnapshot"\n',
    )
    _seed_graphify_out(tmp_path, "pkg/store.go", ["ExistingStore"])
    assert declared_imports_for_target(
        tmp_path,
        "pkg/store.go",
        _ONE_ROW_BRIEF,
        target_atoms=target_atoms_resolver(tmp_path),
    ) == ["ExistingStore"]


def test_grounded_admission_excludes_a_comment_only_occurrence(
    tmp_path: Path,
) -> None:
    _seed_go_store(
        tmp_path,
        "package pkg\n\n"
        "// FutureSnapshot arrives with this delivery.\n"
        "type ExistingStore struct{}\n",
    )
    _seed_graphify_out(tmp_path, "pkg/store.go", ["ExistingStore"])
    assert declared_imports_for_target(
        tmp_path,
        "pkg/store.go",
        _ONE_ROW_BRIEF,
        target_atoms=target_atoms_resolver(tmp_path),
    ) == ["ExistingStore"]


def test_grounded_admission_excludes_a_string_literal_only_occurrence(
    tmp_path: Path,
) -> None:
    _seed_go_store(
        tmp_path,
        'package pkg\n\ntype ExistingStore struct{}\n\nvar doc = "FutureSnapshot"\n',
    )
    _seed_graphify_out(tmp_path, "pkg/store.go", ["ExistingStore"])
    assert declared_imports_for_target(
        tmp_path,
        "pkg/store.go",
        _ONE_ROW_BRIEF,
        target_atoms=target_atoms_resolver(tmp_path),
    ) == ["ExistingStore"]


def test_unreliable_provenance_yields_an_honest_empty_admission(
    tmp_path: Path,
) -> None:
    """No graphify-out data: the chain degrades to the textual floor
    (noisy) for a Go target -- a text scan WOULD find both symbols, but
    a noisy envelope never admits. Honest empty list, never a textual
    admission."""
    _seed_go_store(
        tmp_path,
        "package pkg\n\ntype ExistingStore struct{}\n",
    )
    assert (
        declared_imports_for_target(
            tmp_path,
            "pkg/store.go",
            _ONE_ROW_BRIEF,
            target_atoms=target_atoms_resolver(tmp_path),
        )
        == []
    )


def test_a_missing_target_file_grounds_nothing(tmp_path: Path) -> None:
    # A symbol cannot pre-exist in a file that does not.
    assert target_atoms_resolver(tmp_path)("pkg/store.go") == frozenset()


def _answered_atoms(confidence: str, atoms: list[str]) -> Answered:
    payload = {"atoms": atoms, "unparseable": False}
    return Answered(
        provider_id="probe",
        confidence=confidence,
        payload=CodeFactResult(
            provider="probe", confidence=confidence, payload=payload
        ),
        trace=(
            TraceEntry(
                provider_id="probe",
                event="answered",
                scope="complete",
                fault_count=0,
                exemplars=(),
                detail="",
            ),
        ),
    )


def test_binding_resolved_atoms_decides_on_the_envelope_not_the_payload() -> None:
    # An identically-shaped atoms payload is admitted at binding-resolved
    # and refused at noisy/approx -- the confidence label IS the decision.
    assert binding_resolved_atoms(
        _answered_atoms("binding-resolved", ["ExistingStore"])
    ) == frozenset({"ExistingStore"})
    assert binding_resolved_atoms(_answered_atoms("noisy", ["ExistingStore"])) == (
        frozenset()
    )
    assert binding_resolved_atoms(_answered_atoms("approx", ["ExistingStore"])) == (
        frozenset()
    )


def test_binding_resolved_atoms_refuses_failed_and_unsupported() -> None:
    failed = Failed(
        cause="provider-error",
        trace=(
            TraceEntry(
                provider_id="probe",
                event="failed:provider-error",
                scope="complete",
                fault_count=1,
                exemplars=(),
                detail="",
            ),
        ),
    )
    unsupported = Unsupported(
        capability_id="query.atoms-in-file", consulted=(), trace=()
    )
    assert binding_resolved_atoms(failed) == frozenset()
    assert binding_resolved_atoms(unsupported) == frozenset()


# --- Reject-all-at-once (Ale, 2026-08-22). A validator that stops at the
# FIRST problem charges the caller N producer round-trips where one would
# do: on ADR-AUM-001 (2026-08-22) `des compile-contract` produced THREE
# sequential refusals, each costing a full architect consult, and on
# ADR-CFG-001 (2026-08-21) four. Every INDEPENDENT authority check now
# runs in ONE pass and every problem it found is reported together; a
# check that DEPENDS on a failed one stays sequential but is DECLARED
# unrun, never silently omitted (GDP-6: the third state reaches the
# aggregate).

_MULTI_DEFECT_BRIEF = """\
# Architecture Brief

## Registry gains a route

| Target | Decision | Why |
|---|---|---|
| `pkg/widget.go Registry tuple` | **EXTEND** | A SYMBOL where a path belongs. |
| `pkg/registry.go` | **CREATE_NEW** | Declared new, but the file exists. |
| `pkg/widget.go` | **EXTEND** | The real seam. |

### Delivery obligations (RED_TO_GREEN)

1. **REPRESENTATION_CHANGE** -- law: the route representation gains a field.
"""


def _build_multi_defect_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.go").write_text(_GO_TARGET_MODULE, encoding="utf-8")
    (repo_root / "pkg" / "registry.go").write_text(_GO_TARGET_MODULE, encoding="utf-8")
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
    )
    _init_repo(repo_root)
    return repo_root


def test_three_independent_authority_defects_are_all_reported_in_one_pass(
    tmp_path: Path,
) -> None:
    # RED on the pre-2026-08-22 compiler: it returned the FIRST refusal
    # (the ungrounded EXTEND) and the architect learned of the other two
    # only after two more full consult->compile round-trips.
    repo_root = _build_multi_defect_repo(tmp_path)

    result = compile_delivery_contract(
        _inputs(repo_root, brief_text=_MULTI_DEFECT_BRIEF)
    )

    assert isinstance(result, Blocked)
    whats = [problem.what for problem in result.problems]
    assert len(whats) == 3, whats
    joined = " || ".join(whats)
    assert "pkg/widget.go Registry tuple" in joined  # (1) symbol, not a path
    assert "EXTEND" in joined
    assert "pkg/registry.go" in joined  # (2) CREATE_NEW on an existing file
    assert "CREATE_NEW" in joined
    assert "non-Python subject" in joined  # (3) no oracle cited
    # Every problem carries its OWN complete WHAT/WHY/HOW -- a numbered
    # block is only useful if each block is independently actionable.
    for problem in result.problems:
        assert problem.what and problem.why and problem.how


def test_a_single_defect_still_yields_exactly_one_problem_and_no_unrun_noise(
    tmp_path: Path,
) -> None:
    # No readability regression for the single-problem case: one problem,
    # nothing declared unrun, the same WHAT/WHY/HOW as before.
    repo_root = _build_repo(tmp_path)
    brief = _SYNTHETIC_BRIEF.replace("1. **REUSE_CANDIDATE**", "1. REUSE_CANDIDATE")
    brief = brief.replace("2. **REPRESENTATION_CHANGE**", "2. REPRESENTATION_CHANGE")

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Blocked)
    assert len(result.problems) == 1
    assert result.also == ()
    assert result.not_run == ()
    assert "obligation" in result.what


def test_a_check_that_could_not_run_is_declared_never_silently_omitted(
    tmp_path: Path,
) -> None:
    # GDP-6, third state reaches the aggregate: two target-declaration
    # tables leave the declared target set unknown, so target grounding
    # and every oracle/verification check decided FROM that set could not
    # run. The report says so, by name, with the reason.
    repo_root = _build_repo(tmp_path)
    brief = (
        _SYNTHETIC_BRIEF
        + """
| Target | Decision | Why |
|---|---|---|
| `pkg/widget.py` | **EXTEND** | First declaration. |

Prose between the two tables.

| Target | Decision | Why |
|---|---|---|
| `pkg/other.py` | **CREATE_NEW** | Second, contradicting declaration. |
"""
    )

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Blocked)
    assert len(result.problems) == 1
    assert "target-declaration tables" in result.what
    declared = " || ".join(
        f"{entry.check} -- {entry.because}" for entry in result.not_run
    )
    assert "target grounding" in declared
    assert "oracle" in declared
    assert "verification-scope" in declared
    for entry in result.not_run:
        assert entry.check and entry.because


def test_every_bad_row_of_one_target_table_is_reported_in_the_same_pass(
    tmp_path: Path,
) -> None:
    # Table-level problems belong to the same family: a decision outside
    # the closed vocabulary and a duplicated path are INDEPENDENT of each
    # other, so one pass reports both.
    repo_root = _build_repo(tmp_path)
    brief = (
        _SYNTHETIC_BRIEF
        + """
| Target | Decision | Why |
|---|---|---|
| `pkg/widget.py` | **REUSE** | Outside the closed vocabulary. |
| `pkg/other.py` | **CREATE_NEW** | Fine. |
| `pkg/other.py` | **CREATE_NEW** | Declared twice. |
"""
    )

    result = compile_delivery_contract(_inputs(repo_root, brief_text=brief))

    assert isinstance(result, Blocked)
    joined = " || ".join(problem.what for problem in result.problems)
    assert "REUSE" in joined
    assert "twice" in joined
