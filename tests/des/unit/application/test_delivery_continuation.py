"""Small laws of the runner's foreign-state observation and authority reader."""

from __future__ import annotations

import json
import stat
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    ScopeWindow,
    _status_paths,
)
from des.application.handover import (
    Blocked,
    HandoverValue,
    SharedDesign,
    create_handover,
    design_facts_defect,
    handover_path,
)
from des.domain.design_document import DesignDocument
from des.ports.driven_ports.task_invocation_port import (
    AgreementParty,
    ApplicableADR,
    ApplicableAgreementAnalysis,
    ApplicableImpactClosure,
    DesignFacts,
    DesignTarget,
    FactId,
    FactRecord,
    FactRef,
    ImpactItem,
    NotApplicable,
    ReuseAnalysis,
    ReuseCandidate,
)
from tests.des._helpers.host_facts import design_manifest


TARGET_REASON = FactRef(FactId("V1-F4"))


def test_initial_foreign_observation_includes_rename_and_copy_paths() -> None:
    # A rename and a copy each carry a second NUL-separated origin path.
    statuses = [
        " M notes/changed.txt\0?? notes/new.txt\0",
        "R  notes/new-name.txt\0notes/old-name.txt\0",
        "C  notes/copy.txt\0notes/source.txt\0",
    ]
    assert [_status_paths(status) for status in statuses] == [
        ("notes/changed.txt", "notes/new.txt"),
        ("notes/new-name.txt", "notes/old-name.txt"),
        ("notes/copy.txt", "notes/source.txt"),
    ]


SECTION = """## Value
Paradigm: object-oriented
| Target | Decision |
| --- | --- |
| `src/value.py` | EXTEND |
**PRESERVATION**
Oracle target locator: `tests/acceptance/test_value.py`
Oracle verification command index: `0`
Verification command: `python3 -m pytest tests/acceptance/test_value.py`
"""


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def repo(tmp_path: Path, relative: str, text: str = SECTION) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "a@b")
    git(tmp_path, "config", "user.name", "a")
    document = tmp_path / relative
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(text)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


# Directory and filename convey no authority: a document outside the former
# `docs/product/architecture` whitelist is eligible on the same evidence
# (the Prism defect a path whitelist caused).
def test_locator_authority_is_refused_even_in_tracked_markdown(tmp_path) -> None:
    relative = "notes/any.md"
    root = repo(tmp_path, relative)
    outcome = DeliveryContinuationRunner._derive(root, f"{relative}#Value")
    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure.what == "DesignFactsPreNormalized"
    assert "--replace-current" in outcome.failure.how


