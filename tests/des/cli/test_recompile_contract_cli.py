"""CLI acceptance tests for `des recompile-contract` -- the sanctioned
producer-owned path that re-derives an EXISTING DeliveryContract against the
CURRENT architecture authority while preserving ATD's semantic fills."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.cli.test_compile_contract_cli import (
    _ARCH_AUTHORITY,
    _BinaryStdin,
    _build_repo,
    _git,
)

from des.application.delivery_snapshot import (
    construct_closure,
    construct_closure_correction,
    recognize_closure,
)
from des.application.ordinary_request import compute_delivery_id


_OTHER_MODULE = '"""A second stand-in production module."""\n\n\nVALUE = 1\n'

#: Every brief below uses "# widget" as its top-level heading so
#: `_ARCH_AUTHORITY`'s `#widget` anchor resolves to a REAL, document-
#: spanning section (des compile-contract now derives every fact from the
#: cited section alone, F-COMPILE-CONTRACT-IGNORES-AUTHORITY-ANCHOR) --
#: these fixtures test recompile's own fill-preservation behavior, not
#: anchor-scoping, so one heading covering the whole document is correct.
_BRIEF_WIDGET_AND_OTHER = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) and the sibling module are both touched.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/other.py` | **EXTEND** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_BRIEF_WIDGET_AND_OTHER_WITH_SUPPORT = (
    _BRIEF_WIDGET_AND_OTHER
    + """\

