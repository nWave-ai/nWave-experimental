# @feature-des-refactor-fixer-swarm
"""Regression AT -- a refusal names the command that RAN, and whoever chose it.

RCA (bugfix-refusal-names-none, reproduced against a synthetic repo). An
operator runs `des refactor --pile techdebt.md` with NO `--agent-cmd`, the
drain is blocked at the entry gate, and they read:

    the command you passed to --agent-cmd (None) finished without emitting any
    recognized entry-gate verdict token

They passed nothing. The message (a) names `None` instead of the command that
actually ran, and (b) attributes to them a choice the SYSTEM made, sending them
to look for an option they never wrote -- a direct violation of GDP-3's WHAT,
which must name the real subject.

Mechanism: `des.cli.refactor.main` resolves the default actuator into a LOCAL
`agent_cmd` and dispatches THAT (`_resolve_default_agent_cmd`), but built the
refusal context from the RAW `args.agent_cmd`, which is `None` on that path.
Verified by execution before the fix: `_refusal_context(Path.cwd(), None,
GitWorktreeAdapter())` returned `RefusalContext.agent_cmd = None`.

The same line hid a second defect. That `None` never exploded because
`_repo_relative_paths_in(None)` calls `shlex.split(None)`, which raises
`ValueError` (verified by execution -- it does NOT block on stdin), and that
`ValueError` was swallowed by an `except` written for a DIFFERENT cause, whose
own comment reads "an unbalanced quote leaves no token resolvable". A wrong
TYPE was silently treated as malformed operator input: GDP-6 silent-wrong. Its
user-visible consequence is nil TODAY only by accident -- the resolved actuator
is an ABSOLUTE path, which that function excludes by design anyway, so the
outcome coincides through an exception rather than through a decision. A future
relative default would go silently undetectable.

Driving surface (Mandate 16, default IN-PROCESS): Layer 2 in-process via
`RefactorSwarmComposition.call_refactor_main_in_process[_without_agent_cmd]` --
drives the REAL `des.cli.refactor.main` entry, no interpreter fork, reusing the
production-composition harness `tests/des/refactor/` already established
(Pillar 3) rather than re-deriving a parallel fixture. `capsys` captures the
CLI's OWN stdout/stderr on the same call that produced the refusal -- the exact
surface an operator is looking at. Every repo, stub and script is built fresh
under `tmp_path`; nothing here ever points at this project's own tree, and the
stubbed headless assistant means no real fixer and no network call is involved.

The expected command is read back from PRODUCTION (`resolve_installed_actuator`
+ `sys.executable`), never re-typed as a literal, so a reworded or re-shaped
default cannot silently drift away from what this file asserts.

RED-for-right-reason: the entry gate, the default-actuator resolution and the
refusal rendering are ALL already implemented, so each assertion below is
reached and fails on a genuine observable -- a refusal naming `None` and
blaming the operator -- never a collection/import/fixture error.

covers: bug-observable (bugfix-refusal-names-none)
"""

from __future__ import annotations

import pytest

from des.cli.refactor import _repo_relative_paths_in

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# keeps the runtime freshness gate's one-shot stderr event out of every test's
# captured output below regardless of collection/execution order (mirrors
# tests/des/refactor/test_slice_01_observability.py's precedent).
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401
from des.runtime.interpreter import resolve_installed_actuator
from tests.des.refactor.composition import RefactorSwarmComposition


pytestmark = pytest.mark.acceptance


#: The one pending item every arrangement seeds.
_ITEM_ID = "TD-001"

#: Ways of saying "YOU chose this command". A refusal about a command the
#: operator never typed must carry NONE of them. Enumerated rather than one
#: bare phrase so the failure message can tell an implementer exactly which
#: vocabulary is being rejected, and so a rewording cannot quietly re-blame.
_BLAMES_THE_OPERATOR_FORMS = (
    "you passed",
    "you gave",
    "you supplied",
    "you specified",
    "the command you",
    "your --agent-cmd",
)

#: ...and ways of saying "DES chose it for you". The refusal for a
#: system-resolved actuator must carry at least one, so the operator learns
#: where the command came from instead of hunting for an option they never
#: wrote.
_NAMES_THE_SYSTEM_AS_CHOOSER_FORMS = (
    "resolved for you",
    "des refactor resolved",
    "resolved its own",
    "no --agent-cmd was given",
    "no --agent-cmd given",
)


def _arrange_repo_with_one_pending_item(tmp_path) -> RefactorSwarmComposition:
    """A hermetic scratch repo holding one grammar-valid pending item and one
    committed passing toy test -- the arrangement that lets a drain get all the
    way to the entry gate before it is blocked."""
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)
    return composition