@pytest.mark.parametrize(
    "untracked", ["notes/untracked.md", "notes/[x].md"], ids=["plain", "pathspec-magic"]
)
def test_an_untracked_authority_document_is_refused(tmp_path, untracked: str) -> None:
    # `notes/[x].md` is a Git wildmatch pattern for the tracked `notes/x.md`:
    # an untrusted locator must be compared as an exact path, never a glob.
    root = repo(tmp_path, "notes/x.md")
    (root / untracked).write_text(SECTION)

    outcome = DeliveryContinuationRunner._derive(root, f"{untracked}#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate


@pytest.mark.parametrize(
    "locator",
    [
        "/etc/passwd#Value",
        "../outside.md#Value",
        "docs/adrs/ADR-9-value.md",
        "docs/adrs/ADR-9-value.md#Missing",
        "docs/adrs/notes.txt#Value",
    ],
    ids=["absolute", "traversal", "no-anchor", "missing-section", "not-markdown"],
)
def test_locator_shapes_that_name_no_repo_local_section_are_refused(
    tmp_path, locator: str
) -> None:
    root = repo(tmp_path, "docs/adrs/ADR-9-value.md")

    outcome = DeliveryContinuationRunner._derive(root, locator)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate


def test_a_symlink_escaping_the_repository_is_refused(tmp_path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(SECTION)
    root = repo(tmp_path / "repo", "docs/adrs/ADR-9-value.md")
    link = root / "docs/adrs/linked.md"
    link.symlink_to(outside)
    git(root, "add", "-f", "docs/adrs/linked.md")

    outcome = DeliveryContinuationRunner._derive(root, "docs/adrs/linked.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate


def test_an_ambiguous_anchor_is_refused(tmp_path) -> None:
    # A bound or restarted locator resolves through `_derive` alone, which never
    # sees the changed-document comparison that refuses duplicates earlier.
    root = repo(tmp_path, "docs/adrs/ADR-9-value.md", SECTION + SECTION)

    outcome = DeliveryContinuationRunner._derive(root, "docs/adrs/ADR-9-value.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate


SUPPORTED_SECTION = """## Value
Paradigm: object-oriented
| Target | Decision |
| --- | --- |
| `src/value.py` | EXTEND |
**PRESERVATION**
Oracle target locator: `tests/acceptance/test_value.py`
Oracle verification command index: `0`
Acceptance support locator: `{support}`
Verification command: `python3 -m pytest tests/acceptance/test_value.py`
"""


def _typed(supports: tuple[str, ...]) -> DesignFacts:
    return DesignDocument.from_json(
        json.dumps(
            design_manifest(
                {
                    "targets": [
                        {
                            "path": "src/value.py",
                            "decision": "EXTEND",
                            "reason": "Own the value.",
                        }
                    ],
                    "paradigm": "object_oriented",
                    "decisions": ["reuse the existing port"],
                    "oracle": "tests/acceptance/test_value.py",
                    "acceptance_supports": list(supports),
                    "verification": [
                        ["python3", "-m", "pytest", "tests/acceptance/test_value.py"]
                    ],
                    "oracle_verification_index": 0,
                    "architectural_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no structural boundary change.",
                    },
                    "contract_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture changes no shared contract.",
                    },
                    "prefactoring": {
                        "applicability": "not_applicable",
                        "reason": "The fixture requires no preservation move.",
                    },
                    "agreement_analysis": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no affected agreement.",
                    },
                    "reuse_analysis": {"candidates": []},
                    "impact_closure": {
                        "applicability": "not_applicable",
                        "reason": "The fixture reaches no public surface, consumer or build metadata.",
                    },
                },
                "Expose value.",
                1,
            )
        )
    ).facts


def test_an_ignored_generated_acceptance_support_is_refused(tmp_path) -> None:
    """Measured 2026-09-05: DESIGN named a 60 MB ignored `graphify-out/graph.json`.

    A support is evidence the reviewer judges the oracle against, so it must be
    the repository's own byte, not whatever the last tool run happened to leave
    on this disk.  Tracked-ness is a PRIMITIVE the software already holds.
    """
    root = repo(tmp_path, "notes/any.md")
    (root / ".gitignore").write_text("graphify-out/\n")
    (root / "graphify-out").mkdir()
    (root / "graphify-out/graph.json").write_text("{}")

    outcome = DeliveryContinuationRunner._derive(
        root, _typed(("graphify-out/graph.json",))
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "AcceptanceSupportIgnored"
    assert "graphify-out/graph.json" in outcome.failure.why


def test_an_ignored_support_declared_in_markdown_authority_is_refused(
    tmp_path,
) -> None:
    """The rule belongs to the authority, not to one of its two spellings."""
    root = repo(
        tmp_path,
        "notes/any.md",
        SUPPORTED_SECTION.format(support="build/generated.json"),
    )
    (root / ".gitignore").write_text("build/\n")
    (root / "build").mkdir()
    (root / "build/generated.json").write_text("{}")

    outcome = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsPreNormalized"


def test_a_support_the_designer_has_not_authored_yet_is_admitted(tmp_path) -> None:
    """`nw-acceptance-designer` authors the oracle AND its declared supports.

    The runner derives the authority BEFORE that turn, so an absent support is
    the ordinary RED_TO_GREEN shape, not a generated artifact.  Demanding
    tracked-ness here would refuse every such Request in the tree.
    """
    root = repo(tmp_path, "notes/any.md")

    facts = DeliveryContinuationRunner._derive(
        root, _typed(("tests/acceptance/support.py",))
    )

    assert isinstance(facts, AuthorityFacts)
    assert facts.acceptance_paths == (
        "tests/acceptance/test_value.py",
        "tests/acceptance/support.py",
    )


def test_a_resumed_handover_that_already_bound_an_ignored_support_is_refused(
    tmp_path,
) -> None:
    """The live 2026-09-05 handover had ALREADY bound `graphify-out/graph.json`.

    A durable graph outlives the rule that would have refused it, so the resume
    path -- which rereads the stored authority and never re-elicits DESIGN for a
    bound value -- has to carry the same verdict, and its HOW has to be
    executable without deleting the generated artifact.
    """
    root = repo(tmp_path, "notes/any.md")
    (root / ".gitignore").write_text("graphify-out/\n")
    (root / "graphify-out").mkdir()
    generated = root / "graphify-out/graph.json"
    generated.write_text("{}")
    stored = create_handover(
        root,
        "resume the Request",
        (HandoverValue("the tool answers", (), _typed(("graphify-out/graph.json",))),),
    )
    assert not isinstance(stored, Blocked)

    outcome = DeliveryContinuationRunner()._validate_bound_scopes(root, stored)

    assert outcome is not None
    assert outcome.failure is not None
    assert outcome.failure.what == "AcceptanceSupportIgnored"
    # The HOW, executed: removing the graph re-opens DESIGN and keeps the bytes.
    handover_path(root).unlink()
    assert not handover_path(root).exists()
    assert generated.read_text() == "{}"


def test_the_runners_own_state_directory_is_not_workspace_drift(tmp_path) -> None:
    """Measured 2026-09-05: turn records made the runner accuse itself.

    Recording every model turn under `.nwave/des/logs/turns/` put new untracked
    files in the workspace between a role's before and after observation, and
    `git status --untracked-files=all` reports them like any other byte. Six
    public acceptance tests failed with WorkspaceDriftUnattributed naming the
    runner's OWN record. A role never declares `.nwave/des/`, so a byte there is
    the runner's by construction and cannot be a role's drift; the handover in
    that same directory keeps its own compare-and-set guard.
    """
    root = repo(tmp_path, "notes/any.md")
    runner = DeliveryContinuationRunner()
    observed = runner._observed_scope(root)
    assert not isinstance(observed, DeliveryOutcome)
    status, before = observed

    record = root / ".nwave/des/logs/turns/20260905T000000Z-1/01-nw-product-owner.json"
    record.parent.mkdir(parents=True)
    record.write_text("{}")

    assert record.relative_to(root).as_posix() not in _status_paths(
        runner._observed_scope(root)[0]
    )
    drift = runner._scope_drift(root, ScopeWindow(status=status, workspace=before))
    assert not isinstance(drift, DeliveryOutcome)
    assert drift.attributed == () and drift.unattributed == ()


def test_an_absent_git_degrades_loud_instead_of_raising(tmp_path, monkeypatch) -> None:
    """Portability: a missing tool is INDETERMINATE, never a traceback.

    `git` is not a runtime dependency of DES, so a repository resolved on a box
    without it must reach the aggregate as a third state that says the check
    could not run -- not an OSError escaping the application layer.
    """
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    monkeypatch.delenv("GIT_EXEC_PATH", raising=False)

    outcome = DeliveryContinuationRunner._admit_supports(tmp_path, ("docs/adr.md",))

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "SupportAdmissibilityUnobservable"


def _typed_targets(
    targets: tuple[DesignTarget, ...], supports: tuple[str, ...]
) -> DesignFacts:
    return replace(_typed(()), targets=targets, acceptance_supports=supports)


def test_an_extend_target_required_as_acceptance_support_is_refused_before_binding(
    tmp_path,
) -> None:
    """A support's bytes are pinned by the oracle witness before craft.

    Codex retest 2026-10-01 (local-bug): DESIGN listed the EXTEND target
    `pagination.py` as a support; binding succeeded, craft was then refused
    twice with OracleRecordMoved and the host reverted its own fix to re-measure.
    Refusing at binding names the contradiction where it costs one turn.
    """
    root = repo(tmp_path, "notes/any.md")

    outcome = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (DesignTarget("src/value.py", "EXTEND", TARGET_REASON),),
            ("src/value.py", "tests/acceptance/support.py"),
        ),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsMalformed"
    assert "src/value.py" in outcome.failure.why
    assert "tests/acceptance/support.py" not in outcome.failure.why


def test_an_acceptance_owned_fixture_beside_an_extend_target_stays_admitted(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")

    facts = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (DesignTarget("src/value.py", "EXTEND", TARGET_REASON),),
            ("tests/acceptance/support.py",),
        ),
    )

    assert isinstance(facts, AuthorityFacts)
    assert DeliveryContinuationRunner._mutable_targets(facts) == ("src/value.py",)