Acceptance support locator: `spec/Widget.tla`
Acceptance support locator: `tests/support/widget.json`
"""
)

_BRIEF_WIDGET_AND_BRANDNEW = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) plus one genuinely new module.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/brandnew.py` | **CREATE_NEW** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_BRIEF_WIDGET_AND_NEWMOD_CREATE = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) plus one module authored fresh.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/newmod.py` | **CREATE_NEW** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_BRIEF_WIDGET_AND_NEWMOD_EXTEND = _BRIEF_WIDGET_AND_NEWMOD_CREATE.replace(
    "| `pkg/newmod.py` | **CREATE_NEW** |", "| `pkg/newmod.py` | **EXTEND** |"
)

_PLACEHOLDER = "<ATD: fill>"
_BOUNDARY_FIELDS = (
    "failure-behavior",
    "substrate-lie",
    "substrate-probe",
    "double-blind-spot",
)

_STD_FLAGS = (
    "--delivery-id",
    "widget-color",
    "--architecture-authority",
    _ARCH_AUTHORITY,
)


def _write_brief(repo_root: Path, brief_text: str) -> None:
    (repo_root / "docs" / "product" / "architecture" / "brief.md").write_text(
        brief_text, encoding="utf-8"
    )


def _compile(repo_root: Path) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["compile-contract", "--repo-root", str(repo_root), *_STD_FLAGS],
        cwd=repo_root,
    )


def _recompile(repo_root: Path) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["recompile-contract", "--repo-root", str(repo_root), *_STD_FLAGS],
        cwd=repo_root,
    )


def _contract_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "delivery-contracts" / "widget-color.json"


def test_auto_recompile_conserves_the_exact_value_seed(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = _build_repo(tmp_path)
    value_seed = "Widget gains a validated color attribute."
    delivery_id = compute_delivery_id(value_seed)
    flags = [
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        delivery_id,
        "--architecture-authority",
        _ARCH_AUTHORITY,
    ]
    monkeypatch.setattr(sys, "stdin", _BinaryStdin(value_seed.encode("utf-8")))
    code, _out, err = run_cli_in_process(["compile-contract", *flags], cwd=repo_root)
    assert code == 0, err

    path = repo_root / "docs" / "delivery-contracts" / f"{delivery_id}.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["outcome"] = "stale prior outcome"
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(sys, "stdin", _BinaryStdin(b""))
    code, _out, err = run_cli_in_process(["recompile-contract", *flags], cwd=repo_root)
    assert code == 2
    assert "requires the exact immutable VALUE-SEED" in err

    monkeypatch.setattr(sys, "stdin", _BinaryStdin(value_seed.encode("utf-8")))
    code, _out, err = run_cli_in_process(["recompile-contract", *flags], cwd=repo_root)
    assert code == 0, err
    recompiled = json.loads(path.read_text(encoding="utf-8"))
    assert recompiled["outcome"] == value_seed


def _fill_every_semantic_field(repo_root: Path) -> None:
    """Simulate ATD's authoring turn: replace every placeholder with a
    distinct, recognisable non-placeholder text."""
    path = _contract_path(repo_root)
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["outcome"] = "filled outcome"
    for target_path, plan in contract["targets"].items():
        plan["justification"] = f"filled justification for {target_path}"
        for field in _BOUNDARY_FIELDS:
            plan["boundary"][field] = f"filled {field} for {target_path}"
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def test_recompile_preserves_fills_across_a_modified_target_table(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    (repo_root / "pkg" / "other.py").write_text(_OTHER_MODULE, encoding="utf-8")
    _write_brief(repo_root, _BRIEF_WIDGET_AND_OTHER)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)

    # The authority moves on: one target added, one removed.
    _write_brief(repo_root, _BRIEF_WIDGET_AND_BRANDNEW)
    code, out, err = _recompile(repo_root)
    assert code == 0, err

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert set(contract["targets"]) == {"pkg/widget.py", "pkg/brandnew.py"}
    assert contract["outcome"] == "filled outcome"
    widget = contract["targets"]["pkg/widget.py"]
    assert widget["justification"] == "filled justification for pkg/widget.py"
    for field in _BOUNDARY_FIELDS:
        assert widget["boundary"][field] == f"filled {field} for pkg/widget.py"
    brandnew = contract["targets"]["pkg/brandnew.py"]
    assert brandnew["decision"] == "CREATE_NEW"
    assert brandnew["justification"] == _PLACEHOLDER
    for field in _BOUNDARY_FIELDS:
        assert brandnew["boundary"][field] == _PLACEHOLDER

    assert (
        "DELIVERY-CONTRACT-SKELETON: docs/delivery-contracts/widget-color.json" in out
    )
    assert "ORACLE-LOCATOR: pkg/tests/test_widget_color.py" in out
    assert "RECOMPILE: kept 6 fills, new 1 targets, dropped 1 targets" in out


def test_recompile_refuses_when_no_contract_exists(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _recompile(repo_root)
    assert code == 2
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "des compile-contract" in err


def test_recompile_with_unchanged_authority_preserves_every_fill(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    (repo_root / "pkg" / "other.py").write_text(_OTHER_MODULE, encoding="utf-8")
    _write_brief(repo_root, _BRIEF_WIDGET_AND_OTHER)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)
    filled = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))

    code, out, err = _recompile(repo_root)
    assert code == 0, err

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert set(contract["targets"]) == set(filled["targets"])
    assert contract["outcome"] == "filled outcome"
    for target_path, plan in contract["targets"].items():
        assert plan["justification"] == f"filled justification for {target_path}"
        for field in _BOUNDARY_FIELDS:
            assert plan["boundary"][field] == f"filled {field} for {target_path}"
    assert "RECOMPILE: kept 11 fills, new 0 targets, dropped 0 targets" in out


def test_recompile_corrects_paradigm_from_current_architecture_authority(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    brief_path = repo_root / "docs" / "product" / "architecture" / "brief.md"
    code, _out, err = _compile(repo_root)
    assert code == 0, err

    brief_path.write_text(
        brief_path.read_text(encoding="utf-8").replace(
            "Paradigm: object_oriented", "Paradigm: functional"
        ),
        encoding="utf-8",
    )
    code, _out, err = _recompile(repo_root)

    assert code == 0, err
    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert contract["paradigm"] == "functional"


def test_review_bound_recompile_preserves_original_base_and_advances_closure(
    tmp_path: Path,
) -> None:
    """A mechanical correction after AT reviewed C is a child of C, while
    the DeliveryContract still names the original delivery base B."""
    repo_root = _build_repo(tmp_path)
    (repo_root / "CLAUDE.md").write_text(
        "- Run the subject's own tests: `sh -c true test`\n", encoding="utf-8"
    )
    _git(repo_root, "add", "CLAUDE.md")
    _git(repo_root, "commit", "-q", "-m", "declare preservation")
    code, _out, err = run_cli_in_process(
        [
            "compile-contract",
            "--repo-root",
            str(repo_root),
            *_STD_FLAGS,
            "--examine",
            "false",
        ],
        cwd=repo_root,
    )
    assert code == 0, err

    contract_path = _contract_path(repo_root)
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    original_base = contract["repository"]["base-revision"]
    oracle_locator = contract["acceptance-tests"]["locator"]
    oracle_path = repo_root / oracle_locator.split("::", 1)[0]
    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.write_text(
        "def test_widget_color():\n    assert True\n", encoding="utf-8"
    )
    closure = construct_closure(
        repo_root,
        contract=contract,
        contract_locator=str(contract_path.relative_to(repo_root)),
        contract_bytes=contract_bytes,
        oracle_locator=oracle_locator,
        oracle_bytes=oracle_path.read_bytes(),
        supporting=(),
    )
    assert (
        recognize_closure(closure.root, closure.commit).base
        == original_base.split(":", 1)[1]
    )

    brief_path = closure.root / "docs/product/architecture/brief.md"
    brief_path.write_text(
        brief_path.read_text(encoding="utf-8").replace(
            "Paradigm: object_oriented", "Paradigm: functional"
        ),
        encoding="utf-8",
    )
    code, _out, err = run_cli_in_process(
        [
            "recompile-contract",
            "--repo-root",
            str(closure.root),
            *_STD_FLAGS,
            "--examine",
            "false",
        ],
        cwd=closure.root,
    )
    assert code == 0, err

    corrected_path = _contract_path(closure.root)
    corrected_bytes = corrected_path.read_bytes()
    corrected = json.loads(corrected_bytes)
    assert corrected["repository"]["base-revision"] == original_base
    assert corrected["paradigm"] == "functional"

    corrected_closure = construct_closure_correction(
        closure.root,
        cited=closure,
        contract=corrected,
        contract_locator=str(corrected_path.relative_to(closure.root)),
        contract_bytes=corrected_bytes,
        oracle_locator=oracle_locator,
        oracle_bytes=(closure.root / oracle_locator.split("::", 1)[0]).read_bytes(),
        supporting=(),
    )
    assert corrected_closure.parent == closure.commit
    assert corrected_closure.base == original_base.split(":", 1)[1]


def test_recompile_publish_failure_leaves_existing_contract_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _build_repo(tmp_path)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    contract_path = _contract_path(repo_root)
    before = contract_path.read_bytes()
    _write_brief(
        repo_root,
        _BRIEF_WIDGET_ONLY.replace("Paradigm: object_oriented", "Paradigm: functional"),
    )

    original_replace = Path.replace

    def fail_publish(path: Path, target: Path) -> Path:
        if path.name == f".{contract_path.name}.tmp":
            raise OSError("injected publish failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_publish)
    with pytest.raises(OSError, match="injected publish failure"):
        _recompile(repo_root)

    assert contract_path.read_bytes() == before
    assert not contract_path.with_name(f".{contract_path.name}.tmp").exists()


def test_recompile_preserves_schema_1_4_acceptance_support_closure(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    (repo_root / "pkg" / "other.py").write_text(_OTHER_MODULE, encoding="utf-8")
    _write_brief(repo_root, _BRIEF_WIDGET_AND_OTHER_WITH_SUPPORT)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)

    code, _out, err = _recompile(repo_root)

    assert code == 0, err
    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert contract["schema-version"] == "1.4"
    assert contract["acceptance-tests"]["supporting-locators"] == [
        "spec/Widget.tla",
        "tests/support/widget.json",
    ]
    assert contract["outcome"] == "filled outcome"


def test_recompile_resets_fills_when_a_declared_decision_changes(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_WIDGET_AND_NEWMOD_CREATE)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)

    # The module got authored meanwhile; the authority flips its decision.
    (repo_root / "pkg" / "newmod.py").write_text(_OTHER_MODULE, encoding="utf-8")
    _write_brief(repo_root, _BRIEF_WIDGET_AND_NEWMOD_EXTEND)
    code, out, err = _recompile(repo_root)
    assert code == 0, err

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    widget = contract["targets"]["pkg/widget.py"]
    assert widget["justification"] == "filled justification for pkg/widget.py"
    newmod = contract["targets"]["pkg/newmod.py"]
    assert newmod["decision"] == "EXTEND"
    assert newmod["justification"] == _PLACEHOLDER
    for field in _BOUNDARY_FIELDS:
        assert newmod["boundary"][field] == _PLACEHOLDER

    assert "RECOMPILE-DECISION-CHANGED: pkg/newmod.py CREATE_NEW -> EXTEND" in out
    assert "RECOMPILE: kept 6 fills, new 1 targets, dropped 0 targets" in out


_BRIEF_WIDGET_ONLY = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) alone.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_BRIEF_WIDGET_AND_OTHER_CREATE = _BRIEF_WIDGET_ONLY.replace(
    "| `pkg/widget.py` | **EXTEND** |",
    "| `pkg/widget.py` | **EXTEND** |\n| `pkg/other.py` | **CREATE_NEW** |",
)


def test_recompile_exempts_an_unchanged_declared_target_from_regrounding(
    tmp_path: Path,
) -> None:
    """A CREATE_NEW target the EXISTING contract already declares was
    grounded at the original compile; the crafter authoring that very file
    mid-delivery must not poison the recompile of its own contract."""
    repo_root = _build_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_WIDGET_AND_NEWMOD_CREATE)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)

    # The delivery's own in-flight product: the declared file now exists.
    (repo_root / "pkg" / "newmod.py").write_text(_OTHER_MODULE, encoding="utf-8")
    code, out, err = _recompile(repo_root)
    assert code == 0, err

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    newmod = contract["targets"]["pkg/newmod.py"]
    assert newmod["decision"] == "CREATE_NEW"
    assert newmod["justification"] == "filled justification for pkg/newmod.py"
    for field in _BOUNDARY_FIELDS:
        assert newmod["boundary"][field] == f"filled {field} for pkg/newmod.py"
    assert "RECOMPILE: kept 11 fills, new 0 targets, dropped 0 targets" in out


def test_recompile_still_refuses_a_new_create_new_row_over_an_existing_file(
    tmp_path: Path,
) -> None:
    """The exemption covers only targets the existing contract already
    declares -- a genuinely NEW row is grounded fresh, protection intact."""
    repo_root = _build_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_WIDGET_ONLY)
    code, _out, err = _compile(repo_root)
    assert code == 0, err

    (repo_root / "pkg" / "other.py").write_text(_OTHER_MODULE, encoding="utf-8")
    _write_brief(repo_root, _BRIEF_WIDGET_AND_OTHER_CREATE)
    code, _out, err = _recompile(repo_root)
    assert code == 2
    assert "already exists in the base tree" in err


_GO_MODULE = "package pkg\n\nfunc Value() int { return 1 }\n"

_BRIEF_NONPY_WITH_CITED_ORACLE = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) plus a Go helper; the oracle is cited at
`pkg/tests/test_widget_color.py:1`.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/helper.go` | **EXTEND** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""

_BRIEF_NONPY_NO_ORACLE = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) plus a Go helper.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/helper.go` | **EXTEND** |

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""


def _build_nonpy_repo(tmp_path: Path) -> Path:
    repo_root = _build_repo(tmp_path)
    (repo_root / "pkg" / "helper.go").write_text(_GO_MODULE, encoding="utf-8")
    return repo_root


def test_recompile_reuses_the_existing_oracle_when_the_brief_cites_none(
    tmp_path: Path,
) -> None:
    """The existing contract is the record of the original oracle judgment
    -- a recompile against a brief that no longer cites a test-shaped
    oracle reuses it instead of refusing (the compile-contract refusal for
    a non-Python subject with no cited oracle stays intact)."""
    repo_root = _build_nonpy_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_NONPY_WITH_CITED_ORACLE)
    code, _out, err = _compile(repo_root)
    assert code == 0, err

    _write_brief(repo_root, _BRIEF_NONPY_NO_ORACLE)
    code, out, err = _recompile(repo_root)
    assert code == 0, err
    assert "RECOMPILE-ORACLE: reused from existing contract" in out
    assert "ORACLE-LOCATOR: pkg/tests/test_widget_color.py" in out

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert contract["acceptance-tests"]["locator"] == "pkg/tests/test_widget_color.py"


def test_recompile_without_an_oracle_in_the_existing_contract_still_refuses(
    tmp_path: Path,
) -> None:
    repo_root = _build_nonpy_repo(tmp_path)
    _write_brief(repo_root, _BRIEF_NONPY_WITH_CITED_ORACLE)
    code, _out, err = _compile(repo_root)
    assert code == 0, err

    path = _contract_path(repo_root)
    contract = json.loads(path.read_text(encoding="utf-8"))
    del contract["acceptance-tests"]
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    _write_brief(repo_root, _BRIEF_NONPY_NO_ORACLE)
    code, out, err = _recompile(repo_root)
    assert code == 2
    assert "non-Python subject" in err
    assert "no test/spec oracle could be bound" in err
    # GDP-3: the refusal states the CAUSE (nothing declared, nothing
    # cited), never the bare, unactionable "missing".
    assert "no 'Oracle target locator:' declaration" in err
    assert "RECOMPILE-ORACLE" not in out


def test_recompile_reuses_the_verification_scope_bound_to_a_reused_oracle(
    tmp_path: Path,
) -> None:
    """A reused NON-Python oracle carries its verification-scope portion
    with it: the fresh derivation has no citation and no declared command
    to work from, and the existing contract already records the original
    judgment."""
    repo_root = _build_nonpy_repo(tmp_path)
    brief_with_go_oracle = (
        _BRIEF_NONPY_WITH_CITED_ORACLE.replace(
            "`pkg/tests/test_widget_color.py:1`", "`pkg/widget_test.go:1`"
        )
        + "\nVerification command: `go test ./...`\n"
    )
    _write_brief(repo_root, brief_with_go_oracle)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    original = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))

    _write_brief(repo_root, _BRIEF_NONPY_NO_ORACLE)
    code, out, err = _recompile(repo_root)
    assert code == 0, err
    assert "RECOMPILE-ORACLE: reused from existing contract" in out
    assert "ORACLE-LOCATOR: pkg/widget_test.go" in out

    contract = json.loads(_contract_path(repo_root).read_text(encoding="utf-8"))
    assert contract["acceptance-tests"]["locator"] == "pkg/widget_test.go"
    assert contract["verification-scope"] == original["verification-scope"]


_BRIEF_WIDGET_AND_DIRECTORY = """\
# widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) plus a whole directory, wrongly declared.

| Target | Decision |
|---|---|
| `pkg/widget.py` | **EXTEND** |
| `pkg/newdir/` | **CREATE_NEW** |

Oracle target locator: `pkg/tests/test_widget_color.py`

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""


def test_recompile_refuses_a_directory_target_cell_and_leaves_the_contract(
    tmp_path: Path,
) -> None:
    """Same GDP-0 treatment as des compile-contract: the MERGED contract
    is validated pre-write, so a since-broken authority cannot overwrite a
    good contract with a schema-invalid one."""
    repo_root = _build_repo(tmp_path)
    code, _out, err = _compile(repo_root)
    assert code == 0, err
    _fill_every_semantic_field(repo_root)
    before = _contract_path(repo_root).read_bytes()

    _write_brief(repo_root, _BRIEF_WIDGET_AND_DIRECTORY)
    code, _out, err = _recompile(repo_root)

    assert code == 2
    assert "schema-invalid-skeleton" in err
    assert "the Target cell of the row declaring 'pkg/newdir/'" in err
    assert "docs/product/architecture/brief.md#widget" in err
    assert "re-run des recompile-contract" in err
    # The existing contract is untouched, byte for byte.
    assert _contract_path(repo_root).read_bytes() == before
