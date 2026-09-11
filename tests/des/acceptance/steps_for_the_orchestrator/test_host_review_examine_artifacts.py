"""Public ports for host-selected review and source-blind EXAMINE.

These scenarios keep the host's decisions in the test: DES constructs and
persists candidate-bound inputs/results, while the test explicitly calls each
public command.  No helper decides a next role.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    asked,
    block,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_retains_native_evidence_without_provider import (
    ORACLE,
    TARGET,
    _crafted,
)


REVIEWER_SESSION = "host-reviewer-session"
EXAMINER_SESSION = "host-examiner-session"
SOURCE_ONLY_MARKER = "DES_SUPPLIED_SOURCE_ONLY_MARKER"


def _payload_sha256(document: dict[str, object]) -> str:
    """The public artifact seal: canonical payload bytes excluding its digest."""
    payload = {key: value for key, value in document.items() if key != "payload_sha256"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(canonical).hexdigest()


def _reseal(document: dict[str, object]) -> bytes:
    """Build one structurally valid but stale fixture artifact."""
    payload = {key: value for key, value in document.items() if key != "payload_sha256"}
    return json.dumps(
        {**payload, "payload_sha256": _payload_sha256(payload)},
        sort_keys=True,
        ensure_ascii=False,
    ).encode()


def _host_result(role: str, outcome: str, diagnostic: str) -> str:
    payload: dict[str, object] = {"outcome": outcome, "diagnostic": diagnostic}
    # `record-role-result` reuses `decode_model_run`. Only its whole-diff
    # reviewer role names defects; the source-blind examiner has the ordinary
    # closed outcome envelope. This port supplies no request value enum, so a
    # non-accepting reviewer can only use the set-level null value.
    if role == "reviewer":
        payload |= {
            "defect_owner": None if outcome == "accepted" else "oracle",
            "defect_value": None,
        }
    return json.dumps({"structured_output": payload})


def _counting_subject_interpreter(root: Path, counter: Path) -> None:
    """Make the subject's declared interpreter count the native execution."""
    interpreter = root / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    counter.write_text("", encoding="utf-8")
    interpreter.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "-m" ] && [ "$2" = "pytest" ] && [ "$3" = {shlex.quote(ORACLE)} ]; then\n'
        f"  printf 1 >> {shlex.quote(str(counter))}\n"
        "fi\n"
        f'exec {shlex.quote(sys.executable)} "$@"\n',
        encoding="utf-8",
    )
    interpreter.chmod(0o755)


def _native_only_environment(directory: Path) -> dict[str, str]:
    """Expose Git only; verification supplies its declared interpreter shim."""
    directory.mkdir()
    git = shutil.which("git")
    assert git is not None
    (directory / "git").symlink_to(git)
    return {"PATH": str(directory), "PYTHONPATH": str(PACKAGE_PARENT)}


