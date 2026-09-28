"""Regression oracle for the des-fixes-sonnet-20260917 recovery batch.

Four durable observations, each protecting one approved fix:

1. `oracle --finding` after a first authoring turn that left NO oracle bytes
   at all must route straight back to the AUTHOR, not to a preverification
   execution of a path that was never written.  The finding string the caller
   gave the step must reach that second author turn byte-for-byte.
2. A design correction that changes the bound decisions (D1 -> D2) but yields
   the SAME oracle bytes must not let the settlement step silently re-point
   the record over D1's authoring evidence: the record is a fact about a
   design, not only about a byte string.
3. Non-UTF-8 native stdout/stderr must not crash the closed native-evidence
   boundary; the process exit and a replacement-decoded, readable payload
   survive, and unchanged bytes still round-trip losslessly for valid UTF-8.
4. The declared oracle-verification argv is what actually runs, independent
   of the oracle locator's file extension and never defaulted to pytest --
   proven here with a Go-named locator bound to a generic, tool-independent
   fake executable (no Go toolchain required).

WHY THESE LIVE TOGETHER: each is a distinct closed acceptance requirement
from the same maintenance batch, sharing the same real driving port
(`DeliveryContinuationRunner`) and the same test-side stimulus helpers the
rest of this suite already uses.  None fabricates a field, an operation, a
fixture fact, or an expected result beyond what the production module already
declares.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    AuthorityFacts,
    DeliveryContinuationRunner,
    DeliveryOutcome,
    DesignOptions,
    NativeRun,
)
from des.ports.driven_ports.task_invocation_port import ModelOutcome, ModelRun
from tests.des._helpers.step_stimulus import decomposed, designed, oracled
from tests.des.unit.application.test_authored_oracle_is_executed_red import (
    OBSERVATION,
    ORACLE,
    PRODUCTION,
    RED_ON_ITS_ASSERTION,
    REQUEST,
    ScriptedPort,
    asked,
    fact,
    git,
)


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


# ---------------------------------------------------------------------------
# 1. `oracle --finding` with no authored oracle routes to the author.
# ---------------------------------------------------------------------------


class RejectsThenAuthors(ScriptedPort):
    """First acceptance-design turn REJECTS and writes no byte anywhere.

    The second turn (given a finding) authors normally, through the parent's
    scripted behaviour -- so this class changes exactly the one fact under
    test and reuses every other scripted role verbatim.
    """

    def __init__(self, root: Path, oracle_body: str) -> None:
        super().__init__(root, [oracle_body])
        self._designer_calls = 0

    def invoke(
        self, *, role_id: str, prompt: str, cwd: Path, **rest: object
    ) -> ModelRun:
        if role_id == "nw-acceptance-designer" and self._designer_calls == 0:
            self._designer_calls += 1
            self.roles.append(role_id)
            self.prompts.append((role_id, prompt))
            return ModelRun(
                ModelOutcome.Rejected,
                "left no oracle: still scoping the observation",
                0,
                False,
            )
        if role_id == "nw-acceptance-designer":
            self._designer_calls += 1
        return super().invoke(role_id=role_id, prompt=prompt, cwd=cwd, **rest)  # type: ignore[arg-type]


def test_finding_with_no_authored_oracle_invokes_the_author(subject: Path) -> None:
    # WHAT: a first authoring turn that REJECTED wrote no oracle byte at all.
    # A correction called with `finding` on this state must reach the AUTHOR
    # a second time, not a preverification execution of a path nothing wrote.
    # WHY: `AcceptanceEvidenceUnavailable`, `OracleUnobservable` and similar
    # preverification refusals answer "the oracle exists and is broken";
    # "no oracle exists yet" is a different, cheaper fact the same author turn
    # already answers on its first call, and answering it a second way instead
    # of buying the author's turn drops the finding on the floor.
    # HOW: the fix routes `finding is not None and no oracle byte is present`
    # straight to the same authoring path `finding is None` already takes.
    port = RejectsThenAuthors(subject, RED_ON_ITS_ASSERTION)
    runner = DeliveryContinuationRunner(port)
    stored = decomposed(runner, port, subject, REQUEST)
    stored, design = designed(runner, port, subject, stored)

    first = oracled(runner, port, subject, stored, design)
    assert first.refusal is not None, "the rejecting first turn must refuse"
    assert not (subject / ORACLE).exists(), "a rejected author must own no byte"

    finding = "author the missing oracle for this observation"
    corrected = oracled(runner, port, subject, stored, design, finding=finding)

    assert corrected.refusal is None, (
        f"WHAT: the correction refused instead of authoring: {corrected.refusal}\n"
        f"WHY: no oracle byte existed, so this is a first authoring turn wearing "
        f"a `finding`, not a correction over existing evidence\n"
        f"HOW: route `finding is not None` with no observable oracle byte to "
        f"the same author call `finding is None` already makes"
    )
    assert port.roles.count("nw-acceptance-designer") == 2, (
        f"WHAT: expected exactly 2 author turns (reject, then author), got "
        f"{port.roles.count('nw-acceptance-designer')}\n"
        f"WHY: the second call must be a fresh authoring turn, not a skipped one\n"
        f"HOW: the second designer invocation is the fix's observable effect"
    )
    second_prompt = asked(port, "nw-acceptance-designer", 1)
    assert fact(second_prompt, "finding") == finding, (
        "WHAT: the second author turn's finding does not match the original "
        "string verbatim\n"
        "WHY: ADR-DES-003 requires the finding travel unedited to its author\n"
        "HOW: pass the original finding through, not a synthesized "
        "preverification message"
    )


# ---------------------------------------------------------------------------
# 2. D1 -> D2 with identical oracle bytes must not reuse D1's evidence.
# ---------------------------------------------------------------------------


def test_changed_design_with_unchanged_oracle_bytes_is_not_settled_by_stale_evidence(
    subject: Path,
) -> None:
    # WHAT: correcting the DESIGN (decisions D1 -> D2) while the oracle bytes
    # stay byte-identical must not let `oracle_settlement` re-point the record
    # over D1's authoring evidence without a fresh turn or measurement tied to
    # D2.
    # WHY: `oracle_turn_complete` (gate 1 of `oracle_settlement`) keys only on
    # the value's observation plus its acceptance-path BYTES, never on which
    # design decisions the recorded turn was authored against -- so a changed
    # design with unchanged bytes is settled for free on a stale record.
    # HOW: gate 1 must also compare the design bound to the recorded turn
    # against the CURRENT design, and fall through to gate 4 (re-execute /
    # re-record) when they disagree.
    class ChangingDesignPort(ScriptedPort):
        def __init__(self, root: Path) -> None:
            super().__init__(root, [RED_ON_ITS_ASSERTION])
            self.design_calls = 0

        def invoke(
            self, *, role_id: str, prompt: str, cwd: Path, **rest: object
        ) -> ModelRun:
            if role_id == "nw-solution-architect":
                self.design_calls += 1
                decision = "D1" if self.design_calls == 1 else "D2"
                self.roles.append(role_id)
                self.prompts.append((role_id, prompt))
                from des.ports.driven_ports.task_invocation_port import (
                    DesignFacts,
                    DesignTarget,
                )

                return ModelRun(
                    ModelOutcome.Accepted,
                    "",
                    0,
                    True,
                    design_facts=DesignFacts(
                        targets=(
                            DesignTarget(PRODUCTION, "CREATE_NEW"),
                            DesignTarget(ORACLE, "CREATE_NEW"),
                        ),
                        paradigm="object_oriented",
                        decisions=(decision,),
                        oracle=ORACLE,
                        acceptance_supports=(),
                        verification=(("python", "-m", "pytest", ORACLE, "-q"),),
                        oracle_verification_index=0,
                    ),
                )
            return super().invoke(role_id=role_id, prompt=prompt, cwd=cwd, **rest)  # type: ignore[arg-type]

    port = ChangingDesignPort(subject)
    runner = DeliveryContinuationRunner(port)
    stored = decomposed(runner, port, subject, REQUEST)
    stored, d1 = designed(runner, port, subject, stored)
    first = oracled(runner, port, subject, stored, d1)
    assert first.refusal is None, first.refusal

    # Correct the DESIGN only (same value, same oracle bytes on disk): D2.
    stored, d2 = runner.design_value(
        subject,
        port,
        stored,
        stored.values[0],
        options=DesignOptions(finding="change semantic decision"),
    )
    assert d1.decisions != d2.decisions, "the probe requires a genuine design change"
    assert d1.acceptance_paths == d2.acceptance_paths, (
        "the probe requires unchanged oracle bytes on disk"
    )

    replay = DeliveryContinuationRunner(port).oracle_settlement(
        subject, stored, stored.values[0], d2
    )

    settled_over_stale_record = (
        replay.value == "recorded-over-current-bytes"
        and port.roles.count("nw-acceptance-designer") == 1
    )
    assert not settled_over_stale_record, (
        f"WHAT: oracle_settlement={replay.value} reused the SOLE authoring "
        f"turn ({port.roles.count('nw-acceptance-designer')} designer call) "
        f"even though the design changed D1={d1.decisions} -> D2={d2.decisions}\n"
        f"WHY: gate 1 (`oracle_turn_complete`) must not settle a design it "
        f"never measured evidence against\n"
        f"HOW: key the recorded-turn comparison on the design bound at "
        f"authoring time too, not only on the oracle bytes"
    )


# ---------------------------------------------------------------------------
# 3. Non-UTF-8 native stdout must not crash the closed native-evidence path.
# ---------------------------------------------------------------------------


def test_non_utf8_native_output_does_not_crash_and_stays_readable(
    subject: Path,
) -> None:
    # WHAT: a declared native command that writes an invalid-UTF-8 byte to its
    # own stdout must not raise out of `_native_evidence`; the process exit
    # status and a readable (replacement-decoded) payload must both survive.
    # WHY: `_native_evidence` passes `text=True` straight to `subprocess.run`
    # with no `errors=` kwarg, so a strict UTF-8 decode raises
    # `UnicodeDecodeError` inside the runner instead of the runner returning
    # its own closed `DeliveryOutcome` or `NativeEvidence` tuple.
    # HOW: decode native stdout/stderr with `errors="replace"` (or an
    # equivalent explicit replacement policy), never with strict decoding.
    runner = DeliveryContinuationRunner()
    non_utf8_command = (
        os.environ.get("PYTHON", "python3"),
        "-c",
        "import sys; sys.stdout.buffer.write(bytes([0xFF])); sys.stdout.buffer.flush()",
    )

    try:
        result = runner._native_evidence(
            subject,
            (non_utf8_command,),
            dict(os.environ),
            run=NativeRun(capture_incomplete=True),
        )
    except UnicodeDecodeError as crashed:
        pytest.fail(
            "WHAT: _native_evidence raised UnicodeDecodeError instead of "
            f"returning closed evidence: {crashed}\n"
            "WHY: a native command's stdout byte is not under DES's control; "
            "a boundary that crashes on it turns a real product observation "
            "into an unrelated interpreter traceback\n"
            "HOW: decode native stdout/stderr with errors='replace' before "
            "building NativeEvidence"
        )

    assert not isinstance(result, DeliveryOutcome), (
        f"WHAT: non-UTF-8 stdout produced an indeterminate outcome instead of "
        f"NativeEvidence: {result}\n"
        f"WHY: the fix must preserve an honest, readable evidence record, not "
        f"downgrade a real exit to indeterminate\n"
        f"HOW: return the NativeEvidence tuple with replacement-decoded text"
    )
    assert len(result) == 1
    evidence = result[0]
    assert evidence.exit_status == 0, (
        "the child process itself must have exited cleanly"
    )
    assert "�" in evidence.stdout or evidence.stdout != "", (
        "WHAT: the non-UTF-8 byte must surface as a readable replacement "
        "character, not silence\n"
        "WHY: a swallowed byte is indistinguishable from a swallowed error\n"
        "HOW: decode with errors='replace' so the byte is visible as U+FFFD"
    )


def test_valid_utf8_native_output_is_unchanged(subject: Path) -> None:
    # WHAT/WHY: the same boundary must not alter valid UTF-8 payloads as a
    # side effect of fixing the non-UTF-8 crash -- a lossy "always replace
    # widely" fix would silently corrupt every ordinary passing oracle run.
    runner = DeliveryContinuationRunner()
    utf8_command = (
        os.environ.get("PYTHON", "python3"),
        "-c",
        "print('café ✅ ok')",
    )

    result = runner._native_evidence(
        subject,
        (utf8_command,),
        dict(os.environ),
        run=NativeRun(capture_incomplete=True),
    )

    assert not isinstance(result, DeliveryOutcome)
    assert result[0].stdout.strip() == "café ✅ ok", (
        "HOW: valid UTF-8 must round-trip exactly; errors='replace' is a "
        "no-op on well-formed input"
    )


# ---------------------------------------------------------------------------
# 5. Native oracle command comes from the design's declared argv, never from
#    the locator's file extension or a default pytest invocation.
# ---------------------------------------------------------------------------


def test_go_named_locator_runs_its_declared_generic_argv_not_pytest(
    subject: Path,
) -> None:
    # WHAT: a `.go`-named oracle locator, bound to an explicitly declared
    # argv that runs a generic, tool-independent fake executable (never the
    # `go` toolchain, never `pytest`), must execute exactly that declared
    # argv.
    # WHY: this is a BASELINE PASSING CONTROL -- `_executed_oracle_set`
    # already dispatches on `design.oracle_verification_argv` alone (no
    # extension branching exists in the runner today). Recorded honestly so
    # a future regression that reintroduces extension- or language-based
    # dispatch is caught by this same test turning RED.
    # HOW: n/a for this control -- it documents the invariant the other four
    # observations depend on staying true.
    fake_checker = subject / "bin" / "fakecheck"
    fake_checker.parent.mkdir(parents=True, exist_ok=True)
    fake_checker.write_text(
        "#!/bin/sh\necho ok-from-fakecheck\nexit 0\n", encoding="utf-8"
    )
    fake_checker.chmod(
        fake_checker.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )

    go_oracle = "tests/acceptance/oracle_test.go"
    declared_argv = (str(fake_checker), "run")
    authority = AuthorityFacts(
        locator="docs/architecture.md#Go named oracle",
        modified_authority_paths=(),
        target_decisions=((PRODUCTION, "CREATE_NEW"),),
        paradigm="object_oriented",
        decisions=(),
        obligations=(),
        acceptance_oracle_locator=go_oracle,
        acceptance_paths=(go_oracle,),
        native_verification_argvs=(declared_argv,),
        oracle_verification_index=0,
    )

    runner = DeliveryContinuationRunner()
    measured = runner._executed_oracle_set(subject, [(OBSERVATION, authority)])

    assert not isinstance(measured, DeliveryOutcome), measured
    assert len(measured.measured) == 1
    row = measured.measured[0]
    assert tuple(row["argv"]) == declared_argv, (
        f"WHAT: executed argv {row['argv']!r} does not equal the declared "
        f"{declared_argv!r}\n"
        f"WHY: the command must come from the design's declared argv, never "
        f"be inferred from the `.go` locator extension or defaulted to pytest\n"
        f"HOW: dispatch strictly on `oracle_verification_argv`"
    )
    assert row["exit"] == 0
    assert not any(Path(str(part)).name == "pytest" for part in row["argv"]), row[
        "argv"
    ]
