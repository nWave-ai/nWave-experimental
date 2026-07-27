"""Public Codex SessionStart walking skeleton for a bounded continuation run."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_module_in_process


OPERATOR_OUTCOME_ANCHOR = (
    "operator-sentinel: reconcile the Atlas release notes before handoff"
)
SECOND_OPERATOR_OUTCOME_ANCHOR = (
    "operator-sentinel: prepare the Beryl incident brief for review"
)
FUTURE_OUTCOME_SENTINEL = "operator-sentinel: this future work must not be offered yet"
MINIMUM_EXECUTABLE_ACTION_TOKENS = 2


def _public_command(name: str) -> Path:
    """Resolve the installed public executable beside this test interpreter."""
    command = Path(sys.executable).with_name(name)
    assert command.is_file(), f"public executable is unavailable: {command}"
    return command


def _isolated_codex_environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "NWAVE_AGENTS_HOME": str(home),
        }
    )
    return environment


def _isolated_claude_environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            # A host name in ambient state is not execution authority.
            "NWAVE_HOST": "codex",
        }
    )
    return environment


def _public_loop_state(
    command: Path, project: Path, environment: dict[str, str]
) -> dict[str, object]:
    """Capture durable loop facts only through the public operator surface."""
    snapshot: dict[str, object] = {}
    for operation in ("list", "inspect"):
        observed = subprocess.run(
            [
                str(command),
                "loop",
                operation,
                "--project",
                str(project),
                "--format",
                "json",
            ],
            cwd=project,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert observed.returncode == 0, (
            f"WHAT: public loop {operation} could not read the durable state around Codex SessionStart. "
            "WHY: hook text alone cannot prove that an offer left continued work and attestations untouched. "
            f"HOW: keep `des loop {operation}` available; stdout was {observed.stdout!r}; "
            f"stderr was {observed.stderr!r}."
        )
        snapshot[operation] = json.loads(observed.stdout)
    return snapshot


def _run_installed_session_start(
    command: str, project: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    argv = shlex.split(command)
    # Claude's installed hook command is a shell command with an inline
    # PYTHONPATH assignment; Codex's launcher is an argv-safe executable.
    use_shell = bool(
        command.lstrip().startswith("#")
        or (argv and "=" in argv[0] and not argv[0].startswith("/"))
    )
    return subprocess.run(
        command if use_shell else argv,
        cwd=project,
        env=environment,
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(project)}),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
        shell=use_shell,
    )


def _claude_session_start_commands(home: Path) -> list[str]:
    settings = json.loads(
        (home / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    return [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group.get("hooks", [])
        if hook.get("type") == "command" and isinstance(hook.get("command"), str)
    ]


def _arm_operator_outcome(
    command: Path,
    project: Path,
    environment: dict[str, str],
    *,
    idempotency_key: str,
    outcome: str,
    cooldown_seconds: int = 0,
    max_tokens: int = 1200,
) -> None:
    extra = ["--cooldown-seconds", str(cooldown_seconds)] if cooldown_seconds else []
    arm = subprocess.run(
        [
            str(command),
            "loop",
            "arm",
            "--project",
            str(project),
            "--loop",
            "standing",
            "--idempotency-key",
            idempotency_key,
            "--outcome",
            outcome,
            "--max-tokens",
            str(max_tokens),
            "--max-wall-seconds",
            "30",
            *extra,
            "--format",
            "json",
        ],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert arm.returncode == 0, (
        "WHAT: public loop control could not arm the declared operator outcome. WHY: a SessionStart "
        "must surface durable operator work, not a catalog/default phrase. HOW: preserve `--outcome` "
        f"when arming continued work; stderr was {arm.stderr!r}."
    )


@pytest.mark.negative_at
def test_installed_codex_sessionstart_registration_carries_explicit_codex_provenance(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R8
    """
    home = tmp_path / "codex-provenance-home"
    project = tmp_path / "operator-project"
    home.mkdir()
    project.mkdir()
    environment = _isolated_codex_environment(home)
    installed = subprocess.run(
        [str(_public_command("nwave-ai")), "install", "--platform", "codex", "--yes"],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert installed.returncode == 0, installed.stderr
    hooks = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "--host-provenance=codex" in command, (
        "WHAT: the installed Codex launcher does not pass explicit Codex provenance. "
        "WHY: shared SessionStart code must not infer authority from ambient environment. "
        "HOW: have only the Codex-owned launcher pass `--host-provenance=codex`."
    )


@pytest.mark.negative_at
def test_installed_claude_sessionstart_never_executes_due_codex_continued_work(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: R8

    A forged ambient host value cannot make a Claude SessionStart execute a
    Codex-only continued-work occurrence.
    """
    home = tmp_path / "claude-home"
    project = tmp_path / "operator-project"
    home.mkdir()
    project.mkdir()
    environment = _isolated_claude_environment(home)
    des = _public_command("des")
    installed = subprocess.run(
        [
            str(_public_command("nwave-ai")),
            "install",
            "--platform",
            "claude-code",
            "--yes",
        ],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert installed.returncode == 0, installed.stderr
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="claude-must-not-execute",
        outcome="operator-sentinel: Claude must not run this Codex continuation",
    )
    before = _public_loop_state(des, project, environment)
    commands = _claude_session_start_commands(home)
    assert commands, "installed Claude Code must register its SessionStart surface"
    for command in commands:
        started = _run_installed_session_start(command, project, environment)
        assert started.returncode == 0, started.stderr
    after = _public_loop_state(des, project, environment)
    assert after == before, (
        "WHAT: Claude SessionStart executed or attested Codex continued work. "
        "WHY: host-neutral SessionStart orientation has no authority to advance a "
        "Codex-only loop, even when NWAVE_HOST is forged. HOW: require explicit "
        "Codex launcher provenance before calling the continued-work bridge."
    )


@pytest.mark.walking_skeleton
def test_maintainer_receives_a_bounded_execution_receipt_from_installed_codex_sessionstart(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — ``OPERATOR_OUTCOME_ANCHOR`` is operator-authored,
    not a catalog/default phrase.
    Two independently authored due anchors each execute through their own installed session start;
    a future sentinel does not execute; a repeat observes the original durable receipt.

    # covers: R1 R2 R3 R4 R7
    """
    home = tmp_path / "codex-home"
    project = tmp_path / "operator-project"
    home.mkdir()
    project.mkdir()
    environment = _isolated_codex_environment(home)
    des = _public_command("des")

    install = subprocess.run(
        [str(_public_command("nwave-ai")), "install", "--platform", "codex", "--yes"],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert install.returncode == 0, (
        "WHAT: public Codex installation did not complete. WHY: an operator cannot receive a SessionStart "
        "opportunity from a hook that was never installed. HOW: install the SessionStart command; stderr was "
        f"{install.stderr!r}."
    )

    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="installed-codex-due-work",
        outcome=OPERATOR_OUTCOME_ANCHOR,
    )
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="installed-codex-future-work",
        outcome=FUTURE_OUTCOME_SENTINEL,
        cooldown_seconds=1800,
    )

    hooks = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    durable_before = _public_loop_state(des, project, environment)
    started = _run_installed_session_start(command, project, environment)
    durable_after = _public_loop_state(des, project, environment)

    assert started.returncode == 0, (
        "WHAT: installed Codex SessionStart did not remain available. WHY: a due opportunity must not block "
        f"the maintainer's new session. HOW: keep the hook fail-open; stderr was {started.stderr!r}."
    )
    public_text = started.stdout.lower()
    assert public_text.count("continued-work execution receipt:") == 1, (
        "WHAT: installed SessionStart did not report exactly one bounded execution receipt. WHY: an offer alone "
        "does not prove that Codex launched the generic loop engine. HOW: execute one due occurrence through "
        "the canonical loop tick and project its durable receipt into SessionStart output."
    )
    assert "1200" in public_text and "30" in public_text, (
        "WHAT: installed SessionStart omitted authorised limits. WHY: the maintainer must see that the executed "
        "work was bounded. HOW: project durable token and wall-time limits into the execution receipt."
    )
    assert OPERATOR_OUTCOME_ANCHOR.lower() in public_text, (
        "WHAT: installed SessionStart did not forward the exact operator-authored outcome anchor. WHY: a fixed "
        "catalog/default output can falsely look like a real run. HOW: forward `des loop arm --outcome` into the "
        "generic loop execution context and its receipt."
    )
    assert FUTURE_OUTCOME_SENTINEL.lower() not in public_text, (
        "WHAT: installed SessionStart executed the future-due sentinel. WHY: later work must remain unavailable "
        "until due. HOW: select only due work and leave future records out of execution."
    )
    before_attestations = durable_before["inspect"].get("attestations")
    after_attestations = durable_after["inspect"].get("attestations")
    assert (
        before_attestations == []
        and isinstance(after_attestations, list)
        and len(after_attestations) == 1
    ), (
        "WHAT: SessionStart did not advance exactly one public occurrence from an empty attestation population. "
        "WHY: a genuine bounded run needs one durable execution record, while a second record would overrun the "
        "single-due-unit contract. HOW: claim and execute exactly one selected due occurrence."
    )
    first_receipt = after_attestations[0]
    assert (
        isinstance(first_receipt, dict)
        and first_receipt.get("execution_receipt") is not None
        and first_receipt.get("resources", {}).get("consumed", {}).get("tokens", 0) > 0
    ), (
        "WHAT: SessionStart advanced state without an inspectable bounded execution receipt. WHY: a state change "
        "without measured work cannot prove the generic loop engine ran. HOW: persist and expose the tick receipt "
        "with consumed bounded resources through `des loop inspect`."
    )
    assert durable_before["list"].get("state", {}).get("future_due_count") == 1, (
        "WHAT: public loop listing did not expose the staged future unit before SessionStart. WHY: zero offers only "
        "prove absence when a real future population exists. HOW: preserve future records in `des loop list`."
    )

    replay = _run_installed_session_start(command, project, environment)
    replay_state = _public_loop_state(des, project, environment)
    replay_text = replay.stdout.lower()
    replay_attestations = replay_state["inspect"].get("attestations")
    assert replay.returncode == 0 and "replayed" in replay_text, (
        "WHAT: repeating the same Codex SessionStart did not identify the prior execution as a replay. WHY: hook "
        "retries must not launch duplicate bounded work. HOW: derive a stable SessionStart occurrence key and emit "
        "the canonical replay receipt."
    )
    assert replay_attestations == after_attestations, (
        "WHAT: a repeated SessionStart created a second occurrence receipt. WHY: replay must preserve one execution "
        "for one stable host occurrence. HOW: route retries through the generic loop engine idempotency boundary."
    )

    independent_project = tmp_path / "project-with-independent-due-work"
    independent_project.mkdir()
    _arm_operator_outcome(
        des,
        independent_project,
        environment,
        idempotency_key="installed-codex-independent-due-work",
        outcome=SECOND_OPERATOR_OUTCOME_ANCHOR,
    )
    independent_before = _public_loop_state(des, independent_project, environment)
    independent_offer = _run_installed_session_start(
        command, independent_project, environment
    )
    independent_after = _public_loop_state(des, independent_project, environment)
    independent_text = independent_offer.stdout.lower()
    assert (
        independent_offer.returncode == 0
        and independent_text.count("continued-work execution receipt:") == 1
    ), (
        "WHAT: installed SessionStart did not execute the independently armed operator outcome once. WHY: one "
        "catalog literal could otherwise satisfy a single-fixture witness. HOW: select and execute each project's "
        "durable operator-authored outcome."
    )
    assert (
        SECOND_OPERATOR_OUTCOME_ANCHOR.lower() in independent_text
        and OPERATOR_OUTCOME_ANCHOR.lower() not in independent_text
    ), (
        "WHAT: installed SessionStart did not distinguish the second operator outcome from the first. WHY: a "
        "fixed catalog/default phrase must never pass as a project-bound execution. HOW: pass the selected record's "
        "durable outcome to the generic loop engine rather than emitting a fixed literal."
    )
    assert (
        independent_before["inspect"].get("attestations") == []
        and len(independent_after["inspect"].get("attestations", [])) == 1
    ), (
        "WHAT: the independent SessionStart did not leave one durable execution receipt. WHY: each project's due "
        "work must be executed by its own generic loop occurrence. HOW: retain project-bound selection and attest "
        "the resulting receipt through the public inspection surface."
    )


def test_installed_codex_sessionstart_executes_a_staged_outcome_once_after_it_becomes_due(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — a staged operator outcome remains
    genuinely silent before its due time, then becomes one inspectable bounded
    receipt after it is due.

    # covers: R3 R4
    """
    home = tmp_path / "codex-home"
    project = tmp_path / "operator-project"
    home.mkdir()
    project.mkdir()
    environment = _isolated_codex_environment(home)
    des = _public_command("des")
    installed = subprocess.run(
        [str(_public_command("nwave-ai")), "install", "--platform", "codex", "--yes"],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert installed.returncode == 0, installed.stderr
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="installed-codex-staged-then-due",
        outcome="operator-sentinel: publish the due transition receipt",
        cooldown_seconds=2,
    )
    command = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))[
        "hooks"
    ]["SessionStart"][0]["hooks"][0]["command"]

    before_due = _public_loop_state(des, project, environment)
    early = _run_installed_session_start(command, project, environment)
    after_early = _public_loop_state(des, project, environment)
    assert (
        early.returncode == 0
        and "continued-work execution receipt:" not in early.stdout.lower()
    ), (
        "WHAT: Codex SessionStart executed staged work before its due time. "
        "WHY: a persisted future record must remain an honest no-execution result before it becomes eligible. "
        "HOW: select only records whose cooldown has expired."
    )
    assert (
        after_early == before_due and after_early["inspect"].get("attestations") == []
    ), (
        "WHAT: the pre-due SessionStart changed durable loop evidence. "
        "WHY: a zero-run before due must preserve the staged record and its empty receipt population. "
        "HOW: leave future work and attestations untouched until the due boundary passes."
    )

    time.sleep(2.05)
    due = _run_installed_session_start(command, project, environment)
    after_due = _public_loop_state(des, project, environment)
    attestations = after_due["inspect"].get("attestations")
    assert (
        due.returncode == 0
        and due.stdout.lower().count("continued-work execution receipt:") == 1
    ), (
        "WHAT: a persisted staged outcome did not become exactly one execution receipt after due time. "
        "WHY: future work that can never transition to eligible work is stranded rather than bounded. "
        "HOW: re-evaluate persisted cooldowns at SessionStart and execute one newly due occurrence through the canonical tick."
    )
    assert (
        isinstance(attestations, list)
        and len(attestations) == 1
        and attestations[0].get("execution_receipt") is not None
    ), (
        "WHAT: post-due SessionStart did not persist one inspectable bounded receipt. "
        "WHY: output alone cannot prove the staged outcome executed once. "
        "HOW: retain the canonical occurrence attestation with its execution receipt."
    )
    assert after_due["list"].get("state", {}).get("future_due_count") == 0, (
        "WHAT: an executed post-due outcome remained counted as future work. "
        "WHY: the public state must conserve the staged population as it transitions to its one receipt. "
        "HOW: remove the claimed occurrence from future-due state when its receipt is persisted."
    )
    replay = _run_installed_session_start(command, project, environment)
    assert (
        _public_loop_state(des, project, environment)["inspect"].get("attestations")
        == attestations
        and replay.returncode == 0
    ), (
        "WHAT: replaying the post-due SessionStart changed its receipt population. "
        "WHY: the due transition must execute exactly once even when the host retries the hook. "
        "HOW: preserve the existing occurrence idempotency boundary on the newly due path."
    )


@pytest.mark.negative_at
def test_installed_codex_sessionstart_replays_a_terminal_budget_receipt_for_newly_due_work(
    tmp_path: Path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — a later outcome that cannot pay for
    one bounded action receives one durable terminal receipt, and a host retry
    replays that receipt rather than manufacturing a fresh refusal.

    # covers: R3 R4 R6 R9
    """
    home = tmp_path / "codex-home"
    project = tmp_path / "terminal-budget-project"
    home.mkdir()
    project.mkdir()
    environment = _isolated_codex_environment(home)
    des = _public_command("des")
    installed = subprocess.run(
        [str(_public_command("nwave-ai")), "install", "--platform", "codex", "--yes"],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert installed.returncode == 0, installed.stderr
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="terminal-budget-primary",
        outcome="operator-sentinel: complete the primary bounded occurrence",
    )
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="terminal-budget-future",
        outcome="operator-sentinel: do not execute below one action budget",
        cooldown_seconds=2,
        max_tokens=MINIMUM_EXECUTABLE_ACTION_TOKENS - 1,
    )
    command = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))[
        "hooks"
    ]["SessionStart"][0]["hooks"][0]["command"]

    primary = _run_installed_session_start(command, project, environment)
    assert (
        primary.returncode == 0
        and "continued-work execution receipt:" in primary.stdout.lower()
    )
    after_primary = _public_loop_state(des, project, environment)
    assert after_primary["list"].get("state", {}).get("future_due_count") == 1, (
        "WHAT: the underfunded future outcome disappeared before its due boundary. "
        "WHY: the terminal-budget contract must be exercised by a real staged public record. "
        "HOW: retain the future record until it becomes eligible."
    )
    time.sleep(2.05)

    terminal = _run_installed_session_start(command, project, environment)
    after_terminal = _public_loop_state(des, project, environment)
    terminal_attestations = after_terminal["inspect"].get("attestations")
    assert (
        terminal.returncode == 0
        and "token_budget_exhausted" in terminal.stdout.lower()
        and "continued-work execution receipt:" not in terminal.stdout.lower()
    ), (
        "WHAT: newly due work with less than one action's token budget did not emit a terminal receipt. "
        "WHY: the maintainer needs an inspectable completion of the impossible request, not a hidden later refusal. "
        "HOW: persist and project one TOKEN_BUDGET_EXHAUSTED terminal receipt at the due boundary."
    )
    assert (
        isinstance(terminal_attestations, list)
        and len(terminal_attestations) == 2
        and terminal_attestations[-1].get("budget_verdict") == "EXHAUSTED"
        and terminal_attestations[-1].get("execution_receipt") is None
    ), (
        "WHAT: the due transition spent an action despite its insufficient token allowance. "
        "WHY: a terminal budget result must certify non-execution, not attach exhaustion after work ran. "
        "HOW: persist a distinct terminal receipt before invoking the bounded action."
    )
    retry = _run_installed_session_start(command, project, environment)
    after_retry = _public_loop_state(des, project, environment)
    assert retry.returncode == 0 and "replayed" in retry.stdout.lower(), (
        "WHAT: retrying the terminal SessionStart returned a fresh terminal refusal. "
        "WHY: host retries must replay the one durable terminal receipt. "
        "HOW: bind terminal results to the same occurrence idempotency key as executed results."
    )
    assert after_retry["inspect"].get("attestations") == terminal_attestations, (
        "WHAT: retrying the terminal SessionStart changed the durable receipt population. "
        "WHY: one newly due impossible occurrence has one terminal result. "
        "HOW: replay the persisted terminal receipt without creating or refusing another occurrence."
    )


