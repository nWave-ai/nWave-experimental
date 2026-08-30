"""CLI acceptance tests for `des fill-contract`
(Ale's construction-over-file correction, 2026-08-20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from tests.common.in_process_cli import run_cli_in_process


def _run(*args: str, cwd: Path, stdin: str | None = None) -> tuple[int, str, str]:
    return run_cli_in_process(["fill-contract", *args], cwd=cwd, stdin_text=stdin)


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


def _target(path: str) -> dict:
    target = json.loads(json.dumps(_CONTRACT["targets"]["pkg/widget.py"]))
    target["candidate"] = path
    target["overlap"] = f"{path}:1"
    return target


@st.composite
def _large_disjoint_batches(draw: st.DrawFn) -> tuple[dict, list[dict]]:
    """Every generated batch exceeds the historical 31-call ceiling."""
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


def _value_at(contract: dict, entry: dict) -> str:
    if entry["field"] == "outcome":
        return contract["outcome"]
    target = contract["targets"][entry["target"]]
    if entry["field"] == "justification":
        return target["justification"]
    return target["boundary"][entry["field"].split(".", 1)[1]]


def test_field_flag_is_retired_for_target_write(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    code, _out, _err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/widget.py",
        "--retired-field",
        "justification",
        cwd=tmp_path,
        stdin="Widget gains a ColorValidator helper.\n",
    )
    assert code != 0
    assert contract_path.read_bytes() == _seed(tmp_path).read_bytes()


def test_field_flag_is_retired_for_contract_write(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, _err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        cwd=tmp_path,
        stdin="Widget gains a validated color attribute.\n",
    )
    assert code != 0


def test_field_flag_does_not_publish_legacy_projection(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    code, out, _err = _run(
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
    assert contract_path.read_bytes() == json.dumps(_CONTRACT).encode()


def test_batch_fills_multiple_fields_and_a_later_entry_may_revise_one(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    batch = [
        {"field": "outcome", "value": "First outcome."},
        {
            "field": "justification",
            "target": "pkg/widget.py",
            "value": "Reuse the existing validator.",
        },
        {"field": "outcome", "value": "Revised outcome."},
    ]

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
    written = json.loads(contract_path.read_text(encoding="utf-8"))
    assert written["outcome"] == "Revised outcome."
    assert (
        written["targets"]["pkg/widget.py"]["justification"]
        == "Reuse the existing validator."
    )
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out


def test_batch_reports_every_invalid_entry_and_writes_nothing(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    batch = [
        {"field": "outcome", "value": "A valid entry must not leak through."},
        {
            "field": "justification",
            "target": "pkg/not-declared.py",
            "value": "Invalid target.",
        },
        {
            "field": "declared-imports",
            "target": "pkg/widget.py",
            "value": "mechanical-field",
        },
        {
            "field": "boundary.substrate-probe",
            "target": "pkg/widget.py",
            "value": "  \n",
        },
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

    assert code != 0
    assert "BLOCKED: 3 problems found in one pass" in err
    assert all(f"({index}/3) WHAT:" in err for index in range(1, 4))
    assert "pkg/not-declared.py" in err
    assert "declared-imports" in err
    assert "empty or whitespace-only" in err
    assert contract_path.read_bytes() == before


@given(case=_large_disjoint_batches())
@settings(
    max_examples=16,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_batch_size_and_order_do_not_change_disjoint_fill_results(
    tmp_path: Path, case: tuple[dict, list[dict]]
) -> None:
    contract, batch = case
    assert len(batch) > 31
    contract_path = _seed(tmp_path, contract)

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        cwd=tmp_path,
        stdin=json.dumps(batch),
    )

    assert code == 0, err
    written = json.loads(contract_path.read_text(encoding="utf-8"))
    assert all(_value_at(written, entry) == entry["value"] for entry in batch)


def test_status_reports_every_remaining_field_without_writing(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()

    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code == 0, err
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out
    assert "UNFILLED: outcome" in out
    assert "UNFILLED: targets.pkg/widget.py.justification" in out
    assert contract_path.read_bytes() == before


def test_status_reports_complete_once_every_field_is_filled(tmp_path: Path) -> None:
    contract = json.loads(json.dumps(_CONTRACT))
    contract["outcome"] = "Real outcome."
    target = contract["targets"]["pkg/widget.py"]
    target["justification"] = "Real justification."
    target["boundary"] = {
        "failure-behavior": "Real.",
        "substrate-lie": "Real.",
        "substrate-probe": "Real.",
        "double-blind-spot": "Real.",
    }
    _seed(tmp_path, contract)

    code, out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code == 0, err
    assert out.strip() == "CONTRACT-FILL-STATUS: COMPLETE"


def test_refuses_a_mechanical_field_name_at_argv_parsing(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/widget.py",
        "--retired-field",
        "declared-imports",
        cwd=tmp_path,
        stdin="cronsim.CronSim\n",
    )
    assert code != 0
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert "--status --batch" in err


def test_refuses_an_undeclared_target(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--target",
        "pkg/nonexistent.py",
        "--retired-field",
        "justification",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "--status --batch" in err
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err


def test_refuses_when_no_contract_exists_yet(tmp_path: Path) -> None:
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "--status --batch" in err


def test_revision_overwrites_an_already_filled_field(tmp_path: Path) -> None:
    contract_path = _seed(tmp_path)
    _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        cwd=tmp_path,
        stdin="First outcome.\n",
    )
    code, _out, _err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        cwd=tmp_path,
        stdin="Revised outcome.\n",
    )
    assert code != 0
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["outcome"] == "<ATD: fill>"


def test_refuses_relative_repo_root(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        ".",
        "--delivery-id",
        "widget-color",
        "--status",
        cwd=tmp_path,
    )
    assert code != 0
    assert "absolute" in err


def test_field_and_status_are_mutually_exclusive(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--retired-field",
        "outcome",
        "--status",
        cwd=tmp_path,
        stdin="Real value.\n",
    )
    assert code != 0
    assert "WHAT:" in err


# --batch-file: the provider-safe batch carrier transport (a provider-side
# Bash safety heuristic can reject a heredoc whose body mixes a brace with a
# quote character -- JSON necessarily has both -- before nWave ever sees the
# call). Both transports feed the identical JSON array into the SAME atomic
# parser/validator/publication path exercised above.


def _carrier_path(repo_root: Path, delivery_id: str) -> Path:
    return repo_root / ".des" / "fill-contract-carrier" / f"{delivery_id}.json"


def _run_batch_via(
    transport: str, tmp_path: Path, payload: str
) -> tuple[int, str, str]:
    if transport == "stdin":
        return _run(
            "--repo-root",
            str(tmp_path),
            "--delivery-id",
            "widget-color",
            "--batch",
            cwd=tmp_path,
            stdin=payload,
        )
    assert transport == "batch-file"
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(payload, encoding="utf-8")
    return _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )


@pytest.mark.parametrize("transport", ["stdin", "batch-file"])
def test_both_transports_fill_the_identical_batch_into_the_same_contract(
    tmp_path: Path, transport: str
) -> None:
    contract_path = _seed(tmp_path)
    batch = [
        {"field": "outcome", "value": "Carrier-equivalent outcome."},
        {
            "field": "justification",
            "target": "pkg/widget.py",
            "value": "Reuse the existing validator.",
        },
    ]

    code, out, err = _run_batch_via(transport, tmp_path, json.dumps(batch))

    assert code == 0, err
    written = json.loads(contract_path.read_text(encoding="utf-8"))
    assert written["outcome"] == "Carrier-equivalent outcome."
    assert (
        written["targets"]["pkg/widget.py"]["justification"]
        == "Reuse the existing validator."
    )
    assert "CONTRACT-FILL-STATUS: INCOMPLETE" in out


@pytest.mark.parametrize("transport", ["stdin", "batch-file"])
def test_both_transports_refuse_malformed_json_and_publish_nothing(
    tmp_path: Path, transport: str
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()

    code, _out, err = _run_batch_via(transport, tmp_path, "{not json")

    assert code != 0
    assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_is_removed_after_a_successful_fill(tmp_path: Path) -> None:
    _seed(tmp_path)
    carrier = _carrier_path(tmp_path, "widget-color")
    payload = json.dumps([{"field": "outcome", "value": "Carrier cleanup on success."}])

    code, _out, err = _run_batch_via("batch-file", tmp_path, payload)

    assert code == 0, err
    assert not carrier.exists()


def test_batch_file_carrier_is_removed_after_a_refused_malformed_batch(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    carrier = _carrier_path(tmp_path, "widget-color")

    code, _out, _err = _run_batch_via("batch-file", tmp_path, "{not json")

    assert code != 0
    assert not carrier.exists()


def test_batch_file_flag_without_batch_is_blocked(tmp_path: Path) -> None:
    _seed(tmp_path)
    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--status",
        "--batch-file",
        cwd=tmp_path,
    )
    assert code != 0
    assert "--batch-file" in err


def test_batch_file_missing_carrier_is_blocked_and_writes_nothing(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "no batch carrier exists" in err
    assert contract_path.read_bytes() == before


def test_batch_file_at_the_wrong_locator_is_never_read(tmp_path: Path) -> None:
    """There is no argv route to any OTHER carrier locator: a JSON array
    written anywhere but the one deterministic path is simply never found."""
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    wrong = tmp_path / "docs" / "delivery-contracts" / "widget-color.batch.json"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    wrong.write_text(json.dumps([{"field": "outcome", "value": "Wrong locator."}]))

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "no batch carrier exists" in err
    assert wrong.exists()
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_that_is_a_symlink_is_refused_and_untouched(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    target = tmp_path.parent / "outside-target.json"
    target.write_text(json.dumps([{"field": "outcome", "value": "Escaped."}]))
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.symlink_to(target)

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "not a regular file" in err
    assert carrier.is_symlink()
    assert target.exists()
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_with_invalid_utf8_is_removed_and_refused(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_bytes(b"\xff\xfe not valid utf-8")

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "not valid UTF-8" in err
    assert not carrier.exists()
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_replaced_after_acquisition_is_refused_without_deleting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the carrier at the deterministic path is swapped for a different
    file between being read and being removed, the pre-unlink identity
    check must catch the mismatch and refuse -- the replacement must never
    be deleted."""
    from des.cli import fill_contract

    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(
        json.dumps([{"field": "outcome", "value": "Original."}]), encoding="utf-8"
    )

    original_helper = fill_contract._unlink_carrier_matching_identity

    def _swap_then_check(
        carrier_path: Path, locator: str, file_descriptor: int
    ) -> int | None:
        carrier_path.unlink()
        carrier_path.write_text(
            json.dumps([{"field": "outcome", "value": "Replacement."}]),
            encoding="utf-8",
        )
        return original_helper(carrier_path, locator, file_descriptor)

    monkeypatch.setattr(
        fill_contract, "_unlink_carrier_matching_identity", _swap_then_check
    )

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "replaced" in err
    assert carrier.exists()
    assert json.loads(carrier.read_text(encoding="utf-8"))[0]["value"] == "Replacement."
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_refuses_when_refreshed_link_count_drops_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-unlink re-fstat on the still-open descriptor is the sole
    admitted signal that the carrier lost its link between acquisition and
    removal -- forcing ONLY that second fstat's st_nlink to 0 (leaving the
    real file, and the first fstat taken at open time, untouched) must
    refuse without publishing the contract or deleting the still-valid
    carrier on disk."""
    from des.cli import fill_contract

    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(
        json.dumps([{"field": "outcome", "value": "Unlinked before removal."}]),
        encoding="utf-8",
    )

    real_fstat = fill_contract.os.fstat
    calls: list[int] = []

    def _fstat_reporting_zero_links_on_the_second_call(file_descriptor: int):
        result = real_fstat(file_descriptor)
        calls.append(file_descriptor)
        if len(calls) < 2:
            return result
        return fill_contract.os.stat_result(
            (
                result.st_mode,
                result.st_ino,
                result.st_dev,
                0,
                result.st_uid,
                result.st_gid,
                result.st_size,
                result.st_atime,
                result.st_mtime,
                result.st_ctime,
            )
        )

    monkeypatch.setattr(
        fill_contract.os, "fstat", _fstat_reporting_zero_links_on_the_second_call
    )

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "already unlinked or replaced" in err
    assert carrier.exists()
    assert (
        json.loads(carrier.read_text(encoding="utf-8"))[0]["value"]
        == "Unlinked before removal."
    )
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_unlink_failure_refuses_and_leaves_contract_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(
        json.dumps([{"field": "outcome", "value": "Cleanup fails."}]),
        encoding="utf-8",
    )

    real_unlink = Path.unlink

    def _failing_unlink(self: Path, *args, **kwargs):
        if self == carrier:
            raise OSError("simulated unlink failure")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _failing_unlink)

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "could not be removed" in err
    assert carrier.exists()
    assert contract_path.read_bytes() == before


def _track_carrier_fd_reads(monkeypatch: pytest.MonkeyPatch, carrier: Path):
    """Patch `fill_contract.os.open`/`os.read` so only the exact descriptor
    opened for `carrier` is observable/interceptable -- every other read in
    the process (contract load, interpreter I/O, ...) passes through
    untouched. Returns the mutable single-item list `read_override` is
    read from: set it to a callable `(real_read, fd, length) -> bytes` to
    intercept the carrier's own read."""
    from des.cli import fill_contract

    real_open = fill_contract.os.open
    real_read = fill_contract.os.read
    carrier_fd: list[int] = []
    read_override: list = [None]

    def _tracking_open(path, flags, *args, **kwargs):
        file_descriptor = real_open(path, flags, *args, **kwargs)
        if Path(path) == carrier:
            carrier_fd.append(file_descriptor)
        return file_descriptor

    def _tracking_read(file_descriptor: int, length: int) -> bytes:
        if carrier_fd and file_descriptor == carrier_fd[0] and read_override[0]:
            return read_override[0](real_read, file_descriptor, length)
        return real_read(file_descriptor, length)

    monkeypatch.setattr(fill_contract.os, "open", _tracking_open)
    monkeypatch.setattr(fill_contract.os, "read", _tracking_read)
    return read_override


