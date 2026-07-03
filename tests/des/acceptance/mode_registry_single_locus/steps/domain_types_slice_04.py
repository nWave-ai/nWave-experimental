"""Typed domain vocabulary for mode-registry-single-locus slice-04.

The SSOT-via-Types-Services-DSL mandate, criterion 1 — every domain noun the
slice-04 Gherkin speaks has a typed home here. Shared nouns are IMPORTED from
the earlier slices' modules (one definition per concept, never re-declared):
`WorkflowFlavor` / `RegionId` come from the slice-01/02 vocabulary.

Slice-04 is the BULK slice: its nouns are (i) the two rendering
cardinalities slice-02 routed here (C1a empty conditional set / C3
many-skills list), (ii) the naked-mode-literal sweep contract (the Layer-A
precondition pinned AS DATA — the gate CLI is slice-05 scope), and (iii)
the prose-watcher deletion-safety ledger: every retired presence-assertion
test location named, mapped to what it guarded and to the replacement that
now guards it, with an explicit DELETE / KEEP verdict (the slice-03 AT-03
equivalence pattern applied to the watcher inventory).

Verified inventory provenance (2026-06-11, current tree at 9972dbe2d):
35 asset files / 277 naked `atdd_pure` | `workflow.mode` occurrences across
nWave/{skills,agents,tasks}; 10 watcher locations classified below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .domain_types_slice_02 import RegionId, WorkflowFlavor


__all__ = [
    "AGENT_SPEC_BY_PHRASE",
    "ALLOW_MARKER",
    "GUARDED_ASSET_BY_PHRASE",
    "MANY_SKILLS_SENTINELS",
    "MIGRATED_FAMILIES",
    "NAKED_MODE_LITERAL_PATTERNS",
    "RENDER_CASE_BY_PHRASE",
    "WATCHER_BY_PHRASE",
    "WATCHER_LEDGER",
    "AgentRenderCase",
    "ProseWatcher",
    "RegionId",
    "RenderCaseSpec",
    "WatcherVerdict",
    "WorkflowFlavor",
]


# --- AT-01: the two rendering cardinalities routed here by slice-02 ----------

MANY_SKILLS_SENTINELS: tuple[str, ...] = (
    "nw-bulk-sentinel-skill-alpha",
    "nw-bulk-sentinel-skill-beta",
)
"""Conditional-skill sentinels that appear NOWHERE in the shipped assets —
their presence in a rendered region proves registry read-through (the
slice-02 wiring-witness technique) and their leak into another agent's
region proves cross-contamination."""


class AgentRenderCase(Enum):
    """The C1a / C3 cardinalities of a registry `skill_load_set` answer."""

    EMPTY_SET = "empty-set"
    MANY_SKILLS = "many-skills"


@dataclass(frozen=True)
class RenderCaseSpec:
    """One parametrized rendering case: which agent, which declared answer."""

    case: AgentRenderCase
    agent_id: str
    conditional: tuple[str, ...]
    leak_guards: tuple[str, ...]
    """Skill names that MUST NOT appear in this agent's rendered region."""

    @property
    def spec_rel(self) -> Path:
        return Path("nWave") / "agents" / f"{self.agent_id}.md"


_EMPTY_SET_CASE = RenderCaseSpec(
    case=AgentRenderCase.EMPTY_SET,
    agent_id="nw-product-owner",
    conditional=(),
    # declared-empty must not borrow ANY other agent's answer:
    leak_guards=MANY_SKILLS_SENTINELS + ("nw-crafter-discipline-atdd-pure",),
)

_MANY_SKILLS_CASE = RenderCaseSpec(
    case=AgentRenderCase.MANY_SKILLS,
    agent_id="nw-acceptance-designer",
    conditional=MANY_SKILLS_SENTINELS,
    leak_guards=("nw-crafter-discipline-atdd-pure",),
)

RENDER_CASE_BY_PHRASE: dict[str, RenderCaseSpec] = {
    "no conditional skills for the product owner": _EMPTY_SET_CASE,
    "two freshly minted conditional skills for the acceptance designer": (
        _MANY_SKILLS_CASE
    ),
}

AGENT_SPEC_BY_PHRASE: dict[str, RenderCaseSpec] = {
    "product owner": _EMPTY_SET_CASE,
    "acceptance designer": _MANY_SKILLS_CASE,
}


# --- AT-02: the naked-mode-literal sweep (Layer-A precondition as data) -------

NAKED_MODE_LITERAL_PATTERNS: tuple[str, ...] = (
    r"\batdd_pure\b",
    r"\bworkflow\.mode\b",
)
"""The unambiguous mode-literal pair the sweep pins. Bare-`classic` token
disambiguation (a `classic` word also occurs in mode-unrelated prose) is the
slice-05 `mode_locus_gate` design call — routed, never silently widened."""

ALLOW_MARKER = "<!-- mode-ref-ok -->"
"""A line carrying this marker is an EXPLICIT mode reference (analysis §3.1):
the sweep tolerates it; everything else outside a GENERATED region is a
hand-written re-statement of the mode — the duplication smell."""

MIGRATED_FAMILIES: tuple[Path, ...] = (
    Path("nWave") / "skills",
    Path("nWave") / "agents",
    Path("nWave") / "tasks",
)
"""The three asset families Layer A scans (analysis §3.1)."""


# --- AT-03: the prose-watcher deletion-safety ledger --------------------------


