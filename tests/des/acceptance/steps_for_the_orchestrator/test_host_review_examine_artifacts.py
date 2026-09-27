"""Public ports for host-selected review and source-blind EXAMINE.

These scenarios keep the host's decisions in the test: DES constructs and
persists candidate-bound inputs/results, while the test explicitly calls each
public command.  No helper decides a next role.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.cli.role_artifacts import _examiner_argv
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    accepted_values,
    asked,
    base_repository,
    block,
    hermetic_environment,
    observation,
    stepper,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_retains_native_evidence_without_provider import (
    ORACLE,
    RED_ORACLE,
    REQUEST,
    SUPPORT,
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


COUNT_AND_RUN = "tests/acceptance/count_and_run.py"
COUNT_AND_RUN_SOURCE = (
    "import subprocess\nimport sys\n\n"
    "counter, oracle = sys.argv[1], sys.argv[2]\n"
    "with open(counter, 'a', encoding='utf-8') as handle:\n"
    "    handle.write('1')\n"
    "raise SystemExit(\n"
    "    subprocess.run([sys.executable, '-m', 'pytest', oracle]).returncode\n"
    ")\n"
)


def _counting_declared_argv(root: Path, counter: Path) -> list[str]:
    """Commit the subject's counting script; return the declared native argv.

    The counter is written by the declared argv itself, through the absolute
    interpreter, so no PATH or shim can be bypassed.
    """
    script = root / COUNT_AND_RUN
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(COUNT_AND_RUN_SOURCE, encoding="utf-8")
    counter.write_text("", encoding="utf-8")
    for args in (
        ("add", COUNT_AND_RUN),
        ("commit", "-qm", "subject counting script"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True)
    return [sys.executable, COUNT_AND_RUN, str(counter), ORACLE]


def _crafted_counting(root: Path, step, counter: Path, *, criteria=None) -> list[str]:
    argv = _counting_declared_argv(root, counter)

    def selected_step(*args, **kwargs):
        result = step(*args, **kwargs)
        if args[0] == "design" and result[0] == 0 and criteria is not None:
            manifest = {
                "schema_version": 2,
                "values": [
                    {
                        "observation": observation("A"),
                        "acceptance_obligations": criteria,
                        "oracle": ORACLE,
                        "acceptance_supports": [SUPPORT],
                        "verification": [argv],
                        "oracle_verification_index": 0,
                    }
                ],
            }
            code, out, err = step(
                "distill",
                "--repo-root",
                str(root),
                "--input",
                "-",
                stdin=json.dumps(manifest),
            )
            assert code == 0, out + err
        return result

    _crafted(root, selected_step, verification=[argv])
    # Oracle authoring and craft settlement legitimately run the declared
    # command themselves; the observation under test starts at des verify.
    counter.write_text("", encoding="utf-8")
    return argv


def _native_only_environment(directory: Path, interpreter: Path) -> dict[str, str]:
    """Expose Git and the declared interpreter shim, without a model provider."""
    directory.mkdir()
    git = shutil.which("git")
    assert git is not None
    (directory / "git").symlink_to(git)
    (directory / "python").symlink_to(interpreter)
    return {"PATH": str(directory), "PYTHONPATH": str(PACKAGE_PARENT)}


def _provider_free_verify(
    root: Path, tmp_path: Path, counter: Path | None = None
) -> tuple[str, dict[str, str], Path | None]:
    code, out, err = run_cli_in_process(
        ["verify", "--repo-root", str(root)],
        cwd=root,
        env=_native_only_environment(tmp_path / "native-bin", Path(sys.executable)),
        catch_all=True,
    )
    assert code == 0, (
        f"WHAT: des verify exited {code}: {out + err!r}\n"
        "WHY: the walking-skeleton chain needs a verified candidate before "
        "preparation\n"
        "HOW: fix the crafted verification fixture so des verify succeeds"
    )
    lines = block(out, err)
    assert len(lines["CANDIDATE"]) == 40
    assert lines["NATIVE-EVIDENCE"].startswith(".nwave/des/logs/native/")
    assert len(lines["NATIVE-EVIDENCE-SHA256"]) == 64
    if counter is not None:
        _assert_native_ran_once(counter, "after des verify")
    return lines["CANDIDATE"], lines, counter


def _assert_native_ran_once(counter: Path, when: str) -> None:
    observed = counter.read_text(encoding="utf-8")
    assert observed == "1", (
        f"WHAT: declared native argv ran {len(observed)} time(s) {when}, expected 1. "
        "WHY: verify collects native evidence once; review/EXAMINE preparation, "
        "result recording and integration must only read it. "
        "HOW: reuse the retained native evidence instead of re-running the argv."
    )


def _keys(value: object) -> set[str]:
    """The JSON field names supplied by DES, excluding opaque string values."""
    if isinstance(value, dict):
        return set(value).union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


WITHHELD = {
    "withheld": True,
    "reason": (
        "source-blind examiner: native verification detail may reveal "
        "oracle identifiers or source"
    ),
}
MAX_PACKET_BYTES = 65536


def _tree_sha(root: Path, candidate: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{candidate}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _candidate_object_bytes(root: Path, candidate: str) -> bytes:
    """The immutable Git commit object bytes DES actually stores CANDIDATE as.

    `git cat-file -p` returns the raw stored commit (tree, parent, author,
    committer, message) -- the real candidate artifact -- so a comparison
    against it catches a mutated/replaced object even when the CLI still
    echoes the same identifier string back.
    """
    return subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", candidate],
        check=True,
        capture_output=True,
    ).stdout


def _packet(root: Path, candidate: str, **overrides: object) -> dict[str, object]:
    """A valid public_observations v1 packet a caller captured for CANDIDATE."""
    packet: dict[str, object] = {
        "schema": "nwave.public_observations",
        "version": 1,
        "candidate_sha": candidate,
        "candidate_tree_sha": _tree_sha(root, candidate),
        "producer": {"id": "host-capture", "version": "1"},
        "states": {"S1": {"observation": "A user sees the verified outcome."}},
        "scenarios": [
            {
                "id": "V4-native-counter",
                "substrate": "mock_provider",
                "purpose": "Preparation adds no native execution.",
                "events": [
                    {
                        "seq": 1,
                        "stimulus": {
                            "argv": ["des", "verify", "--repo-root", "<repo>"],
                            "stdin": None,
                        },
                        "response": {
                            "exit": 0,
                            "stdout": "DELIVERY-OUTCOME: Success",
                            "stderr": "",
                        },
                        "state": {"before": None, "after": "S1"},
                        "counter": {"before": 0, "after": 1},
                    }
                ],
            }
        ],
    }
    return {**packet, **overrides}


def _write_packet(
    path: Path, packet: dict[str, object], size: int | None = None
) -> bytes:
    data = json.dumps(packet, sort_keys=True).encode()
    if size is not None:
        assert len(data) <= size, "fixture packet larger than requested size"
        data += b" " * (size - len(data))
    path.write_bytes(data)
    return data


def _role_files(root: Path) -> dict[Path, bytes]:
    directory = root / ".nwave" / "des" / "logs" / "roles"
    return {p: p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()}


def _radius_values(value: object) -> list[object]:
    if isinstance(value, dict):
        found = [v for k, v in value.items() if k == "radius"]
        return found + [x for v in value.values() for x in _radius_values(v)]
    if isinstance(value, list):
        return [x for v in value for x in _radius_values(v)]
    return []


def _prepare(
    root: Path,
    step,
    role: str,
    candidate: str,
    observations: Path | None = None,
) -> tuple[dict[str, str], Path]:
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
        *(("--observations", str(observations)) if observations else ()),
    )
    assert code == 0, (
        f"WHAT: prepare-role {role} exited {code}: {out + err!r}\n"
        "WHY: the walking-skeleton chain needs examiner --observations PATH "
        "admitted through the public prepare-role CLI\n"
        "HOW: add the examiner-only --observations PATH option to des prepare-role"
    )
    lines = block(out, err)
    assert lines["ROLE"] == role
    assert lines["CANDIDATE"] == candidate
    assert len(lines["INPUT-SHA256"]) == 64
    path = root / lines["INPUT"]
    assert path.is_file(), lines
    expected_provider = "claude"
    assert shlex.split(lines["NEXT"]) == [
        "des",
        "invoke-role",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
        "--provider",
        expected_provider,
        "--input",
        lines["INPUT"],
    ]
    return lines, path


def _invalid_runtime(root: Path) -> None:
    (root / ".nwave" / "config.json").write_text(
        json.dumps(
            {
                "model_runtime": {
                    "default": {"provider": "unsupported", "model": "configured"}
                }
            }
        ),
        encoding="utf-8",
    )


def test_prepare_role_refuses_an_unresolvable_configured_provider(
    root: Path, step, tmp_path: Path
) -> None:
    _crafted(root, step)
    candidate, _, _ = _provider_free_verify(root, tmp_path)
    _invalid_runtime(root)
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    )
    assert code != 0, out + err
    lines = block(out, err)
    assert lines["WHAT"] == "RolePreparationUnavailable"
    assert "provider must be claude or codex" in lines["WHY"]


def test_invoke_role_refuses_an_unresolvable_configured_provider_before_a_turn(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    _crafted(root, step)
    candidate, _, _ = _provider_free_verify(root, tmp_path)
    _prepared, input_path = _prepare(root, step, "reviewer", candidate)
    result_directory = root / ".nwave" / "des" / "logs" / "roles"
    before_results = {
        path: path.read_bytes() for path in result_directory.glob("*-result.json")
    }
    turns_before = asked(turns)
    _invalid_runtime(root)
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
        str(input_path.relative_to(root)),
        answers=[],
    )
    assert code != 0, out + err
    lines = block(out, err)
    assert lines["WHAT"] == "RoleRuntimeUnavailable"
    assert "provider must be claude or codex" in lines["WHY"]
    assert lines["HOW"] == "configure one provider and model for the selected role"
    assert lines["TURNS-BOUGHT"] == "0"
    assert asked(turns) == turns_before
    assert {
        path: path.read_bytes() for path in result_directory.glob("*-result.json")
    } == before_results


def test_role_guidance_round_trips_an_absolute_root_with_shell_characters(
    root: Path, step, tmp_path: Path, turns: Path
) -> None:
    _crafted(root, step)
    spaced_root = root.parent / "root with spaces;and$metacharacters"
    root.rename(spaced_root)
    spaced_step = stepper(spaced_root, tmp_path, turns)
    code, out, err = run_cli_in_process(
        ["verify", "--repo-root", str(spaced_root)],
        cwd=spaced_root,
        catch_all=True,
    )
    assert code == 0, out + err
    verified = block(out, err)
    candidate = verified["CANDIDATE"]
    assert shlex.split(verified["NEXT"]) == [
        "des",
        "prepare-role",
        "--repo-root",
        str(spaced_root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    ]
    prepared, _ = _prepare(spaced_root, spaced_step, "reviewer", candidate)
    assert shlex.split(prepared["NEXT"]) == [
        "des",
        "invoke-role",
        "--repo-root",
        str(spaced_root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--input",
        prepared["INPUT"],
    ]
    code, recorded, out, err = _record(
        spaced_root,
        spaced_step,
        role="reviewer",
        candidate=candidate,
        session_id="shell-safe-reviewer-session",
        payload=_host_result("reviewer", "rejected", "reviewer rejected"),
    )
    assert code == 0, out + err
    assert shlex.split(recorded["NEXT"]) == [
        "des",
        "prepare-role",
        "--repo-root",
        str(spaced_root),
        "--role",
        "examiner",
        "--candidate",
        candidate,
    ]


def _record(
    root: Path,
    step,
    *,
    role: str,
    candidate: str,
    session_id: str,
    payload: str,
    prepared_input: Path | None = None,
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
        *(("--prepared-input", str(prepared_input)) if prepared_input else ()),
        stdin=payload,
    )
    return code, block(out, err), out, err


@pytest.mark.parametrize("duplicate", [False, True], ids=["normal", "duplicate"])
def test_preparing_review_and_examine_adds_no_native_execution_and_a_duplicate_is_observed(
    root: Path, step, turns: Path, tmp_path: Path, monkeypatch, duplicate: bool
) -> None:
    """Normal chain keeps the native counter at 1 through integrate; the
    duplicate control replays the declared argv inside reviewer prepare and
    the same counter assertion must fail on it."""
    counter = tmp_path / "declared-argv-invocations"
    argv = _crafted_counting(root, step, counter)
    # The candidate source has a marker that no native output contains.  It
    # distinguishes a DES-supplied diff leak from the allowed opaque output.
    (root / TARGET).write_text(f"VALUE = 1\n# {SOURCE_ONLY_MARKER}\n", encoding="utf-8")
    turns_before_verify = asked(turns)
    candidate, verified, native_counter = _provider_free_verify(root, tmp_path, counter)
    assert asked(turns) == turns_before_verify
    native_record = root / verified["NATIVE-EVIDENCE"]
    native_bytes = native_record.read_bytes()
    assert (
        hashlib.sha256(native_bytes).hexdigest() == verified["NATIVE-EVIDENCE-SHA256"]
    )

    turns_before_artifacts = asked(turns)
    if duplicate:
        from des.cli import role_artifacts

        original = role_artifacts._prepared

        def replaying(*args, **kwargs):
            result = original(*args, **kwargs)
            # The outer native observer injects a pytest plugin through
            # PYTEST_ADDOPTS; the replayed nested pytest cannot import it under
            # this hermetic PYTHONPATH. Drop only that observer hook so the
            # declared argv itself still runs unchanged.
            replay_env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
            replay = subprocess.run(
                argv, cwd=root, env=replay_env, capture_output=True, text=True
            )
            assert replay.returncode == 0, (
                f"WHAT: injected duplicate replay exited {replay.returncode}: "
                f"{replay.stdout}{replay.stderr}"
            )
            return result

        monkeypatch.setattr(role_artifacts, "_prepared", replaying)
        _prepare(root, step, "reviewer", candidate)
        assert native_counter.read_text(encoding="utf-8") == "11", (
            "WHAT: injected duplicate run did not reach the declared counter. "
            "WHY: the control must prove the normal assertion can fail. "
            "HOW: fix the fixture so the wrapper executes the declared argv."
        )
        with pytest.raises(AssertionError):
            _assert_native_ran_once(native_counter, "after preparation/completion")
        return
    reviewer_prepared, reviewer_input = _prepare(root, step, "reviewer", candidate)
    observed = tmp_path / "observations.json"
    _write_packet(observed, _packet(root, candidate))
    examiner_prepared, examiner_input = _prepare(
        root, step, "examiner", candidate, observations=observed
    )
    assert asked(turns) == turns_before_artifacts
    _assert_native_ran_once(native_counter, "after preparation/completion")
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
        assert document["request"] == REQUEST
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
    # Source blindness is structural: native argv/stdout/stderr/cwd/radius
    # are withheld in full; the caller packet carries the public trace.
    examiner_document = json.loads(examiner_bytes)
    examiner_keys = _keys(examiner_document)
    # WHAT/WHY/HOW: native verification detail may reveal oracle identifiers
    # or source, so argv/stdout/stderr/cwd (and radius) equal the exact
    # withheld marker while exit/origin/duration/incomplete stay measured.
    native_entries = json.loads(native_bytes)
    assert len(examiner_document["native_evidence"]) == len(native_entries)
    for entry, native_entry in zip(
        examiner_document["native_evidence"], native_entries, strict=True
    ):
        for field in ("argv", "stdout", "stderr", "cwd"):
            assert entry[field] == WITHHELD, (
                f"WHAT: examiner native {field} is {entry.get(field)!r}, not "
                f"the withheld marker\nWHY: native detail may reveal oracle "
                f"identifiers or source\nHOW: project the exact marker"
            )
        assert entry["exit"] == native_entry["exit"]
        assert entry["origin"] == native_entry["origin"]
        assert entry["incomplete"] == native_entry["incomplete"]
    assert all(v == WITHHELD for v in _radius_values(examiner_document))
    assert examiner_document["public_observations"] == json.loads(observed.read_bytes())
    # Everything that is SOURCE, DIFF, or another role's OPINION stays
    # blind: only the public stimulus (argv/cwd) and the captured native
    # observation are ever visible to the examiner.
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
                prepared_input=examiner_input if role == "examiner" else None,
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
            prepared_input=examiner_input if role == "examiner" else None,
        )
        assert code == 0, out + err
        assert recorded["ROLE"] == role
        assert recorded["CANDIDATE"] == candidate
        assert recorded["OUTCOME"] == outcome
        expected_next = (
            f"des prepare-role --repo-root {root} --role examiner --candidate {candidate}"
            if role == "reviewer"
            else f"des integrate --repo-root {root} --candidate {candidate}"
        )
        assert recorded["NEXT"] == expected_next
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
            prepared_input=examiner_input if role == "examiner" else None,
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
            prepared_input=examiner_input if role == "examiner" else None,
        )
        assert code == 0 if role == "examiner" else code != 0, out + err
        assert result.read_bytes() == original
        results[role] = (result, original, session_id)

    reviewer_result, reviewer_result_bytes, _ = results["reviewer"]
    examiner_result, examiner_result_bytes, _ = results["examiner"]
    assert examiner_result != reviewer_result
    assert EXAMINER_SESSION.encode() in examiner_result_bytes
    assert REVIEWER_SESSION.encode() not in examiner_result_bytes
    assert REVIEWER_SESSION.encode() in reviewer_result_bytes
    assert EXAMINER_SESSION.encode() not in reviewer_result_bytes

    # A role receipt is not an admission gate: every closed examiner outcome
    # yields the same advisory mechanical continuation.
    code, rejected_examiner, out, err = _record(
        root,
        step,
        role="examiner",
        candidate=candidate,
        session_id="host-examiner-rejected-session",
        payload=_host_result("examiner", "rejected", "host examiner rejected"),
        prepared_input=examiner_input,
    )
    assert code == 0, out + err
    assert rejected_examiner["OUTCOME"] == "rejected"
    assert rejected_examiner["NEXT"] == (
        f"des integrate --repo-root {root} --candidate {candidate}"
    )
    assert asked(turns) == turns_before_artifacts
    _assert_native_ran_once(native_counter, "after preparation/completion")

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

    for stale_authority in (
        {**original_reviewer_input, "request_digest": "0" * 64},
        {**original_reviewer_input, "request": "a different, narrower Request"},
    ):
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
    _assert_native_ran_once(native_counter, "after integrate")


def test_optional_invoke_role_buys_one_selected_turn_without_fallback(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _, native_counter = _provider_free_verify(root, tmp_path, counter)
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    _assert_native_ran_once(native_counter, "after preparation/completion")
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
    assert lines["NEXT"] == (
        f"des prepare-role --repo-root {root} --role examiner --candidate {candidate}"
    )
    assert asked(turns) == [*turns_before_invoke, "nw-software-crafter-reviewer"]
    _assert_native_ran_once(native_counter, "after preparation/completion")
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
    assert examiner_lines["NEXT"] == (
        f"des integrate --repo-root {root} --candidate {candidate}"
    )
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
    _assert_native_ran_once(native_counter, "after preparation/completion")


INLINE_SOURCE_MARKER = "DES_INLINE_ARGV_SOURCE_ONLY_MARKER"


def _crafted_with_inline_code_command(root: Path, step) -> None:
    """Reach a crafted candidate whose second declared verification command
    embeds inline interpreter source (`python -c "<code>"`) instead of naming
    a file path. The marker lives only inside that inline code text -- never
    in the command's own stdout -- so a leak is distinguishable from the
    ordinary, legitimate stdout the command produces.
    """
    inline_code = (
        f"{INLINE_SOURCE_MARKER} = 'a production-shaped secret constant'\n"
        "print('second verification command finished')\n"
    )
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    _dcode, _dout, _derr = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "bound facts with a second inline-code verification command",
                    "design_facts": {
                        "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                        "paradigm": "object_oriented",
                        "decisions": ["one observable value"],
                        "oracle": ORACLE,
                        "acceptance_supports": [],
                        "verification": [
                            [sys.executable, "-m", "pytest", ORACLE],
                            [sys.executable, "-c", inline_code],
                        ],
                        "oracle_verification_index": 0,
                    },
                }
            }
        ],
    )
    assert _dcode == 0, _dout + _derr
    assert (
        step(
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored a red acceptance oracle",
                    },
                    "writes": {ORACLE: RED_ORACLE},
                },
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "the oracle set is admissible",
                    }
                },
            ],
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
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value behind its oracle",
                    },
                    "writes": {TARGET: "VALUE = 1\n"},
                }
            ],
        )[0]
        == 0
    )


def test_examiner_artifact_withholds_inline_argv_source_but_keeps_useful_regular_commands(
    root: Path, step, tmp_path: Path
) -> None:
    """Public behavior: a regular declared command (no inline code) still
    hands the examiner a useful `argv`/`cwd`. A command whose argv embeds
    inline interpreter source must not leak that source body into the
    examiner artifact -- withheld with an explicit reason, not silent
    omission -- while the raw native evidence and the reviewer artifact
    keep the full, un-redacted command.
    """
    _crafted_with_inline_code_command(root, step)
    candidate, verified, _ = _provider_free_verify(root, tmp_path)
    native_record = root / verified["NATIVE-EVIDENCE"]
    native_bytes = native_record.read_bytes()
    native_entries = json.loads(native_bytes)
    assert len(native_entries) == 2
    # Raw native evidence keeps the full inline command, unredacted.
    assert any(
        INLINE_SOURCE_MARKER in json.dumps(entry.get("argv"))
        for entry in native_entries
    )

    _reviewer_prepared, reviewer_input = _prepare(root, step, "reviewer", candidate)
    reviewer_bytes = reviewer_input.read_bytes()
    # Reviewer input carries the full-diff/native context; it too is not
    # source-blind, so the inline command's own source may still appear here.
    assert INLINE_SOURCE_MARKER.encode() in reviewer_bytes

    _examiner_prepared, examiner_input = _prepare(root, step, "examiner", candidate)
    examiner_bytes = examiner_input.read_bytes()
    examiner_document = json.loads(examiner_bytes)

    # WHAT/WHY/HOW: the source-blind examiner must never receive the inline
    # code text itself (it IS production/oracle source, not a path) -- but
    # silently dropping the whole entry would be worse, leaving the examiner
    # unable to tell a command ran at all. Fix under review (V4-23): the
    # inline-code entry is replaced by an explicit withheld marker naming the
    # reason, while every other, regular command still projects real argv/cwd.
    assert INLINE_SOURCE_MARKER.encode() not in examiner_bytes, (
        f"WHAT: the examiner artifact contains the inline source-only marker "
        f"{INLINE_SOURCE_MARKER!r}\n"
        f"WHY: an argv that embeds inline interpreter code IS production/"
        f"oracle source text, and source-blindness forbids the examiner from "
        f"ever seeing that text\n"
        f"HOW: project a withheld placeholder for that one native-evidence "
        f"entry's `argv` instead of the raw inline-code tokens"
    )

    entries = examiner_document["native_evidence"]
    assert len(entries) == 2
    regular_entry, inline_entry = entries[0], entries[1]

    # Every native detail is withheld by the exact marker, regular or inline.
    for entry in (regular_entry, inline_entry):
        for field in ("argv", "stdout", "stderr", "cwd"):
            assert entry[field] == WITHHELD, (
                f"WHAT: examiner native {field} is {entry.get(field)!r}\n"
                f"WHY: native detail may reveal oracle identifiers or source\n"
                f"HOW: project the exact withheld marker"
            )
    assert regular_entry["exit"] == native_entries[0]["exit"]
    assert inline_entry["exit"] == native_entries[1]["exit"]


def test_examiner_argv_projection_boundary_table() -> None:
    """Regression for a falsified prior review: `_examiner_argv` must key
    withholding off a recognized INTERPRETER's own inline-code flag, not off
    any argv token that merely spells `-c`/`-e`. A non-interpreter tool using
    the same letter (`go test -c`, `grep -e PATTERN`) stays public; a real
    interpreter's inline-code flag is withheld; `python -m tool -c ...` stays
    public because `-m` hands the rest of argv to the named tool.
    """
    public_cases = [
        ["go", "test", "-c", "./..."],
        ["grep", "-e", "RUNNING", "events.log"],
        ["python", "-m", "pytest", "-c", "pytest.ini"],
        ["python", "-m", "pip", "install", "-e", "."],
        ["python", "-m", "pytest", ORACLE],
        ["python", "script.py", "-c"],
    ]
    for argv in public_cases:
        assert _examiner_argv(argv) == argv, (
            f"WHAT: {argv!r} was withheld\n"
            f"WHY: no token here is a recognized interpreter's own "
            f"inline-code flag\n"
            f"HOW: only withhold when argv[0] is a recognized interpreter "
            f"and its inline-code flag appears before -m or the script path"
        )

    withheld_cases = [
        ["python", "-c", "print(1)"],
        ["python3", "-c", "print(1)"],
        ["python3.11", "-c", "print(1)"],
        ["/usr/bin/python3", "-c", "print(1)"],
        ["sh", "-c", "echo hi"],
        ["bash", "-c", "echo hi"],
        ["node", "-e", "console.log(1)"],
        ["node", "--eval", "console.log(1)"],
        ["ruby", "-e", "puts 1"],
        ["perl", "-e", "print 1"],
        ["python", "-cprint(1)"],
        ["python", "-Ic", "print(1)"],
        ["bash", "-lc", "echo source"],
        ["node", "--eval=console.log(1)"],
        ["python", "-W", "ignore", "-c", "print(1)"],
    ]
    for argv in withheld_cases:
        projected = _examiner_argv(argv)
        assert isinstance(projected, dict) and projected.get("withheld") is True, (
            f"WHAT: {argv!r} was projected as {projected!r}\n"
            f"WHY: argv[0] is a recognized interpreter invoked with its own "
            f"inline-code flag\n"
            f"HOW: project a withheld marker naming the reason"
        )


def test_host_records_implementation_finding_without_buying_a_correction_turn(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    _crafted(root, step)
    candidate, _, _ = _provider_free_verify(root, tmp_path)
    _prepare(root, step, "reviewer", candidate)
    before = asked(turns)
    payload = json.dumps(
        {
            "structured_output": {
                "outcome": "rejected",
                "diagnostic": "Receipt duplicates the existing tax rule; change its implementation.",
                "defect_owner": "implementation",
                "defect_value": None,
            }
        }
    )
    code, lines, out, err = _record(
        root,
        step,
        role="reviewer",
        candidate=candidate,
        session_id="implementation-owner-session",
        payload=payload,
    )
    assert code == 0, out + err
    result = json.loads((root / lines["RESULT"]).read_text())
    assert result["result"]["outcome"] == "rejected"
    assert result["result"]["defect_owner"] == "implementation"
    assert result["result"]["defect_value"] is None
    assert asked(turns) == before
    print(
        json.dumps(
            {
                "operation": "record-role-result",
                "exit": code,
                "terminal": out,
                "recorded_result": result,
                "turns_before": before,
                "turns_after": asked(turns),
            }
        )
    )


def _selected_criteria():
    return [
        {
            "id": "result-visible",
            "stimulus": "Read the public value.",
            "expected": "The result is one.",
        },
        {
            "id": "evidence-kept",
            "stimulus": f"Inspect {ORACLE}::test_value after revision.",
            "expected": f"Keep prior evidence from {TARGET}; it is historical.",
        },
    ]


def _assert_selected_criteria(document):
    entries = document.get("selected_acceptance")
    assert isinstance(entries, list) and len(entries) == 1
    expected = [
        {**_selected_criteria()[0], "redacted_fields": []},
        {
            "id": "evidence-kept",
            "stimulus": "Inspect [withheld repository locator] after revision.",
            "expected": "Keep prior evidence from [withheld repository locator]; it is historical.",
            "redacted_fields": ["stimulus", "expected"],
        },
    ]
    assert entries[0]["value"] == 1
    assert entries[0]["source"] == "DISTILL"
    assert entries[0]["criteria"] == expected
    assert len(entries[0]["revision_sha256"]) == 64


@pytest.mark.parametrize("locator_id", [False, True])
def test_examiner_input_seals_candidate_bound_caller_observations_without_native_detail(
    root: Path, step, turns: Path, tmp_path: Path, locator_id: bool
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    criteria = _selected_criteria()
    if locator_id:
        criteria[0]["id"] = ORACLE
    _crafted_counting(root, step, counter, criteria=criteria)
    candidate, verified, native_counter = _provider_free_verify(root, tmp_path, counter)
    native_bytes = (root / verified["NATIVE-EVIDENCE"]).read_bytes()
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    reviewer_bytes = reviewer_input.read_bytes()
    observed = tmp_path / "observations.json"
    packet_bytes = _write_packet(observed, _packet(root, candidate))
    if locator_id:
        before = _role_files(root)
        turns_before = asked(turns)
        code, out, err = step(
            "prepare-role",
            "--repo-root",
            str(root),
            "--role",
            "examiner",
            "--candidate",
            candidate,
            "--observations",
            str(observed),
        )
        assert code != 0 and "LocatorBearingCriterionId" in out + err
        assert _role_files(root) == before and asked(turns) == turns_before
        return
    _, examiner_input = _prepare(
        root, step, "examiner", candidate, observations=observed
    )
    document = json.loads(examiner_input.read_bytes())
    _assert_selected_criteria(document)
    assert "selected_acceptance" not in json.loads(reviewer_bytes)
    assert document["public_observations"] == json.loads(packet_bytes)
    assert document["candidate_sha"] == candidate
    assert (
        document["public_observations"]["candidate_tree_sha"]
        == document["candidate_tree_sha"]
    )
    assert document["observations_provenance"] == {
        "origin": "caller_supplied",
        "measured_by_des": False,
        "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "packet_bytes": len(packet_bytes),
        "checked": ["shape", "candidate_identity", "size", "known_path_strings"],
        "unverified": [
            "capture_authenticity",
            "declared_substrate",
            "copied_source_or_selectors",
        ],
    }
    assert document["payload_sha256"] == _payload_sha256(document)
    for entry in document["native_evidence"]:
        assert all(entry[f] == WITHHELD for f in ("argv", "stdout", "stderr", "cwd"))
    assert all(v == WITHHELD for v in _radius_values(document))
    assert ORACLE.encode() not in examiner_input.read_bytes()
    assert TARGET.encode() not in examiner_input.read_bytes()
    # Reviewer is prepared without the packet and keeps full native evidence.
    assert reviewer_input.read_bytes() == reviewer_bytes
    assert b"observations_provenance" not in reviewer_bytes or (
        json.loads(reviewer_bytes).get("observations_provenance") is None
    )
    assert ORACLE.encode() in reviewer_bytes
    assert (root / verified["NATIVE-EVIDENCE"]).read_bytes() == native_bytes
    _assert_native_ran_once(native_counter, "after preparation")


def _pointer_token(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


_PARSE_STOP = ("not_utf8", "not_json")
_NOT_RUN = "not run: shape, candidate_identity, known_path_strings"


_TB = ("wrong_type", "bad_value")
_HEX = ("bad_value", "wrong_type")


def _grammar_cases(root: Path, candidate: str, text: str):
    """Every closed v1 grammar equivalence class, one row each."""
    tree = _tree_sha(root, candidate)
    assert candidate.upper() != candidate and tree.upper() != tree, (
        "fixture candidate/tree must contain a hex letter to test lowercase"
    )
    rows = []

    def add(label, mutate, codes, pointer, stop=False):
        packet = json.loads(text)
        mutate(packet)
        rows.append(
            (
                label,
                json.dumps(packet, sort_keys=True).encode(),
                [(codes, pointer)],
                stop,
            )
        )

    def event(p, index=0):
        return p["scenarios"][0]["events"][index]

    def set_at(getter, key, value):
        def mutate(p):
            getter(p)[key] = value

        return mutate

    def drop_at(getter, key):
        def mutate(p):
            del getter(p)[key]

        return mutate

    top = lambda p: p  # noqa: E731
    scen = lambda p: p["scenarios"][0]  # noqa: E731

    def ev0(p):
        return event(p)

    stim = lambda p: event(p)["stimulus"]  # noqa: E731
    resp = lambda p: event(p)["response"]  # noqa: E731
    st = lambda p: event(p)["state"]  # noqa: E731
    prod = lambda p: p["producer"]  # noqa: E731
    S, E = "/scenarios/0", "/scenarios/0/events/0"

    def second_event(p, **fields):
        p["scenarios"][0]["events"].append(
            {**json.loads(json.dumps(event(p))), **fields}
        )

    def two_scenarios(p, **fields):
        p["scenarios"].append({**json.loads(json.dumps(scen(p))), **fields})

    # top level
    rows.append(("top-not-object", b"[]", [(_TB, "")], False))
    add("schema-not-string", set_at(top, "schema", 1), _TB, "/schema")
    add("version-two", set_at(top, "version", 2), ("bad_value",), "/version")
    add("version-float", set_at(top, "version", 1.0), _TB, "/version")
    add("version-string", set_at(top, "version", "1"), _TB, "/version")
    add("missing-schema", drop_at(top, "schema"), ("missing_key",), "")
    add(
        "candidate-uppercase",
        set_at(top, "candidate_sha", candidate.upper()),
        _HEX + ("stale_candidate",),
        "/candidate_sha",
    )
    add(
        "candidate-not-hex",
        set_at(top, "candidate_sha", "z" * 40),
        _HEX + ("stale_candidate",),
        "/candidate_sha",
    )
    add(
        "candidate-short",
        set_at(top, "candidate_sha", candidate[:39]),
        _HEX + ("stale_candidate",),
        "/candidate_sha",
    )
    add("candidate-not-string", set_at(top, "candidate_sha", 5), _TB, "/candidate_sha")
    add(
        "tree-uppercase",
        set_at(top, "candidate_tree_sha", tree.upper()),
        _HEX + ("stale_tree",),
        "/candidate_tree_sha",
    )
    add(
        "tree-not-hex",
        set_at(top, "candidate_tree_sha", "z" * 40),
        _HEX + ("stale_tree",),
        "/candidate_tree_sha",
    )
    add(
        "tree-not-string",
        set_at(top, "candidate_tree_sha", 5),
        _TB,
        "/candidate_tree_sha",
    )
    # producer
    add("producer-not-object", set_at(top, "producer", "x"), _TB, "/producer")
    add(
        "producer-extra-key",
        set_at(prod, "extra", 1),
        ("unknown_key",),
        "/producer/extra",
    )
    add(
        "producer-missing-version",
        drop_at(prod, "version"),
        ("missing_key",),
        "/producer",
    )
    add("producer-id-empty", set_at(prod, "id", ""), _TB, "/producer/id")
    add("producer-id-129", set_at(prod, "id", "a" * 129), _TB, "/producer/id")
    add("producer-id-not-string", set_at(prod, "id", 1), _TB, "/producer/id")
    add("producer-version-empty", set_at(prod, "version", ""), _TB, "/producer/version")
    add(
        "producer-version-65",
        set_at(prod, "version", "1" * 65),
        _TB,
        "/producer/version",
    )
    add(
        "producer-version-not-string",
        set_at(prod, "version", 1),
        _TB,
        "/producer/version",
    )
    # states
    add("states-not-object", set_at(top, "states", []), _TB, "/states")
    for bad in ("bad", "S0", "S123456", "s1", "S01"):
        add(
            f"states-key-{bad}",
            lambda p, bad=bad: p["states"].update({bad: 1}),
            ("bad_value",),
            f"/states/{bad}",
        )
    add("missing-states", drop_at(top, "states"), ("missing_key",), "")
    # scenarios
    add("scenarios-empty", set_at(top, "scenarios", []), ("bad_value",), "/scenarios")
    add("scenarios-not-array", set_at(top, "scenarios", {}), _TB, "/scenarios")
    add("scenario-not-object", set_at(top, "scenarios", [1]), _TB, S)
    add("scenario-extra-key", set_at(scen, "extra", 1), ("unknown_key",), S + "/extra")
    add("scenario-missing-purpose", drop_at(scen, "purpose"), ("missing_key",), S)
    for label, value in (
        ("leading-dot", ".a"),
        ("empty", ""),
        ("space", "a b"),
        ("65-chars", "a" * 65),
        ("slash", "a/b"),
    ):
        add(
            f"scenario-id-{label}", set_at(scen, "id", value), ("bad_value",), S + "/id"
        )
    add("scenario-id-not-string", set_at(scen, "id", 1), _TB, S + "/id")
    add(
        "scenario-id-duplicate",
        two_scenarios,
        ("bad_value",),
        "/scenarios/1/id",
    )
    add(
        "substrate-unknown",
        set_at(scen, "substrate", "real_host"),
        ("bad_value",),
        S + "/substrate",
    )
    add("substrate-not-string", set_at(scen, "substrate", 1), _TB, S + "/substrate")
    add("purpose-empty", set_at(scen, "purpose", ""), _TB, S + "/purpose")
    add("purpose-513", set_at(scen, "purpose", "p" * 513), _TB, S + "/purpose")
    add("purpose-not-string", set_at(scen, "purpose", 1), _TB, S + "/purpose")
    add("events-empty", set_at(scen, "events", []), ("bad_value",), S + "/events")
    add("events-not-array", set_at(scen, "events", {}), _TB, S + "/events")
    # events
    add("event-extra-key", set_at(ev0, "extra", 1), ("unknown_key",), E + "/extra")
    add("event-missing-counter", drop_at(ev0, "counter"), ("missing_key",), E)
    for label, value in (
        ("zero", 0),
        ("negative", -1),
        ("bool", True),
        ("float", 1.5),
        ("string", "1"),
    ):
        add(f"seq-{label}", set_at(ev0, "seq", value), _TB, E + "/seq")
    add(
        "seq-equal",
        lambda p: second_event(p, seq=1),
        ("bad_value",),
        "/scenarios/0/events/1/seq",
    )
    add(
        "seq-decreasing",
        lambda p: (event(p).update(seq=5), second_event(p, seq=2)),
        ("bad_value",),
        "/scenarios/0/events/1/seq",
    )
    add(
        "stimulus-extra-key",
        set_at(stim, "extra", 1),
        ("unknown_key",),
        E + "/stimulus/extra",
    )
    add(
        "stimulus-missing-stdin",
        drop_at(stim, "stdin"),
        ("missing_key",),
        E + "/stimulus",
    )
    add("argv-empty", set_at(stim, "argv", []), ("bad_value",), E + "/stimulus/argv")
    add("argv-not-array", set_at(stim, "argv", "des"), _TB, E + "/stimulus/argv")
    add(
        "argv0-empty",
        lambda p: stim(p)["argv"].__setitem__(0, ""),
        ("bad_value",),
        E + "/stimulus/argv/0",
    )
    add(
        "argv-element-not-string",
        lambda p: stim(p)["argv"].__setitem__(1, 1),
        _TB,
        E + "/stimulus/argv/1",
    )
    add(
        "stdin-not-string-or-null", set_at(stim, "stdin", 5), _TB, E + "/stimulus/stdin"
    )
    for label, value in (
        ("string", "0"),
        ("bool", True),
        ("float", 0.5),
        ("null", None),
    ):
        add(f"exit-{label}", set_at(resp, "exit", value), _TB, E + "/response/exit")
    add("stdout-not-string", set_at(resp, "stdout", 1), _TB, E + "/response/stdout")
    add("stderr-not-string", set_at(resp, "stderr", None), _TB, E + "/response/stderr")
    add(
        "response-extra-key",
        set_at(resp, "extra", 1),
        ("unknown_key",),
        E + "/response/extra",
    )
    add(
        "response-missing-exit",
        drop_at(resp, "exit"),
        ("missing_key",),
        E + "/response",
    )
    add("state-not-object", set_at(ev0, "state", "S1"), _TB, E + "/state")
    add("state-extra-key", set_at(st, "extra", 1), ("unknown_key",), E + "/state/extra")
    add("state-missing-after", drop_at(st, "after"), ("missing_key",), E + "/state")
    add(
        "state-before-unresolved",
        set_at(st, "before", "S9"),
        ("unresolved_ref",),
        E + "/state/before",
    )
    add(
        "state-after-unresolved",
        set_at(st, "after", "S9"),
        ("unresolved_ref",),
        E + "/state/after",
    )
    add("state-ref-not-string", set_at(st, "after", 5), _TB, E + "/state/after")
    # counter
    add("counter-not-object", set_at(ev0, "counter", 5), _TB, E + "/counter")
    ok = {"before": 0, "after": 1}
    for label, value in (
        ("negative", -1),
        ("bool", True),
        ("float", 1.5),
        ("string", "1"),
        ("null", None),
    ):
        add(
            f"counter-before-{label}",
            set_at(ev0, "counter", {**ok, "before": value}),
            _TB,
            E + "/counter/before",
        )
        add(
            f"counter-after-{label}",
            set_at(ev0, "counter", {**ok, "after": value}),
            _TB,
            E + "/counter/after",
        )
    add(
        "counter-extra-key",
        set_at(ev0, "counter", {**ok, "extra": 1}),
        ("unknown_key",),
        E + "/counter/extra",
    )
    add(
        "counter-missing-after",
        set_at(ev0, "counter", {"before": 0}),
        ("missing_key",),
        E + "/counter",
    )
    # additional known-path screens (values at every depth)
    add(
        "path-in-stderr",
        lambda p: resp(p).update(stderr=f"x {ORACLE}"),
        ("path_bearing",),
        E + "/response/stderr",
    )
    add(
        "path-in-purpose",
        set_at(scen, "purpose", f"see {TARGET}"),
        ("path_bearing",),
        S + "/purpose",
    )
    add(
        "path-in-producer-id",
        set_at(prod, "id", ORACLE),
        ("path_bearing",),
        "/producer/id",
    )
    add(
        "path-in-nested-state-list",
        lambda p: p["states"].update({"S1": {"rows": [{"note": TARGET}]}}),
        ("path_bearing",),
        "/states/S1/rows/0/note",
    )
    # U+0000 in any string, keys and values at any depth
    add(
        "nul-in-stdout",
        lambda p: resp(p).update(stdout="a\u0000b"),
        ("bad_value",),
        E + "/response/stdout",
    )
    add(
        "nul-in-purpose",
        set_at(scen, "purpose", "a\u0000b"),
        ("bad_value",),
        S + "/purpose",
    )
    add(
        "nul-in-argv",
        lambda p: stim(p)["argv"].append("a\u0000b"),
        ("bad_value",),
        E + "/stimulus/argv/4",
    )
    add(
        "nul-in-state-value",
        lambda p: p["states"].update({"S1": {"observation": "a\u0000b"}}),
        ("bad_value",),
        "/states/S1/observation",
    )
    add(
        "nul-in-producer-id",
        set_at(prod, "id", "a\u0000b"),
        ("bad_value",),
        "/producer/id",
    )
    return [
        (label, content, exp, None if label.startswith("nul") else stop)
        for label, content, exp, stop in rows
    ]


def _refusal_cases(root: Path, candidate: str, tmp_path: Path):
    """(id, bytes|None, [(accepted codes, pointer)], parse_stopped)."""
    valid = _packet(root, candidate)
    text = json.dumps(valid, sort_keys=True)
    event = "/scenarios/0/events/0"

    def edited(mutate) -> bytes:
        packet = json.loads(text)
        mutate(packet)
        return json.dumps(packet, sort_keys=True).encode()

    def in_stdout(packet):
        packet["scenarios"][0]["events"][0]["response"]["stdout"] = f"ran {ORACLE}"

    def in_state_value(packet):
        packet["states"]["S1"] = {"observation": f"see {TARGET}"}

    def in_state_key(packet):
        packet["states"]["S1"] = {ORACLE: 1}

    def in_argv(packet):
        packet["scenarios"][0]["events"][0]["stimulus"]["argv"].append(TARGET)

    def multi(packet):
        packet["candidate_sha"] = "0" * 40
        packet["surprise"] = 1
        in_stdout(packet)

    parse = (_PARSE_STOP, "")
    dup = text.replace('"version": 1', '"version": 1, "version": 1', 1)
    return [
        ("duplicate-key", dup.encode(), [parse], True),
        ("bom", b"\xef\xbb\xbf" + text.encode(), [parse], True),
        (
            "nan",
            text.replace('"version": 1', '"version": NaN', 1).encode(),
            [parse],
            True,
        ),
        (
            "infinity",
            text.replace('"version": 1', '"version": Infinity', 1).encode(),
            [parse],
            True,
        ),
        ("not-utf8", b"\xff\xfe{", [parse], True),
        ("malformed", b"{not json", [parse], True),
        ("trailing-data", text.encode() + b" {}", [parse], True),
        (
            "oversize",
            text.encode().ljust(MAX_PACKET_BYTES + 1),
            [(("oversize",), "")],
            True,
        ),
        ("unreadable", None, [(("unreadable",), "")], True),
        (
            "boolean-version",
            edited(lambda p: p.update(version=True)),
            [(("wrong_type", "bad_value"), "/version")],
            False,
        ),
        (
            "unknown-key",
            edited(lambda p: p.update(surprise=1)),
            [(("unknown_key",), "/surprise")],
            False,
        ),
        (
            "unknown-key-carrying-path",
            edited(lambda p: p.update({"surprise": ORACLE})),
            [
                (("path_bearing",), "/surprise"),
                (("unknown_key",), "/surprise"),
            ],
            False,
        ),
        (
            "missing-key",
            edited(lambda p: p.pop("producer")),
            [(("missing_key",), "")],
            False,
        ),
        (
            "bad-value",
            edited(lambda p: p.update(schema="something.else")),
            [(("bad_value",), "/schema")],
            False,
        ),
        (
            "unresolved-ref",
            edited(
                lambda p: p["scenarios"][0]["events"][0]["stimulus"].update(stdin="S9")
            ),
            [(("unresolved_ref",), f"{event}/stimulus/stdin")],
            False,
        ),
        (
            "stale-candidate",
            edited(lambda p: p.update(candidate_sha="0" * 40)),
            [(("stale_candidate",), "/candidate_sha")],
            False,
        ),
        (
            "stale-tree",
            edited(lambda p: p.update(candidate_tree_sha="0" * 40)),
            [(("stale_tree",), "/candidate_tree_sha")],
            False,
        ),
        (
            "path-in-value",
            edited(in_stdout),
            [(("path_bearing",), f"{event}/response/stdout")],
            False,
        ),
        (
            "path-in-state-value",
            edited(in_state_value),
            [(("path_bearing",), "/states/S1/observation")],
            False,
        ),
        (
            "path-in-object-key",
            edited(in_state_key),
            [(("path_bearing",), f"/states/S1/{_pointer_token(ORACLE)}")],
            False,
        ),
        (
            "path-in-argv",
            edited(in_argv),
            [(("path_bearing",), f"{event}/stimulus/argv/4")],
            False,
        ),
        (
            "multi-defect",
            edited(multi),
            [
                (("stale_candidate",), "/candidate_sha"),
                (("path_bearing",), f"{event}/response/stdout"),
                (("unknown_key",), "/surprise"),
            ],
            False,
        ),
    ] + _grammar_cases(root, candidate, text)


def test_examiner_observations_packet_is_refused_when_stale_source_bearing_malformed_or_oversized(
    root: Path, step, tmp_path: Path
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _verified, native_counter = _provider_free_verify(
        root, tmp_path, counter
    )
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    reviewer_bytes = reviewer_input.read_bytes()
    before = _role_files(root)

    def prepare(role: str, path: Path):
        return step(
            "prepare-role",
            "--repo-root",
            str(root),
            "--role",
            role,
            "--candidate",
            candidate,
            "--observations",
            str(path),
        )

    for label, content, expected, parse_stopped in _refusal_cases(
        root, candidate, tmp_path
    ):
        target = tmp_path / f"{label}.json"
        if content is not None:
            target.write_bytes(content)
        code, out, err = prepare("examiner", target)
        text = out + err
        what = (
            f"WHAT: {label} packet got code={code}: {text!r}\n"
            "WHY: an invalid packet must be refused as ObservationPacketRefused "
            "with numbered closed codes at RFC 6901 pointers\n"
            "HOW: collect every defect, refuse before writing any role input"
        )
        assert code != 0 and "ObservationPacketRefused" in text, what
        positions = []
        for codes, pointer in expected:
            found = [
                text.find(f"{c} at {pointer}:")
                for c in codes
                if f"{c} at {pointer}:" in text
            ]
            assert found, what
            positions.append(found[0])
        assert positions == sorted(positions), what + "\n(defects must sort by pointer)"
        if len(expected) > 1:
            assert f"{len(expected)} defect" in text, what
            assert all(f"{i}. " in text for i in range(1, len(expected) + 1)), what
        if parse_stopped is None:
            pass
        elif parse_stopped:
            assert _NOT_RUN in text, what
        else:
            assert "not run:" not in text, what
        assert "--observations" in text and "public_observation_capture" in text, what
        assert _role_files(root) == before, what
    code, out, err = prepare("reviewer", _write_good(root, candidate, tmp_path))
    assert (
        code != 0
        and "ObservationPacketRefused" in out + err
        and "role_not_examiner" in out + err
    )
    assert _role_files(root) == before
    _assert_native_ran_once(native_counter, "after refused preparations")
    assert reviewer_input.read_bytes() == reviewer_bytes


def _write_good(root: Path, candidate: str, tmp_path: Path) -> Path:
    good = tmp_path / "good.json"
    _write_packet(good, _packet(root, candidate))
    return good


def test_examiner_observation_revisions_keep_prior_inputs_and_results(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _verified, native_counter = _provider_free_verify(
        root, tmp_path, counter
    )
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    reviewer_bytes = reviewer_input.read_bytes()
    valid = _packet(root, candidate)
    # Every documented upper bound is admitted at its limit.
    valid["producer"] = {"id": "p" * 128, "version": "v" * 64}
    valid["scenarios"][0]["id"] = "a" * 64
    valid["scenarios"][0]["purpose"] = "u" * 512
    # Exactly 65,536 bytes is admitted.
    exact = tmp_path / "exact.json"
    _write_packet(exact, valid, size=MAX_PACKET_BYTES)
    assert exact.stat().st_size == MAX_PACKET_BYTES
    _, examiner_input = _prepare(root, step, "examiner", candidate, observations=exact)
    first = examiner_input.read_bytes()
    # A corrected observation seals a new exact input; the first remains retained.
    other = tmp_path / "other.json"
    _write_packet(
        other, {**valid, "producer": {"id": "another-capture", "version": "2"}}
    )
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "examiner",
        "--candidate",
        candidate,
        "--observations",
        str(other),
    )
    assert code == 0, out + err
    revised = root / block(out, err)["INPUT"]
    assert revised != examiner_input
    assert revised.name.startswith(f"{candidate}-examiner-")
    assert examiner_input.read_bytes() == first
    assert reviewer_input.read_bytes() == reviewer_bytes
    retained = {examiner_input: first, revised: revised.read_bytes()}
    recorded_paths: list[Path] = []
    for index, prepared in enumerate((examiner_input, revised)):
        turns_before = asked(turns)
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
            str(prepared),
            answers=[
                json.loads(
                    _host_result("examiner", "indeterminate", f"revision {index}")
                )
            ],
        )
        assert code == 0, out + err
        invoked = root / block(out, err)["RESULT"]
        assert (
            json.loads(invoked.read_bytes())["input_sha256"]
            == hashlib.sha256(prepared.read_bytes()).hexdigest()
        )
        retained[invoked] = invoked.read_bytes()
        assert asked(turns) == turns_before + ["nw-user-examiner"]
        code, recorded, out, err = _record(
            root,
            step,
            role="examiner",
            candidate=candidate,
            session_id="same-observation-session",
            payload=_host_result("examiner", "indeterminate", "host observation"),
            prepared_input=prepared,
        )
        assert code == 0, out + err
        result_path = root / recorded["RESULT"]
        result = json.loads(result_path.read_bytes())
        assert (
            result["input_sha256"] == hashlib.sha256(prepared.read_bytes()).hexdigest()
        )
        recorded_paths.append(result_path)
        retained[result_path] = result_path.read_bytes()
        assert all(path.read_bytes() == raw for path, raw in retained.items())
    assert recorded_paths[0] != recorded_paths[1]
    code, _lines, out, err = _record(
        root,
        step,
        role="examiner",
        candidate=candidate,
        session_id="implicit-revision",
        payload=_host_result("examiner", "accepted", "must not guess"),
    )
    assert code != 0 and "--prepared-input" in out + err
    _assert_native_ran_once(native_counter, "after refused preparations")


#: A small closed population of same-candidate packet B variations. Each one
#: differs from packet A in both producer identity AND the captured event's
#: response content, so a revision is never merely a metadata edit.
_REVISION_PRODUCER_IDS = ["capture-alpha", "capture-beta", "capture-gamma"]
_REVISION_STDOUT_VARIANTS = [
    "DELIVERY-OUTCOME: Success (rerun)",
    "DELIVERY-OUTCOME: Success -- alternate capture",
    "DELIVERY-OUTCOME: Success; second observation",
]


@given(
    producer_b=st.sampled_from(_REVISION_PRODUCER_IDS),
    stdout_b=st.sampled_from(_REVISION_STDOUT_VARIANTS),
)
@settings(
    max_examples=3,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_examiner_observation_revisions_hold_for_a_generated_packet_population(
    tmp_path_factory, producer_b: str, stdout_b: str
) -> None:
    """The kept-inputs/kept-results law of the fixed regression above, replayed
    deterministically over a small diverse population of same-candidate packet
    A/B pairs that differ in both producer id and captured event/response, not
    merely in one byte. No new state machine, evidence union or liveness claim
    is introduced -- this only widens the existing revision law's coverage.

    Each generated example builds its own checkout/step harness (rather than
    the shared `root`/`step` fixtures), because Hypothesis reuses one
    function-scoped fixture instance across every example it draws, and this
    scenario's setup (a committed declared-argv script, a verified candidate)
    is consumed, not idempotent, across repeats.
    """
    workspace = tmp_path_factory.mktemp("examiner-revision")
    root = base_repository(workspace / "root")
    turns = workspace / "model-log.json"
    step = stepper(root, workspace, turns)
    counter = workspace / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, verified, native_counter = _provider_free_verify(
        root, workspace, counter
    )
    native_record = root / verified["NATIVE-EVIDENCE"]
    native_bytes = native_record.read_bytes()
    assert (
        hashlib.sha256(native_bytes).hexdigest() == verified["NATIVE-EVIDENCE-SHA256"]
    )
    candidate_bytes = _candidate_object_bytes(root, candidate)
    _, reviewer_input = _prepare(root, step, "reviewer", candidate)
    reviewer_bytes = reviewer_input.read_bytes()
    assert _candidate_object_bytes(root, candidate) == candidate_bytes

    packet_a = _packet(root, candidate)
    a_path = workspace / "packet-a.json"
    _write_packet(a_path, packet_a)

    packet_b = _packet(root, candidate, producer={"id": producer_b, "version": "2"})
    packet_b["scenarios"][0]["events"][0]["response"]["stdout"] = stdout_b
    assert packet_b != packet_a
    b_path = workspace / "packet-b.json"
    _write_packet(b_path, packet_b)

    prepared_a, examiner_input_a = _prepare(
        root, step, "examiner", candidate, observations=a_path
    )
    first = examiner_input_a.read_bytes()
    assert prepared_a["CANDIDATE"] == candidate

    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "examiner",
        "--candidate",
        candidate,
        "--observations",
        str(b_path),
    )
    assert code == 0, out + err
    prepared_b = block(out, err)
    examiner_input_b = root / prepared_b["INPUT"]
    assert prepared_b["CANDIDATE"] == candidate

    # Candidate, native evidence and the unrelated reviewer input are untouched
    # by an examiner-only revision; the two selected inputs are distinct; the
    # first packet's exact bytes are retained under its own sealed name.
    assert examiner_input_b != examiner_input_a
    assert examiner_input_a.read_bytes() == first
    assert reviewer_input.read_bytes() == reviewer_bytes
    assert native_record.read_bytes() == native_bytes
    assert _candidate_object_bytes(root, candidate) == candidate_bytes

    result_bytes: dict[Path, bytes] = {}
    for index, prepared in enumerate((examiner_input_a, examiner_input_b)):
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
            str(prepared),
            answers=[
                json.loads(
                    _host_result("examiner", "indeterminate", "generated revision")
                )
            ],
        )
        assert code == 0, out + err
        invoked = root / block(out, err)["RESULT"]
        assert (
            json.loads(invoked.read_bytes())["input_sha256"]
            == hashlib.sha256(prepared.read_bytes()).hexdigest()
        )

        code, recorded, out, err = _record(
            root,
            step,
            role="examiner",
            candidate=candidate,
            session_id=f"generated-revision-session-{index}",
            payload=_host_result(
                "examiner", "indeterminate", f"generated recorded {index}"
            ),
            prepared_input=prepared,
        )
        assert code == 0, out + err
        result_path = root / recorded["RESULT"]
        result = json.loads(result_path.read_bytes())
        assert (
            result["input_sha256"] == hashlib.sha256(prepared.read_bytes()).hexdigest()
        )
        result_bytes[result_path] = result_path.read_bytes()
        # Every result recorded so far, plus the candidate/native evidence and
        # the unrelated reviewer input, stay byte-identical -- recording the
        # second observation must not disturb the first's sealed result.
        assert all(path.read_bytes() == raw for path, raw in result_bytes.items())
        assert examiner_input_a.read_bytes() == first
        assert reviewer_input.read_bytes() == reviewer_bytes
        assert native_record.read_bytes() == native_bytes
        assert _candidate_object_bytes(root, candidate) == candidate_bytes

    result_paths = list(result_bytes)
    assert result_paths[0] != result_paths[1]

    # Re-preparing the FIRST packet's unchanged bytes selects the original
    # sealed input again, not a third one.
    code, out, err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "examiner",
        "--candidate",
        candidate,
        "--observations",
        str(a_path),
    )
    assert code == 0, out + err
    reprepared_a = root / block(out, err)["INPUT"]
    assert reprepared_a == examiner_input_a
    assert reprepared_a.read_bytes() == first
    # Reselecting A after B's recording still preserves both sealed results,
    # the candidate/native evidence, and the unrelated reviewer input.
    assert all(path.read_bytes() == raw for path, raw in result_bytes.items())
    assert reviewer_input.read_bytes() == reviewer_bytes
    assert native_record.read_bytes() == native_bytes
    assert _candidate_object_bytes(root, candidate) == candidate_bytes

    # Recording without a selector must never guess among retained inputs.
    code, _lines, out, err = _record(
        root,
        step,
        role="examiner",
        candidate=candidate,
        session_id="generated-implicit-revision",
        payload=_host_result("examiner", "accepted", "must not guess"),
    )
    assert code != 0 and "--prepared-input" in out + err
    assert all(path.read_bytes() == raw for path, raw in result_bytes.items())

    _assert_native_ran_once(
        native_counter, "after generated-population revision preparations"
    )


def test_examiner_relative_prepared_input_is_rooted_at_repo_from_another_cwd(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _verified, native_counter = _provider_free_verify(
        root, tmp_path, counter
    )
    prepared, input_path = _prepare(root, step, "examiner", candidate)
    assert not Path(prepared["INPUT"]).is_absolute()

    away = tmp_path / "away"
    away.mkdir()
    launcher = tmp_path / "away-bin"
    results = tmp_path / "away-results.json"
    provider_counter = tmp_path / "away-results-consumed"
    environment = hermetic_environment(
        fake_provider.environment(
            root,
            launcher_dir=launcher,
            results=results,
            log=turns,
            counter=provider_counter,
            package_parent=PACKAGE_PARENT,
        ),
        tmp_path / "away-claude-config",
    )

    results.write_text(
        json.dumps([json.loads(_host_result("examiner", "indeterminate", "away"))])
    )
    code, out, err = run_cli_in_process(
        [
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
            prepared["INPUT"],
        ],
        cwd=away,
        env=environment,
        catch_all=True,
    )
    assert code == 0, out + err
    invoked = root / block(out, err)["RESULT"]
    assert (
        json.loads(invoked.read_bytes())["input_sha256"]
        == hashlib.sha256(input_path.read_bytes()).hexdigest()
    )

    code, out, err = run_cli_in_process(
        [
            "record-role-result",
            "--repo-root",
            str(root),
            "--role",
            "examiner",
            "--candidate",
            candidate,
            "--provider",
            "claude",
            "--model",
            "away-model",
            "--session-id",
            "away-session",
            "--input",
            "-",
            "--prepared-input",
            prepared["INPUT"],
        ],
        cwd=away,
        env=environment,
        stdin_text=_host_result("examiner", "indeterminate", "recorded away"),
        catch_all=True,
    )
    assert code == 0, out + err
    recorded = root / block(out, err)["RESULT"]
    assert (
        json.loads(recorded.read_bytes())["input_sha256"]
        == hashlib.sha256(input_path.read_bytes()).hexdigest()
    )
    _assert_native_ran_once(native_counter, "after alternate-cwd exact-input paths")


CAPTURE_PRODUCER = (
    Path(__file__).resolve().parents[4]
    / "tests/evals/atomic-selected-acceptance/public_observation_capture.py"
)


def _capture(root: Path, candidate: str, tmp_path: Path, stdout: str):
    row = {
        "seq": 1,
        "argv_repo_root_normalised": ["des", "verify", "--repo-root", "<repo>"],
        "stdin_present": False,
        "exit": 0,
        "stdout": stdout,
        "stderr": "",
        "handover_before": None,
        "handover_after": {"observation": "A user sees the verified outcome."},
        "declared_counter_before": {"c": ""},
        "declared_counter_after": {"c": "1"},
    }
    calls = tmp_path / "calls.jsonl"
    calls.write_text(json.dumps(row) + "\n", encoding="utf-8")
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "id": "V4-capture",
                        "substrate": "mock_provider",
                        "purpose": "Selected public verify call.",
                        "seqs": [1],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "captured-packet.json"
    done = subprocess.run(
        [
            sys.executable,
            str(CAPTURE_PRODUCER),
            "--repo-root",
            str(root),
            "--candidate",
            candidate,
            "--calls-jsonl",
            str(calls),
            "--selection-json",
            str(selection),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    return done, output


def test_capture_producer_feeds_a_sealed_examiner_input_and_refuses_owned_path_output(
    root: Path, step, turns: Path, tmp_path: Path
) -> None:
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _verified, native_counter = _provider_free_verify(
        root, tmp_path, counter
    )
    _prepare(root, step, "reviewer", candidate)

    done, output = _capture(root, candidate, tmp_path, "DELIVERY-OUTCOME: Success")
    assert done.returncode == 0 and output.is_file(), (
        f"WHAT: producer exited {done.returncode}: {done.stdout + done.stderr!r}\n"
        "WHY: a clean selection must yield a packet self-checked against the real "
        "prepared population\nHOW: make the producer reuse the stored handover"
    )
    _, examiner_input = _prepare(root, step, "examiner", candidate, observations=output)
    document = json.loads(examiner_input.read_bytes())
    assert document["public_observations"] == json.loads(output.read_bytes())
    assert document["public_observations"]["scenarios"][0]["events"][0]["counter"] == {
        "before": 0,
        "after": 1,
    }
    assert document["candidate_sha"] == candidate
    assert document["payload_sha256"] == _payload_sha256(document)
    _assert_native_ran_once(native_counter, "after capture and preparation")

    for owned in (TARGET, ORACLE):
        refused_dir = tmp_path / f"refused-{abs(hash(owned))}"
        refused_dir.mkdir()
        bad, absent = _capture(
            root, candidate, refused_dir, f"leaked {owned} in raw stdout"
        )
        assert bad.returncode != 0 and not absent.exists(), (
            f"WHAT: owned path {owned!r} in selected stdout gave exit "
            f"{bad.returncode}, output exists={absent.exists()}\n"
            "WHY: the producer self-check must hold the real owned-path population\n"
            "HOW: refuse and publish nothing"
        )
    _assert_native_ran_once(native_counter, "after refused captures")


def test_editing_a_declared_target_after_verify_makes_the_record_historical_for_state_and_prepare_role(
    root: Path, step, tmp_path: Path
) -> None:
    """A declared owned path edited after des verify expires that verification.

    Law: a verify record is current only while the candidate still contains every
    declared owned byte. The edit touches TARGET itself (a declared target), never
    an unowned marker, so state and prepare-role must agree the record moved.
    """
    counter = tmp_path / "declared-argv-invocations"
    _crafted_counting(root, step, counter)
    candidate, _verified, _ = _provider_free_verify(root, tmp_path, counter)

    code, before, err = step("state", "--repo-root", str(root))
    assert code == 0, before + err
    assert block(before)["CANDIDATE"] == f"{candidate} recorded", before
    ok_code, _ok_out, ok_err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    )
    assert ok_code == 0, ok_err

    (root / TARGET).write_text("VALUE = 2  # edited after verify\n", encoding="utf-8")

    code, after, err = step("state", "--repo-root", str(root))
    assert code == 0, after + err
    after_row = block(after)["CANDIDATE"]
    assert after_row != f"{candidate} recorded", (
        f"WHAT: state still reads CANDIDATE {after_row!r} after {TARGET} was edited. "
        "WHY: the record was measured over other declared bytes, so it is "
        "historical, not current. "
        "HOW: derive currentness from the declared owned bytes."
    )
    assert after_row.endswith("bytes moved"), after_row
    assert block(after)["NEXT"] == f"des craft --repo-root {root} --value 1", after
    prep_code, prep_out, prep_err = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    )
    assert prep_code != 0, (
        "WHAT: prepare-role accepted a candidate whose declared target was "
        "edited after verification. WHY: state reports it historical; both must "
        "agree. HOW: make prepare-role refuse a non-current verify record."
    )
    refusal = block(prep_out, prep_err)
    assert refusal["DELIVERY-OUTCOME"] == "Refusal", refusal
    assert refusal["WHAT"] == "RolePreparationUnavailable", refusal