def _provider_free_verify(
    root: Path, tmp_path: Path
) -> tuple[str, dict[str, str], Path]:
    counter = tmp_path / "declared-python-invocations"
    _counting_subject_interpreter(root, counter)
    code, out, err = run_cli_in_process(
        ["verify", "--repo-root", str(root)],
        cwd=root,
        env=_native_only_environment(tmp_path / "native-bin"),
        catch_all=True,
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert len(lines["CANDIDATE"]) == 40
    assert lines["NATIVE-EVIDENCE"].startswith(".nwave/des/logs/native/")
    assert len(lines["NATIVE-EVIDENCE-SHA256"]) == 64
    assert counter.read_text(encoding="utf-8") == "1"
    return lines["CANDIDATE"], lines, counter


def _keys(value: object) -> set[str]:
    """The JSON field names supplied by DES, excluding opaque string values."""
    if isinstance(value, dict):
        return set(value).union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


def _prepare(
    root: Path, step, role: str, candidate: str
) -> tuple[dict[str, str], Path]:
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["ROLE"] == role
    assert lines["CANDIDATE"] == candidate
    assert len(lines["INPUT-SHA256"]) == 64
    path = root / lines["INPUT"]
    assert path.is_file(), lines
    return lines, path


def _record(
    root: Path,
    step,
    *,
    role: str,
    candidate: str,
    session_id: str,
    payload: str,
) -> tuple[int, dict[str, str], str, str]:
    code, out, err = step(
        "record-role-result",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--model",
        "host-selected-model",
        "--session-id",
        session_id,
        "--input",
        "-",
        stdin=payload,
    )
    return code, block(out, err), out, err


def test_host_constructs_distinct_bound_inputs_records_results_and_integrates_mechanically(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    _crafted(root, step)
    # The candidate source has a marker that no native output contains.  It
    # distinguishes a DES-supplied diff leak from the allowed opaque output.
    (root / TARGET).write_text(f"VALUE = 1\n# {SOURCE_ONLY_MARKER}\n", encoding="utf-8")
    turns_before_verify = asked(turns)
    candidate, verified, native_counter = _provider_free_verify(root, tmp_path)
    assert asked(turns) == turns_before_verify
    native_record = root / verified["NATIVE-EVIDENCE"]
    native_bytes = native_record.read_bytes()
    assert (
        hashlib.sha256(native_bytes).hexdigest() == verified["NATIVE-EVIDENCE-SHA256"]
    )

    turns_before_artifacts = asked(turns)
    reviewer_prepared, reviewer_input = _prepare(root, step, "reviewer", candidate)
    examiner_prepared, examiner_input = _prepare(root, step, "examiner", candidate)
    assert asked(turns) == turns_before_artifacts
    assert native_counter.read_text(encoding="utf-8") == "1"
    assert reviewer_input != examiner_input

    reviewer_bytes = reviewer_input.read_bytes()
    examiner_bytes = examiner_input.read_bytes()
    for artifact, prepared in (
        (reviewer_bytes, reviewer_prepared),
        (examiner_bytes, examiner_prepared),
    ):
        document = json.loads(artifact)
        assert document["schema_version"] == 1
        assert document["kind"] == "role_input"
        assert document["payload_sha256"] == _payload_sha256(document)
        assert hashlib.sha256(artifact).hexdigest() == prepared["INPUT-SHA256"]
        assert document["candidate_sha"] == candidate
        assert verified["NATIVE-EVIDENCE-SHA256"].encode() in artifact
    # Reviewer receives the existing whole-diff inputs and the native bytes.
    reviewer_document = json.loads(reviewer_bytes)
    # These are the existing `_implementation_review` prompt fields. The
    # fixture declares both paths, so empty placeholder collections cannot
    # satisfy this public reviewer artifact.
    assert TARGET in reviewer_document["owned_paths"]
    assert ORACLE in reviewer_document["owned_paths"]
    assert any(path == ORACLE for path, _ in reviewer_document["approved_oracles"])
    assert TARGET.encode() in reviewer_bytes
    assert ORACLE.encode() in reviewer_bytes
    assert SOURCE_ONLY_MARKER.encode() in reviewer_bytes
    assert b"1 passed" in reviewer_bytes
    # Examiner sees the same measured observation. Source blindness is
    # structural: opaque stdout/stderr are unparsed and may legitimately carry
    # path-looking text, so this oracle examines DES-supplied JSON keys only.
    assert b"1 passed" in examiner_bytes
    examiner_keys = _keys(json.loads(examiner_bytes))
    for forbidden in (
        "diff",
        "owned_paths",
        "approved_oracles",
        "handover",
        "reviewer_input",
        "reviewer_outcome",
        "reviewer_diagnostic",
        "reviewer_identity",
        "reviewer_result_locator",
        "argv",
        "cwd",
        "declared_environment",
        "touches_test_paths",
        "exercised_product_modules",
        "exercised_changed_targets",
    ):
        assert forbidden not in examiner_keys
    # This marker occurs only in the candidate diff, never in native output;
    # its absence therefore proves no DES-provided source context leaked.
    assert SOURCE_ONLY_MARKER.encode() not in examiner_bytes
    assert native_record.read_bytes() == native_bytes

    results: dict[str, tuple[Path, bytes, str]] = {}
    for role, outcome, diagnostic, session_id, conflicting_outcome in (
        (
            "reviewer",
            "rejected",
            "host reviewer found a concern",
            REVIEWER_SESSION,
            "accepted",
        ),
        (
            "examiner",
            "indeterminate",
            "host examiner did not decide",
            EXAMINER_SESSION,
            "accepted",
        ),
    ):
        result_directory = root / ".nwave" / "des" / "logs" / "roles"
        before_invalid = {
            path: path.read_bytes() for path in result_directory.glob("*-result.json")
        }
        # `record-role-result` receives the same provider-neutral envelope as
        # an adapter. An unknown closed outcome or a missing required
        # diagnostic therefore establishes no typed result and writes nothing.
        for invalid in (
            json.dumps(
                {
                    "structured_output": {
                        "outcome": "not-a-model-outcome",
                        "diagnostic": "invalid closed outcome",
                    }
                }
            ),
            json.dumps({"structured_output": {"outcome": outcome}}),
        ):
            code, _, out, err = _record(
                root,
                step,
                role=role,
                candidate=candidate,
                session_id=session_id,
                payload=invalid,
            )
            assert code != 0, out + err
            assert {
                path: path.read_bytes()
                for path in result_directory.glob("*-result.json")
            } == before_invalid

        payload = _host_result(role, outcome, diagnostic)
        code, recorded, out, err = _record(
            root,
            step,
            role=role,
            candidate=candidate,
            session_id=session_id,
            payload=payload,
        )
        assert code == 0, out + err
        assert recorded["ROLE"] == role
        assert recorded["CANDIDATE"] == candidate
        assert recorded["OUTCOME"] == outcome
        result = root / recorded["RESULT"]
        original = result.read_bytes()
        result_document = json.loads(original)
        assert result_document["schema_version"] == 1
        assert result_document["kind"] == "role_result"
        assert result_document["payload_sha256"] == _payload_sha256(result_document)
        assert hashlib.sha256(original).hexdigest() == recorded["RESULT-SHA256"]
        assert b'"declared_provider": "claude"' in original
        assert b'"declared_model": "host-selected-model"' in original
        assert f'"declared_session_id": "{session_id}"'.encode() in original
        for unknown in (
            b'"issued"',
            b'"exit_status"',
            b'"retry_safe"',
            b'"duration"',
            b'"accounting"',
        ):
            assert unknown not in original

        # Identical host input is replay-safe; conflicting bytes under the
        # same declared identity refuse without replacing the stored receipt.
        code, replayed, out, err = _record(
            root,
            step,
            role=role,
            candidate=candidate,
            session_id=session_id,
            payload=payload,
        )
        assert code == 0, out + err
        assert replayed["RESULT"] == recorded["RESULT"]
        assert result.read_bytes() == original
        code, _, out, err = _record(
            root,
            step,
            role=role,
            candidate=candidate,
            session_id=session_id,
            payload=_host_result(role, conflicting_outcome, "conflicting host result"),
        )
        assert code != 0, out + err
        assert result.read_bytes() == original
        results[role] = (result, original, session_id)

    reviewer_result, reviewer_result_bytes, _ = results["reviewer"]
    examiner_result, examiner_result_bytes, _ = results["examiner"]
    assert examiner_result != reviewer_result
    assert EXAMINER_SESSION.encode() in examiner_result_bytes
    assert REVIEWER_SESSION.encode() not in examiner_result_bytes
    assert REVIEWER_SESSION.encode() in reviewer_result_bytes
    assert EXAMINER_SESSION.encode() not in reviewer_result_bytes
    assert asked(turns) == turns_before_artifacts
    assert native_counter.read_text(encoding="utf-8") == "1"

    # A changed byte with its old payload seal is not a prepared artifact; it
    # cannot produce a new receipt or buy a role turn through either public
    # consumer. A resealed stale authority is likewise not current authority.
    original_reviewer_input = json.loads(reviewer_bytes)
    result_directory = root / ".nwave" / "des" / "logs" / "roles"
    before_tamper_results = {
        path: path.read_bytes() for path in result_directory.glob("*-result.json")
    }
    tampered_payload = {**original_reviewer_input, "diff": "tampered source bytes"}
    reviewer_input.write_text(
        json.dumps(tampered_payload, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    code, _, out, err = _record(
        root,
        step,
        role="reviewer",
        candidate=candidate,
        session_id="tampered-payload-session",
        payload=_host_result("reviewer", "accepted", "tampered payload refused"),
    )
    assert code != 0, out + err
    assert {
        path: path.read_bytes() for path in result_directory.glob("*-result.json")
    } == before_tamper_results
    assert asked(turns) == turns_before_artifacts

    stale_authority = {**original_reviewer_input, "request_digest": "0" * 64}
    reviewer_input.write_bytes(_reseal(stale_authority))
    code, out, err = step(
        "invoke-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--input",
        str(reviewer_input.relative_to(root)),
        answers=[],
    )
    assert code != 0, out + err
    assert {
        path: path.read_bytes() for path in result_directory.glob("*-result.json")
    } == before_tamper_results
    assert asked(turns) == turns_before_artifacts

    # Calling integrate is the host's choice. DES does candidate identity, CAS,
    # and cleanup only; rejected/indeterminate role observations are no admission gate.
    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )
    assert code == 0, out + err
    assert block(out, err)["INTEGRATED"] == candidate


def test_optional_invoke_role_buys_one_selected_turn_without_fallback(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    _crafted(root, step)
    candidate, _, native_counter = _provider_free_verify(root, tmp_path)
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    assert native_counter.read_text(encoding="utf-8") == "1"
    turns_before_invoke = asked(turns)

    code, out, err = step(
        "invoke-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--input",
        str(reviewer_input.relative_to(root)),
        answers=[
            json.loads(
                _host_result("reviewer", "accepted", "selected reviewer accepted")
            )
        ],
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["ROLE"] == "reviewer"
    assert lines["CANDIDATE"] == candidate
    assert lines["OUTCOME"] == "accepted"
    assert lines["TURNS-BOUGHT"] == "1"
    assert asked(turns) == [*turns_before_invoke, "nw-software-crafter-reviewer"]
    assert native_counter.read_text(encoding="utf-8") == "1"
    reviewer_result = json.loads((root / lines["RESULT"]).read_bytes())
    assert reviewer_result["kind"] == "role_result"
    assert reviewer_result["payload_sha256"] == _payload_sha256(reviewer_result)
    assert reviewer_result["actual_provider"] == "claude"
    assert reviewer_result["actual_model"] == "claude-opus-5"

    _, examiner_input = _prepare(root, step, "examiner", candidate)
    code, out, err = step(
        "invoke-role",
        "--repo-root",
        str(root),
        "--role",
        "examiner",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--input",
        str(examiner_input.relative_to(root)),
        answers=[
            json.loads(
                _host_result("examiner", "accepted", "selected examiner accepted")
            )
        ],
    )
    assert code == 0, out + err
    examiner_lines = block(out, err)
    assert examiner_lines["ROLE"] == "examiner"
    assert examiner_lines["CANDIDATE"] == candidate
    assert examiner_lines["OUTCOME"] == "accepted"
    assert examiner_lines["TURNS-BOUGHT"] == "1"
    assert asked(turns) == [
        *turns_before_invoke,
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
    ]
    rows = json.loads(turns.read_text(encoding="utf-8"))
    examiner_turn = rows[-1]
    examiner_cwd = Path(examiner_turn["cwd"])
    assert examiner_turn["agent"] == "nw-user-examiner"
    # The configured adapter transports the exact sealed artifact as its first
    # line, then appends its own execution instruction as a separate channel.
    assert json.loads(examiner_turn["prompt"].splitlines()[0]) == json.loads(
        examiner_input.read_bytes()
    )
    assert SOURCE_ONLY_MARKER not in examiner_turn["prompt"]
    assert root not in examiner_cwd.parents
    assert (
        subprocess.run(
            ["git", "-C", str(examiner_cwd), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        ).returncode
        != 0
    )
    examiner_result = json.loads((root / examiner_lines["RESULT"]).read_bytes())
    assert examiner_result["kind"] == "role_result"
    assert examiner_result["payload_sha256"] == _payload_sha256(examiner_result)
    assert examiner_result["actual_provider"] == "claude"
    assert examiner_result["actual_model"] == "claude-opus-5"
    assert native_counter.read_text(encoding="utf-8") == "1"
