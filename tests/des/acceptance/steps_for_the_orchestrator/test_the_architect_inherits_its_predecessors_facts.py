"""The architect turn inherits its bound predecessors' design facts.

ONE observation, read through the ONE public port the orchestrator has: the real
`des design --repo-root R --value N` command, driven in process, against a real
repository, with the shared fake provider first on `PATH`.  Nothing here imports
a production symbol and nothing here asserts how the projection is built.  What
it reads is the only thing an architect turn ever receives -- the PROMPT the
provider was handed -- which the shared fake records verbatim in its turn log,
and which is therefore a public artefact of the paid turn rather than an
internal of the runner.

WHY THE PROMPT IS PARSED PER LINE AND NEVER SEARCHED.  A prompt is one JSON
value per line, `key: <json>`, which is exactly what the shared fake already
relies on to read a Product Owner's observation back.  Reading it as lines makes
two things measurable that a substring search cannot tell apart: that the
inherited block is the key `inherited` rather than prose that happens to quote a
predecessor, and WHERE it sits among the other facts.

THE FALSIFIERS, stated so a reader can see which arm kills which mistake:

  * an entry carrying a predecessor's `decisions`, or any seventh field, dies on
    the closed key set -- the enumeration is closed, and inheriting hundreds of
    characters of rationale is the cost this value exists to avoid;
  * a projection that reads «every value at a lower position» rather than the
    dependency ancestry dies on the value whose only bound ancestor is its
    immediate one while the ancestor BEFORE that is unbound;
  * `inherited: []` on a value with nothing to inherit dies twice: on the key's
    absence, and on the byte-identity of that prompt with the prompt the same
    command composes from the same root once a predecessor IS bound;
  * a correction turn that composes its prompt on a second path dies on the two
    inherited blocks being compared with each other;
  * a probe directory reported when it does not exist, or not reported when it
    does, dies on the two probe arms.

A NOTE ON THE EMPTY AUTHORITY LOCATOR.  The bound facts these scenarios inherit
are provider-authored, and provider-authored facts carry no configured document
section -- `DesignFacts.authority_locator` retains the empty value, as the shared
fake and the port's own dataclass both state.  So the inherited `authority` is
asserted to be exactly the empty string the predecessor was bound with: this is
the byte the handover carries, which is what «rendered from the handover's bound
facts and nothing inferred» means.  An entry whose `authority` were derived from
the document instead could not answer the empty string here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:  # standalone-executable form
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    accepted_values,
    base_repository,
    block,
    hermetic_environment,
    observation,
)


REQUEST = "one Request whose architect turns inherit their bound predecessors"
FINDING = "the reviewer's own prose, which the correction turn carries verbatim"
ARCHITECT = "nw-solution-architect"

#: The keys ONE inherited entry may carry besides its optional probe path: the
#: six enumerated fields, with the oracle-and-verification vector spelled as the
#: two keys the architect's own output grammar uses.  `decisions` and
#: `obligations` are deliberately not among them.
ENTRY_KEYS = frozenset(
    {
        "observation",
        "authority",
        "targets",
        "paradigm",
        "acceptance_supports",
        "oracle",
        "verification",
        "oracle_verification_index",
    }
)


def value_facts(label: str) -> dict:
    """One value's typed design facts, distinct per value in every path."""
    oracle = f"tests/acceptance/test_{label}.py"
    return {
        "targets": [{"path": f"src/product/{label}.py", "decision": "CREATE_NEW"}],
        "paradigm": "object_oriented",
        "decisions": [f"one opaque semantic decision, stated for the value {label}"],
        "oracle": oracle,
        "acceptance_supports": [f"tests/acceptance/support_{label}.py"],
        "verification": [[sys.executable, "-m", "pytest", oracle]],
        "oracle_verification_index": 0,
    }


def inherited_entry(label: str) -> dict:
    """Exactly what a bound predecessor contributes, and nothing more."""
    facts = value_facts(label)
    return {
        "observation": observation(label),
        # Provider-authored facts name no configured section, so the locator the
        # handover bound -- and therefore the one inherited -- is empty.
        "authority": "",
        "targets": facts["targets"],
        "paradigm": facts["paradigm"],
        "acceptance_supports": facts["acceptance_supports"],
        "oracle": facts["oracle"],
        "verification": facts["verification"],
        "oracle_verification_index": facts["oracle_verification_index"],
    }


def design_answer(label: str) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": f"bound the typed facts for the value {label}",
            "design_facts": value_facts(label),
        }
    }


