"""Shared single-line JSON stdout EMIT primitive for the DES CLI surface.

One shape -- "print exactly one single-line JSON object to stdout" -- was
independently defined as ``def _emit(payload): print(json.dumps(payload))``
in 14 separate ``des.cli`` modules (D03, mikado 2026-07-28). All 14 bodies
were byte-identical; none carried ``sort_keys`` or a second stream. This
module is the ONE place that shape now lives.

The precedent for collapsing a duplicated CLI helper into one shared module
and re-importing at each call site is already in the tree:
``des.cli._reverify_core`` extracts its ``_emit`` (+6 other helpers)
verbatim, and ``attest_bundled_slice.py`` / ``reverify_slice_commit.py``
import rather than duplicate it ("the no-parallel-copy witness"). This
module follows the same pattern, generalized to the other 13 sites plus
``_reverify_core`` itself.

WHAT THIS DOES **NOT** COLLAPSE. Three other ``_emit`` shapes exist on the
same CLI surface and are DELIBERATELY left alone:

* dual-stream / ``sort_keys=True`` variants (``_wave_review_cli``,
  ``record_examine_verdict``, ``record_review_verdict``,
  ``verify_slice_commit_completeness``) -- these are not one shape either
  (``sort_keys`` presence differs, stdout-only vs stdout+stderr differs);
  forcing them into this helper would silently change JSON key order for
  any consumer doing exact-string/golden-file comparison.
* dataclass-outcome emitters (``walking_skeleton_gate.GateOutcome``,
  ``wave_clear.ClearFloorOutcome``) -- different input type, not a payload
  dict.
* bespoke positional-argument emitters (``loop``,
  ``feature_end_preconditions_scaffold``, ``walking_skeleton_done_gate``,
  ``earned_verdict_self_test``, ``carpaccio_precheck``, ``carpaccio_slice_gate``,
  ``run_contract_gate``) -- genuinely different call shapes, several already
  more evolved than a plain print (``run_contract_gate`` accepts an
  injectable ``OutputPort``).

Three-to-nine honest variants beat one shape that lies about a fourth.
"""

from __future__ import annotations

import json


def emit_json_line(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object to stdout."""
    print(json.dumps(payload))