@pytest.mark.negative_at
def test_sessionstart_offers_zero_when_only_future_work_exists(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — a future-only operator sentinel is a
    recognisable zero-offer population, not an absent or failed selection.

    # covers: R4 R7
    """
    project = tmp_path / "project-with-only-future-work"
    home = tmp_path / "codex-home"
    project.mkdir()
    home.mkdir()
    environment = _isolated_codex_environment(home)
    des = _public_command("des")
    _arm_operator_outcome(
        des,
        project,
        environment,
        idempotency_key="installed-codex-only-future-work",
        outcome=FUTURE_OUTCOME_SENTINEL,
        cooldown_seconds=1800,
    )
    future_only_before = _public_loop_state(des, project, environment)
    exit_code, stdout, stderr = run_module_in_process(
        "des.adapters.drivers.hooks.hook_router",
        "session-start",
        stdin_text=json.dumps({"hook_event_name": "SessionStart", "cwd": str(project)}),
        cwd=str(project),
    )
    future_only_after = _public_loop_state(des, project, environment)
    no_offer_text = f"{stdout}\n{stderr}".lower()
    assert exit_code == 0, (
        "WHAT: SessionStart with only future work blocked the maintainer. WHY: silence must mean no eligible work, "
        f"not a failed session. HOW: preserve the fail-open SessionStart path; stderr was {stderr!r}."
    )
    assert (
        no_offer_text.count("continued-work opportunity:") == 0
        and "unavailable" not in no_offer_text
    ), (
        "WHAT: future-only SessionStart did not produce a genuine zero-offer result. WHY: the operator must "
        "distinguish no eligible work from an unavailable selector. HOW: emit no opportunity only after canonical "
        "selection succeeds with no due record."
    )
    assert (
        future_only_before == future_only_after
        and future_only_after["inspect"].get("attestations") == []
    ), (
        "WHAT: SessionStart changed a project containing only future work. WHY: zero offers must leave the future "
        "record and completion evidence untouched. HOW: return no offer without claiming, ticking, or rewriting it."
    )
