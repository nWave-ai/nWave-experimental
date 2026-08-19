"""CLI acceptance tests for `des compile-contract`
(ADR-SSOT-002 Section 4/4b item 1)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


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
