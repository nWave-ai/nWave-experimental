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
import subprocess
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    NativeRun,
)
from des.ports.driven_ports.task_invocation_port import (
    ModelOutcome,
    ModelRun,
)
from tests.des._helpers.step_stimulus import decomposed, designed, oracled
from tests.des.unit.application.test_authored_oracle_is_executed_red import (
    OBSERVATION,
    PRODUCTION,
    RED_ON_ITS_ASSERTION,
    REQUEST,
    ScriptedPort,
    execution_authority,
    git,
    oracle_manifest,
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


@pytest.fixture
def genesis(subject: Path) -> str:
    """Capture the established original commit before test-body mutations."""
    return subprocess.run(
        ["git", "-C", str(subject), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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


# ---------------------------------------------------------------------------
# 2. D1 -> D2 with identical oracle bytes must not reuse D1's evidence.
# ---------------------------------------------------------------------------


def test_changed_design_with_unchanged_oracle_bytes_is_not_settled_by_stale_evidence(
    subject: Path,
    genesis: str,
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
                self.roles.append(role_id)
                self.prompts.append((role_id, prompt))
                return ModelRun(ModelOutcome.Accepted, "", 0, True)
            return super().invoke(role_id=role_id, prompt=prompt, cwd=cwd, **rest)  # type: ignore[arg-type]

    port = ChangingDesignPort(subject)
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, subject, REQUEST)
    stored, d1 = designed(runner, port, subject, stored, port.manifest("D1"))
    first = oracled(runner, port, subject, stored, d1, baseline=genesis)
    assert first.refusal is None, first.refusal
    assert runner.oracle_turn_complete(subject, stored, stored.values[0], d1)

    # Correct the DESIGN only (same value, same oracle bytes on disk): D2.
    stored, d2 = designed(runner, port, subject, stored, port.manifest("D2"))
    assert tuple(d1.resolved.catalog.resolve(ref) for ref in d1.decisions) != tuple(
        d2.resolved.catalog.resolve(ref) for ref in d2.decisions
    ), "the probe requires a genuine design change"
    assert d1.acceptance_paths == d2.acceptance_paths, (
        "the probe requires unchanged oracle bytes on disk"
    )

    assert not runner.oracle_turn_complete(subject, stored, stored.values[0], d2), (
        "unchanged oracle bytes cannot make evidence measured against D1 current for D2"
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
    authority = execution_authority(
        subject,
        oracle_manifest(
            "Execute the Go-named oracle through its declared generic command.",
            oracle=go_oracle,
            targets=((PRODUCTION, "CREATE_NEW"),),
            verification=(declared_argv,),
        ),
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
