"""The inert shim must speak the DES role protocol, by REPLAY and only by replay.

Each DES step spawns one `claude --agent <role> --json-schema <schema>` turn per
role it buys, and reads a `structured_output` object back.  Answering those with
the single-delivery payload the rest of `inert_claude` builds refused the whole
nWave arm with `ModelEnvelopeUnavailable` (measured 2026-09-05: the offline chain
stopped at its `campaign` stage for exactly that).

Which process spawns the turn changed on 2026-09-06 and nothing else did:
ADR-SSOT-002 Section 4b retires `des dispatch` as an orchestrator, so the turns
now arrive from `des po`, `des design`, `des oracle`, `des craft` and
`des verify`, one process each.  The protocol on the wire is the same, which is
why every property below is stated over ONE turn and survives the move.

The two properties worth naming, because a replay that has neither is a fixture
pretending to be evidence:

* what comes back is the RECORDED bytes, unchanged -- so `extract_model_run`
  reads in the replay the document it read in the run;
* a role with no recorded turn is refused LOUD, never answered plausibly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    extract_model_run,
)
from scripts.analysis.k4 import inert_claude


BUNDLED_CASE = (
    Path(inert_claude.__file__).resolve().parent
    / "replay"
    / inert_claude._DEFAULT_REPLAY_CASE
)

#: The order the STEPS buy them in for one delivered value, measured at
#: `steps@6d817bc91`: `des oracle` buys the acceptance author and its reviewer,
#: `des verify` buys the whole-diff reviewer and the source-blind examiner.
RUNNER_ROLE_ORDER = (
    "nw-product-owner",
    "nw-solution-architect",
    "nw-acceptance-designer",
    "nw-acceptance-designer-reviewer",
    "nw-software-crafter",
    "nw-software-crafter-reviewer",
    "nw-user-examiner",
)


def _record(role: str, sequence: int, envelope: dict | str) -> dict:
    stdout = envelope if isinstance(envelope, str) else json.dumps(envelope)
    return {
        "run_id": "test",
        "sequence": sequence,
        "role_id": role,
        "prompt": f"prompt for {role} #{sequence}",
        "argv": None,
        "outcome": "accepted",
        "diagnostic": "",
        "exit_status": 0,
        "retry_safe": False,
        "provider_stdout": stdout,
        "provider_stderr": None,
        "raised": None,
        "started_at": "2026-09-05T00:00:00Z",
        "ended_at": "2026-09-05T00:00:01Z",
        "duration_seconds": 1.0,
    }


def _envelope(outcome: str = "accepted", diagnostic: str = "d") -> dict:
    return {
        "type": "result",
        "is_error": False,
        "session_id": "s",
        "structured_output": {"outcome": outcome, "diagnostic": diagnostic},
    }


def _case(tmp_path: Path, records: list[tuple[str, dict | str]]) -> Path:
    directory = tmp_path / "case"
    directory.mkdir(parents=True, exist_ok=True)
    for index, (role, envelope) in enumerate(records, start=1):
        (directory / f"{index:02d}-{role}.json").write_text(
            json.dumps(_record(role, index, envelope)), encoding="utf-8"
        )
    return directory


def _effect(case: Path, stem: str, diff: str) -> None:
    """One recorded workspace effect, in the carrier the case actually uses."""
    (case / f"{stem}{inert_claude._PATCH_SUFFIX}").write_text(
        json.dumps({"source_commit": "test", "diff": diff}), encoding="utf-8"
    )


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q"], cwd=workspace, check=True, stdin=subprocess.DEVNULL
    )
    return workspace


def _shim(
    role: str,
    *,
    case: Path,
    workspace: Path,
    config_dir: Path,
    prompt: str = "the question asked now",
) -> subprocess.CompletedProcess[str]:
    """One turn through a REAL process, with the prompt on stdin as the runner sends it."""
    return subprocess.run(
        [
            sys.executable,
            str(Path(inert_claude.__file__).resolve()),
            "-p",
            "--agent",
            role,
            "--output-format",
            "json",
        ],
        cwd=workspace,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(workspace),
            "K4_INERT_REPLAY_DIR": str(case),
            "CLAUDE_CONFIG_DIR": str(config_dir),
        },
    )


class TestTheRecordedEnvelopeComesBackUnchanged:
    def test_the_requested_role_answers_with_the_recorded_stdout_verbatim(
        self, tmp_path: Path
    ) -> None:
        recorded = json.dumps(_envelope(diagnostic="the recorded judgment"))
        case = _case(tmp_path, [("nw-product-owner", recorded)])

        done = _shim(
            "nw-product-owner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode == 0, done.stderr
        assert done.stdout == recorded

    def test_a_repeated_role_replays_its_turns_in_recorded_order(
        self, tmp_path: Path
    ) -> None:
        case = _case(
            tmp_path,
            [
                ("nw-software-crafter", _envelope(diagnostic="first")),
                ("nw-software-crafter", _envelope(diagnostic="second")),
            ],
        )
        workspace = _workspace(tmp_path)
        config_dir = tmp_path / "cfg"

        seen = [
            json.loads(
                _shim(
                    "nw-software-crafter",
                    case=case,
                    workspace=workspace,
                    config_dir=config_dir,
                ).stdout
            )["structured_output"]["diagnostic"]
            for _ in range(2)
        ]

        assert seen == ["first", "second"]

    def test_two_workspaces_count_their_turns_independently(
        self, tmp_path: Path
    ) -> None:
        """Two concurrent arms share one replay case and must not share a counter."""
        case = _case(
            tmp_path,
            [
                ("nw-software-crafter", _envelope(diagnostic="first")),
                ("nw-software-crafter", _envelope(diagnostic="second")),
            ],
        )
        workspace = _workspace(tmp_path)

        first_of_each = [
            json.loads(
                _shim(
                    "nw-software-crafter",
                    case=case,
                    workspace=workspace,
                    config_dir=tmp_path / arm,
                ).stdout
            )["structured_output"]["diagnostic"]
            for arm in ("cfg-a", "cfg-b")
        ]

        assert first_of_each == ["first", "first"]


class TestAnUnrecordedTurnIsRefusedLoud:
    def test_a_role_with_no_record_exits_non_zero_and_names_it(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-product-owner", _envelope())])

        done = _shim(
            "nw-user-examiner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "nw-user-examiner" in done.stderr
        assert (
            "WHAT:" in done.stderr and "WHY:" in done.stderr and "HOW:" in done.stderr
        )

    def test_a_role_called_more_often_than_it_was_recorded_is_refused(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-software-crafter", _envelope())])
        workspace = _workspace(tmp_path)
        config_dir = tmp_path / "cfg"

        _shim(
            "nw-software-crafter",
            case=case,
            workspace=workspace,
            config_dir=config_dir,
        )
        second = _shim(
            "nw-software-crafter",
            case=case,
            workspace=workspace,
            config_dir=config_dir,
        )

        assert second.returncode != 0
        assert second.stdout == ""
        assert "records 1 turn(s)" in second.stderr

    def test_a_record_that_carries_no_envelope_is_refused_not_answered_empty(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "case"
        directory.mkdir()
        raised = _record("nw-product-owner", 1, "")
        raised["provider_stdout"] = None
        raised["raised"] = "OSError"
        (directory / "01-nw-product-owner.json").write_text(
            json.dumps(raised), encoding="utf-8"
        )

        done = _shim(
            "nw-product-owner",
            case=directory,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "no provider_stdout" in done.stderr


class TestTheRecordedWorkspaceEffect:
    def test_the_sibling_patch_is_applied_in_the_runners_cwd(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-acceptance-designer", _envelope())])
        _effect(
            case,
            "01-nw-acceptance-designer",
            "diff --git a/oracle.txt b/oracle.txt\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/oracle.txt\n"
            "@@ -0,0 +1 @@\n"
            "+recorded oracle\n",
        )
        workspace = _workspace(tmp_path)

        done = _shim(
            "nw-acceptance-designer",
            case=case,
            workspace=workspace,
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode == 0, done.stderr
        assert (workspace / "oracle.txt").read_text(encoding="utf-8") == (
            "recorded oracle\n"
        )

    def test_a_patch_that_cannot_apply_refuses_instead_of_answering_accepted(
        self, tmp_path: Path
    ) -> None:
        """An envelope without its bytes would judge a workspace that never got them."""
        case = _case(tmp_path, [("nw-software-crafter", _envelope())])
        _effect(
            case,
            "01-nw-software-crafter",
            "diff --git a/absent.txt b/absent.txt\n"
            "--- a/absent.txt\n"
            "+++ b/absent.txt\n"
            "@@ -1 +1 @@\n"
            "-was never here\n"
            "+replaced\n",
        )

        done = _shim(
            "nw-software-crafter",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "git apply" in done.stderr


class TestTheBundledCase:
    def test_it_records_every_role_the_runner_calls_for_one_value(self) -> None:
        by_role = inert_claude._recorded_turns(BUNDLED_CASE)

        assert tuple(sorted(by_role)) == tuple(sorted(RUNNER_ROLE_ORDER))

    @pytest.mark.parametrize("role", RUNNER_ROLE_ORDER)
    def test_each_recorded_envelope_survives_the_runners_own_reader(
        self, role: str
    ) -> None:
        """The consumer, not a second parser: `extract_model_run` is the one reader."""
        record = inert_claude._select_record(BUNDLED_CASE, role, 0)
        raw = inert_claude._recorded_envelope(record)
        envelope, migration = inert_claude._replay_envelope(BUNDLED_CASE, record)

        assert raw == inert_claude._recorded_envelope(record)
        if role == "nw-solution-architect":
            assert migration == "add-empty-authority-locator"
            assert envelope != raw
        else:
            assert migration is None
            assert envelope == raw

        run = extract_model_run(envelope, role_id=role)

        assert run.exit_status == 0
        assert run.accounting is not None

    def test_the_examiner_turn_replays_the_rejection_that_was_recorded(self) -> None:
        """No real run has recorded an ACCEPTED examiner turn; the replay says so."""
        record = inert_claude._select_record(BUNDLED_CASE, "nw-user-examiner", 0)

        run = extract_model_run(
            inert_claude._recorded_envelope(record), role_id="nw-user-examiner"
        )

        assert run.outcome.value == "rejected"


class TestACaseRecordedOnAnotherRepositoryIsRefusedAtTheFirstTurn:
    """Measured 2026-09-05: four roles answered happily in a foreign workspace.

    The K4 campaign's workspace is a healthchecks clone and the only recorded
    runs deliver against nwave-dev.  A create-only diff applies in ANY tree, so
    the mismatch stayed invisible until the crafter's modifying diff failed on
    turn five, reported as an opaque failed turn with four turns already spent.
    """

    def test_an_unknown_base_commit_refuses_before_any_envelope_is_emitted(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-product-owner", _envelope())])
        (case / "base-commit.txt").write_text(
            "0" * 40 + "\nrecorded against a tree this workspace never had\n",
            encoding="utf-8",
        )

        done = _shim(
            "nw-product-owner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "does not carry" in done.stderr

    def test_a_base_file_that_names_no_commit_degrades_loud_not_silent(
        self, tmp_path: Path
    ) -> None:
        """A claim that FAILED is not an absent claim; admitting it reopens the hole."""
        case = _case(tmp_path, [("nw-product-owner", _envelope())])
        (case / "base-commit.txt").write_text("\n\n", encoding="utf-8")

        done = _shim(
            "nw-product-owner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "names no commit" in done.stderr

    def test_a_base_file_that_cannot_be_decoded_degrades_loud(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-product-owner", _envelope())])
        (case / "base-commit.txt").write_bytes(b"\xff\xfe not utf-8 \x80")

        done = _shim(
            "nw-product-owner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode != 0
        assert done.stdout == ""
        assert "cannot be read" in done.stderr

    def test_a_case_declaring_no_base_makes_no_claim_and_is_admitted(
        self, tmp_path: Path
    ) -> None:
        case = _case(tmp_path, [("nw-product-owner", _envelope())])

        done = _shim(
            "nw-product-owner",
            case=case,
            workspace=_workspace(tmp_path),
            config_dir=tmp_path / "cfg",
        )

        assert done.returncode == 0, done.stderr
