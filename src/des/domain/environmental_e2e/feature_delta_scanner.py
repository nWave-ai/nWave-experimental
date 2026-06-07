"""Feature-delta `## Environmental E2E` block scanner -- pure, stdlib-only.

The mis-scoped-feature detector reads a feature-delta and reports whether it
carries the `## Environmental E2E` declaration block. L1.4 (gate-family-
implementation-2026-05-21.md, exit-code grid line 279):

    exit 3  MISSCOPED -- no `## Environmental E2E` block (work mis-scoped as
                         a feature)

`--mode verify-authored` consults this scanner to map "no block" -> the
`misscoped` verdict / exit 3 outcome; `--mode run` also consults it to refuse
running a feature that is mis-scoped as such.

Pure function over text -- no I/O. Used by `des.cli.verify_environmental_e2e`.
"""

from __future__ import annotations

import re


_E2E_BLOCK_HEADER_RE = re.compile(r"^##\s+Environmental\s+E2E\s*$", re.MULTILINE)


def has_environmental_e2e_block(feature_delta_text: str) -> bool:
    """Whether the feature-delta text carries a `## Environmental E2E` block.

    Returns ``True`` when the H2 heading `## Environmental E2E` appears on its
    own line anywhere in the text, ``False`` otherwise. The scanner is purely
    structural -- it does NOT validate the block's content (a present-but-
    malformed block surfaces as a parse error downstream, exit 2, not as
    mis-scoped).
    """
    return _E2E_BLOCK_HEADER_RE.search(feature_delta_text) is not None


__all__ = ["has_environmental_e2e_block"]
