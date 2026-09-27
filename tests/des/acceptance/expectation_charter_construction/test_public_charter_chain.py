"""Public process oracle for one source-bound expectation charter.

The provider executable supplies only the declared qualitative answer.  Its
turn log measures issuance; it cannot prove real model reasoning or isolation.
The caller's separate paid-model smoke owns those observations.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


# Direct execution from the repository root is the DESIGN verification entry.
REPOSITORY = Path(__file__).resolve().parents[4]
for import_root in (REPOSITORY, REPOSITORY / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    accepted_values,
    asked,
    base_repository,
    block,
    git,
    hermetic_environment,
    observation,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_host_review_examine_artifacts import (
    _reseal,
)


INTENT = "A maintainer can see the current delivery state."
RECIPE = "des state --repo-root /fixture"
EXPLORATION = "Run the supplied public command from a clean checkout."
POSITIVE = "The command reports the current delivery state."
NEGATIVE = "The command must not report success when no delivery completed."
CHARTER = {
    "intent": INTENT,
    "exploration": EXPLORATION,
    "positive_observations": [POSITIVE],
    "negative_observation": NEGATIVE,
}
CHARTER_ANSWER = {
    "structured_output": {
        "outcome": "accepted",
        "diagnostic": "The supplied value supports a charter.",
        "charter": CHARTER,
    }
}
CHARTER_DIR = Path("docs/product/expectations/_project")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_sha(value: int, stored_observation: str) -> str:
    source = {
        "observation": stored_observation,
        "scope": {"feature_id": None, "id": None, "kind": "project", "slice_id": None},
        "value": value,
    }
    return _sha(
        json.dumps(
            source, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    )


def _canonical(value: int, stored_observation: str, recipe: str = RECIPE) -> bytes:
    return (
        "## Intent\n\n"
        f"Value: {value}\n"
        f"Source SHA-256: {_source_sha(value, stored_observation)}\n"
        f"{INTENT}\n\n"
        "## Preconditions\n\n"
        f"{recipe}\n\n"
        "## Charter\n\n"
        f"{EXPLORATION}\n\n"
        "## Expected observations (oracle)\n\n"
        f"- {POSITIVE}\n"
        f"- Negative: {NEGATIVE}\n\n"
        "## Session log (append-only)\n\n"
        "| date | examiner | verdict | observations |\n"
        "|------|----------|---------|--------------|\n"
    ).encode()


def _input(stored_observation: str, **changes: object) -> str:
    payload = {
        "schema_version": 1,
        "intent": INTENT,
        "observation": stored_observation,
        "public_start_recipe": RECIPE,
    }
    payload.update(changes)
    return json.dumps(payload, ensure_ascii=False)


class PublicProject:
    """A real Git checkout and real des subprocess with one controlled provider."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.root = base_repository(workspace / "root")
        self.turns = workspace / "turns.json"
        self.results = workspace / "results.json"
        self.counter = workspace / "results-consumed"
        self.launchers = workspace / "bin"
        self.claude_dir = workspace / "claude-config"
        self.environment = hermetic_environment(
            fake_provider.environment(
                self.root,
                launcher_dir=self.launchers,
                results=self.results,
                log=self.turns,
                counter=self.counter,
                package_parent=PACKAGE_PARENT,
            ),
            self.claude_dir,
        )
        # The installed charter knowledge belongs to the provider role, not to
        # the selected product checkout.  The production loader resolves it.
        self.environment.pop("ANTHROPIC_API_KEY", None)
        self.environment.pop("OPENAI_API_KEY", None)

    def run(self, *args: str, answers: list[dict] | None = None, stdin: str = ""):
        self.results.write_text(json.dumps(answers or []), encoding="utf-8")
        self.counter.unlink(missing_ok=True)
        result = subprocess.run(
            [sys.executable, "-m", "des", *args],
            cwd=self.root,
            env=self.environment,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr

    def decompose(self, *labels: str) -> None:
        code, out, err = self.run(
            "po",
            "--project",
            "--repo-root",
            str(self.root),
            answers=[accepted_values(*labels)],
            stdin="A maintainer asks for visible delivery state.",
        )
        assert code == 0, (
            f"WHAT: fixture decomposition exited {code}: {out + err}\n"
            "WHY: charter RED requires a persisted value, not broken setup.\n"
            "HOW: restore the existing des po fixture path."
        )

    def construct(
        self,
        value: int = 1,
        supplied: str | None = None,
        *,
        input_path: str | None = None,
    ):
        if supplied is not None:
            path = self.workspace / f"charter-input-{value}.json"
            path.write_text(supplied, encoding="utf-8")
            input_path = str(path)
        argv = [
            "po",
            "--repo-root",
            str(self.root),
            "--project",
            "--charter",
            "--value",
            str(value),
        ]
        if input_path is not None:
            argv.extend(["--input", input_path])
        return self.run(*argv, answers=[CHARTER_ANSWER])

    def member(self, value: int = 1) -> Path:
        return self.root / CHARTER_DIR / f"value-{value}.md"


@pytest.fixture
def project(tmp_path: Path) -> PublicProject:
    return PublicProject(tmp_path)


def _assert_success(result: tuple[int, str, str], action: str) -> None:
    code, out, err = result
    assert code == 0, (
        f"WHAT: {action} exited {code}: {out + err}\n"
        "WHY: the selected value needs a public charter artifact.\n"
        "HOW: make des po --charter complete the declared selected-value operation."
    )


def _malformed(**changes: object) -> dict:
    """One provider envelope whose charter-task shape is broken.

    Provider capability refusal (`resolve_declared_capability` returning
    `ClaimRegister.UNKNOWN`/no `spec_path`/no `declared_tools`) and transport
    timeout/failure reporting are the SAME mechanics
    `tests/des/unit/adapters/driven/task_invocation/test_claude_code_task_adapter.py`
    and `test_codex_task_adapter.py` already exercise for every role turn,
    charter included -- they are cited here, not re-proved. What is
    charter-specific, and therefore belongs in THIS oracle, is the accepted
    charter payload's OWN closed shape: exactly `intent`, `exploration`,
    `positive_observations`, `negative_observation`, no more and no fewer.
    """
    charter = dict(CHARTER)
    charter.update(changes.pop("charter_changes", {}))
    for key in changes.pop("charter_removes", ()):
        charter.pop(key, None)
    payload = {
        "outcome": "accepted",
        "diagnostic": "The supplied value supports a charter.",
        "charter": charter,
    }
    payload.update(changes)
    return {"structured_output": payload}


def _assert_refusal(result: tuple[int, str, str], *terms: str) -> None:
    code, out, err = result
    terminal = out + err
    assert code != 0 and all(term in terminal for term in terms), (
        f"WHAT: malformed or incomplete input returned {code}: {terminal!r}; "
        f"expected a refusal naming {terms!r}.\n"
        "WHY: no charter may be fabricated from an unbound input.\n"
        "HOW: validate before provider issuance and name the corrected input."
    )


def test_a_maintainer_receives_a_source_bound_charter_and_valid_reuse_keeps_its_log(
    project: PublicProject,
) -> None:
    """@walking_skeleton @real-io: selected public input yields canonical value."""
    project.decompose("A")
    stored = observation("A")
    _assert_success(project.construct(supplied=_input(stored)), "charter construction")
    member = project.member()
    assert member.read_bytes() == _canonical(1, stored), (
        "WHAT: the public charter bytes differ from the closed five-section contract.\n"
        "WHY: the recipe, source binding, accepted facts and empty session log are user value.\n"
        "HOW: construct the canonical file from stored observation, CLI recipe and accepted PO facts."
    )
    assert asked(project.turns) == ["nw-product-owner", "nw-product-owner"], (
        "WHAT: construction did not buy exactly one new PO turn.\n"
        "WHY: charter facts require one independent contribution.\n"
        "HOW: invoke the configured PO once for the missing selected charter."
    )
    charter_turn = json.loads(project.turns.read_text())[-1]
    assert all(fact in charter_turn["prompt"] for fact in (stored, INTENT, RECIPE)), (
        "WHAT: the charter PO turn did not receive all three declared product facts.\n"
        "WHY: the qualitative answer must be grounded in the stored value and caller input.\n"
        "HOW: supply stored observation, intent and exact decoded public recipe to the PO."
    )
    charter_argv = charter_turn["argv"]
    assert "--allowedTools" in charter_argv, (
        "WHAT: the charter PO turn declared no effective tool ceiling.\n"
        "WHY: the isolation contract must exclude every source-reaching tool, not merely "
        "omit source facts from the prompt.\n"
        "HOW: project the charter semantic task's launcher argv with an explicit "
        "--allowedTools ceiling."
    )
    allowed_tools = charter_argv[charter_argv.index("--allowedTools") + 1].split(",")
    assert allowed_tools == ["StructuredOutput"], (
        f"WHAT: the charter PO turn's effective tool set was {allowed_tools}, not "
        "structured-reply-only.\n"
        "WHY: the charter task must never reach source, tests, or the filesystem.\n"
        "HOW: cap the charter semantic task's declared tools to the structured-output "
        "channel only."
    )
    assert charter_turn["cwd"] != str(project.root), (
        "WHAT: the charter PO turn executed inside the selected repository root.\n"
        "WHY: the isolation contract requires a private working directory outside the "
        "repository and its ancestor project documents.\n"
        "HOW: spawn the charter turn from a directory that is not the selected repository "
        "root."
    )
    filled = (
        member.read_bytes()
        + b"| 2026-09-26 | examiner | ACCEPTED | Public state was visible. |\n"
    )
    member.write_bytes(filled)
    before_turns = asked(project.turns)
    malformed = project.workspace / "malformed-reuse-input.json"
    malformed.write_text("{", encoding="utf-8")
    _assert_success(
        project.construct(input_path=str(malformed)), "selected valid charter reuse"
    )
    assert member.read_bytes() == filled and asked(project.turns) == before_turns, (
        "WHAT: valid reuse changed an append-only log or bought a PO turn.\n"
        "WHY: a selected valid charter is reusable without reading --input.\n"
        "HOW: validate the namespace and reuse the selected bytes before opening input."
    )


def test_incomplete_or_unbound_value_facts_never_make_a_charter(
    project: PublicProject,
) -> None:
    """@real-io: omission clarifies and malformed facts refuse before a turn."""
    project.decompose("A")
    stored = observation("A")
    cases = [
        (
            None,
            ("CLARIFICATION_NEEDED", "intent", "observation", "public_start_recipe"),
        ),
        (
            json.dumps({"schema_version": 1, "observation": stored}),
            ("CLARIFICATION_NEEDED", "intent", "public_start_recipe"),
        ),
        (
            _input(stored, intent=" ", public_start_recipe="\t"),
            ("CLARIFICATION_NEEDED", "intent", "public_start_recipe"),
        ),
        (_input(stored, intent=42), ("intent", "string")),
        (
            _input("A different persisted observation cannot be substituted."),
            ("observation",),
        ),
        (_input(stored, extra="unadmitted"), ("extra",)),
        ('{"schema_version":1,"schema_version":1,"intent":"x"}', ("schema_version",)),
    ]
    for supplied, terms in cases:
        before = asked(project.turns)
        _assert_refusal(project.construct(supplied=supplied), *terms)
        assert not project.member().exists() and asked(project.turns) == before, (
            "WHAT: refusal wrote a charter or issued a model turn.\n"
            "WHY: missing or malformed facts cannot become a value oracle.\n"
            "HOW: stop construction before provider invocation and whole-file publication."
        )


def test_malformed_provider_envelope_never_becomes_a_charter(
    project: PublicProject,
) -> None:
    """@real-io: an accepted answer with a broken charter shape is refused."""
    project.decompose("A")
    stored = observation("A")
    cases = [
        _malformed(charter_removes=["exploration"]),
        _malformed(charter_changes={"extra": "unadmitted"}),
        _malformed(charter_changes={"positive_observations": "not-an-array"}),
        _malformed(charter_changes={"positive_observations": []}),
        {
            "structured_output": {
                "outcome": "rejected",
                "diagnostic": "broken",
                "charter": dict(CHARTER),
            }
        },
    ]
    for answer in cases:
        before = asked(project.turns)
        path = project.workspace / "envelope-input.json"
        path.write_text(_input(stored), encoding="utf-8")
        result = project.run(
            "po",
            "--repo-root",
            str(project.root),
            "--project",
            "--charter",
            "--value",
            "1",
            "--input",
            str(path),
            answers=[answer],
        )
        code, out, err = result
        terminal = out + err
        assert code != 0 and "ModelEnvelopeUnavailable" in terminal, (
            f"WHAT: a broken accepted-charter payload returned {code}: {terminal!r}, "
            "not a named ModelEnvelopeUnavailable refusal.\n"
            "WHY: an accepted outcome with a missing, extra, or wrong-typed charter "
            "field is a malformed provider envelope, not a valid charter.\n"
            "HOW: validate the closed accepted-charter shape before writing any "
            "canonical bytes."
        )
        assert not project.member().exists(), (
            "WHAT: a malformed provider envelope produced a canonical charter file.\n"
            "WHY: only a payload matching the closed accepted-charter schema may be "
            "published.\n"
            "HOW: reject the envelope before whole-file publication."
        )
        # The turn WAS bought (this is a bad answer, not a missing/unbound input);
        # exactly one new row proves no silent retry hid the malformed reply.
        assert len(asked(project.turns)) == len(before) + 1, (
            "WHAT: a malformed provider envelope did not leave exactly one new turn.\n"
            "WHY: the malformed answer must be observed, not silently retried or "
            "swallowed.\n"
            "HOW: record the one PO turn that returned the broken envelope."
        )


def test_provider_transport_failure_never_fabricates_a_charter(
    project: PublicProject,
) -> None:
    """@real-io: a retry-safe transport failure surfaces without a charter.

    The transport-failure envelope itself (`is_error`, `terminal_reason`) is the
    same shared shape every adapter unit suite already proves the adapters
    translate correctly; this observes only that the charter task, on that
    translated failure, still writes nothing and fabricates no charter --
    the charter-specific half of the obligation.
    """
    project.decompose("A", "B")
    stored_a = observation("A")
    stored_b = observation("B")
    _assert_success(project.construct(1, _input(stored_a)), "value 1 charter")
    before = asked(project.turns)
    path = project.workspace / "transport-failure-input.json"
    path.write_text(_input(stored_b), encoding="utf-8")
    result = project.run(
        "po",
        "--repo-root",
        str(project.root),
        "--project",
        "--charter",
        "--value",
        "2",
        "--input",
        str(path),
        answers=[{"retry_safe": True, "exit": 1}],
    )
    code, out, err = result
    terminal = out + err
    assert code != 0 and not project.member(2).exists(), (
        f"WHAT: a retry-safe transport failure returned {code} and "
        f"{'wrote' if project.member(2).exists() else 'did not write'} a charter: "
        f"{terminal!r}.\n"
        "WHY: a provider transport failure must be reported honestly, never "
        "papered over with a fabricated charter.\n"
        "HOW: propagate the adapter's own translated failure and write nothing."
    )
    assert len(asked(project.turns)) == len(before) + 1, (
        "WHAT: the transport failure did not leave exactly one new turn beyond the "
        "prior successful construction.\n"
        "WHY: a failure is observed once, not silently retried.\n"
        "HOW: record the single failing turn."
    )


def test_stale_source_fingerprint_blocks_reuse(project: PublicProject) -> None:
    """@real-io: a persisted observation that drifted after minting is stale."""
    project.decompose("A")
    stored = observation("A")
    _assert_success(project.construct(supplied=_input(stored)), "charter construction")
    handover = project.root / ".nwave" / "des" / "handover.json"
    persisted = json.loads(handover.read_text(encoding="utf-8"))
    persisted["values"][0]["observation"] = "a different, drifted persisted observation"
    # The persisted handover is a CAS artifact: `read_handover` requires the
    # exact canonical encoding (`ensure_ascii=False`, no trailing whitespace,
    # `separators=(",", ":")`), not merely valid JSON. Re-serializing with
    # `json.dumps` defaults inserts spaces after `:`/`,` and would be refused
    # as `HandoverMalformed: handover bytes are not canonical` before the
    # source-fingerprint check this scenario targets ever runs.
    handover.write_text(
        json.dumps(persisted, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    before = asked(project.turns)
    _assert_refusal(project.construct(), "stale", "value-1.md")
    assert asked(
        project.turns
    ) == before and project.member().read_bytes() == _canonical(1, stored), (
        "WHAT: a drifted persisted observation was silently reused or bought a "
        "turn.\n"
        "WHY: the embedded source fingerprint no longer matches the persisted "
        "value it claims to bind; reuse of stale bytes must be refused, not "
        "issued or silently accepted.\n"
        "HOW: recompute the source fingerprint from the current persisted value "
        "and refuse the mismatch by name before reuse or issuance."
    )


def test_valid_sibling_is_preserved_but_cannot_stand_for_the_selected_value(
    project: PublicProject,
) -> None:
    """@real-io: all assigned values have distinct canonical members."""
    project.decompose("A", "B")
    _assert_success(project.construct(2, _input(observation("B"))), "value 2 charter")
    sibling = project.member(2).read_bytes()
    turns = asked(project.turns)
    _assert_success(project.construct(1, _input(observation("A"))), "value 1 charter")
    assert project.member(1).read_bytes() == _canonical(1, observation("A")), (
        "WHAT: selected value 1 has no own source-bound charter.\n"
        "WHY: a valid value 2 sibling cannot cover value 1.\n"
        "HOW: construct only the missing selected member."
    )
    assert (
        project.member(2).read_bytes() == sibling
        and len(asked(project.turns)) == len(turns) + 1
    ), (
        "WHAT: constructing value 1 altered its sibling or bought the wrong turn count.\n"
        "WHY: one missing value needs one PO contribution while valid siblings persist.\n"
        "HOW: preserve other canonical namespace members during publication."
    )
    (project.root / CHARTER_DIR / "value-9.md").write_text("stale charter\n")
    before = asked(project.turns)
    _assert_refusal(project.construct(1, _input(observation("A"))), "value-9.md")
    assert (
        asked(project.turns) == before and project.member(2).read_bytes() == sibling
    ), (
        "WHAT: an invalid namespace caused issuance or changed valid bytes.\n"
        "WHY: every direct member must be classified before selected reuse.\n"
        "HOW: refuse the whole invalid namespace with the offending path."
    )


_WITHHELD_FIELD = {
    "withheld": True,
    "reason": (
        "source-blind examiner: native verification detail may reveal oracle "
        "identifiers or source"
    ),
}


def _craft_value(
    project: PublicProject, value: int, oracle: str, support: str, target: str
) -> None:
    """Design, author and settle one additional value with its own files."""
    root, step = project.root, project.run
    design_facts = {
        "targets": [{"path": target, "decision": "CREATE_NEW"}],
        "paradigm": "object_oriented",
        "decisions": [f"one observable value at position {value}"],
        "oracle": oracle,
        "acceptance_supports": [support],
        "verification": [[sys.executable, "-m", "pytest", oracle]],
        "oracle_verification_index": 0,
    }
    assert (
        step(
            "design",
            "--repo-root",
            str(root),
            "--value",
            str(value),
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "bound the typed facts",
                        "design_facts": design_facts,
                    }
                }
            ],
        )[0]
        == 0
    )
    module = target[:-3]
    red_oracle = (
        "import pathlib\nimport sys\n\n\ndef test_value():\n"
        "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
        f"    from {module} import VALUE\n\n    assert VALUE == {value}\n"
    )
    assert (
        step(
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            str(value),
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored a red oracle",
                    },
                    "writes": {oracle: red_oracle, support: "MARKER = 1\n"},
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
            str(value),
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value",
                    },
                    "writes": {target: f"VALUE = {value}\n"},
                }
            ],
        )[0]
        == 0
    )


