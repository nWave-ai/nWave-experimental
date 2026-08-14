"""Acceptance specs -- dispatch route examine cutover (ADR-SSOT-002 S4b, S9).

Independent, uncontaminated acceptance designer (ATD) authorship -- no read of
any PO charter. Value seed: a DELIVER-test-executing `des dispatch` rendering
a dispatch prompt must correctly handle both delivery-route choices
(RED_TO_GREEN vs GREEN_TO_GREEN) and the examine=true charter namespace
requirement (C6, ADR-SSOT-002 S9).

CONTRACT_SHAPE: vertical-2 route/examine observable behavior:
  1. RED_TO_GREEN renders an ATD instruction to author/prove a new RED acceptance
     oracle; GREEN_TO_GREEN renders an instruction to bind the existing contract
     locator/digest and forbids creating/mutating an AT. (Parametrized by route)
  2. examine=false succeeds without reading/requiring the charter namespace and
     the prompt contains no PO/Vera charter dispatch.
  3. examine=true + missing namespace refuses before DELIVER prompt with
     actionable Author/PO WHAT/WHY/HOW; nonterminal regardless of route.
  4. examine=true + one or multiple filled valid charters succeeds, projects
     every charter path in deterministic POSIX repo-relative order, says
     reuse/no rewrite, terminal Vera aggregate pass.
  5. examine=true + valid charter + one invalid direct member (non-md or
     unfilled) refuses WHAT/WHY/HOW; no filtering and no partial prompt.
  6. invalid schema delivery-id or path token refuses before touching escaping
     namespace.

Driving surface: the public `des dispatch` CLI, in-process via
`tests.common.in_process_cli.run_cli_in_process` (repo convention) -- the SAME
production `des.cli.__main__.main(argv) -> int` edge a real subprocess invokes.

FAILS TODAY: examine mode routes and charter namespace loading/validation are
not yet wired into the dispatch prompt builder -- every test below fails for
genuine semantic reasons (missing route differentiation / absent charter
namespace enforcement / missing charter validation), never a collection error.

covers: dispatch route examine cutover (ADR-SSOT-002 S4b, S9)
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from tests.common.delivery_contract_fixture import (
    load_valid_contract,
    seed_dispatch_ssot,
)
from tests.common.in_process_cli import run_cli_in_process


_REPO_ROOT = Path(__file__).resolve().parents[3]

_DELIVER_ARGS = (
    "--mode",
    "atdd_pure",
    "--project-id",
    "demo",
    "--slice",
    "slice-01",
    "--phase",
    "A_GREEN",
)


def _dispatch_argv(*args: str) -> list[str]:
    return ["dispatch", *args]


def _run(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Drive the real `des dispatch` public CLI edge in-process."""
    return run_cli_in_process(_dispatch_argv(*args), cwd=cwd or _REPO_ROOT)


def _write_filled_charter(root: Path, rel_path: str) -> Path:
    """Write a minimal valid charter markdown that `des verify-charter-filled`
    accepts. Includes the required sections: ID, Intent, Preconditions, Charter,
    Expected observations, Session log."""
    charter_text = dedent("""\
        # A feature the examiner can verify
        ID: EXP-test-dispatch-examine-1 · Spec rows: n/a · Persona: a developer

        ## Intent
        Test the examine route and charter namespace behavior.

        ## Preconditions
        A working nWave install with `des` on PATH.

        ## Charter
        Verify the examine mode correctly loads and validates charters.

        ## Expected observations (oracle)
        - The charter namespace is readable and contains valid markdown.
        - Vera produces a clean verdict on charter content.
        - Negative: Invalid or incomplete charters are not accepted.

        ## Session log (append-only)
        | date | examiner | verdict | observations |
        |------|----------|---------|--------------|
        """)
    dst = root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(charter_text, encoding="utf-8")
    return dst


def _seed_contract_with_examine(
    root: Path,
    rel_path: str = "delivery-contract.json",
    *,
    route: str = "RED_TO_GREEN",
    examine: bool = False,
    delivery_id: str = "retarget-des-dispatch-contract",
) -> Path:
    """Write a seeded DeliveryContract under root with explicit delivery-route,
    applicability.examine, and delivery-id values."""
    dst = root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    contract = load_valid_contract()
    contract["delivery-route"] = route
    if "applicability" not in contract:
        contract["applicability"] = {}
    contract["applicability"]["examine"] = examine
    contract["delivery-id"] = delivery_id
    dst.write_text(json.dumps(contract), encoding="utf-8")
    return dst


