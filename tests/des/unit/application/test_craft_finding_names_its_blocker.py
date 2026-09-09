"""The crafter names WHO can unblock its batch, as DATA the step hands back.

WHAT CHANGED WITH THE RETIREMENT OF THE COMPOSED RUN, and it is a design
decision this file records rather than a rewrite of convenience. Five scenarios
here asserted that the SOFTWARE spent one correction window on the role the
closed word named -- the acceptance designer for `oracle`, the architect for
`design` -- and re-crafted the same batch afterwards. That is a property over
MORE THAN ONE invocation, so ADR-DES-003 Section 11 sorts it to the composer
(«fixed correction edges (13, 15, 27) | composer | become `NEXT` moves»), and
Section 13's ninth amendment says so in as many words: «the software traverses
no correction edge; the orchestrator chooses the owner and re-invokes it».
`craft_value` carries `route_blockers=False` for exactly that reason.

WHAT SURVIVES, and it is the measurement half. One craft turn still refuses
under its own name, still forwards the crafter's finding verbatim, and still
refuses LOUD when the closed word is absent. Those are laws of ONE invocation,
so they are asserted here on `des craft` driven alone.

MEASURED THREE TIMES: runs 31 (`20260906T014933Z-735633`, turn 08), 32b
(`20260906T032332Z-921671`, turn 04) and 33 (`20260906T032944Z-924463`, turns
05-06).  The crafter implemented the batch, ran the declared oracle, found one
or more cases still red for a defect of the ORACLE ITSELF -- absolute paths
compared across two temporary roots, the wrong fallback provider, the
`file:offset` site format of the text-search adapter -- and refused honestly:
«cannot be driven green without editing the oracle, which is immutable».  The
runner closed with `CraftRejected`/`VerificationFailed` and a HOW reading «act
on the finding, then re-run», whose resume returns to the same crafter over the
same oracle.  The only real way out was a NEW Request -- Product Owner,
architect and acceptance designer paid again, roughly $2.5 and fifteen minutes
each -- so three runs, about $8, were spent on findings one designer turn of
about $0.3 would have answered.

The MODEL decides who is blocking it, the SOFTWARE routes on the closed word
(`boundary:software-measures-model-decides`).  Reading the owner off the
finding's prose is forbidden: a diagnostic is diagnostic only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.application.delivery_continuation import DeliveryOutcome, Disposition
from des.ports.driven_ports.task_invocation_port import (
    CraftBlocker,
    DesignFacts,
    DesignTarget,
    ModelOutcome,
    ModelRun,
    ProductValue,
    TaskInvocationPort,
)
from tests.des._helpers.step_stimulus import crafted, through_oracle


# A real-length observation: the runner refuses a value under the measured
# placeholder floor, so a shorter fixture would exercise that floor instead of
# the routing law under test here.
OBSERVATION = "the installed answer module answers 42 through its public entry point"
ORACLE = "tests/acceptance/test_answer.py"
PRODUCTION = "src/answer.py"
BODY = "ANSWER = 42\n"
#: The existing test file a defective `targets` list omits.
SHARED = "tests/acceptance/test_shared.py"

#: Run 33's finding, in the shape the crafter actually stated it.
FINDING = (
    "the declared oracle compares two absolute paths rooted in different "
    "temporary directories, so no production byte can drive it green; the "
    "repair is in the oracle, which is immutable to me."
)


def _facts(*, extra: tuple[str, ...] = ()) -> DesignFacts:
    return DesignFacts(
        targets=(
            DesignTarget(PRODUCTION, "CREATE_NEW"),
            DesignTarget(ORACLE, "CREATE_NEW"),
            *(DesignTarget(path, "EXTEND") for path in extra),
        ),
        paradigm="object_oriented",
        decisions=(f"one observable value: {OBSERVATION}",),
        oracle=ORACLE,
        acceptance_supports=(),
        verification=(("python", "-m", "pytest", ORACLE, "-q"),),
    )


CORRECTED = _facts(extra=(SHARED,))


def _oracle_body() -> str:
    """RED on its own assertion, never on its scaffolding."""
    return (
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_value() -> None:\n"
        f"    assert Path({PRODUCTION!r}).read_text(encoding='utf-8') == {BODY!r}\n"
    )


def _accepted(**facts: object) -> ModelRun:
    return ModelRun(ModelOutcome.Accepted, "", 0, True, **facts)  # type: ignore[arg-type]


def _blocked(blocker: CraftBlocker | None) -> ModelRun:
    return ModelRun(ModelOutcome.Rejected, FINDING, 0, True, craft_blocker=blocker)


def _fact(prompt: str, key: str) -> object:
    """One rendered prompt fact, read back the way the runner wrote it."""
    for line in prompt.splitlines():
        name, separator, raw = line.partition(": ")
        if separator and name == key:
            return json.loads(raw)
    raise AssertionError(f"the prompt carries no {key}: {prompt}")


def _has(prompt: str, key: str) -> bool:
    return any(line.startswith(f"{key}: ") for line in prompt.splitlines())


class ScriptedPort(TaskInvocationPort):
    """One value, one batch; the crafter answers from a script."""

    def __init__(
        self,
        root: Path,
        crafts: list[ModelRun],
        *,
        corrected: DesignFacts | None = None,
        judgements: list[ModelRun] | None = None,
    ) -> None:
        self.root = root
        self.crafts = list(crafts)
        self.corrected = corrected
        self.judgements = list(judgements or ())
        self.roles: list[str] = []
        self.architect_turns: list[str] = []
        self.designer_findings: list[str] = []
        self.craft_prompts: list[str] = []
        self.designer_corrections = 0
        self._designed = False
        self._oracle = ORACLE

    def _write_oracle(self, *, revised: bool = False) -> None:
        written = self.root / self._oracle
        written.parent.mkdir(parents=True, exist_ok=True)
        body = _oracle_body()
        written.write_text(
            body + "\n\n# revised\n" if revised else body, encoding="utf-8"
        )

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        self.roles.append(role_id)
        if role_id == "nw-product-owner":
            return _accepted(product_values=(ProductValue(OBSERVATION),))
        if role_id == "nw-solution-architect":
            self.architect_turns.append(str(_fact(prompt, "observation")))
            if self._designed:
                assert self.corrected is not None, "unscripted architect correction"
                return _accepted(design_facts=self.corrected)
            self._designed = True
            return _accepted(design_facts=_facts())
        if role_id == "nw-acceptance-designer":
            if _has(prompt, "observation"):
                self._oracle = str(_fact(prompt, "oracle"))
                self._write_oracle()
                return _accepted()
            self.designer_corrections += 1
            self.designer_findings.append(str(_fact(prompt, "finding")))
            self._write_oracle(revised=True)
            return _accepted()
        if role_id == "nw-acceptance-designer-reviewer":
            return _accepted()
        if role_id == "nw-software-crafter":
            self.craft_prompts.append(prompt)
            assert self.crafts, "unscripted craft turn"
            answer = self.crafts.pop(0)
            if answer.outcome is ModelOutcome.Accepted:
                produced = self.root / PRODUCTION
                produced.parent.mkdir(parents=True, exist_ok=True)
                produced.write_text(BODY, encoding="utf-8")
            return answer
        if role_id in ("nw-software-crafter-reviewer", "nw-user-examiner"):
            assert self.judgements, f"unscripted {role_id} judgement"
            return self.judgements.pop(0)
        raise AssertionError(f"unscripted role {role_id}")


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def subject(tmp_path: Path) -> Path:
    root = tmp_path / "subject"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "a@b")
    git(root, "config", "user.name", "a")
    (root / "README.md").write_text("subject\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root


REQUEST = "deliver one value"


def one_craft_turn(subject: Path, port: ScriptedPort) -> DeliveryOutcome | tuple:
    """`po`, `design`, `oracle`, then ONE `craft` -- each invoked by this test."""
    runner, stored, design = through_oracle(port, subject, REQUEST)
    return crafted(runner, port, subject, stored, design)


@pytest.mark.parametrize(
    "blocker",
    [CraftBlocker.Oracle, CraftBlocker.Design, CraftBlocker.Product],
    ids=["oracle", "design", "product"],
)
def test_a_blocked_craft_turn_refuses_and_buys_nobody_a_correction(
    subject: Path, blocker: CraftBlocker
) -> None:
    """Every closed word ends this invocation; none of them routes anywhere.

    The three words used to mean three different things to the software -- two
    opened a correction window on a role, the third did not. A step invoked
    alone treats them alike, because choosing who answers a finding is Section
    4b's decision for the orchestrator and not a branch in here.
    """
    port = ScriptedPort(subject, [_blocked(blocker)])

    outcome = one_craft_turn(subject, port)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Refusal
    assert outcome.failure is not None
    assert outcome.failure.what == "CraftRejected"
    # Nobody was re-invoked: one crafter turn, no correction of any role.
    assert port.roles.count("nw-software-crafter") == 1, port.roles
    assert port.designer_corrections == 0, port.roles
    assert port.architect_turns == [OBSERVATION], port.roles


def test_the_crafters_own_finding_travels_verbatim_into_the_refusal(
    subject: Path,
) -> None:
    """The runner never paraphrases a diagnostic; it forwards it.

    This is the surviving half of the routing scenarios: the finding has to
    reach the orchestrator intact for it to be able to choose an owner at all.
    """
    port = ScriptedPort(subject, [_blocked(CraftBlocker.Oracle)])

    outcome = one_craft_turn(subject, port)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.failure is not None
    assert FINDING in outcome.failure.why


def test_a_refusal_that_names_no_blocker_is_still_the_crafters_own_refusal(
    subject: Path,
) -> None:
    """An absent closed word costs the step nothing, because it routes nothing.

    RECONCILED AGAINST THE CURRENT CODE, and the change is a consequence rather
    than a regression. While the software spent a window on the word, an
    envelope that carried none left it with nothing to route and no honest way
    to guess, so it answered `CraftBlockerMissing` / `Indeterminate` -- the
    DEGRADE-LOUD of a routing decision it could not take (GDP-6). A step takes
    no such decision, so there is nothing left to degrade: the word is data the
    orchestrator may or may not receive, and the turn is the crafter's own
    refusal either way. What must NOT happen is the step inventing an owner,
    and the assertions below are that it does not: no role is re-invoked.
    """
    port = ScriptedPort(subject, [_blocked(None)])

    outcome = one_craft_turn(subject, port)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Refusal
    assert outcome.failure is not None
    assert outcome.failure.what == "CraftRejected"
    assert FINDING in outcome.failure.why
    assert port.designer_corrections == 0, port.roles
    assert port.architect_turns == [OBSERVATION], port.roles


def test_an_indeterminate_craft_turn_buys_no_correction(subject: Path) -> None:
    # A turn that established no semantic result answers nothing, so spending a
    # paid correction on it would buy a repair for a finding nobody made.
    port = ScriptedPort(
        subject,
        [ModelRun(ModelOutcome.Indeterminate, "the crafter did not answer", 0, True)],
    )

    outcome = one_craft_turn(subject, port)

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "CraftIndeterminate"
    assert port.designer_corrections == 0, port.roles


def test_an_accepted_craft_turn_changes_the_declared_target(subject: Path) -> None:
    """The negative control: the same stimulus, answered, writes the byte.

    Without it every assertion above is satisfied by a `craft` step that
    refuses unconditionally.
    """
    port = ScriptedPort(subject, [_accepted()])

    outcome = one_craft_turn(subject, port)

    assert not isinstance(outcome, DeliveryOutcome), outcome
    assert (subject / PRODUCTION).read_text(encoding="utf-8") == BODY
    assert SHARED not in _fact(port.craft_prompts[-1], "mutable_targets")  # type: ignore[operator]


def test_a_failed_standalone_verify_retains_native_evidence_after_candidate_cleanup(
    subject: Path,
) -> None:
    """The terminal locator outlives the temporary candidate it observed."""
    port = ScriptedPort(subject, [_accepted()])
    runner, stored, design = through_oracle(port, subject, REQUEST)
    assert not isinstance(
        crafted(runner, port, subject, stored, design), DeliveryOutcome
    )

    # The declared oracle is genuine, then the candidate deliberately violates
    # it. This is a native failure, not a mocked record or a provider verdict.
    (subject / PRODUCTION).write_text("ANSWER = 41\n", encoding="utf-8")
    outcome = runner.verify_request(
        subject, port, stored, [(stored.values[0].observation, design)]
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.disposition is Disposition.Refusal
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationFailed"
    prefix = "; native evidence retained at "
    locator = outcome.failure.why.partition(prefix)[2]
    assert locator.startswith(".nwave/des/logs/native/"), outcome.failure.why
    record = subject / locator
    assert record.is_file(), locator
    retained = json.loads(record.read_text(encoding="utf-8"))
    assert retained[0]["argv"] == ["python", "-m", "pytest", ORACLE, "-q"]
    assert retained[0]["exit"] == 1
    assert "AssertionError" in retained[0]["stdout"] + retained[0]["stderr"]
    # Candidate worktrees are still ephemeral; only their observation remains.
    worktrees = subprocess.run(
        ["git", "-C", str(subject), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "nwave-candidate-" not in worktrees


@pytest.mark.parametrize(
    ("judgements", "disposition"),
    [
        (
            [ModelRun(ModelOutcome.Rejected, "review refusal", 0, True)],
            Disposition.Refusal,
        ),
        (
            [ModelRun(ModelOutcome.Indeterminate, "review uncertainty", 0, True)],
            Disposition.Indeterminate,
        ),
        (
            [
                _accepted(),
                ModelRun(ModelOutcome.Rejected, "examiner refusal", 0, True),
            ],
            Disposition.Refusal,
        ),
        (
            [
                _accepted(),
                ModelRun(ModelOutcome.Indeterminate, "examiner uncertainty", 0, True),
            ],
            Disposition.Indeterminate,
        ),
    ],
    ids=[
        "reviewer-refusal",
        "reviewer-indeterminate",
        "examiner-refusal",
        "examiner-indeterminate",
    ],
)
def test_native_success_evidence_survives_later_judgement_failure(
    subject: Path,
    monkeypatch: pytest.MonkeyPatch,
    judgements: list[ModelRun],
    disposition: Disposition,
) -> None:
    """A later judge cannot discard the one successful native observation."""
    port = ScriptedPort(subject, [_accepted()], judgements=judgements)
    runner, stored, design = through_oracle(port, subject, REQUEST)
    assert not isinstance(
        crafted(runner, port, subject, stored, design), DeliveryOutcome
    )

    calls = 0
    native = runner._native

    def counted_native(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return native(*args, **kwargs)

    monkeypatch.setattr(runner, "_native", counted_native)
    outcome = runner.verify_request(
        subject, port, stored, [(stored.values[0].observation, design)]
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.disposition is disposition
    assert outcome.failure is not None
    prefix = "; native evidence retained at "
    locator = outcome.failure.why.partition(prefix)[2]
    assert locator.startswith(".nwave/des/logs/native/"), outcome.failure.why
    record = subject / locator
    retained = json.loads(record.read_text(encoding="utf-8"))
    assert len(retained) == 1
    assert retained[0]["argv"] == ["python", "-m", "pytest", ORACLE, "-q"]
    assert retained[0]["exit"] == 0
    assert "1 passed" in retained[0]["stdout"]
    assert retained[0]["stderr"] == ""
    candidate = record.name.split("-20", 1)[0]
    assert len(candidate) == 40
    assert all(character in "0123456789abcdef" for character in candidate)
    assert calls == 1
    worktrees = subprocess.run(
        ["git", "-C", str(subject), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "nwave-candidate-" not in worktrees
