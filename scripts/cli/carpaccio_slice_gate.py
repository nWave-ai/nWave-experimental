"""Thin shim -- the carpaccio slice gate lives in ``des.cli``.

F-11 (atdd-pure-dogfooding-friction-2026-05-20.md): the carpaccio gate logic
moved into the importable ``des.cli.carpaccio_slice_gate`` module so it ships
with the ``des`` package and is invokable layout-independently via
``des carpaccio-slice-gate`` (post-slice-03 dispatcher form) -- the same shape
U2 uses. The U1 PreToolUse hook no longer resolves the gate by a repo-relative
``scripts/cli/`` path that breaks in the installed ``~/.claude/lib/`` layout.

This file survives as a thin shim so the many existing callers of the
``scripts/cli/carpaccio_slice_gate.py`` path -- the ``/nw-deliver`` skill
prose, the gate's own acceptance suite, ``at_review_verdict.py``, manual
invocations -- keep working. It transparently re-exports the ``des.cli``
module's full namespace (public surface AND the ``_``-prefixed helpers a few
sibling CLIs reuse) and delegates ``main``.
"""

from __future__ import annotations

from des.cli import carpaccio_slice_gate as _gate


# Transparently mirror the real module's namespace so every caller of the
# legacy `scripts.cli.carpaccio_slice_gate` path -- including ones that reach
# for `_`-prefixed helpers (`at_review_verdict.py` reuses `read_feature_files`,
# `_slice_scenarios`, `_at_content_hash`) -- resolves against the moved module.
globals().update(
    {name: getattr(_gate, name) for name in dir(_gate) if not name.startswith("__")}
)

main = _gate.main


if __name__ == "__main__":
    raise SystemExit(main())
