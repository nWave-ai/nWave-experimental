"""Plugin for wiring nWave DES hooks into Codex CLI.

Codex CLI hooks are configured via ~/.codex/hooks.json (user-level) or the
[hooks] section of ~/.codex/config.toml. This plugin writes a hooks.json
entry that registers the existing Python DES adapter as a PreToolUse hook.

Walking-skeleton scope:
- Writes a single PreToolUse hook entry to ~/.codex/hooks.json
- The hook points to the same Python DES adapter used by Claude Code
- The hook logs to stderr to confirm it fires (no TDD enforcement yet)
- No PostToolUse / Stop hooks in this slice (deferred)

Hook protocol is identical to Claude Code: JSON on stdin, decision on stdout.
This means the existing claude_code_hook_adapter.py is theoretically reusable
without modification -- empirical validation is out of scope for this slice.

A manifest (.nwave-des-manifest.json) tracks the installed hook config for
clean uninstallation.
"""

import base64
import json
import os
import re
import shlex
import shutil as _shutil
import sys
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.shared.install_paths import (
    host_neutral_runtime_dir,
    is_durable_interpreter_path,
    resolve_des_lib_path_for_spawn,
    resolve_python_command_for_spawn,
)


_HOOKS_FILENAME = "hooks.json"
_MANIFEST_FILENAME = ".nwave-des-manifest.json"
_LAUNCHER_FILENAME = "nwave_claude_code_hook_adapter_launcher.py"

# Event key used by Codex (verified against developers.openai.com/codex/hooks
# and codex-rs/hooks/schema/generated/pre-tool-use.command.*.schema.json).
_PRE_TOOL_USE_EVENT = "PreToolUse"
_SESSION_START_EVENT = "SessionStart"
_SESSION_START_MATCHER = "startup|resume|clear|compact"
_SESSION_START_SUBCOMMAND = "session-start"
_CODEX_HOST_PROVENANCE_ARGUMENT = "--host-provenance=codex"
_SESSION_START_LAUNCHER_FILENAME = "nwave_orchestrator_affordance_launcher.py"
_RUNTIME_RESOLVER_RELATIVE_PATH = Path("nWave/hooks/orchestrator_affordance_refresh.py")

# Observed from the running codex-cli 0.145.0 host on 2026-07-26.  The
# installer must bind a matcher to what the host actually emits, not to a
# similarly named tool from another vendor or documentation-only surface.
_ANNOUNCED_TOOLS: tuple[str, ...] = (
    "exec_command",
    "write_stdin",
    "update_plan",
    "request_user_input",
    "view_image",
    "multi_agent_v1",
    "get_goal",
    "create_goal",
    "update_goal",
    "web_search",
)
_INTERCEPTED_TOOLS: tuple[str, ...] = ("exec_command",)


def _pre_tool_use_matcher() -> str:
    """Return a matcher restricted to tools observed on the Codex host."""
    unannounced = set(_INTERCEPTED_TOOLS).difference(_ANNOUNCED_TOOLS)
    if not _INTERCEPTED_TOOLS or unannounced:
        raise ValueError(
            "Codex PreToolUse matcher names no observed host tool: "
            f"{sorted(unannounced)!r}"
        )
    return "|".join(f"^{re.escape(tool)}$" for tool in _INTERCEPTED_TOOLS)


# Wall-clock bound the generated launcher applies to the DES validation it
# spawns, and the operator's lever over it.  25s is chosen against the two
# opposing costs: it must be generous enough that a cold PreToolUse validation
# doing real filesystem work is never guillotined, and it must stay strictly
# under the `timeout: 30` this installer declares on the hook entry so the
# launcher reaches its own explained verdict before the Codex harness kills it.
_LAUNCHER_TIMEOUT_ENV = "NWAVE_CODEX_HOOK_TIMEOUT"
_LAUNCHER_TIMEOUT_SECONDS = 25.0


def _codex_config_dir() -> Path:
    """Return the Codex CLI configuration directory.

    Returns:
        Path to ~/.codex/ (or $CODEX_HOME if set)
    """
    override = os.environ.get("CODEX_HOME")
    return Path(override) if override else Path.home() / ".codex"


def _build_hook_invocation(python_path: str, pythonpath: str) -> dict:
    """Build a shell-independent DES invocation with literal argv and env."""
    return {
        "argv": [
            python_path,
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "pre-tool-use",
        ],
        "env": {"PYTHONPATH": pythonpath},
    }


