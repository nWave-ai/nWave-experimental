"""Composition root: read authoring-surface files (or a fabricated
fixture) and extract the section-scoped vocabulary text a PO would see.

No production driving port exists for "is this documented" -- these are
prose files, not executable code (same posture as AT-d in
``tests/des/unit/cli/test_carpaccio_ceiling_15_and_coupled_affordance.py``
for the sibling ``@coupled`` affordance). This composition root reads the
real repo files directly, section-scoped: a bare ``"depends-on" in text``
check is testing-theater -- satisfied by pasting the token anywhere in
either file, including an unrelated appendix. Discoverability means the
token sits ALONGSIDE its siblings (``@walking_skeleton`` / ``@infrastructure``
/ ``@coupled``) in the annotation-vocabulary section itself; ``extract_section``
is fence-aware so an embedded example Slice Plan table inside a fenced code
block cannot be mistaken for the section's own closing heading.

Both source and installed copies are checked -- an agent reads the
INSTALLED copy (``~/.claude/skills`` / ``~/.claude/agents``) at runtime, not
the repo source tree. Installed-copy reads report ``surface_present=False``
when absent (fresh clone / CI, not a defect) instead of raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .domain_types import AuthoringSurface, FabricatedFixture


_DEPENDENCY_TOKEN_RE = re.compile(r"depends-on\s*\{slice-id\}", re.IGNORECASE)
_SILENCE_RE = re.compile(
    r"\b(silence|empty(?:\s+annotation)?|no\s+(?:declared|explicit)?\s*"
    r"(?:annotation|dependency))\b",
    re.IGNORECASE,
)
_PARALLEL_SAFE_RE = re.compile(
    r"parallel[- ]safe|parallel\s+by\s+default", re.IGNORECASE
)

_DISCUSS_HEADING = "Slice Plan annotation vocabulary (reference)"
_PO_HEADING = "Slice Plan Template (atdd_pure)"


@dataclass(frozen=True)
class SurfaceSpec:
    path: Path
    heading: str
    existing_tokens: tuple[str, ...]


@dataclass(frozen=True)
class SectionRead:
    section_text: str
    existing_tokens: tuple[str, ...]
    surface_present: bool


def _repo_root() -> Path:
    # steps/composition.py -> steps -> atdd_pure_slice_dependency_annotation_discoverable
    # -> cli -> scripts -> tests -> repo root
    return Path(__file__).resolve().parents[5]


def _surface_table() -> dict[AuthoringSurface, SurfaceSpec]:
    repo = _repo_root()
    home = Path.home()
    return {
        AuthoringSurface.DISCUSS_SKILL_SOURCE: SurfaceSpec(
            repo / "nWave" / "skills" / "nw-discuss" / "SKILL.md",
            _DISCUSS_HEADING,
            ("@walking_skeleton", "@infrastructure", "@coupled"),
        ),
        AuthoringSurface.DISCUSS_SKILL_INSTALLED: SurfaceSpec(
            home / ".claude" / "skills" / "nw-discuss" / "SKILL.md",
            _DISCUSS_HEADING,
            ("@walking_skeleton", "@infrastructure", "@coupled"),
        ),
        AuthoringSurface.PRODUCT_OWNER_AGENT_SOURCE: SurfaceSpec(
            repo / "nWave" / "agents" / "nw-product-owner.md",
            _PO_HEADING,
            ("@walking-skeleton", "@infrastructure"),
        ),
        AuthoringSurface.PRODUCT_OWNER_AGENT_INSTALLED: SurfaceSpec(
            home / ".claude" / "agents" / "nw" / "nw-product-owner.md",
            _PO_HEADING,
            ("@walking-skeleton", "@infrastructure"),
        ),
    }


def extract_section(text: str, heading_prefix: str) -> str:
    """Fence-aware extraction of the first ``## {heading_prefix}...`` H2
    section's body -- a ``## `` line inside a fenced code block never counts
    as a section boundary."""
    lines = text.splitlines()
    collected: list[str] = []
    in_fence = False
    started = False
    for line in lines:
        is_fence_delim = line.strip().startswith("```")
        if not started:
            if (
                not in_fence
                and line.startswith("## ")
                and line[3:].startswith(heading_prefix)
            ):
                started = True
                collected.append(line)
            if is_fence_delim:
                in_fence = not in_fence
            continue
        if is_fence_delim:
            in_fence = not in_fence
            collected.append(line)
            continue
        if not in_fence and line.startswith("## "):
            break
        collected.append(line)
    return "\n".join(collected)


def documents_dependency_token(section_text: str) -> bool:
    return bool(_DEPENDENCY_TOKEN_RE.search(section_text))


def states_default_flip(section_text: str) -> bool:
    return bool(_SILENCE_RE.search(section_text)) and bool(
        _PARALLEL_SAFE_RE.search(section_text)
    )


def documents_all(section_text: str, tokens: tuple[str, ...]) -> bool:
    return all(token in section_text for token in tokens)


_FABRICATED_FIXTURES: dict[FabricatedFixture, tuple[str, tuple[str, ...]]] = {
    FabricatedFixture.TOKEN_OUTSIDE_SECTION: (
        "# nw-discuss\n\n"
        f"## {_DISCUSS_HEADING}\n\n"
        "Annotation tokens:\n"
        "- `@walking_skeleton` / `@infrastructure` -- govern ordering.\n"
        "- `@coupled` -- the carpaccio ceiling-escape.\n\n"
        "## Unrelated Appendix\n\n"
        "Some later, unrelated section that happens to mention "
        "`depends-on {slice-id}` in passing -- silence means parallel-safe "
        "elsewhere in the document, but not in the vocabulary section.\n",
        ("@walking_skeleton", "@infrastructure", "@coupled"),
    ),
    FabricatedFixture.BARE_TOKEN_NO_FLIP: (
        f"## {_DISCUSS_HEADING}\n\n"
        "Annotation tokens:\n"
        "- `@walking_skeleton` / `@infrastructure` -- govern ordering.\n"
        "- `@coupled` -- the carpaccio ceiling-escape.\n"
        "- `depends-on {slice-id}` -- a declared slice dependency.\n",
        ("@walking_skeleton", "@infrastructure", "@coupled"),
    ),
    FabricatedFixture.DROPS_EXISTING_TOKEN: (
        f"## {_DISCUSS_HEADING}\n\n"
        "Annotation tokens:\n"
        "- `@walking_skeleton` / `@infrastructure` -- govern ordering.\n"
        "- `depends-on {slice-id}` -- silence (no declared dependency) reads "
        "parallel-safe by default; a declared dependency must carry a "
        "non-empty Justification.\n",
        ("@walking_skeleton", "@infrastructure", "@coupled"),
    ),
}


class SliceDependencyDiscoverabilityComposition:
    """Resolves a real authoring surface (or a fabricated fixture) to its
    extracted vocabulary section."""

    def read_surface(self, surface: AuthoringSurface) -> SectionRead:
        spec = _surface_table()[surface]
        if not spec.path.is_file():
            return SectionRead(
                section_text="",
                existing_tokens=spec.existing_tokens,
                surface_present=False,
            )
        text = spec.path.read_text(encoding="utf-8")
        return SectionRead(
            section_text=extract_section(text, spec.heading),
            existing_tokens=spec.existing_tokens,
            surface_present=True,
        )

    def read_fabricated(self, fixture: FabricatedFixture) -> SectionRead:
        """Run the fabricated fixture's FULL file text through the SAME
        ``extract_section`` a real surface read uses -- proves the
        negative scenarios exercise the extraction boundary itself, not a
        pre-extracted string standing in for it (the exact bug that made
        the "token outside the section" negative AT pass for the wrong
        reason on first RED: it returned the whole fixture, appendix
        included, unextracted)."""
        text, existing_tokens = _FABRICATED_FIXTURES[fixture]
        return SectionRead(
            section_text=extract_section(text, _DISCUSS_HEADING),
            existing_tokens=existing_tokens,
            surface_present=True,
        )
