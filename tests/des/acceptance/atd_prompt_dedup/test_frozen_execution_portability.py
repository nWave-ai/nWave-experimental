"""Normalized live prompts run portably without rewriting frozen evidence.

Driving port: the real DES subprocess. The existing normalized three-value
fixture and its public constructor journey supply the current handoff.
Only live verification argv[0] is adapted; arguments and semantic declarations
remain unchanged. Both native renders for every role retain full stdout,
the attestation bound, literal caller bytes and immutable input observations.
The frozen run5 input remains refusal-only evidence, never an execution copy.
"""

from __future__ import annotations

import copy
import json
import shutil
from functools import reduce
from operator import getitem
from pathlib import Path

import pytest
from tests.des.acceptance.atd_prompt_dedup import (
    test_role_receives_lossless_facts as attestation,
)
from tests.des.acceptance.normalized_architect_handoff import (
    test_handoff_states_each_fact_once as normalized,
)


def _assert_portable_live_attestation(tmp_path: Path, monkeypatch) -> None:
    frozen_bytes = (attestation.RUN5 / attestation.STATE).read_bytes()
    frozen_root = attestation.RUN5_ROOT.read_bytes()
    names = ("shared.json", "value-1.json", "value-2.json", "value-3.json")
    fixture_bytes = {name: (normalized.FIXTURE / name).read_bytes() for name in names}
    original_documents = [json.loads(fixture_bytes[name]) for name in names]
    live_documents = copy.deepcopy(original_documents)
    executable_slots = [
        (document, command)
        for document, declaration in enumerate(live_documents)
        for command in range(len(declaration["verification"]))
    ]
    for document, command in executable_slots:
        live_documents[document]["verification"][command][0] = "python3"
    restored_documents = copy.deepcopy(live_documents)
    for document, command in executable_slots:
        restored_documents[document]["verification"][command][0] = original_documents[
            document
        ]["verification"][command][0]
    assert restored_documents == original_documents, attestation._message(
        "live declarations changed beyond verification argv[0]",
        "arguments, facts, references, locators and typed metadata retain their meaning",
        "adapt only the declared native executable slots",
    )
    journey = normalized.HandoffJourney(tmp_path / "live-attestation", fork=True)
    journey.current(live_documents[0], live_documents[1:])
    root = journey.root
    context = root / "root-context.md"
    context.write_bytes(frozen_root)
    live_before = (root / attestation.STATE).read_bytes()
    expected = json.loads(live_before)
    assert len(expected["values"]) == 3 and "shared_design" in expected, (
        attestation._message(
            f"bound fixture scopes differ: expected shared plus {names[1:]!r}, actual values={expected['values']!r}, shared={'shared_design' in expected}",
            "the portability journey must observe the complete declared three-value fixture, not an empty or partial setup",
            "bind the declared shared manifest and all three value manifests through the public producer",
        )
    )
    declarations = [
        expected["shared_design"]["design"],
        *(value["authority"] for value in expected["values"]),
    ]
    assert [declaration["verification"] for declaration in declarations] == [
        document["verification"] for document in live_documents
    ], attestation._message(
        f"bound verification differs: expected={[document['verification'] for document in live_documents]!r}, actual={[declaration['verification'] for declaration in declarations]!r}",
        "L-resolve-retains preserves every original argv argument while adapting only its executable",
        "bind the live declarations' complete ordered verification commands unchanged",
    )
    live_paths = [
        ("shared_design", "design", "verification", command, 0)
        for command in range(len(live_documents[0]["verification"]))
    ]
    live_paths.extend(
        ("values", value, "authority", "verification", command, 0)
        for value, document in enumerate(live_documents[1:])
        for command in range(len(document["verification"]))
    )
    assert live_paths, attestation._message(
        f"declared executable population is empty: paths={live_paths!r}, slots={executable_slots!r}",
        "portability cannot pass without observing the fixture's actual verification executables",
        "retain the verification commands and enumerate every shared and value argv[0] slot",
    )
    renders = (
        (attestation.Role.DESIGNER, 1),
        (attestation.Role.DESIGNER, 2),
        (attestation.Role.DESIGNER, 3),
        (attestation.Role.ARCHITECT, None),
    )
    actual_renders = []
    first_arguments = None
    first_designer_size = None
    for role, position in renders:
        subject = attestation.PromptInput(
            root, role, position, root_context=Path("root-context.md")
        )
        arguments = subject.argv()
        if first_arguments is None:
            first_arguments = arguments
        outputs = [attestation._native(arguments, process=True) for _ in range(2)]
        attestation._assert_repeat(*outputs)
        for output in outputs:
            text = output.successful_text()
            packet, other_text = attestation._packet_and_other_text(
                text, frozen_root.decode("utf-8")
            )
            attestation._assert_sole_carrier(other_text)
            expected_observations = [
                value["observation"]
                for index, value in enumerate(expected["values"], 1)
                if position is None or index == position
            ]
            assert [
                value["observation"] for value in packet["values"]
            ] == expected_observations, attestation._message(
                f"{role.value} value={position} observations differ: expected={expected_observations!r}, actual={[value['observation'] for value in packet['values']]!r}",
                "normalization and executable portability must preserve the selected public outcomes and their order",
                "retain each original value observation in the receiving-role packet",
            )
            if position is not None:
                assert all(
                    argv[0] == "python3"
                    for argv in packet["selected_authority"]["verification"]
                ), attestation._message(
                    f"value={position} selected verification uses nonportable executables: {packet['selected_authority']['verification']!r}",
                    "L-resolve-retains must expose the live PATH-based argv, not workstation executables",
                    "carry python3 through every selected verification argv[0] without altering the remaining arguments",
                )
            live = json.loads((root / attestation.STATE).read_bytes())
            executables = {path: reduce(getitem, path, live) for path in live_paths}
            assert executables == dict.fromkeys(live_paths, "python3"), (
                attestation._message(
                    f"live executables differ from PATH python3: {executables!r}",
                    "every declared executable must be portable, not a workstation path",
                    "retain python3 in every live verification argv[0]",
                )
            )
            assert live == expected, attestation._message(
                f"live handover changed after {role.value} value={position}: expected={expected!r}, actual={live!r}",
                "L-roundtrip and the retained read-only boundary forbid prompt rendering from changing any bound declaration",
                "render from the existing live state without rebinding or mutating its fields",
            )
            assert (root / attestation.STATE).read_bytes() == live_before, (
                attestation._message(
                    f"live handover bytes changed after {role.value} value={position}",
                    "semantic equality alone cannot prove the exact read-only input boundary",
                    "preserve the original state bytes during every prompt render",
                )
            )
            assert context.read_bytes() == frozen_root, attestation._message(
                f"caller context differs: expected={frozen_root!r}, actual={context.read_bytes()!r}",
                "portability must preserve independent literal caller input byte-for-byte",
                "read the context without rewriting, normalizing or truncating it",
            )
            assert root.resolve().is_relative_to(tmp_path.resolve()), (
                attestation._message(
                    f"live repository {root.resolve()} is outside disposable root {tmp_path.resolve()}",
                    "this journey may construct live inputs only in its isolated temporary environment",
                    "keep public construction and prompt inputs under the test's temporary root",
                )
            )
            actual_renders.append((role.value, position))
        if role is attestation.Role.DESIGNER and position == 1:
            first_designer_size = len(outputs[0].stdout)
    assert actual_renders == [
        (role.value, position) for role, position in renders for _ in range(2)
    ], attestation._message(
        f"paired render population differs: expected={[(role.value, position) for role, position in renders for _ in range(2)]!r}, actual={actual_renders!r}",
        "repeatability must cover every declared ATD value and the architect, not a sampled subset",
        "retain both complete native renders for each declared role/value pair",
    )
    assert first_designer_size is not None and first_designer_size < 490000, (
        attestation._message(
            f"the complete first designer prompt has {first_designer_size} bytes",
            "portability must retain the attestation bound without truncation",
            "render the normalized current facts once, without manual removal",
        )
    )
    git_only_path = tmp_path / "git-only"
    git_only_path.mkdir()
    git_executable = shutil.which("git")
    assert git_executable is not None, attestation._message(
        f"the legal git-only refusal environment lacks Git: resolved executable={git_executable!r}",
        "an unrelated prerequisite failure cannot establish the missing-PATH-python3 refusal",
        "provide Git before isolating only python3 availability in this native control",
    )
    (git_only_path / "git").symlink_to(git_executable)
    with monkeypatch.context() as unavailable_path:
        unavailable_path.setenv("PATH", str(git_only_path))
        refused = attestation._native(first_arguments, process=True)
    assert (
        refused.exit != 0
        and b"VerificationExecutableUnresolvable" in refused.stderr
        and b"python3" in refused.stderr
    ), attestation._message(
        f"missing PATH python3 produced exit={refused.exit}, stderr={refused.stderr!r}",
        "portability permits neither a fallback nor silent error acceptance",
        "retain the real executable refusal naming python3",
    )
    assert (root / attestation.STATE).read_bytes() == live_before, attestation._message(
        "the missing-PATH-python3 refusal changed live handover bytes",
        "failed prompt admission is read-only and cannot repair or rewrite the bound authority",
        "refuse the unavailable executable without mutating the live state",
    )
    assert context.read_bytes() == frozen_root, attestation._message(
        f"caller context changed during refusal: expected={frozen_root!r}, actual={context.read_bytes()!r}",
        "the portability failure must preserve independent caller bytes",
        "leave the supplied context untouched on both successful and refused renders",
    )
    assert (attestation.RUN5 / attestation.STATE).read_bytes() == frozen_bytes, (
        attestation._message(
            "the versioned frozen run5 handover differs from its captured original bytes",
            "live portability does not authorize rewriting immutable historical refusal evidence",
            "adapt only disposable live argv[0] slots and leave the frozen handover unchanged",
        )
    )
    assert attestation.RUN5_ROOT.read_bytes() == frozen_root, attestation._message(
        f"frozen caller input changed: expected={frozen_root!r}, actual={attestation.RUN5_ROOT.read_bytes()!r}",
        "the historical caller input is immutable evidence, independent of the live copy",
        "leave the versioned ROOT input byte-identical",
    )
    assert {
        name: (normalized.FIXTURE / name).read_bytes() for name in names
    } == fixture_bytes, attestation._message(
        f"normalized fixture inputs changed: expected names={names!r}, changed={[name for name in names if (normalized.FIXTURE / name).read_bytes() != fixture_bytes[name]]!r}",
        "the current fixture semantics and actual argv remain authoritative read-only inputs",
        "perform executable adaptation only on the disposable deep-copied declarations",
    )


@pytest.mark.acceptance
@pytest.mark.integration
def test_live_attestation_uses_path_python_and_preserves_frozen_evidence(
    tmp_path, monkeypatch
):
    """L-substitution-scope; inherited L-identity, L-bound and L-repeat."""
    _assert_portable_live_attestation(tmp_path, monkeypatch)
