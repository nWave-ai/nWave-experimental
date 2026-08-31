"""CLI acceptance tests for `des compile-contract`
(ADR-SSOT-002 Section 4/4b item 1)."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process

from des._internal.delivery_contract_schema import (
    delivery_contract_schema_violation,
)
from des.application.ordinary_request import compute_delivery_id


class _BinaryStdin:
    """A genuine byte stream on `.buffer`, matching `sys.stdin`'s shape."""

    def __init__(self, seed_bytes: bytes) -> None:
        self.buffer = io.BytesIO(seed_bytes)


def _run(*args: str, cwd: Path) -> tuple[int, str, str]:
    return run_cli_in_process(["compile-contract", *args], cwd=cwd)


_TARGET_MODULE = '''\
"""A tiny stand-in production module."""
from thirdpartylib import Helper


class Widget:
    def existing_method(self):
        return None
'''

#: Top-level heading doubles as the section `_ARCH_AUTHORITY` cites (`#widget`)
#: -- these fixtures test OTHER behavior, so making the whole document the
#: cited section (no sibling section to exclude) keeps them unchanged by the
#: anchor-scoping fix; the anchor still resolves to a REAL heading, never a
#: shape-only string the compiler accepted and then discarded.
_BRIEF = """\
# widget

Paradigm: object_oriented

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
    assert contract["schema-version"] == "1.3"
    assert contract["delivery-route"] == "RED_TO_GREEN"
    assert set(contract["targets"]) == {"pkg/widget.py"}
    assert contract["acceptance-tests"]["locator"] == "pkg/tests/test_widget_color.py"
    # No ARCHITECTURE_BOUNDARY_CHANGE obligation and no override -> False.
    assert contract["applicability"]["independent-review"] is False


def test_derives_functional_paradigm_from_architecture_authority(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    brief_path = repo_root / "docs" / "product" / "architecture" / "brief.md"
    brief_path.write_text(
        _BRIEF.replace("Paradigm: object_oriented", "Paradigm: functional"),
        encoding="utf-8",
    )

    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "functional-widget",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 0, err
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/functional-widget.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["paradigm"] == "functional"


def test_refuses_root_paradigm_when_architecture_does_not_own_it(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    brief_path = repo_root / "docs" / "product" / "architecture" / "brief.md"
    brief_path.write_text(
        _BRIEF.replace("Paradigm: object_oriented\n\n", ""), encoding="utf-8"
    )

    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "root-guessed-widget",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        "--paradigm",
        "object_oriented",
        cwd=repo_root,
    )

    assert code == 2
    assert "does not declare a paradigm" in err
    assert "cannot be silently defaulted or supplied by root" in err


@pytest.mark.parametrize(
    ("declaration", "root_assertion", "expected"),
    [
        (
            "Paradigm: functional\nParadigm: OO",
            None,
            "conflicting paradigms",
        ),
        (
            "Paradigm: functional\nParadigm: FP",
            None,
            "declares the paradigm more than once",
        ),
        ("Paradigm: procedural", None, "unsupported paradigm 'procedural'"),
        (
            "Paradigm: functional",
            "object_oriented",
            "contradicts the architecture authority",
        ),
    ],
)
def test_refuses_ambiguous_paradigm_projection(
    tmp_path: Path,
    declaration: str,
    root_assertion: str | None,
    expected: str,
) -> None:
    repo_root = _build_repo(tmp_path)
    brief_path = repo_root / "docs" / "product" / "architecture" / "brief.md"
    brief_path.write_text(
        _BRIEF.replace("Paradigm: object_oriented", declaration), encoding="utf-8"
    )
    args = [
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "ambiguous-widget",
        "--architecture-authority",
        _ARCH_AUTHORITY,
    ]
    if root_assertion is not None:
        args.extend(("--paradigm", root_assertion))

    code, _out, err = _run(*args, cwd=repo_root)

    assert code == 2
    assert expected in err


def test_canonical_test_dependencies_select_schema_1_4_closure(tmp_path: Path) -> None:
    repo_root = _build_repo(tmp_path)
    brief_path = repo_root / "docs" / "product" / "architecture" / "brief.md"
    brief_path.write_text(
        _BRIEF
        + "\nTest dependency locator: `spec/Widget.tla`\n"
        + "Test dependency locator: `tests/support/widget.json`\n",
        encoding="utf-8",
    )

    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-with-dependencies",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 0, err
    contract = json.loads(
        (repo_root / "docs/delivery-contracts/widget-with-dependencies.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["schema-version"] == "1.4"
    assert contract["acceptance-tests"]["supporting-locators"] == [
        "spec/Widget.tla",
        "tests/support/widget.json",
    ]


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
    assert "WHAT: existing-contract: a contract already exists" in err
    assert "already exists" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_existing_non_file_collision_is_not_an_existing_contract(
    tmp_path: Path,
) -> None:
    repo_root = _build_repo(tmp_path)
    destination = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    args = (
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
    )
    code, _out, err = _run(*args, cwd=repo_root)
    assert code == 2
    assert "WHAT: existing-non-file:" in err
    assert "existing-contract" not in err

    recompile = run_cli_in_process(["recompile-contract", *args], cwd=repo_root)
    assert recompile[0] == 2
    assert "no contract exists" in recompile[2]
    assert "existing-contract" not in recompile[2]


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
# widget

Paradigm: object_oriented

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
# widget

Paradigm: object_oriented

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


def test_an_unreadable_installed_schema_is_a_structured_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _build_repo(tmp_path)
    config_root = tmp_path / "claude"
    schema = (
        config_root / "lib" / "nWave" / "schemas" / "thin-delivery-contract.schema.json"
    )
    schema.parent.mkdir(parents=True)
    schema.write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_root))

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
    assert "contract-schema-unreadable" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "Traceback" not in err
    assert not (repo_root / "docs" / "delivery-contracts").exists()


# --- F-COMPILE-CONTRACT-IGNORES-AUTHORITY-ANCHOR (docs/product/backlog.md):
# `--architecture-authority <path>.md#<anchor>` validated the anchor's SHAPE
# then discarded it -- every fact was derived from the WHOLE document, never
# the cited section alone.

_TWO_SECTION_BRIEF = """\
# Architecture Brief

