"""The REAL Codex host, booted by the acceptance test.

Declaring a hook in the native format proves CONFIGURATION. Only the host
itself calling that hook proves ACTIVATION, and only the forbidden action
failing to happen proves ENFORCEMENT. This module boots the real ``codex``
binary so the walking skeleton can observe the last two, and it does so
without any external model:

* an EPHEMERAL ``CODEX_HOME`` -- the isolated home the candidate installed
  into, never the user's own;
* the REAL binary discovered on the prefix-rooted PATH, never a stub;
* hook trust granted for the invocation through the host's own supported flag
  (``--dangerously-bypass-hook-trust``), so nothing here depends on guessing
  how the host persists trust;
* a deterministic mock Responses provider that answers with EXACTLY ONE tool
  call and then one final message;
* the tool it calls is the one CODEX ITSELF ADVERTISES in its request, read
  off the wire -- so a safeguard registered for a tool name the host does not
  use is caught here rather than assumed away;
* an event nonce carried INTO the tool call, so the safeguard's mark is
  attributable to this event and to no other, against a measured baseline.

Absence of an ingredient is never a skip: each one fails loudly, naming what
is missing, why it matters and how to supply it.
"""

from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


#: Tool names, in preference order, under which a Codex user's shell action
#: arrives. The host advertises what it supports; this list only decides which
#: of the ADVERTISED tools to drive.
_SHELL_TOOL_PREFERENCE = ("exec_command", "shell", "local_shell", "bash")

_MIN_HOST_VERSION = (0, 145, 0)

_CALL_ID = "call_1"

#: What a safeguard's own record says it is, and the event it answers.
SAFEGUARD_REACTION = "safeguard-reaction"
NATIVE_EVENT = "PreToolUse"

#: How a registered hook names the log it owns, inside its own command.
_REACTION_LOG = re.compile(r"--reaction-log[= ](?P<path>\S+)")


#: The decoy host planted inside the candidate's own `bin`, and the mark it
#: leaves if it is ever the binary that runs.
_DECOY_MARK = ".codex-decoy-was-invoked"

#: A plausible host: it announces a supported version and answers the protocol
#: well enough to look like the real thing. Written in Python, so it needs no
#: shell, and it records every invocation before doing anything else.
_DECOY_SOURCE = """#!/usr/bin/env python3
import pathlib
import sys

pathlib.Path(__file__).with_name({mark!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
if "--version" in sys.argv:
    print("codex-cli 9.999.0")
else:
    print("done")
raise SystemExit(0)
"""


@dataclass(frozen=True)
class NativeHostObservation:
    """What the real host did, measured on the machine afterwards."""

    host_binary: Path
    decoy_in_the_candidate: Path
    decoy_is_executable: bool
    decoy_was_invoked: bool
    host_version: str
    host_exit: int
    registered_events: frozenset[str]
    tool_the_host_offered: str
    event_nonce: str
    tool_call_reported_back: bool
    tool_outcome_text: str
    reaction_log: Path | None
    marks_before: int
    reactions: tuple[dict[str, Any], ...]
    forbidden_effect_happened: bool
    commands_reaching_the_checkout: int
    transcript: str


