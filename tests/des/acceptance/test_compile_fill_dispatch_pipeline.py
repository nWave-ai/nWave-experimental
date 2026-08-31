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

import json
import subprocess
from pathlib import Path

import pytest

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

#: Top-level heading doubles as the section `_ARCH_AUTHORITY` cites
#: (`#widget`) -- des compile-contract now derives every fact from the
#: CITED SECTION alone (F-COMPILE-CONTRACT-IGNORES-AUTHORITY-ANCHOR), so
#: the anchor must resolve to a real heading, never a shape-only string.
_BRIEF = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) already exposes `existing_method`
(`pkg/widget.py:6`).

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_ARCH_AUTHORITY = "ARCHITECTURE-COVERED: docs/product/architecture/brief.md#widget"


def _build_repo(tmp_path: Path, *, brief: str = _BRIEF) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "pkg" / "widget.py").write_text(_TARGET_MODULE, encoding="utf-8")
    (repo_root / "pkg" / "tests").mkdir()
    (repo_root / "pkg" / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "CLAUDE.md").write_text(
        "- Run the whole suite: `python3 -c 'pass' test`\n", encoding="utf-8"
    )
    (repo_root / "docs" / "product" / "architecture").mkdir(parents=True)
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        brief, encoding="utf-8"
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


@pytest.mark.parametrize("with_support", [False, True])
def test_compile_fill_dispatch_reports_zero_content_defects(
    tmp_path: Path, with_support: bool
) -> None:
    support_locators = ["spec/Widget.tla", "tests/support/widget.json"]
    brief = _BRIEF
    if with_support:
        brief += "\n" + "\n".join(
            f"Acceptance support locator: `{locator}`" for locator in support_locators
        )
        brief += "\n"
    repo_root = _build_repo(tmp_path, brief=brief)

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
    compiled = json.loads(
        (repo_root / "docs" / "delivery-contracts" / "widget-color.json").read_text(
            encoding="utf-8"
        )
    )
    assert compiled["schema-version"] == ("1.4" if with_support else "1.3")

    # 2. ATD publishes all semantic facts in one atomic batch.
    batch = [
        {"field": "outcome", "value": "Widget gains a validated color attribute."},
        {
            "field": "justification",
            "target": "pkg/widget.py",
            "value": "Widget gains a new ColorValidator helper (pkg/widget.py:5, insertion point).",
        },
        {
            "field": "boundary.failure-behavior",
            "target": "pkg/widget.py",
            "value": "An invalid color value is rejected.",
        },
        {
            "field": "boundary.substrate-lie",
            "target": "pkg/widget.py",
            "value": "Nothing lies here -- a real validator call.",
        },
        {
            "field": "boundary.substrate-probe",
            "target": "pkg/widget.py",
            "value": "Assert the rejection raises ValueError.",
        },
        {
            "field": "boundary.double-blind-spot",
            "target": "pkg/widget.py",
            "value": "None known for this small a change.",
        },
    ]
    code, out, err = _run(
        "fill-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=repo_root,
        stdin=json.dumps(batch),
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
    for locator in support_locators if with_support else []:
        support_path = repo_root / locator
        support_path.parent.mkdir(parents=True, exist_ok=True)
        support_path.write_text(f"support:{locator}\n", encoding="utf-8")
    # The construction fixture must name a base-runnable preservation vector.
    compiled = json.loads(
        (repo_root / "docs/delivery-contracts" / "widget-color.json").read_text(
            encoding="utf-8"
        )
    )
    compiled["verification-scope"] = {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "python3"},
                "arguments": ["-c", "pass", "test"],
            }
        ]
    }
    (repo_root / "docs/delivery-contracts" / "widget-color.json").write_text(
        json.dumps(compiled), encoding="utf-8"
    )

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


