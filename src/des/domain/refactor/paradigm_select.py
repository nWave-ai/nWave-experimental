"""Paradigm-select domain -- refuses cross-application of the wrong lens.

CREATE_NEW (des-refactor-fixer-swarm slice-05, feature-delta D10, AT-9). Pure
Python, no I/O -- ``CONTRACT_SHAPE: pure-function``.

D10: read the pile item's OWN declared field; refuse (never guess/cross-apply)
on mismatch or absence. The recognized closed set mirrors this feature's own
already-committed pile-grammar precedent (``tests/des/refactor/composition.py``'s
``_DEFAULT_PARADIGM``, ``des.cli.refactor``'s grammar example) and this repo's
own ``CLAUDE.md`` "## Development Paradigm" convention -- deliberately NOT the
``oop``/``fp`` abbreviation pair used by the unrelated ``nw-design
--paradigm=[auto|oop|fp]`` CLI knob.

The test-side ``tests/des/refactor/domain_types.py:DeclaredParadigm`` enum is
a DISTILL-authored mirror of this exact closed set for the acceptance tests'
own typed-parameter convention (Mandate 12) -- production code never imports
test code, so the two enums are independently declared and must be kept in
sync by construction (both enumerate exactly ``{"object-oriented",
"functional"}``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecognizedParadigm(str, Enum):
    """The recognized closed set of declared-paradigm lens tokens a pile item
    may carry (D10). ``select_paradigm_lens`` accepts ONLY these two values;
    any other parsed token -- garbage word, near-miss abbreviation, or
    wrong-case variant -- refuses before dispatch (AT-9)."""

    OBJECT_ORIENTED = "object-oriented"
    FUNCTIONAL = "functional"


@dataclass(frozen=True)
class ParadigmSelection:
    """The outcome of selecting a paradigm lens for a pile item's declared
    field -- a WHAT/WHY/HOW-shaped refusal on the negative path, never a bare
    bool (Earned Trust principle 13; the standing what/why/how mandate)."""

    accepted: bool
    paradigm: str | None
    reason: str | None = None


def select_paradigm_lens(declared: str) -> ParadigmSelection:
    """Select the FP/OOP lens for a pile item's declared paradigm.

    D10: single-source read of the item's OWN declared field -- there is no
    second lens to compare against within this slice's scope, so "mismatch"
    and "unrecognized" collapse into ONE refusal condition: the declared
    token is not a member of ``RecognizedParadigm``.
    """
    try:
        RecognizedParadigm(declared)
    except ValueError:
        return ParadigmSelection(
            accepted=False, paradigm=None, reason=_refusal_message(declared)
        )
    return ParadigmSelection(accepted=True, paradigm=declared)


def _refusal_message(declared: str) -> str:
    """WHAT/WHY/HOW: names the offending declared value verbatim and at
    least one recognized member, so an operator can fix ``techdebt.md``
    without reading source code (AT-9's self-explaining requirement)."""
    recognized = ", ".join(member.value for member in RecognizedParadigm)
    return (
        f"unrecognized declared paradigm {declared!r} -- refusing dispatch "
        "before any worktree/agent invocation. Fix: set this pile item's "
        f"paradigm= field in techdebt.md to one of the recognized values: "
        f"{recognized}."
    )