def _launcher_source(python_path: str, pythonpath: str) -> str:
    """Return the exact bytes of an nWave-generated launcher.

    This text becomes executable code on the operator's machine, so the spawn it
    emits owes the same two duties every hand-written spawn in this tree owes
    (``tests/build/test_no_unbounded_unstdin_spawn.py``): an explicit stdin
    decision and a wall-clock bound.  The static ban cannot see this one -- at
    scan time it is a string literal, not a Call node -- so the duties are
    discharged here and witnessed behaviourally by
    ``tests/bugs/test_bug_generated_launcher_unbounded_spawn.py``.

    The stdin decision is a FORWARD, not a ``DEVNULL``: the Codex hook protocol
    is JSON on stdin and the DES adapter reads it, while
    ``read_and_parse_stdin`` fails OPEN on empty input -- starving the child
    would switch validation off silently.  It is a pass-through rather than an
    ``input=`` read so the launcher itself never blocks on a descriptor that
    never reaches EOF; the child's read stays the only blocking wait on the
    path, and the bound covers it.

    The bound sits below the ``timeout: 30`` this installer declares on the hook
    entry, so the launcher reaches its own explained verdict before the harness
    kills it, and degrades LOUD-and-allow on expiry (the adapter's own policy:
    a hook never bricks a session).
    """
    return (
        '"""nWave Codex DES launcher. Generated; reinstall to update."""\n'
        "import os\n"
        "import subprocess\n"
        "import sys\n\n"
        f"PYTHON_PATH = {json.dumps(python_path)}\n"
        f"PYTHONPATH = {json.dumps(pythonpath)}\n"
        f"TIMEOUT_ENV = {json.dumps(_LAUNCHER_TIMEOUT_ENV)}\n"
        f"DEFAULT_TIMEOUT_SECONDS = {_LAUNCHER_TIMEOUT_SECONDS!r}\n"
        "env = os.environ.copy()\n"
        'env["PYTHONPATH"] = PYTHONPATH\n'
        "argv = [\n"
        "    PYTHON_PATH,\n"
        '    "-m",\n'
        '    "des.adapters.drivers.hooks.claude_code_hook_adapter",\n'
        '    "pre-tool-use",\n'
        "]\n"
        "try:\n"
        "    bound = float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS))\n"
        "except (TypeError, ValueError):\n"
        "    bound = DEFAULT_TIMEOUT_SECONDS\n"
        "try:\n"
        "    stdin_channel = sys.stdin.fileno()\n"
        "except (AttributeError, OSError, ValueError):\n"
        "    stdin_channel = subprocess.DEVNULL\n"
        "try:\n"
        "    completed = subprocess.run(\n"
        "        argv, env=env, check=False, stdin=stdin_channel, timeout=bound\n"
        "    )\n"
        "except subprocess.TimeoutExpired:\n"
        "    sys.stderr.write(\n"
        '        f"WHAT: the nWave DES PreToolUse validation did not finish "\n'
        '        f"within its {bound:g}s bound and was killed.\\n"\n'
        '        f"WHY: a hook that never returns hangs the Codex session, so "\n'
        '        f"this launcher bounds its child and always yields.\\n"\n'
        '        f"HOW: re-run. If the validation genuinely needs longer, set "\n'
        '        f"{TIMEOUT_ENV}=<seconds>. Allowing the tool without a "\n'
        '        f"verdict.\\n"\n'
        "    )\n"
        "    sys.exit(0)\n"
        "sys.exit(completed.returncode)\n"
    )


def _v1_launcher_source(python_path: str, pythonpath: str) -> str:
    """Return the exact launcher body emitted by the public v1 bootstrap."""
    return (
        '"""nWave Codex DES launcher. Generated; reinstall to update."""\n'
        "import os\nimport subprocess\nimport sys\n\n"
        f"PYTHON_PATH = {json.dumps(python_path)}\n"
        f"PYTHONPATH = {json.dumps(pythonpath)}\n"
        'env = os.environ.copy()\nenv["PYTHONPATH"] = PYTHONPATH\n'
        'argv = [PYTHON_PATH, "-m", '
        '"des.adapters.drivers.hooks.claude_code_hook_adapter", "pre-tool-use"]\n'
        "completed = subprocess.run(argv, env=env, check=False)\n"
        "sys.exit(completed.returncode)\n"
    )


def _write_launcher(launcher_path: Path, python_path: str, pythonpath: str) -> None:
    """Materialize a stdlib launcher carrying dynamic values as data."""
    launcher_path.write_text(
        _launcher_source(python_path, pythonpath), encoding="utf-8"
    )


def _runtime_resolver_path() -> Path:
    """Return the resolver shipped with the host-neutral nWave runtime.

    This is deliberately not ``~/.claude`` and never a development checkout:
    the same public candidate must serve a Codex-only user after its source
    tree has gone away.
    """
    # DES code lives in ~/.nwave/runtime/des while its sibling nWave assets
    # deliberately live at ~/.nwave/nWave.  Runtime assets are a peer of the
    # code runtime, not a child of it.
    return host_neutral_runtime_dir().parent / _RUNTIME_RESOLVER_RELATIVE_PATH


def _session_start_launcher_source(
    python_path: str, pythonpath: str, resolver_path: str
) -> str:
    """Return the bounded transparent launcher for Codex SessionStart.

    A real Codex SessionStart envelope is routed to the DES handler, where the
    canonical standing-loop facade can offer one due bounded opportunity.  An
    invocation with no host envelope retains the standalone resolver used by
    non-host probes and older host shapes.  This launcher never invents an
    occurrence or completion claim.
    """
    return (
        '"""nWave Codex SessionStart launcher. Generated; reinstall to update."""\n'
        "import os\n"
        "import subprocess\n"
        "import sys\n\n"
        f"PYTHON_PATH = {json.dumps(python_path)}\n"
        f"PYTHONPATH = {json.dumps(pythonpath)}\n"
        f"RESOLVER_PATH = {json.dumps(resolver_path)}\n"
        "stdin_text = sys.stdin.read()\n"
        "if stdin_text:\n"
        "    env = os.environ.copy()\n"
        '    env["PYTHONPATH"] = PYTHONPATH\n'
        "    argv = [\n"
        "        PYTHON_PATH,\n"
        '        "-m",\n'
        '        "des.adapters.drivers.hooks.hook_router",\n'
        '        "session-start",\n'
        f"        {_CODEX_HOST_PROVENANCE_ARGUMENT!r},\n"
        "    ]\n"
        '    kwargs = {"input": stdin_text, "text": True, "env": env}\n'
        "else:\n"
        '    argv = [PYTHON_PATH, RESOLVER_PATH, "SessionStart"]\n'
        '    kwargs = {"stdin": subprocess.DEVNULL}\n'
        "try:\n"
        "    completed = subprocess.run(\n"
        "        argv, timeout=10, check=False, **kwargs\n"
        "    )\n"
        "except subprocess.TimeoutExpired:\n"
        "    sys.exit(0)\n"
        "sys.exit(completed.returncode)\n"
    )


