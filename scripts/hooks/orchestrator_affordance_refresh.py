#!/usr/bin/env python3
"""Standalone, spine-independent orchestrator-affordance refresh hook.

# des-hook:orchestrator-affordance-refresh-standalone

Fixes the discoverability defect where the "how to use nWave" affordance
(every `*.md` asset under `nWave/data/orchestrator-affordance/` -- the
loader globs the directory, and basenames carry a numeric injection-order
prefix that is expected to churn) was injected ONLY by the DES runtime hooks
(`src/des/adapters/drivers/hooks/{session_start_handler,
user_prompt_submit_handler}.py`), which meant:

  (A) a 30-minute refresh cadence, not the mandated ~15 minutes;
  (B) zero affordance in a session where the `des` package cannot be
      imported (non-DES repo, broken install);
  (C) SessionStart registered with `matcher="startup"` only, so it never
      fired on Claude Code's `resume`/`clear`/`compact` sub-events.

This script is stdlib-only -- it NEVER imports the `des` package -- and
mirrors the existing `~/.claude/hooks/load_persona.py` pattern: resolve its
own assets relative to `Path(__file__)`, read them fresh on every call,
print the Claude Code `hookSpecificOutput` JSON envelope.

Usage: orchestrator_affordance_refresh.py <SessionStart|UserPromptSubmit>

SessionStart: unconditional injection (no matcher registration -- fires on
startup|resume|clear|compact).
UserPromptSubmit: self-gated on a 900-second (~15-minute) sentinel file
(`.nwave/orchestrator-affordance-last-injected`, relative to the process
cwd) -- the SAME sentinel path the DES-side
`user_prompt_submit_handler._maybe_refresh_orchestrator_affordance` uses,
so the two paths never double-inject.

Degrade-loud: a missing assets directory prints a one-line stderr
diagnostic and exits 0 (fail-open for the hook protocol) -- never a silent
no-op.

D71 EXTENSION (context_admission emitter): every firing (SessionStart
unconditional, UserPromptSubmit when the sentinel has elapsed) appends a
`context_admission` block to `.nwave/staging/d71/context-admission.jsonl`
(cwd-relative, same convention as the sentinel) immediately before the
firing commits (the sentinel touch for UserPromptSubmit; the envelope
print for SessionStart, which has no sentinel).

The block is FLAT, never nested: exactly ONE parent row
(`kind: "context_admission"`, scalar fields only) plus one CHILD row per
asset -- `kind: "context_admission_payload"` for each asset actually
offered, `kind: "context_admission_dropped_asset"` for each asset whose
read failed. Every child joins back to its parent on `correlation_id`. A
nested list inside a record would break both the hash domain and every
reader that assumes one row is one fact, so no record carries a list value.

TWO join keys, for TWO different joins -- not alternatives, and not
interchangeable:

  - `correlation_id` -- generated here, unique per FIRING. This is the
    PARENT<->CHILD key.
  - `stdout_sha256` -- the digest of the exact stdout bytes this firing
    wrote. This is the CROSS-BOUNDARY key, joining this record to the
    harness's own `hook_success` record; it works there because both sides
    independently hold the same stdout and can recompute the digest.

`stdout_sha256` must NOT be used as the parent<->child key. It designates
CONTENT, not the EVENT: SessionStart's stdout is a module constant, so every
SessionStart firing hashes identically (measured: two firings, ONE distinct
digest), and a reader joining children to parents on it silently gets a cross
product. Conversely `correlation_id` cannot serve the cross-boundary join --
the harness never sees a value this process invented.

The record NEVER carries a non-null `bytes_admitted` and NEVER invents a
`tool_use_id` -- the harness assigns `toolUseID` and decides admission
after this process has already exited, so neither is observable from inside
the hook. The honest, emitter-side join key is `stdout_sha256`: the sha256
hex digest of the exact bytes this process wrote to stdout for the firing.
`session_id` is read from the JSON envelope Claude Code pipes on stdin
(fail-open buffered read, the `hook_router.py` pattern) and is `null`
whenever that envelope is absent, malformed, or carries no session id --
never an invented value. `feature_id` is `null` with `scope: "session"`:
this hook fires on session lifecycle events and has no feature attribution
to offer, and a synthetic feature id would be a declared-but-meaningless
field.

A ledger write failure (unwritable staging directory) is caught, diagnosed
to stderr by name (path + `OSError` subclass), and the hook still exits
0 -- fail-open, same contract as the missing-assets diagnostic above. An
asset that fails to read contributes a dropped-asset row naming it and the
error rather than silently shrinking `total_bytes_offered`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path


# Same-directory sibling load (R-8): the reconciliation RULE between two
# install roots moved to a shared, stdlib-only module so the DES-side producer
# (`session_start_handler.load_orchestrator_affordance`) reaches the SAME
# decision instead of duplicating it. `DESPlugin.DES_HOOKS` ships both files
# flat to the same directory.
#
# Loaded by ABSOLUTE PATH off `__file__`, never as a bare `import` statement:
# the registered Claude Code hook command invokes this script through
# `runpy.run_path(...)`, which leaves `sys.path[0]` pointing at the CALLER's
# cwd rather than at this script's directory. A bare sibling import therefore
# resolves when the script is run directly (as the tests do) and silently
# fails in the shipped invocation -- losing reconciliation on exactly the
# real installs this fix exists for, with no error anywhere.
#
# Fail-open, matching this hook's degrade-never-raise contract: a copy of this
# script relocated without its sibling loses reconciliation rather than
# crashing the session.
def _load_resolution_module():
    import importlib.util

    path = Path(__file__).resolve().parent / "orchestrator_affordance_resolution.py"
    try:
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(
            "orchestrator_affordance_resolution", path
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


_resolution = _load_resolution_module()


_REFRESH_SECONDS = 900
_SENTINEL_RELATIVE = Path(".nwave") / "orchestrator-affordance-last-injected"
_LEDGER_RELATIVE = Path(".nwave") / "staging" / "d71" / "context-admission.jsonl"
_ASSET_SEPARATOR = "\n\n"

_SCHEMA_VERSION = "1"
_HOOK_NAME = "orchestrator-affordance-refresh"
_KIND_PARENT = "context_admission"
_KIND_PAYLOAD = "context_admission_payload"
_KIND_DROPPED = "context_admission_dropped_asset"
# This hook fires on session lifecycle events (SessionStart /
# UserPromptSubmit) and carries no feature attribution, so every record it
# writes is session-scoped with `feature_id: null`.  The discriminator is a
# statement about what the record describes, not a placeholder.
_SCOPE_SESSION = "session"

# SessionStart is paid on every new session, so it is deliberately a small
# orientation rather than the rich, multi-document UserPromptSubmit refresh.
# Keep the established operational markers: downstream affordance checks and
# existing maintainer muscle memory rely on them.  This is immutable data; the
# SessionStart path never creates a sentinel, project directory, or nWave state.
_COMPACT_SESSION_START_ORIENTATION = """# Orchestrator discipline
nWave is driven through the DES spine. Start with `des next`; follow its gate
and evidence instructions; use `des examine-fixture` for observable checks.

