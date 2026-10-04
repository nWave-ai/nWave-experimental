"""Native construction, selection, evidence and immutable candidate behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    RecordIdentity,
    SelectedValue,
    TurnRecordTarget,
)
from des.application.delivery_state import read_state
from des.application.delivery_steps import DeliverySteps
from des.application.handover import HandoverValue, SharedDesign, StoredHandover
from des.domain.delivery_disposition import Disposition
from des.domain.document_scope import Project
from des.domain.turn_record_ref import CRAFT_TURN, ORACLE_TURN
from des.ports.driven_ports.task_invocation_port import (
    ApplicablePrefactoring,
    DesignFacts,
    DesignTarget,
    NotApplicable,
    ReuseAnalysis,
)
from tests.des._helpers.host_facts import design_manifest, product_manifest


OBSERVATION = "the native public command reports the agreed answer of forty-two"
ORACLE_ACCEPTED = json.dumps(
    {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "The native assertion falsifies the missing public answer.",
        }
    }
)
ACCEPTED = json.dumps(
    {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "Host classified the observed native assertion.",
            "blocked_by": None,
        }
    }
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "subject"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "native@example.test")
    _git(root, "config", "user.name", "Native Fixture")
    (root / ".gitignore").write_text("_build/\n.nwave/\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "Native baseline")
    return root


def _success(result):
    assert result.disposition is Disposition.Success, result
    return result


def _native_project(root: Path) -> None:
    (root / "lib").mkdir()
    (root / "dune-project").write_text("(lang dune 2.9)\n(name native_fixture)\n")
    (root / "lib/dune").write_text("(library (name answer) (wrapped false))\n")
    (root / "lib/answer.ml").write_text('let value = 0\nlet protocol = "v1"\n')
    (root / "lib/answer.mli").write_text("val value : int\nval protocol : string\n")
    (root / "dune").write_text(
        "(executable (name oracle) (modules oracle) (libraries answer))\n"
        "(executable (name contract) (modules contract) (libraries answer))\n"
    )
    (root / "oracle.ml").write_text("let () = assert (Answer.value = 42)\n")
    (root / "contract.ml").write_text('let () = assert (Answer.protocol = "v1")\n')
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "Existing native implementation")


def test_dune_constructor_distill_oracle_craft_verify_and_owned_drift(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("dune") is None:
        pytest.skip("Dune toolchain is unavailable; no Python replacement is installed")
    root = repository
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    _native_project(root)
    steps = DeliverySteps()
    _success(
        steps.discuss_document(
            root,
            json.dumps(
                product_manifest(
                    "Deliver the native public answer using the existing Dune project.",
                    [OBSERVATION],
                )
            ),
            project=False,
            feature="native",
        )
    )
    facts = {
        "targets": [{"path": "lib/answer.ml", "decision": "EXTEND"}],
        "paradigm": "functional",
        "decisions": ["Retain the native project seam."],
        "oracle": "oracle.ml",
        "acceptance_supports": ["dune-project", "dune", "lib/dune"],
        "verification": [
            ["dune", "exec", "./oracle.exe"],
            ["dune", "build", "@check"],
            ["dune", "exec", "./contract.exe"],
        ],
        "oracle_verification_index": 0,
    }
    facts["architectural_tests"] = {
        "applicability": "applicable",
        "obligations": [
            {
                "obligation": "Implementation conforms to the published native interface.",
                "oracle": "lib/answer.mli",
                "verification_index": 1,
            }
        ],
    }
    facts["agreement_analysis"] = {
        "applicability": "applicable",
        "parties": [
            {
                "contract": "answer-protocol",
                "role": role,
                "locator": locator,
                "decision": "UNCHANGED_COMPATIBLE",
                "reason": "Protocol v1 remains unchanged.",
            }
            for role, locator in (
                ("producer", "lib/answer.ml:1"),
                ("consumer", "contract.ml:1"),
            )
        ],
    }
    facts["contract_tests"] = {
        "applicability": "applicable",
        "obligations": [
            {
                "obligation": "The native consumer observes the agreed protocol.",
                "contract": "answer-protocol",
                "producer": "lib/answer.ml:1",
                "consumer": "contract.ml:1",
                "observation": "The consumer accepts protocol v1.",
                "oracle": "contract.ml",
                "verification_index": 2,
            }
        ],
    }
    facts["prefactoring"] = {
        "applicability": "not_applicable",
        "reason": "The existing native seam supports the change without a preservation move.",
    }
    manifest = design_manifest(facts, OBSERVATION, 1)
    _success(steps.design_document(root, 1, json.dumps(manifest)))
    _success(
        steps.distill_document(
            root,
            json.dumps(
                {
                    "schema_version": 2,
                    "values": [
                        {
                            "observation": OBSERVATION,
                            "acceptance_obligations": [
                                {
                                    "id": "public-answer",
                                    "stimulus": "Run the native public command.",
                                    "expected": "The public answer is forty-two.",
                                }
                            ],
                            "oracle": "oracle.ml",
                            "acceptance_supports": ["dune-project", "dune", "lib/dune"],
                            "verification": [
                                ["dune", "exec", "./oracle.exe", "--", "--public"]
                            ],
                            "oracle_verification_index": 0,
                        }
                    ],
                }
            ),
        )
    )
    state = read_state(root)
    assert state.values[0].selection.verification == (
        ("dune", "exec", "./oracle.exe", "--", "--public"),
        ("dune", "build", "@check"),
        ("dune", "exec", "./contract.exe"),
    )
    oracle = _success(steps.oracle(root, 1, ORACLE_ACCEPTED))
    assert any("verdict=indeterminate" in row for row in oracle.facts), oracle
    (root / "lib/answer.ml").write_text('let value = 42\nlet protocol = "v1"\n')
    _success(steps.craft(root, 1, ACCEPTED))
    verified = _success(steps.verify(root))
    candidate = next(
        row.removeprefix("CANDIDATE: ")
        for row in verified.facts
        if row.startswith("CANDIDATE: ")
    )
    runner = DeliveryContinuationRunner()
    assert runner.load_native_evidence_identity(root, candidate)
    evidence_path = root / runner.native_evidence_locator
    evidence = json.loads(evidence_path.read_bytes())
    assert [row["argv"] for row in evidence] == [
        ["dune", "exec", "./oracle.exe", "--", "--public"],
        ["dune", "build", "@check"],
        ["dune", "exec", "./contract.exe"],
    ]
    assert all(
        row["exit"] == 0 and Path(row["executable"]).name == "dune" for row in evidence
    )
    assert all(
        "PYTEST_ADDOPTS" not in row["declared_environment"]
        and "PYTHONPATH" not in row["declared_environment"]
        for row in evidence
    )
    assert not list(root.rglob("*.py"))
    assert not list(root.glob("nwave-*-runtime*"))
    _success(steps.verify(root))
    assert evidence_path.exists()
    foreign = root / "human-wip.txt"
    foreign.write_bytes(b"unrelated human bytes\n")
    (root / "lib/answer.ml").write_text('let value = 42\nlet protocol = "v2"\n')
    refused = steps.integrate(root, candidate)
    assert refused.failure.what == "CandidateUnverified"
    assert foreign.read_bytes() == b"unrelated human bytes\n"
    assert evidence_path.exists()
    _success(steps.craft(root, 1, ACCEPTED))
    failed = steps.verify(root)
    assert failed.failure.what == "VerificationFailed", failed
    (root / "lib/answer.ml").write_text('let value = 42\nlet protocol = "v1"\n')
    _success(steps.integrate(root, candidate))
    assert foreign.read_bytes() == b"unrelated human bytes\n"
    assert evidence_path.exists()


def _facts(name: str) -> DesignFacts:
    return DesignFacts(
        targets=(DesignTarget(f"{name}.ml", "EXTEND"),),
        paradigm="functional",
        decisions=(f"Own the {name} public contract.",),
        oracle=f"{name}_oracle.ml",
        acceptance_supports=(),
        verification=((sys.executable, "-c", "raise SystemExit(0)"),),
        oracle_verification_index=0,
        architectural_tests=NotApplicable("No changed structural boundary."),
        contract_tests=NotApplicable("No changed agreement."),
        prefactoring=NotApplicable("No selected structural move."),
        agreement_analysis=NotApplicable("No affected consumer."),
        reuse_analysis=ReuseAnalysis(()),
        impact_closure=NotApplicable(
            "The fixture reaches no public surface, consumer or build metadata."
        ),
    )


def _record(root: Path, runner, stored, value, design) -> None:
    identity = RecordIdentity.of(root, stored, value, design)
    assert identity is not None
    for role, paths in (
        (ORACLE_TURN, design.acceptance_paths),
        (CRAFT_TURN, runner._craft_record_paths(design)),
    ):
        runner._record_turn(
            root,
            TurnRecordTarget(
                base=_git(root, "rev-parse", "HEAD"),
                request=stored.request,
                values=((value.observation, identity),),
            ),
            role=role,
            tree=runner._paths_tree(root, paths),
        )


def test_consumed_prerequisite_contract_invalidates_only_dependent_evidence(
    repository: Path,
) -> None:
    root = repository
    runner = DeliveryContinuationRunner()
    names = ("producer", "consumer", "independent")
    authority = root / "design.md"
    authority.write_text(
        "# Design\n\n"
        + "\n".join(f"## {name}\n\n{name} contract: v1.\n" for name in names)
    )
    values = tuple(
        HandoverValue(
            name,
            ("producer",) if name == "consumer" else (),
            replace(_facts(name), authority_locator=f"design.md#{name}"),
        )
        for name in names
    )
    stored = StoredHandover("Three separately owned values", values, b"{}", Project())
    designs = []
    for value in values:
        (root / value.authority.targets[0].path).write_text("let answer = 42\n")
        (root / value.authority.oracle).write_text("let () = ()\n")
        design = runner.derive_authority(root, value.authority)
        assert not isinstance(design, DeliveryOutcome)
        designs.append(design)
        _record(root, runner, stored, value, design)
    original_refs = _git(
        root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/nwave/turns"
    )
    changed_producer = replace(
        values[0],
        authority=replace(
            values[0].authority, decisions=("The public protocol changed.",)
        ),
    )
    changed = replace(stored, values=(changed_producer, *values[1:]))
    assert not runner.oracle_turn_complete(root, changed, values[1], designs[1])
    assert not runner.craft_turn_complete(root, changed, values[1], designs[1])
    assert runner.oracle_turn_complete(root, changed, values[2], designs[2])
    assert runner.craft_turn_complete(root, changed, values[2], designs[2])
    assert (
        _git(
            root,
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/nwave/turns",
        )
        == original_refs
    )
    assert runner.oracle_turn_complete(root, stored, values[1], designs[1])
    authority.write_text(
        authority.read_text().replace(
            "producer contract: v1.", "producer contract: v2."
        )
    )
    assert not runner.oracle_turn_complete(root, stored, values[1], designs[1])
    assert not runner.craft_turn_complete(root, stored, values[1], designs[1])
    assert runner.oracle_turn_complete(root, stored, values[2], designs[2])
    assert runner.craft_turn_complete(root, stored, values[2], designs[2])
    (root / "independent.ml").write_text("let answer = 7\n")
    assert not runner.craft_turn_complete(root, stored, values[2], designs[2])
    assert runner.oracle_turn_complete(root, stored, values[2], designs[2])


def _preservation(root: Path) -> SelectedValue:
    source = root / "product.txt"
    source.write_text("before\n")
    executable = root / "preserve.py"
    executable.write_text(
        "from pathlib import Path\n"
        "raise SystemExit(0 if Path('product.txt').read_text().strip() in {'before', 'after'} else 1)\n"
    )
    (root / "support.txt").write_text("same support\n")
    facts = replace(
        _facts("value"),
        targets=(DesignTarget("product.txt", "EXTEND"),),
        prefactoring=ApplicablePrefactoring(
            existing_oracle="preserve.py",
            move="Move the representation without changing its public result.",
            preserved_observation="The selected existing result remains accepted.",
            verification=((sys.executable, "preserve.py"),),
            acceptance_supports=("support.txt",),
        ),
    )
    value = HandoverValue(OBSERVATION, (), facts)
    stored = StoredHandover(
        "Preserve the existing public result before changing behavior",
        (value,),
        b"{}",
        Project(),
    )
    design = DeliveryContinuationRunner().derive_authority(root, facts)
    assert not isinstance(design, DeliveryOutcome)
    return SelectedValue(stored, value, design)


def test_prefactoring_retains_distinct_green_middle_snapshot_and_rejects_substitution(
    repository: Path,
) -> None:
    root = repository
    selected = _preservation(root)
    runner = DeliveryContinuationRunner()
    before = runner.measure_prefactoring(root, selected, "before-move")
    assert isinstance(before, tuple), before
    unchanged = runner.measure_prefactoring(
        root, selected, "after-move-before-behavior"
    )
    assert unchanged.failure.what == "PrefactoringProductionUnchanged"
    (root / "product.txt").write_text("after\n")
    (root / "support.txt").write_text("substituted support\n")
    changed = runner.measure_prefactoring(root, selected, "after-move-before-behavior")
    assert changed.failure.what == "PrefactoringWitnessChanged"
    (root / "support.txt").write_text("same support\n")
    after = runner.measure_prefactoring(root, selected, "after-move-before-behavior")
    assert isinstance(after, tuple), after
    prior, middle = (
        json.loads((root / receipt[0]).read_bytes()) for receipt in (before, after)
    )
    assert prior["witness"] == middle["witness"]
    assert prior["production"] != middle["production"]
    assert middle["before_locator"] == before[0]
    assert _git(root, "show", f"{prior['snapshot']}:product.txt") == "before"
    assert _git(root, "show", f"{middle['snapshot']}:product.txt") == "after"
    assert runner._prefactoring_ready(root, selected, before_behavior=True) is None
    (root / "support.txt").write_text("substituted after the GREEN middle\n")
    replaced = runner._prefactoring_ready(root, selected, before_behavior=True)
    assert replaced.failure.what == "PrefactoringPreservationUnrecorded"
    (root / "support.txt").write_text("same support\n")
    (root / "product.txt").write_text("feature\n")
    moved = runner._prefactoring_ready(root, selected, before_behavior=True)
    assert moved.failure.what == "PrefactoringPreservationUnrecorded"
    (root / "product.txt").write_text("broken\n")
    failed = runner.measure_prefactoring(root, selected, "after-move-before-behavior")
    assert failed.failure.what == "PrefactoringNotGreen"
    records = runner._prefactoring_records(root, selected)
    assert records[-1][1]["green"] is False
    assert records[-1][1]["evidence"][0]["exit"] == 1
    assert (root / before[0]).exists() and (root / after[0]).exists()
    rejected = runner._prefactoring_ready(root, selected)
    assert rejected.failure.what == "PrefactoringPreservationUnrecorded"


def test_committed_preservation_pair_survives_committed_feature_without_replaying_phases(
    repository: Path,
) -> None:
    root = repository
    runner = DeliveryContinuationRunner()
    selected = _preservation(root)
    oracle = "feature_oracle.py"
    (root / oracle).write_text(
        "from pathlib import Path\n"
        "def test_feature():\n"
        "    assert Path('product.txt').read_text() == 'feature\\n'\n"
    )
    facts = replace(
        selected.ready.authority,
        oracle=oracle,
        verification=((sys.executable, "-m", "pytest", oracle, "-q"),),
    )
    value = replace(selected.ready, authority=facts)
    stored = replace(selected.stored, values=(value,))
    design = runner.derive_authority(root, facts)
    assert not isinstance(design, DeliveryOutcome), design
    selected = SelectedValue(stored, value, design)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "Existing preservation witness")
    before = runner.measure_prefactoring(root, selected, "before-move")
    assert isinstance(before, tuple), before
    (root / "product.txt").write_text("after\n")
    _git(root, "add", "product.txt")
    _git(root, "commit", "-qm", "Preserving-only representation move")
    after = runner.measure_prefactoring(root, selected, "after-move-before-behavior")
    assert isinstance(after, tuple), after
    before_bytes, after_bytes = (
        (root / receipt[0]).read_bytes() for receipt in (before, after)
    )
    prior, middle = json.loads(before_bytes), json.loads(after_bytes)
    assert prior["base"] != middle["base"]
    assert prior["witness"] == middle["witness"]
    assert middle["before_locator"] == before[0]
    red = runner.measure_oracle(root, selected)
    assert red.refusal is None, red
    assert red.measured[0]["verdict"] == "red", red
    assert red.measured[0]["counts"] == (1, 0, 1), red
    (root / "product.txt").write_text("feature\n")
    _git(root, "add", "product.txt")
    _git(root, "commit", "-qm", "Implement the feature after preserved GREEN")
    assert runner.record_craft(root, selected) is None
    assert runner.craft_turn_complete(root, stored, value, design)
    late = runner.measure_prefactoring(root, selected, "before-move")
    assert late.failure.what == "PrefactoringTooLate"
    assert (root / before[0]).read_bytes() == before_bytes
    assert (root / after[0]).read_bytes() == after_bytes
    # Identical witness bytes in an unrelated real Git history cannot reuse it.
    unrelated = _git(root, "commit-tree", "HEAD^{tree}", "-m", "Unrelated root")
    current = runner._prefactoring_identity(root, selected)
    assert current is not None
    assert not runner._same_preservation(root, {**current, "base": unrelated}, middle)


def test_preservation_identity_binds_the_whole_child_environment_not_volatile_or_secret_names(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository
    selected = _preservation(root)
    monkeypatch.setenv("DOTNET_ROOT", "/sdk-a")
    monkeypatch.setenv("NODE_OPTIONS", "--require=a.js")
    # A nonsecret selector may be any length or shape; length alone is not a secret.
    prefix = "x86_64-unknown-linux-gnu-gcc-"
    selector_a, selector_b = prefix + "a" * 12, prefix + "b" * 12
    assert len(selector_a) == len(selector_b) >= 40
    monkeypatch.setenv("CC", selector_a)
    runner = DeliveryContinuationRunner()
    before = runner.measure_prefactoring(root, selected, "before-move")
    assert isinstance(before, tuple), before
    prior = json.loads((root / before[0]).read_bytes())
    assert prior["observation_basis"] == "exit-status-only"
    assert set(prior["context"]["environment"]) == {"digest"}
    (root / "product.txt").write_text("after\n")

    # A toolchain selector no closed list names is part of what the child ran.
    for name, other in (
        ("DOTNET_ROOT", "/sdk-b"),
        ("NODE_OPTIONS", "--require=b.js"),
        ("CC", selector_b),
    ):
        monkeypatch.setenv(name, other)
        changed = runner.measure_prefactoring(
            root, selected, "after-move-before-behavior"
        )
        assert changed.failure.what == "PrefactoringWitnessChanged", name
    monkeypatch.setenv("DOTNET_ROOT", "/sdk-a")
    monkeypatch.setenv("NODE_OPTIONS", "--require=a.js")
    monkeypatch.setenv("CC", selector_a)

    # Per-invocation locations and credentials are not identity; the receipt
    # displays only the public subset and never a credential.
    monkeypatch.setenv("NWAVE_EVIDENCE_DIR", str(root / "evidence-two"))
    monkeypatch.setenv("TMPDIR", str(root / "tmp-two"))
    monkeypatch.setenv("DEPLOY_TOKEN", "rotated-credential-value")
    monkeypatch.setenv("REGISTRY_URL", "https://user:hunter2@registry.example/pkg")
    monkeypatch.setenv("VENDOR_CONFIG", "ghp_" + "r" * 30)
    after = runner.measure_prefactoring(root, selected, "after-move-before-behavior")
    assert isinstance(after, tuple), after
    middle_bytes = (root / after[0]).read_bytes()
    middle = json.loads(middle_bytes)
    assert middle["context"] == prior["context"]
    assert b"rotated-credential-value" not in middle_bytes
    assert b"hunter2" not in middle_bytes
    assert "DOTNET_ROOT" not in middle["environment_public"]


def test_shared_applicable_prefactoring_must_be_carried_by_a_measured_value(
    repository: Path,
) -> None:
    root = repository
    selected = _preservation(root)
    runner = DeliveryContinuationRunner()
    move = selected.ready.authority
    shared = SharedDesign("design.md#shared", "0" * 64, "1" * 64, move)
    stored = replace(selected.stored, shared_design=shared)

    # Carried: the value declares the shared witness, so its own measured
    # before/after pair is demanded as for any applicable move.
    carried = SelectedValue(stored, selected.ready, selected.design)
    assert (
        runner._prefactoring_ready(root, carried).failure.what
        == "PrefactoringPreservationUnrecorded"
    )

    # Unassigned: the value declares no move and no sibling carries the shared
    # one, so ORACLE and CRAFT must not proceed with no witness at all.
    plain = replace(
        selected.ready,
        authority=replace(move, prefactoring=NotApplicable("No move for this value.")),
    )
    design = replace(selected.design, prefactoring=NotApplicable("No move."))
    alone = SelectedValue(replace(stored, values=(plain,)), plain, design)
    assert (
        runner._prefactoring_ready(root, alone).failure.what
        == "SharedPrefactoringUnassigned"
    )
    assert (
        runner.measure_oracle(root, alone).refusal.failure.what
        == "SharedPrefactoringUnassigned"
    )
    different = replace(
        move,
        prefactoring=replace(move.prefactoring, verification=((sys.executable, "-V"),)),
    )
    elsewhere = HandoverValue("another observation", (), different)
    mismatched = SelectedValue(
        replace(stored, values=(plain, elsewhere)), plain, design
    )
    assert (
        runner._prefactoring_ready(root, mismatched).failure.what
        == "SharedPrefactoringUnassigned"
    )

    # Assigned elsewhere: a sibling carries the same witness and measures it,
    # so this value is not forced through a pair it cannot produce.
    sibling = HandoverValue("another observation", (), move)
    assigned = SelectedValue(replace(stored, values=(plain, sibling)), plain, design)
    assert runner._prefactoring_ready(root, assigned) is None


def test_native_spawn_and_setup_failures_preserve_ownership_and_name_native_repair(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository
    owned = root / "owned.ml"
    owned.write_bytes(b"let existing = 1\n")
    runner = DeliveryContinuationRunner()
    absent = runner._native(root, (("absent-native-build-tool", "runtest"),), root)
    assert absent.disposition is Disposition.Indeterminate
    assert absent.failure.what == "VerificationExecutableAbsent"
    assert "absent-native-build-tool" in absent.failure.how
    assert "pytest" not in absent.failure.how
    assert owned.read_bytes() == b"let existing = 1\n"

    def unavailable_temporary_workspace(*args, **kwargs):
        raise PermissionError("isolated runtime workspace denied")

    monkeypatch.setattr(
        "des.application.delivery_continuation.tempfile.TemporaryDirectory",
        unavailable_temporary_workspace,
    )
    denied = runner._native(
        root, ((sys.executable, "-c", "raise SystemExit(0)"),), root
    )
    assert denied.disposition is Disposition.Indeterminate
    assert denied.failure.what == "NativeRuntimeSetupUnavailable"
    assert owned.read_bytes() == b"let existing = 1\n"
