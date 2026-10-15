"""The authored oracle is EXECUTED before any craft turn, and must be RED.

MEASURED TWICE, runs 22 and 23 (2026-09-05).  The acceptance designer wrote an
oracle that never reached its own assertion -- run 22 a freshness gate refusing
the installed `des` (4/4 ERROR), run 23 a support path resolved one directory
too high (3/3 ERROR at setup).  Both times the oracle reviewer APPROVED, the
crafter implemented, the declared native verification failed, and the single
correction turn refused with a finding about the ORACLE that no role downstream
of the designer may repair.  Three paid turns per run spent on an artefact the
software could have measured in one second.

`nw-acceptance-designer` holds `Read, Edit` and `nw-acceptance-designer-reviewer`
an enforced EMPTY tool set: neither role can EXECUTE what it authors or judges.
So the property "this oracle fails on its assertion, not on its scaffolding" is
owned by the software (`boundary:software-measures-model-decides`), and
execution-observation is a fixed floor (GDP-7, ADR-025 RED before GREEN).

WHY EXIT STATUS ALONE CANNOT DECIDE IT, measured on run 23's real oracle before
this test was written: `pytest` answers exit 1 for a genuine assertion failure
AND for three tests that ERRORED in fixture setup.  The discriminating fact is
the report's own error/failure split, which the runner asks for through
`PYTEST_ADDOPTS` so the model's declared argv is never rewritten.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    NativeEvidence,
)
from des.domain.design_document import (
    DesignDocument,
    ResolvedDesign,
    resolve_inheritance,
)
from des.domain.oracle_observation import (
    ObservationUnavailable,
    OracleObservation,
    OracleObservationKind,
    decode_native_observation,
    observation_from_counts,
)
from des.ports.driven_ports.task_invocation_port import (
    ModelOutcome,
    ModelRun,
    ProductValue,
    TaskInvocationPort,
)
from tests.des._helpers.host_facts import design_manifest
from tests.des._helpers.step_stimulus import decomposed, designed, oracled


# Long enough to be a real product value: the runner refuses an observation
# under the measured floor, so a placeholder fixture would test the floor
# instead of the oracle.
OBSERVATION = "the installed answer module answers 42 through its public entry point"
ORACLE = "tests/acceptance/test_answer.py"
PRODUCTION = "src/answer.py"
DECLARED_OUTSIDE_ORACLE = "hc/api/tests/test_maintenance_windows_api.py"
DECLARED_OUTSIDE_SUPPORT = "hc/api/tests/maintenance_windows_support.py"

BROKEN_AT_IMPORT = "import nwave_absent_module_for_this_test\n\n\ndef test_answer():\n    assert True\n"
BROKEN_AT_SETUP = """import pytest


@pytest.fixture
def support():
    raise RuntimeError("the support this oracle needs is not there")


def test_answer(support):
    assert support == 42
"""
GREEN_BEFORE_CRAFT = "def test_answer():\n    assert True\n"
RED_ON_ITS_ASSERTION = """def test_answer():
    from pathlib import Path

    assert Path("src/answer.py").read_text(encoding="utf-8") == "ANSWER = 42\\n"
"""
# Runs 31 and 32b in one shape: an oracle that IS red, and red for a defect of
# its own -- two absolute roots that can never be equal -- rather than for the
# behaviour the value promises.  Nothing about the verdict distinguishes it from
# the oracle above; only the failure message does.
RED_FOR_A_DEFECT_OF_ITS_OWN = """import tempfile
from pathlib import Path


def test_answer():
    one = Path(tempfile.mkdtemp(prefix="scenario-")) / "module_b.py:5"
    other = Path(tempfile.mkdtemp(prefix="control-")) / "module_b.py:5"
    assert str(one) == str(other)
