"""Acceptance contract for the thin DeliveryContract dispatch boundary.

The public surface validates one repository-relative immutable contract,
resolves the independent EXAMINE applicability axis, and emits only the two
identity headers consumed by DELIVER.  Route, outcome, obligations and charter
paths remain in their canonical authorities rather than being copied into a
second prompt model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from textwrap import dedent

import pytest

from des.cli.dispatch import closure_digest
from tests.common.delivery_contract_fixture import (
    load_valid_contract,
    seed_referenced_oracle,
)
from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    return run_cli_in_process(["dispatch", *args], cwd=cwd or _REPO_ROOT)


def _seed_contract(
    root: Path,
    *,
    route: str = "RED_TO_GREEN",
    examine: bool = False,
    delivery_id: str = "thin-dispatch",
) -> Path:
    contract = load_valid_contract()
    contract["delivery-id"] = delivery_id
    contract["delivery-route"] = route
    contract["applicability"]["examine"] = examine
    seed_referenced_oracle(root, contract)
    path = root / "delivery-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return path


def _write_charter(root: Path, name: str = "charter.md") -> Path:
    path = root / "docs" / "product" / "expectations" / "thin-dispatch" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        dedent(
            """\
            # Observable delivery
            ID: EXP-thin-dispatch · Spec rows: n/a · Persona: a developer

            ## Intent
            Observe the delivered behavior through its public surface.

            ## Preconditions
            The installed product is available.

            ## Charter
            Exercise the user-visible outcome without reading source.

            ## Expected observations (oracle)
            - The promised outcome is observable.
            - Negative: a failed outcome never reports PASS.

            ## Session log (append-only)
            | date | examiner | verdict | observations |
            |------|----------|---------|--------------|
            """
        ),
        encoding="utf-8",
    )
    return path


def _expected_handoff(path: Path) -> str:
    contract = json.loads(path.read_text(encoding="utf-8"))
    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_bytes = (path.parent / oracle_locator).read_bytes()
    digest = closure_digest(path.read_bytes(), oracle_bytes)
    return (
        "THIN-DELIVERY-CONTRACT: delivery-contract.json\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
    )


def test_help_makes_the_only_locator_pair_discoverable() -> None:
    exit_code, out, err = _run("--help")

    assert exit_code == 0
    assert "--repo-root" in out
    assert "--delivery-contract" in out
    assert "relative to --repo-root" in out
    assert not err


@pytest.mark.parametrize("route", ["RED_TO_GREEN", "GREEN_TO_GREEN"])
def test_valid_contract_emits_only_locator_and_digest(
    tmp_path: Path, route: str
) -> None:
    contract_path = _seed_contract(tmp_path, route=route)

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0
    assert out == _expected_handoff(contract_path)
    assert err == ""
    assert route not in out
    assert "feature-delta" not in out.casefold()


@pytest.mark.parametrize(
    "legacy_args",
    [
        ("--mode", "atdd_pure"),
        ("--project-id", "demo"),
        ("--slice", "slice-01"),
        ("--phase", "A_GREEN"),
        ("--wave", "deliver"),
        ("--lane", "prefactoring"),
    ],
)
def test_retired_control_plane_flags_are_not_public(
    tmp_path: Path, legacy_args: tuple[str, str]
) -> None:
    contract_path = _seed_contract(tmp_path)

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
        *legacy_args,
    )

    assert exit_code != 0
    assert out == ""
    assert "unrecognized arguments" in err


@pytest.mark.parametrize(
    "unsafe_locator",
    [
        "",
        "/absolute.json",
        "../escape.json",
        "a/../../escape.json",
        "a\\b.json",
        "*.json",
    ],
)
def test_unsafe_contract_locator_refuses_before_handoff(
    tmp_path: Path, unsafe_locator: str
) -> None:
    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        unsafe_locator,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_examine_false_never_reads_the_charter_namespace(tmp_path: Path) -> None:
    contract_path = _seed_contract(tmp_path, examine=False)
    namespace = tmp_path / "docs" / "product" / "expectations" / "thin-dispatch"
    namespace.mkdir(parents=True)
    (namespace / "invalid.txt").write_text("must be ignored", encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0
    assert out == _expected_handoff(contract_path)
    assert err == ""


@pytest.mark.parametrize("namespace_shape", ["missing", "empty"])
def test_examine_true_requires_a_nonempty_valid_charter_namespace(
    tmp_path: Path, namespace_shape: str
) -> None:
    contract_path = _seed_contract(tmp_path, examine=True)
    if namespace_shape == "empty":
        (tmp_path / "docs" / "product" / "expectations" / "thin-dispatch").mkdir(
            parents=True
        )

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "charter" in err.casefold()


def test_examine_true_validates_every_member_but_does_not_copy_charters(
    tmp_path: Path,
) -> None:
    contract_path = _seed_contract(tmp_path, examine=True)
    _write_charter(tmp_path, "a.md")
    _write_charter(tmp_path, "b.md")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0
    assert out == _expected_handoff(contract_path)
    assert "charter" not in out.casefold()
    assert err == ""

    invalid = (
        tmp_path / "docs" / "product" / "expectations" / "thin-dispatch" / "invalid.txt"
    )
    invalid.write_text("not a charter", encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )
    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


@pytest.mark.parametrize(
    "corrupt_oracle",
    ["missing", "directory", "fifo", "symlink_escape"],
)
def test_unsafe_or_missing_oracle_refuses_before_handoff(
    tmp_path: Path, corrupt_oracle: str
) -> None:
    contract_path = _seed_contract(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_path = tmp_path / oracle_locator
    oracle_path.unlink()

    if corrupt_oracle == "directory":
        oracle_path.mkdir()
    elif corrupt_oracle == "fifo":
        os.mkfifo(oracle_path)
    elif corrupt_oracle == "symlink_escape":
        outside = tmp_path.parent / "outside-oracle.txt"
        outside.write_text("outside", encoding="utf-8")
        oracle_path.symlink_to(outside)

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


@pytest.mark.parametrize(
    "self_referencing_oracle_locator_kind",
    ["textual", "physical"],
)
def test_oracle_locator_matching_contract_path_refuses_before_read(
    tmp_path: Path, self_referencing_oracle_locator_kind: str
) -> None:
    contract_path = _seed_contract(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    if self_referencing_oracle_locator_kind == "textual":
        self_referencing_oracle_locator = contract_path.name
    else:
        alias_path = tmp_path / "oracle-alias.py"
        alias_path.symlink_to(contract_path.name)
        self_referencing_oracle_locator = alias_path.name

    contract["acceptance-tests"]["locator"] = self_referencing_oracle_locator
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "same physical path" in err


def test_declared_import_absent_from_the_base_tree_refuses_before_handoff(
    tmp_path: Path,
) -> None:
    """Run 4 shift-left: `des dispatch` is the documented early gate called
    immediately after CONTRACT_READY, before any crafter subagent starts
    (`nWave/skills/nw-distill/SKILL.md`); it must catch an ATD-invented
    declared-import here, not only later at the crafter's own BASELINE
    `des validate-delivery-contract` call."""
    contract_path = _seed_contract(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    target_path = next(iter(contract["targets"]))
    contract["targets"][target_path]["declared-imports"] = ["cronsim.CronSim"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "cronsim.CronSim" in err
    assert (
        f"not present at base revision {contract['repository']['base-revision']}" in err
    )


def test_verification_command_naming_a_wrong_test_path_refuses_before_handoff(
    tmp_path: Path,
) -> None:
    """K4 Run 9: ATD-1 wrote a `manage.py test`-shaped verification command
    citing a dotted path missing its real package prefix; `des dispatch`
    accepted it and crafter-1 spent 525.8s/62 tool calls discovering the
    command itself was wrong. Catch it here, before any crafter starts."""
    contract_path = _seed_contract(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["verification-scope"]["commands"].append(
        {
            "executable": {"kind": "repository", "path": "manage.py"},
            "arguments": ["test", "totally.invented.test_module"],
        }
    )
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "totally.invented.test_module" in err
    assert "does not resolve to a base-tree test module or file" in err


def test_schema_invalid_contract_refuses_before_handoff(tmp_path: Path) -> None:
    contract_path = tmp_path / "delivery-contract.json"
    contract_path.write_text("{}", encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "schema" in err.casefold()
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_three_distinct_defects_are_all_named_in_one_refusal(tmp_path: Path) -> None:
    """Run 5 (K4 matrix): `des dispatch` rejected the same contract three
    times in sequence, one defect per REVISE cycle, each costing a full ATD
    REVISE round (~236s + up to 676K cache-read tokens on the third). ONE
    dispatch call, with three distinct real defects present at once --
    TWO invented declared-imports across TWO different targets, plus a
    non-regular-file oracle path -- must name all three in its single
    refusal, not only the first."""
    contract = load_valid_contract()
    _original_target_path, original_target_plan = next(
        iter(contract["targets"].items())
    )

    # Defect A: an invented import absent from the base tree entirely.
    original_target_plan["declared-imports"] = ["nonexistent_module_xyz.invented"]

    # Defect B: a SECOND target, its own independently invented import --
    # proves "across ALL targets", not only the first target checked.
    second_target_path = "src/des/fake_second_target.py"
    second_target_plan = json.loads(json.dumps(original_target_plan))
    second_target_plan["declared-imports"] = ["another_nonexistent_module.Invented"]
    contract["targets"][second_target_path] = second_target_plan

    seed_referenced_oracle(tmp_path, contract)
    contract_path = tmp_path / "delivery-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    # Defect C: the oracle locator resolves to a directory, not a regular
    # file -- reproducing Run 5's third rejected cycle verbatim.
    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_path = tmp_path / oracle_locator
    oracle_path.unlink()
    oracle_path.mkdir()

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "nonexistent_module_xyz.invented" in err, (
        "defect A (first target's invented import) must be named"
    )
    assert "another_nonexistent_module.Invented" in err, (
        "defect B (second target's invented import) must be named"
    )
    assert "not a regular file" in err, "defect C (oracle path) must be named"
    assert err.count("HOW:") == 3, (
        f"each of the three defects must carry its own HOW; got {err.count('HOW:')} "
        f"in: {err!r}"
    )


def test_extend_target_without_insertion_citation_is_refused(tmp_path: Path) -> None:
    """GDP-8 second axis on "lossless contract projection": an EXTEND
    target whose `overlap`/`justification` carries zero file:line-shaped
    citation must be refused -- DESIGN's architecture authority always
    names an exact insertion point for an EXTEND target; dropping it on
    the way into the DeliveryContract leaves the crafter to relocate it
    itself instead of reading it verbatim."""
    contract = load_valid_contract()
    target_path, target_plan = next(iter(contract["targets"].items()))
    assert target_plan["decision"] == "EXTEND"
    target_plan["overlap"] = "The existing schema is the sole shape authority."
    target_plan["justification"] = "Relax syntax at the existing boundary."

    seed_referenced_oracle(tmp_path, contract)
    contract_path = tmp_path / "delivery-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code != 0
    assert out == ""
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert target_path in err, "the uncited EXTEND target must be named"
    assert "insertion" in err.lower()


def test_extend_target_with_citation_in_either_field_is_accepted(
    tmp_path: Path,
) -> None:
    """A citation in `overlap` alone (not just `justification`) must
    satisfy the check -- the rule is "somewhere in this target's own
    text", not one specific field."""
    contract = load_valid_contract()
    _target_path, target_plan = next(iter(contract["targets"].items()))
    assert target_plan["decision"] == "EXTEND"
    target_plan["overlap"] = (
        "See nWave/schemas/thin-delivery-contract.schema.json:64 for the "
        "existing shape authority."
    )
    target_plan["justification"] = "Relax syntax at the existing boundary."

    seed_referenced_oracle(tmp_path, contract)
    contract_path = tmp_path / "delivery-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    exit_code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0, err