def _commit_charter(root: Path, value: int) -> None:
    """Commit one written charter into the base tree the next candidate reads.

    A candidate's tree starts from `git read-tree <base>`; only design-declared
    target/oracle/support paths are then explicitly re-staged (`_owned_with_
    authority`). An expectation-charter path is none of those -- it reaches the
    candidate only by already being part of the committed base, exactly as a
    human/CI caller commits `des po --charter`'s written file before the next
    `des verify`, same as any other artifact `des` writes to disk without
    itself owning a git commit.
    """
    path = str(CHARTER_DIR / f"value-{value}.md")
    git(root, "add", "--", path)
    git(root, "commit", "-qm", f"expectation charter for value {value}")


def test_actual_examiner_input_contains_each_candidates_own_bound_charter(
    project: PublicProject,
    tmp_path: Path,
) -> None:
    """@real-io: two distinct candidates each receive their own complete charter.

    `des verify` requires every value bound to its own single candidate to be
    settled before that candidate is verifiable -- a value never verifies
    "unless all of them are". The two candidates are therefore minted from two
    independent, fully-prepared whole-Request fixture repositories: candidate 1
    is a one-value project (value 1 alone, fully designed/oracled/crafted/
    chartered before its own verify), and candidate 2 is a two-value project
    (values 1 and 2, both fully settled before its own verify) -- never a
    single shared graph verified mid-flight with an unbound sibling.
    """
    project1 = project
    project1.decompose("A")
    stored_a = observation("A")

    _craft_value(
        project1,
        1,
        "tests/acceptance/test_value_1.py",
        "tests/acceptance/support_1.py",
        "product_value_1.py",
    )
    _assert_success(project1.construct(1, _input(stored_a)), "value 1 charter")
    charter1_bytes = project1.member(1).read_bytes()
    charter1_turn = json.loads(project1.turns.read_text())[-1]
    forbidden = (
        "product_value_1.py",
        "tests/acceptance/test_value_1.py",
        "tests/acceptance/support_1.py",
        "VALUE = 1",
    )
    assert not any(marker in charter1_turn["prompt"] for marker in forbidden), (
        "WHAT: the charter PO turn's prompt carries a settled value's own "
        "target/oracle/support path or implementation content.\n"
        "WHY: the charter task's only product inputs are the stored observation, "
        "intent and recipe -- never source, test, or diff material, even for an "
        "already-crafted value.\n"
        "HOW: build the charter prompt from stored facts only, never from the "
        "candidate's own design targets, oracle, or implementation."
    )
    _commit_charter(project1.root, 1)
    verified1 = project1.run("verify", "--repo-root", str(project1.root))
    _assert_success(verified1, "candidate 1 verification")
    candidate1 = block(verified1[1], verified1[2])["CANDIDATE"]

    project2 = PublicProject(tmp_path / "project2")
    project2.decompose("A", "B")
    stored_b = observation("B")

    _craft_value(
        project2,
        1,
        "tests/acceptance/test_value_1.py",
        "tests/acceptance/support_1.py",
        "product_value_1.py",
    )
    _assert_success(
        project2.construct(1, _input(stored_a)), "value 1 charter (project 2)"
    )
    _commit_charter(project2.root, 1)
    _craft_value(
        project2,
        2,
        "tests/acceptance/test_value_2.py",
        "tests/acceptance/support_2.py",
        "product_value_2.py",
    )
    _assert_success(project2.construct(2, _input(stored_b)), "value 2 charter")
    charter2_bytes = project2.member(2).read_bytes()
    _commit_charter(project2.root, 2)
    verified2 = project2.run("verify", "--repo-root", str(project2.root))
    _assert_success(verified2, "candidate 2 verification")
    candidate2 = block(verified2[1], verified2[2])["CANDIDATE"]

    assert candidate1 != candidate2, (
        "WHAT: the two crafted increments resolved to the same candidate identity.\n"
        "WHY: two distinct bound-charter observations require two distinct candidates.\n"
        "HOW: verify after each crafted increment to mint its own candidate."
    )

    entry1 = {
        "value": 1,
        "path": str(CHARTER_DIR / "value-1.md"),
        "content_sha256": _sha(charter1_bytes),
        "source_sha256": _source_sha(1, stored_a),
        "intent": INTENT,
        "public_start_recipe": RECIPE,
        "exploration": EXPLORATION,
        "positive_observations": [POSITIVE],
        "negative_observation": NEGATIVE,
    }
    entry2 = {
        "value": 2,
        "path": str(CHARTER_DIR / "value-2.md"),
        "content_sha256": _sha(charter2_bytes),
        "source_sha256": _source_sha(2, stored_b),
        "intent": INTENT,
        "public_start_recipe": RECIPE,
        "exploration": EXPLORATION,
        "positive_observations": [POSITIVE],
        "negative_observation": NEGATIVE,
    }

    def prepare(proj: PublicProject, candidate: str) -> tuple[dict, str]:
        prepared = proj.run(
            "prepare-role",
            "--repo-root",
            str(proj.root),
            "--role",
            "examiner",
            "--candidate",
            candidate,
        )
        _assert_success(prepared, f"examiner preparation for {candidate}")
        fields = block(prepared[1], prepared[2])
        packet_path = proj.root / fields["INPUT"]
        return json.loads(packet_path.read_bytes()), fields["INPUT"]

    packet1, input1 = prepare(project1, candidate1)
    packet2, input2 = prepare(project2, candidate2)

    assert packet1.get("expectation_charters") == [entry1], (
        "WHAT: candidate 1's examiner input is not exactly its own single bound charter.\n"
        "WHY: a candidate with one settled value may show only that value's charter, "
        "neither truncated nor borrowed from another candidate.\n"
        "HOW: project only the charters validated for this candidate's own tree."
    )
    assert packet2.get("expectation_charters") == [entry1, entry2], (
        "WHAT: candidate 2's examiner input does not contain both complete, correctly "
        "ordered charters.\n"
        "WHY: a later candidate must show every settled charter bound to its own tree, "
        "none missing and none truncated.\n"
        "HOW: project every validated candidate charter for the requested candidate."
    )
    assert packet1.get("expectation_charters") != packet2.get("expectation_charters"), (
        "WHAT: both candidates produced the identical charter projection.\n"
        "WHY: candidate-bound projection must differ when the settled value set differs.\n"
        "HOW: bind the projection to the requested candidate's own tree, not a cached one."
    )

    # Finding 1: existing EXAMINE evidence keys must retain their actual, known
    # content -- not merely remain present while emptied or corrupted.
    for packet in (packet1, packet2):
        assert packet.get("public_observations") is None, (
            "WHAT: public_observations carries a value though no --observations packet "
            "was supplied.\n"
            "WHY: this field's known absence must be preserved exactly, not replaced.\n"
            "HOW: keep public_observations None when no observations packet is bound."
        )
        assert packet.get("observations_provenance") is None, (
            "WHAT: observations_provenance carries a value though no --observations "
            "packet was supplied.\n"
            "WHY: this field's known absence must be preserved exactly, not replaced.\n"
            "HOW: keep observations_provenance None when no observations packet is bound."
        )
        selected = packet.get("selected_acceptance")
        assert (
            isinstance(selected, list)
            and selected
            and selected[0].get("value") == 1
            and selected[0].get("source") == "DESIGN"
            and selected[0].get("criteria") is None
            and isinstance(selected[0].get("revision_sha256"), str)
            and len(selected[0]["revision_sha256"]) == 64
        ), (
            "WHAT: selected_acceptance lost its known value-1 DESIGN-sourced projection.\n"
            "WHY: adding the charter must not empty or corrupt the established acceptance "
            "projection.\n"
            "HOW: keep projecting each design's own value, source and revision digest."
        )
        native = packet.get("native_evidence")
        assert (
            isinstance(native, list)
            and native
            and native[0].get("exit") == 0
            and native[0].get("origin") == "declared"
            and native[0].get("incomplete") is False
            and native[0].get("argv") == _WITHHELD_FIELD
            and native[0].get("stdout") == _WITHHELD_FIELD
            and native[0].get("stderr") == _WITHHELD_FIELD
            and native[0].get("cwd") == _WITHHELD_FIELD
        ), (
            "WHAT: native_evidence lost its known exit/origin content or its withheld "
            "source-bearing fields.\n"
            "WHY: adding the charter must not empty or corrupt the established native "
            "projection.\n"
            "HOW: keep projecting the real exit/origin facts and the withheld markers "
            "unchanged."
        )

    # A prepared examiner packet whose candidate-bound charter bytes no longer
    # agree with its own re-computed digest is stale authority, not a usable
    # input: the tamper must be refused before any provider turn, and the
    # original bytes must remain invokable once restored.
    packet1_path = project1.root / input1
    original_packet1_bytes = packet1_path.read_bytes()
    tampered_packet1 = dict(packet1)
    tampered_packet1["expectation_charters"] = [
        {**entry1, "content_sha256": "0" * 64},
    ]
    packet1_path.write_bytes(_reseal(tampered_packet1))
    before_tamper_turns = asked(project1.turns)
    tampered_invoke1 = project1.run(
        "invoke-role",
        "--repo-root",
        str(project1.root),
        "--role",
        "examiner",
        "--candidate",
        candidate1,
        "--provider",
        "claude",
        "--input",
        input1,
        answers=[
            {
                "structured_output": {
                    "outcome": "indeterminate",
                    "diagnostic": "Public observation is pending.",
                }
            }
        ],
    )
    code, out, err = tampered_invoke1
    assert code != 0, (
        "WHAT: invoke-role accepted a prepared examiner packet whose bound "
        f"charter digest no longer matches its own entry: exited {code}: {out + err}\n"
        "WHY: a candidate/charter digest mismatch is stale prepared input and must "
        "never buy a model turn.\n"
        "HOW: revalidate the candidate-bound charter digest before invocation and "
        "refuse a mismatch."
    )
    assert asked(project1.turns) == before_tamper_turns, (
        "WHAT: a stale prepared examiner packet still bought a new PO/examiner turn.\n"
        "WHY: revalidation must happen before provider issuance, not after.\n"
        "HOW: refuse the mismatch before spawning any model turn."
    )
    packet1_path.write_bytes(original_packet1_bytes)

    invoked1 = project1.run(
        "invoke-role",
        "--repo-root",
        str(project1.root),
        "--role",
        "examiner",
        "--candidate",
        candidate1,
        "--provider",
        "claude",
        "--input",
        input1,
        answers=[
            {
                "structured_output": {
                    "outcome": "indeterminate",
                    "diagnostic": "Public observation is pending.",
                }
            }
        ],
    )
    _assert_success(invoked1, "examiner invocation for candidate 1")
    invoked2 = project2.run(
        "invoke-role",
        "--repo-root",
        str(project2.root),
        "--role",
        "examiner",
        "--candidate",
        candidate2,
        "--provider",
        "claude",
        "--input",
        input2,
        answers=[
            {
                "structured_output": {
                    "outcome": "indeterminate",
                    "diagnostic": "Public observation is pending.",
                }
            }
        ],
    )
    _assert_success(invoked2, "examiner invocation for candidate 2")

    examiner_turns = [
        row
        for row in (
            json.loads(project1.turns.read_text())
            + json.loads(project2.turns.read_text())
        )
        if row["agent"] == "nw-user-examiner"
    ]
    assert len(examiner_turns) == 2, (
        "WHAT: the two candidate invocations did not buy exactly two examiner turns.\n"
        "WHY: each candidate needs its own independent EXAMINE consumption.\n"
        "HOW: invoke the examiner once per candidate through invoke-role."
    )
    path1, path2 = str(CHARTER_DIR / "value-1.md"), str(CHARTER_DIR / "value-2.md")
    assert (
        path1 in examiner_turns[0]["prompt"]
        and path2 not in examiner_turns[0]["prompt"]
    ), (
        "WHAT: candidate 1's actual examiner turn is missing its own charter, or carries "
        "candidate 2's.\n"
        "WHY: a full-content check on the fake's reply is not proof of which prepared "
        "bytes the real invocation consumed.\n"
        "HOW: bind the invoked examiner prompt to exactly the requested candidate's own "
        "prepared input."
    )
    assert (
        path1 in examiner_turns[1]["prompt"] and path2 in examiner_turns[1]["prompt"]
    ), (
        "WHAT: candidate 2's actual examiner turn is missing one of its two bound "
        "charters.\n"
        "WHY: a truncated real invocation is indistinguishable from a complete one "
        "without checking every settled charter reached the examiner.\n"
        "HOW: bind the invoked examiner prompt to every charter in candidate 2's own "
        "prepared input."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))