def _terminal(capsys) -> str:
    """Everything the operator sees from one run -- stdout and stderr are one
    terminal to them, so they are read as one."""
    captured = capsys.readouterr()
    return (captured.out + captured.err).strip()


def _expected_default_actuator() -> str:
    """The actuator path `des refactor` resolves when no `--agent-cmd` is
    given, read out of production rather than re-typed here."""
    actuator = resolve_installed_actuator()
    assert actuator is not None, (
        "arrangement integrity: this checkout carries no scripts/"
        "refactor_agent.py, so `des refactor` would refuse for a DIFFERENT "
        "reason (actuator-not-found) and this scenario cannot reproduce the "
        "defect at all"
    )
    return str(actuator)


def _missing(lowered: str, accepted_forms: tuple[str, ...]) -> bool:
    return not any(form in lowered for form in accepted_forms)


# --- The diagnosed defect: the refusal names what RAN, not None -------------


def test_the_refusal_names_the_dispatched_command_not_none(
    tmp_path, capsys, monkeypatch
):
    """Given an operator who ran `des refactor` WITHOUT `--agent-cmd`, so the
    system resolved and dispatched its own actuator, When the drain is blocked
    because that actuator emitted no recognized entry-gate verdict, Then the
    refusal names the command that ACTUALLY ran and never the string `None`.

    `None` is not a command an operator can inspect, re-run or fix -- it is the
    absence of the very argument the message tells them to look at, so the WHAT
    names nothing at all.

    CONTRACT_SHAPE: bounded-change
    """
    composition = _arrange_repo_with_one_pending_item(tmp_path)
    for (
        name,
        value,
    ) in composition.env_making_the_default_actuator_emit_no_verdict().items():
        monkeypatch.setenv(name, value)

    exit_code = composition.call_refactor_main_in_process_without_agent_cmd()
    output = _terminal(capsys)

    assert output != "", (
        "a blocked drain must tell the operator something -- got completely "
        f"empty stdout+stderr (exit_code={exit_code})"
    )
    assert "None" not in output, (
        "the refusal must never name `None` as the command it ran: the "
        "operator passed no --agent-cmd, so `None` is the ABSENCE of the "
        "argument the message points them at, and there is nothing there for "
        f"them to inspect or fix; got: {output!r}"
    )
    assert _expected_default_actuator() in output, (
        "the refusal must name the command the run ACTUALLY dispatched -- the "
        "actuator des refactor resolved when no --agent-cmd was given -- so "
        "the operator can look at the thing that produced this outcome; "
        f"expected {_expected_default_actuator()!r} inside: {output!r}"
    )


def test_the_refusal_does_not_blame_the_operator_for_a_command_the_system_chose(
    tmp_path, capsys, monkeypatch
):
    """Given the same run with no `--agent-cmd`, When the drain refuses, Then
    the refusal attributes the command to DES, never to the operator, and still
    names `--agent-cmd` as the override -- so the reader learns where the
    command came from and how to replace it, instead of hunting for an option
    they never wrote.

    Distinguishability from the operator-passed refusal is the point: a fix
    that merely swapped in the right command string while keeping "the command
    you passed to --agent-cmd" would still send the reader looking for their
    own mistake in a choice that was never theirs.

    CONTRACT_SHAPE: bounded-change
    """
    composition = _arrange_repo_with_one_pending_item(tmp_path)
    for (
        name,
        value,
    ) in composition.env_making_the_default_actuator_emit_no_verdict().items():
        monkeypatch.setenv(name, value)

    composition.call_refactor_main_in_process_without_agent_cmd()
    output = _terminal(capsys)
    lowered = output.lower()

    blaming = [form for form in _BLAMES_THE_OPERATOR_FORMS if form in lowered]
    assert not blaming, (
        "the refusal must not attribute the dispatched command to the "
        "operator: they passed no --agent-cmd at all, so being told it is "
        "what THEY passed sends them looking for an option they never wrote; "
        f"offending phrase(s) {blaming!r} in: {output!r}"
    )
    assert not _missing(lowered, _NAMES_THE_SYSTEM_AS_CHOOSER_FORMS), (
        "the refusal must say the command was resolved BY des refactor, so "
        "the operator learns where it came from; accepted forms "
        f"{_NAMES_THE_SYSTEM_AS_CHOOSER_FORMS!r}, got: {output!r}"
    )
    assert "--agent-cmd" in output, (
        "the refusal must still name --agent-cmd as the way to override the "
        f"resolved actuator -- that is the HOW; got: {output!r}"
    )


