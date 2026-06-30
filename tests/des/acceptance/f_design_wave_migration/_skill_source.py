"""Shared driving-port helper for f-design-wave-migration prose-contract ATs.

The soft-gate this feature ships is LLM-reads-markdown-prose behaviour: there is
NO runtime code path that emits the DESIGN-skip advisory. The honest, deterministic,
Python-only, git-free, cross-OS acceptance surface is therefore a *prose-contract*
read of the REAL shipped repo skill file (Mandate-13 prose-surface case): the
scaffold reads the actual file on disk — never an inline test string — and asserts
on DISCRIMINATING multi-word phrases (single tokens like "table"/"rigor" produce
empirical false positives against "acceptable"/"rigorous").

The driving port = the filesystem read of the canonical shipped skill file.

Slice scope: slice-01/02/03 drive ONLY nw-distill (rows 7b/7c + the named
Advisory-Skip-Gate pattern block). slice-04 ADDS nw-deliver to the removal
surface (R-1 `:315` DESIGN MANDATORY-read + R-2 `:321` READING-ENFORCEMENT
"You MUST read … brief.md") alongside the TWO nw-distill DESIGN-absent BLOCK
matrices (R-3 `:632`, R-4 `:309` + the `:311` EXCEPT carve-out). The
`read_deliver()` reader below is introduced JIT at slice-04's DISTILL
micro-wave (mirrors `read_distill()`, no dead helper before now).
"""

from __future__ import annotations

from pathlib import Path


# Repo root = four parents up from this file
# (tests/des/acceptance/f_design_wave_migration/_skill_source.py)
_REPO_ROOT = Path(__file__).resolve().parents[4]

NW_DISTILL = _REPO_ROOT / "nWave" / "skills" / "nw-distill" / "SKILL.md"
NW_DELIVER = _REPO_ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"


def read_distill() -> str:
    """Read the REAL shipped nw-distill skill CORPUS (driving port: filesystem).

    After the monolith->lean decomposition the prose may live in the monolith
    `nw-distill/SKILL.md` OR any `nw-distill-*` sub-skill. The prose-contract read
    is the UNION (concatenation of monolith + sub-skills) so a discriminating
    phrase is found wherever it was migrated -- decoupling the AT from the physical
    skill layout (additive: the monolith is still read, sub-skills only ADD).
    """
    skills_root = _REPO_ROOT / "nWave" / "skills"
    parts = [NW_DISTILL.read_text(encoding="utf-8")]
    parts += [
        sub.read_text(encoding="utf-8")
        for sub in sorted(skills_root.glob("nw-distill-*/SKILL.md"))
    ]
    return "\n".join(parts)


def read_deliver() -> str:
    """Read the REAL shipped nw-deliver skill (driving port: filesystem).

    slice-04 R-1/R-2 removal surface: the DESIGN MANDATORY-read (`:315`) and
    the READING-ENFORCEMENT "You MUST read … brief.md" hard-require (`:321`).
    """
    return NW_DELIVER.read_text(encoding="utf-8")
