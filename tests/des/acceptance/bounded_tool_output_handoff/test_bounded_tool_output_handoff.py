# @feature-bounded-tool-output-handoff
"""Public active-RED contract for bounded command-output handoff."""

from __future__ import annotations

import base64
import hashlib
import json
import shlex
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


_FEATURE_ID = "bounded-tool-output-handoff"
_BOUND_BYTES = 2_048


def _dispatch(
    workspace: Path,
    log: Path,
    *,
    command: str = "uv run pytest -q",
    result: str = "exit=1",
) -> tuple[int, str, str]:
    """Drive the installed public ``des dispatch`` entry in-process."""
    return run_cli_in_process(
        [
            "dispatch",
            "--mode",
            "atdd_pure",
            "--project-id",
            _FEATURE_ID,
            "--slice",
            "slice-01",
            "--phase",
            "A_GREEN",
            "--tool-output-log",
            str(log),
            "--tool-command",
            command,
            "--tool-result",
            result,
        ],
        cwd=workspace,
        catch_all=True,
    )


def _retrieve(workspace: Path, details_command: str) -> tuple[int, str, str]:
    """Drive the public details command exactly as the compact result names it."""
    argv = shlex.split(details_command)
    assert argv[:2] == ["des", "dispatch"], (
        "WHAT: the compact handoff did not name a public DES details command; "
        "WHY: a developer must not reconstruct hidden retrieval state; "
        "HOW: emit a runnable `des dispatch --show-tool-output <record>` command."
    )
    return run_cli_in_process(argv[1:], cwd=workspace)


def _assert_actionable_refusal(exit_code: int, stdout: str, stderr: str) -> None:
    """Pin that an untrusted handoff never turns into a success-shaped record."""
    diagnostic = f"{stdout}\n{stderr}".lower()
    assert exit_code != 0, (
        "WHAT: an invalid evidence handoff exited successfully; "
        "WHY: a success exit can certify evidence that was never safely retained; "
        "HOW: refuse non-zero until the handoff or record passes its public integrity checks."
    )
    assert all(word in diagnostic for word in ("what", "why", "how")), (
        "WHAT: an invalid evidence handoff did not explain the refusal; "
        "WHY: a developer cannot distinguish a recoverable evidence problem from a valid empty record; "
        "HOW: state WHAT failed, WHY it prevents verification, and HOW to recover."
    )
    assert "traceback" not in diagnostic, (
        "WHAT: malformed evidence leaked a Python traceback; "
        "WHY: implementation detail is not an operator recovery path; "
        "HOW: convert malformed input into the public WHAT/WHY/HOW refusal."
    )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return
    assert not isinstance(payload, dict) or not {
        "command",
        "result",
        "output",
    }.issubset(payload), (
        "WHAT: invalid evidence produced a success-shaped complete record; "
        "WHY: a developer could mistake rejected data for verified evidence; "
        "HOW: omit command/result/output record fields whenever verification fails."
    )


