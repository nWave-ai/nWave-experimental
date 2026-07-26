"""Composition root for mode-registry-single-locus slice-03 (the SSOT-via-Types-Services-DSL mandate).

Pillar 3 (App as in production): the SUT is the REAL docgen CLI
(`scripts/docgen.py`), driven as a Layer-3 subprocess — the slice-02 contract
surface (`--root <working-copy>` + `--output-dir` + `--check`) REUSED, no
second mechanism. The working copy is built from BYTE-COPIES of the real
framework catalog + ALL shipped command guides (plus the flavor registry and
the empty asset dirs docgen's scan stage requires), so the full real entry
(argparse -> scan -> extract -> enrich -> render -> projection / check) runs
exactly as in production, never mutating the live repository.

Driving-Port-Only Boundary attestation (S2 gate): ZERO production imports in
this module. docgen is driven by subprocess only; the EXPECTED-side oracle is
an independent YAML parse of the working catalog and guide frontmatter — the
exact comparison the retired hand-sync test (`test_command_frontmatter.py`)
performed, which is what makes AT-03 the deletion-safety pin. No
`des.domain.*` / `des.application.*` / `des.adapters.*` import.

Mechanism pin (DISTILL decision, slice-03): GENERATED HTML-comment markers
cannot live inside YAML frontmatter, so the projection REWRITES the
`description:` / `argument-hint:` VALUES of every catalog-declared command
guide from the catalog; `--check` compares YAML-PARSED frontmatter values to
catalog values and NAMES each stale guide. Parsed-value equality (not raw
bytes) is the contract — the same equality the retired test asserted and the
same value the host's frontmatter parse yields (port-exposed observable).

Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared slice-03 seam —
the catalog->frontmatter projection reachable from the real docgen entry
(D-project) — is driven through the real CLI entry point in every scenario
and asserted by observable effect (bounded guide delta / refusal verdict /
idempotent re-projection + full-catalog agreement sweep).

DISTILL-authored ACTIVE-RED (ADR-025 / ADR-GV-001 D6): NO production scaffold
is needed — the driving entry (`scripts/docgen.py`) and its `--root` surface
already exist (slice-02 GREEN). The missing capability (frontmatter
projection) surfaces as guides that never receive the catalog's sentinel
values and as a staleness check that vacuously accepts a desynced copy —
every scenario RUNS and FAILS with `MISSING_FUNCTIONALITY` (AssertionError in
a Then), none is skipped, and no import/setup error masks the RED.

Mandate 8 (layer-3 FS acceptance): every mutating step asserts via
`assert_state_delta(before, after, universe, expected)` over port-exposed
observables only (parsed frontmatter values, guide bodies, an
other-guides fingerprint, the catalog text). The staleness check and the
second projection assert the empty-expected preservation contract:
anything in the universe that changes is a violation (fail-closed).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from nwave_ai.state_delta import assert_state_delta, containing

from scripts import docgen
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_03 import (
    DISTILL_HINT_ANCHOR,
    DISTILL_HINT_SENTINEL,
    EXECUTE_DESCRIPTION_ANCHOR,
    EXECUTE_DESCRIPTION_SENTINEL,
    HAND_EDIT_SENTINEL,
    CommandGuide,
    GuideDesync,
)


REPO_ROOT = Path(__file__).resolve().parents[5]

COMMANDS_REL = Path("nWave") / "tasks" / "nw"
CATALOG_REL = Path("nWave") / "framework-catalog.yaml"
FLAVORS_REL = Path("nWave") / "flavors"


@dataclass(frozen=True)
class _CliOutcome:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def transcript(self) -> str:
        return f"exit={self.exit_code}\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """(parsed frontmatter mapping, body after the closing marker).

    Same frontmatter grammar the retired hand-sync test used: a leading
    `---\\n` block closed by `\\n---\\n`, parsed with yaml.safe_load.
    """
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}, text
    end = text.index("\n---\n", 4)
    parsed = yaml.safe_load(text[4:end]) or {}
    return parsed, text[end + len("\n---\n") :]


class CatalogFrontmatterProjectionComposition:
    """Single source of truth for all slice-03 step-method business logic.

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

    # --- Given: working copy + catalog edits ---------------------------------

    def build_working_copy(self) -> None:
        """Byte-copy the catalog + ALL shipped command guides + the flavor
        registry; create the empty asset dirs docgen's scan stage requires."""
        self._copy_shipped(CATALOG_REL)
        for guide in sorted((REPO_ROOT / COMMANDS_REL).glob("*.md")):
            self._copy_shipped(COMMANDS_REL / guide.name)
        for flavor_file in sorted((REPO_ROOT / FLAVORS_REL).glob("*.yaml")):
            self._copy_shipped(FLAVORS_REL / flavor_file.name)
        for empty_dir in ("agents", "skills", "templates"):
            (self._worktree / "nWave" / empty_dir).mkdir(parents=True, exist_ok=True)

    def edit_catalog_description_for_execute(self) -> None:
        """The wiring-witness edit: the working catalog now describes the
        execute command with a sentinel that appears nowhere in the shipped
        assets (the first 2026-06-10 hotfix desync victim)."""
        self._replace_in_file(
            self._worktree / CATALOG_REL,
            EXECUTE_DESCRIPTION_ANCHOR,
            EXECUTE_DESCRIPTION_SENTINEL,
        )

    def edit_catalog_hint_for_distill(self) -> None:
        """The second hotfix victim: the working catalog re-hints distill."""
        self._replace_in_file(
            self._worktree / CATALOG_REL,
            DISTILL_HINT_ANCHOR,
            DISTILL_HINT_SENTINEL,
        )

    def freshly_project_and_accept(self) -> None:
        """Pillar-2 chaining: reuse the projection (AT-01's When) and the
        staleness check as the AT-02/AT-03 baseline. Outcomes recorded,
        asserted in Then (never in Given) so RED stays an AssertionError."""
        self._render = self._docgen()
        self._baseline_check = self._docgen("--check")

    def apply_desync(self, desync: GuideDesync) -> None:
        if desync is GuideDesync.CATALOG_EDITED_WITHOUT_REPROJECTION:
            self.edit_catalog_description_for_execute()
        else:
            self._hand_edit_execute_guide_description()

    # --- When: drive the real docgen CLI -------------------------------------

    def project_command_guides(self) -> None:
        self._before = self._capture_universe()
        self._render = self._docgen()
        self._after = self._capture_universe()

    def run_staleness_check(self) -> None:
        self._before = self._capture_universe()
        self._check = self._docgen("--check")
        self._after = self._capture_universe()

    # --- Then: projection outcomes --------------------------------------------

    def assert_projection_completed(self) -> None:
        assert self._render is not None and self._render.exit_code == 0, (
            "the catalog projection was REFUSED by the docgen entry point — "
            "the command-frontmatter projection capability is missing.\n"
            f"{self._render.transcript if self._render else '(never ran)'}"
        )

    def assert_execute_description_follows_catalog(self) -> None:
        catalog_value = self._catalog_field(CommandGuide.EXECUTE, "description")
        guide_value = self._guide_field(CommandGuide.EXECUTE, "description")
        assert EXECUTE_DESCRIPTION_SENTINEL in guide_value, (
            "the execute guide's description never received the edited "
            "catalog's sentinel — the catalog->frontmatter projection did "
            f"not land in the guide.\nguide description: {guide_value!r}"
        )
        assert guide_value == catalog_value, (
            "the execute guide's description is NOT exactly what the edited "
            "catalog declares (parsed-value equality, the retired hand-sync "
            f"contract's own comparison).\ncatalog: {catalog_value!r}\n"
            f"guide:   {guide_value!r}"
        )

    def assert_distill_hint_follows_catalog(self) -> None:
        catalog_value = self._catalog_field(CommandGuide.DISTILL, "argument_hint")
        guide_value = self._guide_field(CommandGuide.DISTILL, "argument-hint")
        assert DISTILL_HINT_SENTINEL in guide_value, (
            "the distill guide's argument hint never received the edited "
            "catalog's sentinel — the catalog->frontmatter projection did "
            f"not land in the guide.\nguide argument hint: {guide_value!r}"
        )
        assert guide_value == catalog_value, (
            "the distill guide's argument hint is NOT exactly what the "
            "edited catalog declares (parsed-value equality).\n"
            f"catalog: {catalog_value!r}\nguide:   {guide_value!r}"
        )

    def assert_bounded_change_only(self) -> None:
        """Fail-closed: ONLY the two edited fields change — guide bodies,
        the untouched fields, every other guide, and the catalog itself
        (the projection writes guides, never its own source) are preserved."""
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={
                "execute_guide.description": containing(EXECUTE_DESCRIPTION_SENTINEL),
                "distill_guide.argument_hint": containing(DISTILL_HINT_SENTINEL),
            },
        )

    # --- Then: staleness-check outcomes ----------------------------------------

    def assert_refused_naming_execute_guide(self) -> None:
        assert self._check is not None, "the staleness check never ran"
        output = self._check.stdout + self._check.stderr
        stale_name = CommandGuide.EXECUTE.filename
        assert self._check.exit_code != 0 and stale_name in output, (
            "the staleness check did not refuse the desynced command guides "
            f"by naming the stale guide ({stale_name}) — the 2026-06-10 "
            "hotfix desync class would be served stale again.\n"
            f"{self._check.transcript}"
        )

    def assert_accepted_before_desync(self) -> None:
        assert self._baseline_check is not None and (
            self._baseline_check.exit_code == 0
        ), (
            "the freshly projected command guides were NOT accepted by the "
            "staleness check before the desync — the refusal above proves "
            "nothing.\n"
            f"{self._baseline_check.transcript if self._baseline_check else '(never ran)'}"
        )

    def assert_check_left_guides_untouched(self) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={},  # fail-closed: ANY change under the check is a violation
        )

    # --- Then: byte-match degradation pin (AT-03) -------------------------------

    def assert_fresh_projection_was_accepted(self) -> None:
        assert self._baseline_check is not None and (
            self._baseline_check.exit_code == 0
        ), (
            "the freshly projected command guides were NOT accepted by the "
            "staleness check — acceptance-implies-agreement cannot be "
            "pinned.\n"
            f"{self._baseline_check.transcript if self._baseline_check else '(never ran)'}"
        )

    def assert_every_declared_guide_agrees_with_catalog(self) -> None:
        """The retired hand-sync test's own sweep, as an independent oracle:
        every catalog-declared command with a guide file agrees on
        description and argument hint (parsed-value equality). With this
        holding on a check-ACCEPTED state, `test_command_frontmatter.py`
        is safely deletable at GREEN."""
        mismatches: list[str] = []
        for name, meta in self._catalog_commands().items():
            guide_path = self._worktree / COMMANDS_REL / f"{name.replace('_', '-')}.md"
            if not guide_path.exists():  # retired-test semantics: update/workshopper
                continue
            frontmatter, _ = _split_frontmatter(guide_path.read_text(encoding="utf-8"))
            if frontmatter.get("description", "") != meta.get("description", ""):
                mismatches.append(f"{guide_path.name}: description disagrees")
            if "argument_hint" in meta and (
                frontmatter.get("argument-hint", "") != meta["argument_hint"]
            ):
                mismatches.append(f"{guide_path.name}: argument hint disagrees")
        assert not mismatches, (
            "command guides the catalog declares DISAGREE with the catalog "
            "on a state the staleness check accepted — acceptance does not "
            "imply agreement, so the retired hand-sync contract is NOT "
            "subsumed and deleting it would lose coverage:\n  "
            + "\n  ".join(mismatches)
        )

    def assert_second_projection_changed_nothing(self) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={},  # idempotency: an agreeing copy is re-projected to itself
        )

    # --- internals --------------------------------------------------------------

    def _copy_shipped(self, rel: Path) -> None:
        source = REPO_ROOT / rel
        target = self._worktree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    def _replace_in_file(self, path: Path, anchor: str, replacement: str) -> None:
        original = path.read_text(encoding="utf-8")
        edited = original.replace(anchor, replacement)
        if edited == original:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"WHAT: {path} no longer carries the anchor {anchor!r} -- zero "
                "occurrences to replace. "
                "WHY: this is a wiring-witness edit (hand-edit the working copy, "
                "re-render, assert the projection disagrees with the stale "
                "hand-edit) -- the caller needs this exact substring present "
                "and unique before it can plant its sentinel. "
                f"HOW: diff {path} against its shipped source "
                "(nWave/framework-catalog.yaml or nWave/tasks/nw/execute.md, "
                "depending on which caller triggered this). If the wording was "
                "RENAMED there, update the matching *_ANCHOR constant in "
                "domain_types_slice_03.py. If the field the anchor names is "
                "GENUINELY gone from the shipped asset, this witness has "
                "nothing left to hand-edit -- replace the calling scenario with "
                "one targeting a field that still exists; do NOT rename the "
                "anchor onto unrelated text."
            )
        path.write_text(edited, encoding="utf-8")

    def _hand_edit_execute_guide_description(self) -> None:
        self._replace_in_file(
            self._worktree / COMMANDS_REL / CommandGuide.EXECUTE.filename,
            EXECUTE_DESCRIPTION_ANCHOR,
            HAND_EDIT_SENTINEL,
        )

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

    def _catalog_commands(self) -> dict:
        catalog = yaml.safe_load(
            (self._worktree / CATALOG_REL).read_text(encoding="utf-8")
        )
        return catalog.get("commands", {})

    def _catalog_field(self, guide: CommandGuide, field: str) -> str:
        return str(self._catalog_commands()[guide.value].get(field, ""))

    def _guide_field(self, guide: CommandGuide, field: str) -> str:
        frontmatter, _ = _split_frontmatter(
            (self._worktree / COMMANDS_REL / guide.filename).read_text(encoding="utf-8")
        )
        return str(frontmatter.get(field, ""))

    def _capture_universe(self) -> dict[str, str]:
        """Port-exposed observables only (Mandate 8): YAML-parsed frontmatter
        values (what the host's parse yields — quoting-style normalization
        tolerated by design), guide bodies, an other-guides fingerprint, the
        catalog text. Never parser internals."""
        universe: dict[str, str] = {
            "catalog.text": (self._worktree / CATALOG_REL).read_text(encoding="utf-8")
        }
        fingerprints: list[str] = []
        probed = {guide.filename for guide in CommandGuide}
        for guide_path in sorted((self._worktree / COMMANDS_REL).glob("*.md")):
            frontmatter, body = _split_frontmatter(
                guide_path.read_text(encoding="utf-8")
            )
            description = str(frontmatter.get("description", ""))
            hint = str(frontmatter.get("argument-hint", ""))
            if guide_path.name in probed:
                stem = guide_path.stem
                universe[f"{stem}_guide.description"] = description
                universe[f"{stem}_guide.argument_hint"] = hint
                universe[f"{stem}_guide.body"] = body
            else:
                body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
                fingerprints.append(
                    f"{guide_path.name} description={description!r} "
                    f"argument_hint={hint!r} body_sha={body_sha}"
                )
        universe["other_guides.fingerprint"] = "\n".join(fingerprints)
        return universe
