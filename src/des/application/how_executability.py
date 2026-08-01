"""Execute-verification of the HOW strings a gate prints when it refuses (GDP-4).

GDP-3 requires every rejection to say WHAT/WHY/HOW; GDP-4 requires the HOW to
invoke the tool that PRODUCES the artefact rather than describe a manual
repair. Neither is worth anything if the invocation the HOW prescribes is not
one the CLI actually accepts: a HOW naming a flag that does not exist looks
like guidance and is a dead end, which is worse than an honest absence.

This module extracts the invocations embedded in HOW strings -- ``des
<subcommand>`` AND script invocations (``python3 scripts/...``, ``python -m
scripts...``, ``uv run python3 scripts/...``) -- and verifies them BY
EXECUTION -- it runs each one and asks whether the CLI's/script's argument
parser accepted the shape.

**Why the oracle keys on parser rejection and not on the exit code.** The
obvious oracle -- run ``des <cmd> --help`` and treat a non-zero exit as "no
such subcommand" -- reports ``des feature-delta-schema`` broken, because that
subcommand hand-rolls its usage and exits 1 on ``--help``. That oracle keys on
the FORM of one response instead of the property being asked about. The
property is "the CLI accepts this invocation shape", and argparse says so in
its own vocabulary (:data:`PARSE_REJECTIONS`) regardless of what the command
then does with the arguments. The same discipline applies to a script
invocation: a script that does not exist on disk is refused (the script-side
twin of an unknown ``des`` subcommand); a script whose OWN argparse rejects a
flag is refused via the same :data:`PARSE_REJECTIONS` vocabulary; a script
that runs and then reports a problem it found is NOT refused.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.runtime.interpreter import python_for
from des.runtime.spawn import spawn


if TYPE_CHECKING:
    from pathlib import Path


#: Dict keys and keyword arguments that carry a GDP-3 HOW payload. Two names
#: for one device: ``verify_readiness_pre_dispatch`` calls it ``remediation``.
HOW_KEYS = frozenset({"how", "remediation"})

#: argparse's own wording for "I do not accept this invocation shape". Keying
#: on these makes the oracle independent of what any command does after its
#: arguments parse -- see the module docstring.
PARSE_REJECTIONS = (
    "invalid choice",
    "unrecognized arguments",
    "no such option",
    "expected one argument",
    "unknown subcommand",
)

#: Marker substituted for an f-string interpolation, so a value only known at
#: runtime is treated as a placeholder rather than as a literal argument.
INTERPOLATION = "<INTERPOLATED>"

#: A single argument as it appears in prose. Quoted forms come FIRST so a
#: multi-word `"<commit message>"` is read as the one argument it is, instead
#: of being truncated at the opening quote -- which would leave a dangling
#: flag and make a correct HOW look refused.
_TOKEN = (
    r"""(?:"[^"]*"|'[^']*'|--[a-z][a-z0-9-]*|<[^>]*>?|\{[^}]*\}|[A-Za-z0-9._/@=-]+)"""
)
_INVOCATION_RE = re.compile(rf"\bdes\s+([a-z][a-z0-9-]*)((?:\s+{_TOKEN})*)")
_PLACEHOLDER_RE = re.compile(r"""^(<.*|.*>|\{.*\}|"[^"]*"|'[^']*'|\.\.\.)$""")

#: A script's own target: a ``scripts/``-rooted file path, a dotted
#: ``scripts.`` module (the ``-m`` form), or an interpolation marker -- the
#: script's own identity is sometimes only known at runtime (built from
#: ``Path(__file__)`` inside a HOW-builder helper), and that case must still
#: be COLLECTED (visible) rather than silently dropped; :func:`_unresolvable_shape`
#: is what turns an interpolated target into could-not-verify rather than a
#: false pass or a false refusal.
_SCRIPT_TARGET = (
    r"scripts/[A-Za-z0-9_./-]+\.py"
    r"|scripts(?:\.[A-Za-z0-9_]+)+"
    rf"|{re.escape(INTERPOLATION)}"
)
#: ``python``/``python3``, optionally ``uv run``-prefixed and/or ``-m``-invoked,
#: naming a script target. B1 (RCA): the CLI-only :data:`_INVOCATION_RE` above
#: is blind to this whole population -- every script HOW outside ``des`` used
#: this shape and none of them were ever execute-verified.
_SCRIPT_INVOCATION_RE = re.compile(
    rf"\b(?:uv\s+run\s+)?python3?\s+(?:-m\s+)?({_SCRIPT_TARGET})((?:\s+{_TOKEN})*)"
)