@pytest.mark.negative_at
def test_large_command_result_has_bounded_summary_and_recoverable_complete_record(
    tmp_path: Path,
) -> None:
    """# covers: R1 R2 R3

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer keeps working from a
    compact command summary and recovers the same complete evidence without guessing.
    """
    raw_log = tmp_path / "full-command.log"
    full_output = "diagnostic-line\n" * 10_000
    raw_log.write_text(full_output, encoding="utf-8")

    exit_code, stdout, stderr = _dispatch(tmp_path, raw_log)

    assert exit_code == 0, (
        "WHAT: the public dispatch command did not create a bounded evidence handoff; "
        "WHY: a developer must not choose between carrying a huge transcript and losing proof; "
        "HOW: accept a persisted log, command, and observed result through `des dispatch`. "
        f"stderr={stderr!r}"
    )
    assert len(stdout.encode("utf-8")) <= _BOUND_BYTES, (
        "WHAT: the command handoff exceeded the 2 KiB context budget; "
        "WHY: raw command output would be repaid in every subsequent agent turn; "
        "HOW: return only compact metadata and keep the complete result in a durable record."
    )
    assert full_output not in stdout, (
        "WHAT: unbounded command output was retained in the returned context; "
        "WHY: the handoff must reduce prompt amplification rather than rename it; "
        "HOW: keep raw output exclusively in the durable record."
    )

    handoff = json.loads(stdout)
    result_digest = hashlib.sha256(b"exit=1").hexdigest()
    raw_digest = hashlib.sha256(full_output.encode("utf-8")).hexdigest()
    record = handoff.get("record")
    assert isinstance(record, dict), (
        "WHAT: the compact handoff has no durable record descriptor; "
        "WHY: a digest without a locator cannot recover complete evidence; "
        "HOW: emit a record locator, SHA-256, and byte count."
    )
    record_locator = Path(str(record.get("locator", "")))
    assert handoff.get("command") == "uv run pytest -q" and handoff.get("result") == {
        "exit_code": 1,
        "digest": result_digest,
    }, (
        "WHAT: the compact handoff omitted the command or observed-result digest; "
        "WHY: a developer cannot correlate a short summary to the completed invocation; "
        "HOW: include the exact command and result exit-code/digest in the envelope."
    )
    assert record_locator.is_file(), (
        "WHAT: the compact handoff named no readable durable record; "
        "WHY: later investigation must not depend on process memory or reconstruction; "
        "HOW: persist a record before returning the compact handoff."
    )
    assert (
        record.get("bytes") == record_locator.stat().st_size
        and record.get("sha256")
        == hashlib.sha256(record_locator.read_bytes()).hexdigest()
    ), (
        "WHAT: the durable record descriptor cannot verify its referenced record; "
        "WHY: an unverifiable locator can silently point at different evidence; "
        "HOW: publish the durable record's exact SHA-256 and byte count."
    )

    details_command = handoff.get("details_command")
    assert isinstance(details_command, str), (
        "WHAT: the compact handoff did not provide an on-demand retrieval command; "
        "WHY: a developer should not guess how to inspect full evidence; "
        "HOW: emit one public `des dispatch --show-tool-output` command."
    )
    assert "--sha256" in details_command and record["sha256"] in details_command, (
        "WHAT: the details command does not carry the immutable record digest; "
        "WHY: a locator alone cannot reveal that the durable record was replaced after handoff; "
        "HOW: include the record SHA-256 in the public retrieval command."
    )
    details_exit, details_stdout, details_stderr = _retrieve(tmp_path, details_command)
    assert details_exit == 0, (
        "WHAT: the public details command could not recover the durable record; "
        "WHY: the compact result promised evidence that a developer cannot inspect; "
        "HOW: make the named command load and integrity-check its record. "
        f"stderr={details_stderr!r}"
    )
    assert json.loads(details_stdout) == {
        "command": "uv run pytest -q",
        "result": {"exit_code": 1, "digest": result_digest},
        "output": {
            "locator": str(raw_log),
            "sha256": raw_digest,
            "bytes": len(full_output.encode("utf-8")),
            "content": full_output,
        },
    }, (
        "WHAT: the recovered record did not contain the same command, result, and complete output; "
        "WHY: a short handoff is trustworthy only when its complete evidence is correlatable; "
        "HOW: persist and retrieve the immutable invocation record, including the full raw result."
    )


@pytest.mark.negative_at
def test_unavailable_command_output_is_refused_without_a_success_shaped_handoff(
    tmp_path: Path,
) -> None:
    """# covers: R4

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer sees an actionable refusal
    when complete evidence cannot be recorded, never a summary imitating success.
    """
    absent_log = tmp_path / "missing-command.log"

    exit_code, stdout, stderr = _dispatch(tmp_path, absent_log)

    diagnostic = f"{stdout}\n{stderr}".lower()
    assert exit_code != 0, (
        "WHAT: dispatch accepted a missing command log; "
        "WHY: success-looking output without evidence is indistinguishable from never inspecting it; "
        "HOW: refuse non-zero until a readable persisted log is supplied."
    )
    assert all(word in diagnostic for word in ("what", "why", "how")), (
        "WHAT: the missing-record refusal is not actionable; "
        "WHY: a developer cannot distinguish unavailable evidence from valid empty output; "
        "HOW: state what could not be read, why no handoff is trustworthy, and how to provide it."
    )
    assert "details_command" not in stdout and '"record"' not in stdout, (
        "WHAT: a missing record produced a success-shaped handoff; "
        "WHY: consumers could mistake unavailable evidence for verified output; "
        "HOW: emit no compact success envelope unless the full record is persisted and hashed."
    )


