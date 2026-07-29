"""Execute-verification of the HOW strings a gate prints when it refuses (GDP-4).

GDP-3 requires every rejection to say WHAT/WHY/HOW; GDP-4 requires the HOW to
invoke the tool that PRODUCES the artefact rather than describe a manual
repair. Neither is worth anything if the invocation the HOW prescribes is not
one the CLI actually accepts: a HOW naming a flag that does not exist looks
like guidance and is a dead end, which is worse than an honest absence.

This module extracts the ``des <subcommand>`` invocations embedded in HOW
strings and verifies them BY EXECUTION -- it runs each one and asks whether
the CLI's argument parser accepted the shape.

**Why the oracle keys on parser rejection and not on the exit code.** The
obvious oracle -- run ``des <cmd> --help`` and treat a non-zero exit as "no
such subcommand" -- reports ``des feature-delta-schema`` broken, because that
subcommand hand-rolls its usage and exits 1 on ``--help``. That oracle keys on
the FORM of one response instead of the property being asked about. The
property is "the CLI accepts this invocation shape", and argparse says so in
its own vocabulary (:data:`PARSE_REJECTIONS`) regardless of what the command
then does with the arguments.
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


def _split_arguments(raw: str) -> tuple[str, ...]:
    """The argument tokens of an invocation, keeping quoted spans whole."""
    return tuple(match.group(0) for match in re.finditer(_TOKEN, raw))


@dataclass(frozen=True)
class HowInvocation:
    """One ``des`` invocation prescribed by a HOW string."""

    module: Path
    line: int
    key: str
    subcommand: str
    arguments: tuple[str, ...]
    text: str

    @property
    def rendered(self) -> str:
        return " ".join(("des", self.subcommand, *self.arguments))


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


def _how_strings(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Every literal HOW payload in one parsed module: (line, key, text)."""
    found: list[tuple[int, str, str]] = []
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
                if keyword.arg in HOW_KEYS:
                    text = _literal_of(keyword.value)
                    if text:
                        found.append((keyword.value.lineno, keyword.arg, text))
    return found


def invocations_in(
    text: str, *, module: Path, line: int, key: str
) -> list[HowInvocation]:
    """The ``des`` invocations one HOW string prescribes."""
    return [
        HowInvocation(
            module=module,
            line=line,
            key=key,
            subcommand=match.group(1),
            arguments=_split_arguments(match.group(2) or ""),
            text=text,
        )
        for match in _INVOCATION_RE.finditer(text)
    ]


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


def _runnable(arguments: tuple[str, ...]) -> list[str]:
    """Placeholders swapped for a benign value so parsing can proceed."""
    return ["PLACEHOLDER" if _PLACEHOLDER_RE.match(a) else a for a in arguments]


def execute(invocation: HowInvocation, *, cwd: Path) -> str:
    """Run the prescribed invocation and return everything it printed."""
    completed = spawn(
        [
            python_for(None),
            "-m",
            "des",
            invocation.subcommand,
            *_runnable(invocation.arguments),
        ],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=180,
    )
    return completed.stdout + completed.stderr


def _unresolvable_shape(arguments: tuple[str, ...]) -> str | None:
    """Why this argument list cannot be execute-verified, or None if it can.

    An interpolation standing where a flag's VALUE goes still parses (the flag
    consumes whatever it is). One standing on its own can render to anything,
    including a flag or several tokens, so its arity is unknown until runtime.
    """
    for position, argument in enumerate(arguments):
        if argument != INTERPOLATION:
            continue
        preceding = arguments[position - 1] if position else ""
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
        reason = _unresolvable_shape(invocation.arguments)
        if reason is not None:
            unverifiable.append(Indeterminate(invocation=invocation, reason=reason))
            continue
        output = execute(invocation, cwd=cwd)
        hit = next((phrase for phrase in PARSE_REJECTIONS if phrase in output), None)
        if hit is None:
            continue
        said = next((ln.strip() for ln in output.splitlines() if hit in ln), hit)
        refused.append(Rejection(invocation=invocation, cli_said=said))
    return refused, unverifiable