def test_batch_file_carrier_read_failure_refuses_with_identity_safe_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(
        json.dumps([{"field": "outcome", "value": "Read fails."}]),
        encoding="utf-8",
    )

    read_override = _track_carrier_fd_reads(monkeypatch, carrier)

    def _fail(real_read, file_descriptor, length):
        raise OSError("simulated read failure")

    read_override[0] = _fail

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "cannot be read" in err
    assert not carrier.exists()
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_short_read_is_refused_without_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    carrier = _carrier_path(tmp_path, "widget-color")
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_text(
        json.dumps([{"field": "outcome", "value": "Short read."}]),
        encoding="utf-8",
    )

    read_override = _track_carrier_fd_reads(monkeypatch, carrier)

    def _truncate(real_read, file_descriptor, length):
        return real_read(file_descriptor, length)[:1]

    read_override[0] = _truncate

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "byte" in err
    assert not carrier.exists()
    assert contract_path.read_bytes() == before


def test_batch_file_carrier_through_a_symlinked_ancestor_directory_is_refused(
    tmp_path: Path,
) -> None:
    contract_path = _seed(tmp_path)
    before = contract_path.read_bytes()
    escape_root = tmp_path.parent / "carrier-escape"
    (escape_root / "fill-contract-carrier").mkdir(parents=True)
    real_carrier = escape_root / "fill-contract-carrier" / "widget-color.json"
    real_carrier.write_text(json.dumps([{"field": "outcome", "value": "Escaped."}]))
    (tmp_path / ".des").symlink_to(escape_root)

    code, _out, err = _run(
        "--repo-root",
        str(tmp_path),
        "--delivery-id",
        "widget-color",
        "--batch",
        "--batch-file",
        cwd=tmp_path,
    )

    assert code != 0
    assert "escapes the repository root" in err
    assert real_carrier.exists()
    assert contract_path.read_bytes() == before