# ---------------------------------------------------------------------------
# 1. examine=false succeeds without requiring charter namespace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delivery_route", ["RED_TO_GREEN", "GREEN_TO_GREEN"])
def test_examine_false_succeeds_without_charter_namespace(
    tmp_path: Path, delivery_route: str
) -> None:
    """When examine=false, dispatch succeeds without reading or requiring any
    charter namespace."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=False, route=delivery_route)
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"
    assert "charter" not in out.lower(), (
        f"examine=false must not mention charter; prompt=\n{out}"
    )
    assert "vera" not in out.lower(), (
        f"examine=false must not invoke Vera dispatch; prompt=\n{out}"
    )


# ---------------------------------------------------------------------------
# 2. examine=true + missing namespace refuses WHAT/WHY/HOW before prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delivery_route", ["RED_TO_GREEN", "GREEN_TO_GREEN"])
def test_examine_true_missing_namespace_refuses_before_prompt(
    tmp_path: Path, delivery_route: str
) -> None:
    """When examine=true and the charter namespace does not exist, dispatch
    refuses BEFORE rendering any dispatch prompt, with actionable diagnostics
    naming WHAT/WHY/HOW."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=True, route=delivery_route)
    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code != 0, f"must refuse; stdout={out!r} stderr={err!r}"
    assert out == "", f"no prompt may be rendered before refusal; stdout={out!r}"
    text = err.lower()
    assert "charter" in text or "namespace" in text or "examine" in text, (
        f"refusal must name WHAT failed; stderr={err!r}"
    )
    assert "why" in text or "missing" in text or "required" in text, (
        f"refusal must explain WHY; stderr={err!r}"
    )
    assert "how" in text or "create" in text or "author" in text, (
        f"refusal must say HOW to fix; stderr={err!r}"
    )


# ---------------------------------------------------------------------------
# 3. examine=true + one valid charter succeeds, projects charter path,
#    says reuse/no-rewrite, terminal Vera aggregate pass
# ---------------------------------------------------------------------------


def test_examine_true_one_valid_charter_succeeds(tmp_path: Path) -> None:
    """When examine=true and one valid filled charter exists, dispatch succeeds,
    projects the charter path in the prompt in deterministic POSIX order, states
    reuse (no charter rewrite), and preserves charters for terminal Vera
    aggregate pass."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=True, route="RED_TO_GREEN")

    # Seed one valid filled charter under the exact namespace: docs/product/expectations/{delivery-id}/.
    charter_dir = (
        tmp_path
        / "docs"
        / "product"
        / "expectations"
        / "retarget-des-dispatch-contract"
    )
    _write_filled_charter(charter_dir, "charter.md")

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"

    # Project the charter path in repo-relative POSIX order.
    expected_path = (
        "docs/product/expectations/retarget-des-dispatch-contract/charter.md"
    )
    assert expected_path in out, (
        f"charter path {expected_path!r} must be projected in prompt; prompt=\n{out}"
    )

    # State reuse/no rewrite.
    assert (
        "reuse" in out.lower()
        or "no rewrite" in out.lower()
        or ("existing" in out.lower() and "charter" in out.lower())
    ), f"prompt must state charter reuse (no rewrite); prompt=\n{out}"

    # Preserve charters for future terminal Vera aggregate pass.
    assert "vera" in out.lower(), (
        f"prompt must preserve charters for Vera; prompt=\n{out}"
    )
    assert "charter" in out.lower(), (
        f"prompt must retain charter references for Vera processing; prompt=\n{out}"
    )


# ---------------------------------------------------------------------------
# 4. examine=true + two valid charters succeeds, projects both in POSIX order
# ---------------------------------------------------------------------------


def test_examine_true_multiple_valid_charters_succeeds(tmp_path: Path) -> None:
    """When examine=true and multiple filled charters exist as direct namespace
    members, dispatch succeeds and projects every charter path in deterministic
    POSIX repo-relative order."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=True, route="GREEN_TO_GREEN")

    # Seed two valid filled charters as direct members of the namespace
    # (not nested subdirectories). A direct directory is Invalid; only direct
    # .md files are collected. Use filenames for POSIX ordering.
    charter_dir = (
        tmp_path
        / "docs"
        / "product"
        / "expectations"
        / "retarget-des-dispatch-contract"
    )
    _write_filled_charter(charter_dir, "a-charter.md")
    _write_filled_charter(charter_dir, "b-charter.md")

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"

    # Both paths in POSIX order (a before b).
    expected_path_1 = (
        "docs/product/expectations/retarget-des-dispatch-contract/a-charter.md"
    )
    expected_path_2 = (
        "docs/product/expectations/retarget-des-dispatch-contract/b-charter.md"
    )
    assert expected_path_1 in out, (
        f"first charter path {expected_path_1!r} must be projected; prompt=\n{out}"
    )
    assert expected_path_2 in out, (
        f"second charter path {expected_path_2!r} must be projected; prompt=\n{out}"
    )

    # a comes before b in the output (alphabetic POSIX order).
    idx_1 = out.find(expected_path_1)
    idx_2 = out.find(expected_path_2)
    assert idx_1 < idx_2, (
        f"charters must be ordered POSIX-deterministically; "
        f"a index={idx_1}, b index={idx_2}; prompt=\n{out}"
    )


# ---------------------------------------------------------------------------
# 5. examine=true + valid charter + one invalid direct member refuses
#    WHAT/WHY/HOW, no filtering, no partial prompt
# ---------------------------------------------------------------------------


