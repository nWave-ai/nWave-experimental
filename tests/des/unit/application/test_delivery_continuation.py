"""Small laws of the runner's foreign-state observation and authority reader."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    _status_paths,
)
from des.application.handover import (
    Blocked,
    HandoverValue,
    create_handover,
    handover_path,
)
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


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
def test_authority_is_derived_from_any_tracked_markdown_section(tmp_path) -> None:
    relative = "notes/any.md"
    root = repo(tmp_path, relative)

    facts = DeliveryContinuationRunner._derive(root, f"{relative}#Value")

    assert isinstance(facts, AuthorityFacts)
    assert facts.acceptance_oracle_locator == "tests/acceptance/test_value.py"


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
Acceptance support locator: `{support}`
Verification command: `python3 -m pytest tests/acceptance/test_value.py`
"""


def _typed(supports: tuple[str, ...]) -> DesignFacts:
    return DesignFacts(
        targets=(DesignTarget("src/value.py", "EXTEND"),),
        paradigm="object_oriented",
        decisions=("reuse the existing port",),
        oracle="tests/acceptance/test_value.py",
        acceptance_supports=supports,
        verification=(("python3", "-m", "pytest", "tests/acceptance/test_value.py"),),
    )


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
    assert outcome.failure.what == "AcceptanceSupportIgnored"


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


def test_a_provider_that_never_started_is_not_reported_as_an_envelope_defect(
    tmp_path,
) -> None:
    """Measured 2026-09-05, run 12: `[Errno 7] Argument list too long` was
    reported as `ModelEnvelopeUnavailable`, HOW "observe the provider result" --
    a HOW nobody can execute, because no provider process ever existed."""

    class RefusingPort:
        def invoke(self, **_kwargs):
            raise OSError(7, "Argument list too long", "/usr/bin/claude")

    outcome = DeliveryContinuationRunner()._invoke(
        RefusingPort(), tmp_path, "nw-product-owner", "classify", None
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert outcome.failure.what == "ProviderSpawnFailed"
    assert "no provider process existed" in outcome.failure.how


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
    drift = runner._scope_drift(root, status, before)
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
    return DesignFacts(
        targets=targets,
        paradigm="object_oriented",
        decisions=("reuse the existing port",),
        oracle="tests/acceptance/test_value.py",
        acceptance_supports=supports,
        verification=(("python3", "-m", "pytest", "tests/acceptance/test_value.py"),),
    )


def test_a_declared_target_that_is_also_an_acceptance_support_stays_mutable(
    tmp_path,
) -> None:
    """Measured 2026-09-05, run 15 turn 04: the crafter was handed nothing.

    The architect named `graphify_code_fact_adapter.py` both as the EXTEND
    target and as a support the oracle's reviewer must read -- legitimate in
    meaning: read this file to judge the oracle, change it to deliver.  The
    runner subtracted the whole acceptance set from the targets, so
    `mutable_targets` reached the paid crafter turn EMPTY while
    `target_decisions` authorized an EXTEND, and the crafter answered
    `indeterminate` on the contradiction instead of working.  A target
    declaration is the model's decision about what the delivery changes; being
    read as evidence never withdraws it.
    """
    root = repo(tmp_path, "notes/any.md")

    facts = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (DesignTarget("src/value.py", "EXTEND"),),
            ("src/value.py", "tests/acceptance/support.py"),
        ),
    )

    assert isinstance(facts, AuthorityFacts)
    assert DeliveryContinuationRunner._mutable_targets(facts) == ("src/value.py",)


def test_the_oracle_is_never_a_mutable_target(tmp_path) -> None:
    """ADR-SSOT-002 §12: the crafter never edits the immutable acceptance oracle."""
    root = repo(tmp_path, "notes/any.md")

    facts = DeliveryContinuationRunner._derive(
        root,
        _typed_targets(
            (
                DesignTarget("tests/acceptance/test_value.py", "CREATE_NEW"),
                DesignTarget("src/value.py", "EXTEND"),
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
            (DesignTarget("tests/acceptance/test_value.py", "CREATE_NEW"),), ()
        ),
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "NoMutableProductionTarget"
    assert "targets" in outcome.failure.why
    assert "tests/acceptance/test_value.py" in outcome.failure.why
    assert "tests/acceptance/test_value.py" in outcome.failure.how


ORACLE_ONLY_SECTION = """## Value
Paradigm: object-oriented
| Target | Decision |
| --- | --- |
| `tests/acceptance/test_value.py` | CREATE_NEW |
**PRESERVATION**
Oracle target locator: `tests/acceptance/test_value.py`
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
    assert outcome.failure.what == "NoMutableProductionTarget"


def test_a_resumed_handover_bound_to_an_oracle_only_table_is_refused(tmp_path) -> None:
    """A durable graph outlives the rule, so the resume path carries the verdict.

    `_derive` runs on the resume path too, through `_validate_bound_scopes`,
    and there the value is ALREADY bound: no rerun can re-elicit DESIGN for it,
    so a HOW naming only the re-elicitation would send the operator into a run
    that fails identically forever.  The durable case has one exit and the HOW
    must name it -- the same clause `_admit_supports` already carries.
    """
    root = repo(tmp_path, "notes/any.md")
    stored = create_handover(
        root,
        "resume the Request",
        (
            HandoverValue(
                "the tool answers",
                (),
                _typed_targets(
                    (DesignTarget("tests/acceptance/test_value.py", "CREATE_NEW"),), ()
                ),
            ),
        ),
    )
    assert not isinstance(stored, Blocked)

    outcome = DeliveryContinuationRunner()._validate_bound_scopes(root, stored)

    assert outcome is not None
    assert outcome.failure is not None
    assert outcome.failure.what == "NoMutableProductionTarget"
    # The HOW, executed: it names the handover, and deleting it is what the
    # bound case actually needs.
    assert ".nwave/des/handover.json" in outcome.failure.how
    handover_path(root).unlink()
    assert not handover_path(root).exists()