@pytest.mark.negative_at
def test_tampered_output_is_refused_when_the_named_record_is_recovered(
    tmp_path: Path,
) -> None:
    """# covers: R5

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer is warned when complete
    evidence no longer matches the compact record, never shown false verification.
    """
    raw_log = tmp_path / "full-command.log"
    raw_log.write_text("trusted diagnostic\n", encoding="utf-8")
    handoff_exit, handoff_stdout, handoff_stderr = _dispatch(tmp_path, raw_log)
    assert handoff_exit == 0, (
        "WHAT: a valid command result could not create a durable record; "
        "WHY: tamper detection needs an originally verified record to compare; "
        "HOW: create the compact handoff before testing later recovery. "
        f"stderr={handoff_stderr!r}"
    )
    details_command = json.loads(handoff_stdout)["details_command"]
    record = json.loads(handoff_stdout)["record"]
    record_path = Path(record["locator"])
    record_path.write_text('{"substituted":"record"}\n', encoding="utf-8")

    exit_code, stdout, stderr = _retrieve(tmp_path, details_command)

    diagnostic = f"{stdout}\n{stderr}".lower()
    assert exit_code != 0, (
        "WHAT: the details command accepted output changed after handoff; "
        "WHY: a recovered record must never certify different evidence as the original invocation; "
        "HOW: compare the persisted raw-output digest before returning record content."
    )
    assert all(word in diagnostic for word in ("what", "why", "how")), (
        "WHAT: the integrity refusal does not explain recovery; "
        "WHY: a developer needs to identify tampering rather than treating it as a generic tool failure; "
        "HOW: name the integrity mismatch, its trust consequence, and the remediation."
    )
    assert "verified" not in diagnostic or "not verified" in diagnostic, (
        "WHAT: tampered evidence was described as verified; "
        "WHY: integrity language must never turn a mismatch into false success; "
        "HOW: refuse the record and explicitly state that verification failed."
    )


@pytest.mark.negative_at
def test_oversized_command_and_locator_never_escape_the_bounded_handoff_budget(
    tmp_path: Path,
) -> None:
    """# covers: R6

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer never pays an oversized
    command name or storage location as resident context after a completed tool run.
    """
    locator_parts = [f"segment-{index}-{'x' * 96}" for index in range(18)]
    raw_log = tmp_path.joinpath(*locator_parts, "complete.log")
    raw_log.parent.mkdir(parents=True)
    raw_log.write_text("complete output\n", encoding="utf-8")
    command = "tool " + ("--very-long-argument=" + ("x" * 120)) * 20

    exit_code, stdout, stderr = _dispatch(tmp_path, raw_log, command=command)

    if exit_code == 0:
        assert len(stdout.encode("utf-8")) <= _BOUND_BYTES, (
            "WHAT: a successful handoff exceeded 2 KiB when command and locator were long; "
            "WHY: metadata can amplify context just like raw tool output; "
            "HOW: compact or indirect oversized fields before returning a successful envelope."
        )
        assert (
            json.loads(stdout).get("command_digest")
            == hashlib.sha256(command.encode("utf-8")).hexdigest()
        ), (
            "WHAT: a compacted long command has no correlation digest; "
            "WHY: an operator must still distinguish the completed invocation without raw metadata; "
            "HOW: publish the SHA-256 of any command omitted from the bounded summary."
        )
    else:
        _assert_actionable_refusal(exit_code, stdout, stderr)


