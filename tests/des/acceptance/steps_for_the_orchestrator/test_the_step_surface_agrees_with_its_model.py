"""One property holds the whole contract: the surface agrees with its model.

ADR-DES-003 §12 asks for this instead of a checklist reviewers must remember:

    The real surface agrees with its reference model on every generated
    sequence.

Hypothesis draws sequences of step invocations through the PUBLIC surface -- the
CLI in process, the shared fake provider scripted to answer `accepted`,
`rejected` or `malformed` -- including repeats, out-of-range positions and
out-of-order values, and after each invocation asserts that the parsed terminal
equals the model terminal on outcome, `WHAT`, `TURNS-BOUGHT` and the number of
`NEXT` lines, and that the turns the provider was actually asked for equal the
model's cost.

**The generator is where both classes are falsified.** It draws the ADMISSIBLE
odd orders and repeats, for which the model predicts `Success` at the measured
cost, and the INADMISSIBLE ones -- integrate before verify, craft before oracle
-- for which it predicts exactly one sequence refusal with exactly one `NEXT`.
A slice that adds a precautionary content refusal, or drops a sequence one, goes
red here before it reaches a review.

Why one is enough: L1, G3 to G8, §2.4's preconditions and §4's class rule are
all CONSEQUENCES of the model. A slice that changes a step without changing the
model goes red; one that changes both shows the design change in a single diff,
where a reviewer can see it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator import step_model
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    base_repository,
    block,
    hermetic_environment,
    observation,
)


REQUEST = "one Request whose whole step surface is compared with its model"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
RED_ORACLE = "def test_value():\n    import product_value  # noqa\n"
# This property explores many generated command sequences. Its native command
# must resolve, but must not run a real suite for every generated state.
FAST_VERIFICATION = [
    sys.executable,
    "-c",
    "from pathlib import Path; raise SystemExit(not Path('product_value.py').exists())",
]

#: The invocations the generator may draw. Positions 1 and 2 exist after `po`;
#: 9 never does, which is how `ValueOutOfRange` is reached.
_INVOCATIONS = [
    ("state", None),
    ("project", None),
    ("po", None),
    ("rewrite", None),
    ("design", 1),
    ("design", 2),
    ("design", 9),
    ("oracle", 1),
    ("oracle", 2),
    ("craft", 1),
    ("craft", 2),
    ("verify", None),
    ("integrate", None),
]

#: What the provider says. A first version drew only `accepted`, which left the
#: whole content-refusal half of the model unreachable and let a mutation of
#: `orchestrator_line` survive -- the prose claimed otherwise, which is the same
#: class of lie this project spent a day removing from its terminals.
_ANSWERS = ["accepted", "rejected", "malformed"]

#: A second Request, so the §7 rewrite is drawn rather than excluded by
#: construction: `po` twice with the same bytes is L1, `rewrite` is the other.
SECOND_REQUEST = "a second Request, which keeps one value and drops the other"


def _answer(role: str, answer: str = "accepted") -> dict:
    """One envelope per role and answer, shaped as the real boundary requires.

    `malformed` carries an unexpected key, which every role's reader refuses the
    same way -- one shape for a class the model states once (§4 class E).
    """
    if answer == "malformed":
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "an answer the boundary cannot read",
                "unexpected": 1,
            }
        }
    if answer == "rejected":
        payload = {"outcome": "rejected", "diagnostic": "this does not hold"}
        if role in ("po", "rewrite"):
            payload["values"] = []
        if role == "design":
            payload["design_facts"] = None
        if role == "craft":
            payload["blocked_by"] = "oracle"
        if role == "verify":
            # The first of the two turns is the whole-diff review, and a
            # REFUSING review still owes the word that routes its finding.
            payload |= {"defect_owner": "oracle", "defect_value": None}
        return {"structured_output": payload}
    return _accepted(role)


def _accepted(role: str) -> dict:
    """One accepted envelope per role, shaped as the real boundary requires."""
    if role == "po":
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "decomposed into two ordered observable values",
                "values": [
                    {"observation": observation("A")},
                    {"observation": observation("B")},
                ],
            }
        }
    if role == "rewrite":
        # The first observation VERBATIM plus one new: one KEPT, one ARCHIVED,
        # one NEW, split by byte identity exactly as §7 measures it.
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "one value still holds; the other does not",
                "values": [
                    {"observation": observation("A")},
                    {"observation": observation("C")},
                ],
            }
        }
    if role == "design":
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "bound the typed facts",
                "design_facts": {
                    "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                    "paradigm": "object_oriented",
                    "decisions": ["one opaque semantic decision"],
                    "oracle": ORACLE,
                    "acceptance_supports": [SUPPORT],
                    "verification": [FAST_VERIFICATION],
                    "oracle_verification_index": 0,
                },
            }
        }
    if role == "oracle":
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "authored the oracle",
            },
            "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
        }
    if role == "craft":
        return {
            "structured_output": {
                "outcome": "accepted",
                "diagnostic": "implemented the value",
            },
            "writes": {TARGET: "VALUE = 1\n"},
        }
    # `verify` is native-only. The generated provider envelope is deliberately
    # unused there: review and examination are explicit host choices through
    # their separate public ports.
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "the candidate answers the observation",
        }
    }


#: How many answers each step may consume, so the fake never runs out.
_BUDGET = {
    "po": 1,
    "rewrite": 1,
    "design": 1,
    "oracle": 1,
    "craft": 1,
    "verify": 0,
    "integrate": 0,
}


class Harness:
    """One throwaway repository and provider, built FRESH for each example.

    Hypothesis reuses a function-scoped fixture across examples, so a shared
    repository accumulates state the model restarts without -- and the first run
    of this property found exactly that, reporting a real disagreement that was
    the test's own leak. A comparison between a model and a surface is only a
    comparison when both start from the same state.
    """

    def __init__(self, home: Path, index: int) -> None:
        # The SAME checkout the rest of the corpus builds, specs included: a
        # repository carrying only a README resolves no role spec of its own and
        # falls through to whatever the host developer installed, so the model
        # would be compared against the machine rather than against the tree.
        self.root = base_repository(home / f"root-{index}")
        self.claude = home / f"claude-{index}"
        self.bin = home / f"bin-{index}"
        self.results = home / f"results-{index}.json"
        self.counter = home / f"counter-{index}"
        self.log = home / f"log-{index}.json"

    def run(self, argv: list[str], answers: list[dict], stdin: str = ""):
        self.results.write_text(json.dumps(answers))
        self.counter.unlink(missing_ok=True)
        return run_cli_in_process(
            argv,
            cwd=self.root,
            env=hermetic_environment(
                fake_provider.environment(
                    self.root,
                    launcher_dir=self.bin,
                    results=self.results,
                    log=self.log,
                    counter=self.counter,
                    package_parent=Path(__file__).parents[4] / "src",
                ),
                self.claude,
            ),
            stdin_text=stdin,
            catch_all=True,
        )


def _canonical_invocation(state) -> tuple[str, int | None]:
    """The step the model says the canonical order owes next, as an invocation.

    The order is DATA the design states once; following it here is what a real
    orchestrator does with a `NEXT` line, and it is how the generator reaches
    a built candidate at all.
    """
    name = step_model.canonical_next(state)
    if name in ("design", "oracle", "craft"):
        for position, value in enumerate(state.values, start=1):
            missing = (
                not value.design_bound
                or not value.oracle_recorded
                or not value.craft_recorded
            )
            if missing:
                return name, position
    return name, None


def _argv(root: Path, name: str, value: int | None) -> list[str]:
    argv = [name, "--repo-root", str(root)]
    if name == "po":
        argv.append("--project")
    if name == "project":
        argv += ["--html", str(root.parent / f"{root.name}-projection.html")]
    if value is not None:
        argv += ["--value", str(value)]
    return argv


def walk(harness: Harness, moves) -> None:
    """Drive one sequence through the real surface, comparing every terminal.

    `moves` is a callable taking the model state and returning the next
    invocation, or `None` to stop. Two callers pass two different sources: the
    property draws adaptively, the parametrised cases replay a fixed list, and
    both compare against the same model with the same assertions.
    """
    root, turns = harness.root, harness.log
    state = step_model.ModelState()
    #: The candidate the surface last named. An orchestrator re-invoking
    #: `integrate` passes back the SHA it was given, so the walk does too --
    #: which is what makes «this candidate is already the destination»
    #: reachable at all, and tells it apart from a Request that never existed.
    #:
    #: IT IS LEARNT WHERE THE SURFACE STATES IT, which is the `CANDIDATE` row
    #: `verify` prints. Reading it only off a `NEXT` line that happens to name
    #: `integrate` made the walk depend on the canonical order having nothing
    #: else to owe: a candidate built while a later value still owes its oracle
    #: is real and integrable, but the order names that oracle, so the walk
    #: invented a SHA of zeros and measured the identity refusal that answers
    #: it against a model that was talking about the candidate.
    last_named = ""
    while True:
        drawn = moves(state)
        if drawn is None:
            return
        name, value, answer = drawn
        if name == "integrate":
            # The candidate SHA is not a model fact -- the model says only
            # whether one exists -- so the real form is read from the surface.
            _code, out, err = harness.run(["state", "--repo-root", str(root)], [])
            named = block(out, err).get("NEXT", "")
            if "--candidate " in named:
                last_named = named.rsplit(" ", 1)[-1]
            sha = last_named or "0" * 40
            argv = ["integrate", "--repo-root", str(root), "--candidate", sha]
        else:
            argv = _argv(root, "po" if name == "rewrite" else name, value)

        spent = len(asked(turns))
        code, out, err = harness.run(
            argv,
            [_answer(name, answer)] * _BUDGET.get(name, 0),
            # `po` reads its Request from stdin; `rewrite` is the same command
            # with different bytes, which is what makes §7 reachable here
            # instead of excluded by construction.
            SECOND_REQUEST if name == "rewrite" else (REQUEST if name == "po" else ""),
        )
        state, expected = step_model.step(
            state, name, value, answer, same_candidate=bool(last_named)
        )
        rows = block(out, err)
        if "CANDIDATE" in rows:
            last_named = rows["CANDIDATE"].split()[0]

        if "DELIVERY-OUTCOME" not in rows:
            raise AssertionError(
                "step emitted no terminal outcome",
                {"argv": argv, "answer": answer, "stdout": out, "stderr": err},
            )
        assert rows["DELIVERY-OUTCOME"] == expected.outcome, (argv, answer, out + err)
        assert (code == 0) is (expected.outcome == "Success"), (argv, answer)
        if expected.what is not None:
            assert rows["WHAT"] == expected.what, (argv, answer, out + err)
        assert rows["TURNS-BOUGHT"] == str(expected.turns_bought), (
            argv,
            answer,
            rows.get("WHAT"),
            rows.get("WHY"),
        )
        assert len(asked(turns)) - spent == expected.turns_bought, (argv, answer)

        # The rows the model says the block must CARRY. Without this a mutation
        # that stops printing RECORDED, ORACLE-RED or RADIUS leaves the surface
        # agreeing with a model that never looked at what it printed.
        for label in expected.facts:
            assert label in rows, (argv, answer, label, out + err)

        # G5: the ORCHESTRATOR line is absent on Success and, on a refusal, says
        # which of the three states the block is in. A review mutated this line
        # and the property stayed green, because it never read it -- the same
        # class of gap as a terminal naming rows it does not carry.
        direction = step_model.orchestrator_row(expected)
        if direction is None:
            assert "ORCHESTRATOR" not in rows, (argv, answer, out + err)
        else:
            assert direction in rows["ORCHESTRATOR"], (argv, answer, out + err)

        printed = [
            line
            for line in (out + "\n" + err).splitlines()
            if line.startswith("NEXT: ")
        ]
        if expected.what in step_model.SEQUENCE_REFUSALS:
            assert len(printed) == 1, (argv, out + err)
        else:
            assert len(printed) >= expected.next_count, (argv, out + err)

        # `des state` is compared with the model state, not merely invoked: it
        # is the projection every other step is read against, and a projection
        # that drifts from the state names a step that would refuse.
        _code, out, err = harness.run(["state", "--repo-root", str(root)], [])
        projected = block(out, err)
        if state.request is None:
            assert projected["REQUEST"] == "(none)", out + err
        else:
            assert projected["REQUEST"] != "(none)", out + err
            # The verification the Request carries is projected on the same
            # terms as the value rows: present when the model holds one, and
            # never a bare SHA the reader has to decide the meaning of.
            assert ("CANDIDATE" in projected) is (state.candidate is not None), (
                out + err
            )
            for index, value_state in enumerate(state.values, start=1):
                row = projected[f"VALUE-{index}"]
                assert ("design=bound" in row) is value_state.design_bound, row
                assert ("oracle=recorded" in row) is value_state.oracle_recorded, row
                assert ("craft=recorded" in row) is value_state.craft_recorded, row


#: MEASURED on this tree, three independent runs per cell. All three mutations
#: the review named -- an `ORCHESTRATOR` line that names nothing, a
#: precautionary content refusal on `verify`'s READY path, a `design` that
#: re-buys over a bound value -- are RED here at 60 and RED at 200. A run at 60
#: costs 38s and one at 200 costs 3m00s, so the larger budget buys 2m22s of
#: nothing and is not taken (GDP-10).
#:
#: What made those mutations die is not the budget. It is that the generator
#: draws the provider's ANSWER, that the assertions read the labels and the
#: derived `ORCHESTRATOR` row, and that the model states what a closed graph
#: answers. A first version of this comment credited the budget and named an
#: example number that was a temp-directory counter: the reviewer could not
#: reproduce it, and was right not to.
#:
#: The deep path does not rest on a draw either way: the whole canonical order
#: through a closed graph is written by hand below, so `verify` on a ready
#: Request is exercised on every run. The generated half is here for BREADTH --
#: the odd orders, the repeats, the answers -- not to be the only witness of
#: any one class.
_EXAMPLES = 60


@settings(
    max_examples=_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
@given(data=st.data())
def test_every_generated_sequence_agrees_with_the_model(
    tmp_path_factory, data: st.DataObject
) -> None:
    harness = Harness(tmp_path_factory.mktemp("surface"), 0)
    length = data.draw(st.integers(min_value=1, max_value=12), label="length")
    remaining = [length]

    def moves(state):
        if not remaining[0]:
            return None
        remaining[0] -= 1
        # ADAPTIVE, and it is what makes the deep states reachable at all. A
        # uniform draw over thirteen invocations needs eight specific ones in a
        # row to reach a verified candidate, which no feasible budget produces:
        # a review measured exactly that, and a precautionary refusal added to
        # `verify` survived because nothing ever got there. Most draws follow
        # the canonical order, as a real orchestrator does with a NEXT line; the
        # rest are the odd and the inadmissible ones, where the classes live.
        if data.draw(st.integers(0, 3), label="follow"):
            name, value = _canonical_invocation(state)
        else:
            name, value = data.draw(st.sampled_from(_INVOCATIONS), label="step")
        return name, value, data.draw(st.sampled_from(_ANSWERS), label="answer")

    walk(harness, moves)


@pytest.mark.parametrize(
    "sequence",
    [
        # The inadmissible orders decision 3 names by example.
        [("integrate", None, "accepted")],
        [("po", None, "accepted"), ("craft", 1, "accepted")],
        [("po", None, "accepted"), ("verify", None, "accepted")],
        [("design", 1, "accepted")],
        # The admissible odd ones: repeats, and a later value designed first.
        [("po", None, "accepted"), ("po", None, "accepted")],
        [
            ("po", None, "accepted"),
            ("design", 2, "accepted"),
            ("design", 2, "accepted"),
        ],
        [("po", None, "accepted"), ("design", 9, "accepted")],
        # A paid turn whose answer the boundary cannot read, and a rejecting one.
        [("po", None, "malformed")],
        [("po", None, "accepted"), ("design", 1, "rejected")],
        # The whole canonical order to a closed graph, and what a closed graph
        # answers: the same candidate again is already the destination, every
        # other step has no Request left to owe anything, and `po` starts the
        # next one. Written by hand because the generator reaches this depth
        # only on a long run of canonical draws.
        [
            ("po", None, "accepted"),
            ("design", 1, "accepted"),
            ("oracle", 1, "accepted"),
            ("craft", 1, "accepted"),
            ("design", 2, "accepted"),
            ("oracle", 2, "accepted"),
            ("craft", 2, "accepted"),
            ("verify", None, "accepted"),
            ("integrate", None, "accepted"),
            ("integrate", None, "accepted"),
            ("oracle", 1, "accepted"),
            ("state", None, "accepted"),
            ("po", None, "accepted"),
        ],
        # Authored evidence without a craft is a real native execution that
        # refuses as VerificationFailed; it is not missing evidence.
        [
            ("po", None, "accepted"),
            ("design", 1, "accepted"),
            ("oracle", 1, "accepted"),
            ("design", 2, "accepted"),
            ("oracle", 2, "accepted"),
            ("verify", None, "accepted"),
        ],
        # Both values declare the fixture's same oracle/support paths.  An
        # oracle turn for value 1 therefore leaves physical authored evidence
        # for native verify even though value 2 still projects unrecorded.
        # The verifier reaches its actual command and refuses for missing
        # crafts; it must not report missing acceptance evidence by counting
        # role receipts instead of the shared declared paths.
        [
            ("po", None, "accepted"),
            ("design", 2, "accepted"),
            ("design", 1, "accepted"),
            ("oracle", 1, "accepted"),
            ("verify", None, "accepted"),
        ],
        # The target path is shared too.  Once value 1 writes it, native verify
        # can execute the one declared command after value 2 is designed even
        # though value 2 still projects `craft=unrecorded`.
        [
            ("po", None, "accepted"),
            ("design", 1, "accepted"),
            ("oracle", 1, "accepted"),
            ("craft", 1, "accepted"),
            ("design", 2, "accepted"),
            ("verify", None, "accepted"),
        ],
        # A candidate integrated while a LATER value still owes its oracle.
        # The candidate is real and the destination accepts it, but the
        # canonical order names that oracle rather than the integration, so
        # this is the order in which the walk has to have learnt the SHA from
        # the terminal that stated it instead of from a `NEXT` line.
        [
            ("po", None, "accepted"),
            ("design", 1, "accepted"),
            ("oracle", 1, "accepted"),
            ("craft", 1, "accepted"),
            ("design", 2, "accepted"),
            ("verify", None, "accepted"),
            ("integrate", None, "accepted"),
        ],
        # The §7 rewrite, and the rewrite twice, which is L1 over it.
        [("po", None, "accepted"), ("rewrite", None, "accepted")],
        [
            ("po", None, "accepted"),
            ("rewrite", None, "accepted"),
            ("rewrite", None, "accepted"),
        ],
    ],
)
def test_the_named_orders_agree_with_the_model(
    tmp_path_factory, sequence: list[tuple[str, int | None, str]]
) -> None:
    """The two classes, drawn by hand as well, so a shrink cannot hide them."""
    drawn = iter(sequence)
    walk(
        Harness(tmp_path_factory.mktemp("named"), 0),
        lambda _state: next(drawn, None),
    )