class Lane:
    """One real repository and one fake provider, driven through the CLI edge.

    Built here rather than taken from the `step` fixture because one scenario
    needs TWO repositories at once -- a first value and a later value, each with
    no bound predecessor, are two different worlds -- and a single fixture root
    can only ever be one of them.  The construction is the corpus's own --
    `base_repository`, the shared fake, the hermetic environment -- so every
    world is the same surface.
    """

    def __init__(self, home: Path, name: str) -> None:
        self.root = base_repository(home / f"root-{name}")
        self.log = home / f"log-{name}.json"
        self._bin = home / f"bin-{name}"
        self._results = home / f"results-{name}.json"
        self._counter = home / f"counter-{name}"
        self._claude = home / f"claude-{name}"

    def run(self, argv: list[str], answers: list[dict], stdin: str = ""):
        self._results.write_text(json.dumps(answers))
        self._counter.unlink(missing_ok=True)
        return run_cli_in_process(
            argv,
            cwd=self.root,
            env=hermetic_environment(
                fake_provider.environment(
                    self.root,
                    launcher_dir=self._bin,
                    results=self._results,
                    log=self.log,
                    counter=self._counter,
                    package_parent=PACKAGE_PARENT,
                ),
                self._claude,
            ),
            stdin_text=stdin,
            catch_all=True,
        )

    def decompose(self, *labels: str) -> None:
        code, out, err = self.run(
            ["po", "--project", "--repo-root", str(self.root)],
            [accepted_values(*labels)],
            REQUEST,
        )
        assert code == 0, out + err

    def design(
        self, position: int, label: str, finding: str | None = None
    ) -> dict[str, str]:
        argv = ["design", "--repo-root", str(self.root), "--value", str(position)]
        stdin = ""
        if finding is not None:
            argv += ["--finding", "-"]
            stdin = finding
        code, out, err = self.run(argv, [design_answer(label)], stdin)
        assert code == 0, out + err
        return block(out, err)

    def turns(self) -> list[dict]:
        return json.loads(self.log.read_text()) if self.log.exists() else []

    def last_architect_prompt(self) -> str:
        rows = self.turns()
        assert rows, "no turn was bought at all"
        assert rows[-1]["agent"] == ARCHITECT, rows[-1]["agent"]
        return rows[-1]["prompt"]


def facts_of(prompt: str) -> dict[str, object]:
    """The prompt as the typed facts it carries, one JSON value per line."""
    found: dict[str, object] = {}
    for line in prompt.splitlines():
        label, separator, rest = line.partition(": ")
        if separator:
            found.setdefault(label, json.loads(rest))
    return found


def keys_of(prompt: str) -> list[str]:
    """Every fact key the prompt states, in the order the architect reads them."""
    return [line.partition(": ")[0] for line in prompt.splitlines() if ": " in line]


def entries_of(prompt: str) -> list[dict]:
    inherited = facts_of(prompt)["inherited"]
    assert isinstance(inherited, list), inherited
    return inherited


def enumerated(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if key in ENTRY_KEYS}


def probe_paths(entry: dict) -> list[str]:
    """Whatever the entry carries BESIDES the closed enumeration.

    Read by exclusion rather than by a key name so the assertion measures the
    observation -- the predecessor's probe evidence directory is reported, and
    nothing else is -- without this oracle inventing a spelling for it.
    """
    return [
        str(value).rstrip("/") for key, value in entry.items() if key not in ENTRY_KEYS
    ]