def _split_arguments(raw: str) -> tuple[str, ...]:
    """The argument tokens of an invocation, keeping quoted spans whole."""
    return tuple(match.group(0) for match in re.finditer(_TOKEN, raw))


@dataclass(frozen=True)
class HowInvocation:
    """One invocation prescribed by a HOW string -- a ``des`` subcommand or a script.

    ``kind`` distinguishes the two shapes ``execute()`` and
    ``_unresolvable_shape()`` branch on: ``"des"`` (the default, back-compatible
    shape) routes through ``python -m des <target>``; ``"script"`` routes
    through the script named by ``target`` directly (a file path) or via
    ``-m`` (when ``is_module_form`` is set, a dotted ``scripts.`` module).
    """

    module: Path
    line: int
    key: str
    target: str
    arguments: tuple[str, ...]
    text: str
    kind: str = "des"
    is_module_form: bool = False

    @property
    def rendered(self) -> str:
        if self.kind == "script":
            prefix = "python -m" if self.is_module_form else "python"
            return " ".join((prefix, self.target, *self.arguments))
        return " ".join(("des", self.target, *self.arguments))


@dataclass(frozen=True)
class Rejection:
    """A HOW whose prescribed invocation the CLI refuses to parse."""

    invocation: HowInvocation
    cli_said: str


@dataclass(frozen=True)
class Indeterminate:
    """A HOW whose prescribed shape is only known at runtime.

    ``des blast-radius --repo {repo} {scope_arg}`` renders its scope as
    ``--all`` or ``--paths a b`` depending on the caller: statically its arity
    is unknown, so executing it with a stand-in argument proves nothing. Per
    GDP-6 this degrades LOUD -- it is a third state that must reach the
    aggregate, never a silent pass and never a false rejection.
    """

    invocation: HowInvocation
    reason: str


def _literal_of(node: ast.AST) -> str | None:
    """The string a node evaluates to, with interpolations marked, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
            else INTERPOLATION
            for part in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_of(node.left), _literal_of(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _how_builder_functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    """Every function in ``tree`` whose name marks it as a HOW-string builder.

    A HOW payload built by a helper -- ``how=_how_explain(doc_path, node_id)``
    -- is otherwise invisible: ``_literal_of`` only reads Assign / Dict-key /
    keyword payloads that are ALREADY a literal, and a ``Call`` node is none of
    those. Any function whose name contains "how" (case-insensitive) is a
    builder candidate; only its RETURN literal is ever read -- the module
    under audit is never imported or executed.
    """
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and "how" in node.name.lower()
    }


def _call_name(call: ast.Call) -> str | None:
    """The plain name a call site invokes, for ``f()`` and ``obj.f()`` alike."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _how_builder_return_literal(
    call: ast.Call, builders: dict[str, ast.FunctionDef]
) -> str | None:
    """The literal a HOW-builder function call RETURNS, else None.

    A pure AST read: the callee is looked up by name among ``builders`` and
    its ``return`` statements are inspected for a literal -- nothing is
    imported or executed.
    """
    name = _call_name(call)
    if name is None:
        return None
    builder = builders.get(name)
    if builder is None:
        return None
    for node in ast.walk(builder):
        if isinstance(node, ast.Return) and node.value is not None:
            literal = _literal_of(node.value)
            if literal:
                return literal
    return None


