"""Acceptance support: the injected notice's declared size and its ceiling.

Authority: docs/product/architecture/brief.md#The Injected Notice Declares Its
Measured Size And Refuses To Grow Past It.

This module drives the SAME published driving port as the sibling route-notice
oracle -- the installed Claude Code SessionStart command, discovered out of the
sandbox ``settings.json`` and executed as a real process -- and projects two
observations out of it:

1. On every invocation the hook REPORTS the size of the notice it is about to
   inject, as a measured fact in both units, on stderr. Standard output is
   reserved for exactly one JSON object, so the measurement cannot ride there;
   and there is deliberately no ``systemMessage``, because a user-visible
   banner at every session start is the noise the earlier retirement removed.

2. When the shipped text is enlarged past the declared ceiling, the hook
   REFUSES the injection and names both the measured and the permitted size.

WHY THE UNITS ARE WHAT THEY ARE. Bytes are primitive: the exact UTF-8 length of
the ``additionalContext`` actually written to stdout. Tokens are DERIVED as
``ceil(bytes / 4)`` and must be reported with that provenance named, because a
SessionStart hook must never touch the network and no tokenizer is available to
it at runtime; ``ceil(bytes / 4)`` over-states real tokenization for this text,
so it can never under-report bloat. A number presented as a counted token would
be a fabricated measurement.

THE ORACLE NEVER IMPORTS THE CEILING. The permitted number is read back out of
the hook's OWN reported text. A drifted constant therefore cannot silently
agree with a drifted expectation; the two observations below are questions put
to the running system, not to a shared symbol.

THE FALSIFIER'S STIMULUS TOUCHES NO TRACKED FILE AND NO PRODUCTION SYMBOL. It
pads every INSTALLED copy of the notice template discovered under the sandbox
``HOME``, never the repository template, so the enlargement reaches the real
subject by the same route a drifting installed tree would.
"""

from __future__ import annotations

import json
import math
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

#: The enlargement is driven far past any defensible ceiling, so the falsifier
#: never has to know what the declared ceiling happens to be.
OVERSIZE_TARGET_BYTES = 8192

#: The reported measurement is machine-readable so an operator and a check read
#: the SAME numbers. Labels, not positions, carry the meaning.
MEASURED_BYTES = re.compile(r"\bbytes=(\d+)\b")
DERIVED_TOKENS = re.compile(r"\btokens=(\d+)\b")
PERMITTED_BYTES = re.compile(r"\bpermitted=(\d+)\b")

#: Tokens may only be presented as what they are: a derived upper bound.
TOKEN_PROVENANCE = "conservative upper bound"

#: Refusal keeps the established WHAT/WHY/HOW shape of the handler's existing
#: degradations; oversize is a new member of that family, not a new algebra.
REFUSAL_MARKERS = ("WHAT:", "WHY:", "HOW:")


def _sole_int(pattern: re.Pattern[str], text: str) -> int | None:
    """The one labelled number, or None when it is absent or stated twice."""
    found = pattern.findall(text)
    if len(found) != 1:
        return None
    return int(found[0])


def _report(stderr: str) -> dict[str, Any]:
    """Project the reported measurement out of the hook's stderr."""
    measured = _sole_int(MEASURED_BYTES, stderr)
    tokens = _sole_int(DERIVED_TOKENS, stderr)
    permitted = _sole_int(PERMITTED_BYTES, stderr)
    return {
        "measured_bytes": measured,
        "derived_tokens": tokens,
        "permitted_bytes": permitted,
        "names_token_provenance": TOKEN_PROVENANCE in stderr,
    }


def _enlarge_installed_notices(system_home: Path) -> list[str]:
    """Pad every INSTALLED copy of the notice past any plausible ceiling.

    Returns the padded paths so an empty list -- which would make the falsifier
    vacuous -- stays visible in the observation.
    """
    padded: list[str] = []
    for copy in sorted(system_home.rglob(NOTICE_TEMPLATE_FILENAME)):
        if not copy.is_file():
            continue
        text = copy.read_text(encoding="utf-8")
        filler = "\nThis line is padding added by the notice-budget falsifier.\n"
        while len(text.encode("utf-8")) < OVERSIZE_TARGET_BYTES:
            text += filler
        copy.write_text(text, encoding="utf-8")
        padded.append(str(copy.relative_to(system_home)))
    return padded