def test_native_go_primary_and_distinct_support_compile_fill_dispatch(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "go-repo"
    (repo_root / "pkg").mkdir(parents=True)
    (repo_root / "pkg" / "widget.go").write_text(
        "package widget\n\nfunc Existing() {}\n", encoding="utf-8"
    )
    (repo_root / "pkg" / "widget_test.go").write_text(
        'package widget\n\nimport "testing"\n\nfunc TestWidgetColor(t *testing.T) {}\n',
        encoding="utf-8",
    )
    (repo_root / "go.mod").write_text(
        "module example.invalid/widget\n\ngo 1.22\n", encoding="utf-8"
    )
    (repo_root / "CLAUDE.md").write_text(
        "- Run the whole suite: `go test ./...`\n", encoding="utf-8"
    )
    (repo_root / "docs" / "product" / "architecture").mkdir(parents=True)
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        """\
# widget

Paradigm: object_oriented

`pkg/widget.go:3` exposes `Existing` as the extension seam.
The acceptance oracle is `pkg/widget_test.go::TestWidgetColor`.

Acceptance support locator: `spec/widget.tla`
Verification command: `go test pkg/widget_test.go`
Verification command: `go test ./...`

### Delivery obligations (RED_TO_GREEN)

1. **PRESERVATION** -- law: existing widget behavior remains available.
""",
        encoding="utf-8",
    )
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")

    code, out, err = _run(
        "compile-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-go-color",
        "--architecture-authority",
        "ARCHITECTURE-COVERED: docs/product/architecture/brief.md#widget",
        "--examine",
        "false",
        cwd=repo_root,
    )
    assert code == 0, err
    oracle_locator = next(
        line.removeprefix("ORACLE-LOCATOR: ")
        for line in out.splitlines()
        if line.startswith("ORACLE-LOCATOR: ")
    )

    contract_relative = "docs/delivery-contracts/widget-go-color.json"
    contract_path = repo_root / contract_relative
    compiled = json.loads(contract_path.read_text(encoding="utf-8"))
    assert compiled["schema-version"] == "1.4"
    assert oracle_locator == "pkg/widget_test.go::TestWidgetColor"
    assert compiled["acceptance-tests"] == {
        "locator": "pkg/widget_test.go::TestWidgetColor",
        "supporting-locators": ["spec/widget.tla"],
    }
    commands = compiled["verification-scope"]["commands"]
    assert [command["executable"] for command in commands] == [
        {"kind": "toolchain", "name": "go"},
        {"kind": "toolchain", "name": "go"},
    ]
    assert "python" not in json.dumps(commands).lower()
    assert "pytest" not in json.dumps(commands).lower()

    batch = []
    for field, value in (
        ("outcome", "Widget gains native Go color validation."),
        (
            "justification",
            "Extend the existing Go seam at pkg/widget.go:3 without replacement.",
        ),
        ("boundary.failure-behavior", "Invalid colors are rejected."),
        ("boundary.substrate-lie", "The real Go package is exercised."),
        ("boundary.substrate-probe", "Run the native Go oracle."),
        ("boundary.double-blind-spot", "No additional blind spot is known."),
    ):
        entry = {"field": field, "value": value}
        if field != "outcome":
            entry["target"] = "pkg/widget.go"
        batch.append(entry)
    code, out, err = _run(
        "fill-contract",
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-go-color",
        "--batch",
        cwd=repo_root,
        stdin=json.dumps(batch),
    )
    assert code == 0, err

    assert "CONTRACT-FILL-STATUS: COMPLETE" in out
    support_path = repo_root / "spec" / "widget.tla"
    support_path.parent.mkdir(parents=True)
    support_path.write_text("---- MODULE widget ----\n====\n", encoding="utf-8")

    code, out, err = _run(
        "dispatch",
        "--repo-root",
        str(repo_root),
        "--delivery-contract",
        contract_relative,
        cwd=repo_root,
    )

    assert code == 0, err
    assert "WHAT:" not in err
    assert out.startswith(f"THIN-DELIVERY-CONTRACT: {contract_relative}\n")
    assert "THIN-DELIVERY-CONTRACT-DIGEST: sha256:" in out