def test_markdown_refuses_a_new_non_oracle_target_required_as_acceptance_support(
    tmp_path,
) -> None:
    root = repo(
        tmp_path,
        "notes/any.md",
        SECTION.replace(
            "| `src/value.py` | EXTEND |",
            "| `tests/support/new_helper.py` | CREATE_NEW |",
        ).replace(
            "Oracle verification command index: `0`",
            "Acceptance support locator: `tests/support/new_helper.py`\n"
            "Oracle verification command index: `0`",
        ),
    )

    outcome = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsPreNormalized"


def test_typed_facts_refuse_a_new_non_oracle_target_required_as_acceptance_support(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")

    outcome = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (DesignTarget("tests/support/new_helper.py", "CREATE_NEW", TARGET_REASON),),
            ("tests/support/new_helper.py",),
        ),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsMalformed"
    assert "tests/support/new_helper.py" in outcome.failure.why


def test_the_oracle_is_never_a_mutable_target(tmp_path) -> None:
    """ADR-SSOT-002 §12: the crafter never edits the immutable acceptance oracle."""
    root = repo(tmp_path, "notes/any.md")

    facts = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (
                DesignTarget(
                    "tests/acceptance/test_value.py", "CREATE_NEW", TARGET_REASON
                ),
                DesignTarget("src/value.py", "EXTEND", TARGET_REASON),
            ),
            (),
        ),
    )

    assert isinstance(facts, AuthorityFacts)
    assert DeliveryContinuationRunner._mutable_targets(facts) == ("src/value.py",)


