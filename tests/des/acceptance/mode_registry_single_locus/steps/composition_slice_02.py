"""Composition root for mode-registry-single-locus slice-02 (the SSOT-via-Types-Services-DSL mandate).

Pillar 3 (App as in production): the SUT is the REAL docgen CLI
(`scripts/docgen.py`), driven as a Layer-3 subprocess — the Driving-Port-Only
Boundary mandate's preferred surface for CLI behaviors (SSOT
`nw-test-design-mandates`). The `--root <working-copy>` override (analogous to
the existing `--output-dir`) is part of the slice-02 contract surface: it
rebases the asset tree docgen scans/projects so the full real entry
(argparse -> pipeline -> projection / staleness check) runs against a working
copy under tmp_path, never mutating the live repository.

The working copy is built from BYTE-COPIES of the real shipped assets
(`nw-software-crafter.md`, the `nw-deliver` guide, both flavor files, the
framework catalog) plus minimal stubs for the agent's referenced skills so the
real docgen pipeline enriches and renders exactly as in production. Because
the copies ARE the shipped bytes, the retirement and region assertions witness
the REAL assets' migrated state at GREEN.

Driving-Port-Only Boundary attestation (S2 gate): the ONLY production import
here is `des.application.flavor_dispatcher.resolve_skill_load_set` — the
slice-01-attested Layer-3 composition driving port, used as the EXPECTED-side
read API per the slice plan ("region content equals seam output"; one
registry-read SSOT, two consumers: gates + docgen). docgen itself is driven by
subprocess, never imported. No `des.domain.*` / `des.adapters.*` import; no
hand-rolled markdown rewrite as oracle — region-content assertions are
sanctioned because the projected region content IS the observable contract.

Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared slice-02 seams —
(i) the docgen projection consuming `resolve_skill_load_set` (resolving the
slice-01 owned dormancy), (ii) the `GENERATED:mode-descriptor` render from the
new `descriptor` + `deliver_phase_shape` registry fields, (iii) the Layer-C
staleness check — are each driven through the real CLI entry point and
asserted by observable effect (bounded file delta / refusal verdict).

DISTILL-authored ACTIVE-RED (ADR-025 / ADR-GV-001 D6): NO production scaffold
is needed — the driving entry (`scripts/docgen.py`) already exists. The
missing capability surfaces as a captured CLI refusal (exit 2, unknown
`--root`) recorded in When and asserted semantically in Then, so every
scenario RUNS and FAILS with `MISSING_FUNCTIONALITY` (AssertionError), none is
skipped, and no import/setup error masks the RED.

Mandate 8 (layer-3 FS acceptance): every mutating step asserts via
`assert_state_delta(before, after, universe, expected)` over port-exposed
observables only (generated-region bodies, asset text outside the regions,
registry file texts). The staleness check asserts the empty-expected
preservation contract: anything in the universe that changes is a violation
(fail-closed) — the check rewrites nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from nwave_ai.state_delta import assert_state_delta, containing, unchanged

from des.application.flavor_dispatcher import resolve_skill_load_set
from scripts import docgen
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_02 import (
    ATDD_DESCRIPTOR_SENTINEL,
    CRAFTER_AGENT,
    DESCRIPTOR_SENTINEL_BY_FLAVOR,
    EDITED_CRAFTER_SKILL,
    INLINE_ROW_MARKER,
    RETIRED_INLINE_SKILL,
    SHIPPED_FLAVORS,
    ProjectionDrift,
    RegionId,
    WorkflowFlavor,
)


REPO_ROOT = Path(__file__).resolve().parents[5]

CRAFTER_SPEC_REL = Path("nWave") / "agents" / "nw-software-crafter.md"
DELIVER_GUIDE_REL = Path("nWave") / "skills" / "nw-deliver" / "SKILL.md"
FLAVORS_REL = Path("nWave") / "flavors"
CATALOG_REL = Path("nWave") / "framework-catalog.yaml"

# Frontmatter `skills:` list entries of the copied agent spec — each gets a
# minimal stub skill dir so the real docgen enrich stage validates the copy
# exactly as it validates the shipped tree.
_FRONTMATTER_SKILL_RE = re.compile(r"^\s+-\s+(nw-[a-z0-9-]+)\s*$", re.MULTILINE)

# Replace-in-place targets for the working registry's descriptor fields
# (post-review amendment 2026-06-11: single-key legal registry — the shipped
# folded `descriptor: >` block and the quoted `deliver_phase_shape:` line).
_DESCRIPTOR_BLOCK_RE = re.compile(r"^descriptor: >\n(?:  .+\n)+", re.MULTILINE)
_PHASE_SHAPE_LINE_RE = re.compile(r"^deliver_phase_shape: .+$", re.MULTILINE)

# Two-space-indented agent rows of a flavor's `skill_load_set` block (dots in
# lifecycle-event keys exclude them from this charset by construction).
_SKILL_LOAD_AGENT_RE = re.compile(r"^  ([a-z][a-z0-9-]*[a-z0-9]):$", re.MULTILINE)

_HAND_EDIT_SENTINEL = "hand-edited drift sentinel — not what the registry says"


def _region_pattern(region_id: RegionId) -> re.Pattern[str]:
    """Marker grammar per the DESIGN SSOT (analysis §2.3.2)."""
    rid = re.escape(region_id.value)
    return re.compile(
        rf"<!--\s*GENERATED:{rid}\s+START.*?-->\n?(.*?)<!--\s*GENERATED:{rid}\s+END\s*-->",
        re.DOTALL,
    )


def _extract_region(text: str, region_id: RegionId) -> str:
    """The generated region body, or '' when the asset carries no region yet."""
    match = _region_pattern(region_id).search(text)
    return match.group(1) if match else ""


def _outside_region(text: str, region_id: RegionId) -> str:
    """The asset text with the generated region (markers + body) collapsed."""
    return _region_pattern(region_id).sub("<GENERATED-REGION>", text)


@dataclass(frozen=True)
class _CliOutcome:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def transcript(self) -> str:
        return f"exit={self.exit_code}\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"


class DocgenProjectionComposition:
    """Single source of truth for all slice-02 step-method business logic.

    Step bodies delegate here (the SSOT-via-Types-Services-DSL mandate,
    criterion 3: <=2 statements, no control flow inline).
    """

    def __init__(self, tmp_path: Path) -> None:
        self._worktree = tmp_path / "worktree"
        self._before: dict[str, str] | None = None
        self._after: dict[str, str] | None = None
        self._render: _CliOutcome | None = None
        self._baseline_check: _CliOutcome | None = None
        self._check: _CliOutcome | None = None

    # --- Given: working copy + registry authoring ---------------------------

    def build_working_copy(self) -> None:
        """Byte-copy the shipped assets + registry into a tmp working copy."""
        for rel in (CRAFTER_SPEC_REL, DELIVER_GUIDE_REL, CATALOG_REL):
            self._copy_shipped(rel)
        # Copy what SHIPS. Iterating the enum copies a retired fixture identity
        # too, and there is no file behind it to byte-copy.
        for flavor in SHIPPED_FLAVORS:
            self._copy_shipped(FLAVORS_REL / f"{flavor.value}.yaml")
        (self._worktree / "nWave" / "tasks" / "nw").mkdir(parents=True, exist_ok=True)
        (self._worktree / "nWave" / "templates").mkdir(parents=True, exist_ok=True)
        self._stub_referenced_skills()
        self._stub_declared_agents()

    def author_mode_descriptors(self) -> None:
        """Replace the registry's descriptor fields IN PLACE with sentinel
        values proving registry read-through (post-review amendment
        2026-06-11: the shipped flavor files already carry the fields since
        slice-02 GREEN, so the working copy must stay a LEGAL single-key
        registry — each field declared EXACTLY ONCE, the state the slice-05
        Layer-B gate demands; the earlier append-pattern relied on illegal
        duplicate-key shadowing). The phase-shape sentinel targets the
        CLASSIC flavor only: the DEFAULT flavor's `deliver_phase_shape`
        keeps the shipped runtime-canonical value the Layer-C agreement leg
        cross-checks (see `domain_types_slice_02` module docstring)."""
        self._replace_descriptor(
            WorkflowFlavor.ATDD_PURE,
            descriptor=ATDD_DESCRIPTOR_SENTINEL,
        )
        # The second flavor is gone with the mode: the projection now has one
        # descriptor to cross-check, not two. Replacing a descriptor in a file
        # the product no longer ships fails on the file, not on the property.

    def edit_registry_to_direct_crafter_elsewhere(self) -> None:
        """The wiring-witness edit: the working registry now directs the
        crafter to a sentinel skill that appears nowhere in the shipped
        assets."""
        flavor_file = self._flavors_dir / f"{WorkflowFlavor.ATDD_PURE.value}.yaml"
        original = flavor_file.read_text(encoding="utf-8")
        edited = original.replace(
            f"- {RETIRED_INLINE_SKILL}", f"- {EDITED_CRAFTER_SKILL}"
        )
        if edited == original:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"WHAT: working registry {flavor_file} no longer carries the "
                f"skill_load_set row '- {RETIRED_INLINE_SKILL}' under "
                "nw-software-crafter's `conditional:` list. "
                "WHY: this fixture edits that exact row to a sentinel skill to "
                "prove the crafter-spec projection reads the registry (never a "
                "baked value) -- with no row there is nothing to edit. "
                f"HOW: diff {flavor_file} against the shipped "
                "nWave/flavors/atdd_pure.yaml. If nw-software-crafter still "
                "directs this skill under a RENAMED value, update "
                "RETIRED_INLINE_SKILL in domain_types_slice_01.py to the new "
                "name. If nw-software-crafter no longer directs ANY conditional "
                "skill (the row is gone, not renamed), this scenario's witness "
                "is no longer plantable -- replace it with an edit against a "
                "row that still exists; do NOT rename the sentinel onto a row "
                "that is not there."
            )
        flavor_file.write_text(edited, encoding="utf-8")

    def freshly_project_and_accept(self) -> None:
        """Pillar-2 chaining: reuse the projection (AT-01/02's When) and the
        staleness check as the AT-03 baseline. Outcomes recorded, asserted in
        Then (never in Given) so RED stays an AssertionError in Then."""
        self._render = self._docgen()
        self._baseline_check = self._docgen("--check")

    def apply_drift(self, drift: ProjectionDrift) -> None:
        if drift is ProjectionDrift.REGISTRY_EDITED_WITHOUT_RERENDER:
            self.edit_registry_to_direct_crafter_elsewhere()
        else:
            self._hand_edit_skill_load_region()

    # --- When: drive the real docgen CLI -------------------------------------

    def project_working_copy(self) -> None:
        self._before = self._capture_universe()
        self._render = self._docgen()
        self._after = self._capture_universe()

    def run_staleness_check(self) -> None:
        self._before = self._capture_universe()
        self._check = self._docgen("--check")
        self._after = self._capture_universe()

    # --- Then: render outcomes ------------------------------------------------

    def assert_render_completed(self) -> None:
        assert self._render is not None and self._render.exit_code == 0, (
            "the projection re-render was REFUSED by the docgen entry point — "
            "the mode-region projection capability is missing.\n"
            f"{self._render.transcript if self._render else '(never ran)'}"
        )

    def assert_crafter_region_follows_registry(self) -> None:
        seam_answer = resolve_skill_load_set(
            CRAFTER_AGENT,
            WorkflowFlavor.ATDD_PURE.value,
            flavors_dir=self._flavors_dir,
        )
        region = (self._after or {})["crafter_spec.skill_load_region"]
        assert region.strip(), (
            "the crafter spec carries NO generated skill-load region after the "
            "re-render — the registry projection never landed in the asset"
        )
        missing = [skill for skill in seam_answer if skill not in region]
        assert not missing, (
            f"the generated skill-load region disagrees with the registry "
            f"resolution seam: seam answers {list(seam_answer)}, region is "
            f"missing {missing}.\nregion body:\n{region}"
        )
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe={
                "crafter_spec.skill_load_region",
                "crafter_spec.outside_region",
            },
            expected={
                "crafter_spec.skill_load_region": containing(EDITED_CRAFTER_SKILL),
                "crafter_spec.outside_region": unchanged(),
            },
        )

    def assert_inline_row_retired(self) -> None:
        text = (self._worktree / CRAFTER_SPEC_REL).read_text(encoding="utf-8")
        surviving = [
            line
            for line in text.splitlines()
            if RETIRED_INLINE_SKILL in line
            and INLINE_ROW_MARKER.lower() in line.lower()
        ]
        assert not surviving, (
            "the hand-written conditional-skill row still survives in the "
            "crafter spec (the registry was edited to a different skill, so "
            "any line still pairing the retired skill with its CONDITIONAL "
            f"marker is the un-retired inline copy): {surviving}"
        )

    def assert_crafter_outside_region_untouched(self) -> None:
        assert self._before is not None and self._after is not None
        assert (
            self._before["crafter_spec.outside_region"]
            == self._after["crafter_spec.outside_region"]
        ), (
            "the projection rewrote the crafter spec OUTSIDE its generated "
            "region — the bounded-change contract is broken"
        )

    def assert_deliver_region_carries_all_descriptors(self) -> None:
        region = (self._after or {})["deliver_guide.mode_descriptor_region"]
        assert region.strip(), (
            "the deliver guide carries NO generated mode-descriptor region "
            "after the re-render — the registry projection never landed"
        )
        absent = [
            DESCRIPTOR_SENTINEL_BY_FLAVOR[flavor]
            for flavor in SHIPPED_FLAVORS
            if DESCRIPTOR_SENTINEL_BY_FLAVOR[flavor] not in region
        ]
        assert not absent, (
            f"the mode-descriptor region does not carry the registry's "
            f"descriptor for every declared mode — missing {absent}.\n"
            f"region body:\n{region}"
        )
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe={
                "deliver_guide.mode_descriptor_region",
                "deliver_guide.outside_region",
            },
            expected={
                "deliver_guide.mode_descriptor_region": containing(
                    ATDD_DESCRIPTOR_SENTINEL
                ),
                "deliver_guide.outside_region": unchanged(),
            },
        )

    def assert_deliver_region_carries_phase_shape(self) -> None:
        """Registry read-through for `deliver_phase_shape`, witnessed against
        the value the WORKING REGISTRY actually declares.

        The sentinel technique this assertion used until the classic flavor was
        retired is no longer available: the sentinel had to live on a NON-default
        flavor, because the slice-05 Layer-C agreement leg requires the DEFAULT
        flavor's phase shape to stay runtime-canonical — with one shipped flavor,
        which IS the default, a planted sentinel and the AT-03 accepted baseline
        are mutually exclusive.

        So the witness reads the field from the registry file and asserts the
        rendered region agrees. This is DELIBERATELY weaker than a sentinel: a
        guide that hard-coded the canonical shape would also pass. What keeps the
        scenario honest is the descriptor sentinel asserted just above — it
        proves this same region is registry-rendered, and docgen renders both
        fields through the ONE `resolve_mode_descriptor` code path."""
        region = (self._after or {})["deliver_guide.mode_descriptor_region"]
        registry_text = (
            self._flavors_dir / f"{WorkflowFlavor.ATDD_PURE.value}.yaml"
        ).read_text(encoding="utf-8")
        declared = _PHASE_SHAPE_LINE_RE.search(registry_text)
        if declared is None:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                "WHAT: the working copy of nWave/flavors/atdd_pure.yaml "
                "declares no top-level `deliver_phase_shape:` line. "
                "WHY: this assertion reads the registry's OWN declared phase "
                "shape and checks the rendered deliver-guide region agrees -- "
                "deliberately not a sentinel, because atdd_pure is the only "
                "shipped (and therefore default) flavor, and a planted sentinel "
                "here would collide with the slice-05 Layer-C agreement leg. "
                "HOW: diff the working copy against the shipped "
                "nWave/flavors/atdd_pure.yaml. If the field was RENAMED there, "
                "update `_PHASE_SHAPE_LINE_RE` in composition_slice_02.py. If "
                "the field is GENUINELY gone from the schema, this witness has "
                "nothing left to read through -- replace the assertion with one "
                "against whatever field replaced it; do NOT keep reading a "
                "field the schema no longer carries."
            )
        shape = declared.group(0).split(":", 1)[1].strip().strip('"')
        assert shape in region, (
            "the mode-descriptor region does not carry the registry's "
            f"declared deliver phase shape '{shape}' — the rendered region "
            "and the registry file disagree on the field.\n"
            f"region body:\n{region}"
        )

    def assert_deliver_outside_region_untouched(self) -> None:
        assert self._before is not None and self._after is not None
        assert (
            self._before["deliver_guide.outside_region"]
            == self._after["deliver_guide.outside_region"]
        ), (
            "the projection rewrote the deliver guide OUTSIDE its generated "
            "region — the bounded-change contract is broken"
        )

    # --- Then: staleness-check outcomes ---------------------------------------

    def assert_refused_naming_crafter_spec(self) -> None:
        assert self._check is not None, "the staleness check never ran"
        output = self._check.stdout + self._check.stderr
        assert self._check.exit_code != 0 and CRAFTER_SPEC_REL.name in output, (
            "the staleness check did not refuse the drifted working copy by "
            f"naming the stale crafter spec ({CRAFTER_SPEC_REL.name}) — a "
            "drifted projection would be served stale.\n"
            f"{self._check.transcript}"
        )

    def assert_accepted_before_drift(self) -> None:
        assert self._baseline_check is not None and (
            self._baseline_check.exit_code == 0
        ), (
            "the freshly projected working copy was NOT accepted by the "
            "staleness check before the drift — the refusal above proves "
            "nothing.\n"
            f"{self._baseline_check.transcript if self._baseline_check else '(never ran)'}"
        )

    def assert_check_rewrites_nothing(self) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={},  # fail-closed: ANY change under the check is a violation
        )

    # --- internals --------------------------------------------------------------

    @property
    def _flavors_dir(self) -> Path:
        return self._worktree / FLAVORS_REL

    def _copy_shipped(self, rel: Path) -> None:
        source = REPO_ROOT / rel
        target = self._worktree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    def _stub_referenced_skills(self) -> None:
        spec_text = (self._worktree / CRAFTER_SPEC_REL).read_text(encoding="utf-8")
        frontmatter = spec_text.split("---", 2)[1]
        for ref in _FRONTMATTER_SKILL_RE.findall(frontmatter):
            stub = self._worktree / "nWave" / "skills" / ref / "SKILL.md"
            if stub.exists():
                continue
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text(
                f"---\nname: {ref}\ndescription: stub skill authored by the "
                f"slice-02 working-copy fixture\n---\n# {ref}\n",
                encoding="utf-8",
            )

    def _replace_descriptor(
        self,
        flavor: WorkflowFlavor,
        *,
        descriptor: str,
        phase_shape: str | None = None,
    ) -> None:
        """Replace-in-place (slice-04 `_upsert_skill_load_row` precedent):
        each registry field stays declared EXACTLY ONCE — the working copy
        remains a LEGAL registry the slice-05 Layer-B gate accepts. Every
        substitution is guarded subn==1 (fixture integrity, fail-loud)."""
        flavor_file = self._flavors_dir / f"{flavor.value}.yaml"
        text = flavor_file.read_text(encoding="utf-8")
        text = self._sub_exactly_once(
            _DESCRIPTOR_BLOCK_RE,
            f"descriptor: >\n  {descriptor}\n",
            text,
            flavor_file,
            "descriptor",
        )
        if phase_shape is not None:
            text = self._sub_exactly_once(
                _PHASE_SHAPE_LINE_RE,
                f'deliver_phase_shape: "{phase_shape}"',
                text,
                flavor_file,
                "deliver_phase_shape",
            )
        flavor_file.write_text(text, encoding="utf-8")

    @staticmethod
    def _sub_exactly_once(
        pattern: re.Pattern[str],
        replacement: str,
        text: str,
        flavor_file: Path,
        field: str,
    ) -> str:
        new_text, count = pattern.subn(replacement, text)
        if count != 1:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"WHAT: {flavor_file} must declare {field!r} exactly once but "
                f"the working copy has {count} replaceable declarations "
                f"(regex {pattern.pattern!r}). "
                "WHY: `_replace_descriptor` requires each registry field "
                "declared EXACTLY ONCE so the working copy stays the LEGAL "
                "single-key registry the slice-05 Layer-B completeness gate "
                "demands. "
                f"HOW: diff {flavor_file} against the shipped "
                f"nWave/flavors/{flavor_file.name}. If {field!r} was RENAMED "
                "there, update the pattern this helper is called with "
                "(_DESCRIPTOR_BLOCK_RE / _PHASE_SHAPE_LINE_RE) to the new name. "
                "If the field is GENUINELY gone from the schema, that field's "
                "registry-read-through witness is no longer plantable -- "
                "replace the calling scenario; do NOT rename the sentinel onto "
                "a field the schema no longer carries."
            )
        return new_text

    def _stub_declared_agents(self) -> None:
        """Every agent the working registry's `skill_load_set` directs gets a
        minimal spec stub (the `_stub_referenced_skills` pattern, applied to
        agents): the slice-05 Layer-B gate verifies agent existence under
        `--root`, and the slice-02 working copy must be a LEGAL registry-
        bearing tree end-to-end — fixture mechanics, never an oracle."""
        # Iterate what the working copy actually CARRIES (the shipped set the
        # `build_working_copy` loop above copied), never the enum: the enum
        # retains CLASSIC as a fixture-only identity, and stubbing agents for a
        # flavor file that was never copied fails on the file, not the property.
        for flavor in SHIPPED_FLAVORS:
            text = (self._flavors_dir / f"{flavor.value}.yaml").read_text(
                encoding="utf-8"
            )
            for agent_id in _SKILL_LOAD_AGENT_RE.findall(text):
                stub = self._worktree / "nWave" / "agents" / f"{agent_id}.md"
                if stub.exists():
                    continue
                stub.parent.mkdir(parents=True, exist_ok=True)
                stub.write_text(
                    f"---\nname: {agent_id}\ndescription: stub agent authored "
                    "by the slice-02 working-copy fixture\n---\n"
                    f"# {agent_id}\n",
                    encoding="utf-8",
                )

    def _hand_edit_skill_load_region(self) -> None:
        spec_path = self._worktree / CRAFTER_SPEC_REL
        text = spec_path.read_text(encoding="utf-8")
        pattern = _region_pattern(RegionId.SKILL_LOAD_SET)
        if pattern.search(text):
            text = pattern.sub(
                f"<!-- GENERATED:{RegionId.SKILL_LOAD_SET.value} START — "
                f"hand-edited -->\n{_HAND_EDIT_SENTINEL}\n"
                f"<!-- GENERATED:{RegionId.SKILL_LOAD_SET.value} END -->",
                text,
            )
        else:  # active-RED state: no region yet — plant a stale one
            text += (
                f"\n<!-- GENERATED:{RegionId.SKILL_LOAD_SET.value} START — "
                f"hand-planted -->\n{_HAND_EDIT_SENTINEL}\n"
                f"<!-- GENERATED:{RegionId.SKILL_LOAD_SET.value} END -->\n"
            )
        spec_path.write_text(text, encoding="utf-8")

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

    def _capture_universe(self) -> dict[str, str]:
        """Port-exposed observables only (Mandate 8): generated-region bodies,
        asset text outside the regions, registry texts. Never parser internals."""
        crafter = (self._worktree / CRAFTER_SPEC_REL).read_text(encoding="utf-8")
        deliver = (self._worktree / DELIVER_GUIDE_REL).read_text(encoding="utf-8")
        return {
            "crafter_spec.skill_load_region": _extract_region(
                crafter, RegionId.SKILL_LOAD_SET
            ),
            "crafter_spec.outside_region": _outside_region(
                crafter, RegionId.SKILL_LOAD_SET
            ),
            "deliver_guide.mode_descriptor_region": _extract_region(
                deliver, RegionId.MODE_DESCRIPTOR
            ),
            "deliver_guide.outside_region": _outside_region(
                deliver, RegionId.MODE_DESCRIPTOR
            ),
            "registry.atdd_pure": (
                self._flavors_dir / f"{WorkflowFlavor.ATDD_PURE.value}.yaml"
            ).read_text(encoding="utf-8"),
        }
