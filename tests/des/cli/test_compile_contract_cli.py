"""CLI acceptance tests for `des compile-contract`
(ADR-SSOT-002 Section 4/4b item 1)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from des._internal.delivery_contract_schema import (
    delivery_contract_schema_violation,
)


def _run(*args: str, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["compile-contract", *args], cwd=cwd)


_TARGET_MODULE = '''\
"""A tiny stand-in production module."""
from thirdpartylib import Helper


class Widget:
    def existing_method(self):
        return None
'''

_BRIEF = """\
# Architecture Brief

`Widget` (`pkg/widget.py:5`) already exposes `existing_method`
(`pkg/widget.py:6`).

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    )


def _build_repo(tmp_path: Path, *, with_tests_dir: bool = True) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.py").write_text(_TARGET_MODULE, encoding="utf-8")
    if with_tests_dir:
        (repo_root / "pkg" / "tests").mkdir()
    (repo_root / "docs" / "product" / "architecture").mkdir(parents=True)
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        _BRIEF, encoding="utf-8"
    )
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")
    return repo_root


_ARCH_AUTHORITY = "ARCHITECTURE-COVERED: docs/product/architecture/brief.md#widget"


def test_writes_a_schema_shaped_skeleton(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )
    assert code == 0, err
    assert (
        "DELIVERY-CONTRACT-SKELETON: docs/delivery-contracts/widget-color.json" in out
    )
    assert "ORACLE-LOCATOR: pkg/tests/test_widget_color.py" in out

    contract_path = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["delivery-id"] == "widget-color"
    assert contract["schema-version"] == "1.2"
    assert contract["delivery-route"] == "RED_TO_GREEN"
    assert set(contract["targets"]) == {"pkg/widget.py"}
    assert contract["acceptance-tests"]["locator"] == "pkg/tests/test_widget_color.py"
    # No ARCHITECTURE_BOUNDARY_CHANGE obligation and no override -> False.
    assert contract["applicability"]["independent-review"] is False


def test_independent_review_flag_overrides_the_obligations_proxy(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        "--independent-review",
        "true",
        cwd=repo_root,
    )
    assert code == 0, err
    contract_path = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["applicability"]["independent-review"] is True


def test_refuses_when_no_test_directory_convention_is_discoverable(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path, with_tests_dir=False)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )
    assert code != 0
    assert "test-directory convention" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_refuses_when_contract_already_exists(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    args = (
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
    )
    first = _run(*args, cwd=repo_root)
    assert first[0] == 0
    code, _out, err = _run(*args, cwd=repo_root)
    assert code != 0
    assert "already exists" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_refuses_relative_repo_root(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        ".",
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )
    assert code != 0
    assert "absolute" in err


def test_refuses_malformed_delivery_id(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "Not_Kebab",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )
    assert code != 0
    assert "schema-shaped" in err


def test_refuses_malformed_architecture_authority(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        "not-a-path-anchor",
        cwd=repo_root,
    )
    assert code != 0
    assert "path#anchor" in err or "well-formed" in err


def test_refuses_unreadable_brief(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        "ARCHITECTURE-COVERED: docs/product/architecture/missing.md#widget",
        cwd=repo_root,
    )
    assert code != 0
    assert "cannot be read" in err


def test_refuses_missing_required_flag(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run("--repo-root", str(repo_root), cwd=repo_root)
    assert code != 0
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


# --- Reject-all-at-once rendering (Ale, 2026-08-22): a multi-problem
# refusal leads with HOW MANY, then one numbered block per problem, each
# carrying its own WHAT/WHY/HOW. Exit code unchanged.

_GO_MODULE = "package pkg\n\nfunc Existing() {}\n"

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
    (repo_root / "pkg" / "widget.go").write_text(_GO_MODULE, encoding="utf-8")
    (repo_root / "pkg" / "registry.go").write_text(_GO_MODULE, encoding="utf-8")
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `go test ./...`\n", encoding="utf-8"
    )
    (repo_root / "docs" / "product" / "architecture").mkdir(parents=True)
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        _MULTI_DEFECT_BRIEF, encoding="utf-8"
    )
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")
    return repo_root