def test_a_target_table_that_declares_only_the_oracle_is_refused_before_binding(
    tmp_path,
) -> None:
    """The residual contradiction, refused where it costs one turn, not two.

    With the oracle removed from the mutable set, a table naming nothing else
    leaves the crafter authorized to change no byte at all.  `_derive` runs
    after the architect turn and BEFORE the bind, so the value stays unbound
    and the next run re-elicits DESIGN -- which is the HOW this names.
    """
    root = repo(tmp_path, "notes/any.md")

    outcome = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (
                DesignTarget(
                    "tests/acceptance/test_value.py", "CREATE_NEW", TARGET_REASON
                ),
            ),
            (),
        ),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsMalformed"
    assert "targets" in outcome.failure.why
    assert "tests/acceptance/test_value.py" in outcome.failure.why
    assert "des design" in outcome.failure.how


def _verification_facts(
    *,
    targets: tuple[DesignTarget, ...] = (
        DesignTarget("src/value.py", "EXTEND", TARGET_REASON),
    ),
    supports: tuple[str, ...] = (),
    verification: tuple[tuple[str, ...], ...],
) -> DesignFacts:
    return replace(_typed_targets(targets, supports), verification=verification)


def test_an_unresolvable_typed_verification_executable_is_refused_before_bind(
    tmp_path, monkeypatch
) -> None:
    """The architect's facts stay ephemeral when argv0 cannot ever start."""
    root = repo(tmp_path, "notes/any.md")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))

    outcome = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(verification=(("missing-verification-tool",),)),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationExecutableUnresolvable"
    assert "verification[0]" in outcome.failure.why
    assert "missing-verification-tool" in outcome.failure.why
    assert "PATH" in outcome.failure.how


def test_bare_and_absolute_verification_executables_are_admitted(
    tmp_path, monkeypatch
) -> None:
    root = repo(tmp_path, "notes/any.md")
    tools = root / "tools"
    tools.mkdir()
    bare = tools / "bare-checker"
    absolute = tools / "absolute-checker"
    for tool in (bare, absolute):
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tools))

    facts = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(
            verification=(("bare-checker",), (str(absolute),)),
        ),
    )

    assert isinstance(facts, AuthorityFacts)


def test_an_unresolvable_markdown_verification_executable_is_refused_before_bind(
    tmp_path,
) -> None:
    """The Markdown authority follows the same pre-publication admission."""
    text = SECTION.replace(
        "python3 -m pytest tests/acceptance/test_value.py", "tools/missing-checker"
    )
    root = repo(tmp_path, "notes/any.md", text)

    outcome = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsPreNormalized"
    assert "--replace-current" in outcome.failure.how


def test_a_missing_relative_verification_executable_is_admitted_when_targeted(
    tmp_path, monkeypatch
) -> None:
    """A CREATE_NEW command may be authored by this delivery before it runs."""
    root = repo(tmp_path, "notes/any.md")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))

    facts = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(
            targets=(DesignTarget("tools/checker", "CREATE_NEW", TARGET_REASON),),
            verification=(("./tools/checker",),),
        ),
    )

    assert isinstance(facts, AuthorityFacts)


def test_a_missing_relative_markdown_executable_is_admitted_when_support_declares_it(
    tmp_path,
) -> None:
    """Acceptance supports are also materialized before native verification."""
    text = SUPPORTED_SECTION.format(support="tools/checker").replace(
        "python3 -m pytest tests/acceptance/test_value.py", "./tools/checker"
    )
    root = repo(tmp_path, "notes/any.md", text)

    facts = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(facts, DeliveryOutcome)
    assert facts.failure.what == "DesignFactsPreNormalized"
    assert "--replace-current" in facts.failure.how


