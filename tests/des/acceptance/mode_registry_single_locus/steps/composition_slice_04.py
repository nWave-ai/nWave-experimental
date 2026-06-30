"""Composition root for mode-registry-single-locus slice-04 (the SSOT-via-Types-Services-DSL mandate).

Pillar 3 (App as in production): the SUT is the REAL docgen CLI
(`scripts/docgen.py`), driven as a Layer-3 subprocess via the slice-02/03
contract surface (`--root <working-copy> [--check]`) — one mechanism, fourth
projection consumer. The working copy is built from BYTE-COPIES of the
ENTIRE shipped nWave/{agents,tasks,skills,flavors,templates} trees + the
framework catalog, so the assertions witness the REAL assets' migrated
state at GREEN.

Driving-Port-Only Boundary attestation (S2 gate): the ONLY production import
here is `des.application.flavor_dispatcher.resolve_skill_load_set` — the
slice-01-attested Layer-3 composition driving port, used as the
EXPECTED-side read API ("region content equals seam output"). docgen itself
is driven by subprocess, never imported. The watcher-ledger assertions read
the live repository test tree — the legitimate structural-gate driving
surface for a removal-debt contract (precedent:
tests/methodology/test_code_design_skill_dedup.py). No `des.domain.*` /
`des.adapters.*` import anywhere.

Dormant-Seam Reconciliation (D11 / S3): slice-04 declares no net-new
production seam — the DESIGN-declared net-new SURFACE is data reach,
witnessed through the real entry point: registry rows for the remaining
agents incl. the declared-EMPTY cardinality (AT-01), bulk region coverage +
the zero-naked-literal end state (AT-02), watcher deletion with replacement
teeth (AT-03).

DISTILL-authored ACTIVE-RED (ADR-025 / ADR-GV-001 D6): no Mandate-7 scaffold
is needed — the driving entry and both region ids exist (slice-02 GREEN).
The missing capability surfaces as semantic `AssertionError` in Then steps:
AT-01 fails because the byte-copied agent specs carry NO generated
skill-load region yet; AT-02 fails because 277 naked mode literals survive
in the copied families; AT-03 fails because the DELETE-verdict watcher dirs
are still present in the live test tree. Never an import/setup error.

Mandate 8 (layer-3 FS acceptance): mutating steps assert via
`assert_state_delta(before, after, universe, expected)` over port-exposed
observables only (generated-region bodies, asset text outside regions,
per-family content fingerprints). The sweep and the staleness check assert
the empty-expected preservation contract (they rewrite nothing).
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from nwave_ai.state_delta import assert_state_delta

from des.application.flavor_dispatcher import resolve_skill_load_set
from scripts import docgen
from tests.common.in_process_cli import run_cli_in_process

from .composition_slice_02 import (
    _CliOutcome,
    _extract_region,
    _outside_region,
    _region_pattern,
)
from .domain_types_slice_04 import (
    ALLOW_MARKER,
    MIGRATED_FAMILIES,
    NAKED_MODE_LITERAL_PATTERNS,
    WATCHER_LEDGER,
    ProseWatcher,
    RegionId,
    RenderCaseSpec,
    WatcherVerdict,
    WorkflowFlavor,
)


REPO_ROOT = Path(__file__).resolve().parents[5]

FLAVORS_REL = Path("nWave") / "flavors"
CATALOG_REL = Path("nWave") / "framework-catalog.yaml"

# The whole-tree byte-copy set: everything the real docgen pipeline scans.
_COPIED_TREES = (
    Path("nWave") / "agents",
    Path("nWave") / "tasks",
    Path("nWave") / "skills",
    Path("nWave") / "templates",
    FLAVORS_REL,
)

_SWEEP_SUFFIXES = {".md", ".yaml", ".yml"}

_NAKED_LITERAL_RES = tuple(re.compile(p) for p in NAKED_MODE_LITERAL_PATTERNS)

# Any GENERATED region, any region id — the sweep strips them all before
# counting (a literal INSIDE a projection is the registry speaking, not a
# hand-written copy). Grammar per the DESIGN SSOT (analysis §2.3.2).
_ANY_REGION_RE = re.compile(
    r"<!--\s*GENERATED:[a-z][a-z0-9-]*\s+START.*?-->.*?"
    r"<!--\s*GENERATED:[a-z][a-z0-9-]*\s+END\s*-->",
    re.DOTALL,
)

_HAND_EDIT_SENTINEL = "hand-edited bulk drift sentinel — not what the registry projects"


def _strip_regions(text: str) -> str:
    return _ANY_REGION_RE.sub("<GENERATED-REGION>", text)


def _count_naked_literals(text: str) -> int:
    survivors = 0
    for line in _strip_regions(text).splitlines():
        if ALLOW_MARKER in line:
            continue
        survivors += sum(len(rx.findall(line)) for rx in _NAKED_LITERAL_RES)
    return survivors


class BulkMigrationSweepComposition:
    """Single source of truth for all slice-04 step-method business logic.

    Step bodies delegate here (the SSOT-via-Types-Services-DSL mandate,
    criterion 3: <=2 statements, no control flow inline).
    """

    def __init__(self, tmp_path: Path) -> None:
        self._worktree = tmp_path / "worktree"
        self._case: RenderCaseSpec | None = None
        self._before: dict[str, str] | None = None
        self._after: dict[str, str] | None = None
        self._render: _CliOutcome | None = None
        self._baseline_check: _CliOutcome | None = None
        self._check: _CliOutcome | None = None
        self._sweep_findings: list[tuple[str, int]] | None = None

    # --- Given: the bulk working copy + registry authoring --------------------

    def build_bulk_working_copy(self) -> None:
        """Byte-copy the entire shipped asset families + registry + catalog."""
        for rel in _COPIED_TREES:
            shutil.copytree(REPO_ROOT / rel, self._worktree / rel)
        target = self._worktree / CATALOG_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / CATALOG_REL).read_bytes())

    def declare_render_case(self, case: RenderCaseSpec) -> None:
        """Author the case's `skill_load_set` row into the WORKING registry —
        replace-or-insert, so the AT is stable whether or not the shipped
        registry already declares the agent (GREEN ships the real rows).
        The classic flavor declares the agent with the empty set (the
        slice-01 refusal contract forbids a missing row)."""
        self._case = case
        self._upsert_skill_load_row(
            WorkflowFlavor.ATDD_PURE, case.agent_id, case.conditional
        )
        self._upsert_skill_load_row(WorkflowFlavor.CLASSIC, case.agent_id, ())

    def freshly_render_and_accept(self) -> None:
        """Pillar-2 chaining: the AT-01 When reused as the AT-02/03 baseline.
        Outcomes recorded, asserted in Then (never in Given) so RED stays an
        AssertionError in Then."""
        self._render = self._docgen()
        self._baseline_check = self._docgen("--check")

    def hand_edit_guarded_region(self, asset_rel: Path) -> None:
        """Corrupt the formerly-guarded asset's generated region behind the
        projection's back (the slice-02 drift technique, applied to a
        bulk-family asset). Active-RED state: the byte-copied asset carries
        no region yet — plant a stale one so the check has something to
        refuse; the RED failure comes from the watcher-gone assertion."""
        path = self._worktree / asset_rel
        text = path.read_text(encoding="utf-8")
        pattern = _region_pattern(RegionId.MODE_DESCRIPTOR)
        stale = (
            f"<!-- GENERATED:{RegionId.MODE_DESCRIPTOR.value} START — "
            f"hand-edited -->\n{_HAND_EDIT_SENTINEL}\n"
            f"<!-- GENERATED:{RegionId.MODE_DESCRIPTOR.value} END -->"
        )
        if pattern.search(text):
            text = pattern.sub(stale, text)
        else:
            text += f"\n{stale}\n"
        path.write_text(text, encoding="utf-8")

    # --- When: drive the real docgen CLI / the sweep ---------------------------

    def render_bulk_working_copy(self) -> None:
        self._before = self._capture_case_universe()
        self._render = self._docgen()
        self._after = self._capture_case_universe()

    def run_naked_literal_sweep(self) -> None:
        self._before = self._capture_family_universe()
        self._sweep_findings = self._sweep()
        self._after = self._capture_family_universe()

    def run_bulk_staleness_check(self) -> None:
        self._before = self._capture_family_universe()
        self._check = self._docgen("--check")
        self._after = self._capture_family_universe()

    # --- Then: AT-01 rendering outcomes -----------------------------------------

    def assert_bulk_render_completed(self) -> None:
        assert self._render is not None and self._render.exit_code == 0, (
            "the bulk re-render was REFUSED by the docgen entry point.\n"
            f"{self._render.transcript if self._render else '(never ran)'}"
        )

    def assert_agent_region_matches_seam(self, case: RenderCaseSpec) -> None:
        seam_answer = resolve_skill_load_set(
            case.agent_id,
            WorkflowFlavor.ATDD_PURE.value,
            flavors_dir=self._worktree / FLAVORS_REL,
        )
        region = (self._after or {})[f"{case.agent_id}.skill_load_region"]
        assert region.strip(), (
            f"the {case.agent_id} spec carries NO generated skill-load region "
            "after the bulk re-render — the registry projection never landed "
            "in this agent's spec (the bulk migration has not reached it)"
        )
        missing = [skill for skill in seam_answer if skill not in region]
        assert not missing, (
            f"the generated skill-load region disagrees with the registry "
            f"resolution seam for {case.agent_id}: seam answers "
            f"{list(seam_answer)}, region is missing {missing}.\n"
            f"region body:\n{region}"
        )
        leaked = [guard for guard in case.leak_guards if guard in region]
        assert not leaked, (
            f"the {case.agent_id} spec's region leaks another agent's answer "
            f"({leaked}) — the registry declared "
            f"{list(seam_answer) or 'NO conditional skills'} for this agent.\n"
            f"region body:\n{region}"
        )

    def assert_agent_outside_region_untouched(self, case: RenderCaseSpec) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe={f"{case.agent_id}.outside_region"},
            expected={},  # bounded change: anything outside the region is frozen
        )

    # --- Then: AT-02 sweep outcomes ----------------------------------------------

    def assert_no_naked_literal_survives(self) -> None:
        assert self._sweep_findings is not None, "the sweep never ran"
        total = sum(count for _, count in self._sweep_findings)
        worklist = "\n".join(
            f"  {count:4}  {rel}" for rel, count in self._sweep_findings[:40]
        )
        assert not self._sweep_findings, (
            f"{total} hand-written mode statement(s) survive outside a "
            f"GENERATED region / `{ALLOW_MARKER}` line across "
            f"{len(self._sweep_findings)} asset file(s) in the migrated "
            "families — the bulk migration is incomplete. Worklist (count, "
            f"file):\n{worklist}"
        )

    def assert_sweep_rewrites_nothing(self) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={},  # fail-closed: the sweep is a pure read
        )

    # --- Then: AT-03 watcher-ledger outcomes ---------------------------------------

    def assert_watcher_deleted(self, watcher: ProseWatcher) -> None:
        location = REPO_ROOT / watcher.location
        assert not location.exists(), (
            f"the retired prose-watcher still stands at {watcher.location} — "
            f"it guarded '{watcher.guarded}', which is now guarded by: "
            f"{watcher.replacement}. The watcher must be DELETED (stale-record "
            "rule: behaviour changed, git keeps the history)"
        )

    def assert_keeper_watchers_still_present(self) -> None:
        missing = [
            watcher.location
            for watcher in WATCHER_LEDGER
            if watcher.verdict is WatcherVerdict.KEPT
            and not (REPO_ROOT / watcher.location).exists()
        ]
        assert not missing, (
            "watcher(s) ruled KEPT by the deletion-safety ledger were "
            f"deleted anyway — their guard has NO replacement: {missing}"
        )

    def assert_refused_naming_guarded_asset(self, asset_rel: Path) -> None:
        assert self._check is not None, "the staleness check never ran"
        output = self._check.stdout + self._check.stderr
        assert self._check.exit_code != 0 and asset_rel.name in output, (
            "the staleness check did not refuse the drifted working copy by "
            f"naming the formerly-guarded asset ({asset_rel}) — the "
            "replacement guard has no teeth on the bulk-migrated families.\n"
            f"{self._check.transcript}"
        )

    def assert_accepted_before_hand_edit(self) -> None:
        assert self._baseline_check is not None and (
            self._baseline_check.exit_code == 0
        ), (
            "the freshly re-rendered working copy was NOT accepted by the "
            "staleness check before the hand-edit — the refusal above proves "
            "nothing.\n"
            f"{self._baseline_check.transcript if self._baseline_check else '(never ran)'}"
        )

    # --- internals -------------------------------------------------------------------

    def _upsert_skill_load_row(
        self, flavor: WorkflowFlavor, agent_id: str, conditional: tuple[str, ...]
    ) -> None:
        flavor_file = self._worktree / FLAVORS_REL / f"{flavor.value}.yaml"
        text = flavor_file.read_text(encoding="utf-8")
        if "skill_load_set:" not in text:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"working registry {flavor_file} carries no skill_load_set "
                "block — slice-04 fixture needs re-basing on the shipped tree"
            )
        # drop any existing row for the agent (replace-or-insert)
        text = re.sub(
            rf"^  {re.escape(agent_id)}:\n(?:    .*\n|\n(?=    ))*",
            "",
            text,
            flags=re.MULTILINE,
        )
        if conditional:
            items = "".join(f"      - {skill}\n" for skill in conditional)
            row = f"  {agent_id}:\n    conditional:\n{items}"
        else:
            row = f"  {agent_id}:\n    conditional: []\n"
        text = text.replace("skill_load_set:\n", f"skill_load_set:\n{row}", 1)
        flavor_file.write_text(text, encoding="utf-8")

    def _docgen(self, *args: str) -> _CliOutcome:
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--root",
                str(self._worktree),
                "--output-dir",
                str(self._worktree / "docs" / "reference"),
                *args,
            ],
            cwd=REPO_ROOT,
            main=docgen.main,
        )
        return _CliOutcome(exit_code, stdout, stderr)

    def _iter_family_files(self):
        for family in MIGRATED_FAMILIES:
            root = self._worktree / family
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix in _SWEEP_SUFFIXES:
                    yield path

    def _sweep(self) -> list[tuple[str, int]]:
        findings: list[tuple[str, int]] = []
        for path in self._iter_family_files():
            count = _count_naked_literals(path.read_text(encoding="utf-8"))
            if count:
                findings.append((str(path.relative_to(self._worktree)), count))
        return findings

    def _capture_case_universe(self) -> dict[str, str]:
        """Port-exposed observables for the AT-01 rendering case: the case
        agent's generated region body + the spec text outside it."""
        assert self._case is not None, "no render case declared"
        text = (self._worktree / self._case.spec_rel).read_text(encoding="utf-8")
        return {
            f"{self._case.agent_id}.skill_load_region": _extract_region(
                text, RegionId.SKILL_LOAD_SET
            ),
            f"{self._case.agent_id}.outside_region": _outside_region(
                text, RegionId.SKILL_LOAD_SET
            ),
        }

    def _capture_family_universe(self) -> dict[str, str]:
        """Port-exposed observables for the bulk steps: one content
        fingerprint per migrated family (preservation contract — the sweep
        and the check rewrite nothing)."""
        universe: dict[str, str] = {}
        for family in MIGRATED_FAMILIES:
            digest = hashlib.sha256()
            for path in sorted((self._worktree / family).rglob("*")):
                if path.is_file():
                    digest.update(str(path.relative_to(self._worktree)).encode())
                    digest.update(path.read_bytes())
            universe[f"families.{family.name}_fingerprint"] = digest.hexdigest()
        return universe