Keep work slices small, run the required acceptance checks, and use DES commands
for state changes. SessionStart is orientation only: it does not tick loops,
apply updates, run housekeeping, or modify project or ~/.nwave state.

For multi-slice or multi-feature work, load `nw-throughput` before scheduling.
"""


def _candidate_assets_dirs() -> list[Path]:
    """Every plausible location of the shipped `orchestrator-affordance/` assets.

    Three install shapes, tried in order from MOST to LEAST specific to
    this exact script instance (a candidate that ships alongside/beside the
    running script wins over a whole-machine, any-install fallback):
      1. Installed Claude-scoped layout -- this script ships flat to
         `<claude_dir>/scripts/orchestrator_affordance_refresh.py`, and the
         nWave runtime assets ship to `<claude_dir>/lib/nWave/data/...`
         (`DESPlugin._ship_nwave_runtime_assets`). Two `.parent` hops off
         the script's own file reach `<claude_dir>`.
      2. Dev-checkout layout -- this script lives at
         `<repo_root>/scripts/hooks/orchestrator_affordance_refresh.py`,
         and the assets live at `<repo_root>/nWave/data/...`. Three
         `.parent` hops off the script's own file reach `<repo_root>`.
      3. Installed host-neutral layout (Codex, Copilot, OpenCode) --
         `DESPlugin._runtime_python_dir` ships the SAME runtime assets to
         `~/.nwave/nWave/data/...` instead, whenever "codex" is in
         the install's target platforms (fix-codex-only-orchestrator-
         affordance-runtime-aware-resolver). A host-neutral install never
         populates candidate 1, so this script found nothing there and
         diagnosed a false "missing assets" -- even though the data had
         already landed on disk, just under a different root. Computed
         inline (not imported from scripts/shared/install_paths) to keep
         this script's zero-coupling, stdlib-only contract intact. Tried
         LAST (not 2nd) because it is a whole-machine, any-repo fallback --
         a machine that carries BOTH a real install and a dev checkout of
         this same repo must not have the dev checkout's own, more
         relevant assets shadowed by an unrelated global install.

    Never cwd-dependent -- always resolved relative to `Path(__file__)` (and,
    for candidate 3, `Path.home()`, which is what the shipping side also
    resolves against).
    """
    script_path = Path(__file__).resolve()
    installed_candidate = (
        script_path.parent.parent / "lib" / "nWave" / "data" / "orchestrator-affordance"
    )
    dev_checkout_candidate = (
        script_path.parent.parent.parent / "nWave" / "data" / "orchestrator-affordance"
    )
    host_neutral_candidate = (
        Path.home() / ".nwave" / "nWave" / "data" / "orchestrator-affordance"
    )
    return [installed_candidate, dev_checkout_candidate, host_neutral_candidate]


def _resolve_assets_dir() -> Path | None:
    """First existing candidate assets directory, or `None` if none exist."""
    for candidate in _candidate_assets_dirs():
        if candidate.is_dir():
            return candidate
    return None


# R-8: the notice templates and the reconciliation DECISION
# (`directory_content_digest` / `directory_freshness` /
# `reconcile_install_roots`) moved to the shared sibling module
# `orchestrator_affordance_resolution.py` so the DES-side producer reaches
# the identical rule. This hook keeps its own candidate ENUMERATION
# (`_candidate_assets_dirs` above) and the SELECTION wiring below --
# behavior-preserving, byte-identical output.


def _resolve_assets_selection() -> tuple[Path | None, str | None]:
    """Chosen assets dir + an optional in-band divergence notice (P1 fix).

    Preserves the existing candidate-order shadowing protection EXACTLY: a
    dev-checkout root (candidate 2) wins unconditionally over either install
    output and is NEVER reconciled -- a dev checkout is deliberately at
    whatever revision the operator checked out, and reconciling it against a
    global install would reintroduce the exact shadowing bug the candidate
    order exists to prevent. Reconciliation applies ONLY between the two
    INSTALL roots (candidate 1, Claude-scoped, and candidate 3, host-neutral),
    which are obliged to agree, and only when the dev-checkout candidate is
    absent.

    The reconciliation itself is delegated to the shared sibling module
    (R-8). When that sibling could not be imported, the two install roots are
    left unreconciled -- the pick stays on candidate order, no notice -- which
    is a degradation, never a crash.
    """
    installed, dev_checkout, host_neutral = _candidate_assets_dirs()

    if installed.is_dir():
        if dev_checkout.is_dir():
            # Mutually exclusive by construction (see _candidate_assets_dirs
            # docstring) -- preserve the original first-match order intact.
            return installed, None
        if host_neutral.is_dir() and _resolution is not None:
            return _resolution.reconcile_install_roots(installed, host_neutral)
        return installed, None
    if dev_checkout.is_dir():
        return dev_checkout, None
    if host_neutral.is_dir():
        return host_neutral, None
    return None, None


def _collect_affordance_payloads(
    assets_dir: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    """Read every `*.md` file directly under `assets_dir`, sorted by name.

    Content is read fresh on every call -- never cached -- mirroring
    `session_start_handler.load_orchestrator_affordance`. Returns
    `(payloads, dropped_assets, contents)`:
      - `payloads`: one `{path, source_path, bytes_offered, role}` entry per
        readable file. `path` is the asset's identity (its bare name, stable
        across install shapes); `source_path` is the locator an operator can
        actually `wc -c` to check `bytes_offered` against the file on disk.
        Both are load-bearing: the identity does not resolve to a file, and
        the locator differs between a dev checkout and an install.
      - `dropped_assets`: one `{path, source_path, reason}` entry per `*.md`
        file that raised `OSError` on read, the reason NAMING the error
        (degrade-loud, never a silent under-report).
      - `contents`: the readable text, in the same sorted order, for the
        existing envelope-building path.
    """
    md_paths = sorted(assets_dir.glob("*.md"))
    payloads: list[dict[str, object]] = []
    dropped_assets: list[dict[str, object]] = []
    contents: list[str] = []
    for path in md_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            dropped_assets.append(
                {
                    "path": path.name,
                    "source_path": str(path),
                    "reason": f"{exc.__class__.__name__}: {exc}",
                }
            )
            continue
        contents.append(text)
        payloads.append(
            {
                "path": path.name,
                "source_path": str(path),
                "bytes_offered": len(text.encode("utf-8")),
                "role": "orchestrator-affordance",
            }
        )
    return payloads, dropped_assets, contents


def _load_affordance(
    assets_dir: Path,
) -> tuple[str | None, list[dict[str, object]], list[dict[str, object]]]:
    """Concatenate every readable `*.md` file's content under `assets_dir`.

    Returns `(text_or_None, payloads, dropped_assets)` -- `text_or_None` is
    `None` when the directory carries no readable `.md` file; `payloads`/
    `dropped_assets` feed the D71 `context_admission` rows (see
    `_collect_affordance_payloads`).
    """
    payloads, dropped_assets, contents = _collect_affordance_payloads(assets_dir)
    if not contents:
        return None, payloads, dropped_assets
    return _ASSET_SEPARATOR.join(contents), payloads, dropped_assets


def _session_start_payloads() -> list[dict[str, object]]:
    """The single in-code payload SessionStart always offers (no asset file).

    `source_path` is `null` because there is no file to point at: this
    payload is a module constant. Naming the identity `<inline:...>` says so
    in the record rather than leaving a reader to `wc -c` a path that does
    not exist.
    """
    text = _COMPACT_SESSION_START_ORIENTATION
    return [
        {
            "path": "<inline:session-start-orientation>",
            "source_path": None,
            "bytes_offered": len(text.encode("utf-8")),
            "role": "session-start-orientation",
        }
    ]


def _build_envelope(event: str, additional_context: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": additional_context,
        }
    }


def _sentinel_path() -> Path:
    """The refresh sentinel, relative to the process's own cwd.

    Claude Code invokes hooks with `cwd` set to the project root, so this
    resolves to the SAME path the DES-side handler computes from the hook
    payload's `cwd` field -- the shared sentinel that prevents double
    injection between the two paths.
    """
    return Path.cwd() / _SENTINEL_RELATIVE


def _ledger_path() -> Path:
    """The D71 `context_admission` ledger, relative to the process's own cwd.

    Same convention as `_sentinel_path()` -- runtime staging state is
    cwd-relative (Claude Code invokes hooks with `cwd` set to the project
    root), never resolved off `Path(__file__)` (that resolution is reserved
    for the shipped, read-only asset directory).
    """
    return Path.cwd() / _LEDGER_RELATIVE


def _is_sentinel_elapsed(sentinel: Path) -> bool:
    """True when the sentinel is missing, corrupt, or `>= _REFRESH_SECONDS` old.

    Degrade-safe: a missing sentinel, a directory occupying the sentinel
    path, or any other stat failure all count as elapsed so the caller
    re-injects rather than staying silently dormant forever.
    """
    try:
        if sentinel.is_dir():
            return True
        mtime = sentinel.stat().st_mtime
    except OSError:
        return True
    return (time.time() - mtime) >= _REFRESH_SECONDS


def _touch_sentinel(sentinel: Path) -> None:
    """Create/refresh the sentinel file's mtime to now."""
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch(exist_ok=True)
    now = time.time()
    os.utime(sentinel, (now, now))