def _write_session_start_launcher(
    launcher_path: Path, python_path: str, pythonpath: str, resolver_path: Path
) -> None:
    launcher_path.write_text(
        _session_start_launcher_source(python_path, pythonpath, str(resolver_path)),
        encoding="utf-8",
    )


def _build_launcher_hook_entry(launcher_path: Path) -> dict:
    """Render a hook command containing only fixed installer-controlled values.

    Resolves the interpreter with the SAME durability guard the Claude-side
    hook uses (DESPlugin._resolve_python_path): reject an interpreter rooted
    under an ephemeral location (a dev worktree, a throwaway clone) that will
    not exist when Codex later fires this persisted hook command, falling
    back to the portable ``python3``. Deliberately NOT
    ``resolve_python_command_for_spawn()`` -- that helper (and its
    ``resolve_des_lib_path_for_spawn`` sibling) exists to produce values that
    get embedded as Python string literals inside the LAUNCHER SCRIPT's own
    source, tolerant of shell-hostile characters (spaces, quotes, backticks);
    the hook COMMAND's own interpreter is a distinct, simpler concern and
    must stay a value ``shlex``/the shell can invoke directly
    (fix-codex-hook-command-embeds-ephemeral-interpreter-path).
    """
    python_path = (
        sys.executable if is_durable_interpreter_path(sys.executable) else "python3"
    )
    if os.name == "nt":
        powershell = " ".join(
            (
                "&",
                _powershell_literal(python_path),
                _powershell_literal(str(launcher_path)),
                _powershell_literal("pre-tool-use"),
            )
        )
        encoded = base64.b64encode(powershell.encode("utf-16le")).decode("ascii")
        command = f"powershell -NoProfile -EncodedCommand {encoded}"
    else:
        command = shlex.join([python_path, str(launcher_path), "pre-tool-use"])
    return {
        "matcher": _pre_tool_use_matcher(),
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 30,
                "statusMessage": "nWave DES validation...",
            }
        ],
    }


def _build_session_start_hook_entry(launcher_path: Path) -> dict:
    """Render the observed Codex SessionStart schema for the nWave launcher.

    See ``_build_launcher_hook_entry`` for why this resolves the interpreter
    via a durability guard on ``sys.executable`` rather than either raw
    ``sys.executable`` or ``resolve_python_command_for_spawn()``.
    """
    python_path = (
        sys.executable if is_durable_interpreter_path(sys.executable) else "python3"
    )
    if os.name == "nt":
        powershell = " ".join(
            (
                "&",
                _powershell_literal(python_path),
                _powershell_literal(str(launcher_path)),
                _powershell_literal(_SESSION_START_SUBCOMMAND),
                _powershell_literal(_CODEX_HOST_PROVENANCE_ARGUMENT),
            )
        )
        encoded = base64.b64encode(powershell.encode("utf-16le")).decode("ascii")
        command = f"powershell -NoProfile -EncodedCommand {encoded}"
    else:
        command = shlex.join(
            [
                python_path,
                str(launcher_path),
                _SESSION_START_SUBCOMMAND,
                _CODEX_HOST_PROVENANCE_ARGUMENT,
            ]
        )
    return {
        "matcher": _SESSION_START_MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 15,
                "statusMessage": "nWave orchestrator affordance...",
            }
        ],
    }


def _powershell_literal(value: str) -> str:
    """Render one exact PowerShell single-quoted string literal."""
    return "'" + value.replace("'", "''") + "'"


def _powershell_argv(command: str) -> list[str] | None:
    """Decode the exact literal-only PowerShell command emitted by this plugin."""
    tokens = command.split()
    if (
        tokens[:3] != ["powershell", "-NoProfile", "-EncodedCommand"]
        or len(tokens) != 4
    ):
        return None
    try:
        source = base64.b64decode(tokens[3], validate=True).decode("utf-16le")
    except (ValueError, UnicodeDecodeError):
        return None
    if not source.startswith("&"):
        return None

    values: list[str] = []
    index = 1
    while index < len(source):
        while index < len(source) and source[index].isspace():
            index += 1
        if index == len(source):
            break
        if source[index] != "'":
            return None
        index += 1
        value = ""
        while index < len(source):
            if source[index] != "'":
                value += source[index]
                index += 1
            elif index + 1 < len(source) and source[index + 1] == "'":
                value += "'"
                index += 2
            else:
                index += 1
                break
        else:
            return None
        if index < len(source) and not source[index].isspace():
            return None
        values.append(value)
    return values