def test_examine_true_valid_plus_invalid_charter_refuses_completely(
    tmp_path: Path,
) -> None:
    """When examine=true and one valid and one invalid charter exist in the
    same direct namespace, dispatch refuses BEFORE rendering any dispatch
    prompt with WHAT/WHY/HOW diagnostics. No filtering and no partial prompt.
    Discover validates EVERY DIRECT member, so a single invalid member blocks
    the entire namespace."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=True, route="RED_TO_GREEN")

    # Seed one valid charter in the exact namespace.
    charter_dir = (
        tmp_path
        / "docs"
        / "product"
        / "expectations"
        / "retarget-des-dispatch-contract"
    )
    _write_filled_charter(charter_dir, "a-valid.md")

    # Seed one invalid charter (unfilled, missing required sections) as a direct
    # namespace member. Discover validates every direct member.
    invalid_charter = charter_dir / "b-invalid.md"
    invalid_charter.write_text(
        "# Incomplete Charter\nID: EXP-invalid\n(missing Intent, Preconditions, etc.)",
        encoding="utf-8",
    )

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code != 0, f"must refuse; stdout={out!r} stderr={err!r}"
    assert out == "", (
        f"no partial prompt may be rendered before refusal; stdout={out!r}"
    )
    text = err.lower()
    assert "charter" in text or "invalid" in text or "unfilled" in text, (
        f"refusal must name WHAT failed; stderr={err!r}"
    )
    assert "why" in text or "missing" in text or "required" in text, (
        f"refusal must explain WHY; stderr={err!r}"
    )
    assert "how" in text or "complete" in text or "fix" in text, (
        f"refusal must say HOW to fix; stderr={err!r}"
    )


# ---------------------------------------------------------------------------
# 6. examine=true + invalid delivery-id/path token refuses before
#    charter namespace access
# ---------------------------------------------------------------------------


def test_examine_true_invalid_delivery_id_refuses_early(tmp_path: Path) -> None:
    """When examine=true and the delivery-id contains an unsafe path token
    (traversal, absolute, glob), dispatch refuses BEFORE attempting to access
    any charter namespace."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(
        tmp_path,
        examine=True,
        route="RED_TO_GREEN",
        delivery_id="../outside/invalid",
    )

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code != 0, (
        f"must refuse unsafe delivery-id; stdout={out!r} stderr={err!r}"
    )
    assert out == ""
    text = err.lower()
    assert (
        "delivery-id" in text or "path" in text or "invalid" in text or "unsafe" in text
    ), f"refusal must name the unsafe token; stderr={err!r}"


# ---------------------------------------------------------------------------
# 7. RED_TO_GREEN route renders ATD instruction to author/prove new RED oracle
# ---------------------------------------------------------------------------


def test_red_to_green_route_authors_new_red_oracle(tmp_path: Path) -> None:
    """RED_TO_GREEN delivery-route renders a complete ATD instruction to
    author a NEW acceptance oracle and prove the intended RED (failure)
    behavior before implementation."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=False, route="RED_TO_GREEN")

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"

    # RED_TO_GREEN must direct the AT author to AUTHOR (create) a new oracle.
    assert "author" in out.lower(), (
        f"RED_TO_GREEN must instruct to author a new oracle; prompt=\n{out}"
    )
    # Must also direct to PROVE the RED behavior (test failure first).
    assert "prove" in out.lower() or "red" in out.lower(), (
        f"RED_TO_GREEN must instruct to prove RED behavior; prompt=\n{out}"
    )


# ---------------------------------------------------------------------------
# 8. GREEN_TO_GREEN route binds existing locator and forbids AT mutation
# ---------------------------------------------------------------------------


def test_green_to_green_route_binds_and_forbids_mutation(tmp_path: Path) -> None:
    """GREEN_TO_GREEN delivery-route renders a complete instruction to bind
    the EXISTING contract locator/digest and explicitly forbids AT creation
    or mutation."""
    seed_dispatch_ssot(tmp_path)
    _seed_contract_with_examine(tmp_path, examine=False, route="GREEN_TO_GREEN")

    exit_code, out, err = _run(
        *_DELIVER_ARGS,
        "--repo-root",
        str(tmp_path),
        "--delivery-contract",
        "delivery-contract.json",
    )
    assert exit_code == 0, f"stdout={out!r} stderr={err!r}"

    # GREEN_TO_GREEN must direct to BIND the existing locator/digest.
    assert "bind" in out.lower() or "existing" in out.lower(), (
        f"GREEN_TO_GREEN must instruct to bind existing locator; prompt=\n{out}"
    )
    # Must explicitly forbid AT creation or mutation.
    assert (
        "forbid" in out.lower()
        or "do not" in out.lower()
        or "no creation" in out.lower()
        or "no mutation" in out.lower()
    ), f"GREEN_TO_GREEN must forbid AT creation/mutation; prompt=\n{out}"


# End READY_FOR_BOX