# --- The no-regression companion: an operator-passed command is still theirs -


def test_a_command_the_operator_did_pass_is_still_attributed_to_them(tmp_path, capsys):
    """Given an operator who DID pass `--agent-cmd`, When the same entry-gate
    refusal renders, Then it names their command verbatim AND still says it is
    the one they passed.

    The companion to the two above: telling the two origins apart is the whole
    fix, so a change that stopped attributing an operator's OWN command to them
    would be the same defect with the sides swapped.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = _arrange_repo_with_one_pending_item(tmp_path)
    agent_cmd = composition.agent_cmd_emitting_no_recognized_verdict()

    composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    output = _terminal(capsys)
    lowered = output.lower()

    assert agent_cmd in output, (
        "an operator who passed --agent-cmd must see their own command named "
        f"verbatim; expected {agent_cmd!r} inside: {output!r}"
    )
    assert not _missing(lowered, _BLAMES_THE_OPERATOR_FORMS), (
        "a command the operator really did pass must still be attributed to "
        "them -- otherwise the refusal has simply moved the mis-attribution "
        f"to the other path; accepted forms {_BLAMES_THE_OPERATOR_FORMS!r}, "
        f"got: {output!r}"
    )


# --- The second defect at the same line: a wrong TYPE is not malformed input -


def test_a_non_string_command_is_refused_loudly_never_read_as_an_unbalanced_quote():
    """Given `_repo_relative_paths_in`, the shadowed-fixer detection's token
    reader, When it is handed something that is not a command string at all,
    Then it fails LOUD -- it must never be absorbed by the `except ValueError`
    that exists for the ONE cause that clause declares (an unbalanced quote in
    a real command), because a wrong type answering "no repo-relative paths"
    silently disables the detection for every caller (GDP-6 silent-wrong).

    The declared cause is pinned alongside it: a genuinely unbalanced quote
    still resolves to no paths, exactly as before. Narrowing the catch must not
    turn an operator's malformed command into a crash.

    Asserted at this seam rather than through the CLI deliberately, and the
    reason is worth stating: on today's default path the resolved actuator is
    an ABSOLUTE path, which this function excludes by design anyway, so the two
    behaviours produce the SAME user-visible outcome. There is no operator
    observable to drive -- the honest test is the one that pins the decision
    instead of the coincidence.

    CONTRACT_SHAPE: bounded-change
    """
    assert _repo_relative_paths_in("sh -c 'unbalanced") == (), (
        "the declared cause must keep behaving as its own comment says: an "
        "unbalanced quote leaves no token resolvable, so nothing is claimed "
        "about any of them"
    )

    with pytest.raises(TypeError) as raised:
        _repo_relative_paths_in(None)  # type: ignore[arg-type]

    message = str(raised.value)
    assert "None" in message or "NoneType" in message, (
        "the loud failure must name what it actually received, so a reader "
        f"can see it was a type error and not a quoting error; got: {message!r}"
    )


# --- Arrangement integrity: the stubbed default really is what ran ----------


def test_the_default_actuator_arrangement_dispatches_the_resolved_actuator(
    tmp_path, capsys, monkeypatch
):
    """Given the no-`--agent-cmd` arrangement, When the drain runs, Then the
    stubbed headless assistant really was invoked by the resolved actuator --
    proving the scenarios above exercise the DEFAULT dispatch path and are not
    passing against some earlier refusal that never reached the entry gate.

    Without this witness, a refusal raised before dispatch (no actuator found,
    an unresolvable probe) could satisfy the assertions above for the wrong
    reason. It asserts nothing about the refusal's WORDING -- that is the
    scenarios' job -- so it holds both before and after the fix, which is what
    makes it evidence that they were RED for the right reason.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = _arrange_repo_with_one_pending_item(tmp_path)
    for (
        name,
        value,
    ) in composition.env_making_the_default_actuator_emit_no_verdict().items():
        monkeypatch.setenv(name, value)

    exit_code = composition.call_refactor_main_in_process_without_agent_cmd()
    output = _terminal(capsys)

    assert exit_code != 0, (
        "a drain blocked at the entry gate is a refusal, not a quiet success; "
        f"got exit_code={exit_code}, output: {output!r}"
    )
    assert composition.text_the_headless_cli_received(), (
        "the resolved actuator must actually have dispatched the stubbed "
        "headless assistant -- otherwise this scenario never reached the "
        "entry gate and the refusal above is about something else entirely"
    )
    assert composition.pile_contains(_ITEM_ID), (
        f"{_ITEM_ID} must remain pending in techdebt.md -- a drain refused at "
        "the entry gate must never move the item as a side effect"
    )