def _multi_defect_run(tmp_path: Path, command: str) -> tuple[int, str, str]:
    repo_root = _build_multi_defect_repo(tmp_path)
    return run_cli_in_process(
        [
            command,
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            "widget-color",
            "--architecture-authority",
            _ARCH_AUTHORITY,
        ],
        cwd=repo_root,
    )


def test_compile_contract_reports_every_problem_numbered_in_one_refusal(
    tmp_path: Path,
) -> None:
    code, _out, err = _multi_defect_run(tmp_path, "compile-contract")

    assert code == 2, err
    assert "BLOCKED: 3 problems" in err
    assert "(1/3) WHAT:" in err
    assert "(2/3) WHAT:" in err
    assert "(3/3) WHAT:" in err
    assert err.count("WHY:") == 3
    assert err.count("HOW:") == 3
    assert "NOT CHECKED:" in err


def test_recompile_contract_renders_the_same_multi_problem_refusal(
    tmp_path: Path,
) -> None:
    # The twin producer path shares the ONE renderer -- never a copy.
    repo_root = _build_multi_defect_repo(tmp_path)
    contract = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    contract.parent.mkdir(parents=True)
    contract.write_text('{"targets": {}}\n', encoding="utf-8")

    code, _out, err = run_cli_in_process(
        [
            "recompile-contract",
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            "widget-color",
            "--architecture-authority",
            _ARCH_AUTHORITY,
        ],
        cwd=repo_root,
    )

    assert code == 2, err
    assert "BLOCKED: 3 problems" in err
    assert "(3/3) WHAT:" in err


def test_a_single_problem_refusal_stays_the_one_line_it_has_always_been(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path, with_tests_dir=False)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 2
    assert "BLOCKED:" not in err
    assert "(1/" not in err
    assert err.strip().count("\n") == 0
    assert err.startswith("WHAT:")


_BRIEF_DIRECTORY_TARGET_CELL = """\
# Architecture Brief

`Widget` (`pkg/widget.py:5`) already exposes `existing_method`
(`pkg/widget.py:6`).

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/newdir/` | **CREATE_NEW** |

Oracle target locator: `pkg/tests/test_widget_color.py`

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""


def _write_brief(repo_root: Path, brief_text: str) -> None:
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        brief_text, encoding="utf-8"
    )


def test_a_directory_target_cell_is_refused_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """GDP-0, third occurrence of the class (Ale, 2026-08-22): this
    compiler wrote its skeleton unvalidated, so a Target cell naming a
    DIRECTORY where the schema admits only a FILE was transcribed verbatim
    into a contract no version of the schema has ever accepted -- it
    reached the trunk and went red in CI. Grounding did not stop it:
    ``is_file`` is False for EVERY non-file, directories included."""
    repo_root = _build_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_DIRECTORY_TARGET_CELL)

    code, out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 2, out
    assert "schema-invalid-skeleton" in err
    # The WHAT names the failing node and the offending value.
    assert "/targets/pkg/newdir//candidate" in err
    assert "'pkg/newdir/'" in err
    # The HOW names the AUTHORITY DOCUMENT and the CELL to correct --
    # a reader must know which row of the ADR is wrong, not merely that
    # the JSON does not validate.
    assert "the Target cell of the row declaring 'pkg/newdir/'" in err
    assert "target-declaration table" in err
    assert "docs/product/architecture/brief.md#widget" in err
    # Nothing was written: the invalid state is unrepresentable on disk.
    assert not (
        repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    ).exists()


def test_a_valid_authority_still_compiles_a_schema_valid_skeleton(
    tmp_path: Path,
) -> None:
    """The pre-write validation must not reject the good case: a
    validation that refuses valid input is worse than the defect."""
    repo_root = _build_repo(tmp_path)
    code, out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 0, err
    assert "DELIVERY-CONTRACT-SKELETON:" in out
    contract_path = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert delivery_contract_schema_violation(contract) is None
