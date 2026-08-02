# Cross-wave handoff registry

A `# HANDOFF: <id> <what a later wave must do>` comment marks a spot where an
earlier wave (DESIGN/DISTILL) left a constraint for a LATER wave (DELIVER) to
satisfy — e.g. "wire `ledger_root` into the CLI entry point when this scaffold
goes real." A code comment alone is not an executable constraint: no gate
reads prose, so the instruction can be silently missed even when every AT is
green (D70 slice-02, 2026-08-02 — `evaluate_node` went real, `ledger_root`
never got threaded, and the gate that was supposed to become real stayed
dormant behind a `None` default; caught only by Vera driving the real CLI,
not by any of the 34 unit-level ATs, all of which called the pure function
directly and never exercised the wiring).

`tests/build/test_every_handoff_marker_is_registered.py` enforces the
mechanical half of the fix: every `# HANDOFF: <id> ...` comment anywhere
under `src/`, `scripts/`, `tests/` MUST have a matching row below, keyed by
the same `<id>`. It does not (cannot, in general) verify the handoff was
actually DONE — that stays a human/reviewer judgment — but it guarantees the
marker is never invisible: a marker with no registry row fails the build
loudly, at authoring time, instead of waiting for the next Vera examine to
notice nobody read the comment.

## Row grammar

`- [ ] <id>: file=<path> what="<what the later wave must do>" opened_by=<wave-or-lane> opened=<YYYY-MM-DD>`

Close a row (`- [x]`) only after the paired code change has actually landed
and the `# HANDOFF:` comment has been removed from the source — a closed row
with the marker still present in code is the same silent-wrong this registry
exists to prevent, just inverted.

## Open handoffs

(none yet — this registry ships empty; the D70 slice-02 incident that
motivated it was fixed directly, not left as a tracked handoff)
