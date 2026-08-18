"""K4 matrix row 4 -- verification command/env mismatch.

First divergence: a persisted `python3 manage.py` verification command ran
against the WRONG python3 in a clean fixture and died with
`ModuleNotFoundError`, making the K4 subject execution non-reproducible.

ADMISSION falsifier: `preflight` executes the persisted argv VERBATIM
against a clean fixture -- it runs, no ModuleNotFound.

Real execution, no faking of the interpreter: `sys.executable` importing a
module that genuinely does not exist raises a REAL ModuleNotFoundError,
which `probe_persisted_verification_commands` must catch and report.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from scripts.analysis.k4 import preflight


def _write_contract(path, commands):
    path.write_text(
        json.dumps({"verification-scope": {"commands": commands}}), encoding="utf-8"
    )


def _prepare_main_run(tmp_path, monkeypatch):
    """Shared scaffolding for a `preflight.main()` call that reaches the
    verification-probe step: bounded claude/socat stand-ins on PATH (real
    git still resolves), a real clean git checkout for --checkout, and the
    heavy packaging/probe-engagement functions stubbed so only the
    verification wiring under test actually runs. Returns (root, checkout,
    task_file)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "socat"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    git_dir = shutil.which("git")
    monkeypatch.setenv("PATH", f"{bin_dir}:{git_dir.rsplit('/', 1)[0]}")

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "config", "user.email", "k4@example.test"], cwd=checkout, check=True
    )
    subprocess.run(["git", "config", "user.name", "k4"], cwd=checkout, check=True)
    (checkout / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=checkout, check=True)

    monkeypatch.setattr(
        preflight, "build_arm_runtime_from_wheel", lambda root, wheel: root / "venv"
    )

    def _probe_engagement_stub(root, venv, auth_profile, model):
        # The real probe_engagement creates the probe workspace as a side
        # effect; stubbing it out must not silently remove that directory's
        # existence, or a later `probe_persisted_verification_commands`
        # spawn fails on a MISSING cwd (FileNotFoundError) instead of on the
        # actual verification command under test -- a defect this exact
        # helper originally had, caught only because a later test's genuine
        # ModuleNotFoundError assertion happened to tolerate either failure.
        preflight._probe_workspace(root).mkdir(parents=True, exist_ok=True)
        return ("present", [])

    monkeypatch.setattr(preflight, "probe_engagement", _probe_engagement_stub)
    monkeypatch.setattr(preflight, "cleanup_probe_workspace", lambda *a, **k: False)
    # `route_walk` builds its OWN throwaway workspace via `nwave_setup_steps`
    # (a real git clone + install) -- exactly the heavy setup this helper's
    # own docstring says is stubbed out so only the verification wiring
    # under test actually runs. Left unstubbed, every test using this
    # fixture would silently start cloning healthchecks and building a real
    # venv on every run.
    monkeypatch.setattr(
        preflight, "route_walk", lambda *a, **k: {"status": "proven", "steps": []}
    )

    root = tmp_path / "root"
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")
    return root, checkout, task_file


def test_verification_command_argv_flattens_executable_and_arguments():
    command = {
        "executable": {"kind": "toolchain", "name": "pytest"},
        "arguments": ["tests/unit/test_x.py"],
    }

    assert preflight.verification_command_argv(command) == [
        "pytest",
        "tests/unit/test_x.py",
    ]


def test_verification_command_argv_refuses_a_command_naming_no_executable():
    with pytest.raises(ValueError):
        preflight.verification_command_argv({"arguments": ["-c", "1"]})


def test_empty_verification_scope_is_refused_before_anything_runs(tmp_path):
    contract = tmp_path / "contract.json"
    _write_contract(contract, [])

    with pytest.raises(SystemExit) as excinfo:
        preflight.probe_persisted_verification_commands(contract, tmp_path)

    message = str(excinfo.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message


def test_a_command_hitting_a_real_modulenotfounderror_is_reported(tmp_path):
    """Real execution: sys.executable really does not have
    `nonexistent_module_xyz_k4` installed, so this is a genuine
    ModuleNotFoundError, not a simulated one."""
    contract = tmp_path / "contract.json"
    _write_contract(
        contract,
        [
            {
                "executable": {"kind": "interpreter", "name": sys.executable},
                "arguments": ["-c", "import nonexistent_module_xyz_k4"],
            }
        ],
    )

    problems = preflight.probe_persisted_verification_commands(contract, tmp_path)

    assert len(problems) == 1
    assert "ModuleNotFoundError" in problems[0]


def test_a_command_that_runs_clean_reports_no_problems(tmp_path):
    contract = tmp_path / "contract.json"
    _write_contract(
        contract,
        [
            {
                "executable": {"kind": "interpreter", "name": sys.executable},
                "arguments": ["-c", "print('ok')"],
            }
        ],
    )

    assert preflight.probe_persisted_verification_commands(contract, tmp_path) == []


def test_main_wires_verification_probe_and_refuses_on_modulenotfound(
    tmp_path, monkeypatch
):
    root, checkout, task_file = _prepare_main_run(tmp_path, monkeypatch)

    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"not a real wheel")
    contract = tmp_path / "contract.json"
    _write_contract(
        contract,
        [
            {
                "executable": {"kind": "interpreter", "name": sys.executable},
                "arguments": ["-c", "import nonexistent_module_xyz_k4"],
            }
        ],
    )

    code = preflight.main(
        [
            "--root",
            str(root),
            "--checkout",
            str(checkout),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
            "--contract",
            str(contract),
        ]
    )

    assert code == 1
    assert not (root / "arms.json").exists()


