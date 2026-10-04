"""Fresh verification is an execution, not recovery of an older green receipt."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import block
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_retains_native_evidence_without_provider import (
    ORACLE,
    _crafted,
)


def test_public_fresh_reexecutes_and_failed_fresh_revokes_active_green(
    root: Path, step, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = [
        sys.executable,
        "-c",
        "import os, sys, uuid, pytest; "
        "status = pytest.main([sys.argv[1], '-q']); "
        "print('EXECUTED_TEST', uuid.uuid4(), flush=True); "
        "raise SystemExit(status or int(os.environ.get('FIXTURE_FAIL', '0')))",
        ORACLE,
    ]
    second_command = [
        sys.executable,
        "-c",
        "import uuid; from product_value import VALUE; "
        "assert VALUE == 1; print('SECOND_CHECK', uuid.uuid4())",
    ]
    declared_commands = [command, second_command]
    _crafted(root, step, verification=declared_commands)
    log_root = root / ".nwave/des/logs/native"
    setup_records = {p: p.read_bytes() for p in log_root.glob("*.json")}
    config_path = root / ".nwave/config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config["verification"] = {"reuse": {"outputs": ["target"]}}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config))
    calls = []

    def verify(*flags: str):
        argv = ("verify", "--repo-root", str(root), *flags)
        result = step(*argv)
        calls.append(
            {"argv": argv, "exit": result[0], "stdout": result[1], "stderr": result[2]}
        )
        destination = os.environ.get("NWAVE_REUSE_PROOF_DIR")
        if destination:
            directory = Path(destination)
            directory.mkdir(parents=True, exist_ok=True)
            native = {
                str(path.relative_to(root)): json.loads(path.read_text())
                for path in (root / ".nwave/des/logs/native").glob("*.json")
            }
            (directory / "public-fresh-receipts.json").write_text(
                json.dumps({"calls": calls, "native": native}, indent=2) + "\n"
            )
        return result

    code, out, err = verify("--fresh")
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    original = {p: p.read_bytes() for p in log_root.glob("*.json")}
    assert set(original) > set(setup_records), (
        "Fresh execution lost its evidence; persist native stdout and exit separately from setup."
    )

    code, out, err = verify()
    assert code == 0, out + err
    assert "RECORDED" in out + err, (
        "Default recovery did not identify historical evidence; keep RECORDED distinct from measured execution."
    )
    assert {p: p.read_bytes() for p in log_root.glob("*.json")} == original, (
        "Default recovery changed receipts; recover existing evidence without re-executing."
    )

    code, out, err = verify("--fresh")
    assert code == 0, out + err
    assert block(out, err)["CANDIDATE"] == candidate, (
        "Unchanged fresh execution changed candidate identity; reuse the exact matching candidate."
    )
    fresh = {p: p.read_bytes() for p in log_root.glob("*.json")}
    assert set(fresh) > set(original), (
        "Fresh execution reused its receipt; persist this execution separately from historical evidence."
    )
    for path, content in original.items():
        assert fresh[path] == content, (
            "Fresh verification rewrote history; retain previous receipts unchanged."
        )
    observations = [
        json.loads(content)
        for path, content in fresh.items()
        if path not in setup_records
    ]
    for observation in observations:
        assert [item["argv"] for item in observation] == declared_commands, (
            "Fresh verification dropped a declared check; execute the complete ordered command population."
        )
        assert (
            "EXECUTED_TEST" in observation[0]["stdout"]
            and "1 passed" in observation[0]["stdout"]
        ), "A receipt lacks the executed oracle; freshly execute every required check."
        assert "SECOND_CHECK" in observation[1]["stdout"], (
            "The independent assertion did not execute; run all declared checks rather than only the oracle."
        )
    for index in range(len(declared_commands)):
        outputs = [observation[index]["stdout"] for observation in observations]
        assert len(set(outputs)) == len(outputs), (
            "Execution nonces were replayed; execute each native command on every --fresh invocation."
        )

    monkeypatch.setenv("FIXTURE_FAIL", "7")
    code, out, err = verify("--fresh")
    assert code != 0, out + err
    assert "VerificationFailed" in out + err, (
        "The failing native command was not reported; return its measured failure instead of an older GREEN."
    )
    failures = [
        json.loads(path.read_text())
        for path in log_root.glob("*.json")
        if path not in fresh
    ]
    assert failures, (
        "Failed fresh execution lost its receipt; preserve the measured failure outside the mutable workspace."
    )
    for observation in failures:
        assert [item["argv"] for item in observation] == declared_commands, (
            "A failed check suppressed another declared check; execute the complete fresh command population."
        )
    code, out, err = verify()
    assert code != 0, out + err
    assert "RECORDED" not in out + err, (
        "An old GREEN survived failed fresh execution; revoke active approval before executing."
    )
    for path, content in fresh.items():
        assert (
            hashlib.sha256(path.read_bytes()).digest()
            == hashlib.sha256(content).digest()
        ), (
            "Failure destroyed earlier evidence; revoke active approval without rewriting history."
        )
