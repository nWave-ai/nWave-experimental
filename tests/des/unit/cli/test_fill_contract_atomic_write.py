"""Atomic publication oracle for the canonical DeliveryContract path."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.adapters.drivers.hooks import pre_tool_use_handler
from des.application.compile_contract import CompileContractInputs, Compiled
from des.cli import compile_contract as compile_cli
from des.cli import fill_contract as fill_cli
from tests.common.in_process_cli import run_cli_in_process


_CONTRACT = {
    "schema-version": "1.3",
    "delivery-id": "widget-color",
    "repository": {"worktree": ".", "base-revision": "git-sha1:" + "a" * 40},
    "outcome": "<ATD: fill>",
    "targets": {
        "pkg/widget.py": {
            "candidate": "pkg/widget.py",
            "overlap": "pkg/widget.py:5",
            "decision": "EXTEND",
            "justification": "<ATD: fill>",
            "declared-imports": [],
            "contract-shape": "bounded-change",
            "boundary": {
                "failure-behavior": "<ATD: fill>",
                "substrate-lie": "<ATD: fill>",
                "substrate-probe": "<ATD: fill>",
                "double-blind-spot": "<ATD: fill>",
            },
        }
    },
    "paradigm": "object_oriented",
    "delivery-route": "RED_TO_GREEN",
    "obligations": ["REUSE_CANDIDATE"],
    "acceptance-tests": {"locator": "pkg/tests/test_widget_color.py"},
    "verification-scope": {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "python"},
                "arguments": ["-m", "pytest", "-q", "pkg/tests/test_widget_color.py"],
            }
        ]
    },
    "applicability": {"independent-review": False, "examine": True},
    "budget": {"token-limit": 2_000_000, "wall-clock-minutes": 30},
}


def _seed(repo_root: Path, contract: dict | None = None) -> Path:
    contracts_dir = repo_root / "docs" / "delivery-contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    path = contracts_dir / "widget-color.json"
    path.write_text(json.dumps(contract if contract is not None else _CONTRACT))
    return path


def _run(*args: str, cwd: Path, stdin: str | None = None) -> tuple[int, str, str]:
    return run_cli_in_process(["fill-contract", *args], cwd=cwd, stdin_text=stdin)


def _target(path: str) -> dict:
    target = json.loads(json.dumps(_CONTRACT["targets"]["pkg/widget.py"]))
    target["candidate"] = path
    target["overlap"] = f"{path}:1"
    return target


@st.composite
def _transport_fitting_large_batches(
    draw: st.DrawFn,
) -> tuple[dict, list[dict[str, str]]]:
    target_count = draw(st.integers(min_value=7, max_value=12))
    contract = json.loads(json.dumps(_CONTRACT))
    contract["targets"] = {
        f"pkg/widget_{index}.py": _target(f"pkg/widget_{index}.py")
        for index in range(target_count)
    }
    entries = [{"field": "outcome", "value": "Batch outcome."}]
    for target in contract["targets"]:
        entries.extend(
            {
                "field": field,
                "target": target,
                "value": f"{target}::{field}",
            }
            for field in (
                "justification",
                "boundary.failure-behavior",
                "boundary.substrate-lie",
                "boundary.substrate-probe",
                "boundary.double-blind-spot",
            )
        )
    return contract, list(draw(st.permutations(entries)))


def _entry_value(contract: dict, entry: dict[str, str]) -> str:
    if entry["field"] == "outcome":
        return contract["outcome"]
    target = contract["targets"][entry["target"]]
    if entry["field"] == "justification":
        return target["justification"]
    return target["boundary"][entry["field"].split(".", 1)[1]]


def _interrupt_during_write(
    original_write_text: Callable[..., int],
) -> Callable[..., int]:
    def interrupted(path: Path, data: str, *args: object, **kwargs: object) -> int:
        # Model KillDuringWrite: some bytes reach the current write target,
        # then the writer dies before publication can complete.
        original_write_text(path, data[: max(1, len(data) // 3)], *args, **kwargs)
        raise RuntimeError("simulated kill during write")

    return interrupted


@given(case=_transport_fitting_large_batches())
@settings(
    max_examples=16,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_one_batch_fills_every_value_beyond_the_historical_31_call_ceiling(
    tmp_path: Path, case: tuple[dict, list[dict[str, str]]]
) -> None:
    contract, batch = case
    assert len(batch) > 31
    canonical = _seed(tmp_path, contract)

    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=tmp_path,
        stdin=json.dumps(batch),
    )

    assert code == 0, err
    assert "CONTRACT-FILL-STATUS: COMPLETE" in out
    written = json.loads(canonical.read_text(encoding="utf-8"))
    assert all(_entry_value(written, entry) == entry["value"] for entry in batch)


def test_large_batch_reports_all_detectable_problems_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    canonical = _seed(tmp_path)
    before = canonical.read_bytes()
    batch = [
        {"field": "outcome", "value": f"Valid revision {index}."} for index in range(32)
    ]
    batch.extend(
        [
            {
                "field": "justification",
                "target": "pkg/not-declared.py",
                "value": "Invalid target.",
            },
            {
                "field": "declared-imports",
                "target": "pkg/widget.py",
                "value": "Mechanical field.",
            },
            {
                "field": "boundary.substrate-probe",
                "target": "pkg/widget.py",
                "value": "  \n",
            },
        ]
    )
    assert len(batch) > 31

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=tmp_path,
        stdin=json.dumps(batch),
    )

    assert code == 2
    assert "BLOCKED: 3 problems found in one pass" in err
    assert all(f"({index}/3) WHAT:" in err for index in range(1, 4))
    assert "pkg/not-declared.py" in err
    assert "declared-imports" in err
    assert "empty or whitespace-only" in err
    assert canonical.read_bytes() == before


def test_explicit_null_target_is_malformed_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    canonical = _seed(tmp_path)
    before = canonical.read_bytes()
    batch = [
        {
            "field": "outcome",
            "value": "Null target must be malformed when its key is present.",
            "target": None,
        }
    ]

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=tmp_path,
        stdin=json.dumps(batch),
    )

    assert code == 2
    assert all(label in err for label in ("WHAT:", "WHY:", "HOW:"))
    assert "target" in err
    assert "string when present" in err
    assert canonical.read_bytes() == before


@pytest.mark.parametrize(
    ("extra_args", "payload", "diagnostic_fragments"),
    [
        (
            ("--target", "ignored.py"),
            json.dumps([{"field": "outcome", "value": "Must not publish."}]),
            ("--batch", "--target"),
        ),
        ((), "{", ("JSON",)),
        ((), json.dumps({"field": "outcome"}), ("array",)),
        ((), json.dumps([]), ("empty", "array")),
        ((), json.dumps([42]), ("entry", "object")),
    ],
    ids=(
        "target-is-forbidden-in-batch-mode",
        "malformed-json",
        "non-array-json",
        "empty-array",
        "non-object-entry",
    ),
)
def test_invalid_batch_transport_is_actionable_and_never_publishes(
    tmp_path: Path,
    extra_args: tuple[str, ...],
    payload: str,
    diagnostic_fragments: tuple[str, ...],
) -> None:
    canonical = _seed(tmp_path)
    before = canonical.read_bytes()

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        *extra_args,
        cwd=tmp_path,
        stdin=payload,
    )

    assert code == 2
    assert all(label in err for label in ("WHAT:", "WHY:", "HOW:"))
    assert err.strip()
    assert canonical.read_bytes() == before


def test_duplicate_json_member_key_is_actionable_and_never_publishes(
    tmp_path: Path,
) -> None:
    canonical = _seed(tmp_path)
    before = canonical.read_bytes()
    payload = (
        '[{"field":"declared-imports","field":"outcome","value":"accepted last wins"}]'
    )

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=tmp_path,
        stdin=payload,
    )

    assert code == 2
    assert all(label in err for label in ("WHAT:", "WHY:", "HOW:"))
    assert "duplicate" in err.casefold()
    assert "field" in err.casefold()
    assert canonical.read_bytes() == before


def test_real_atd_hook_admits_one_quoted_batch_larger_than_31_entries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    batch = [{"field": "outcome", "value": f"Revision {index}."} for index in range(32)]
    command = (
        "des fill-contract --repo-root /repo --delivery-id widget-color "
        "--batch <<'NW_FILL'\n"
        f"{json.dumps(batch)}\n"
        "NW_FILL"
    )
    envelope = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "agent_type": "nw-acceptance-designer",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(envelope)))

    assert pre_tool_use_handler.handle_pre_tool_use() == 0
    output = capsys.readouterr().out.strip()
    decision = json.loads(output) if output else None
    assert decision is None or decision.get("decision") != "block"


def test_retired_scalar_write_is_rejected_and_status_remains_read_only(
    tmp_path: Path,
) -> None:
    canonical = _seed(tmp_path)
    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        cwd=tmp_path,
        stdin="  Legacy outcome.  \n",
    )
    assert code != 0
    assert out == ""
    assert canonical.read_bytes() == _seed(tmp_path).read_bytes()

    before_status = canonical.read_bytes()
    code, status_out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code == 0, err
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in status_out
    assert canonical.read_bytes() == before_status


def test_interrupted_fill_never_changes_canonical_bytes_and_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = _seed(tmp_path)
    before = canonical.read_bytes()
    original_write_text = Path.write_text

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps([{"field": "outcome", "value": "First outcome."}])),
    )
    with monkeypatch.context() as interrupted:
        interrupted.setattr(
            Path,
            "write_text",
            _interrupt_during_write(original_write_text),
        )
        with pytest.raises(RuntimeError, match="simulated kill"):
            fill_cli.main(
                [
                    "--repo-root",
                    str(tmp_path),
                    "--delivery-id",
                    "widget-color",
                    "--batch",
                ]
            )

    assert canonical.read_bytes() == before
    json.loads(canonical.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps([{"field": "outcome", "value": "Recovered outcome."}])),
    )
    assert (
        fill_cli.main(
            [
                "--repo-root",
                str(tmp_path),
                "--delivery-id",
                "widget-color",
                "--batch",
            ]
        )
        == 0
    )
    recovered = json.loads(canonical.read_text(encoding="utf-8"))
    assert recovered["outcome"] == "Recovered outcome."


def test_interrupted_first_compile_never_publishes_torn_canonical_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "docs" / "delivery-contracts" / "widget-color.json"
    contract = json.loads(json.dumps(_CONTRACT))
    inputs = CompileContractInputs(
        repo_root=tmp_path,
        delivery_id="widget-color",
        brief_text="sealed authority",
        delivery_route="RED_TO_GREEN",
        paradigm="object_oriented",
        examine=True,
        budget_token_limit=2_000_000,
        budget_wall_clock_minutes=30,
        independent_review=False,
    )
    parsed = SimpleNamespace(architecture_authority="ARCHITECTURE-COVERED: x.md#x")
    parser = SimpleNamespace(parse_args=lambda _argv: parsed)
    monkeypatch.setattr(compile_cli, "_parser", lambda: parser)
    monkeypatch.setattr(compile_cli, "resolve_inputs", lambda _args: inputs)
    monkeypatch.setattr(
        compile_cli,
        "compile_delivery_contract",
        lambda _inputs: Compiled(contract=contract),
    )
    monkeypatch.setattr(
        compile_cli,
        "refuse_schema_invalid_skeleton",
        lambda *_args, **_kwargs: None,
    )
    original_write_text = Path.write_text

    with monkeypatch.context() as interrupted:
        interrupted.setattr(
            Path,
            "write_text",
            _interrupt_during_write(original_write_text),
        )
        with pytest.raises(RuntimeError, match="simulated kill"):
            compile_cli.main([])

    assert not canonical.exists()
    assert compile_cli.main([]) == 0
    assert json.loads(canonical.read_text(encoding="utf-8")) == contract
