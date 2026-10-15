"""Frozen original inputs remain byte-identical and explicitly non-executable.

Driving port: the incumbent public pytest node and existing EOF/Git commands.
@contract-shape: real-io. The original pre-normalized authority must refuse with
DesignFactsPreNormalized and a same-scope replace-current remedy.
No observer plugin, alternate HOME, private helper or prompt implementation is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


CHECKOUT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).resolve().with_name("fixture") / "run5"
INCUMBENT_NODE = (
    "tests/des/acceptance/atd_prompt_dedup/test_role_receives_lossless_facts.py"
    "::test_supplied_prompt_fits_attestation_and_repeats_without_manual_removal"
)


@dataclass(frozen=True)
class FrozenInput:
    name: str
    relative_path: Path
    byte_length: int
    sha256: str


ORIGINAL_INPUTS = (
    FrozenInput(
        "original run5 handover",
        Path(".nwave/des/handover.json"),
        529073,
        "833ef043034cdc4e8c2e0dcf3db3fc29ae33b487ae4210c8120f23724d3f65be",
    ),
    FrozenInput(
        "original ROOT caller context",
        Path("root.txt"),
        98,
        "2298035414b878c5d77dfbe6bec6d254248ed96b6343243c61ea78b477563aba",
    ),
)


def _read_original_inputs() -> tuple[bytes, ...]:
    contents = []
    for original in ORIGINAL_INPUTS:
        path = FIXTURE / original.relative_path
        assert path.is_file(), (
            f"WHAT: checkout fixture {original.name} is missing at {path}. "
            "WHY: this regression requires the frozen original input, not an ambient substitute. "
            "HOW: binary-copy the authorized original into its declared repository fixture."
        )
        data = path.read_bytes()
        actual = (len(data), hashlib.sha256(data).hexdigest())
        expected = (original.byte_length, original.sha256)
        assert actual == expected, (
            f"WHAT: {original.name} identity is {actual}, expected {expected}. "
            "WHY: different bytes do not reproduce the original-run5 attestation. "
            "HOW: restore the exact authorized binary copy; do not serialize, normalize or substitute it."
        )
        contents.append(data)
    return tuple(contents)


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    # Prefix candidate source paths without discarding native caller probe paths
    # or the inherited Git isolation. No process-global environment is changed.
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(CHECKOUT / "src"), str(CHECKOUT), environment.get("PYTHONPATH", "")]
    )
    return subprocess.run(
        argv,
        cwd=CHECKOUT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _successful(
    result: subprocess.CompletedProcess[str], operation: str, remediation: str
) -> None:
    assert result.returncode == 0, (
        f"WHAT: {operation} exited {result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n"
        "WHY: the required native observation did not succeed; collection/runtime failure is not attestation success. "
        f"HOW: {remediation}."
    )


def _run_frozen_attestation() -> None:
    before = _read_original_inputs()
    paths = [
        str((FIXTURE / original.relative_path).relative_to(CHECKOUT))
        for original in ORIGINAL_INPUTS
    ]
    versioned = _run(["git", "ls-files", "--error-unmatch", "--", *paths])
    _successful(
        versioned,
        "versioned original fixture lookup",
        "version both exact fixture files in the actual candidate, not only in local staging",
    )

    attestation = _run([sys.executable, "-m", "pytest", "-q", "-rA", INCUMBENT_NODE])
    _successful(
        attestation,
        "existing original-run5 refusal observation",
        "use the exact frozen fixture and retain repeated refusal, DesignFactsPreNormalized, replace-current remediation and unchanged-input assertions; restore native runtime if collection/setup failed",
    )
    payloads = [
        line.partition("NWAVE_TEST_RESULT:")[2]
        for line in attestation.stdout.splitlines()
        if "NWAVE_TEST_RESULT:" in line
    ]
    try:
        results = [json.loads(payload) for payload in payloads]
    except json.JSONDecodeError as error:
        pytest.fail(
            f"WHAT: the selected incumbent emitted an unreadable native result: {error}.\n"
            f"stdout:\n{attestation.stdout}\nstderr:\n{attestation.stderr}\n"
            "WHY: an unreadable result cannot distinguish actual success from skipped or unexecuted attestation. "
            "HOW: restore the existing NWAVE_TEST_RESULT JSON emission in the native pytest runtime."
        )
    expected_result = {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "exit_status": 0,
    }
    passed = (
        len(results) == 1
        and isinstance(results[0], dict)
        and all(results[0].get(key) == value for key, value in expected_result.items())
    )
    assert passed, (
        f"WHAT: native results for the one explicitly selected incumbent are {results!r}; expected one result containing {expected_result!r}.\n"
        f"stdout:\n{attestation.stdout}\nstderr:\n{attestation.stderr}\n"
        "WHY: a skip, deselection or empty collection does not exercise the existing attestation. "
        "HOW: run the exact incumbent node without skipping or fallback in the declared pytest runtime."
    )
    assert _read_original_inputs() == before, (
        "WHAT: a frozen input changed during the incumbent attestation. "
        "WHY: the original regression promises unchanged inputs. "
        "HOW: retain the existing read-only input behavior and restore the exact fixture bytes."
    )

    eof = _run(
        [sys.executable, "scripts/hooks/check_end_of_file.py", "--check", *paths]
    )
    _successful(
        eof,
        "exact fixture EOF check",
        "add only the frozen no-final-LF handover to the existing exact-file exception",
    )
    attributes = _run(["git", "check-attr", "-z", "text", "--", *paths])
    _successful(
        attributes,
        "effective frozen fixture Git attributes",
        "restore native Git and add the two exact-path -text entries after text=auto",
    )
    expected = [part for path in paths for part in (path, "text", "unset")] + [""]
    assert attributes.stdout.split("\0") == expected, (
        f"WHAT: effective frozen text attributes are {attributes.stdout!r}, expected {expected!r}. "
        "WHY: checkout text conversion must not change either historical input. "
        "HOW: add only the two exact frozen-path -text entries after the general text=auto rule."
    )
    assert _read_original_inputs() == before, (
        "WHAT: native byte-policy checks changed a frozen input. "
        "WHY: necessary EOF/Git handling must preserve the authorized bytes. "
        "HOW: keep the policy checks read-only and restore the exact original fixture bytes."
    )


@pytest.mark.acceptance
@pytest.mark.integration
def test_existing_attestation_uses_exact_versioned_original_inputs():
    _run_frozen_attestation()
