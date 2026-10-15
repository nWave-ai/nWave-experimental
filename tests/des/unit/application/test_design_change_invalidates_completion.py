"""A DESIGN correction preserves historical turn records without reuse.

Turn records retain their authored identity and owned-byte snapshot.  A changed
DESIGN makes those records historical through the normal currentness predicate;
it does not delete them.  If the complete original authority returns, the same
records can become current again.  No second registry or destructive cleanup is
needed.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from des.application.handover import StoredHandover
from des.domain.turn_record_ref import ORACLE_WITNESS_TURN, turn_ref
from des.ports.driven_ports.task_invocation_port import (
    ModelOutcome,
    ModelRun,
    ProductValue,
    TaskInvocationPort,
)
from tests.des._helpers.step_stimulus import (
    crafted,
    decomposed,
    designed,
    immutable_source,
    oracled,
)
from tests.des.unit.application.test_authored_oracle_is_executed_red import (
    oracle_manifest,
)


OBSERVATION = "the installed answer module answers 42 through its public entry point"
ORACLE = "tests/acceptance/test_answer.py"
PRODUCTION = "src/answer.py"
REQUEST = "deliver the answer, corrected mid-flight"

RED_ON_ITS_ASSERTION = (
    "def test_answer():\n"
    "    from pathlib import Path\n"
    "\n"
    f"    assert Path({PRODUCTION!r}).read_text(encoding='utf-8') == 'ANSWER = 42\\n'\n"
)


def _design(decision: str) -> dict:
    """Submit the shared fixture's complete schema-2 producer manifest."""
    return oracle_manifest(decision)


def _accepted(**facts: object) -> ModelRun:
    return ModelRun(ModelOutcome.Accepted, "", 0, True, **facts)  # type: ignore[arg-type]