def _command_argv(command: str) -> list[str] | None:
    """Return argv only for the exact command encodings the installer emits."""
    if os.name == "nt":
        return _powershell_argv(command)
    try:
        return shlex.split(command)
    except ValueError:
        return None


def _command_targets_launcher(
    command: str, launcher_path: Path, subcommand: str = "pre-tool-use"
) -> bool:
    """Verify the serialized command is exactly the canonical invocation."""
    python_path = (
        sys.executable if is_durable_interpreter_path(sys.executable) else "python3"
    )
    expected_argv = [python_path, str(launcher_path), subcommand]
    if subcommand == _SESSION_START_SUBCOMMAND:
        expected_argv.append(_CODEX_HOST_PROVENANCE_ARGUMENT)
    return _command_argv(command) == expected_argv


def _command_owns_launcher(
    command: str, launcher_path: Path, subcommand: str = "pre-tool-use"
) -> bool:
    """Identify an nWave hook by its canonical launcher, not its interpreter.

    The interpreter is intentionally excluded from this ownership identity: a
    reinstall may run under a different Python than the one that rendered the
    previous hook command.  The launcher path and event are installer-owned
    and remain stable across that change.
    """
    argv = _command_argv(command)
    if argv is None or len(argv) < 1:
        return False
    expected_tail = [str(launcher_path), subcommand]
    if subcommand == _SESSION_START_SUBCOMMAND:
        expected_tail.append(_CODEX_HOST_PROVENANCE_ARGUMENT)
    return argv[1:] == expected_tail


def _command_is_legacy_session_start(command: str, launcher_path: Path) -> bool:
    """Recognize only the pre-provenance SessionStart invocation."""
    argv = _command_argv(command)
    return (
        argv is not None
        and len(argv) == 3
        and argv[1:] == [str(launcher_path), _SESSION_START_SUBCOMMAND]
    )


def _build_hook_entry(python_path: str, pythonpath: str) -> dict:
    """Build the Codex PreToolUse hook entry for the DES adapter.

    The hook entry follows the Codex hooks.json format:
    - matcher: regex that matches tool names to intercept
    - hooks: list of command entries with type, command, timeout

    Matcher is narrowed to ``^Bash$|^apply_patch$`` — the two tools
    Codex actually emits in PreToolUse per
    developers.openai.com/codex/hooks (DDD-6, verified by DDD-8 spike Q6):
    - Bash: shell command execution
    - apply_patch: file edits performed by Codex

    The pre-FM-3 matcher (``^Task$|^Bash$``) referenced ``Task`` — a
    Claude-Code-internal tool name Codex never emits — by analogy with the
    Claude Code plugin. FM-3 root cause: mirrored a peer without reading
    the Codex docs. ``Edit|Write`` aliases for apply_patch and ``mcp__*``
    matchers are deferred to a later slice per DESIGN.

    Read / Grep / Glob and other read-only tools are excluded to avoid
    unnecessary overhead on every file access. Using ``.*`` (all tools)
    was the walking-skeleton default; this matcher is the
    production-grade narrow form.

    Args:
        python_path: Absolute path to the Python executable
        pythonpath: Path to add to PYTHONPATH for DES imports

    Returns:
        Dict representing a single hooks.json entry
    """
    # DDD-4 (FM-2 closure): the shared DES adapter (hook_router.py) requires
    # an argv positional event token (one of pre-tool-use / subagent-stop /
    # post-tool-use / ...). Codex does NOT inject the event name as argv —
    # only `cwd` is set; the configured `command` runs as-is. The token must
    # therefore be baked into the command string at install time. Without it,
    # the adapter exits 1 with "Missing command argument" on every fire.
    invocation = _build_hook_invocation(python_path, pythonpath)
    _, *module_argv = invocation["argv"]
    module_and_event = " ".join(module_argv)
    pythonpath = invocation["env"]["PYTHONPATH"]
    windows_path = len(python_path) >= 3 and python_path[1:3] in {":/", ":\\"}
    if windows_path:
        powershell_python = python_path.replace("'", "''")
        powershell_pythonpath = pythonpath.replace("'", "''")
        hook_command = (
            "powershell -NoProfile -Command "
            f"""'$env:PYTHONPATH = "{powershell_pythonpath}"; """
            f"""& "{powershell_python}" {module_and_event}'"""
        )
    else:
        hook_command = (
            f"PYTHONPATH={shlex.quote(pythonpath)} "
            f"{shlex.quote(python_path)} {module_and_event}"
        )
    return {
        "matcher": _pre_tool_use_matcher(),
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": 30,
                "statusMessage": "nWave DES validation...",
            }
        ],
    }