@pytest.mark.negative_at
def test_non_utf8_output_is_refused_actionably_or_recovered_byte_for_byte(
    tmp_path: Path,
) -> None:
    """# covers: R7

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer can trust that unusual
    tool bytes are either preserved exactly or refused without an implementation crash.
    """
    raw_log = tmp_path / "non-utf8.log"
    original_bytes = b"before\xffafter\x00\x80"
    raw_log.write_bytes(original_bytes)

    exit_code, stdout, stderr = _dispatch(tmp_path, raw_log)

    if exit_code != 0:
        _assert_actionable_refusal(exit_code, stdout, stderr)
        return

    handoff = json.loads(stdout)
    details_exit, details_stdout, details_stderr = _retrieve(
        tmp_path, handoff["details_command"]
    )
    assert details_exit == 0, (
        "WHAT: a successful non-UTF-8 handoff could not recover its promised record; "
        "WHY: accepting bytes without retrievable evidence silently discards the tool result; "
        "HOW: either refuse the input before success or encode the complete bytes safely. "
        f"stderr={details_stderr!r}"
    )
    recovered = json.loads(details_stdout)
    encoded = recovered.get("output", {}).get("content_base64")
    assert isinstance(encoded, str) and base64.b64decode(encoded) == original_bytes, (
        "WHAT: a non-UTF-8 result was accepted but not recovered byte-for-byte; "
        "WHY: lossy decoding changes the evidence a developer investigates; "
        "HOW: use an explicit byte-preserving encoding such as content_base64 in the durable record."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("corruption", ("missing-output", "mismatched-output"))
def test_corrupt_durable_record_is_refused_even_when_its_outer_digest_matches(
    tmp_path: Path, corruption: str
) -> None:
    """# covers: R8

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer never receives a complete
    record when its internal evidence fields no longer agree with each other.
    """
    raw_log = tmp_path / "complete.log"
    raw_log.write_text("trusted output\n", encoding="utf-8")
    handoff_exit, handoff_stdout, handoff_stderr = _dispatch(tmp_path, raw_log)
    assert handoff_exit == 0, (
        "WHAT: a valid invocation could not create the record needed for corruption recovery; "
        "WHY: inner-schema validation must be proven against a formerly valid durable record; "
        "HOW: create a valid record before exercising the public details command. "
        f"stderr={handoff_stderr!r}"
    )
    record_path = Path(json.loads(handoff_stdout)["record"]["locator"])
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if corruption == "missing-output":
        record.pop("output", None)
    else:
        output = record["output"]
        output["content"] = "substituted output\n"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    altered_digest = hashlib.sha256(record_path.read_bytes()).hexdigest()
    details_command = f"des dispatch --show-tool-output {shlex.quote(str(record_path))} --sha256 {altered_digest}"

    exit_code, stdout, stderr = _retrieve(tmp_path, details_command)

    _assert_actionable_refusal(exit_code, stdout, stderr)


@pytest.mark.negative_at
def test_accepted_noncanonical_result_stays_retrievable_with_the_same_result_evidence(
    tmp_path: Path,
) -> None:
    """# covers: R9

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch — a developer can recover the same
    result evidence that a compact handoff accepted, even when its input spelling
    was not canonical.
    """
    raw_log = tmp_path / "complete.log"
    raw_log.write_text(
        "completed with a noncanonical exit spelling\n", encoding="utf-8"
    )

    exit_code, stdout, stderr = _dispatch(tmp_path, raw_log, result="exit=001")

    if exit_code != 0:
        _assert_actionable_refusal(exit_code, stdout, stderr)
        return

    handoff = json.loads(stdout)
    details_command = handoff.get("details_command")
    assert isinstance(details_command, str), (
        "WHAT: dispatch accepted a noncanonical result without a details command; "
        "WHY: an accepted handoff must not strand its own complete evidence; "
        "HOW: either normalize/refuse the result before success or emit a retrievable record."
    )
    details_exit, details_stdout, details_stderr = _retrieve(tmp_path, details_command)
    assert details_exit == 0, (
        "WHAT: dispatch accepted a result but its emitted details command refused it; "
        "WHY: a compact handoff cannot truthfully promise evidence that its own public recovery path rejects; "
        "HOW: normalize the result representation once before hashing and persist that exact representation. "
        f"stderr={details_stderr!r}"
    )
    recovered = json.loads(details_stdout)
    assert recovered.get("result") == handoff.get("result"), (
        "WHAT: compact and recovered records disagree about one accepted result; "
        "WHY: a developer cannot correlate the summary to the evidence when normalization changes mid-journey; "
        "HOW: use one canonical result representation and digest on both public surfaces."
    )
