"""Host claims never substitute for measured current-byte evidence or buy roles."""

from __future__ import annotations

import json
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.steps_for_the_orchestrator.conftest import asked, block, git
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_retains_native_evidence_without_provider import (
    ORACLE,
    SUPPORT,
    TARGET,
    _crafted,
)


def test_host_acceptance_cannot_record_red_implementation_or_stale_oracle(
    root: Path, step, turns: Path
):
    _crafted(root, step)
    accepted = json.dumps(
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "host completed its attempt",
                "blocked_by": None,
            }
        }
    )
    before = git(
        root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/nwave/turns"
    )
    (root / TARGET).write_text("VALUE = 2\n")
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=accepted,
    )
    assert code != 0 and block(out, err)["WHAT"] == "CraftNotGreen"
    assert (
        git(
            root,
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/nwave/turns",
        )
        == before
    )

    (root / TARGET).write_text("VALUE = 1\n")
    (root / ORACLE).write_text(
        (root / ORACLE).read_text() + "\n# host changed the selected oracle\n"
    )
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=accepted,
    )
    moved = block(out, err)
    assert code != 0 and moved["WHAT"] == "OracleRecordMoved"
    assert ORACLE in moved["WHY"] and SUPPORT not in moved["WHY"]
    measured = json.dumps(
        {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "host revised oracle",
            }
        }
    )
    assert (
        step(
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--input",
            "-",
            stdin=measured,
        )[0]
        == 0
    )
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--input",
            "-",
            stdin=accepted,
        )[0]
        == 0
    )
    assert asked(turns) == []


def test_a_moved_oracle_witness_names_the_acceptance_path_that_changed(
    root: Path, step, turns: Path
):
    """The host learns WHICH declared acceptance bytes moved, not only that some did.

    Codex retest 2026-10-01 (local-bug): a generic "restore the recorded oracle"
    sent the host to revert its own production fix twice to re-measure RED.
    """
    _crafted(root, step)
    (root / SUPPORT).write_text("MARKER = 2\n")
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--input",
        "-",
        stdin=json.dumps(
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "host completed its attempt",
                    "blocked_by": None,
                }
            }
        ),
    )
    moved = block(out, err)
    assert code != 0 and moved["WHAT"] == "OracleRecordMoved"
    assert SUPPORT in moved["WHY"] and ORACLE not in moved["WHY"]
    assert asked(turns) == []


def test_public_commands_cannot_launch_a_specialist_without_supplied_facts(root: Path):
    for arguments in (
        ["po", "--repo-root", str(root), "--project"],
        ["design", "--repo-root", str(root), "--value", "1"],
        ["oracle", "--repo-root", str(root), "--value", "1"],
        ["craft", "--repo-root", str(root), "--value", "1"],
        ["invoke-role", "--repo-root", str(root), "--role", "examiner"],
    ):
        code, out, err = run_cli_in_process(
            arguments, cwd=root, stdin_text="A request", catch_all=True
        )
        assert code != 0, (arguments, out, err)
        assert not (root / ".nwave/des/handover.json").exists()