def _legacy_direct_des_command(
    manifest: object, hooks_path: Path, hooks_document: object
) -> str | None:
    """Return the sole direct-hook command proven by the pre-launcher manifest.

    The original Codex bootstrap recorded only its hook file, interpreter and
    PYTHONPATH.  That sparse record is ownership evidence only when it has its
    exact three-field shape *and* either the recorded direct command or the
    exact v1 launcher file and command still appears in ``hooks.PreToolUse``.
    A module-name substring, another event, or a merely similar shell command
    is deliberately not enough.
    """
    if not (
        isinstance(manifest, dict)
        and set(manifest) == {"hooks_file", "python_path", "pythonpath"}
        and manifest.get("hooks_file") == str(hooks_path)
        and isinstance(manifest.get("python_path"), str)
        and manifest["python_path"]
        and isinstance(manifest.get("pythonpath"), str)
        and manifest["pythonpath"]
        and isinstance(hooks_document, dict)
        and isinstance(hooks_document.get("hooks"), dict)
    ):
        return None
    expected_direct = _build_hook_entry(
        manifest["python_path"], manifest["pythonpath"]
    )["hooks"][0]["command"]
    launcher_path = hooks_path.parent / _LAUNCHER_FILENAME
    try:
        launcher_is_v1 = (
            launcher_path.is_file()
            and not launcher_path.is_symlink()
            and launcher_path.read_text(encoding="utf-8")
            == _v1_launcher_source(manifest["python_path"], manifest["pythonpath"])
        )
    except (OSError, UnicodeDecodeError):
        launcher_is_v1 = False
    expected_launcher = shlex.join(
        [manifest["python_path"], str(launcher_path), "pre-tool-use"]
    )
    pretool = hooks_document["hooks"].get(_PRE_TOOL_USE_EVENT)
    if not isinstance(pretool, list):
        return None
    for group in pretool:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            continue
        for handler in group["hooks"]:
            command = handler.get("command") if isinstance(handler, dict) else None
            if command == expected_direct or (
                launcher_is_v1 and command == expected_launcher
            ):
                return command
    return None


def _is_legacy_direct_des_command(command: object) -> bool:
    """Recognize the pre-launcher DES invocation, not an adapter substring.

    This is the exact five-token POSIX form emitted by the old Codex
    installer.  It is intentionally restricted to ``PreToolUse`` by the
    caller so a user command in another event cannot be adopted.
    """
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return (
        len(tokens) == 5
        and tokens[0].startswith("PYTHONPATH=")
        and len(tokens[0]) > len("PYTHONPATH=")
        and tokens[1]
        and tokens[2:]
        == [
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "pre-tool-use",
        ]
    )


def _empty_doc() -> dict:
    """Return a fresh, empty event-keyed hooks document."""
    return {"hooks": {}}


def _read_hooks(hooks_path: Path) -> dict:
    """Read existing hooks.json content or return an empty event-keyed doc.

    Codex expects an event-keyed object root per
    developers.openai.com/codex/hooks (DDD-1, verified by SPIKE 2026-05-13):

        {"hooks": {"PreToolUse": [<matcher-group>, ...], ...}}

    Legacy top-level arrays produced by pre-FM-1 installs are auto-migrated
    into ``hooks.PreToolUse`` so re-install is idempotent without leaving the
    file in a Codex-incompatible shape.

    Args:
        hooks_path: Path to ~/.codex/hooks.json

    Returns:
        Event-keyed hooks document (always a dict with a 'hooks' dict).
    """
    if not hooks_path.exists():
        return _empty_doc()
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        # Malformed JSON: rebuild from scratch rather than silently keep bytes.
        return _empty_doc()

    # Legacy top-level array → migrate into PreToolUse.
    if isinstance(data, list):
        return {"hooks": {_PRE_TOOL_USE_EVENT: list(data)}}

    if isinstance(data, dict):
        hooks_obj = data.get("hooks")
        if not isinstance(hooks_obj, dict):
            # Unexpected shape (e.g. {"hooks": [...]}); normalise.
            data = _empty_doc()
        return data

    # Any other top-level type (number, string, null): rebuild.
    return _empty_doc()


def _is_nwave_matcher_group(
    entry: dict,
    launcher_path: Path | None = None,
    subcommand: str = "pre-tool-use",
) -> bool:
    """True if the matcher group contains a proven nWave DES handler."""
    if not isinstance(entry, dict):
        return False
    for handler in entry.get("hooks", []):
        if not isinstance(handler, dict):
            continue
        command = handler.get("command", "")
        if launcher_path is not None and _command_owns_launcher(
            command, launcher_path, subcommand
        ):
            return True
    return False


