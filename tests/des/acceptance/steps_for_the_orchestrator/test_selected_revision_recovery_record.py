"""Public oracle: acceptance-designer selected-revision-recovery is recordable.

`des invoke-role --role acceptance-designer --task selected-revision-recovery`
succeeds at the native role turn and then crashes recording it:
`record_selected_revision_recovery()` is called by `invoke_role.py` with the
prepared input's own path as a 6th positional argument, but the recorder in
`role_artifacts.py` never declared a matching parameter. Every real component
between the CLI edge and the recorder is exercised for real; only the paid
provider (`claude`) is a stand-in.
"""

from __future__ import annotations

import hashlib
import json

from tests.des.acceptance.distill_document_construction.test_distill_document_construction import (
    _call,
    _Subject,
    _value_manifest,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import block


def _misalign(subject: _Subject, expected: str) -> None:
    """Change value 1's own DESIGN so its already-selected revision goes stale."""
    code, out, err = _call(
        subject.root,
        "design",
        json.dumps(_value_manifest(expected=expected)),
        value=1,
        replace_current=True,
    )
    assert code == 0, out + err


def _recovery_document() -> dict[str, object]:
    """One complete, valid schema_version 2 recovery document for value 1."""
    return {
        "schema_version": 2,
        "values": [
            {
                "observation": "A user selects a widget color.",
                "acceptance_obligations": [
                    {
                        "id": "select-blue",
                        "stimulus": "Choose blue in the public widget control.",
                        "expected": "The selected color is blue.",
                    }
                ],
                "oracle": "tests/acceptance/test_selected_blue.py::test_selects_blue",
                "acceptance_supports": ["tests/support/blue_driver.py"],
                "verification": [
                    [
                        "python3",
                        "-m",
                        "pytest",
                        "tests/acceptance/test_selected_blue.py",
                    ]
                ],
                "oracle_verification_index": 0,
            }
        ],
    }


def test_stale_recovery_input_is_refused_before_any_provider_turn_or_write(
    tmp_path,
) -> None:
    """Existing recovery machinery already refuses a stale prepared input.

    A recovery input sealed against one DESIGN state must not be silently
    substituted once the selection has moved again -- this is the ONE
    protection `load_selected_revision_recovery` already owns, orthogonal to
    the recording defect this file's other scenario reproduces.
    """
    subject = _Subject(tmp_path, None).designed()
    subject.select("blue")
    _misalign(subject, "stdout is green and exit is zero.")

    code, out, err = subject.step(
        "prepare-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--value",
        "1",
        "--finding",
        "-",
        stdin="value 1 needs a complete realignment.",
    )
    assert code == 0, out + err
    stale_input = block(out, err)["INPUT"]

    _misalign(
        subject, "stdout is yellow and exit is zero."
    )  # moves again; input now stale

    seen = len(subject.rows())
    code, out, err = subject.step(
        "invoke-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--provider",
        "claude",
        "--input",
        stale_input,
        answers=[],
    )
    assert code != 0, (
        "WHAT: a stale recovery input was accepted. WHY: it was "
        "sealed against a DESIGN state the selection no longer carries. HOW: "
        "load_selected_revision_recovery must refuse before any provider turn."
    )
    assert "authority binding differs" in out + err
    assert subject.rows()[seen:] == [], "a refused stale input bought a provider turn"


def test_accepted_recovery_records_its_typed_result_and_retains_the_exact_document(
    tmp_path,
) -> None:
    """RED: the real CLI crashes recording an accepted recovery turn.

    `invoke_role.py` passes the prepared input's own path to
    `record_selected_revision_recovery(...)` as a 6th positional argument; the
    recorder only declares 5. This drives every real component -- prepare-role,
    invoke-role, the recorder, the DISTILL document constructor -- through the
    actual CLI; only the paid provider `claude` is stubbed.
    """
    subject = _Subject(tmp_path, None).designed()
    subject.select("blue")
    _misalign(subject, "stdout is green and exit is zero.")

    code, out, err = subject.step(
        "prepare-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--value",
        "1",
        "--finding",
        "-",
        stdin="value 1 needs a complete realignment.",
    )
    assert code == 0, out + err
    lines = block(out, err)
    input_path = lines["INPUT"]
    input_digest = lines["INPUT-SHA256"]
    prepared_raw = (subject.root / input_path).read_bytes()
    assert hashlib.sha256(prepared_raw).hexdigest() == input_digest

    document = _recovery_document()
    code, out, err = subject.step(
        "invoke-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--provider",
        "claude",
        "--input",
        input_path,
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "the recovered selection is admissible",
                    "distill_document": document,
                }
            }
        ],
    )
    assert code == 0, (
        "WHAT: `des invoke-role` crashed instead of recording an accepted "
        "acceptance-designer recovery. WHY: invoke_role.py:192 calls "
        "record_selected_revision_recovery(root, value, provider, model, "
        "run, expected) with the prepared input's own path as a 6th "
        "positional argument, but role_artifacts.py:836 declares only 5 "
        "parameters. HOW: role_artifacts.record_selected_revision_recovery "
        "must accept that input path (mirroring record_model's own optional "
        "input_path parameter) so the caller's binding is honored instead of "
        "raising TypeError.\n--- actual stdout ---\n"
        + out
        + "\n--- actual stderr ---\n"
        + err
    )
    lines = block(out, err)
    assert lines["OUTCOME"] == "accepted"
    assert lines["TASK"] == "selected-revision-recovery"
    assert lines["VALUE"] == "1"

    result_raw = (subject.root / lines["RESULT"]).read_bytes()
    assert hashlib.sha256(result_raw).hexdigest() == lines["RESULT-SHA256"]
    result = json.loads(result_raw)
    assert result["role"] == "acceptance-designer"
    assert result["task"] == "selected-revision-recovery"
    assert result["value"] == 1
    assert result["outcome"] == "accepted"
    assert result["input_sha256"] == input_digest, (
        "WHAT: the recorded result's input_sha256 does not bind the exact "
        "prepared input the caller invoked with. WHY: a recorder that "
        "re-derives without binding could silently accept a different input "
        "than the one the CLI validated. HOW: bind the recorded input digest "
        "to the exact bytes read at invoke-role's own validation."
    )

    document_path = lines["DISTILL-DOCUMENT"]
    document_raw = (subject.root / document_path).read_bytes()
    assert hashlib.sha256(document_raw).hexdigest() == lines["DISTILL-DOCUMENT-SHA256"]
    assert json.loads(document_raw) == document, (
        "WHAT: the retained recovery document does not match the accepted "
        "provider turn's DISTILL document verbatim. WHY: the document is "
        "canonicalized once by its domain owner and never reconstructed by "
        "the CLI. HOW: persist run.distill_document.canonical_json() exactly."
    )