class RedesigningPort(TaskInvocationPort):
    """`nw-solution-architect` answers D1 first, then whatever `next_design`
    holds on every later call -- the shape a `finding`-carrying correction
    takes. Every other role writes real bytes so the oracle/craft turns are
    genuine, measured facts and not fixtures pretending to be.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.roles: list[str] = []
        self.next_design: dict = _design("D2")
        self._architect_calls = 0

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
            self._architect_calls += 1
            if self._architect_calls == 1:
                return _accepted()
            return _accepted()
        if role_id == "nw-acceptance-designer":
            written = self.root / ORACLE
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text(RED_ON_ITS_ASSERTION, encoding="utf-8")
            return _accepted()
        if role_id == "nw-software-crafter":
            produced = self.root / PRODUCTION
            produced.parent.mkdir(parents=True, exist_ok=True)
            produced.write_text("ANSWER = 42\n", encoding="utf-8")
            return _accepted()
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


@pytest.fixture
def genesis(subject: Path) -> str:
    """Retain the base established by the fixture, before any author or craft call."""
    return subprocess.run(
        ["git", "-C", str(subject), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _authored_and_crafted(
    subject: Path, port: RedesigningPort, *, baseline: str
) -> tuple[DeliveryContinuationRunner, StoredHandover, object]:
    """Reach D1 authored (RED, recorded) and crafted (GREEN bytes, recorded)."""
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, subject, REQUEST)
    stored, d1 = designed(
        runner,
        port,
        subject,
        stored,
        _design("D1"),
    )
    first = oracled(runner, port, subject, stored, d1, baseline=baseline)
    assert first.refusal is None, first.refusal
    outcome = crafted(runner, port, subject, stored, d1)
    assert not isinstance(outcome, DeliveryOutcome), outcome
    assert runner.oracle_turn_complete(subject, stored, stored.values[0], d1), (
        "the probe requires D1's oracle turn to already be a recorded fact"
    )
    assert runner.craft_turn_complete(subject, stored, stored.values[0], d1), (
        "the probe requires D1's craft turn to already be a recorded fact"
    )
    return runner, stored, d1


def test_changed_design_invalidates_old_author_and_craft_completion(
    subject: Path,
    genesis: str,
) -> None:
    # WHAT: D1 is authored and crafted; the architect then corrects the
    # DECISIONS field alone (D1 -> D2) over the exact same oracle bytes.
    # WHY: `_turn_completed`'s tree-only comparison cannot see a changed
    # `decisions` that leaves the same acceptance/mutable bytes on disk, so
    # re-running the UNCHANGED old oracle is not D2 semantic evidence -- the
    # recorded author and craft claims are stale the moment the design moves.
    # HOW: `_bind_authority` forgets the affected value's oracle/craft turn
    # refs before the new authority becomes bound.
    port = RedesigningPort(subject)
    runner, stored, d1 = _authored_and_crafted(subject, port, baseline=genesis)

    corrected = designed(
        runner,
        port,
        subject,
        stored,
        port.next_design,
    )
    assert not isinstance(corrected, DeliveryOutcome), corrected
    stored, d2 = corrected
    assert tuple(d1.resolved.catalog.resolve(ref) for ref in d1.decisions) != tuple(
        d2.resolved.catalog.resolve(ref) for ref in d2.decisions
    ), "the probe requires a genuine design change"
    assert d1.acceptance_paths == d2.acceptance_paths, (
        "the probe requires unchanged oracle bytes on disk"
    )

    assert not runner.oracle_turn_complete(subject, stored, stored.values[0], d2), (
        "WHAT: oracle_turn_complete still reads D1's authoring as complete "
        "over D2\n"
        "WHY: unchanged oracle bytes executed under D1 are not evidence of "
        "judgement over D2's decisions\n"
        "HOW: forget the recorded oracle turn when the bound design changes"
    )
    assert not runner.craft_turn_complete(subject, stored, stored.values[0], d2), (
        "WHAT: craft_turn_complete still reads D1's craft as complete over D2\n"
        "WHY: bytes built to satisfy D1 carry no judgement about D2\n"
        "HOW: forget the recorded craft turn when the bound design changes"
    )


def test_identical_design_correction_keeps_completion_and_cheap_resume(
    subject: Path,
    genesis: str,
) -> None:
    # WHAT: an accepted correction that returns the SAME typed facts D1 already
    # holds must not disturb either recorded claim.
    # WHY: ADR-DES-003 -- identity of a model's answer with the previous one is
    # a fact, not a hazard; forgetting on no real change would turn every
    # no-op correction into a paid re-authoring and re-crafting.
    # HOW: `_bind_authority` compares current vs. replacement by the typed
    # facts' own equality and forgets nothing when they match.
    port = RedesigningPort(subject)
    runner, stored, d1 = _authored_and_crafted(subject, port, baseline=genesis)
    port.next_design = _design("D1")  # byte-identical replacement

    corrected = designed(
        runner,
        port,
        subject,
        stored,
        port.next_design,
    )
    assert not isinstance(corrected, DeliveryOutcome), corrected
    stored, d1_again = corrected
    assert d1_again == d1, "the probe requires a byte-identical replacement"

    assert runner.oracle_turn_complete(subject, stored, stored.values[0], d1_again), (
        "an identical accepted correction must keep the recorded oracle turn"
    )
    assert runner.craft_turn_complete(subject, stored, stored.values[0], d1_again), (
        "an identical accepted correction must keep the recorded craft turn"
    )


def test_changed_design_preserves_records_as_historical_without_ref_deletion(
    subject: Path,
    genesis: str,
) -> None:
    """A correction succeeds even if a hypothetical ref deletion would fail.

    Currentness is established by the complete DESIGN identity, not by erasing
    recorded evidence.  This preserves the D1 record for an eventual exact D1
    restoration while preventing it from being reused for D2.
    """
    port = RedesigningPort(subject)
    runner, stored, _d1 = _authored_and_crafted(subject, port, baseline=genesis)

    real_git = runner._git

    def deletion_hostile_git(root: Path, *args: str, env: dict[str, str] | None = None):
        if args[:2] == ("update-ref", "-d"):
            raise AssertionError("DES must not delete historical turn records")
        return real_git(root, *args, env=env)

    runner._git = deletion_hostile_git  # type: ignore[method-assign]
    corrected = designed(
        runner,
        port,
        subject,
        stored,
        port.next_design,
    )

    assert not isinstance(corrected, DeliveryOutcome), corrected
    reread, d2 = corrected
    assert tuple(d2.resolved.catalog.resolve(ref) for ref in d2.decisions) == ("D2",)
    assert not runner.oracle_turn_complete(subject, reread, reread.values[0], d2)
    assert not runner.craft_turn_complete(subject, reread, reread.values[0], d2)


def test_witness_history_tracks_authority_and_byte_currentness_without_losing_red(
    subject: Path,
    genesis: str,
) -> None:
    port = RedesigningPort(subject)
    runner, stored, d1 = _authored_and_crafted(subject, port, baseline=genesis)
    first = runner.oracle_witness(subject, stored, OBSERVATION, d1)
    assert first and first[0]["current"] is True
    assert first[0]["oracles"][0]["verdict"] == "red"

    corrected, d2 = designed(
        runner,
        port,
        subject,
        stored,
        port.next_design,
    )
    historical = runner.oracle_witness(subject, corrected, OBSERVATION, d2)
    assert historical and historical[0]["current"] is False
    assert historical[0]["oracles"] == first[0]["oracles"]

    port.next_design = _design("D1")
    restored, original = designed(
        runner,
        port,
        subject,
        corrected,
        port.next_design,
    )
    assert runner.oracle_witness(subject, restored, OBSERVATION, original) == first
    (subject / ORACLE).write_text(RED_ON_ITS_ASSERTION + "\n# changed acceptance\n")
    moved = runner.oracle_witness(subject, restored, OBSERVATION, original)
    assert moved and moved[0]["current"] is False


def test_a_first_green_witness_is_durable_and_follows_value_record_lifecycle(
    subject: Path,
) -> None:
    port = RedesigningPort(subject)
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, subject, REQUEST)
    stored, design = designed(
        runner,
        port,
        subject,
        stored,
        _design("D1"),
    )
    (subject / PRODUCTION).parent.mkdir(parents=True, exist_ok=True)
    (subject / PRODUCTION).write_text("ANSWER = 42\n")
    green_source, green_tree = immutable_source(subject, (PRODUCTION,))
    outcome = oracled(runner, port, subject, stored, design, baseline=green_source)
    assert outcome.refusal is None
    witness = runner.oracle_witness(subject, stored, OBSERVATION, design)
    assert witness and witness[0]["oracles"][0]["verdict"] == "green"
    assert witness[0]["current"] is True
    assert witness[0]["baseline"] == {
        "sha": green_source,
        "tree": green_tree,
        "source": "explicit",
    }, (
        "WHAT: the first GREEN witness does not identify the explicitly selected product source. "
        "WHY: dirty workspace GREEN must never be mistaken for original-source evidence. "
        "HOW: record the resolved immutable GREEN SHA/tree supplied by the test host."
    )

    new_request = REQUEST + " with an amended scope"
    runner._rekey_turn_records(subject, REQUEST, new_request, (OBSERVATION,))
    assert runner.oracle_witness(subject, stored, OBSERVATION, design) == ()
    rewritten = replace(stored, request=new_request)
    assert runner.oracle_witness(subject, rewritten, OBSERVATION, design) == witness
    runner._drop_records_for(subject, new_request, (OBSERVATION,))
    assert runner.oracle_witness(subject, rewritten, OBSERVATION, design) == ()
    assert (
        runner._git(
            subject,
            "rev-parse",
            "--verify",
            "--quiet",
            turn_ref(new_request, OBSERVATION, ORACLE_WITNESS_TURN),
        ).returncode
        != 0
    )
