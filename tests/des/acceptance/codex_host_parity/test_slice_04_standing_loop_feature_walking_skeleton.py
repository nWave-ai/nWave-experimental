"""The feature's single installed-artifact standing-loop walking skeleton.

Vera reloop: in a fresh disposable project ``des --help`` was unreachable.
This test consumes the exact PyPI-shape wheel through a clean venv install and
drives the installed ``des`` console script, never a source import or runner.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
from tests.e2e.conftest import pypi_shape_wheel  # noqa: F401 -- pytest fixture


pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.walking_skeleton,
    pytest.mark.wiring_e2e,
    pytest.mark.negative_at,
]


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _runtime_requirements(candidate: Path) -> tuple[str, ...]:
    with zipfile.ZipFile(candidate) as archive:
        metadata_path = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = archive.read(metadata_path).decode("utf-8")
    return tuple(re.findall(r"^Requires-Dist:\s*(.+)$", metadata, re.MULTILINE))


def _requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    assert match is not None
    return match.group(0).replace("_", "-").lower()


def _json_result(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    stderr = completed.stderr or ""
    lowered_stderr = stderr.lower()
    forbidden_stderr = (
        "traceback (most recent call last)",
        "-----begin private key-----",
        "-----begin rsa private key-----",
        "password=",
        "access_token=",
    )
    assert not any(marker in lowered_stderr for marker in forbidden_stderr), (
        "WHAT: the installed command exposed a traceback or secret-shaped material "
        "on stderr. WHY: stderr may carry diagnostics but must remain safe for an "
        "operator terminal. HOW: translate faults at the public boundary and redact "
        f"sensitive values. stderr={stderr!r}"
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            "WHAT: an installed `des loop --format json` command emitted no single "
            "des.loop.command-result.v1 object. WHY: operators cannot recover durable "
            "identity from prose, tracebacks, or empty output. HOW: route every public "
            f"verb through the shared JSON projector. output={completed.stdout!r}"
        ) from None
    assert isinstance(value, dict)
    assert value.get("schema_version") == "des.loop.command-result.v1", (
        "WHAT: stdout did not contain exactly one des.loop.command-result.v1 object. "
        "WHY: auxiliary stderr diagnostics must not change the public JSON protocol. "
        "HOW: emit one command result on stdout and keep auxiliary diagnostics on "
        f"stderr. stdout={completed.stdout!r}; stderr={stderr!r}"
    )
    return value


def _durable_events(ledger: Path) -> list[dict[str, object]]:
    """Read only event envelopes the installed CLI durably shipped.

    The acceptance oracle deliberately discovers JSON rows rather than importing
    ledger classes or naming an implementation table: ``des.loop.event.v1`` is
    the public durable-artifact contract.
    """
    assert ledger.is_file(), (
        "WHAT: the installed command did not ship a durable loop ledger. "
        "WHY: command stdout alone cannot prove that continuation state survives a "
        "fresh process. HOW: persist des.loop.event.v1 envelopes in the project "
        "ledger before reporting a successful mutation."
    )
    with sqlite3.connect(ledger) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        values: list[object] = []
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            values.extend(
                value
                for row in connection.execute(f"SELECT * FROM {quoted}")
                for value in row
            )
    envelopes: list[dict[str, object]] = []
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(decoded, dict)
            and decoded.get("schema_version") == "des.loop.event.v1"
        ):
            envelopes.append(decoded)
    return envelopes


def _event_time(event: dict[str, object]) -> datetime:
    value = event.get("recorded_at")
    assert isinstance(value, str) and value, (
        "WHAT: a durable loop event has no recorded_at timestamp. WHY: the operator "
        "cannot determine whether a tombstone preceded an attestation. HOW: write an "
        "RFC3339 recorded_at field into every des.loop.event.v1 envelope."
    )
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_installed_des_offers_truthful_bounded_loop_control(
    pypi_shape_wheel: Path,
    tmp_path: Path,
) -> None:
    """One public candidate supports truthful dry-run and fail-restrictive refusal."""
    # covers: R1 R2 R3 R4 R5 R6 R7 R8 R9 R10 R11
    project = tmp_path / "fresh-project"
    isolated_home = tmp_path / "isolated-home"
    wheelhouse = pypi_shape_wheel.parent / "offline-wheelhouse"
    dependency_lock = wheelhouse / "requirements.lock"
    pipx_home = tmp_path / "pipx-home"
    pipx_bin = tmp_path / "pipx-bin"
    project.mkdir()
    isolated_home.mkdir()
    pipx_bin.mkdir()

    requirements = _runtime_requirements(pypi_shape_wheel)
    required_names = {
        _requirement_name(requirement)
        for requirement in requirements
        if "extra ==" not in requirement
    }
    handoff_observations = {
        "offline_wheelhouse_present": wheelhouse.is_dir(),
        "dependency_lock_present": dependency_lock.is_file(),
    }
    assert all(handoff_observations.values()), (
        "WHAT: the exact public candidate handoff lacks its deterministic offline "
        "dependency closure. WHY: normal pipx install upgrades its bootstrap pip and "
        "resolves candidate Requires-Dist entries; without a wheelhouse and lock it "
        "retries live PyPI and can leave operators with no `des` executable. "
        "HOW: emit `offline-wheelhouse/requirements.lock` beside the candidate wheel "
        "and place the locked pip bootstrap plus every runtime dependency wheel in "
        f"that directory. observations={handoff_observations}; "
        f"required_runtime_distributions={sorted(required_names)}"
    )
    locked_names = {
        _requirement_name(line)
        for line in dependency_lock.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {"pip", *required_names} <= locked_names, (
        "WHAT: the handoff dependency lock is incomplete. WHY: pipx requires its "
        "bootstrap pip and the candidate requires every Requires-Dist entry offline. "
        "HOW: lock pip and every runtime distribution named by candidate metadata. "
        f"locked={sorted(locked_names)}; required={sorted({'pip', *required_names})}"
    )

    pipx = shutil.which("pipx")
    assert pipx is not None, (
        "WHAT: the public-install acceptance environment has no pipx executable. "
        "WHY: the charter requires the normal supported pipx install surface. "
        "HOW: install the project's pipx test prerequisite and rerun this scope."
    )
    install_env = os.environ.copy()
    install_env.update(
        {
            "PIPX_HOME": str(pipx_home),
            "PIPX_BIN_DIR": str(pipx_bin),
            "PIPX_MAN_DIR": str(tmp_path / "pipx-man"),
            "PIPX_DEFAULT_PYTHON": sys.executable,
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": str(wheelhouse),
        }
    )
    install_env.pop("PYTHONPATH", None)
    install = _run(
        [
            pipx,
            "install",
            "--force",
            "--python",
            sys.executable,
            "--pip-args",
            f"--no-index --find-links {wheelhouse}",
            str(pypi_shape_wheel),
        ],
        cwd=project,
        env=install_env,
    )

    des = pipx_bin / ("des.exe" if os.name == "nt" else "des")
    clean_env = os.environ.copy()
    clean_env.update(
        {
            "HOME": str(isolated_home),
            "PATH": os.pathsep.join((str(pipx_bin), os.environ.get("PATH", ""))),
            "XDG_CACHE_HOME": str(isolated_home / ".cache"),
            "XDG_CONFIG_HOME": str(isolated_home / ".config"),
            "XDG_DATA_HOME": str(isolated_home / ".local" / "share"),
        }
    )
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("VIRTUAL_ENV", None)

    help_command = [str(des), "loop", "--help"]
    probe_command = [
        str(des),
        "loop",
        "probe",
        "--project",
        str(project),
        "--context",
        "reconstructed",
        "--format",
        "json",
    ]
    inspect_command = [
        str(des),
        "loop",
        "inspect",
        "--project",
        str(project),
        "--format",
        "json",
    ]
    dry_command = [
        str(des),
        "loop",
        "arm",
        "--project",
        str(project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "dry-run-key",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
        "--dry-run",
        "--format",
        "json",
    ]
    native_refusal_command = [
        str(des),
        "loop",
        "arm",
        "--project",
        str(project),
        "--loop",
        "standing",
        "--context",
        "native_chat",
        "--idempotency-key",
        "native-without-proof",
        "--format",
        "json",
    ]
    if des.is_file():
        help_result = _run(help_command, cwd=project, env=clean_env)
        probe = _run(probe_command, cwd=project, env=clean_env)
        inspect = _run(inspect_command, cwd=project, env=clean_env)
        dry_run = _run(dry_command, cwd=project, env=clean_env)
        unproved_native = _run(native_refusal_command, cwd=project, env=clean_env)
    else:
        unavailable = (
            "installed des executable is absent because normal pipx dependency "
            f"resolution failed: {install.stdout}"
        )
        help_result = subprocess.CompletedProcess(help_command, 127, unavailable)
        probe = subprocess.CompletedProcess(probe_command, 127, unavailable)
        inspect = subprocess.CompletedProcess(inspect_command, 127, unavailable)
        dry_run = subprocess.CompletedProcess(dry_command, 127, unavailable)
        unproved_native = subprocess.CompletedProcess(
            native_refusal_command, 127, unavailable
        )

    help_output = help_result.stdout.lower()
    dry_output = dry_run.stdout.lower()
    refusal_output = unproved_native.stdout.lower()
    ledger = project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    observations = {
        "runtime_metadata_excludes_pip": all(
            _requirement_name(requirement) != "pip" for requirement in requirements
        ),
        "candidate_installed": install.returncode == 0,
        "public_des_exists": des.is_file(),
        "all_seven_verbs_exposed": all(
            verb in help_output
            for verb in ("probe", "inspect", "list", "arm", "tick", "recover", "stop")
        ),
        "probe_succeeded": probe.returncode == 0,
        "inspect_succeeded": inspect.returncode == 0,
        "dry_run_succeeded": dry_run.returncode == 0,
        "dry_run_disclosed_reconstructed_context": "reconstructed" in dry_output,
        "dry_run_disclosed_limits": "max_tokens_per_tick" in dry_output,
        "dry_run_did_not_create_ledger": not ledger.exists(),
        "unproved_native_context_refused": unproved_native.returncode != 0,
        "refusal_states_what_why_how": all(
            word in refusal_output for word in ("what", "why", "how")
        ),
    }

    assert all(observations.values()), (
        "WHAT: the installed public standing-loop surface is incomplete or untruthful. "
        "WHY: a source-green facade cannot satisfy operators when the exact candidate "
        "declares pip as a runtime dependency, does not install `des` through normal "
        "offline-resolved pipx semantics, omits a non-mutating reconstructed dry-run, or "
        "refuse unproved native context with WHAT/WHY/HOW. "
        "HOW: keep pip out of runtime Requires-Dist, ship and register the `des loop` "
        "public entry in the PyPI candidate, "
        "route dry-run through standing-loop control without ledger mutation, and "
        "make native_chat_required fail-restrictive. "
        f"requirements={requirements}; observations={observations}; "
        f"pipx_install_output={install.stdout!r}; help_output={help_result.stdout!r}; "
        f"probe_output={probe.stdout!r}; inspect_output={inspect.stdout!r}; "
        f"dry_run_output={dry_run.stdout!r}; "
        f"refusal_output={unproved_native.stdout!r}"
    )

    probe_event = _json_result(probe)
    inspect_event = _json_result(inspect)
    dry_event = _json_result(dry_run)
    refusal_event = _json_result(unproved_native)
    assert (
        probe_event["schema_version"]
        == inspect_event["schema_version"]
        == dry_event["schema_version"]
        == ("des.loop.command-result.v1")
    )
    assert probe_event["event_type"] == "LOOP_PROBED"
    assert dry_event["event_type"] == "LOOP_ARM_PLANNED"
    assert dry_event["status"] == "ok" and dry_event["resources"]["authorised"]
    assert refusal_event["status"] == "refused"
    assert refusal_event["diagnostic"]["code"] == "CONTEXT_CONTINUITY_UNPROVED"
    assert not ledger.exists()

    def public(
        *args: str,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        completed = _run(
            [str(des), "loop", *args, "--format", "json"],
            cwd=project,
            env=clean_env,
        )
        return completed, _json_result(completed)

    arm_result, armed = public(
        "arm",
        "--project",
        str(project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "arm-once",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    handle_id = armed["selection"]["handle_id"]
    list_result, listed = public("list", "--project", str(project))
    tick_result, ticked = public(
        "tick",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
        "--idempotency-key",
        "tick-once",
    )
    recover_result, recovered = public(
        "recover",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
    )
    recover_apply_result, recovered_applied = public(
        "recover",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
        "--apply",
        "--idempotency-key",
        "recover-once",
    )
    stop_result, stopped = public(
        "stop",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
        "--idempotency-key",
        "stop-once",
    )
    repeat_stop_result, repeat_stopped = public(
        "stop",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
        "--idempotency-key",
        "stop-again",
    )
    journey = (
        arm_result,
        list_result,
        tick_result,
        recover_result,
        recover_apply_result,
        stop_result,
        repeat_stop_result,
    )
    assert all(result.returncode == 0 for result in journey)
    assert armed["state"]["desired"] == "ARMED"
    assert listed["state"]["desired"] == "ARMED"
    # EXAMINE reloop: all three hostile requests must be refused at the installed
    # public boundary before they can claim a handle, occurrence, or progress.
    # Keep these in this feature's sole walking skeleton rather than adding more
    # subprocess-E2E tests for the same command.
    invalid_limit_project = tmp_path / "invalid-limit-project"
    invalid_limit_result, invalid_limit = public(
        "arm",
        "--project",
        str(invalid_limit_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "zero-budget-must-not-arm",
        "--max-tokens",
        "0",
        "--max-wall-seconds",
        "30",
    )
    invalid_limit_ledger = (
        invalid_limit_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )

    foreign_project = tmp_path / "foreign-project"
    foreign_project.mkdir()
    foreign_arm_result, foreign_armed = public(
        "arm",
        "--project",
        str(foreign_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "foreign-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    foreign_ledger = foreign_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    assert foreign_arm_result.returncode == 0 and foreign_ledger.is_file()
    foreign_handle_id = foreign_armed["selection"]["handle_id"]
    foreign_ledger_before = hashlib.sha256(foreign_ledger.read_bytes()).hexdigest()
    cross_project_result, cross_project = public(
        "tick",
        "--project",
        str(foreign_project),
        "--handle",
        str(handle_id),
        "--idempotency-key",
        "foreign-handle-must-not-claim",
    )
    foreign_ledger_after = hashlib.sha256(foreign_ledger.read_bytes()).hexdigest()

    stopped_tick_result, stopped_tick = public(
        "tick",
        "--project",
        str(project),
        "--handle",
        str(handle_id),
        "--idempotency-key",
        "must-not-run-after-stop",
    )

    def refusal_has_diagnostic(result: dict[str, object], code: str) -> bool:
        diagnostic = result.get("diagnostic")
        return (
            isinstance(diagnostic, dict)
            and diagnostic.get("code") == code
            and all(diagnostic.get(field) for field in ("what", "why", "how"))
        )

    safety_observations = {
        "invalid_limit_exit_2": invalid_limit_result.returncode == 2,
        "invalid_limit_closed_refusal": (
            invalid_limit.get("event_type") == "LOOP_COMMAND_REFUSED"
            and invalid_limit.get("status") == "refused"
            and refusal_has_diagnostic(invalid_limit, "INVALID_LIMIT")
        ),
        "invalid_limit_no_handle_or_ledger": (
            "selection" not in invalid_limit and not invalid_limit_ledger.exists()
        ),
        "foreign_handle_exit_3": cross_project_result.returncode == 3,
        "foreign_handle_closed_refusal": (
            cross_project.get("event_type") == "LOOP_COMMAND_REFUSED"
            and cross_project.get("status") == "refused"
            and refusal_has_diagnostic(cross_project, "PROJECT_MISMATCH")
        ),
        "foreign_handle_no_claim_attestation_or_leak": (
            "attestation" not in cross_project
            and "selection" not in cross_project
            and foreign_ledger_before == foreign_ledger_after
            and str(foreign_handle_id) != str(handle_id)
        ),
        "stopped_handle_exit_5": stopped_tick_result.returncode == 5,
        "stopped_handle_closed_refusal": (
            stopped_tick.get("event_type") == "LOOP_COMMAND_REFUSED"
            and stopped_tick.get("status") == "refused"
            and refusal_has_diagnostic(stopped_tick, "HANDLE_STOPPED")
        ),
        "stopped_handle_no_tick_attestation": "attestation" not in stopped_tick,
    }
    assert all(safety_observations.values()), (
        "WHAT: the installed public loop command accepted an invalid resource bound, "
        "a foreign handle, or a stopped handle. WHY: each path can mint, leak, or "
        "misrepresent authority for continued work. HOW: validate non-positive limits "
        "before mutation; bind handle lookup to ProjectId before a claim; and revalidate "
        "the tombstone before tick. expected closed refusals are INVALID_LIMIT/2, "
        "PROJECT_MISMATCH/3, and HANDLE_STOPPED/5, all as LOOP_COMMAND_REFUSED with "
        f"WHAT/WHY/HOW. observations={safety_observations}; "
        f"invalid_limit={invalid_limit}; cross_project={cross_project}; "
        f"stopped_tick={stopped_tick}"
    )

    # EXAMINE reloop: selectors are authority, not display decoration.  These
    # hostile requests use an existing opaque handle from another project, then
    # compare the SUT's own durable artifact before/after every refusal.
    selector_project = tmp_path / "selector-project"
    selector_arm_result, selector_armed = public(
        "arm",
        "--project",
        str(selector_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "selector-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    selector_ledger = (
        selector_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )
    assert selector_arm_result.returncode == 0 and selector_ledger.is_file()
    selector_before = hashlib.sha256(selector_ledger.read_bytes()).hexdigest()
    selector_list_result, selector_list = public(
        "list", "--project", str(selector_project), "--handle", str(foreign_handle_id)
    )
    selector_after_list = hashlib.sha256(selector_ledger.read_bytes()).hexdigest()
    selector_recover_result, selector_recover = public(
        "recover",
        "--project",
        str(selector_project),
        "--handle",
        str(foreign_handle_id),
    )
    selector_after_recover = hashlib.sha256(selector_ledger.read_bytes()).hexdigest()
    selector_stop_result, selector_stop = public(
        "stop",
        "--project",
        str(selector_project),
        "--handle",
        str(foreign_handle_id),
        "--idempotency-key",
        "foreign-stop-must-not-rebind",
    )
    selector_after_stop = hashlib.sha256(selector_ledger.read_bytes()).hexdigest()
    selector_list_after_result, selector_list_after = public(
        "list", "--project", str(selector_project)
    )
    selector_observations = {
        "all_foreign_selector_calls_exit_3": all(
            result.returncode == 3
            for result in (
                selector_list_result,
                selector_recover_result,
                selector_stop_result,
            )
        ),
        "all_foreign_selector_calls_are_closed_refusals": all(
            event.get("event_type") == "LOOP_COMMAND_REFUSED"
            and event.get("status") == "refused"
            and refusal_has_diagnostic(event, "PROJECT_MISMATCH")
            and "selection" not in event
            and "attestation" not in event
            for event in (selector_list, selector_recover, selector_stop)
        ),
        "foreign_selectors_never_mutate": (
            selector_before
            == selector_after_list
            == selector_after_recover
            == selector_after_stop
        ),
        "foreign_stop_did_not_stop_local_handle": (
            selector_list_after_result.returncode == 0
            and selector_list_after["state"]["desired"] == "ARMED"
            and selector_list_after["selection"]["handle_id"]
            == selector_armed["selection"]["handle_id"]
        ),
    }
    assert all(selector_observations.values()), (
        "WHAT: list, recover, or stop accepted a foreign opaque handle or changed the "
        "local loop despite refusing no authority. WHY: a selector cannot be rebound to "
        "the current project without crossing an operator boundary. HOW: validate every "
        "handle selector against ProjectId before lookup, reconciliation, or tombstone "
        f"write. observations={selector_observations}; list={selector_list}; "
        f"recover={selector_recover}; stop={selector_stop}"
    )

    empty_selector_project = tmp_path / "empty-selector-project"
    empty_selector_project.mkdir()
    empty_selector_ledger = (
        empty_selector_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )
    empty_selector_result, empty_selector = public(
        "list",
        "--project",
        str(empty_selector_project),
        "--handle",
        str(foreign_handle_id),
    )
    assert (
        empty_selector_result.returncode == 3
        and empty_selector.get("event_type") == "LOOP_COMMAND_REFUSED"
        and empty_selector.get("status") == "refused"
        and refusal_has_diagnostic(empty_selector, "PROJECT_MISMATCH")
        and "selection" not in empty_selector
        and "attestation" not in empty_selector
        and not empty_selector_ledger.exists()
    ), (
        "WHAT: a foreign opaque selector against a project with no local loop was "
        "treated as an empty local listing or caused a lookup artifact. WHY: authority "
        "validation cannot depend on first finding local state; that leaks selector "
        "semantics and permits fail-open rebinding. HOW: validate the opaque handle's "
        "ProjectId before lookup, output selection, or ledger creation and return "
        f"PROJECT_MISMATCH/3. result={empty_selector}; "
        f"ledger_exists={empty_selector_ledger.exists()}"
    )

    forged_proof_project = tmp_path / "forged-proof-project"
    forged_proof_result, forged_proof = public(
        "arm",
        "--project",
        str(forged_proof_project),
        "--loop",
        "standing",
        "--context",
        "native_chat",
        "--continuity-proof",
        "self-asserted-not-a-host-receipt",
        "--idempotency-key",
        "forged-proof-must-not-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    forged_proof_ledger = (
        forged_proof_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )
    assert (
        forged_proof_result.returncode == 5
        and forged_proof.get("event_type") == "LOOP_COMMAND_REFUSED"
        and forged_proof.get("status") == "refused"
        and refusal_has_diagnostic(forged_proof, "CONTEXT_CONTINUITY_UNPROVED")
        and "selection" not in forged_proof
        and not forged_proof_ledger.exists()
    ), (
        "WHAT: a self-asserted native continuity string armed a standing loop. WHY: "
        "native-chat authority requires a fresh host-issued, project- and challenge-bound "
        "receipt, not proof-shaped user input. HOW: verify the ContinuityProofReceipt's "
        "project, host composition, challenge response, and freshness before any ledger "
        f"mutation. result={forged_proof}"
    )

    idempotency_project = tmp_path / "idempotency-project"
    first_idempotency_result, first_idempotency = public(
        "arm",
        "--project",
        str(idempotency_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "same-key-different-request",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    idempotency_ledger = (
        idempotency_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )
    assert first_idempotency_result.returncode == 0 and idempotency_ledger.is_file()
    idempotency_before = hashlib.sha256(idempotency_ledger.read_bytes()).hexdigest()
    conflict_result, conflict = public(
        "arm",
        "--project",
        str(idempotency_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "same-key-different-request",
        "--max-tokens",
        "1199",
        "--max-wall-seconds",
        "30",
    )
    idempotency_after = hashlib.sha256(idempotency_ledger.read_bytes()).hexdigest()
    assert (
        conflict_result.returncode == 4
        and conflict.get("event_type") == "LOOP_COMMAND_REFUSED"
        and conflict.get("status") == "refused"
        and refusal_has_diagnostic(conflict, "IDEMPOTENCY_CONFLICT")
        and "selection" not in conflict
        and idempotency_before == idempotency_after
        and first_idempotency["selection"]["handle_id"]
    ), (
        "WHAT: reusing an arm idempotency key for a different normalized request did "
        "not fail closed. WHY: a key is an authority receipt, not a hint to overwrite "
        "limits on an existing handle. HOW: seal the normalized request digest with the "
        "first receipt and return IDEMPOTENCY_CONFLICT/4 before mutation. "
        f"conflict={conflict}"
    )

    # Every public mutating verb that accepts an idempotency key seals the whole
    # normalized request.  Generation changes provide a public, non-production
    # oracle for a different request while retaining ProjectId + verb + key.
    verb_project = tmp_path / "all-verb-idempotency-project"
    first_generation_result, first_generation = public(
        "arm",
        "--project",
        str(verb_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "generation-one-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert first_generation_result.returncode == 0
    first_generation_handle = str(first_generation["selection"]["handle_id"])
    first_tick_result, _ = public(
        "tick",
        "--project",
        str(verb_project),
        "--handle",
        first_generation_handle,
        "--idempotency-key",
        "same-tick-key-different-generation",
    )
    first_recover_result, _ = public(
        "recover",
        "--project",
        str(verb_project),
        "--handle",
        first_generation_handle,
        "--apply",
        "--idempotency-key",
        "same-recover-key-different-generation",
    )
    first_stop_result, _ = public(
        "stop",
        "--project",
        str(verb_project),
        "--handle",
        first_generation_handle,
        "--idempotency-key",
        "same-stop-key-different-generation",
    )
    assert all(
        result.returncode == 0
        for result in (first_tick_result, first_recover_result, first_stop_result)
    )
    second_generation_result, second_generation = public(
        "arm",
        "--project",
        str(verb_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "generation-two-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert second_generation_result.returncode == 0
    second_generation_handle = str(second_generation["selection"]["handle_id"])
    verb_ledger = verb_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    verb_before = hashlib.sha256(verb_ledger.read_bytes()).hexdigest()
    conflicting_tick_result, conflicting_tick = public(
        "tick",
        "--project",
        str(verb_project),
        "--handle",
        second_generation_handle,
        "--idempotency-key",
        "same-tick-key-different-generation",
    )
    conflicting_recover_result, conflicting_recover = public(
        "recover",
        "--project",
        str(verb_project),
        "--handle",
        second_generation_handle,
        "--apply",
        "--idempotency-key",
        "same-recover-key-different-generation",
    )
    conflicting_stop_result, conflicting_stop = public(
        "stop",
        "--project",
        str(verb_project),
        "--handle",
        second_generation_handle,
        "--idempotency-key",
        "same-stop-key-different-generation",
    )
    verb_after = hashlib.sha256(verb_ledger.read_bytes()).hexdigest()
    verb_conflicts = (
        (conflicting_tick_result, conflicting_tick),
        (conflicting_recover_result, conflicting_recover),
        (conflicting_stop_result, conflicting_stop),
    )
    assert (
        first_generation_handle == second_generation_handle
        and all(
            result.returncode == 4
            and event.get("event_type") == "LOOP_COMMAND_REFUSED"
            and event.get("status") == "refused"
            and refusal_has_diagnostic(event, "IDEMPOTENCY_CONFLICT")
            and "selection" not in event
            and "attestation" not in event
            for result, event in verb_conflicts
        )
        and verb_before == verb_after
    ), (
        "WHAT: tick, recover --apply, or stop silently scoped idempotency more "
        "narrowly than the declared public `(ProjectId, verb, key)` contract. WHY: "
        "a generation is part of the normalized authority request; replaying a key "
        "against a new generation must not execute, reconcile, or tombstone it. HOW: "
        "seal and compare request digests for every key-accepting mutating verb, or "
        "remove the unsupported key from that verb's public grammar. "
        f"conflicts={verb_conflicts}; ledger_unchanged={verb_before == verb_after}"
    )

    # RELOOP_C / R13: accepted scope selectors are part of the authority request,
    # not inert decoration.  A delivery may instead remove an unsupported selector
    # from the grammar; in that case argparse must reject it before touching the
    # pre-existing durable ledger.  This keeps the public oracle independent of
    # parser or ledger implementation details.
    scope_project = tmp_path / "scope-idempotency-project"
    scope_arm_result, scope_armed = public(
        "arm",
        "--project",
        str(scope_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "scope-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert scope_arm_result.returncode == 0
    scope_handle = str(scope_armed["selection"]["handle_id"])
    scope_ledger = scope_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"

    def changed_scope_is_closed(*arguments: str, ledger_before: str) -> bool:
        completed = _run(
            [str(des), "loop", *arguments, "--format", "json"],
            cwd=project,
            env=clean_env,
        )
        ledger_after = hashlib.sha256(scope_ledger.read_bytes()).hexdigest()
        if completed.returncode == 2:
            # A parser rejection is the permitted alternative when a selector is
            # deliberately removed from public grammar.  It still must precede
            # effect or durable mutation.
            return ledger_after == ledger_before
        event = _json_result(completed)
        diagnostic = event.get("diagnostic")
        return (
            completed.returncode == 4
            and event.get("event_type") == "LOOP_COMMAND_REFUSED"
            and event.get("status") == "refused"
            and isinstance(diagnostic, dict)
            and diagnostic.get("code") == "IDEMPOTENCY_CONFLICT"
            and all(diagnostic.get(field) for field in ("what", "why", "how"))
            and "selection" not in event
            and "attestation" not in event
            and ledger_after == ledger_before
        )

    first_scope_tick_result, _ = public(
        "tick",
        "--project",
        str(scope_project),
        "--handle",
        scope_handle,
        "--idempotency-key",
        "scope-tick-key",
    )
    assert first_scope_tick_result.returncode == 0
    tick_scope_before = hashlib.sha256(scope_ledger.read_bytes()).hexdigest()
    tick_scope_closed = changed_scope_is_closed(
        "tick",
        "--project",
        str(scope_project),
        "--handle",
        scope_handle,
        "--idempotency-key",
        "scope-tick-key",
        "--occurrence",
        "different-occurrence-selector",
        ledger_before=tick_scope_before,
    )

    first_scope_recover_result, _ = public(
        "recover",
        "--project",
        str(scope_project),
        "--handle",
        scope_handle,
        "--apply",
        "--idempotency-key",
        "scope-recover-key",
    )
    assert first_scope_recover_result.returncode == 0
    recover_scope_before = hashlib.sha256(scope_ledger.read_bytes()).hexdigest()
    recover_scope_closed = changed_scope_is_closed(
        "recover",
        "--project",
        str(scope_project),
        "--all",
        "--apply",
        "--idempotency-key",
        "scope-recover-key",
        ledger_before=recover_scope_before,
    )

    first_scope_stop_result, _ = public(
        "stop",
        "--project",
        str(scope_project),
        "--handle",
        scope_handle,
        "--idempotency-key",
        "scope-stop-key",
    )
    assert first_scope_stop_result.returncode == 0
    stop_scope_before = hashlib.sha256(scope_ledger.read_bytes()).hexdigest()
    stop_scope_closed = changed_scope_is_closed(
        "stop",
        "--project",
        str(scope_project),
        "--all",
        "--idempotency-key",
        "scope-stop-key",
        ledger_before=stop_scope_before,
    )
    assert tick_scope_closed and recover_scope_closed and stop_scope_closed, (
        "WHAT: a public scope selector was ignored while replaying the same "
        "idempotency key. WHY: `(ProjectId, verb, key)` is safe only when its "
        "receipt seals the complete normalized selector scope. HOW: include "
        "--occurrence/--all in the keyed request digest and refuse changed reuse "
        "with IDEMPOTENCY_CONFLICT/4, or reject an unsupported selector before "
        "effect and without mutating the ledger. "
        f"tick={tick_scope_closed}; recover={recover_scope_closed}; "
        f"stop={stop_scope_closed}"
    )

    assert ticked["event_type"] == "LOOP_TICKED"
    assert ticked["attestation"]["requested_digest"]
    assert ticked["attestation"]["outcome"] == "changed", (
        "WHAT: the installed executable tick returned no_change instead of progressing "
        "the declared continuation. WHY: a legitimate no-change attestation is distinct, "
        "but cannot satisfy this charter's progress outcome. HOW: execute and observe one "
        "bounded semantic action before issuing a changed receipt."
    )
    assert ticked["attestation"]["observed_digest"]
    assert ticked["resources"]["authorised"] and ticked["resources"]["consumed"]
    authorised = ticked["resources"]["authorised"]
    consumed = ticked["resources"]["consumed"]
    assert set(consumed) == {
        "tokens",
        "wall_seconds",
        "agent_concurrency",
        "box_concurrency",
    }
    assert 0 < consumed["tokens"] <= authorised["max_tokens_per_tick"]
    assert 0 < consumed["wall_seconds"] <= authorised["max_wall_seconds"]
    assert 0 < consumed["agent_concurrency"] <= authorised["max_agent_concurrency"]
    assert 0 < consumed["box_concurrency"] <= authorised["max_box_concurrency"]
    assert ticked["isolation"]["receipt_id"]
    execution_receipt = ticked["attestation"].get("execution_receipt")
    resource_receipt = ticked["resources"].get("measurement_receipt")
    assert (
        isinstance(execution_receipt, dict)
        and execution_receipt.get("executor_id")
        and execution_receipt.get("effect_id")
        and execution_receipt.get("effect_digest")
        == ticked["attestation"]["observed_digest"]
        and execution_receipt.get("observed_at")
        and execution_receipt.get("resource_receipt_id")
        and isinstance(resource_receipt, dict)
        and resource_receipt.get("receipt_id")
        == execution_receipt["resource_receipt_id"]
        and resource_receipt.get("measured_at")
        and resource_receipt.get("source")
        and resource_receipt.get("consumed") == consumed
    ), (
        "WHAT: the installed tick claimed changed progress without an executor-observed "
        "effect receipt and one source-linked measurement receipt for all four resources. "
        "WHY: a deterministic digest or hard-coded resource values can describe a request "
        "without proving any bounded semantic action occurred. HOW: obtain the observed "
        "effect from the real tick executor, bind its digest to the attestation, and "
        "project the executor's measured token/time/agent/box receipt unchanged. "
        f"attestation={ticked['attestation']}; resources={ticked['resources']}"
    )
    effect_path = project / str(execution_receipt["effect_id"])
    executor_measurement = execution_receipt.get("resource_measurement")
    assert (
        effect_path.is_file()
        and hashlib.sha256(effect_path.read_bytes()).hexdigest()
        == execution_receipt["effect_digest"]
        and isinstance(executor_measurement, dict)
        and executor_measurement.get("schema_version")
        == "des.loop.resource-measurement.v1"
        and executor_measurement.get("source") == "executor_observed"
        and executor_measurement.get("effect_digest")
        == execution_receipt["effect_digest"]
        and executor_measurement.get("consumed") == consumed
        and resource_receipt.get("measurement_id")
        == executor_measurement.get("measurement_id")
    ), (
        "WHAT: the resource receipt can be reconstructed from an effect digest or "
        "fixed constants instead of carrying executor-observed measurements. WHY: "
        "cross-project resource limits require evidence from the executor that applied "
        "the bound effect, not two agreeing projections of synthetic values. HOW: have "
        "the executor emit one versioned measurement bound to the observed effect bytes "
        "and project that measurement unchanged into the public receipt. "
        f"execution_receipt={execution_receipt}; resource_receipt={resource_receipt}"
    )

    # RELOOP_C / R14: two changed executions make provenance falsifiable.  A
    # single top-level measurement ID cannot show that agent/box values were
    # actually observed rather than copied from a fixed one-process default.
    measurement_project = tmp_path / "measurement-provenance-project"
    measurement_arm_result, measurement_armed = public(
        "arm",
        "--project",
        str(measurement_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "measurement-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert measurement_arm_result.returncode == 0
    measurement_handle = str(measurement_armed["selection"]["handle_id"])
    measurement_ticks = [
        public(
            "tick",
            "--project",
            str(measurement_project),
            "--handle",
            measurement_handle,
            "--idempotency-key",
            key,
        )
        for key in ("measurement-first-effect", "measurement-second-effect")
    ]
    assert all(result.returncode == 0 for result, _event in measurement_ticks)

    def executor_observations(event: dict[str, object]) -> dict[str, dict[str, object]]:
        attestation = event.get("attestation")
        assert isinstance(attestation, dict)
        receipt = attestation.get("execution_receipt")
        assert isinstance(receipt, dict)
        measurement = receipt.get("resource_measurement")
        assert isinstance(measurement, dict)
        observations = measurement.get("resource_receipts")
        assert isinstance(observations, dict)
        public_consumed = event.get("resources", {}).get("consumed")
        assert isinstance(public_consumed, dict)
        observed_effect = receipt.get("effect_digest")
        executor_id = receipt.get("executor_id")
        expected_resources = {
            "tokens",
            "wall_seconds",
            "agent_concurrency",
            "box_concurrency",
        }
        assert set(observations) == expected_resources
        assert set(public_consumed) == expected_resources
        assert all(
            isinstance(observation, dict)
            and observation.get("resource") == resource
            and observation.get("value") == public_consumed[resource]
            and observation.get("executor_id") == executor_id
            and observation.get("effect_digest") == observed_effect
            and observation.get("observed_at")
            and observation.get("measurement_id")
            for resource, observation in observations.items()
        )
        assert (
            len(
                {
                    str(observation["measurement_id"])
                    for observation in observations.values()
                }
            )
            == 4
        )
        return observations

    first_measurement_event = measurement_ticks[0][1]
    second_measurement_event = measurement_ticks[1][1]
    first_resource_observations = executor_observations(first_measurement_event)
    second_resource_observations = executor_observations(second_measurement_event)
    first_effect_digest = first_measurement_event["attestation"]["observed_digest"]
    second_effect_digest = second_measurement_event["attestation"]["observed_digest"]
    assert first_effect_digest != second_effect_digest and {
        str(observation["measurement_id"])
        for observation in first_resource_observations.values()
    }.isdisjoint(
        {
            str(observation["measurement_id"])
            for observation in second_resource_observations.values()
        }
    ), (
        "WHAT: a changed execution reused resource provenance. WHY: fixed agent/box "
        "constants or digest-shaped projections can agree with public output without "
        "being measured by the executor. HOW: emit one executor-issued receipt per "
        "resource, bind each to its observed effect digest, and mint fresh measurement "
        "IDs when the executor observes a different effect. "
        f"first={first_resource_observations}; second={second_resource_observations}"
    )
    assert recovered["event_type"] == "LOOP_RECOVERY_PLANNED"
    assert recovered["selection"]["handle_id"] == handle_id
    assert recovered["attestation"]["id"] == ticked["attestation"]["id"]
    assert recovered["attestation"]["outcome"] == "changed"
    assert (
        recovered["attestation"]["observed_digest"]
        == ticked["attestation"]["observed_digest"]
    )
    assert stopped["state"]["observed"] == "STOPPED"
    assert repeat_stopped["state"]["observed"] == "STOPPED"
    assert repeat_stopped["replayed"] is False
    assert recovered_applied["event_type"] == "LOOP_RECOVERED", (
        "WHAT: `recover --apply` did not report an applied recovery. WHY: a recovery "
        "plan is not durable progress until the operator explicitly applies it. HOW: "
        "record the application and emit LOOP_RECOVERED only after that transition."
    )

    durable_events = _durable_events(ledger)
    required_event_types = {
        "LOOP_ARMED",
        "TICK_CLAIMED",
        "EFFECT_APPLIED",
        "TICK_ATTESTED",
        "RECOVERY_APPLIED",
        "STOP_REQUESTED",
        "STOP_OBSERVED",
    }
    observed_event_types = {event.get("event_type") for event in durable_events}
    common_event_fields = {
        "event_id",
        "recorded_at",
        "ProjectId",
        "HandleId",
        "generation",
        "fence_epoch",
        "idempotency_key_digest",
        "request_digest",
    }
    malformed_events = [
        event
        for event in durable_events
        if not common_event_fields <= set(event)
        or not all(event.get(field) for field in common_event_fields)
        or event.get("HandleId") != handle_id
    ]
    claim_events = [
        event for event in durable_events if event.get("event_type") == "TICK_CLAIMED"
    ]
    attested_events = [
        event for event in durable_events if event.get("event_type") == "TICK_ATTESTED"
    ]
    effect_events = [
        event for event in durable_events if event.get("event_type") == "EFFECT_APPLIED"
    ]
    assert (
        required_event_types <= observed_event_types
        and not malformed_events
        and all(
            event.get("OccurrenceId") for event in (*claim_events, *attested_events)
        )
        and len(claim_events) == len(effect_events) == len(attested_events) == 1
        and _event_time(claim_events[0])
        <= _event_time(effect_events[0])
        <= _event_time(attested_events[0])
        and claim_events[0].get("fence_token")
        == effect_events[0].get("fence_token")
        == attested_events[0].get("fence_token")
        and effect_events[0].get("effect_digest")
        == ticked["attestation"]["observed_digest"]
        and isinstance(attested_events[0].get("attestation"), dict)
        and attested_events[0]["attestation"].get("id") == ticked["attestation"]["id"]
    ), (
        "WHAT: the installed ledger did not preserve the complete des.loop.event.v1 "
        "mutation history with identity, timestamp, request, claim, attestation, recovery, "
        "effect, and stop evidence. WHY: stdout cannot establish a durable ordering or prove that "
        "a later process recovered the same authority. HOW: append immutable envelopes for "
        "the closed event set and seal the public tick attestation in TICK_ATTESTED. "
        f"event_types={observed_event_types}; malformed={malformed_events}; "
        f"events={durable_events}"
    )

    # This is a real public-process race, not an in-process monkeypatch.  It
    # must remain valid regardless of whether tick or stop wins scheduling: the
    # durable order may never contain a tick attestation after STOP_OBSERVED.
    race_project = tmp_path / "multiprocess-stop-tick-race"
    race_arm_result, race_armed = public(
        "arm",
        "--project",
        str(race_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "race-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert race_arm_result.returncode == 0
    race_handle = str(race_armed["selection"]["handle_id"])
    race_tick_command = [
        str(des),
        "loop",
        "tick",
        "--project",
        str(race_project),
        "--handle",
        race_handle,
        "--idempotency-key",
        "race-tick",
        "--format",
        "json",
    ]
    race_stop_command = [
        str(des),
        "loop",
        "stop",
        "--project",
        str(race_project),
        "--handle",
        race_handle,
        "--idempotency-key",
        "race-stop",
        "--format",
        "json",
    ]
    tick_process = subprocess.Popen(
        race_tick_command,
        cwd=project,
        env=clean_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stop_process = subprocess.Popen(
        race_stop_command,
        cwd=project,
        env=clean_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tick_stdout, tick_stderr = tick_process.communicate(timeout=120)
    stop_stdout, stop_stderr = stop_process.communicate(timeout=120)
    race_tick = subprocess.CompletedProcess(
        race_tick_command, tick_process.returncode, tick_stdout, tick_stderr
    )
    race_stop = subprocess.CompletedProcess(
        race_stop_command, stop_process.returncode, stop_stdout, stop_stderr
    )
    race_tick_event = _json_result(race_tick)
    race_stop_event = _json_result(race_stop)
    race_ledger = race_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    race_events = _durable_events(race_ledger)
    stop_observed_events = [
        event for event in race_events if event.get("event_type") == "STOP_OBSERVED"
    ]
    race_attestations = [
        event for event in race_events if event.get("event_type") == "TICK_ATTESTED"
    ]
    race_claims = [
        event for event in race_events if event.get("event_type") == "TICK_CLAIMED"
    ]
    race_effects = [
        event for event in race_events if event.get("event_type") == "EFFECT_APPLIED"
    ]
    assert (
        tick_process.pid != stop_process.pid
        and race_stop.returncode == 0
        and race_tick.returncode in {0, 5}
        and race_stop_event.get("event_type") == "LOOP_STOPPED"
        and len(stop_observed_events) == 1
        and all(
            _event_time(effect) < _event_time(stop_observed_events[0])
            for effect in race_effects
        )
        and all(
            isinstance(effect.get("fence_epoch"), int)
            and isinstance(stop_observed_events[0].get("fence_epoch"), int)
            and effect["fence_epoch"] < stop_observed_events[0]["fence_epoch"]
            for effect in race_effects
        )
        and all(
            claim.get("fence_token") == effect.get("fence_token")
            for claim in race_claims
            for effect in race_effects
            if claim.get("OccurrenceId") == effect.get("OccurrenceId")
        )
        and all(
            _event_time(attestation) < _event_time(stop_observed_events[0])
            for attestation in race_attestations
        )
        and (
            race_tick_event.get("event_type") != "LOOP_TICKED"
            or (
                bool(race_attestations)
                and _event_time(race_attestations[-1])
                < _event_time(stop_observed_events[0])
            )
        )
    ), (
        "WHAT: two real installed CLI processes produced, or projected, a tick "
        "attestation after durable STOP_OBSERVED. WHY: a process-local lock cannot fence "
        "a separate process once its tombstone commits. HOW: make claim/finalization and "
        "stop use one cross-process transactional decision, then project HANDLE_STOPPED "
        "without an attestation whenever stop wins. "
        f"tick_pid={tick_process.pid}; stop_pid={stop_process.pid}; "
        f"tick={race_tick_event}; stop={race_stop_event}; events={race_events}"
    )

    # Two independent installed processes using one occurrence authority may
    # replay one durable result; they may not both cross the executor boundary.
    duplicate_project = tmp_path / "duplicate-occurrence-race"
    duplicate_arm_result, duplicate_arm = public(
        "arm",
        "--project",
        str(duplicate_project),
        "--loop",
        "standing",
        "--context",
        "reconstructed",
        "--idempotency-key",
        "duplicate-race-arm",
        "--max-tokens",
        "1200",
        "--max-wall-seconds",
        "30",
    )
    assert duplicate_arm_result.returncode == 0
    duplicate_handle = str(duplicate_arm["selection"]["handle_id"])
    duplicate_command = [
        str(des),
        "loop",
        "tick",
        "--project",
        str(duplicate_project),
        "--handle",
        duplicate_handle,
        "--idempotency-key",
        "one-occurrence-two-processes",
        "--format",
        "json",
    ]
    duplicate_processes = [
        subprocess.Popen(
            duplicate_command,
            cwd=project,
            env=clean_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    duplicate_results = []
    for process in duplicate_processes:
        stdout, stderr = process.communicate(timeout=120)
        duplicate_results.append(
            subprocess.CompletedProcess(
                duplicate_command, process.returncode, stdout, stderr
            )
        )
    duplicate_outputs = [_json_result(result) for result in duplicate_results]
    duplicate_events = _durable_events(
        duplicate_project / ".nwave" / "standing-loops" / "ledger-v1.sqlite3"
    )
    duplicate_effects = [
        event
        for event in duplicate_events
        if event.get("event_type") == "EFFECT_APPLIED"
        and event.get("OccurrenceId") == "one-occurrence-two-processes"
    ]
    duplicate_attestations = [
        event
        for event in duplicate_events
        if event.get("event_type") == "TICK_ATTESTED"
        and event.get("OccurrenceId") == "one-occurrence-two-processes"
    ]
    assert (
        all(result.returncode == 0 for result in duplicate_results)
        and len(duplicate_effects) == 1
        and len(duplicate_attestations) == 1
        and len({output["attestation"]["id"] for output in duplicate_outputs}) == 1
        and sorted(bool(output.get("replayed")) for output in duplicate_outputs)
        == [False, True]
    ), (
        "WHAT: two processes sharing one occurrence authority crossed the executor "
        "boundary more than once or produced divergent receipts. WHY: an idempotent "
        "attestation after duplicate effects cannot undo duplicated semantic work. HOW: "
        "claim the occurrence with one durable unique fence before execution; the loser "
        "waits for and replays the winner's receipt without executing. "
        f"outputs={duplicate_outputs}; events={duplicate_events}"
    )