## sibling-defect -- a DIFFERENT bug, must never leak into widget's contract

`Sibling` (`pkg/sibling.py:1`) is the target of an UNRELATED defect.

Oracle target locator: `pkg/tests/test_sibling_wrong.py`

### Delivery obligations (RED_TO_GREEN)

1. **CONTESTED_LAW** -- law: unrelated to widget, must not leak.

## widget

Paradigm: object_oriented

`Widget` (`pkg/widget.py:5`) already exposes `existing_method`
(`pkg/widget.py:6`).

Oracle target locator: `pkg/tests/test_widget_color.py`

### Delivery obligations (RED_TO_GREEN)

1. **REUSE_CANDIDATE** -- law: reuse existing_method.
"""


def test_only_the_cited_section_feeds_the_compiled_contract(tmp_path: Path) -> None:
    """The falsifier: `--architecture-authority` cites ONLY `#widget`. A
    SIBLING section (`## sibling-defect`) carries its own target citation,
    oracle locator and obligation -- none of it may land in the compiled
    skeleton. Before the fix these leaked in because the anchor was
    accepted-then-ignored and the whole document was read regardless."""
    repo_root = _build_repo(tmp_path)
    _write_brief(repo_root, _TWO_SECTION_BRIEF)

    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 0, err
    contract_path = repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert set(contract["targets"]) == {"pkg/widget.py"}
    assert contract["acceptance-tests"]["locator"] == "pkg/tests/test_widget_color.py"
    assert contract["obligations"] == ["REUSE_CANDIDATE"]


# --- Construction, not prose (auto delivery outcome = the piped VALUE-SEED,
# never `<ATD: fill>`): compile-contract is a producer in the SAME raw-stdin
# VALUE-SEED family as `des prepare-ordinary-request`/`des resolve-charters`
# (`read_value_seed_text`) -- for an auto DeliveryId (`compute_delivery_id`),
# the exact piped seed bytes must land in `contract["outcome"]` verbatim,
# never the `<ATD: fill>` placeholder ATD would otherwise have to author.


def test_an_auto_delivery_writes_outcome_as_the_exact_piped_value_seed(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = _build_repo(tmp_path)
    value_seed = "Widget gains a validated color attribute."
    auto_delivery_id = compute_delivery_id(value_seed)
    monkeypatch.setattr(sys, "stdin", _BinaryStdin(value_seed.encode("utf-8")))

    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        auto_delivery_id,
        "--architecture-authority",
        _ARCH_AUTHORITY,
        cwd=repo_root,
    )

    assert code == 0, err
    contract_path = (
        repo_root / "docs" / "delivery-contracts" / f"{auto_delivery_id}.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["outcome"] == value_seed


def test_refuses_when_the_cited_anchor_names_no_real_heading(tmp_path: Path) -> None:
    """The other half of the same defect: a lexically well-formed anchor
    matching NO real heading was previously accepted by the shape-only
    check and the whole document was read regardless (accepted-then-
    ignored is worse than refusing). It must now be a typed refusal, never
    a silent whole-document fallback."""
    repo_root = _build_repo(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(repo_root),
        "--delivery-id",
        "widget-color",
        "--architecture-authority",
        "ARCHITECTURE-COVERED: docs/product/architecture/brief.md#no-such-heading",
        cwd=repo_root,
    )
    assert code != 0
    assert "no heading" in err
    assert "matches the anchor" in err
    assert not (
        repo_root / "docs" / "delivery-contracts" / "widget-color.json"
    ).exists()
