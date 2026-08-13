"""Regression witness -- the GENERATED Codex hook launcher spawns unbounded.

DEFECT. ``scripts/install/plugins/codex_des_plugin.py`` does not spawn: it EMITS a
launcher, as a string, that lands on the user's machine at install time and spawns
there. The emitted body was

    completed = subprocess.run(argv, env=env, check=False)

-- no ``timeout=`` and no explicit stdin decision. That is the same four-process
deadlock already diagnosed for ``des refactor --pile`` (RCA
``docs/feature/fix-inherited-stdin-deadlocks-spawns/rca.md``), reproduced in a file
we SHIP: the child reads whatever descriptor fd 0 happens to be, and if that
descriptor delivers data and never reaches EOF the child blocks forever while
nothing on the path holds a wall clock. The operator's Codex session hangs on a
PreToolUse hook.

WHY NO GATE CAUGHT IT. ``tests/build/test_no_unbounded_unstdin_spawn.py`` HAS this
file in its perimeter (``scripts/**``) and NOT in its allowlist, but its predicate
is pure-AST over the SOURCE: the plugin's own AST holds zero ``subprocess.*`` Call
nodes and two string literals containing ``subprocess.run``. At scan time the spawn
is DATA; it becomes CODE afterwards. That blindness is a second, separately-tracked
defect with tree-wide reach -- it is deliberately NOT fixed here, and neither the
ratchet's predicate nor its allowlist is touched by this slice.

WHAT IS PINNED, AND WHY IT IS BEHAVIOUR AND NOT SHAPE. The code under test is a
STRING, so a test grepping the generated text for ``timeout=`` would pin FORM and
would pass against a bound wired to nothing. Two of the three witnesses here EXECUTE
the generated launcher and assert an OBSERVABLE (it returned within a bound; the
hook payload reached the child). The third asserts a PROPERTY of the generated code
-- parsed as Python, every ``subprocess`` spawn in the RESULT carries an explicit
stdin decision and a bound -- which survives any rewrite of the generator.

THE CURE MUST NOT OVERSHOOT, AND HERE THAT MATTERS MORE THAN USUAL. The obvious
answer, ``stdin=subprocess.DEVNULL``, is WRONG for this file: the hook protocol is
JSON on stdin, and the DES adapter reads it (``hook_router.py:56``). DEVNULL would
starve every hook fire, and ``read_and_parse_stdin`` fails OPEN on empty input --
Codex validation would silently stop working. The explicit decision this launcher
owes is an explicit FORWARD. ``test_generated_launcher_delivers_the_payload_to_its_
child`` is the guard that fails if a future edit reaches for DEVNULL.

WHY THE FORWARD IS PASS-THROUGH AND NOT ``input=``. Reading the payload in the
launcher and handing it over as ``input=`` would move the unbounded read UP, into
the launcher, where no ``timeout=`` covers it -- the hang would move rather than
close. With pass-through the launcher never blocks on a read, so the child's read is
the only blocking wait on the path and the launcher's bound covers it. That is
exactly what the first witness observes.

BOUNDEDNESS IS A TEST-DESIGN REQUIREMENT. A witness that hangs is a second outage.
Every driver here is bounded on a wall clock, captures to TEMP FILES rather than
pipes (a pipe held open by a hung grandchild would block the reader -- the bug under
test), and is killed on every exit path.

active-RED at HEAD: witness 1 hangs against the shipped generator and fails on its
wall-clock bound with a semantic ``AssertionError``; witness 3 fails naming the
absent kwargs. Witness 2 is GREEN at HEAD by design -- its job is to fail if the
CURE regresses the protocol.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.install.plugins.codex_des_plugin import _launcher_source


# The launcher's own bound is generous by design (a PreToolUse validation doing
# real filesystem work must not be guillotined). These witnesses drive it through
# its operator lever instead of sleeping for the production default.
_TIMEOUT_ENV = "NWAVE_CODEX_HOOK_TIMEOUT"
_CHILD_BOUND_SECONDS = "2"
_DRIVER_BOUND_SECONDS = 30.0

_BOUNDABLE_SPAWNERS = {"run", "call", "check_call", "check_output"}
_SPAWNERS = _BOUNDABLE_SPAWNERS | {"Popen"}

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt",
    reason="the witness stands the child up as a shebang script (POSIX exec)",
)


def _stub_interpreter(tmp_path: Path, body: str) -> Path:
    """Stand up an executable that occupies the launcher's PYTHON_PATH slot.

    The launcher spawns ``[PYTHON_PATH, "-m", <adapter>, "pre-tool-use"]``. The stub
    ignores those arguments and plays only the part of the child that matters to the
    witness, so nothing here imports or runs the real DES adapter.
    """
    stub = tmp_path / "stub_python"
    stub.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    stub.chmod(0o755)
    return stub


def _write_launcher(tmp_path: Path, python_path: Path) -> Path:
    launcher = tmp_path / "nwave_claude_code_hook_adapter_launcher.py"
    launcher.write_text(
        _launcher_source(str(python_path), str(tmp_path / "runtime")), encoding="utf-8"
    )
    return launcher


def _drive(
    launcher: Path, tmp_path: Path, stdin_fd: int, env_overrides: dict[str, str]
) -> tuple[int, str, str]:
    """Run the launcher against a caller-owned stdin, bounded, capture to files."""
    out_path, err_path = tmp_path / "out.txt", tmp_path / "err.txt"
    env = {**os.environ, **env_overrides}
    with out_path.open("wb") as out, err_path.open("wb") as err:
        child = subprocess.Popen(
            [sys.executable, str(launcher), "pre-tool-use"],
            stdin=stdin_fd,
            stdout=out,
            stderr=err,
            env=env,
            start_new_session=True,
        )
        try:
            returncode = child.wait(timeout=_DRIVER_BOUND_SECONDS)
        except subprocess.TimeoutExpired:
            returncode = -1
        finally:
            if child.poll() is None:
                os.killpg(os.getpgid(child.pid), 9)
                child.wait(timeout=10)
    return (
        returncode,
        out_path.read_text(encoding="utf-8", errors="replace"),
        err_path.read_text(encoding="utf-8", errors="replace"),
    )


def _generated_subprocess_spawns(source: str) -> list[ast.Call]:
    """Return every ``subprocess.<spawner>(...)`` Call node in generated source."""
    tree = ast.parse(source)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SPAWNERS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]


@_POSIX_ONLY
def test_generated_launcher_returns_when_its_child_blocks_on_a_hostile_stdin(
    tmp_path: Path,
) -> None:
    """The four-process deadlock, reproduced through the file we ship.

    The launcher's stdin is a descriptor that DELIVERS DATA AND NEVER REACHES EOF --
    the only shape that blocks forever (an empty never-closed pipe is survivable).
    The child does the read the real adapter does. Unbounded, the launcher never
    returns: that is the operator's hung Codex session.
    """
    stub = _stub_interpreter(tmp_path, "import sys\nsys.stdin.read()\n")
    launcher = _write_launcher(tmp_path, stub)

    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'{"tool_name": "Bash"}')  # data, and never closed
        returncode, _, stderr = _drive(
            launcher, tmp_path, read_fd, {_TIMEOUT_ENV: _CHILD_BOUND_SECONDS}
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert returncode != -1, (
        "WHAT: the generated Codex hook launcher never returned; it was still "
        f"running after {_DRIVER_BOUND_SECONDS:g}s and had to be killed.\n"
        "WHY: it spawns the DES adapter with no wall-clock bound, and the child "
        "inherits a descriptor that delivers data and never reaches EOF, so it "
        "blocks in its stdin read with nothing on the path able to escape. On the "
        "operator's machine that is a Codex session hung on a PreToolUse hook.\n"
        "HOW: emit the spawn with an explicit `timeout=` (and an explicit stdin "
        "decision) in `_launcher_source` in "
        "scripts/install/plugins/codex_des_plugin.py."
    )
    assert returncode == 0, (
        "WHAT: the launcher gave up on its child but did not fail open "
        f"(exit {returncode}).\n"
        "WHY: a PreToolUse hook that cannot reach a verdict must degrade LOUD and "
        "allow, never block the operator's tool on its own timeout "
        "(claude_code_hook_adapter.py:73).\n"
        "HOW: on `subprocess.TimeoutExpired`, explain on stderr and exit 0.\n"
        f"--- launcher stderr ---\n{stderr}"
    )
    assert _TIMEOUT_ENV in stderr, (
        "WHAT: the launcher timed out without naming the operator's lever.\n"
        "WHY: a self-explaining timeout's HOW has to name a way out; without it "
        "the only remedy the operator can infer is uninstalling the hook.\n"
        f"HOW: name {_TIMEOUT_ENV} in the timeout message.\n"
        f"--- launcher stderr ---\n{stderr}"
    )


@_POSIX_ONLY
def test_generated_launcher_delivers_the_payload_to_its_child(tmp_path: Path) -> None:
    """Cure-must-not-overshoot: the hook payload still reaches the adapter.

    GREEN at HEAD. It fails if the explicit stdin decision is ever written as
    ``stdin=subprocess.DEVNULL``: the adapter reads the hook JSON from stdin and
    fails OPEN on empty input, so that cure would silently switch Codex validation
    off while every other test stayed green.
    """
    stub = _stub_interpreter(
        tmp_path, "import sys\nsys.stdout.write(sys.stdin.read())\n"
    )
    launcher = _write_launcher(tmp_path, stub)

    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'{"tool_name": "Bash", "session_id": "s-1"}')
        os.close(write_fd)  # a well-behaved harness closes: the child sees EOF
        write_fd = -1
        returncode, stdout, _ = _drive(launcher, tmp_path, read_fd, {})
    finally:
        os.close(read_fd)
        if write_fd != -1:
            os.close(write_fd)

    assert returncode == 0, f"launcher exited {returncode}, expected the child's 0"
    assert '"session_id": "s-1"' in stdout, (
        "WHAT: the hook payload written to the launcher's stdin did not reach the "
        f"child (child saw: {stdout!r}).\n"
        "WHY: the Codex hook protocol is JSON on stdin; the DES adapter reads it "
        "(hook_router.py:56) and fails OPEN on empty input, so starving the child "
        "-- e.g. with stdin=subprocess.DEVNULL -- disables validation SILENTLY.\n"
        "HOW: make the stdin decision an explicit FORWARD of the launcher's own "
        "stdin, not a DEVNULL."
    )


_DENIAL_REASON = "Invoke nw-mode-select before the first Bash/Write/Edit."
_DENIAL_CONFLICTING_REASON = "stdout-json-reason-that-must-not-win"
_DENIAL_CHILD_STDERR = "adapter wrote this directly to stderr"

# (child stdout, child stderr, substrings that must appear in the derived
# reason, substrings that must NOT). Every case exits 2; only the
# reason-derivation path differs -- top-level JSON reason, nested reason,
# stderr-wins-over-a-conflicting-JSON-reason, and the no-reason-found
# fallback.
_DENIAL_CASES = [
    pytest.param(
        json.dumps({"decision": "block", "reason": _DENIAL_REASON}),
        "",
        (_DENIAL_REASON,),
        (),
        id="stdout_top_level_reason",
    ),
    pytest.param(
        json.dumps(
            {
                "decision": "block",
                "hookSpecificOutput": {
                    "permissionDecisionReason": _DENIAL_REASON,
                },
            }
        ),
        "",
        (_DENIAL_REASON,),
        (),
        id="stdout_nested_hookSpecificOutput_reason",
    ),
    pytest.param(
        json.dumps({"decision": "block", "reason": _DENIAL_CONFLICTING_REASON}),
        _DENIAL_CHILD_STDERR,
        (_DENIAL_CHILD_STDERR,),
        (_DENIAL_CONFLICTING_REASON,),
        id="nonempty_child_stderr_wins_over_conflicting_stdout_reason",
    ),
    pytest.param(
        "not valid json, and no reason field either",
        "",
        ("WHAT", "WHY", "HOW"),
        (),
        id="reasonless_stdout_falls_back_to_what_why_how",
    ),
]


@_POSIX_ONLY
@pytest.mark.parametrize(
    ("child_stdout", "child_stderr", "must_contain", "must_not_contain"),
    _DENIAL_CASES,
)
def test_generated_launcher_translates_a_denial_into_codexs_native_block_json(
    tmp_path: Path,
    child_stdout: str,
    child_stderr: str,
    must_contain: tuple[str, ...],
    must_not_contain: tuple[str, ...],
) -> None:
    """rc=2: translate to Codex's native stdout-JSON block, exit 0, silent stderr.

    Codex's legacy exit-2-plus-stderr path is the one that produces "PreToolUse
    hook exited with code 2 but did not write a blocking reason to stderr" when
    stderr goes missing in transit. The robust boundary is Codex's documented
    normal-block shape: a single valid ``{"decision": "block", "reason": ...}``
    JSON document on stdout with the process exiting 0.
    """
    stub_body = (
        "import sys\n"
        "sys.stdin.read()\n"
        f"sys.stdout.write({child_stdout!r})\n"
        f"sys.stderr.write({child_stderr!r})\n"
        "sys.exit(2)\n"
    )
    stub = _stub_interpreter(tmp_path, stub_body)
    launcher = _write_launcher(tmp_path, stub)

    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'{"tool_name": "Bash"}')
        os.close(write_fd)  # a well-behaved harness closes: the child sees EOF
        write_fd = -1
        returncode, stdout, stderr = _drive(launcher, tmp_path, read_fd, {})
    finally:
        os.close(read_fd)
        if write_fd != -1:
            os.close(write_fd)

    assert returncode == 0, (
        "WHAT: the launcher did not translate the block into Codex's native "
        f"protocol (exit {returncode}).\n"
        "WHY: Codex reads a valid JSON decision:block/reason document on "
        "stdout with exit 0 as a normal block; propagating the legacy exit 2 "
        "is the path that produces Codex's stale-stderr UI noise.\n"
        f"--- launcher stdout ---\n{stdout}\n--- launcher stderr ---\n{stderr}"
    )
    assert stderr == "", (
        "WHAT: the translated block path wrote to stderr.\n"
        "WHY: the native protocol is a stdout JSON document on exit 0; "
        "writing ordinary blocking output to stderr here reintroduces the "
        "condition that makes Codex misreport the hook as failed.\n"
        f"--- launcher stderr ---\n{stderr}"
    )
    lines = stdout.splitlines()
    assert len(lines) == 1, (
        "WHAT: the launcher's stdout is not exactly one JSON document.\n"
        "WHY: the child's own stdout (the legacy Claude Code JSON) must not "
        "also be forwarded, or Codex sees two JSON documents where it "
        "expects one.\n"
        f"--- launcher stdout ---\n{stdout!r}"
    )
    payload = json.loads(lines[0])
    assert payload.get("decision") == "block", payload
    reason = payload.get("reason")
    assert isinstance(reason, str) and reason, payload
    assert all(expected in reason for expected in must_contain), (
        must_contain,
        reason,
    )
    assert not any(bad in reason for bad in must_not_contain), (
        must_not_contain,
        reason,
    )


@_POSIX_ONLY
def test_generated_launcher_does_not_duplicate_the_childs_own_json_on_denial(
    tmp_path: Path,
) -> None:
    """Falsifier: the child's legacy stdout JSON must not survive alongside it.

    A launcher that regressed to `sys.stdout.write(child_stdout)` unconditionally
    plus the new native payload would emit TWO JSON documents on stdout; Codex's
    parser expects exactly one.
    """
    # A distinctive extra key makes the child's raw JSON text byte-different
    # from the minimal {"decision", "reason"} payload the launcher emits, so a
    # substring match below cannot coincidentally pass.
    child_json = json.dumps(
        {
            "decision": "block",
            "reason": _DENIAL_REASON,
            "legacyMarkerNotPartOfNativePayload": True,
        }
    )
    stub_body = (
        f"import sys\nsys.stdin.read()\nsys.stdout.write({child_json!r})\nsys.exit(2)\n"
    )
    stub = _stub_interpreter(tmp_path, stub_body)
    launcher = _write_launcher(tmp_path, stub)

    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'{"tool_name": "Bash"}')
        os.close(write_fd)
        write_fd = -1
        returncode, stdout, stderr = _drive(launcher, tmp_path, read_fd, {})
    finally:
        os.close(read_fd)
        if write_fd != -1:
            os.close(write_fd)

    assert returncode == 0, f"launcher exited {returncode}, expected 0"
    assert "legacyMarkerNotPartOfNativePayload" not in stdout, (
        "WHAT: the child's raw legacy JSON survived in the launcher's stdout "
        "alongside the translated native payload.\n"
        "WHY: Codex must see exactly one JSON document; duplicating the "
        "child's stdout alongside the translated payload breaks that "
        "contract.\n"
        f"--- launcher stdout ---\n{stdout!r}"
    )
    assert len(stdout.splitlines()) == 1, (
        "WHAT: the launcher's stdout is not exactly one line/JSON document.\n"
        f"--- launcher stdout ---\n{stdout!r}"
    )
    assert stderr == "", f"expected empty stderr on the translated path, got {stderr!r}"


def test_generated_launcher_ensures_bounded_spawn_with_proper_channels() -> None:
    """Every spawn in the GENERATED code carries stdin decision, bound, and temp-file I/O.

    Asserted on the AST of the generator's OUTPUT, not on its text: the property
    holds through any rewrite of how the launcher is assembled. This is the same
    predicate ``tests/build/test_no_unbounded_unstdin_spawn.py`` applies to
    hand-written modules -- applied here where that scan cannot see, because the
    spawn is a string at scan time and code only after install.

    The observable safety contract combines three hazards: (1) a child that blocks
    on stdin drags the launcher down unless stdin is forwarded explicitly; (2) an
    unbounded spawn can hang forever if the child blocks; (3) pipes held open by
    grandchildren block subprocess.run's wait even after the direct child exits,
    perpetuating the deadlock this hook exists to close.
    """
    source = _launcher_source("/opt/nwave/bin/python", "/opt/nwave/runtime")
    tree = ast.parse(source)

    # Collect TemporaryFile context variables once
    temp_file_vars = {
        node.optional_vars.id
        for node in ast.walk(tree)
        if isinstance(node, ast.withitem)
        and isinstance(node.context_expr, ast.Call)
        and isinstance(node.context_expr.func, ast.Attribute)
        and node.context_expr.func.attr == "TemporaryFile"
        and isinstance(node.context_expr.func.value, ast.Name)
        and node.context_expr.func.value.id == "tempfile"
        and isinstance(node.optional_vars, ast.Name)
    }

    # Collect all subprocess spawns once
    spawns = _generated_subprocess_spawns(source)
    assert spawns, "the generated launcher no longer spawns; re-point this witness"

    offences: list[str] = []
    for node in spawns:
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        kwargs_names = {kw.arg for kw in node.keywords if kw.arg}

        # Check explicit stdin or input
        if not kwargs_names & {"stdin", "input"}:
            offences.append(
                f"line {node.lineno}: subprocess.{node.func.attr}(...) passes neither "
                f"stdin= nor input=, so the child INHERITS fd 0"
            )

        # Check timeout for boundable spawners
        if node.func.attr in _BOUNDABLE_SPAWNERS and "timeout" not in kwargs_names:
            offences.append(
                f"line {node.lineno}: subprocess.{node.func.attr}(...) is UNBOUNDED: "
                f"no timeout="
            )

        # Check no capture_output
        if "capture_output" in kwargs:
            offences.append(f"line {node.lineno}: capture_output=True")

        # Check stdout/stderr are TemporaryFile, not PIPE
        for channel in ("stdout", "stderr"):
            value = kwargs.get(channel)
            is_pipe = (
                isinstance(value, ast.Attribute)
                and value.attr == "PIPE"
                and isinstance(value.value, ast.Name)
                and value.value.id == "subprocess"
            )
            if is_pipe:
                offences.append(f"line {node.lineno}: {channel}=subprocess.PIPE")
            else:
                is_temp_file_var = (
                    isinstance(value, ast.Name) and value.id in temp_file_vars
                )
                if not is_temp_file_var:
                    offences.append(
                        f"line {node.lineno}: {channel}= not a TemporaryFile var"
                    )

    assert not offences, (
        "WHAT: the launcher generated by `_launcher_source` -- the file that lands "
        "on the operator's machine at install time -- does not consistently apply "
        "the observable safety contract for spawned subprocesses.\n"
        "WHY: this text becomes executable code on someone else's machine. The "
        "static spawn ban cannot see it (at scan time it is a string literal, not "
        "a Call node), so the hazard ships unchallenged into a PreToolUse hook.\n"
        "HOW: ensure every subprocess spawn in `_launcher_source` "
        "(scripts/install/plugins/codex_des_plugin.py) carries an explicit stdin "
        "decision (stdin= or input=), a timeout= for boundable spawners, and uses "
        "TemporaryFile rather than PIPE for stdout and stderr. Do NOT widen the "
        "allowlist in tests/build/test_no_unbounded_unstdin_spawn.py.\n"
        "--- offending sites ---\n" + "\n".join(offences)
    )
