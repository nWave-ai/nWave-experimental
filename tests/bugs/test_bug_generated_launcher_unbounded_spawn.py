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


def test_generated_launcher_bounds_its_spawn_and_decides_stdin() -> None:
    """Every spawn in the GENERATED code carries a stdin decision and a bound.

    Asserted on the AST of the generator's OUTPUT, not on its text: the property
    holds through any rewrite of how the launcher is assembled, and cannot be
    satisfied by a substring. This is the same predicate
    ``tests/build/test_no_unbounded_unstdin_spawn.py`` applies to hand-written
    modules -- applied where that scan cannot see, because here the spawn is a
    string at scan time and code only after install.
    """
    source = _launcher_source("/opt/nwave/bin/python", "/opt/nwave/runtime")
    tree = ast.parse(source)

    spawns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SPAWNERS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert spawns, "the generated launcher no longer spawns; re-point this witness"

    offences: list[str] = []
    for node in spawns:
        kwargs = {kw.arg for kw in node.keywords if kw.arg}
        if not kwargs & {"stdin", "input"}:
            offences.append(
                f"generated line {node.lineno}: subprocess.{node.func.attr}(...) "
                f"passes neither stdin= nor input=, so the child INHERITS fd 0 "
                f"transitively"
            )
        elif node.func.attr in _BOUNDABLE_SPAWNERS and "timeout" not in kwargs:
            offences.append(
                f"generated line {node.lineno}: subprocess.{node.func.attr}(...) is "
                f"UNBOUNDED: no timeout=, so a blocked child hangs the hook forever"
            )

    assert not offences, (
        "WHAT: the launcher generated by `_launcher_source` -- the file that lands "
        "on the operator's machine at install time -- spawns without an explicit "
        "stdin decision or without a wall-clock bound.\n"
        "WHY: this text becomes executable code on someone else's machine. The "
        "static spawn ban cannot see it (at scan time it is a string literal, not "
        "a Call node), so the hazard ships unchallenged into a PreToolUse hook.\n"
        "HOW: pass both kwargs in the emitted body in `_launcher_source` "
        "(scripts/install/plugins/codex_des_plugin.py). Do NOT widen the allowlist "
        "in tests/build/test_no_unbounded_unstdin_spawn.py, and do NOT change that "
        "ban's predicate here.\n"
        "--- offending generated sites ---\n" + "\n".join(offences)
    )
