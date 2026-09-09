"""The terminal block every invocable DES step writes, and nothing else.

ADR-SSOT-002 Section 4b: «The DES exposes steps that may be invoked singly.
Each takes minimal typed input and returns one closed outcome -- `Success |
Refusal | Retry | Indeterminate` -- with WHAT / WHY / HOW and, where a role
ran, that role's DIAGNOSTIC forwarded verbatim.»  Beside those the terminal
carries `ORCHESTRATOR`, `NEXT` and `HOW-TO-INVOKE` as data the step does not
act on.

ADR-DES-003 Section 3 makes that block a CONTRACT with laws, and this module is
where they are made unrepresentable rather than reviewable:

- **G1** one outcome first, one `HOW-TO-INVOKE` last, one stream.
- **G2** `WHAT`/`WHY`/`HOW` present exactly when the outcome is not `Success`.
- **G3** a terminal names only rows it carries.
- **G5** `ORCHESTRATOR` is DERIVED from primitive rows and never authored by a
  step; on `Success` it is absent, because the move available now IS `NEXT` and
  a second sentence saying so is waste (GDP-10).
- **G6** `TURNS-BOUGHT` and `ROLE` are primitive rows with named consumers: the
  orchestrator's cost and liveness judgement, and G5's own derivation.
- **G7** the fork is the COUNT of `NEXT` lines. One lawful move prints one.

A step passes FACTS and a closed outcome; it writes no sentence about the block.
That is what stops a step naming a row it does not carry, measured twice on this
lane: a constant naming `BLOCKED-BY` over a software refusal that printed
neither, and a success sentence promising `ORACLE-RED` on a branch that prints
none.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.delivery_disposition import Disposition
from des.domain.orchestrator_terminal import diagnostic_line


if TYPE_CHECKING:
    from pathlib import Path


HOW_TO_INVOKE = (
    "every DES step is invoked alone -- `des <step> --repo-root <root> ...` -- "
    "and returns one closed outcome plus the canonical next step as DATA; no "
    "step executes what its own NEXT names, and the orchestrator may ignore it"
)

#: What a step prints when the canonical order has nothing further to name.
NOTHING_OWED = "no step is owed"

#: The rows a refusal may point its reader at, in the order it names them.
#: Each is printed only when the step measured it, which is what lets the
#: `ORCHESTRATOR` line below be DERIVED rather than written per step.
_POINTABLE = ("BLOCKED-BY", "DEFECT-OWNER")


@dataclass(frozen=True, slots=True)
class StepRefusal:
    """Why a step did not do its work, already WHAT / WHY / HOW.

    ONE carrier for the disposition (ADR-DES-003 §4): three spellings of the same
    four-valued answer existed -- two booleans here, two on `Blocked`, and the
    `Disposition` enum -- and seven CLI files re-derived it by comparing
    `disposition.value` to a string. A value spelled three ways is a value three
    sites can disagree about, so the enum is carried directly.
    """

    what: str
    why: str
    how: str
    disposition: Disposition = Disposition.Refusal

    @property
    def outcome(self) -> str:
        return self.disposition.value


def _row(lines: list[str], label: str) -> str | None:
    for line in lines:
        if line.startswith(f"{label}: "):
            return line[len(label) + 2 :]
    return None


def orchestrator_line(rows: list[str]) -> str:
    """The move a refusal leaves, DERIVED from the rows this block prints (G5).

    Two measured incidents shaped it. A step used to hand over a finished
    sentence, and one told its reader to «read BLOCKED-BY and the DIAGNOSTIC
    below» over a software refusal that printed neither. The replacement read
    «did a role run» off the diagnostic, and a paid turn whose envelope the
    boundary refused -- no diagnostic, process ran -- was reported as no turn at
    all. So this reads the primitive rows instead: the turns bought, the role
    that ran, and which pointable rows are present.
    """
    bought = _row(rows, "TURNS-BOUGHT")
    if bought is None or bought == "0":
        return (
            "no role turn ran: the software refused before buying one, so the "
            "HOW above is the whole move"
        )
    role = _row(rows, "ROLE") or "role"
    if _row(rows, "DIAGNOSTIC") is None:
        return (
            f"the {role} turn was bought and its answer did not survive the "
            "provider boundary, so there is no DIAGNOSTIC to read: the HOW "
            "above is the whole move, and the turn is spent"
        )
    named = [label for label in _POINTABLE if _row(rows, label) is not None]
    pointed = " and ".join([*named, "the DIAGNOSTIC"])
    return f"read {pointed} below: they are {role}'s own answer and what it left"


def _emit(
    outcome: str,
    facts: list[str],
    failure: tuple[str, str, str] | None,
    step: str | tuple[str, ...],
    *,
    turns_bought: int,
    role: str | None,
    diagnostic: str | None,
) -> None:
    """One terminal, one stream, in the order G1 fixes.

    stdout, whatever the outcome: a step has no `--json` projection to keep
    parseable -- Section 4b makes the LINE the machine form -- so splitting the
    block across two streams would cost a reader the guarantee that the lines
    arrive in the order they were written.
    """
    rows = [f"DELIVERY-OUTCOME: {outcome}", *facts, f"TURNS-BOUGHT: {turns_bought}"]
    if role is not None:
        rows.append(f"ROLE: {role}")
    if failure is not None:
        what, why, how = failure
        rows += [f"WHAT: {what}", f"WHY: {why}", f"HOW: {how}"]
    if diagnostic is not None:
        rows.append(diagnostic_line(diagnostic))
    if failure is not None:
        # G5: derived AFTER the rows exist, so it can only name what is there,
        # and absent on Success where `NEXT` already is the move.
        rows.insert(
            len(rows) - (1 if diagnostic is not None else 0),
            f"ORCHESTRATOR: {orchestrator_line(rows)}",
        )
    steps = (step,) if isinstance(step, str) else step
    rows += [f"NEXT: {item}" for item in steps]
    rows.append(f"HOW-TO-INVOKE: {HOW_TO_INVOKE}")
    print("\n".join(rows))
    sys.stdout.flush()


def succeed(
    facts: list[str],
    step: str | tuple[str, ...],
    *,
    turns_bought: int = 0,
    role: str | None = None,
    diagnostic: str | None = None,
) -> int:
    _emit(
        Disposition.Success.value,
        facts,
        None,
        step,
        turns_bought=turns_bought,
        role=role,
        diagnostic=diagnostic,
    )
    return 0


def refuse(
    refusal: StepRefusal,
    step: str | tuple[str, ...],
    *,
    facts: list[str] | None = None,
    turns_bought: int = 0,
    role: str | None = None,
    diagnostic: str | None = None,
) -> int:
    """A refusal still carries what the step MEASURED before it refused.

    `facts` is that evidence -- the executed RED, the owner a reviewer named --
    and it is printed above the WHAT. Section 4b: a step's terminal must not
    omit a fact the software already held, and a refusal that drops its own
    measurement leaves the orchestrator deciding on the designation.
    """
    _emit(
        refusal.outcome,
        list(facts or ()),
        (refusal.what, refusal.why, refusal.how),
        step,
        turns_bought=turns_bought,
        role=role,
        diagnostic=diagnostic,
    )
    return 1


def read_request(stream: object | None = None) -> str | StepRefusal:
    """One non-empty strict-UTF-8 Request from stdin, never rewritten.

    Strict, because a Request is the key the handover is stored under: a byte
    replaced by a decoder would make the next invocation of the same Request
    look like a different one.
    """
    source = sys.stdin if stream is None else stream
    buffer = getattr(source, "buffer", None)
    raw = buffer.read() if buffer is not None else source.read()  # type: ignore[union-attr]
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raw = None
    if not raw:
        return StepRefusal(
            "InvalidRequest",
            "stdin must carry one non-empty strict-UTF-8 Request",
            "pipe the Request into this step on stdin",
        )
    return raw


def resolved_root(raw: Path) -> Path | StepRefusal:
    """The one physical repository root, or the refusal that it is not one."""
    if not raw.is_absolute() or not raw.is_dir() or raw.is_symlink():
        return StepRefusal(
            "InvalidRepositoryRoot",
            f"{raw} is not an absolute real directory",
            "pass the physical repository root",
        )
    return raw.resolve()