def test_an_existing_relative_verification_executable_must_be_executable(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")
    checker = root / "tools" / "checker"
    checker.parent.mkdir()
    checker.write_text("not executable\n")

    outcome = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(verification=(("./tools/checker",),)),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationExecutableUnresolvable"

    checker.chmod(checker.stat().st_mode | stat.S_IXUSR)
    admitted = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(verification=(("./tools/checker",),)),
    )

    assert isinstance(admitted, AuthorityFacts)


def test_a_relative_executable_outside_the_repository_is_refused_before_bind(
    tmp_path,
) -> None:
    root = repo(tmp_path / "repository", "notes/any.md")
    checker = tmp_path / "outside" / "checker"
    checker.parent.mkdir()
    checker.write_text("#!/bin/sh\nexit 0\n")
    checker.chmod(checker.stat().st_mode | stat.S_IXUSR)

    outcome = DeliveryContinuationRunner._derive(
        root,
        _verification_facts(verification=(("../outside/checker",),)),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationExecutableUnresolvable"
    assert "../outside/checker" in outcome.failure.why


ORACLE_ONLY_SECTION = """## Value
Paradigm: object-oriented
| Target | Decision |
| --- | --- |
| `tests/acceptance/test_value.py` | CREATE_NEW |
**PRESERVATION**
Oracle target locator: `tests/acceptance/test_value.py`
Oracle verification command index: `0`
Verification command: `python3 -m pytest tests/acceptance/test_value.py`
"""


def test_the_oracle_only_target_table_is_refused_in_markdown_authority_too(
    tmp_path,
) -> None:
    """The rule belongs to the authority, not to one of its two spellings."""
    root = repo(tmp_path, "notes/any.md", ORACLE_ONLY_SECTION)

    outcome = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsPreNormalized"


def test_an_out_of_range_markdown_oracle_binding_names_its_repair(tmp_path) -> None:
    root = repo(
        tmp_path,
        "notes/any.md",
        SECTION.replace(
            "Oracle verification command index: `0`",
            "Oracle verification command index: `1`",
        ),
    )

    outcome = DeliveryContinuationRunner._derive(root, "notes/any.md#Value")

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "DesignFactsPreNormalized"
    assert "--replace-current" in outcome.failure.how


def test_restoring_an_oracle_only_handover_is_refused_before_publication(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")
    stored = create_handover(
        root,
        "resume the Request",
        (
            HandoverValue(
                "the tool answers",
                (),
                _typed_targets(
                    (
                        DesignTarget(
                            "tests/acceptance/test_value.py",
                            "CREATE_NEW",
                            TARGET_REASON,
                        ),
                    ),
                    (),
                ),
            ),
        ),
    )
    assert isinstance(stored, Blocked)
    assert stored.what == "HandoverMalformed"
    assert "test_value.py" in stored.why
    assert "des design" in stored.how
    assert not handover_path(root).exists()


def _reasoned(**overrides) -> DesignFacts:
    return replace(
        _typed(()),
        facts=(
            *_typed(()).facts,
            *(
                FactRecord(FactId(identifier), text)
                for identifier, text in (
                    ("ReuseReason", "No existing renderer fits the contract."),
                    ("ImpactReason", "The target is rewritten."),
                    ("AdrContext", "context"),
                    ("AdrDecision", "decision"),
                    ("AdrAlternative", "alternative"),
                    ("AdrConsequence", "consequence"),
                    ("NoAdr", "The fixture needs no decision record."),
                    ("MigratedReason", "The target is migrated."),
                    ("ProtocolReason", "Protocol v1 remains unchanged."),
                )
            ),
        ),
        reuse_analysis=ReuseAnalysis(
            (
                ReuseCandidate(
                    "Value.render",
                    "src/value.py:10",
                    "CREATE_NEW",
                    FactRef(FactId("ReuseReason")),
                ),
            )
        ),
        impact_closure=ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime",
                    "src/value.py",
                    "CHANGED",
                    FactRef(FactId("ImpactReason")),
                ),
            )
        ),
        adr=ApplicableADR(
            FactRef(FactId("AdrContext")),
            FactRef(FactId("AdrDecision")),
            (FactRef(FactId("AdrAlternative")),),
            (FactRef(FactId("AdrConsequence")),),
            "accepted",
        ),
        **overrides,
    )


