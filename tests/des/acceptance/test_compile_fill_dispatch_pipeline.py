"""Run-13-brief acceptance test: the full construction pipeline, end to end
(Ale's construction-over-file correction, 2026-08-20).

`des compile-contract` -> ATD fills EACH semantic field via its own `des
fill-contract` Bash call, writes ONLY the oracle -> `des dispatch` reports
ZERO content defects. Every step runs the real installed CLI in-process
(never a hand-typed contract, never an intermediate fill file), proving
the construction closes the exact gap the Agda vacuity report
(`~/nwave-formal/2026-08-19-gates/report/2026-08-19-gate-analysis.md`)
named as blocking removal of the three now-deleted `des dispatch`
validators: "a hand-typed contract... gets NONE of this protection" --
here, nothing is hand-typed, and no intermediate JSON artifact -- itself a
representable wrong state -- ever exists at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


def _run(
    command: str, *args: str, cwd: Path, stdin: str | None = None
) -> tuple[int, str, str]:
    return run_cli_in_process([command, *args], cwd=cwd, stdin_text=stdin)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    )


_TARGET_MODULE = '''\
"""A tiny stand-in production module."""


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

_ARCH_AUTHORITY = "ARCHITECTURE-COVERED: docs/product/architecture/brief.md#widget"


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "pkg" / "widget.py").write_text(_TARGET_MODULE, encoding="utf-8")
    (repo_root / "pkg" / "tests").mkdir()
    (repo_root / "pkg" / "tests" / "__init__.py").write_text("", encoding="utf-8")
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


_ORACLE_BODY = """\
from pkg.widget import ColorValidator


def test_color_validator_rejects_an_invalid_color():
    assert ColorValidator("not-a-color") is None
"""


def test_compile_fill_dispatch_reports_zero_content_defects(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)

    # 1. Compile: the schema-shaped skeleton, no semantic field guessed.
    code, out, err = _run(
        "compile-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        "--examine",
        "false",
        cwd=repo_root,
    )
    assert code == 0, err
    assert (
        "DELIVERY-CONTRACT-SKELETON: docs/delivery-contracts/widget-color.json" in out
    )
    oracle_locator = next(
        line.removeprefix("ORACLE-LOCATOR: ")
        for line in out.splitlines()
        if line.startswith("ORACLE-LOCATOR: ")
    )

    # 2. ATD's entire authoring surface: one `des fill-contract` Bash call
    # per semantic field, plus the oracle -- never a Write/Edit on the
    # contract path, never an intermediate file.
    code, out, err = _run(
        "fill-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--field",
        "outcome",
        cwd=repo_root,
        stdin="Widget gains a validated color attribute.\n",
    )
    assert code == 0, err
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out

    code, out, err = _run(
        "fill-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/widget.py",
        "--field",
        "justification",
        cwd=repo_root,
        stdin=(
            "Widget gains a new ColorValidator helper "
            "(pkg/widget.py:5, insertion point).\n"
        ),
    )
    assert code == 0, err

    for boundary_field, value in (
        ("boundary.failure-behavior", "An invalid color value is rejected."),
        ("boundary.substrate-lie", "Nothing lies here -- a real validator call."),
        ("boundary.substrate-probe", "Assert the rejection raises ValueError."),
        ("boundary.double-blind-spot", "None known for this small a change."),
    ):
        code, out, err = _run(
            "fill-contract",
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            "widget-color",
            "--target",
            "pkg/widget.py",
            "--field",
            boundary_field,
            cwd=repo_root,
            stdin=f"{value}\n",
        )
        assert code == 0, err

    assert "CONTRACT-FILL-STATUS: COMPLETE" in out

    # Confirmable independently too, matching the ATD skill's own
    # "quote the CLI fact" terminal-handoff discipline.
    code, out, err = _run(
        "fill-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=repo_root,
    )
    assert code == 0, err
    assert out.strip() == "CONTRACT-FILL-STATUS: COMPLETE"

    oracle_path = repo_root / oracle_locator
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.write_text(_ORACLE_BODY, encoding="utf-8")

    # 3. Dispatch: zero content defects -- no "WHAT:" refusal at all.
    code, out, err = _run(
        "dispatch",
        "--repo-root",
        str(repo_root),
        "--delivery-contract",
        "docs/delivery-contracts/widget-color.json",
        cwd=repo_root,
    )
    assert code == 0, err
    assert "WHAT:" not in err
    assert out.startswith(
        "THIN-DELIVERY-CONTRACT: docs/delivery-contracts/widget-color.json"
    )
    assert "THIN-DELIVERY-CONTRACT-DIGEST: sha256:" in out
