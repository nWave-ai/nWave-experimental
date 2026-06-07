"""DESIGN_CONTEXT content-presence predicate.

Feature ``crafter-design-adherence-enforcement`` slice-01 (DDD-1, INPUT-b).
Closes backlog #63 (INPUT side).

Pure domain predicate, zero I/O. ``design_context_carries_architecture(body)``
answers: does this ``# DESIGN_CONTEXT`` section *body* carry a real architecture
citation, or is it empty / a template placeholder / citation-free prose?

A citation is the mechanical proof the architecture was carried to the crafter.
The ``AtddPurePromptValidator`` (the driving-port surface) consults this predicate
to turn the cosmetic header-only ``# DESIGN_CONTEXT`` check into a hard
content-presence gate.

Contract shape: **pure-function** (``body -> bool``). No write method exists on
this module — "the check silently mutates" is structurally non-representable.
git-free, cross-OS, OSS-tier.
"""

from __future__ import annotations

import re


# The literal "no design artifacts" sentinel shipped in the dispatch template
# (nw-execute/SKILL.md). A dispatch that opts out of citing architecture carries
# this verbatim — it is NOT proof the architecture was carried, so it is refused.
_NO_ARTIFACTS_SENTINEL = "No design artifacts available — use project conventions."

# The literal unfilled template placeholder shipped in nw-execute/SKILL.md
# (the ``{Summary of architectural decisions…`` block). A dispatch that forgot
# to fill DESIGN_CONTEXT carries this verbatim. It cites a *templated*
# feature-delta path (``docs/feature/{feature-id}/feature-delta.md``) that would
# otherwise false-match the design-reference token regex — so it must be refused
# explicitly: an unfilled placeholder is NOT proof the architecture was carried.
_TEMPLATE_PLACEHOLDER_PREFIX = "{Summary of architectural decisions"

# Design-reference tokens. The presence of any ONE is the mechanical proof that
# a real architecture artifact was carried into the DESIGN_CONTEXT body:
#   * DDD-N            — a DDD decision id
#   * ADR[-A-Z]*-N     — an ADR id (ADR-027, ADR-CP-001, ...)
#   * SYS-N            — a SYS contract id
#   * ## Wave: DESIGN  — a DESIGN-wave reference
#   * docs/feature/.../feature-delta.md — a feature-delta DESIGN path
#   * brief.md         — the component-inventory brief
_DESIGN_REFERENCE_TOKEN = re.compile(
    r"DDD-\d+"
    r"|ADR[-A-Z]*-?\d+"
    r"|SYS-\d+"
    r"|## Wave: DESIGN"
    r"|docs/feature/[^ ]+/feature-delta\.md"
    r"|brief\.md"
)


def design_context_carries_architecture(body: str) -> bool:
    """Return True iff the DESIGN_CONTEXT body carries a real architecture citation.

    The body is the text of the ``# DESIGN_CONTEXT`` section AFTER the heading
    line is stripped. The predicate is True only when the body is non-empty,
    is not the "no design artifacts" sentinel, is not the unfilled template
    placeholder, and contains at least one design-reference token (DDD-N /
    ADR[-A-Z]*-N / SYS-N / a feature-delta.md path / brief.md / a
    ``## Wave: DESIGN`` reference).

    Args:
        body: The DESIGN_CONTEXT section body (heading line already stripped).

    Returns:
        True when the body carries a real architecture citation; False when it
        is empty/whitespace, the no-artifacts sentinel, the unfilled template
        placeholder, or citation-free prose. The placeholder is refused
        explicitly because it embeds a *templated* feature-delta path that would
        otherwise false-match the design-reference token regex.
    """
    if not body.strip():
        return False
    if _NO_ARTIFACTS_SENTINEL in body:
        return False
    if _TEMPLATE_PLACEHOLDER_PREFIX in body:
        return False
    return _DESIGN_REFERENCE_TOKEN.search(body) is not None