def without_inherited(prompt: str) -> str:
    return "\n".join(
        line for line in prompt.splitlines() if not line.startswith("inherited: ")
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path


def test_the_bound_predecessor_is_inherited_whole_and_costs_one_turn(
    home: Path,
) -> None:
    """The six enumerated fields, verbatim from the handover, and nothing more."""
    lane = Lane(home, "whole")
    lane.decompose("a", "b")
    lane.design(1, "a")
    spent = len(lane.turns())
    rows = lane.design(2, "b")

    entries = entries_of(lane.last_architect_prompt())
    assert entries == [inherited_entry("a")]

    # Neither the terminal nor the cost moves: one architect turn, as today.
    assert rows["TURNS-BOUGHT"] == "1", rows
    assert len(lane.turns()) - spent == 1
    assert [row["agent"] for row in lane.turns()[spent:]] == [ARCHITECT]


def test_the_whole_bound_ancestry_is_inherited_in_canonical_order(
    home: Path,
) -> None:
    """Transitive, and in the handover's order -- never just the nearest one."""
    lane = Lane(home, "ancestry")
    lane.decompose("a", "b", "c")
    lane.design(1, "a")
    lane.design(2, "b")
    lane.design(3, "c")

    assert entries_of(lane.last_architect_prompt()) == [
        inherited_entry("a"),
        inherited_entry("b"),
    ]


def test_an_unbound_predecessor_contributes_nothing(home: Path) -> None:
    """A gap in the ancestry is skipped; the bound ancestor still arrives.

    This is the arm that tells the dependency ancestry apart from «every value
    at a lower position»: value 1 is never designed, so a projection that
    rendered positions rather than BOUND facts would have to invent bytes for it
    or refuse.
    """
    lane = Lane(home, "gap")
    lane.decompose("a", "b", "c")
    lane.design(2, "b")
    lane.design(3, "c")

    assert entries_of(lane.last_architect_prompt()) == [inherited_entry("b")]


def test_a_value_with_no_bound_predecessor_carries_no_inherited_key(
    home: Path,
) -> None:
    """Absence is the representation of nothing to inherit -- never an empty list."""
    first = Lane(home, "first")
    first.decompose("a", "b")
    first.design(1, "a")
    assert "inherited" not in facts_of(first.last_architect_prompt())

    later = Lane(home, "later")
    later.decompose("a", "b")
    later.design(2, "b")
    assert "inherited" not in facts_of(later.last_architect_prompt())


def test_the_prompt_is_todays_prompt_apart_from_the_inherited_block(
    home: Path,
) -> None:
    """Byte-identity, measured against the same command in ONE repository.

    The same root, the same Request, the same decomposition, the same value
    under design, bought twice: once while its predecessor is unbound, and once
    after that predecessor has been bound.  The ONLY difference between the two
    worlds is the bound predecessor.  Drop the inherited line and the two
    prompts must be the same bytes: nothing else about what an architect
    receives is allowed to move for this value.

    ONE root rather than two, deliberately.  Every role prompt states its
    `repository_root` as an absolute path -- a fact of the runner, not of any
    value -- so two distinct repositories could never answer this question: the
    two prompts would differ on that line whatever the projection did.  Held
    within a single root, the comparison measures exactly the claim.

    TWO CORRECTION TURNS rather than two plain ones, deliberately.  A value
    whose design is already bound buys NO architect turn on a plain
    `des design --value N`; only `--finding -` buys a turn for it.  Since the
    comparison needs the SAME value designed twice in the SAME root, both
    measured prompts are correction turns carrying the same finding -- and the
    Request states the correction turn inherits identically, so this reads the
    claim exactly.
    """
    lane = Lane(home, "identity")
    lane.decompose("a", "b")

    lane.design(2, "b")
    lane.design(2, "b", finding=FINDING)
    unbound_prompt = lane.last_architect_prompt()
    assert "inherited" not in facts_of(unbound_prompt), unbound_prompt

    lane.design(1, "a")
    lane.design(2, "b", finding=FINDING)

    theirs = lane.last_architect_prompt()
    assert keys_of(theirs).count("inherited") == 1, theirs
    assert without_inherited(theirs) == unbound_prompt


def test_the_inherited_block_sits_directly_after_the_decomposition(
    home: Path,
) -> None:
    """`observation` stays first; the inherited block follows `decomposition`."""
    lane = Lane(home, "order")
    lane.decompose("a", "b")
    lane.design(1, "a")
    lane.design(2, "b")

    keys = keys_of(lane.last_architect_prompt())
    assert keys[0] == "observation", keys
    assert keys.index("inherited") == keys.index("decomposition") + 1, keys


def test_a_correction_turn_inherits_identically(home: Path) -> None:
    """`--finding -` is the same prompt composition, not a second one."""
    lane = Lane(home, "correction")
    lane.decompose("a", "b")
    lane.design(1, "a")
    lane.design(2, "b")
    ordinary = entries_of(lane.last_architect_prompt())

    lane.design(2, "b", finding=FINDING)
    corrected = lane.last_architect_prompt()

    assert entries_of(corrected) == ordinary == [inherited_entry("a")]
    assert facts_of(corrected)["finding"] == FINDING
    keys = keys_of(corrected)
    # The inherited block precedes every current-value typed fact, so the flat
    # correction keys stay unambiguously about THIS value.
    assert keys.index("inherited") == keys.index("decomposition") + 1, keys
    assert keys.index("inherited") < keys.index("finding"), keys


def test_an_existing_probe_directory_is_reported_repository_relative(
    home: Path,
) -> None:
    """The predecessor's probe evidence directory, named by its canonical position."""
    lane = Lane(home, "probe")
    lane.decompose("a", "b")
    lane.design(1, "a")
    (lane.root / ".nwave" / "des" / "probe-value-1").mkdir(parents=True)
    lane.design(2, "b")

    (entry,) = entries_of(lane.last_architect_prompt())
    assert enumerated(entry) == inherited_entry("a")
    assert probe_paths(entry) == [".nwave/des/probe-value-1"]


def test_an_absent_probe_directory_is_not_reported_at_all(home: Path) -> None:
    """Nothing is claimed about a directory that does not exist."""
    lane = Lane(home, "no-probe")
    lane.decompose("a", "b")
    lane.design(1, "a")
    lane.design(2, "b")

    (entry,) = entries_of(lane.last_architect_prompt())
    assert probe_paths(entry) == []
    assert set(entry) == ENTRY_KEYS


if __name__ == "__main__":  # the observation is EXECUTED, not merely defined
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
