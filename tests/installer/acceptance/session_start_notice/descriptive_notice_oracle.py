"""Acceptance support: the injected notice is guarded as DESCRIPTIVE.

Authority: docs/product/architecture/brief.md#The Injected Notice Is Guarded As
Descriptive.

This module drives the SAME published driving port as its two siblings -- the
installed Claude Code SessionStart command, discovered out of the sandbox
``settings.json`` and executed as a real process -- and projects three
observations out of it:

1. The shipped notice is injected, and on that invocation the hook REPORTS that
   the descriptive guard RAN and over how many declared phrases it decided. An
   unfired guard is not evidence, so a green run must be distinguishable from a
   guard that was never invoked.

2. When the installed notice is made to COMMAND the route, the hook REFUSES the
   injection and quotes the offending phrase back.

3. When the installed notice drops the sentence that keeps working directly
   open as a legitimate answer, the hook REFUSES and names that missing
   property. Measured necessary: the words "working directly" survive that
   deletion (they also open the third route entry), so a whole-text presence
   check would not discriminate -- the property is sentence-level.

THE ORACLE NEVER IMPORTS THE FORBIDDEN SET. It restates exactly ONE phrase --
the one it APPENDS to build the commanding stimulus -- and reads the offence
back out of the hook's own refusal text, asserting the quoted phrase is the
phrase it introduced. A drifted production declaration therefore cannot silently
agree with a drifted expectation. Nothing here imports a production symbol,
reads a template from the source tree, or inspects a handler module.

THE STIMULI TOUCH NO TRACKED FILE. Both edit every INSTALLED copy of the notice
discovered under the sandbox ``HOME``, never the repository template, so they
reach the real subject by the same route a drifting installed tree would -- the
route that the install-time section guard provably cannot see.

AGREEMENT WITH THE SIZE OBSERVATION. That sibling reads ``bytes=``, ``tokens=``
and ``permitted=`` as labels occurring EXACTLY ONCE in this same stderr, so
every token asserted here is checked to introduce none of those three
substrings. The commanding stimulus is also deliberately SMALL, so it stays
under the declared size ceiling and the size guard cannot stand in for this one.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from tests.installer.acceptance.session_start_notice.session_journey import (
    environment_for,
    injected_context,
    installed_session_start_registration,
    process_diagnostic,
    run_cli,
    run_installed_hook,
)


#: The installed name of the shipped notice, as an artefact on disk. This is a
#: stimulus target, not a production import.
NOTICE_TEMPLATE_FILENAME = "delivery-route-fragment.md"

#: The ONE commanding phrase this oracle restates. It is introduced by the
#: stimulus below and must be quoted back by the refusal; the remaining members
#: of the production declaration are deliberately unknown here.
INTRODUCED_COMMANDING_PHRASE = "You must"

#: The sentence carrying that phrase. Kept to one short line so the enlarged
#: notice stays well inside the declared size ceiling -- otherwise the oversize
#: guard, not the descriptive guard, could produce the refusal.
COMMANDING_SENTENCE = "You must record the delivery route before answering."

#: The shipped sentence that keeps working directly open as a legitimate answer.
#: Deleting it leaves the words "working directly" present elsewhere in the
#: notice, which is exactly why the guarded property is sentence-level.
LEGITIMACY_SENTENCE = (
    "Working directly remains open as an answer when little has to survive; "
    "when you take it, say so."
)

#: The words the legitimacy refusal must name, so an operator learns WHICH
#: property went missing rather than that "the notice is wrong".
LEGITIMACY_SUBJECT = "working directly"

#: The guard states that it ran, and over how many declared phrases. The label
#: introduces none of the size oracle's three labels.
PHRASES_CHECKED = re.compile(r"\bphrases-checked=(\d+)\b")

#: Labels owned by the sibling size observation. Each must occur exactly once in
#: this same stderr, so nothing added here may introduce another occurrence.
SIZE_LABELS = ("bytes=", "tokens=", "permitted=")

#: Refusal keeps the handler's established WHAT/WHY/HOW shape: these two are new
#: members of that family, not a new algebra.
REFUSAL_MARKERS = ("WHAT:", "WHY:", "HOW:")


def _installed_notice_copies(system_home: Path) -> list[Path]:
    return [
        copy
        for copy in sorted(system_home.rglob(NOTICE_TEMPLATE_FILENAME))
        if copy.is_file()
    ]


def _make_installed_notices_command(system_home: Path) -> list[str]:
    """Append one commanding sentence to every INSTALLED copy of the notice.

    Returns the touched paths so an empty list -- which would make the falsifier
    vacuous -- stays visible in the observation.
    """
    touched: list[str] = []
    for copy in _installed_notice_copies(system_home):
        text = copy.read_text(encoding="utf-8")
        copy.write_text(f"{text.rstrip()}\n{COMMANDING_SENTENCE}\n", encoding="utf-8")
        touched.append(str(copy.relative_to(system_home)))
    return touched


def _delete_legitimacy_sentence(system_home: Path) -> tuple[list[str], bool]:
    """Remove the still-open sentence from every INSTALLED copy of the notice.

    The template hard-wraps, so the sentence is matched after flattening
    whitespace and then rewritten flat. Also reports whether the words "working
    directly" SURVIVE the deletion, because the observation is only meaningful
    while they do.
    """
    touched: list[str] = []
    subject_survives = False
    for copy in _installed_notice_copies(system_home):
        flattened = " ".join(copy.read_text(encoding="utf-8").split())
        if LEGITIMACY_SENTENCE not in flattened:
            continue
        remainder = " ".join(flattened.replace(LEGITIMACY_SENTENCE, " ").split())
        copy.write_text(f"{remainder}\n", encoding="utf-8")
        touched.append(str(copy.relative_to(system_home)))
        subject_survives = LEGITIMACY_SUBJECT in remainder.lower()
    return touched, subject_survives


def _sole_phrase_count(stderr: str) -> int | None:
    found = PHRASES_CHECKED.findall(stderr)
    if len(found) != 1:
        return None
    return int(found[0])


def _refusal_is_wellformed(process: Any) -> bool:
    """Refusal: nothing on stdout, WHAT/WHY/HOW on stderr, and never a block."""
    return (
        process is not None
        and process.stdout.strip() == ""
        and process.returncode == 0
        and all(marker in process.stderr for marker in REFUSAL_MARKERS)
    )


def observe_descriptive_notice() -> dict[str, Any]:
    """Run the journey three times -- shipped, commanding, stripped."""
    with tempfile.TemporaryDirectory(prefix="nwave-descriptive-notice-") as temporary:
        root = Path(temporary)
        system_home = root / "system-home"
        agents_home = root / "selected-nwave-home"
        project_root = root / "some-user-project"
        for directory in (system_home, agents_home, project_root):
            directory.mkdir()
        environment = environment_for(system_home=system_home, agents_home=agents_home)

        install = run_cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        enable = run_cli(environment, project_root, "project", "enable", "--yes")

        settings_path = system_home / ".claude" / "settings.json"
        command: str | None = None
        discovery_failure: str | None = None
        try:
            _registration, command = installed_session_start_registration(settings_path)
        except (
            LookupError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ) as error:
            discovery_failure = f"hook-discovery: {error}"

        def run() -> Any:
            if command is None:
                return None
            return run_installed_hook(command, environment, project_root)

        # 1. The notice as shipped: injected, with the guard reporting it ran.
        shipped = run()
        context, _shape, contract_failure = (
            injected_context(shipped)
            if shipped is not None
            else (None, {}, "hook command was not discoverable")
        )
        shipped_stderr = shipped.stderr if shipped is not None else ""
        phrases_checked = _sole_phrase_count(shipped_stderr)

        # 2. The same notice, made to COMMAND the route on disk.
        commanded_copies = _make_installed_notices_command(system_home)
        commanding = run()
        commanding_stderr = commanding.stderr if commanding is not None else ""

        # 3. A notice that no longer keeps working directly open. Rebuilt from a
        #    clean install so the two stimuli never compound into one verdict.
        reinstall = run_cli(
            environment, project_root, "install", "--yes", "--platform", "claude-code"
        )
        stripped_copies, subject_survives = _delete_legitimacy_sentence(system_home)
        stripped = run()
        stripped_stderr = stripped.stderr if stripped is not None else ""

        semantic = {
            "install_exit_code": install.returncode,
            "enable_exit_code": enable.returncode,
            "command_is_uniquely_discoverable": command is not None,
            # -- the shipped notice passes the guard, visibly -----------------
            "shipped_notice_is_injected": bool(context and context.strip()),
            # check:unfired-is-not-evidence -- a green run says the guard RAN.
            "report_states_the_guard_ran": phrases_checked is not None,
            "report_states_a_nonempty_declared_set": (
                phrases_checked is not None and phrases_checked >= 1
            ),
            # The verdict never contaminates the host contract.
            "verdict_stays_off_stdout": (
                shipped is not None and "phrases-checked=" not in shipped.stdout
            ),
            # Agreement with the sibling size observation: exactly one of each.
            "report_preserves_the_size_labels": all(
                shipped_stderr.count(label) == 1 for label in SIZE_LABELS
            ),
            # -- commanding wording is refused -------------------------------
            "the_commanding_stimulus_reached_an_installed_copy": bool(commanded_copies),
            "commanding_notice_is_refused": (
                commanding is not None and commanding.stdout.strip() == ""
            ),
            "commanding_refusal_does_not_block_the_session": (
                commanding is not None and commanding.returncode == 0
            ),
            "commanding_refusal_keeps_the_what_why_how_shape": _refusal_is_wellformed(
                commanding
            ),
            # The offence is QUOTED back, and it is the phrase introduced here.
            "commanding_refusal_quotes_the_introduced_phrase": (
                INTRODUCED_COMMANDING_PHRASE.lower() in commanding_stderr.lower()
            ),
            # -- losing the legitimacy sentence is refused -------------------
            "reinstall_exit_code": reinstall.returncode,
            "the_stripped_stimulus_reached_an_installed_copy": bool(stripped_copies),
            # Without this, a whole-text presence check would discriminate and
            # the sentence-level predicate would be unmotivated.
            "the_subject_survives_the_deletion": subject_survives,
            "stripped_notice_is_refused": (
                stripped is not None and stripped.stdout.strip() == ""
            ),
            "stripped_refusal_does_not_block_the_session": (
                stripped is not None and stripped.returncode == 0
            ),
            "stripped_refusal_keeps_the_what_why_how_shape": _refusal_is_wellformed(
                stripped
            ),
            "stripped_refusal_names_the_missing_property": (
                LEGITIMACY_SUBJECT in stripped_stderr.lower()
            ),
            # The two refusals are DISTINCT observations, not one generic error.
            "the_two_refusals_are_distinguishable": (
                commanding_stderr.strip() != ""
                and commanding_stderr.strip() != stripped_stderr.strip()
            ),
        }

        diagnostics: dict[str, Any] = {
            "install": process_diagnostic("install", install, ["install"]),
            "enable": process_diagnostic("enable", enable, ["project", "enable"]),
            "reinstall": process_diagnostic("reinstall", reinstall, ["install"]),
            "published_command": command,
            "hook_discovery_failure": discovery_failure,
            "host_contract_failure": contract_failure,
            "phrases_checked": phrases_checked,
            "commanded_installed_copies": commanded_copies,
            "stripped_installed_copies": stripped_copies,
        }
        for phase, process in (
            ("session-start-shipped", shipped),
            ("session-start-commanding", commanding),
            ("session-start-stripped", stripped),
        ):
            if process is not None:
                diagnostics[f"hook_{phase}"] = process_diagnostic(
                    phase, process, ["/bin/sh", "-c", command or ""]
                )

        return {"semantic": semantic, "diagnostics": diagnostics}


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "enable_exit_code": 0,
    "command_is_uniquely_discoverable": True,
    "shipped_notice_is_injected": True,
    "report_states_the_guard_ran": True,
    "report_states_a_nonempty_declared_set": True,
    "verdict_stays_off_stdout": True,
    "report_preserves_the_size_labels": True,
    "the_commanding_stimulus_reached_an_installed_copy": True,
    "commanding_notice_is_refused": True,
    "commanding_refusal_does_not_block_the_session": True,
    "commanding_refusal_keeps_the_what_why_how_shape": True,
    "commanding_refusal_quotes_the_introduced_phrase": True,
    "reinstall_exit_code": 0,
    "the_stripped_stimulus_reached_an_installed_copy": True,
    "the_subject_survives_the_deletion": True,
    "stripped_notice_is_refused": True,
    "stripped_refusal_does_not_block_the_session": True,
    "stripped_refusal_keeps_the_what_why_how_shape": True,
    "stripped_refusal_names_the_missing_property": True,
    "the_two_refusals_are_distinguishable": True,
}


if __name__ == "__main__":
    observation = observe_descriptive_notice()
    print(json.dumps(observation, indent=2, sort_keys=True, default=str))
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit("descriptive notice observation differs from contract")
