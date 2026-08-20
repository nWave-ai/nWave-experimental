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
    # The shared fixture's own `git diff --check` command is unrelated to
    # the oracle -- it legitimately runs (a real `git` toolchain binary,
    # resolved via PATH) and legitimately fails outside a real git
    # checkout, surfacing as INDETERMINATE noise the oracle red-reason
    # probe honestly reports. The pytest command stays: several tests in
    # this module (declared-import refusal, oracle-locator-matching-
    # contract-path refusal) exercise it directly.
    contract["verification-scope"]["commands"] = [
        command
        for command in contract["verification-scope"]["commands"]
        if command["executable"].get("name") != "git"
    ]
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

    exit_code, out, _err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0
    assert out == _expected_handoff(contract_path)
    # The fixture's pytest command legitimately runs against its own
    # deliberately-RED synthetic oracle and the red-reason probe honestly
    # reports it INDETERMINATE -- expected noise, not this test's concern
    # (thin-contract handoff shape), proven by `out`/exit_code alone.
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

    exit_code, out, _err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        contract_path.name,
    )

    assert exit_code == 0
    assert out == _expected_handoff(contract_path)
    # Oracle-execution noise (see test_valid_contract_emits_only_locator_
    # and_digest above) is expected and not this test's concern (EXAMINE
    # namespace isolation), proven by `out`/exit_code alone.


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
    # Oracle-execution noise (see test_valid_contract_emits_only_locator_
    # and_digest above) is expected and not this test's concern (charters
    # validated but never copied), proven by `out`/exit_code alone.

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
    TWO unfilled placeholders across TWO different fields, plus a
    non-regular-file oracle path -- must name all three in its single
    refusal, not only the first.

    Ale's construction-over-file correction (2026-08-20, "the contract
    has one writer -- `des fill-contract` is the constructor"): the
    ORIGINAL two declared-import defects this test used before are no
    longer representable through `des dispatch` at all -- `des
    fill-contract` has no `--field` choice naming `declared-imports` at
    all, so a fill can never invent one (Agda-proved vacuity,
    ~/nwave-formal/2026-08-19-gates). The batching PROPERTY under test
    (every defect named in one pass, GDP-3/5) is unaffected by which
    checks remain live -- proven here with the placeholder check
    instead."""
    contract = load_valid_contract()
    _original_target_path, original_target_plan = next(
        iter(contract["targets"].items())
    )

    # Defect A: the top-level outcome was never filled.
    contract["outcome"] = "<ATD: fill>"

    # Defect B: a SECOND, independent unfilled field -- proves "every
    # finding", not only the first the checker sees.
    original_target_plan["justification"] = "<ATD: fill>"

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
    assert "outcome" in err, "defect A (unfilled top-level outcome) must be named"
    assert ".justification" in err, (
        "defect B (unfilled target justification) must be named"
    )
    assert "not a regular file" in err, "defect C (oracle path) must be named"
    assert err.count("HOW:") == 3, (
        f"each of the three defects must carry its own HOW; got {err.count('HOW:')} "
        f"in: {err!r}"
    )