def _sha256_of(text: str) -> str:
    """sha256 hex digest of the exact UTF-8 bytes `text` represents."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_hook_envelope() -> dict[str, object]:
    """The JSON hook payload Claude Code pipes on stdin, or `{}`. Fail-open.

    Same defensive shape as `hook_router.py`'s buffered read: an unreadable,
    empty, or malformed stdin yields `{}` rather than raising -- reading the
    envelope must never be able to block or fail a session lifecycle hook.
    """
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return envelope if isinstance(envelope, dict) else {}


def _session_id_of(envelope: dict[str, object]) -> str | None:
    """The envelope's `session_id`, or `None` -- never an invented value.

    An absent, non-string, or empty `session_id` is `None`: "I was not told
    which session this was" and "it was session X" must not look alike.
    """
    value = envelope.get("session_id")
    return value if isinstance(value, str) and value else None


def _build_admission_records(
    event: str,
    payloads: list[dict[str, object]],
    dropped_assets: list[dict[str, object]],
    stdout_sha256: str,
    session_id: str | None,
) -> list[dict[str, object]]:
    """One firing -> one PARENT row + N flat CHILD rows, in write order.

    PRIMARY and complete at write time: every field is knowable by THIS
    process at the moment it writes. The parent never carries a non-null
    `bytes_admitted` and never invents a `tool_use_id` -- the harness
    assigns `toolUseID` and decides admission AFTER this process has already
    exited, so neither is observable from inside the hook (a causality
    boundary, not an engineering gap).

    TWO join keys, each for a DIFFERENT join -- they are not alternatives:
      - `correlation_id` joins PARENT<->CHILD within this one firing. It is
        generated here, unique by construction.
      - `stdout_sha256` joins THIS RECORD <-> the harness's `hook_success`
        record across the process boundary. It works there, and only there,
        because both sides independently hold the same stdout and can
        recompute the digest.

    `stdout_sha256` CANNOT serve as the parent<->child key: it is a
    designation of CONTENT, not an identity of the EVENT. SessionStart's
    stdout is a module constant, so every SessionStart firing hashes
    identically (measured: two firings, ONE distinct digest), and a reader
    joining children to parents on it gets a silent cross product.

    Flat by construction: the per-asset facts are SEPARATE ROWS, never a
    nested `payloads` list on the parent. One row is one fact.
    """
    ts = time.time()
    correlation_id = uuid.uuid4().hex
    common: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "ts": ts,
        "session_id": session_id,
        "correlation_id": correlation_id,
        "event": event,
        "hook": _HOOK_NAME,
        "stdout_sha256": stdout_sha256,
        "feature_id": None,
        "scope": _SCOPE_SESSION,
    }

    parent: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": _KIND_PARENT,
        "ts": ts,
        "session_id": session_id,
        "correlation_id": correlation_id,
        "agent_name": None,
        "agent_id": None,
        "event": event,
        "hook": _HOOK_NAME,
        "tool_use_id": None,
        "payload_count": len(payloads),
        "dropped_asset_count": len(dropped_assets),
        "total_bytes_offered": sum(int(p["bytes_offered"]) for p in payloads),
        "bytes_admitted": None,
        "stdout_sha256": stdout_sha256,
        "feature_id": None,
        "scope": _SCOPE_SESSION,
    }

    records: list[dict[str, object]] = [parent]
    for payload in payloads:
        records.append(
            {
                **common,
                "kind": _KIND_PAYLOAD,
                "path": payload["path"],
                "source_path": payload["source_path"],
                "bytes_offered": payload["bytes_offered"],
                "role": payload["role"],
            }
        )
    for dropped in dropped_assets:
        records.append(
            {
                **common,
                "kind": _KIND_DROPPED,
                "path": dropped["path"],
                "source_path": dropped["source_path"],
                "reason": dropped["reason"],
            }
        )
    return records


def _append_admission_records(records: list[dict[str, object]]) -> None:
    """Append one firing's rows as one contiguous JSONL block. Fail-open.

    A single `open(..., "a")` for the whole block so a concurrent reader
    never observes a parent without its children. An unwritable staging
    directory (permission/disk-full/not-a-directory) is caught, diagnosed to
    stderr by name (the path + the `OSError` subclass), and swallowed -- the
    block is dropped for this firing, but the hook must never block on a
    broken ledger.
    """
    ledger = _ledger_path()
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
    except OSError as exc:
        sys.stderr.write(
            "[orchestrator-affordance-refresh] context_admission ledger "
            f"append failed for {ledger} -- {exc.__class__.__name__}: {exc}\n"
        )


def _diagnose_missing_assets(assets_dir_candidates: list[Path]) -> None:
    """Non-silent stderr diagnostic naming the problem (degrade-loud)."""
    tried = ", ".join(str(candidate) for candidate in assets_dir_candidates)
    sys.stderr.write(
        "[orchestrator-affordance-refresh] assets directory not found -- "
        f"tried: {tried}\n"
    )


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "SessionStart"

    # Buffered at the top, before any branch decides whether it needs it, so
    # the read happens exactly once per process regardless of path taken.
    session_id = _session_id_of(_read_hook_envelope())

    candidates = _candidate_assets_dirs()
    assets_dir, divergence_notice = _resolve_assets_selection()

    if event == "UserPromptSubmit":
        if assets_dir is None:
            _diagnose_missing_assets(candidates)
            return 0
        sentinel = _sentinel_path()
        if not _is_sentinel_elapsed(sentinel):
            return 0
        affordance, payloads, dropped_assets = _load_affordance(assets_dir)
        stdout_text = ""
        if affordance:
            # Divergence call-out is ADDED on top of the substantive
            # guidance, never a replacement for it -- prepended so it is the
            # first thing read, never buried past the preview window.
            if divergence_notice:
                affordance = divergence_notice + affordance
            stdout_text = json.dumps(_build_envelope(event, affordance)) + "\n"
            sys.stdout.write(stdout_text)
        _append_admission_records(
            _build_admission_records(
                event,
                payloads,
                dropped_assets,
                _sha256_of(stdout_text),
                session_id,
            )
        )
        _touch_sentinel(sentinel)
        return 0

    # SessionStart (and any other event Claude Code may route here):
    # unconditional compact orientation.  This payload is immutable code data,
    # so a missing rich-refresh asset directory must not turn a valid session
    # start into an empty stdout response.  Keep the diagnostic as shipping
    # evidence; UserPromptSubmit still requires the full asset set.
    if assets_dir is None:
        _diagnose_missing_assets(candidates)
    stdout_text = (
        json.dumps(_build_envelope(event, _COMPACT_SESSION_START_ORIENTATION)) + "\n"
    )
    _append_admission_records(
        _build_admission_records(
            event,
            _session_start_payloads(),
            [],
            _sha256_of(stdout_text),
            session_id,
        )
    )
    sys.stdout.write(stdout_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
