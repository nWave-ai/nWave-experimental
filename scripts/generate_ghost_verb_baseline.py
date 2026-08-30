#!/usr/bin/env python3
"""Regenerate `nWave/data/ghost-verb-citation-baseline.json` -- the known-
debt baseline `scripts/hooks/check_no_new_ghost_verb_citations.py` ratchets
against (F-INSTALL-REMOVAL-TRANSPARENCY follow-up).

Run this deliberately, never automatically from a gate:

    uv run python scripts/generate_ghost_verb_baseline.py

The baseline can only shrink in an honest run (documentation cleanup
removing ghost citations) or grow ONLY alongside a reviewed, intentional
decision to accept new debt -- never as a side effect of an unrelated
commit. That is exactly why the ratchet gate does not call this script
itself: regenerating on every commit would let any new ghost citation
silently join "known debt" instead of blocking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))  # for `scripts.shared.*`, run standalone

from des.cli.registry_diff import registry_names_from_source  # noqa: E402
from scripts.shared.ghost_verb_census import census_ghost_citations  # noqa: E402


_MAIN_PATH = REPO_ROOT / "src" / "des" / "cli" / "__main__.py"
_BASELINE_PATH = REPO_ROOT / "nWave" / "data" / "ghost-verb-citation-baseline.json"

# Never scan a worktree's own copy of the tree (box rule: worktrees are
# per-lane, not repo content) or version control internals.
_EXCLUDED_DIR_NAMES = {".git", ".claude", "node_modules", ".venv"}


def _iter_markdown_files(root: Path) -> list[Path]:
    """Every `.md` file under *root*, excluding VCS/tooling internals.

    Exclusion checks the path RELATIVE to *root*, not the absolute path:
    a worktree lives at `<repo>/.claude/worktrees/<lane>/`, so an absolute-
    path check against `.claude` would exclude the entire worktree it is
    running from -- the bug this comment pins against regressing.
    """
    files = []
    for path in root.rglob("*.md"):
        relative_parts = path.relative_to(root).parts
        if any(part in _EXCLUDED_DIR_NAMES for part in relative_parts):
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    live = registry_names_from_source(_MAIN_PATH)
    if live is None:
        print(
            f"WHAT: could not parse {_MAIN_PATH} for the live `_REGISTRY` "
            "verb names.\n"
            "WHY: the baseline needs the live set to decide which "
            "citations are ghosts.\n"
            "HOW: fix the syntax error in that file, then re-run this "
            "script.",
            file=sys.stderr,
        )
        return 1

    markdown_files = _iter_markdown_files(REPO_ROOT)
    census = census_ghost_citations(markdown_files, live=live)

    relative_census = {
        str(Path(path).relative_to(REPO_ROOT)): sorted(verbs)
        for path, verbs in census.items()
    }

    total_occurrences = sum(
        len(verbs) for verbs in census.values()
    )  # per-file distinct-verb count, the ratchet's own unit -- see module
    # docstring in scripts/shared/ghost_verb_census.py for why this is not
    # the same number as a raw backtick-occurrence count.
    ghost_verb_names = sorted({v for verbs in census.values() for v in verbs})

    _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _BASELINE_PATH.write_text(
        json.dumps(
            {
                "$comment": (
                    "Known-debt baseline for scripts/hooks/"
                    "check_no_new_ghost_verb_citations.py. Regenerate with "
                    "scripts/generate_ghost_verb_baseline.py. Ratchet unit: "
                    "one entry per (file, distinct ghost verb cited in that "
                    "file) -- NOT a raw backtick-occurrence count."
                ),
                "distinct_ghost_verbs": len(ghost_verb_names),
                "distinct_file_verb_pairs": total_occurrences,
                "files": relative_census,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Baseline written: {len(relative_census)} files, "
        f"{len(ghost_verb_names)} distinct ghost verbs, "
        f"{total_occurrences} (file, verb) pairs -> {_BASELINE_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