def observe_notice_budget() -> dict[str, Any]:
    """Run the journey twice -- shipped, then enlarged -- and report both."""
    with tempfile.TemporaryDirectory(prefix="nwave-notice-budget-") as temporary:
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

        # 1. The notice as shipped: injected, and its size reported.
        shipped = (
            run_installed_hook(command, environment, project_root)
            if command is not None
            else None
        )
        context, _shape, contract_failure = (
            injected_context(shipped)
            if shipped is not None
            else (None, {}, "hook command was not discoverable")
        )
        shipped_report = _report(shipped.stderr if shipped is not None else "")
        injected_bytes = len(context.encode("utf-8")) if context is not None else None

        # 2. The same notice, enlarged past the ceiling on disk.
        padded = _enlarge_installed_notices(system_home)
        oversize = (
            run_installed_hook(command, environment, project_root)
            if command is not None
            else None
        )
        oversize_report = _report(oversize.stderr if oversize is not None else "")
        oversize_stderr = oversize.stderr if oversize is not None else ""

        semantic = {
            "install_exit_code": install.returncode,
            "enable_exit_code": enable.returncode,
            "command_is_uniquely_discoverable": command is not None,
            # -- the shipped notice is injected AND measured --------------
            "shipped_notice_is_injected": bool(context and context.strip()),
            # The reported byte count is the exact size of the bytes the agent
            # actually receives, not the size of some file on disk.
            "reported_bytes_equal_injected_bytes": (
                injected_bytes is not None
                and shipped_report["measured_bytes"] == injected_bytes
            ),
            # Tokens are a deterministic function of bytes, stated as such.
            "reported_tokens_are_derived_from_bytes": (
                shipped_report["derived_tokens"] is not None
                and shipped_report["measured_bytes"] is not None
                and shipped_report["derived_tokens"]
                == math.ceil(shipped_report["measured_bytes"] / 4)
            ),
            "reported_tokens_name_their_provenance": shipped_report[
                "names_token_provenance"
            ],
            # The ceiling is declared by the running system, never by this
            # oracle, and the shipped text lives within it.
            "report_declares_the_permitted_ceiling": (
                shipped_report["permitted_bytes"] is not None
            ),
            "shipped_notice_is_within_the_declared_ceiling": (
                shipped_report["measured_bytes"] is not None
                and shipped_report["permitted_bytes"] is not None
                and shipped_report["measured_bytes"]
                <= shipped_report["permitted_bytes"]
            ),
            # The measurement never contaminates the host contract.
            "measurement_stays_off_stdout": (
                shipped is not None
                and "bytes=" not in shipped.stdout
                and "permitted=" not in shipped.stdout
            ),
            # -- enlarging the text makes the check fail -------------------
            "the_stimulus_reached_an_installed_copy": bool(padded),
            "oversize_notice_is_refused": (
                oversize is not None and oversize.stdout.strip() == ""
            ),
            # Fail-open is preserved: a refusal must never brick a session.
            "oversize_refusal_does_not_block_the_session": (
                oversize is not None and oversize.returncode == 0
            ),
            "oversize_refusal_keeps_the_what_why_how_shape": all(
                marker in oversize_stderr for marker in REFUSAL_MARKERS
            ),
            # Both sizes are NAMED, so an operator learns by how much.
            "oversize_refusal_names_the_measured_size": (
                oversize_report["measured_bytes"] is not None
                and oversize_report["measured_bytes"] >= OVERSIZE_TARGET_BYTES
            ),
            "oversize_refusal_names_the_permitted_size": (
                oversize_report["permitted_bytes"] is not None
            ),
            "oversize_refusal_names_the_same_ceiling": (
                oversize_report["permitted_bytes"] is not None
                and oversize_report["permitted_bytes"]
                == shipped_report["permitted_bytes"]
            ),
            "oversize_report_states_the_violation": (
                oversize_report["measured_bytes"] is not None
                and oversize_report["permitted_bytes"] is not None
                and oversize_report["measured_bytes"]
                > oversize_report["permitted_bytes"]
            ),
        }

        diagnostics: dict[str, Any] = {
            "install": process_diagnostic("install", install, ["install"]),
            "enable": process_diagnostic("enable", enable, ["project", "enable"]),
            "published_command": command,
            "hook_discovery_failure": discovery_failure,
            "host_contract_failure": contract_failure,
            "injected_bytes": injected_bytes,
            "shipped_report": shipped_report,
            "oversize_report": oversize_report,
            "padded_installed_copies": padded,
        }
        if shipped is not None:
            diagnostics["hook_shipped"] = process_diagnostic(
                "session-start-shipped", shipped, ["/bin/sh", "-c", command or ""]
            )
        if oversize is not None:
            diagnostics["hook_oversize"] = process_diagnostic(
                "session-start-oversize", oversize, ["/bin/sh", "-c", command or ""]
            )

        return {"semantic": semantic, "diagnostics": diagnostics}


EXPECTED_SEMANTIC_OBSERVATION = {
    "install_exit_code": 0,
    "enable_exit_code": 0,
    "command_is_uniquely_discoverable": True,
    "shipped_notice_is_injected": True,
    "reported_bytes_equal_injected_bytes": True,
    "reported_tokens_are_derived_from_bytes": True,
    "reported_tokens_name_their_provenance": True,
    "report_declares_the_permitted_ceiling": True,
    "shipped_notice_is_within_the_declared_ceiling": True,
    "measurement_stays_off_stdout": True,
    "the_stimulus_reached_an_installed_copy": True,
    "oversize_notice_is_refused": True,
    "oversize_refusal_does_not_block_the_session": True,
    "oversize_refusal_keeps_the_what_why_how_shape": True,
    "oversize_refusal_names_the_measured_size": True,
    "oversize_refusal_names_the_permitted_size": True,
    "oversize_refusal_names_the_same_ceiling": True,
    "oversize_report_states_the_violation": True,
}


if __name__ == "__main__":
    observation = observe_notice_budget()
    print(json.dumps(observation, indent=2, sort_keys=True, default=str))
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit("notice budget observation differs from contract")