class NativeCodexHost:
    """Boot the real Codex binary against the installed candidate."""

    def __init__(self, home: Path, workspace: Path, prefix: Path) -> None:
        self._home = home
        self._workspace = workspace
        self._prefix = prefix
        self._offered: list[dict[str, Any]] = []
        self._bodies: list[dict[str, Any]] = []
        self._chosen: dict[str, str] = {}

    # -- the one public observation -----------------------------------------

    def observe_one_forbidden_action(
        self, checkout_root: Path, candidate: str
    ) -> NativeHostObservation:
        """Let the host attempt ONE forbidden action and watch what happens."""
        decoy = self._plant_a_host_inside_the_candidate()
        binary = self._require_the_real_binary()
        version = self._require_a_supporting_version(binary)
        document = self._require_a_registration()

        log = self._reaction_log_of(document)
        nonce = f"forbidden-event-{uuid.uuid4().hex[:16]}"
        effect = self._workspace / f"{nonce}.happened"
        before = self._reactions_to(log, nonce, candidate)

        port, stop = self._serve_one_tool_call(nonce, effect)
        try:
            exit_code, transcript = self._boot(binary, port)
        finally:
            stop()

        return NativeHostObservation(
            host_binary=Path(binary).resolve(),
            decoy_in_the_candidate=decoy,
            decoy_is_executable=os.access(decoy, os.X_OK),
            decoy_was_invoked=decoy.with_name(_DECOY_MARK).exists(),
            host_version=version,
            host_exit=exit_code,
            registered_events=frozenset(document.get("hooks", {})),
            tool_the_host_offered=self._chosen.get("name", ""),
            event_nonce=nonce,
            tool_call_reported_back=self._tool_call_came_back(),
            tool_outcome_text=self._tool_outcome_text(),
            reaction_log=log,
            marks_before=len(before),
            reactions=self._reactions_to(log, nonce, candidate),
            forbidden_effect_happened=effect.exists(),
            commands_reaching_the_checkout=self._commands_reaching(
                document, checkout_root
            ),
            transcript=transcript,
        )

    # -- ingredients, each failing loudly when absent ------------------------

    def _plant_a_host_inside_the_candidate(self) -> Path:
        """Put a plausible `codex` in the candidate's own `bin`, and watch it.

        The rule that the host comes from the machine is only worth as much as
        the case that would break it, so the case is BUILT rather than assumed
        away: a working executable named exactly what the resolver looks for,
        sitting exactly where the candidate could have shipped one, announcing a
        supported version and answering the protocol. If resolution ever
        preferred the candidate's own tree, this file would run -- and it
        records the fact -- so the difference between routing around the
        candidate and merely believing one does is visible on the machine
        instead of resting on a reading of the code.

        Planting never CLOBBERS: a `codex` the candidate itself shipped is the
        very thing the resolver must refuse, and overwriting it would erase the
        evidence.
        """
        decoy = self._prefix / "bin" / "codex"
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy.with_name(_DECOY_MARK).unlink(missing_ok=True)
        if not decoy.exists():
            decoy.write_text(_DECOY_SOURCE.format(mark=_DECOY_MARK), encoding="utf-8")
            decoy.chmod(0o755)
        return decoy

    def _require_the_real_binary(self) -> str:
        """The host, resolved from the machine -- never from the candidate.

        The candidate's own `bin` is deliberately NOT on the path searched
        here. A wheel that shipped its own `codex` could otherwise announce a
        supported version, speak the mock protocol back to us and write the
        very log and outcome this scenario reads: every oracle above rests on
        the host being real, so a producer that supplies the host does not
        fabricate the evidence -- it fabricates the judge, and the rest is
        coherent theatre. The child's path is a different path, and it does
        include the prefix, because that is where the installed `des` and the
        registered hook must be found.
        """
        binary = shutil.which("codex", path=self._machine_path())
        if binary is None:
            raise AssertionError(
                "WHAT: no real `codex` binary is reachable from this "
                "machine's own path -- which is searched with everything under "
                f"the candidate's install {self._prefix} removed. WHY: a "
                "safeguard "
                "can only be proved active by the host that would call it; a "
                "stand-in host proves our own code, not the user's machine, and "
                "skipping the check would report enforcement nobody observed. "
                "HOW: install Codex on the machine that runs this suite."
            )
        resolved = Path(binary).resolve()
        prefix = self._prefix.resolve()
        if resolved == prefix or prefix in resolved.parents:
            raise AssertionError(
                f"WHAT: the host that would judge this run is {resolved}, "
                f"inside the candidate's own install {prefix}. WHY: a candidate "
                "that ships its host decides what the host reports -- version, "
                "protocol, transcript and outcome alike -- so every observation "
                "this scenario takes would be the producer marking its own "
                "work. HOW: resolve the host from the machine, and let the "
                "candidate supply only what the host is asked to find."
            )
        return binary

    def _require_a_supporting_version(self, binary: str) -> str:
        reported = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=60
        ).stdout.strip()
        digits = tuple(
            int(part)
            for part in "".join(
                char if char.isdigit() else " " for char in reported
            ).split()[:3]
        )
        if digits < _MIN_HOST_VERSION:
            raise AssertionError(
                f"WHAT: the host reports {reported!r}, below the version whose "
                "lifecycle hooks this feature targets "
                f"{'.'.join(str(part) for part in _MIN_HOST_VERSION)}. WHY: an "
                "older host may never call the safeguard at all, so a green run "
                "would say nothing about the machines users are on. HOW: run "
                "against a host at or above the supported version."
            )
        return reported

    def _require_a_registration(self) -> dict[str, Any]:
        path = self._home / ".codex" / "hooks.json"
        if not path.is_file():
            raise AssertionError(
                "__SCAFFOLD__ WHAT: the install left no native hook "
                f"registration at {path}. WHY: without one the host never calls "
                "nWave at all, so the safeguard could only ever be exercised by "
                "a command of our own -- which proves our code runs, not that "
                "the user is protected. HOW: write the event-keyed hooks "
                "document into the machine's Codex home during install."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    # -- the deterministic model, replaced by a mock provider ---------------

    def _serve_one_tool_call(self, nonce: str, effect: Path) -> tuple[int, Any]:
        """One tool call carrying this event's nonce, then one final message."""
        host = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(inner) -> None:
                length = int(inner.headers.get("Content-Length", "0"))
                body = json.loads(inner.rfile.read(length).decode("utf-8", "replace"))
                host._bodies.append(body)
                first = len(host._bodies) == 1
                if first:
                    host._offered.extend(body.get("tools", []))
                    host._chosen["name"] = host._preferred_tool(host._offered)
                payload = (
                    host._tool_call_stream(host._chosen.get("name", ""), nonce, effect)
                    if first
                    else host._final_message_stream()
                )
                inner.send_response(200)
                inner.send_header("Content-Type", "text/event-stream")
                inner.end_headers()
                inner.wfile.write(payload.encode())
                inner.wfile.flush()

            def log_message(inner, *args: object) -> None:
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server.server_address[1], server.shutdown

    @staticmethod
    def _preferred_tool(offered: list[dict[str, Any]]) -> str:
        names = [str(tool.get("name") or "") for tool in offered]
        for preferred in _SHELL_TOOL_PREFERENCE:
            if preferred in names:
                return preferred
        return names[0] if names else ""

    @staticmethod
    def _tool_call_stream(tool: str, nonce: str, effect: Path) -> str:
        """The forbidden action, carrying this event's nonce into the host."""
        arguments = json.dumps({"cmd": f"/bin/echo {nonce} > {effect}"})
        item = {
            "type": "function_call",
            "name": tool,
            "call_id": _CALL_ID,
            "arguments": arguments,
        }
        return (
            "event: response.created\n"
            'data: {"type":"response.created","response":{"id":"resp_1"}}\n\n'
            "event: response.output_item.done\n"
            "data: "
            + json.dumps(
                {"type": "response.output_item.done", "output_index": 0, "item": item}
            )
            + "\n\n"
            "event: response.completed\n"
            'data: {"type":"response.completed","response":{"id":"resp_1",'
            '"output":[],"usage":{"input_tokens":1,"output_tokens":1,'
            '"total_tokens":2}}}\n\n'
        )

    @staticmethod
    def _final_message_stream() -> str:
        return (
            "event: response.created\n"
            'data: {"type":"response.created","response":{"id":"resp_2"}}\n\n'
            "event: response.output_item.done\n"
            'data: {"type":"response.output_item.done","output_index":0,"item":'
            '{"type":"message","role":"assistant","status":"completed",'
            '"content":[{"type":"output_text","text":"done"}]}}\n\n'
            "event: response.completed\n"
            'data: {"type":"response.completed","response":{"id":"resp_2",'
            '"output":[],"usage":{"input_tokens":1,"output_tokens":1,'
            '"total_tokens":2}}}\n\n'
        )

    # -- what came back over the wire ---------------------------------------

    def _tool_call_records(self) -> list[dict[str, Any]]:
        """The host's own report of what became of the tool call it was given.

        Read from the SECOND request the host made: it carries the outcome of
        that call, so a boot that never reached the tool at all is
        distinguishable from one where the safeguard turned the action away.
        """
        if len(self._bodies) < 2:
            return []
        return [
            item
            for item in self._bodies[1].get("input", []) or []
            if isinstance(item, dict)
            and item.get("call_id") == _CALL_ID
            and "output" in item
        ]

    def _tool_call_came_back(self) -> bool:
        return bool(self._tool_call_records())

    def _tool_outcome_text(self) -> str:
        return " ".join(
            json.dumps(record.get("output")) for record in self._tool_call_records()
        )

    # -- the boot itself -----------------------------------------------------

    def _boot(self, binary: str, port: int) -> tuple[int, str]:
        self._point_at_the_mock_provider(port)
        booted = subprocess.run(
            [
                binary,
                "exec",
                "--skip-git-repo-check",
                "--dangerously-bypass-hook-trust",
                "attempt the forbidden action",
            ],
            cwd=self._workspace,
            capture_output=True,
            text=True,
            timeout=300,
            env={
                "PATH": self._path(),
                "HOME": str(self._home),
                "CODEX_HOME": str(self._home / ".codex"),
                "OPENAI_API_KEY": "mock-provider-key",
            },
        )
        return booted.returncode, f"{booted.stdout}\n{booted.stderr}"

    def _point_at_the_mock_provider(self, port: int) -> None:
        config = self._home / ".codex" / "config.toml"
        existing = config.read_text(encoding="utf-8") if config.is_file() else ""
        config.write_text(
            existing
            + "\n"
            + 'model = "mock-model"\n'
            + 'model_provider = "mock"\n'
            + 'approval_policy = "never"\n'
            + 'sandbox_mode = "danger-full-access"\n'
            + "\n[model_providers.mock]\n"
            + 'name = "mock"\n'
            + f'base_url = "http://127.0.0.1:{port}/v1"\n'
            + 'wire_api = "responses"\n'
            + "requires_openai_auth = false\n"
            + "\n[features]\n"
            + "hooks = true\n",
            encoding="utf-8",
        )
        (self._home / ".codex" / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": "mock-provider-key"}), encoding="utf-8"
        )

    def _machine_path(self) -> str:
        """The inherited PATH with everything under the candidate removed.

        Used to find the HOST, and nothing else.
        """
        prefix = self._prefix.resolve()
        kept: list[str] = []
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            if not entry:
                continue
            resolved = Path(entry).resolve()
            if resolved == prefix or prefix in resolved.parents:
                continue
            kept.append(entry)
        return os.pathsep.join(kept)

    def _path(self) -> str:
        """The CHILD's PATH, which does include the candidate.

        This one is for what the host must find: the installed `des` and the
        registered hook command. Keeping the two paths apart is the whole
        point -- the prefix is legitimate for the artifacts under test and
        illegitimate for the host that tests them.
        """
        return os.pathsep.join(
            [str(self._prefix / "bin"), *os.environ.get("PATH", "").split(os.pathsep)]
        )

    # -- what the test counts, bound to THIS event --------------------------

    def _reaction_log_of(self, document: dict[str, Any]) -> Path | None:
        """Where the REGISTERED hook says it records, read from the registration.

        Ownership is a fact of the registration, not of a record's own claim: a
        file anywhere under HOME can contain an object that SAYS it is a
        safeguard reaction, and believing that field would let a stranger's
        writing stand in for the hook the host actually called. The command the
        install registered names its own log, and only that file counts.
        """
        for group in document.get("hooks", {}).get(NATIVE_EVENT, []) or []:
            for hook in group.get("hooks", []) or []:
                command = str(hook.get("command", ""))
                match = _REACTION_LOG.search(command)
                if match:
                    return Path(match.group("path"))
        return None

    def _reactions_to(
        self, log: Path | None, nonce: str, candidate: str
    ) -> tuple[dict[str, Any], ...]:
        """The registered hook's OWN reactions to THIS event, from ITS log.

        Read only from the file the registration names, and only records that
        are typed as a safeguard reaction and bound to this event's nonce, this
        lifecycle event, the tool answered and the candidate. A matching record
        in some other file under HOME is somebody else's writing and is not
        counted -- which is the whole difference between a record that says what
        it is and a record whose owner is known.
        """
        if log is None or not log.is_file():
            return ()
        found: list[dict[str, Any]] = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped.startswith("{") or nonce not in stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if self._is_a_reaction(record, nonce, candidate):
                found.append(record)
        return tuple(found)

    def _is_a_reaction(
        self, record: dict[str, Any], nonce: str, candidate: str
    ) -> bool:
        """Bound to this exact event, and answerable to the host."""
        if not isinstance(record, dict):
            return False
        return (
            str(record.get("kind", "")) == SAFEGUARD_REACTION
            and str(record.get("event_nonce", "")) == nonce
            and str(record.get("event", "")) == NATIVE_EVENT
            and str(record.get("tool", "")) == self._chosen.get("name", "")
            and str(record.get("candidate_id", "")) == candidate
            and bool(str(record.get("record_id", "")))
        )

    def _commands_reaching(self, document: dict[str, Any], checkout: Path) -> int:
        needle = str(checkout.resolve())
        return sum(
            1
            for groups in document.get("hooks", {}).values()
            for group in groups
            for hook in group.get("hooks", []) or []
            if needle in str(hook.get("command", ""))
        )