def test_a_corrected_finding_seals_a_distinct_recovery_input_on_claude(
    tmp_path,
) -> None:
    """A corrected finding changes the sealed bytes, so the INPUT-SHA256 changes.

    The path is content-addressed by the exact sealed bytes (including the
    finding), so identical findings reuse the same path, but corrected
    findings seal distinct immutable inputs with different paths. Both
    preparations succeed; the second one does not conflict with the first.
    Legacy binding-only paths are also recognized for backward compatibility.
    """
    subject = _Subject(tmp_path, None).designed()
    subject.select("blue")
    _misalign(subject, "stdout is green and exit is zero.")

    # First preparation with one finding
    code, out, err = subject.step(
        "prepare-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--value",
        "1",
        "--finding",
        "-",
        stdin="initial finding",
    )
    assert code == 0, out + err
    lines1 = block(out, err)
    path1 = lines1["INPUT"]
    digest1 = lines1["INPUT-SHA256"]

    # Second preparation with a corrected finding
    code, out, err = subject.step(
        "prepare-role",
        "--repo-root",
        str(subject.root),
        "--role",
        "acceptance-designer",
        "--task",
        "selected-revision-recovery",
        "--value",
        "1",
        "--finding",
        "-",
        stdin="corrected finding",
    )
    assert code == 0, out + err
    lines2 = block(out, err)
    path2 = lines2["INPUT"]
    digest2 = lines2["INPUT-SHA256"]

    # Corrected finding seals distinct bytes with distinct digest
    assert digest1 != digest2, (
        "WHAT: identical digest for two preparations with different findings. "
        "WHY: the finding is part of the sealed payload, so different findings "
        "seal distinct bytes. HOW: the INPUT-SHA256 must change when the "
        "finding changes."
    )
    # Paths differ because they are content-addressed by the sealed bytes
    assert path1 != path2, (
        "WHAT: identical path for two preparations with different findings. "
        "WHY: paths are content-addressed by the exact sealed bytes (which "
        "include the finding). HOW: distinct sealed bytes must use distinct "
        "paths."
    )

    # Both files exist at their distinct paths
    raw1 = (subject.root / path1).read_bytes()
    raw2 = (subject.root / path2).read_bytes()
    assert hashlib.sha256(raw1).hexdigest() == digest1
    assert hashlib.sha256(raw2).hexdigest() == digest2
    assert raw1 != raw2
