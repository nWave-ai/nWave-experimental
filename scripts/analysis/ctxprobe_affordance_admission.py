#!/usr/bin/env python3
"""WHICH affordance asset actually reaches the model, and from WHICH revision.

The orchestrator-affordance payload is concatenated in `sorted(glob("*.md"))`
order and offered whole; the harness admits only a preview and persists the rest
to a file. So the asset sorting FIRST owns the admitted window, and the others
may contribute nothing at all. That makes the filename prefix a COST decision and
a SAFETY decision at once: `50-standing-loops.md` opens with the truncated-preview
recovery pointer, and if a rename ever sorts it out of the window the recovery
mechanism disappears silently.

This probe answers both questions from the transcript -- the only place that
records what was actually delivered:

  * which assets' HEADS survive admission, counted per asset;
  * whether the bytes delivered match the assets ON DISK, which detects a
    runtime serving a STALE installed copy.

The second check is the one that matters operationally. The asset resolver
(`scripts/hooks/orchestrator_affordance_refresh.py:_candidate_assets_dirs`)
prefers `<claude_dir>/lib/...` over `~/.nwave/...`, so refreshing one install
shape does not necessarily change what fires -- and nothing else on the box
reports which revision is in flight.

Markers are DERIVED from the assets directory at run time, never hardcoded.
A hardcoded marker is a designation that goes stale at the next rename; the
file's own first line is the property. That is the whole point of this probe,
so it must not commit the defect it hunts.

Head-survival ALONE cannot decide staleness, and an earlier draft of this probe
claimed it could. An asset's opening line often survives a rename and several
edits unchanged, so the same marker matches two different revisions and the
report reads identical whether the runtime is current or 34 hours behind -- a
check that cannot fail, which is worse than no check. The revision leg therefore
compares the ADMITTED PREVIEW BYTES against the on-disk concatenation and reports
AGREES / DIVERGES on the bytes themselves.

Usage:
  ctxprobe_affordance_admission.py <transcript.jsonl> [assets-dir]

`assets-dir` defaults to the first existing resolver candidate, so a bare run
reports on the payload the RUNTIME would pick, not the repo's.
"""

import json
import sys
from collections import Counter
from pathlib import Path


_DEFAULT_ASSET_DIRS = (
    Path.home() / ".claude" / "lib" / "nWave" / "data" / "orchestrator-affordance",
    Path.home() / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
    Path("nWave/data/orchestrator-affordance"),
)
# Long enough to be unique, short enough to survive a preview cut.
_MARKER_CHARS = 60
_ASSET_SEPARATOR = "\n\n"  # mirrors orchestrator_affordance_refresh._ASSET_SEPARATOR
_PREVIEW_OPENER = "Preview (first "


def _as_text(content: object) -> str:
    """Flatten an attachment's content to the text the model saw.

    `content` is usually a LIST of strings. Serialising it with `json.dumps`
    escapes every newline, which silently defeats any prefix comparison against
    a file on disk -- the failure that made this probe's first revision check
    report `undecidable` on all 171 records instead of answering.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c for c in content if isinstance(c, str))
    return json.dumps(content, ensure_ascii=False)


def _on_disk_payload(assets_dir: Path) -> str:
    """Rebuild what the hook WOULD offer from this directory, in its own order."""
    contents: list[str] = []
    for path in sorted(assets_dir.glob("*.md")):
        try:
            contents.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return _ASSET_SEPARATOR.join(contents)


def _preview_body(text: str) -> str | None:
    """The asset bytes inside a persisted-output wrapper, or None if not wrapped."""
    start = text.find(_PREVIEW_OPENER)
    if start == -1:
        return None
    newline = text.find("\n", start)
    if newline == -1:
        return None
    body = text[newline + 1 :]
    for terminator in ("\n...\n", "\n</persisted-output>"):
        cut = body.find(terminator)
        if cut != -1:
            body = body[:cut]
    return body


def _resolve_assets_dir(argv: list[str]) -> Path | None:
    if len(argv) > 2:
        return Path(argv[2])
    return next((d for d in _DEFAULT_ASSET_DIRS if d.is_dir()), None)


def _derive_markers(assets_dir: Path) -> dict[str, str]:
    """First non-blank line of each asset, truncated -- the head-survival marker."""
    markers: dict[str, str] = {}
    for path in sorted(assets_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"!! INDETERMINATE {path.name}: {exc}", file=sys.stderr)
            continue
        line = next((ln for ln in text.splitlines() if ln.strip()), "")
        if line:
            markers[path.name] = line[:_MARKER_CHARS]
    return markers


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    transcript = Path(sys.argv[1])
    assets_dir = _resolve_assets_dir(sys.argv)
    if assets_dir is None or not assets_dir.is_dir():
        print("!! no affordance assets directory found -- cannot derive markers")
        return 1

    markers = _derive_markers(assets_dir)
    if not markers:
        print(f"!! {assets_dir} carries no readable *.md asset")
        return 1

    print(f"assets dir (what the runtime would serve): {assets_dir}")
    print("concatenation order, and each asset's size on disk:")
    for name in markers:
        size = (assets_dir / name).stat().st_size
        print(f"  {name:32s} {size:>8,} B")
    print()

    on_disk = _on_disk_payload(assets_dir)
    head_survivals: Counter[str] = Counter()
    revision: Counter[str] = Counter()
    injected_sizes: list[int] = []
    persisted = 0
    records = 0

    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "hook_additional_context" not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            att = rec.get("attachment") if isinstance(rec, dict) else None
            if not isinstance(att, dict):
                continue
            if att.get("type") != "hook_additional_context":
                continue
            text = _as_text(att.get("content"))
            hits = [name for name, marker in markers.items() if marker in text]
            if not hits:
                continue
            records += 1
            injected_sizes.append(len(text))
            if "Full output saved to:" in text:
                persisted += 1
            for name in hits:
                head_survivals[name] += 1
            body = _preview_body(text)
            if body is None:
                revision["unwrapped"] += 1
            elif on_disk.startswith(body):
                revision["agrees"] += 1
            else:
                revision["diverges"] += 1

    if not records:
        print("no injection carried ANY asset's head marker.")
        print("Either the transcript predates these assets, or the runtime is")
        print("serving a DIFFERENT revision whose first lines no longer match.")
        print("That second case is the staleness this probe exists to catch.")
        return 1

    print(f"injections carrying at least one asset head: {records:,}")
    print(f"  of which declared as persisted-to-file: {persisted:,}")
    print(
        f"  admitted size: min {min(injected_sizes):,} B  "
        f"max {max(injected_sizes):,} B\n"
    )
    print("=== whose HEAD survived admission (the file that owns the window) ===")
    for name in markers:
        count = head_survivals.get(name, 0)
        share = 100.0 * count / records
        flag = "" if count else "   <-- contributes NOTHING to admitted bytes"
        print(f"  {name:32s} {count:>6,} {share:>6.1f}%{flag}")

    print("\n=== is the runtime serving THIS revision? (bytes, not markers) ===")
    print(f"  preview AGREES with this directory: {revision['agrees']:>6,}")
    print(f"  preview DIVERGES from it:           {revision['diverges']:>6,}")
    print(f"  not persisted-wrapped, undecidable: {revision['unwrapped']:>6,}")
    if revision["diverges"] and not revision["agrees"]:
        print(
            "\n  STALE: every wrapped injection diverges from these assets.\n"
            "  The runtime is serving a DIFFERENT revision than this directory.\n"
            "  Check which install shape the resolver picked -- "
            "`<claude_dir>/lib/...` wins over `~/.nwave/...`."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