def _how_strings(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Every literal HOW payload in one parsed module: (line, key, text)."""
    found: list[tuple[int, str, str]] = []
    builders = _how_builder_functions(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (
                    "HOW" in target.id or "REMEDIATION" in target.id
                ):
                    text = _literal_of(node.value)
                    if text:
                        found.append((node.lineno, target.id, text))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=False):
                if isinstance(key, ast.Constant) and key.value in HOW_KEYS:
                    text = _literal_of(value)
                    if text:
                        found.append((key.lineno, str(key.value), text))
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg not in HOW_KEYS:
                    continue
                text = _literal_of(keyword.value)
                if text is None and isinstance(keyword.value, ast.Call):
                    text = _how_builder_return_literal(keyword.value, builders)
                if text:
                    found.append((keyword.value.lineno, keyword.arg, text))
    return found


def invocations_in(
    text: str, *, module: Path, line: int, key: str
) -> list[HowInvocation]:
    """The invocations one HOW string prescribes -- ``des`` subcommands and scripts."""
    found = [
        HowInvocation(
            module=module,
            line=line,
            key=key,
            kind="des",
            target=match.group(1),
            arguments=_split_arguments(match.group(2) or ""),
            text=text,
        )
        for match in _INVOCATION_RE.finditer(text)
    ]
    found.extend(
        HowInvocation(
            module=module,
            line=line,
            key=key,
            kind="script",
            target=match.group(1),
            is_module_form="/" not in match.group(1),
            arguments=_split_arguments(match.group(2) or ""),
            text=text,
        )
        for match in _SCRIPT_INVOCATION_RE.finditer(text)
    )
    return found


def collect_invocations(source_root: Path) -> list[HowInvocation]:
    """Every ``des`` invocation prescribed by a HOW string under ``source_root``."""
    collected: list[HowInvocation] = []
    for path in sorted(source_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for line, key, text in _how_strings(tree):
            collected.extend(invocations_in(text, module=path, line=line, key=key))
    return collected


def _enumerated_choice(placeholder: str) -> str | None:
    """The first concrete alternative an enumerated placeholder names, else None.

    ``<bugfix|prefactoring|charter|...>`` tells the reader its own legal
    values inline. Substituting the literal ``"PLACEHOLDER"`` for it
    manufactures an "invalid choice" that proves nothing about the
    invocation's SHAPE (GDP-8 designation error): the property under test is
    "the CLI accepts this shape", and the placeholder already names a value
    the CLI does accept -- so use one of its own alternatives instead of a
    value the checker invented.
    """
    inner = placeholder.strip()
    if (inner.startswith("<") and inner.endswith(">")) or (
        inner.startswith("{") and inner.endswith("}")
    ):
        inner = inner[1:-1]
    else:
        return None
    if "|" not in inner:
        return None
    for alternative in inner.split("|"):
        alternative = alternative.strip()
        if alternative and alternative != "...":
            return alternative
    return None


def _runnable(arguments: tuple[str, ...]) -> list[str]:
    """Placeholders swapped for a benign value so parsing can proceed."""
    runnable: list[str] = []
    for argument in arguments:
        if not _PLACEHOLDER_RE.match(argument):
            runnable.append(argument)
            continue
        choice = _enumerated_choice(argument)
        runnable.append(choice if choice is not None else "PLACEHOLDER")
    return runnable


def _script_path(invocation: HowInvocation, *, cwd: Path) -> Path:
    """Where ``invocation``'s script would live on disk, resolved against ``cwd``."""
    if invocation.is_module_form:
        return (cwd / Path(*invocation.target.split("."))).with_suffix(".py")
    return cwd / invocation.target


def _script_exists(invocation: HowInvocation, *, cwd: Path) -> bool:
    """Whether the script a HOW names is actually on disk.

    The script-side twin of ``des``'s "invalid choice" for an unknown
    subcommand: a HOW routing to a script that was never shipped must not
    pass, and checked BEFORE executing so the refusal names the real cause
    instead of a stderr string an ``ImportError``/``FileNotFoundError``
    happens to print.
    """
    return _script_path(invocation, cwd=cwd).is_file()


def execute(invocation: HowInvocation, *, cwd: Path) -> str:
    """Run the prescribed invocation and return everything it printed."""
    python = python_for(None)
    if invocation.kind == "script":
        argv = (
            [python, "-m", invocation.target, *_runnable(invocation.arguments)]
            if invocation.is_module_form
            else [python, invocation.target, *_runnable(invocation.arguments)]
        )
    else:
        argv = [
            python,
            "-m",
            "des",
            invocation.target,
            *_runnable(invocation.arguments),
        ]
    completed = spawn(
        argv,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=180,
    )
    return completed.stdout + completed.stderr


#: Script directories whose default (flagless) action performs a REAL,
#: side-effecting action rather than failing fast on a missing required
#: argument. Every ``des`` subcommand audited here declares at least one
#: REQUIRED argument, so a bare invocation is safely rejected by argparse
#: itself before any business logic runs -- but a script under
#: ``scripts/install/`` is designed to be runnable with ZERO flags (every one
#: of its flags is optional, default action = install for real), so
#: execute-verifying its shape would mutate the operator's own environment.
#: Path-prefix-based, not name-based, so any future script placed under the
#: same directory inherits the guard without a per-file allowlist entry.
_SIDE_EFFECTING_SCRIPT_DIRS = ("scripts/install/",)


def _is_side_effecting_script(invocation: HowInvocation) -> bool:
    normalized = (
        invocation.target.replace(".", "/") + "/"
        if invocation.is_module_form
        else invocation.target
    )
    return any(normalized.startswith(prefix) for prefix in _SIDE_EFFECTING_SCRIPT_DIRS)


def _unresolvable_shape(invocation: HowInvocation) -> str | None:
    """Why this invocation cannot be execute-verified, or None if it can.

    An interpolation standing where a flag's VALUE goes still parses (the flag
    consumes whatever it is). One standing on its own can render to anything,
    including a flag or several tokens, so its arity is unknown until runtime.
    A script whose own TARGET is only known at runtime (built inside a
    HOW-builder helper from ``Path(__file__)``, e.g.) is unresolvable for the
    same reason: there is no static answer to "which script" to execute.

    A script under a known side-effecting directory (:data:`_SIDE_EFFECTING_SCRIPT_DIRS`)
    is unresolvable for a THIRD reason: unlike a ``des`` subcommand -- which
    always declares a required argument, so a bare invocation fails fast at
    argparse before any business logic runs -- a script like the installer
    accepts zero arguments and its flagless default IS the real action.
    Executing it "just to check the shape" would mutate the operator's own
    environment, so it degrades to could-not-verify instead.
    """
    if invocation.target == INTERPOLATION:
        return (
            "the invoked script's own path is only known at runtime (built "
            "from an interpolated expression); its identity cannot be "
            "verified statically"
        )
    if invocation.kind == "script" and _is_side_effecting_script(invocation):
        return (
            f"{invocation.target} lives under a side-effecting script directory "
            f"({', '.join(_SIDE_EFFECTING_SCRIPT_DIRS)}) whose flagless default "
            "action performs a real, mutating action (e.g. an install) rather "
            "than failing fast on a missing required argument; running it for "
            "shape-verification would mutate the operator's own environment"
        )
    for position, argument in enumerate(invocation.arguments):
        if argument != INTERPOLATION:
            continue
        preceding = invocation.arguments[position - 1] if position else ""
        if not preceding.startswith("--"):
            return (
                "carries a runtime-interpolated argument in a standalone position; "
                "its arity is unknown until the gate renders it"
            )
    return None


def rejections(
    invocations: list[HowInvocation], *, cwd: Path
) -> tuple[list[Rejection], list[Indeterminate]]:
    """Execute-verify each prescribed invocation: refused, and could-not-verify.

    Returns BOTH outcomes. Handing back only the refusals would let the
    could-not-verify population disappear from the aggregate, which is the
    silent-pass GDP-6 forbids -- a caller must be able to see that some HOWs
    were never actually proven.
    """
    refused: list[Rejection] = []
    unverifiable: list[Indeterminate] = []
    for invocation in invocations:
        reason = _unresolvable_shape(invocation)
        if reason is not None:
            unverifiable.append(Indeterminate(invocation=invocation, reason=reason))
            continue
        if invocation.kind == "script" and not _script_exists(invocation, cwd=cwd):
            refused.append(
                Rejection(
                    invocation=invocation,
                    cli_said=(
                        f"no such script on disk: {invocation.target} "
                        "(python would refuse with FileNotFoundError / "
                        "ModuleNotFoundError before its own parser ever runs)"
                    ),
                )
            )
            continue
        output = execute(invocation, cwd=cwd)
        hit = next((phrase for phrase in PARSE_REJECTIONS if phrase in output), None)
        if hit is None:
            continue
        said = next((ln.strip() for ln in output.splitlines() if hit in ln), hit)
        refused.append(Rejection(invocation=invocation, cli_said=said))
    return refused, unverifiable