class WatcherVerdict(Enum):
    """DELETED — the watcher's guarded fact migrated into the registry
    projection, so the staleness check now guards it and the watcher goes.
    KEPT — the watcher guards something the slice-04 migration does NOT
    replace; deleting it would lose a guard (routed, see `routed_to`)."""

    DELETED = "deleted"
    KEPT = "kept"


@dataclass(frozen=True)
class ProseWatcher:
    """One presence-assertion test location from the verified inventory."""

    location: str
    """Repo-root-relative test dir (or single file) — the deletion unit."""
    guarded: str
    """What the watcher asserted, in one line."""
    verdict: WatcherVerdict
    replacement: str
    """The guard that takes over (DELETED) or why it must stay (KEPT)."""


WATCHER_LEDGER: tuple[ProseWatcher, ...] = (
    # --- DELETE: guarded nWave asset mode prose; the prose migrates into
    # GENERATED regions projected from the registry, so the guarded fact
    # ceases to exist as hand-written text and `docgen --check` (shipped
    # slice-02) guards the projection that replaces it. ---
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_nw_deliver_spine",
        "nw-deliver SKILL.md carries the atdd_pure spine-branch prose",
        WatcherVerdict.DELETED,
        "GENERATED:mode-descriptor region in nw-deliver (shipped slice-02) "
        "+ docgen --check staleness refusal",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_nw_bugfix_mode",
        "nw-bugfix SKILL.md carries the mode-awareness prose",
        WatcherVerdict.DELETED,
        "GENERATED:mode-descriptor region in nw-bugfix + docgen --check",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_nw_execute_continue",
        "nw-execute / nw-continue SKILLs + tasks execute/continue carry "
        "mode-coherent prose",
        WatcherVerdict.DELETED,
        "GENERATED regions in those four assets + docgen --check; "
        "residual mode references carry the allow-marker and the sweep",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_finalize_mutation_optimize",
        "nw-finalize / nw-mutation-test / nw-optimize-tests carry mode-coherent prose",
        WatcherVerdict.DELETED,
        "GENERATED regions in those three skills + docgen --check",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_review_methodology_coherence",
        "the three reviewer agent specs + nw-review / "
        "nw-deliver-orchestration / nw-tdd-review-enforcement carry "
        "mode-coherent prose",
        WatcherVerdict.DELETED,
        "GENERATED skill-load-set / mode-descriptor regions in those six "
        "assets + registry skill_load_set rows + docgen --check",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_roadmap_classic_only_coherence",
        "nw-roadmap / nw-root-why + tasks/roadmap flag roadmap as classic-only",
        WatcherVerdict.DELETED,
        "GENERATED regions / allow-markers in those assets + docgen --check "
        "+ the slice-04 naked-literal sweep",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_mode_detection_resume_coherence",
        "nw-at-completeness-check / nw-buddy-project-reading / "
        "nw-fast-forward carry mode-coherent prose",
        WatcherVerdict.DELETED,
        "GENERATED regions in those three skills + docgen --check",
    ),
    ProseWatcher(
        "tests/scripts/cli/atdd_pure_feature_end_cycle",
        "nw-deliver SKILL.md carries the feature-end-cycle mode prose",
        WatcherVerdict.DELETED,
        "registry deliver_phase_shape projected into nw-deliver's "
        "GENERATED:mode-descriptor region (shipped slice-02) + docgen --check",
    ),
    # --- KEEP: not replaced by the slice-04 migration; deleting would lose
    # a guard. Routed explicitly (feature-delta DISTILL slice-04 section). ---
    # NOTE: the atdd_pure_documentation_coherence watcher (formerly KEPT here)
    # was removed — the docs/ prose it guarded (des-markers.md AT-completion
    # ledger, deliver tutorial) was WITHDRAWN by hotfix 47d6a504c, an ancestor
    # of this branch, so the guarded fact no longer exists at HEAD. It was not
    # migrated into a registry projection (so not DELETED-verdict either); it
    # is simply retired. Stale-record rule: behaviour changed, git keeps history.
    ProseWatcher(
        "tests/des/acceptance/atdd_pure_phase_count_slice03/"
        "test_prose_runtime_parity.py",
        "nw-deliver phase-set prose agrees with the live runtime CLI",
        WatcherVerdict.KEPT,
        "post-migration the open leg is registry<->runtime agreement — "
        "slice-05 Layer-C scope; docgen --check alone does not cover it",
    ),
    ProseWatcher(
        "tests/des/acceptance/atdd_pure_dispatch_lifecycle/"
        "test_atdd_pure_dispatch_template.py",
        "the FUNCTIONAL atdd_pure dispatch template in nw-execute "
        "round-trips through the real parser",
        WatcherVerdict.KEPT,
        "guards behaviour (parser validity), not prose presence; the "
        "template's mode literals get allow-markers at GREEN, the template "
        "content itself is preserved",
    ),
)


WATCHER_BY_PHRASE: dict[str, ProseWatcher] = {
    "bugfix mode watcher": WATCHER_LEDGER[1],
    "review methodology watcher": WATCHER_LEDGER[4],
}

GUARDED_ASSET_BY_PHRASE: dict[str, Path] = {
    "bugfix guide": Path("nWave") / "skills" / "nw-bugfix" / "SKILL.md",
    "software-crafter reviewer spec": (
        Path("nWave") / "agents" / "nw-software-crafter-reviewer.md"
    ),
}