def test_derived_authority_exposes_reuse_adr_and_impact_closure(tmp_path) -> None:
    root = repo(tmp_path, "notes/any.md")
    design = _reasoned()

    facts = DeliveryContinuationRunner._derive(root, design)

    assert isinstance(facts, AuthorityFacts)
    assert facts.reuse_analysis == design.reuse_analysis
    assert facts.adr == design.adr
    assert facts.impact_closure == design.impact_closure


def test_selected_revision_identity_moves_with_each_reuse_adr_and_closure(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")
    facts = DeliveryContinuationRunner._derive(root, _reasoned())
    assert isinstance(facts, AuthorityFacts)
    variants = {
        "reuse_analysis": ReuseAnalysis(()),
        "adr": NotApplicable(FactRef(FactId("NoAdr"))),
        "impact_closure": ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime",
                    "src/value.py",
                    "MIGRATED",
                    FactRef(FactId("MigratedReason")),
                ),
            )
        ),
    }

    for name, value in variants.items():
        changed = replace(facts, **{name: value})
        assert changed.selected_revision_sha256 != facts.selected_revision_sha256, name


def test_typed_and_shared_projections_carry_reuse_closure_and_adr_when_present(
    tmp_path,
) -> None:
    root = repo(tmp_path, "notes/any.md")
    with_adr = _reasoned()
    derived = DeliveryContinuationRunner._derive(root, with_adr)
    assert isinstance(derived, AuthorityFacts)

    typed = DeliveryContinuationRunner._typed_facts(derived)
    assert typed["reuse_analysis"]["candidates"][0]["decision"] == "CREATE_NEW"
    assert typed["impact_closure"]["applicability"] == "applicable"
    assert typed["impact_closure"]["items"][0]["locator"] == "src/value.py"
    assert typed["adr"]["decision"] == {"ref": "AdrDecision"}
    without_adr = DeliveryContinuationRunner._derive(root, replace(with_adr, adr=None))
    assert isinstance(without_adr, AuthorityFacts)
    assert DeliveryContinuationRunner._typed_facts(without_adr).get("adr") is None

    def shared_of(design: DesignFacts) -> dict:
        stored = SimpleNamespace(
            shared_design=SharedDesign(
                "notes/any.md#Shared design", "a" * 64, "b" * 64, design
            )
        )
        return DeliveryContinuationRunner._shared(stored)["shared_design"]

    shared = shared_of(with_adr)
    assert shared == {
        "authority_locator": "notes/any.md#Shared design",
        "section_sha256": "a" * 64,
        "semantic_sha256": "b" * 64,
    }
    assert shared_of(replace(with_adr, adr=None)) == shared


def test_facts_whose_impact_closure_omits_a_declared_consumer_are_refused() -> None:
    design = replace(
        _reasoned(),
        agreement_analysis=ApplicableAgreementAnalysis(
            (
                AgreementParty(
                    FactId("ProtocolConsumer"),
                    "answer-protocol",
                    "consumer",
                    "bin/main.ml:1",
                    "UNCHANGED_COMPATIBLE",
                    FactRef(FactId("ProtocolReason")),
                ),
            )
        ),
    )

    defect = design_facts_defect(design)

    assert defect is not None
    assert "bin/main.ml:1" in defect


@pytest.mark.parametrize(
    "consulted", [(), ("src/consulted.py",), ("src/a.py", "src/b.py")]
)
def test_bound_no_change_authority_has_no_crafter_mutation_population(
    tmp_path, consulted
):
    root = repo(tmp_path, "notes/any.md")
    declared = replace(
        _typed_targets((), ()),
        product_change="none",
        facts=(
            *_typed(()).facts,
            FactRecord(FactId("ConsultOwner"), "Consult existing owner."),
        ),
        reuse_analysis=ReuseAnalysis(
            tuple(
                ReuseCandidate(
                    path, path + ":1", "REUSE", FactRef(FactId("ConsultOwner"))
                )
                for path in consulted
            )
        ),
    )
    facts = DeliveryContinuationRunner._derive(root, declared)
    assert isinstance(facts, AuthorityFacts)
    assert DeliveryContinuationRunner._mutable_targets(facts) == ()
    assert facts.product_change == "none"
    assert DeliveryContinuationRunner._typed_facts(facts)["product_change"] == "none"
    assert not set(consulted).intersection(
        DeliveryContinuationRunner._owned_paths(facts)
    )