def test_discover_delivery_contract_returns_none_when_absent(tmp_path):
    assert preflight.discover_delivery_contract(tmp_path) is None


def test_discover_delivery_contract_returns_the_one_candidate(tmp_path):
    contracts_dir = tmp_path / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True)
    contract = contracts_dir / "some-delivery-id.json"
    contract.write_text("{}", encoding="utf-8")

    assert preflight.discover_delivery_contract(tmp_path) == contract


def test_discover_delivery_contract_refuses_ambiguity_over_more_than_one(tmp_path):
    contracts_dir = tmp_path / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "a.json").write_text("{}", encoding="utf-8")
    (contracts_dir / "b.json").write_text("{}", encoding="utf-8")

    assert preflight.discover_delivery_contract(tmp_path) is None


def test_main_without_contract_flag_prints_loud_indeterminate_and_still_proceeds(
    tmp_path, monkeypatch, capsys
):
    """ADMISSION row 4: --contract omitted, and no discoverable contract in
    the nWave arm's workspace -- main() must print a LOUD, unmissable
    INDETERMINATE line (WHAT/WHY/HOW), never silently skip the check, and
    the campaign must still proceed (a fresh preflight genuinely has no
    contract yet, before any delivery has happened)."""
    root, checkout, task_file = _prepare_main_run(tmp_path, monkeypatch)

    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"not a real wheel")

    code = preflight.main(
        [
            "--root",
            str(root),
            "--checkout",
            str(checkout),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
        ]
    )

    err = capsys.readouterr().err
    assert "INDETERMINATE" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert code == 0
    arms_json = root / "arms.json"
    assert arms_json.exists(), (
        "an unproven ADMISSION row must not block the campaign -- it is "
        "INDETERMINATE, not a FAIL"
    )
    spec = json.loads(arms_json.read_text(encoding="utf-8"))
    for arm_name in ("control", "nwave"):
        verification = spec["arms"][arm_name]["verification"]
        assert verification["status"] == "indeterminate", (
            f"GDP-8 arity corollary: the third state must reach arms.json "
            f"itself (arm {arm_name!r}), not stop at stdout/stderr"
        )
        assert verification["reason"], "the indeterminate reason must be recorded"


def test_main_discovers_and_executes_the_canonical_contract_when_flag_omitted(
    tmp_path, monkeypatch
):
    """The `docs/delivery-contracts/{DeliveryId}.json` projection ADR-SSOT-002
    Section 4c admits, discovered inside the nWave arm's probe workspace and
    executed for real -- proving the persisted argv actually runs even when
    the operator never passed --contract by hand."""
    root, checkout, task_file = _prepare_main_run(tmp_path, monkeypatch)

    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"not a real wheel")

    probe_workspace = preflight._probe_workspace(root)
    contracts_dir = probe_workspace / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True)
    _write_contract(
        contracts_dir / "some-delivery-id.json",
        [
            {
                "executable": {"kind": "interpreter", "name": sys.executable},
                "arguments": ["-c", "import nonexistent_module_xyz_k4"],
            }
        ],
    )

    code = preflight.main(
        [
            "--root",
            str(root),
            "--checkout",
            str(checkout),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
        ]
    )

    assert code == 1, (
        "the discovered contract's ModuleNotFoundError must actually refuse "
        "the run -- proving the argv was executed, not merely located"
    )
    assert not (root / "arms.json").exists()


def test_main_persists_proven_verification_status_when_contract_runs_clean(
    tmp_path, monkeypatch
):
    """GDP-8 arity corollary: the PROVEN state, not only INDETERMINATE, must
    reach arms.json -- a downstream reader must be able to distinguish
    "this campaign's row-4 ADMISSION was proven" from "it was never
    checked" without re-reading preflight's own stdout."""
    root, checkout, task_file = _prepare_main_run(tmp_path, monkeypatch)

    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"not a real wheel")
    contract = tmp_path / "contract.json"
    _write_contract(
        contract,
        [
            {
                "executable": {"kind": "interpreter", "name": sys.executable},
                "arguments": ["-c", "print('ok')"],
            }
        ],
    )

    code = preflight.main(
        [
            "--root",
            str(root),
            "--checkout",
            str(checkout),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
            "--contract",
            str(contract),
        ]
    )

    assert code == 0
    spec = json.loads((root / "arms.json").read_text(encoding="utf-8"))
    for arm_name in ("control", "nwave"):
        verification = spec["arms"][arm_name]["verification"]
        assert verification["status"] == "proven"
        assert verification["contract"] == str(contract)
        assert verification["source"] == "--contract"