"""


def oracle_manifest(  # noqa: PLR0913 - explicit independent native-fixture contract axes
    decision: str = "one observable value",
    *,
    oracle: str = ORACLE,
    acceptance_supports: tuple[str, ...] = (),
    targets: tuple[tuple[str, str], ...] = (
        (PRODUCTION, "CREATE_NEW"),
        (ORACLE, "CREATE_NEW"),
    ),
    verification: tuple[tuple[str, ...], ...] | None = None,
    oracle_verification_index: int = 0,
    paradigm: str = "object_oriented",
) -> dict:
    """The authored-oracle family's explicit facts through the shared producer."""
    return design_manifest(
        {
            "targets": [{"path": path, "decision": choice} for path, choice in targets],
            "paradigm": paradigm,
            "decisions": [decision],
            "oracle": oracle,
            "acceptance_supports": list(acceptance_supports),
            "verification": verification
            if verification is not None
            else (("python", "-m", "pytest", oracle, "-q"),),
            "oracle_verification_index": oracle_verification_index,
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
        OBSERVATION,
        1,
    )


def execution_authority(root: Path, manifest: dict) -> AuthorityFacts:
    """Construct the execution fixture without testing executable admission."""
    document = DesignDocument.from_json(json.dumps(manifest))
    resolved = resolve_inheritance(None, (), document.facts)
    assert isinstance(resolved, ResolvedDesign), resolved
    authority = DeliveryContinuationRunner._derive(
        root,
        resolved.design,
        admit_verification=False,
        resolution=resolved,
    )
    assert isinstance(authority, AuthorityFacts), authority
    return replace(authority, resolved=resolved)


def fact(prompt: str, key: str) -> object:
    """One dynamic fact out of a prompt `_prompt` framed: `key: <one JSON value>`."""
    prefix = f"{key}: "
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return json.loads(line[len(prefix) :])
    raise AssertionError(f"{key} is not among the facts asked: {prompt[:400]}")


def asked(port: ScriptedPort, role: str, occurrence: int = 0) -> str:
    prompts = [text for asked_role, text in port.prompts if asked_role == role]
    assert len(prompts) > occurrence, [role for role, _ in port.prompts]
    return prompts[occurrence]


def _accepted(**facts: object) -> ModelRun:
    return ModelRun(ModelOutcome.Accepted, "", 0, True, **facts)  # type: ignore[arg-type]


class ScriptedPort(TaskInvocationPort):
    """Every role answers from a script; the designer writes the queued oracle."""

    def __init__(
        self,
        root: Path,
        oracles: list[str],
        *,
        oracle: str = ORACLE,
        acceptance_supports: tuple[str, ...] = (),
        mutate_production: bool = False,
    ) -> None:
        self.root = root
        self.oracles = list(oracles)
        self.oracle = oracle
        self.acceptance_supports = acceptance_supports
        self.mutate_production = mutate_production
        self.roles: list[str] = []
        self.prompts: list[tuple[str, str]] = []

    def manifest(self, decision: str = "one observable value") -> dict:
        return oracle_manifest(
            decision,
            oracle=self.oracle,
            acceptance_supports=self.acceptance_supports,
            targets=((PRODUCTION, "CREATE_NEW"), (self.oracle, "CREATE_NEW")),
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
        self.prompts.append((role_id, prompt))
        if role_id == "nw-product-owner":
            return _accepted(product_values=(ProductValue(OBSERVATION),))
        if role_id == "nw-solution-architect":
            return _accepted()
        if role_id == "nw-acceptance-designer":
            written = self.root / self.oracle
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text(self.oracles.pop(0), encoding="utf-8")
            for support in self.acceptance_supports:
                support_path = self.root / support
                support_path.parent.mkdir(parents=True, exist_ok=True)
                support_path.write_text(
                    "# declared acceptance support\n", encoding="utf-8"
                )
            if self.mutate_production:
                production = self.root / PRODUCTION
                production.parent.mkdir(parents=True, exist_ok=True)
                production.write_text(
                    "unexpected production mutation\n", encoding="utf-8"
                )
            return _accepted()
        if role_id in (
            "nw-acceptance-designer-reviewer",
            "nw-software-crafter-reviewer",
            "nw-user-examiner",
        ):
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
    """Retain the fixture's original source before any test-body authoring or fix."""
    return subprocess.run(
        ["git", "-C", str(subject), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


REQUEST = "deliver the answer"


def one_oracle_turn(
    subject: Path, port: ScriptedPort, *, baseline: str, finding: str | None = None
):
    """`po`, `design`, then ONE `oracle` -- each invoked explicitly by this test.

    MIGRATED STIMULUS. These scenarios used to reach `oracle` by starting a
    whole composed Request and letting the software walk to it. `des dispatch`
    is retired, so the test does what an orchestrator does: it names each step.
    """
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, subject, REQUEST)
    stored, design = designed(runner, port, subject, stored, port.manifest())
    return (
        runner,
        stored,
        design,
        oracled(
            runner, port, subject, stored, design, baseline=baseline, finding=finding
        ),
    )


def crafted(port: ScriptedPort) -> bool:
    return "nw-software-crafter" in port.roles


@pytest.mark.parametrize(
    "body",
    [BROKEN_AT_IMPORT, BROKEN_AT_SETUP],
    ids=["import-error", "setup-error"],
)
def test_a_broken_oracle_is_refused_by_the_step_that_measured_it(
    subject: Path, genesis: str, body: str
) -> None:
    # Run 22 and run 23 in one shape: the oracle never reaches its assertion.
    # The step refuses on the EXECUTED property, and it refuses in the same
    # invocation that authored the bytes -- no craft turn is reachable from a
    # value whose oracle step never recorded.
    port = ScriptedPort(subject, [body])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert not crafted(port), f"the crafter ran on a broken oracle: {port.roles}"
    outcome = measured.refusal
    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.disposition is Disposition.Refusal
    assert outcome.failure is not None
    assert outcome.failure.what == "OracleNotRed"
    assert ORACLE in outcome.failure.why


def test_a_declared_oracle_and_support_outside_pytest_testpaths_are_authored(
    subject: Path,
    genesis: str,
) -> None:
    """Authority, rather than a fixture pyproject, authorizes this test layout."""
    port = ScriptedPort(
        subject,
        [RED_ON_ITS_ASSERTION],
        oracle=DECLARED_OUTSIDE_ORACLE,
        acceptance_supports=(DECLARED_OUTSIDE_SUPPORT,),
    )

    _, _, design, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert measured.refusal is None, measured.refusal
    assert design.acceptance_paths == (
        DECLARED_OUTSIDE_ORACLE,
        DECLARED_OUTSIDE_SUPPORT,
    )
    assert (subject / DECLARED_OUTSIDE_ORACLE).is_file()
    assert (subject / DECLARED_OUTSIDE_SUPPORT).is_file()


def test_aggregate_correction_owns_declared_oracle_outside_pytest_testpaths(
    subject: Path,
    genesis: str,
) -> None:
    port = ScriptedPort(
        subject,
        [BROKEN_AT_SETUP, RED_ON_ITS_ASSERTION],
        oracle=DECLARED_OUTSIDE_ORACLE,
        acceptance_supports=(DECLARED_OUTSIDE_SUPPORT,),
    )

    runner, stored, design, first = one_oracle_turn(subject, port, baseline=genesis)
    assert first.refusal is not None

    corrected = oracled(
        runner,
        port,
        subject,
        stored,
        design,
        baseline=genesis,
        finding="the oracle errors at setup",
    )

    assert corrected.refusal is None, corrected.refusal


@pytest.mark.parametrize(
    "missing",
    [(ORACLE,), (DECLARED_OUTSIDE_SUPPORT,), (ORACLE, DECLARED_OUTSIDE_SUPPORT)],
    ids=["oracle", "support", "oracle-and-support"],
)
def test_missing_acceptance_files_are_named_with_their_actual_role(
    subject: Path, genesis: str, missing: tuple[str, ...]
) -> None:
    class IncompleteAuthor(ScriptedPort):
        def invoke(self, **kwargs: object) -> ModelRun:
            result = super().invoke(**kwargs)
            if kwargs["role_id"] == "nw-acceptance-designer":
                for path in missing:
                    (self.root / path).unlink()
            return result

    port = IncompleteAuthor(
        subject,
        [RED_ON_ITS_ASSERTION],
        acceptance_supports=(DECLARED_OUTSIDE_SUPPORT,),
    )

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    outcome = measured.refusal
    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    assert outcome.failure.what == "OracleUnavailable"
    for path in missing:
        role = "oracle" if path == ORACLE else "acceptance support"
        assert f"{role} {path!r}" in outcome.failure.why
    if ORACLE not in missing:
        assert f"oracle {ORACLE!r}" not in outcome.failure.why
    assert "declaration" in outcome.failure.how
    assert not crafted(port)


def test_unobservable_support_is_not_reported_as_a_missing_oracle(
    subject: Path, genesis: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = ScriptedPort(
        subject,
        [RED_ON_ITS_ASSERTION],
        acceptance_supports=(DECLARED_OUTSIDE_SUPPORT,),
    )
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, subject, REQUEST)
    stored, design = designed(runner, port, subject, stored, port.manifest())
    regular_file = DeliveryContinuationRunner._regular_file

    def observe(path: Path) -> bool | None:
        if path == subject / DECLARED_OUTSIDE_SUPPORT:
            return None
        return regular_file(path)

    monkeypatch.setattr(
        DeliveryContinuationRunner, "_regular_file", staticmethod(observe)
    )

    measured = oracled(runner, port, subject, stored, design, baseline=genesis)

    outcome = measured.refusal
    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    assert outcome.failure.what == "OracleUnobservable"
    assert f"acceptance support {DECLARED_OUTSIDE_SUPPORT!r}: unobservable" in (
        outcome.failure.why
    )
    assert "missing" not in outcome.failure.why
    assert f"oracle {ORACLE!r}" not in outcome.failure.why
    assert (subject / DECLARED_OUTSIDE_SUPPORT).is_file()


def test_a_green_oracle_is_measured_and_reported_but_does_not_refuse(
    subject: Path, genesis: str, capfd: pytest.CaptureFixture[str]
) -> None:
    # MEASURED, and the reason `green` is not in `_ORACLE_REFUSING`.  Several
    # designed behaviours present a green oracle before any craft turn -- a
    # resume whose earlier craft bytes survived a failed integration, a value a
    # sibling already delivered, the no-delta Request that writes no commit and
    # still swaps, the silent craft turn on an already-delivered value.  The
    # verdict is still computed and printed, so a vacuous oracle is visible
    # without a paid turn spent refusing one.
    port = ScriptedPort(subject, [GREEN_BEFORE_CRAFT])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert measured.refusal is None
    reported = [
        line
        for line in capfd.readouterr().err.splitlines()
        if line.startswith("ORACLE-RED:")
    ]
    assert reported and f"{ORACLE} exit=0 verdict=green" in reported[0], reported


def test_a_correction_that_answers_the_finding_records_the_turn(
    subject: Path,
    genesis: str,
) -> None:
    # The second invocation is a real repair: the author is given the finding,
    # writes a RED oracle, and THIS step admits the set and records it -- the
    # precondition `craft` reads. Which role answers, and whether to spend the
    # turn at all, is the orchestrator's decision and not a branch in here.
    port = ScriptedPort(subject, [BROKEN_AT_SETUP, RED_ON_ITS_ASSERTION])

    runner, stored, design, first = one_oracle_turn(subject, port, baseline=genesis)
    assert first.refusal is not None

    corrected = oracled(
        runner,
        port,
        subject,
        stored,
        design,
        baseline=genesis,
        finding="the oracle errors at setup",
    )

    assert corrected.refusal is None, corrected.refusal
    assert port.roles.count("nw-acceptance-designer") == 2, port.roles
    assert runner.oracle_turn_complete(subject, stored, stored.values[0], design)


def test_the_step_measures_the_red_before_it_admits_the_set(
    subject: Path,
    genesis: str,
) -> None:
    """The measurement is the step's own answer, not a claim about a role.

    RECONCILED. This scenario asserted that the pre-craft REVIEWER was told the
    measured red. `des oracle` buys no such turn -- ADR-DES-003 Section 14
    retires the pre-craft judge, a change documented and landed separately -- so
    the same observation is read where it now lives: the measured set the step
    returns to its caller.
    """
    port = ScriptedPort(subject, [RED_ON_ITS_ASSERTION])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert measured.refusal is None
    assert port.roles == [
        "nw-product-owner",
        "nw-solution-architect",
        "nw-acceptance-designer",
    ], port.roles
    assert len(measured.measured) == 1, measured.measured


@pytest.mark.parametrize(
    ("exit_status", "counts", "report_requested", "verdict"),
    [
        (1, (3, 0, 3), False, "red"),
        (1, (3, 3, 0), False, "broken"),
        (1, (5, 1, 4), False, "broken"),
        (1, None, False, "indeterminate"),
        (1, None, True, "broken"),
        (0, (2, 0, 0), False, "green"),
        (0, None, False, "indeterminate"),
        (0, None, True, "broken"),
        (2, None, False, "indeterminate"),
        (4, (0, 0, 0), True, "indeterminate"),
        (5, (0, 0, 0), True, "indeterminate"),
        (1, (0, 0, 0), False, "indeterminate"),
    ],
    ids=[
        "failures-only-is-red",
        "errors-only-is-broken",
        "any-error-is-broken",
        "native-exit-one-is-unclassified",
        "no-report-under-a-pytest-vector-is-broken",
        "green-report",
        "no-observation-is-indeterminate",
        "green-no-report-under-a-pytest-vector-is-broken",
        "native-exit-two-is-unclassified",
        "internal-usage-error",
        "no-test-collected",
        "exit-one-with-a-silent-report",
    ],
)
def test_the_verdict_reads_both_axes(
    exit_status: int,
    counts: tuple[int, int, int] | None,
    report_requested: bool,
    verdict: str,
) -> None:
    observation = (
        observation_from_counts(counts[0], counts[2], counts[1], source="junit-report")
        if counts is not None
        else ObservationUnavailable("junit-report-absent", "requested report absent")
        if report_requested
        else OracleObservation(OracleObservationKind.Missing, "native-observation")
    )
    measured = DeliveryContinuationRunner._oracle_verdict(
        exit_status, observation, completed=True
    )
    assert measured[0] == verdict


def test_same_oracle_with_distinct_explicit_bindings_executes_each_binding(
    subject: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broad = ("python", "manage.py", "test", "hc.api.tests")
    django_module = (
        "python",
        "manage.py",
        "test",
        "hc.api.tests.test_maintenance_windows",
    )
    first = execution_authority(
        subject,
        oracle_manifest(
            verification=(broad, django_module),
            oracle_verification_index=0,
        ),
    )
    second = execution_authority(
        subject,
        oracle_manifest(
            verification=(broad, django_module),
            oracle_verification_index=1,
        ),
    )
    executed: list[tuple[str, ...]] = []

    def native(
        _root: Path, commands: tuple[tuple[str, ...], ...], *_args: object, run: object
    ) -> tuple[NativeEvidence, ...]:
        executed.extend(commands)
        return (NativeEvidence(commands[0], 1, "", ""),)

    runner = DeliveryContinuationRunner()
    monkeypatch.setattr(runner, "_native", native)
    monkeypatch.setattr(runner, "_junit_counts", lambda _report: (1, 0, 1))
    monkeypatch.setattr(runner, "_junit_failures", lambda _report: ())

    measured = runner._executed_oracle_set(
        subject, [("first", first), ("second", second)]
    )

    assert not isinstance(measured, DeliveryOutcome)
    assert executed == [broad, django_module]


def test_the_measured_red_carries_every_axis_the_reader_needs(
    subject: Path,
    genesis: str,
) -> None:
    # A reader of this measurement -- the correction author below, or the
    # orchestrator -- cannot run what it is judging, so a fact it is not told
    # is a fact it must take on faith. Read off the step's own answer, which is
    # where the measurement lives now that no pre-craft judge is bought.
    port = ScriptedPort(subject, [RED_ON_ITS_ASSERTION])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert len(measured.measured) == 1, measured.measured
    only = measured.measured[0]
    assert only["path"] == ORACLE
    assert only["verdict"] == "red"
    assert only["exit"] == 1
    assert only["counts"] == (1, 0, 1)
    assert ORACLE in " ".join(only["argv"])  # type: ignore[arg-type]
    assert only["failures"], only
    assert PRODUCTION in only["failures"][0]["message"], only["failures"]  # type: ignore[index]


def test_a_red_reached_on_the_oracles_own_defect_says_so_in_its_message(
    subject: Path,
    genesis: str,
) -> None:
    # The whole point.  Both oracles are `red` on every axis the runner had
    # before this: exit 1, one failure, zero errors.  The message is the only
    # place the difference between "the behaviour is missing" and "this oracle
    # compares two roots that can never be equal" is written down.
    port = ScriptedPort(subject, [RED_FOR_A_DEFECT_OF_ITS_OWN])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    only = measured.measured[0]
    message = only["failures"][0]["message"]  # type: ignore[index]
    assert only["verdict"] == "red"
    assert message.count("module_b.py:5") >= 2, message
    assert "scenario-" in message and "control-" in message, message


def test_a_green_oracle_is_reported_as_green_with_no_failures(
    subject: Path,
    genesis: str,
) -> None:
    # The field is a MEASUREMENT and not a refusal: green stays admitted, and
    # the reader is told it is green rather than left to assume a red.
    port = ScriptedPort(subject, [GREEN_BEFORE_CRAFT])

    _, _, _, measured = one_oracle_turn(subject, port, baseline=genesis)

    assert measured.measured[0]["verdict"] == "green"
    assert measured.measured[0]["failures"] == ()


def test_the_failure_text_is_cut_at_a_declared_ceiling(tmp_path: Path) -> None:
    # A ceiling that is not stated is silent-wrong: the reader cannot tell a
    # short failure from a trimmed one, so the cut is MARKED and the failures
    # dropped past it are counted rather than silently absent.
    body = "".join(
        f'<testcase classname="t" name="test_{index}">'
        f'<failure message="AssertionError">{"x" * 3000}</failure>'
        "</testcase>"
        for index in range(5)
    )
    report = tmp_path / "report.xml"
    report.write_text(f"<testsuite>{body}</testsuite>", encoding="utf-8")

    failures = DeliveryContinuationRunner._junit_failures(report)

    assert failures is not None
    spoken = "".join(entry["message"] for entry in failures)
    assert len(spoken) < 2 * DeliveryContinuationRunner._ORACLE_FAILURE_BUDGET
    assert "[...truncated]" in spoken
    assert failures[-1]["kind"] == "ceiling"
    assert "3 further failing tests" in failures[-1]["message"]


def test_an_unreadable_report_is_absence_of_observation_not_of_failures(
    tmp_path: Path,
) -> None:
    # The same world `_junit_counts` answers None for.  Returning an empty
    # tuple there would tell the judge the oracle failed nowhere, which is a
    # claim nothing observed (GDP-6).
    assert DeliveryContinuationRunner._junit_failures(tmp_path / "absent.xml") is None


@pytest.mark.parametrize("exit_status", [1, 101])
def test_unclassified_native_failure_is_refused_without_inventing_a_pytest_verdict(
    subject: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_status: int,
) -> None:
    command = ("cargo", "test", "--offline")
    authority = execution_authority(
        subject,
        oracle_manifest(
            "Observe queue visibility.",
            oracle="tests/queue_visibility.rs",
            targets=(("src/lib.rs", "EXTEND"),),
            verification=(command,),
            paradigm="functional",
        ),
    )
    runner = DeliveryContinuationRunner()
    monkeypatch.setattr(
        runner,
        "_native",
        lambda *_args, **_kwargs: (
            NativeEvidence(
                command, exit_status, "native test output", "native diagnostic"
            ),
        ),
    )
    monkeypatch.setattr(runner, "_junit_counts", lambda _report: None)
    monkeypatch.setattr(runner, "_junit_failures", lambda _report: ())
    result = runner._executed_oracle_set(subject, [(OBSERVATION, authority)])
    assert not isinstance(result, DeliveryOutcome)
    assert result.refusal is not None
    outcome = result.refusal.terminal
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "OracleRedUnobservable"
    assert "DES-ORACLE-OBSERVATION:" in outcome.failure.how
    assert result.measured[0]["verdict"] == "indeterminate"
    assert result.measured[0]["axis"] == "exit-status-only"
    assert result.measured[0]["counts"] is None
    assert result.measured[0]["exit"] == exit_status
    assert result.measured[0]["argv"] == list(command)
    assert "native diagnostic" in result.measured[0]["diagnostic"]


@pytest.mark.parametrize(
    "payload",
    [
        {"version": True, "observed": 1, "assertions_failed": 1, "setup_failed": 0},
        {"version": 1, "observed": True, "assertions_failed": 1, "setup_failed": 0},
        {"version": 1, "observed": -1, "assertions_failed": 0, "setup_failed": 0},
        {"version": 1, "observed": 0, "assertions_failed": 1, "setup_failed": 0},
        {"version": 1, "observed": 1, "assertions_failed": 1, "setup_failed": -1},
    ],
    ids=[
        "boolean-version",
        "boolean-count",
        "negative-count",
        "incoherent-count",
        "negative-setup",
    ],
)
def test_invalid_native_construction_is_refused_with_its_reason(payload: dict) -> None:
    observation = decode_native_observation(
        "DES-ORACLE-OBSERVATION: " + json.dumps(payload) + "\n", completed=True
    )
    assert isinstance(observation, ObservationUnavailable)
    assert observation.reason
    verdict, axis = DeliveryContinuationRunner._oracle_verdict(
        1, observation, completed=True
    )
    assert (verdict, axis) == ("indeterminate", "native-observation-invalid")


@pytest.mark.parametrize(
    "observation",
    [
        OracleObservation(OracleObservationKind.AssertionFailed, "native-observation"),
        OracleObservation(
            OracleObservationKind.AssertionFailed, "native-observation", 1, 2
        ),
        OracleObservation(
            OracleObservationKind.AssertionFailed, "native-observation", 1, 1, 1
        ),
        OracleObservation(
            OracleObservationKind.AssertionFailed, "native-observation", True, 1
        ),
    ],
    ids=["no-observation", "excess-failures", "mixed-setup", "raw-boolean"],
)
def test_raw_python_construction_cannot_promote_invalid_assertion_evidence(
    observation: OracleObservation,
) -> None:
    assert DeliveryContinuationRunner._oracle_verdict(
        1, observation, completed=True
    ) == ("indeterminate", "native-observation-invalid")


@pytest.mark.parametrize("exit_status", [0, 1, 2, 127])
@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("source", ["native-observation", "junit-report"])
def test_captured_assertion_requires_completion_and_nonzero_exit(
    exit_status: int, completed: bool, source: str
) -> None:
    observation = observation_from_counts(1, 1, 0, source=source)
    verdict, _ = DeliveryContinuationRunner._oracle_verdict(
        exit_status, observation, completed=completed
    )
    assert verdict == (
        "broken" if not completed else "red" if exit_status else "indeterminate"
    )


@pytest.mark.parametrize("exit_status", [0, 1, 2, 127])
@pytest.mark.parametrize("source", ["native-observation", "junit-report"])
def test_setup_after_assertions_never_becomes_a_positive_outcome(
    exit_status: int, source: str
) -> None:
    observation = observation_from_counts(1, 1, 1, source=source)
    assert DeliveryContinuationRunner._oracle_verdict(
        exit_status, observation, completed=True
    ) == ("broken", source)