def _remove_nwave_hooks(
    doc: dict,
    launcher_path: Path | None = None,
    legacy_direct_command: str | None = None,
    *,
    subcommand: str = "pre-tool-use",
) -> dict:
    """Remove only proven nWave DES handlers from the doc.

    Operates on the event-keyed document shape. A handler is nWave-owned only
    when it invokes the canonical launcher; an adapter-module substring is not
    ownership evidence. Co-located foreign handlers stay in their matcher
    group, as do wholly foreign matcher groups.

    Args:
        doc: Event-keyed hooks document (``{"hooks": {<event>: [...], ...}}``)

    Returns:
        New document with nWave matcher groups filtered out of every event
        list. Empty event lists are kept (callers may re-append).
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("hooks"), dict):
        return _empty_doc()
    cleaned_events: dict = {}
    for event_name, entries in doc["hooks"].items():
        if not isinstance(entries, list):
            cleaned_events[event_name] = entries
            continue
        cleaned_entries: list[dict] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                cleaned_entries.append(entry)
                continue
            is_session_start_event = event_name == _SESSION_START_EVENT
            is_pretool_event = event_name == _PRE_TOOL_USE_EVENT

            def is_owned_handler(
                handler: object,
                *,
                session_start_event: bool = is_session_start_event,
                pretool_event: bool = is_pretool_event,
            ) -> bool:
                if not isinstance(handler, dict):
                    return False
                command = handler.get("command", "")
                owns_canonical = launcher_path is not None and _command_owns_launcher(
                    command, launcher_path, subcommand
                )
                owns_legacy_session_start = (
                    session_start_event
                    and subcommand == _SESSION_START_SUBCOMMAND
                    and launcher_path is not None
                    and _command_is_legacy_session_start(command, launcher_path)
                )
                owns_legacy_pretool = (
                    pretool_event
                    and legacy_direct_command is not None
                    and command == legacy_direct_command
                )
                return (
                    owns_canonical or owns_legacy_session_start or owns_legacy_pretool
                )

            owned_handler_present = any(
                isinstance(handler, dict) and is_owned_handler(handler)
                for handler in entry["hooks"]
            )
            retained_handlers = [
                handler for handler in entry["hooks"] if not is_owned_handler(handler)
            ]
            if not owned_handler_present:
                # An empty group, or a group with no nWave-owned command, is
                # a user-owned configuration surface.  It must survive a
                # reinstall byte-for-byte rather than being mistaken for an
                # emptied nWave matcher group.
                cleaned_entries.append(entry)
            elif retained_handlers:
                retained_entry = dict(entry)
                retained_entry["hooks"] = retained_handlers
                cleaned_entries.append(retained_entry)
        cleaned_events[event_name] = cleaned_entries
    return {"hooks": cleaned_events}


class CodexDESPlugin(InstallationPlugin):
    """Plugin for wiring nWave DES hooks into Codex CLI."""

    def __init__(self) -> None:
        """Initialize Codex DES plugin with name, priority, and dependencies."""
        super().__init__(name="codex-des", priority=55)
        self.dependencies = ["des", "codex-skills"]

    def validate_prerequisites(self, context: InstallContext) -> PluginResult:
        """Validate Codex CLI and DES prerequisites.

        Checks:
        1. ~/.codex/ directory exists OR `codex` binary in PATH (skip if neither)
        2. DES Python module is installed at ~/.claude/lib/python/des/

        Args:
            context: InstallContext with claude_dir

        Returns:
            PluginResult with success=True to skip/proceed, success=False on errors
        """
        codex_dir = _codex_config_dir()
        codex_binary = _shutil.which("codex") is not None

        if (
            "codex" not in context.target_platforms
            and not codex_dir.exists()
            and not codex_binary
        ):
            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Codex CLI not detected, skipping DES hook installation",
            )

        des_module = host_neutral_runtime_dir() / "des"
        if not des_module.exists():
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=(
                    f"DES Python module not found at {des_module}. Install DES first."
                ),
                errors=["DES module must be installed before Codex DES hooks"],
            )

        return PluginResult(
            success=True,
            plugin_name=self.name,
            message="Codex DES prerequisites validated",
        )

    def install(self, context: InstallContext) -> PluginResult:
        """Install DES PreToolUse hook entry into ~/.codex/hooks.json.

        Steps:
        1. Validate prerequisites (skip if Codex not detected)
        2. Resolve Python path and PYTHONPATH for the hook command
        3. Load existing hooks.json (or start with empty list)
        4. Remove any prior nWave DES entries (idempotent reinstall)
        5. Append new hook entry
        6. Write hooks.json and manifest

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            prereq = self.validate_prerequisites(context)
            if not prereq.success:
                return prereq
            if "skip" in prereq.message.lower():
                return prereq

            codex_dir = _codex_config_dir()
            codex_dir.mkdir(parents=True, exist_ok=True)

            python_path = resolve_python_command_for_spawn()
            pythonpath = resolve_des_lib_path_for_spawn()
            launcher_path = codex_dir / _LAUNCHER_FILENAME
            session_start_launcher_path = codex_dir / _SESSION_START_LAUNCHER_FILENAME
            resolver_path = _runtime_resolver_path()
            if not resolver_path.is_file() or resolver_path.is_symlink():
                raise FileNotFoundError(
                    "WHAT: Codex SessionStart cannot install because its "
                    f"host-neutral resolver is absent: {resolver_path}. "
                    "WHY: registering a hook whose installed implementation "
                    "does not exist would silently deprive Codex-only users "
                    "of standing-loop/parallelism/drain guidance. "
                    "HOW: install the DES runtime assets from the same public "
                    "candidate before registering Codex hooks."
                )
            hooks_path = codex_dir / _HOOKS_FILENAME
            existing_doc = _read_hooks(hooks_path)
            manifest_path = codex_dir / _MANIFEST_FILENAME
            try:
                legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                legacy_manifest = None
            legacy_direct_command = _legacy_direct_des_command(
                legacy_manifest, hooks_path, existing_doc
            )
            _write_launcher(launcher_path, python_path, pythonpath)
            _write_session_start_launcher(
                session_start_launcher_path, python_path, pythonpath, resolver_path
            )

            doc = _remove_nwave_hooks(
                existing_doc, launcher_path, legacy_direct_command
            )
            doc = _remove_nwave_hooks(
                doc,
                session_start_launcher_path,
                subcommand=_SESSION_START_SUBCOMMAND,
            )
            doc.setdefault("hooks", {})
            pretool_list = doc["hooks"].setdefault(_PRE_TOOL_USE_EVENT, [])
            new_entry = _build_launcher_hook_entry(launcher_path)
            pretool_list.append(new_entry)
            session_start = doc["hooks"].setdefault(_SESSION_START_EVENT, [])
            session_start.append(
                _build_session_start_hook_entry(session_start_launcher_path)
            )

            hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

            manifest = {
                "hooks_file": str(hooks_path),
                "python_path": python_path,
                "pythonpath": pythonpath,
                "launcher_file": str(launcher_path),
                "session_start_launcher_file": str(session_start_launcher_path),
                "resolver_script_file": str(resolver_path),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

            context.logger.info(f"  Codex DES hook installed in {hooks_path}")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Codex DES hook installed successfully",
                installed_files=[
                    hooks_path,
                    manifest_path,
                    launcher_path,
                    session_start_launcher_path,
                ],
            )

        except Exception as e:
            context.logger.error(f"  Failed to install Codex DES hook: {e}")
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex DES hook installation failed: {e!s}",
                errors=[str(e)],
            )

    def uninstall(self, context: InstallContext) -> PluginResult:
        """Remove nWave DES hook entries from ~/.codex/hooks.json.

        Reads hooks.json and removes only hooks proven by an exact nWave
        manifest witness: either the canonical launcher, or the v1 direct
        command derived from its three-field manifest. Launcher and manifest
        files are removed only when their expected generated bytes are also
        proven. User-created hooks and same-shaped foreign artifacts remain.

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating success or failure
        """
        try:
            codex_dir = _codex_config_dir()
            manifest_path = codex_dir / _MANIFEST_FILENAME
            launcher_path = codex_dir / _LAUNCHER_FILENAME
            session_start_launcher_path = codex_dir / _SESSION_START_LAUNCHER_FILENAME

            hooks_path = codex_dir / _HOOKS_FILENAME
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                manifest = None

            existing: dict | None = None
            legacy_direct_command: str | None = None
            if hooks_path.exists():
                existing = _read_hooks(hooks_path)
                legacy_direct_command = _legacy_direct_des_command(
                    manifest, hooks_path, existing
                )

            # A launcher is removable only when the manifest proves the exact
            # bytes we generated.  In particular, do not delete a file merely
            # because it occupies our historical pathname: a failed/partial
            # migration must not turn that into ownership of somebody else's
            # launcher.
            launcher_is_owned = False
            current_manifest_is_owned = (
                isinstance(manifest, dict)
                and set(manifest)
                == {
                    "hooks_file",
                    "python_path",
                    "pythonpath",
                    "launcher_file",
                    "session_start_launcher_file",
                    "resolver_script_file",
                }
                and manifest.get("hooks_file") == str(hooks_path)
                and manifest.get("launcher_file") == str(launcher_path)
                and manifest.get("session_start_launcher_file")
                == str(session_start_launcher_path)
                and manifest.get("resolver_script_file")
                == str(_runtime_resolver_path())
                and isinstance(manifest.get("python_path"), str)
                and manifest["python_path"]
                and isinstance(manifest.get("pythonpath"), str)
                and manifest["pythonpath"]
            )
            if current_manifest_is_owned:
                try:
                    launcher_is_owned = (
                        launcher_path.is_file()
                        and not launcher_path.is_symlink()
                        and launcher_path.read_text(encoding="utf-8")
                        == _launcher_source(
                            manifest["python_path"], manifest["pythonpath"]
                        )
                    )
                except (OSError, UnicodeDecodeError):
                    pass

            session_start_launcher_is_owned = False
            if current_manifest_is_owned:
                try:
                    session_start_launcher_is_owned = (
                        session_start_launcher_path.is_file()
                        and not session_start_launcher_path.is_symlink()
                        and session_start_launcher_path.read_text(encoding="utf-8")
                        == _session_start_launcher_source(
                            manifest["python_path"],
                            manifest["pythonpath"],
                            manifest["resolver_script_file"],
                        )
                    )
                except (OSError, UnicodeDecodeError):
                    pass

            # Public v1 sometimes had already written its transitional
            # launcher.  Its exact manifest + exact bytes + exact hook command
            # are the closed ownership witness for removing that file.
            legacy_launcher_is_owned = False
            if legacy_direct_command is not None and isinstance(manifest, dict):
                try:
                    legacy_launcher_is_owned = (
                        launcher_path.is_file()
                        and not launcher_path.is_symlink()
                        and launcher_path.read_text(encoding="utf-8")
                        == _v1_launcher_source(
                            manifest["python_path"], manifest["pythonpath"]
                        )
                        and legacy_direct_command
                        == shlex.join(
                            [
                                manifest["python_path"],
                                str(launcher_path),
                                "pre-tool-use",
                            ]
                        )
                    )
                except (KeyError, OSError, UnicodeDecodeError):
                    pass

            manifest_is_owned = (
                legacy_direct_command is not None
                or launcher_is_owned
                or session_start_launcher_is_owned
            )
            if hooks_path.exists():
                assert existing is not None
                cleaned = _remove_nwave_hooks(
                    existing,
                    launcher_path if launcher_is_owned else None,
                    legacy_direct_command,
                )
                cleaned = _remove_nwave_hooks(
                    cleaned,
                    session_start_launcher_path
                    if session_start_launcher_is_owned
                    else None,
                    subcommand=_SESSION_START_SUBCOMMAND,
                )
                events = cleaned.get("hooks", {}) if isinstance(cleaned, dict) else {}
                any_user_entries = any(
                    isinstance(v, list) and len(v) > 0 for v in events.values()
                )
                if any_user_entries:
                    hooks_path.write_text(
                        json.dumps(cleaned, indent=2) + "\n", encoding="utf-8"
                    )
                else:
                    hooks_path.unlink()
                context.logger.info(f"  Removed nWave DES hook from {hooks_path}")

            if launcher_is_owned or legacy_launcher_is_owned:
                launcher_path.unlink()
                context.logger.info(f"  Removed Codex DES launcher: {launcher_path}")

            if session_start_launcher_is_owned:
                session_start_launcher_path.unlink()
                context.logger.info(
                    "  Removed Codex SessionStart affordance launcher: "
                    f"{session_start_launcher_path}"
                )

            if (
                manifest_is_owned
                and manifest_path.exists()
                and not manifest_path.is_symlink()
            ):
                manifest_path.unlink()
                context.logger.info(f"  Removed Codex DES manifest: {manifest_path}")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Codex DES hook uninstalled",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex DES hook uninstall failed: {e}",
                errors=[str(e)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        """Verify the DES hook is present in ~/.codex/hooks.json.

        Checks:
        1. hooks.json exists and contains a nWave DES entry
        2. Manifest exists

        Args:
            context: InstallContext with shared installation utilities

        Returns:
            PluginResult indicating verification success or failure
        """
        try:
            codex_dir = _codex_config_dir()

            codex_binary = _shutil.which("codex") is not None
            if not codex_dir.exists() and not codex_binary:
                return PluginResult(
                    success=True,
                    plugin_name=self.name,
                    message="Codex CLI not detected, verification skipped",
                )

            errors: list[str] = []
            launcher_path = codex_dir / _LAUNCHER_FILENAME
            session_start_launcher_path = codex_dir / _SESSION_START_LAUNCHER_FILENAME
            resolver_path = _runtime_resolver_path()

            hooks_path = codex_dir / _HOOKS_FILENAME
            if not hooks_path.exists():
                errors.append(f"hooks.json not found: {hooks_path}")
            else:
                doc = _read_hooks(hooks_path)
                pretool = (
                    doc.get("hooks", {}).get(_PRE_TOOL_USE_EVENT, [])
                    if isinstance(doc, dict)
                    else []
                )
                nwave_entries = [
                    entry
                    for entry in pretool
                    if _is_nwave_matcher_group(entry, launcher_path)
                ]
                if not nwave_entries:
                    errors.append("No nWave DES hook entry found in hooks.json")
                elif not all(
                    _command_targets_launcher(hook.get("command", ""), launcher_path)
                    for entry in nwave_entries
                    for hook in entry.get("hooks", [])
                    if isinstance(hook, dict)
                ):
                    errors.append("DES hook does not target canonical launcher")

                session_start = doc.get("hooks", {}).get(_SESSION_START_EVENT, [])
                if not isinstance(session_start, list):
                    session_start = []
                session_commands = [
                    handler.get("command", "")
                    for entry in session_start
                    if isinstance(entry, dict) and isinstance(entry.get("hooks"), list)
                    for handler in entry["hooks"]
                    if isinstance(handler, dict)
                ]
                current_session_commands = [
                    command
                    for command in session_commands
                    if _command_owns_launcher(
                        command,
                        session_start_launcher_path,
                        _SESSION_START_SUBCOMMAND,
                    )
                ]
                legacy_session_commands = [
                    command
                    for command in session_commands
                    if _command_is_legacy_session_start(
                        command, session_start_launcher_path
                    )
                ]
                if (
                    len(current_session_commands) != 1
                    or legacy_session_commands
                    or len(current_session_commands) + len(legacy_session_commands) != 1
                ):
                    errors.append(
                        "Expected exactly one nWave SessionStart affordance hook"
                    )
                elif not _command_targets_launcher(
                    current_session_commands[0],
                    session_start_launcher_path,
                    _SESSION_START_SUBCOMMAND,
                ):
                    errors.append(
                        "SessionStart affordance hook does not target canonical launcher"
                    )

            manifest_path = codex_dir / _MANIFEST_FILENAME
            if not manifest_path.exists():
                errors.append(f"DES manifest not found: {manifest_path}")
            else:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                launcher_file = manifest.get("launcher_file")
                if launcher_file != str(launcher_path):
                    errors.append("DES manifest launcher path is not canonical")
                if not launcher_path.is_file():
                    errors.append("DES canonical launcher is missing")
                if manifest.get("session_start_launcher_file") != str(
                    session_start_launcher_path
                ):
                    errors.append(
                        "DES manifest SessionStart launcher path is not canonical"
                    )
                if manifest.get("resolver_script_file") != str(resolver_path):
                    errors.append("DES manifest resolver path is not canonical")
                if (
                    not session_start_launcher_path.is_file()
                    or session_start_launcher_path.is_symlink()
                ):
                    errors.append("Codex SessionStart launcher is missing or unsafe")
                if not resolver_path.is_file() or resolver_path.is_symlink():
                    errors.append(
                        "Host-neutral affordance resolver is missing or unsafe"
                    )

            if errors:
                return PluginResult(
                    success=False,
                    plugin_name=self.name,
                    message="Codex DES hook verification failed",
                    errors=errors,
                )

            context.logger.info("  Codex DES hook verified")

            return PluginResult(
                success=True,
                plugin_name=self.name,
                message="Codex DES hook verification passed",
            )

        except Exception as e:
            return PluginResult(
                success=False,
                plugin_name=self.name,
                message=f"Codex DES hook verification failed: {e}",
                errors=[str(e)],
            )
