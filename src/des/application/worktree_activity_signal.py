"""The Sentinel's two remaining evidence axes: recent write activity and
declared ownership.

lane/sentinel-tool. Companion to `des.domain.worktree_sentinel_verdict.
classify_sentinel`, which consumes both of these as already-collected
values -- this module is where the I/O and the name-matching that PRODUCE
them live.

ACTIVITY AXIS (`read_activity_age_seconds`). Seconds since a worktree's own
`.git` HEAD or index was last written, the second liveness signal the
Sentinel needs because `/proc`-based process-cwd liveness is structurally
blind for most of an LLM agent's life (it is waiting on the model between
tool calls, not running a process). Read-only `stat()` calls; degrades to
`Indeterminate` -- never a guessed number -- when the gitdir cannot be
resolved or its files cannot be stat'd.

DECLARED-OWNERSHIP AXIS (`resolve_declared_ownership`). Two sources, tried
in order:

  1. A MARKER FILE inside the worktree, `.nwave/lane-owner.json`, written
     and removed by whatever tool manages the lane's lifecycle. Chosen over
     a hand-maintained external list (the prototype's `--owned` CLI flag)
     BECAUSE a hand-maintained list goes stale the moment an operator
     forgets to update it on every single Sentinel invocation -- the exact
     defect class named in this lane's dispatch. A marker travels WITH the
     worktree: it cannot point at a worktree that no longer exists, and it
     needs no separate registry to fall out of sync with reality. Nothing
     in this repo writes this marker yet (`des dispatch` does not -- see
     the module docstring in `des.cli.dispatch` for the in-PROMPT marker
     block, which is transient and never touches disk); wiring a writer is
     the natural next slice, out of THIS lane's scope, and is why the
     marker's ABSENCE degrades to "not declared", not to an error.
  2. The `--owned` CLI flag, kept as a zero-wiring-cost manual fallback for
     lanes the marker is not yet wired into. This is where defect #3 lived:
     the prototype's row-name normalization prefixed the WRONG side
     (`"wt-" + "wt-charterarm"` inside `.removeprefix`, matching nothing),
     so the whole axis silently reported zero owners. `normalize_lane_name`
     is the fix -- ONE function, both sides of every comparison go through
     it, so there is no second place the same bug can hide.

Two worktree PARENT DIRECTORIES are in live use on this box (`~/Projects/`
and `~/Projects/wt/`), so a bare basename is not always unique --
`qualified_name` disambiguates for DISPLAY and for an EXACT-match declared
token (`"wt/charterarm"`); `normalize_lane_name` still allows a bare token
to match by name alone when no collision exists, so the common case stays
a one-word `--owned` flag.
"""

from __future__ import annotations

import time
from pathlib import Path

from des.ports.driven_ports.committed_scope_port import Indeterminate


__all__ = [
    "normalize_lane_name",
    "qualified_name",
    "read_activity_age_seconds",
    "resolve_declared_ownership",
]


#: Prefixes stripped, IN ORDER, to reach the canonical lane name. Order
#: matters: "nWave-dev-wt-charterarm" must lose "nWave-dev-" BEFORE
#: "wt-" is considered, or the leftover "wt-" survives unstripped.
_NAME_PREFIXES: tuple[str, ...] = ("nwave-dev-", "wt-")


def normalize_lane_name(raw: str) -> str:
    """Reduce a worktree basename or a declared `--owned` token to one
    canonical lane name, case-insensitively.

    Strips `nWave-dev-` then `wt-` (in that order -- see module docstring)
    from EITHER side of a comparison, so `"charterarm"`, `"wt-charterarm"`,
    and `"nWave-dev-wt-charterarm"` all normalize to `"charterarm"`. This
    is the fix for defect #3: the prototype stripped only ONE fixed prefix
    from only ONE side, so a declared token spelled differently from the
    worktree's own basename (a bare name vs. a `wt-`-prefixed one, or vice
    versa) silently failed to match.
    """
    name = raw.strip().lower()
    changed = True
    while changed:
        changed = False
        for prefix in _NAME_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix) :]
                changed = True
    return name


def qualified_name(path: Path) -> str:
    """`"<parent-dir-basename>/<worktree-basename>"` -- the display AND
    exact-match identity that survives two same-named worktrees living
    under DIFFERENT parent directories (`~/Projects/nWave-dev-wt-X` vs.
    `~/Projects/wt/X`). The prototype's display name collapsed both to the
    bare basename; two same-named worktrees were indistinguishable in its
    receipt."""
    return f"{path.parent.name}/{path.name}"


def resolve_declared_ownership(
    *,
    path: Path,
    owned_tokens: frozenset[str],
    marker_present: bool,
) -> tuple[bool, str]:
    """Decide whether `path` is a declared-owned worktree, and name how.

    Tries the marker first (the non-stale source), then the qualified name
    (`"wt/charterarm"`, exact, for disambiguating a name collision), then
    the normalized bare name (`"charterarm"` matches `"wt-charterarm"` and
    `"nWave-dev-wt-charterarm"` alike -- the defect #3 fix). Returns
    `(False, "")` when none apply -- absence is never an error here, only
    the CALLER (the Sentinel verdict) decides what absence means.
    """
    if marker_present:
        return (
            True,
            f"lane-owner marker present at {path / '.nwave' / 'lane-owner.json'}",
        )

    qualified = qualified_name(path)
    if qualified in owned_tokens:
        return True, f"--owned {qualified!r} (qualified match)"

    normalized_path_name = normalize_lane_name(path.name)
    for token in owned_tokens:
        if normalize_lane_name(token) == normalized_path_name:
            return (
                True,
                f"--owned {token!r} (normalized match: {normalized_path_name!r})",
            )

    return False, ""


def _mtime_age_seconds(p: Path, *, now: float) -> int | None:
    try:
        return int(now - p.stat().st_mtime)
    except OSError:
        return None


def read_activity_age_seconds(
    path: Path, *, now: float | None = None
) -> int | Indeterminate:
    """Seconds since `path`'s own `.git` HEAD or index was last written --
    the younger (more recent) of the two, since either one changing is
    evidence of a write.

    `path` may be a linked worktree (`.git` is a FILE naming `gitdir: ...`)
    or the main checkout (`.git` is the directory itself); both are
    resolved to the real per-worktree gitdir before stat'ing. Returns
    `Indeterminate` -- never a fabricated age -- when `.git` is absent,
    malformed, or neither file is stat'able; a caller must not read
    `Indeterminate` as "very old" or "very new".
    """
    now = time.time() if now is None else now
    gitfile = path / ".git"
    try:
        if gitfile.is_file():
            content = gitfile.read_text(encoding="utf-8")
            marker = "gitdir:"
            if marker not in content:
                return Indeterminate(f"{gitfile} does not declare a gitdir: line")
            gitdir = Path(content.split(marker, 1)[1].strip())
        elif gitfile.is_dir():
            gitdir = gitfile
        else:
            return Indeterminate(f"{gitfile} is neither a file nor a directory")
    except OSError as exc:
        return Indeterminate(f"could not read {gitfile}: {exc}")

    ages = [
        age
        for age in (
            _mtime_age_seconds(gitdir / "HEAD", now=now),
            _mtime_age_seconds(gitdir / "index", now=now),
        )
        if age is not None
    ]
    if not ages:
        return Indeterminate(
            f"neither {gitdir / 'HEAD'} nor {gitdir / 'index'} could be stat'd"
        )
    return min(ages)
