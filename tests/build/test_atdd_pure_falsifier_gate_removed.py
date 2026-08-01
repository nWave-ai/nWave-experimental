"""Tripwire -- the withdrawn atdd_pure pilot falsifier-gate stays withdrawn.

Mikado D24, unit 3 of 3 (`docs/mikado/2026-07-28-decisions-consolidated.md:63`).
Feature: `docs/feature/remove-atdd-pure-falsifier-gate/feature-delta.md`. The
falsifier-gate's own input telemetry path
(`nWave/telemetry/wave-time-token-telemetry/pilot/`) never had a writer in repo
history and its rollback target (classic mode) is retired, so the pilot it
falsifies can no longer be un-chosen. Removal covers: the standalone script, its
own unit test, the unconsumed `FalsifierGateTripped` event-shape dataclass plus
its `__all__` export, and every prose surface that arms or names the mechanism
(`## Wave: DESIGN / [REF] Component decomposition -- Decommission Surface
Inventory`, rows 1-8, plus two additional surfaces this scan itself found --
see below).

FALSIFIABILITY (DISTILL-owed proof, per `## Wave: DESIGN / [REF] Architecture &
Contract Tests`). This test is authored against the CURRENT, pre-removal tree,
where it MUST fail on all three checks below -- the RED observation is recorded
mechanically (`des verify-red-green --record-red`) before the crafter's removal
turns it GREEN in the same coupled commit. A tripwire only ever seen passing
never demonstrates its own discriminating power.

SCOPING -- two DISTINCT mechanisms both loosely describable as "falsifier-gate"
share this repo, and must not be confused:

1. THIS one -- the atdd_pure pilot health-halt valve (plan v3 Section 4.5),
   the subject of this removal. Named by the literal tokens in
   `_NARROW_LITERALS` below: the module name `atdd_pure_falsifier_gate`, the
   dataclass name `FalsifierGateTripped`/`FalsifierGateHealthy`, the
   Title-Case section-header phrase `Falsifier-Gate`, and two exact prose
   clauses unique to their own sentences.
2. The UNRELATED AT-completeness / PBT-taxonomy "falsifier-gate" (empirical
   prune/escalate of AT-completeness categories from telemetry; the PBT
   paradigm-match rule that blocks property-based testing on closed-world
   finite domains). Lives in `nw-at-completeness-check*`,
   `nw-property-based-testing`, `nw-test-optimization*`,
   `nw-acceptance-designer.md:179`, and is referenced by name (lowercase
   `falsifier-gate` / Sentence-case `Falsifier-gate`) in dozens of test
   docstrings across `tests/**` that justify an example-based (not PBT)
   treatment. A broad case-insensitive `falsifier[-_]gate` scan collides with
   every one of those -- confirmed empirically before authoring the literal
   set below (`grep -rniE "falsifier[-_]gate" nWave scripts src tests` during
   DISTILL surfaced 50+ hits, all belonging to mechanism 2). The literals here
   are deliberately narrow enough to name ONLY mechanism 1;
   `test_narrow_literals_do_not_collide_with_the_at_completeness_falsifier_gate`
   below is the mechanical proof of that narrowness, run against a real
   positive-control corpus (files confirmed, this session, to legitimately
   reference mechanism 2) -- not merely claimed in prose.

BONUS FINDINGS beyond the DESIGN inventory's 8 prose rows -- this scan's job is
to be the exhaustive mechanized census DESIGN's own hand-curated inventory
cannot guarantee to be (the KPI DISCUSS specified is itself a walk, not a
fixed row count). Two live surfaces the DESIGN inventory did not enumerate,
found by literal search during this DISTILL pass:

- `src/des/application/workflow_mode.py:191` -- `_parse_workflow_mode`'s
  docstring cites `scripts/automation/atdd_pure_falsifier_gate.py` by name as
  the writer of the `.nwave/config.yaml` shape it tolerates.
- `nWave/skills/nw-deliver/SKILL.md:45,255` -- two pointer sentences naming
  "Falsifier-Gate hook" / "Post-Commit Falsifier-Gate Hook" as a section that
  lives in `nw-deliver-atdd-pure-slice-gates`.

Both are real, both are caught by the same literal scan below, and both must
fall in the crafter's coupled removal commit alongside the 8 DESIGN-named
rows -- the scan does not stop at DESIGN's list, it supersedes it.

UNOBSERVABILITY COST (declared, not discovered later, per DESIGN). The scan is
literal-string, `.py`/`.md` only, no AST/regex-obscured-reference detection --
a fragment built via string concatenation or an occurrence in a `.yaml`/`.json`
file is NOT caught. Deliberate trade-off against the portability floor: stdlib
`pathlib` + string containment only, no `git`/`gh`/subprocess dependency.
"""

from __future__ import annotations

import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SELF_RELATIVE = Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix()

_SCRIPT_PATH = "scripts/automation/atdd_pure_falsifier_gate.py"
_SCRIPT_TEST_PATH = "tests/scripts/automation/test_atdd_pure_falsifier_gate.py"

_DOMAIN_MODULE = "des.domain.atdd_pure_phases"
_DATACLASS_NAME = "FalsifierGateTripped"

# Roots + extensions DESIGN specified for the tree-wide census. docs/** is
# deliberately excluded -- ADR-027/ADR-028/docs/proposals/* are historical
# record and must-not-touch (feature-delta row 12); docs/reference/** is an
# auto-generated mirror of nWave/** and would only double-count.
_WALK_ROOTS = ("nWave", "scripts", "src", "tests")
_WALK_EXTENSIONS = (".py", ".md")

# Literal tokens naming ONLY mechanism 1 (the withdrawn pilot valve). Every
# entry was verified, this session, to have ZERO hits inside the files that
# legitimately reference mechanism 2 (see the module docstring + the
# narrowness-proof test below) -- narrow by measurement, not by assumption.
_NARROW_LITERALS: tuple[str, ...] = (
    "atdd_pure_falsifier_gate",  # module/script name (rows 1,2,5,6 + both bonus finds)
    "FalsifierGateTripped",  # dataclass name (rows 3,4 + the script + its test)
    "FalsifierGateHealthy",  # companion healthy-path event name (rows 5,6 bodies)
    "Falsifier-Gate",  # Title-Case section-header phrase (rows 5,6 headers + nw-deliver/SKILL.md:45,255)
    "the post-commit falsifier-gate hook",  # row 7 -- exact frontmatter clause
    "invalidates falsifier-gate",  # row 8 -- exact distill.md:71 clause
)

# Positive-control corpus for the narrowness proof: files confirmed this
# session to legitimately reference the UNRELATED AT-completeness/PBT
# "falsifier-gate" and that must therefore survive this removal untouched.
# Each must (a) exist and (b) contain falsifier-gate-shaped text (case
# insensitive) -- proving the corpus is real, not a vacuous empty check.
_OTHER_MECHANISM_FILES: tuple[str, ...] = (
    "nWave/agents/nw-acceptance-designer.md",
    "nWave/skills/nw-at-completeness-check/SKILL.md",
    "nWave/skills/nw-at-completeness-check-taxonomy-lifecycle/SKILL.md",
    "nWave/skills/nw-property-based-testing/SKILL.md",
    "nWave/skills/nw-test-optimization/SKILL.md",
    "nWave/skills/nw-test-optimization-paradigm-match/SKILL.md",
    "nWave/skills/nw-test-optimization-scope-selection/SKILL.md",
    "tests/des/unit/commit_author_identity/test_identity_core_properties.py",
)


def _scanned_files() -> list[Path]:
    """Every `.py`/`.md` file under the DESIGN-fixed walk roots, self excluded."""
    files: list[Path] = []
    for root in _WALK_ROOTS:
        base = PROJECT_ROOT / root
        if not base.exists():
            continue
        for ext in _WALK_EXTENSIONS:
            files.extend(sorted(base.rglob(f"*{ext}")))
    return [
        f for f in files if f.relative_to(PROJECT_ROOT).as_posix() != _SELF_RELATIVE
    ]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def test_script_and_its_test_are_gone() -> None:
    """The falsifier-gate script and its own unit test must not exist."""
    survivors = [
        rel
        for rel in (_SCRIPT_PATH, _SCRIPT_TEST_PATH)
        if (PROJECT_ROOT / rel).exists()
    ]
    assert not survivors, (
        "WHAT: the withdrawn atdd_pure falsifier-gate script and/or its own "
        "unit test still exist on disk.\n"
        "WHY: Mikado D24 unit 3 withdraws this mechanism -- its input "
        "telemetry path never had a writer in repo history and its rollback "
        "target (classic mode) is retired, so armed-only-by-prose code left "
        "standing teaches a false safety net.\n"
        "HOW: delete both files in the same coupled commit as the prose "
        "reduction and the dataclass removal (feature-delta rows 1-2).\n"
        f"    still present: {survivors}"
    )


def test_falsifier_gate_tripped_dataclass_is_gone() -> None:
    """`FalsifierGateTripped` must be neither importable nor exported."""
    module = importlib.import_module(_DOMAIN_MODULE)
    importlib.reload(module)
    assert getattr(module, _DATACLASS_NAME, None) is None, (
        f"WHAT: `{_DATACLASS_NAME}` is still importable from `{_DOMAIN_MODULE}`.\n"
        "WHY: DISCUSS's GOES decision (feature-delta rows 3-4) found all "
        "three named consumers in the dataclass's own docstring fictional -- "
        "the script writes a raw dict instead of importing it, the DES "
        "sequencer wiring was never built, and the telemetry aggregator was "
        "never built. A declared-but-never-consumed event shape is the same "
        "defect class this feature exists to remove elsewhere.\n"
        f"HOW: delete the `{_DATACLASS_NAME}` dataclass definition from "
        f"`{_DOMAIN_MODULE.replace('.', '/')}.py`."
    )
    assert _DATACLASS_NAME not in module.__all__, (
        f"WHAT: `{_DATACLASS_NAME}` is still present in "
        f"`{_DOMAIN_MODULE}.__all__`.\n"
        "WHY/HOW: see the sibling assertion in this test -- the export line "
        "must fall together with the class definition, in the same edit."
    )


def test_no_surface_names_the_falsifier_gate() -> None:
    """Zero tree-wide literal hits for the gate's names (the KPI measure).

    Mechanizes DISCUSS's stated KPI measure ("`grep -ril
    atdd_pure_falsifier_gate nWave/` returning empty") in pure Python rather
    than shelling out to `grep` -- portability floor: runs on Python alone,
    no `git`/`gh` dependency, degrades to a hard `AssertionError` naming the
    offending file/line/literal on failure, never silent.
    """
    offenders: list[str] = []
    for path in _scanned_files():
        text = _read_text(path)
        if not text:
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for literal in _NARROW_LITERALS:
                if literal in line:
                    offenders.append(f"{rel}:{lineno} — {literal!r}")

    assert not offenders, (
        "WHAT: a shipped surface still names the withdrawn atdd_pure "
        "falsifier-gate.\n"
        "WHY: the mechanism is withdrawn (Mikado D24 unit 3) -- a surviving "
        "reference teaches a contributor that a hook exists which cannot "
        "fire (its telemetry path never had a writer; its rollback target, "
        "classic mode, is retired).\n"
        "HOW: reduce/delete the offending surface per feature-delta "
        "`## Wave: DESIGN / [REF] Component decomposition` (rows 5-8 for the "
        "named prose sections; any other hit is a real surface DESIGN's "
        "hand-curated inventory missed and must be fixed on sight, per the "
        "zero-defects standing rule -- never catalogued for later).\n"
        "--- offending sites ---\n" + "\n".join(offenders)
    )


def test_narrow_literals_do_not_collide_with_the_at_completeness_falsifier_gate() -> (
    None
):
    """Proves the literal set is narrow -- never fires on the OTHER mechanism.

    Two unrelated mechanisms both loosely describable as "falsifier-gate"
    share this repo (see module docstring). A blanket `falsifier[-_]gate`
    scan collides with dozens of files belonging to the UNRELATED
    AT-completeness/PBT-taxonomy mechanism, which is confirmed OUT OF SCOPE
    for this removal and must survive untouched. This test is the mechanical
    proof, not a prose claim: it (a) confirms each file in the positive-control
    corpus is real and does legitimately mention falsifier-gate-shaped text
    (guards against a vacuous, always-passing corpus), then (b) asserts NONE
    of this test's own `_NARROW_LITERALS` appear in any of them.
    """
    missing_corpus_files = [
        rel for rel in _OTHER_MECHANISM_FILES if not (PROJECT_ROOT / rel).is_file()
    ]
    assert not missing_corpus_files, (
        "WHAT: the narrowness-proof's positive-control corpus names a file "
        "that does not exist.\n"
        "WHY: a missing corpus file can silently turn this proof vacuous.\n"
        f"HOW: fix the path in _OTHER_MECHANISM_FILES.\n    {missing_corpus_files}"
    )

    not_actually_mentioning_it = [
        rel
        for rel in _OTHER_MECHANISM_FILES
        if "falsifier" not in _read_text(PROJECT_ROOT / rel).lower()
    ]
    assert not not_actually_mentioning_it, (
        "WHAT: a positive-control file no longer mentions 'falsifier' at "
        "all.\n"
        "WHY: this corpus exists to prove the narrow literals do NOT "
        "collide with real other-mechanism text -- a corpus entry that no "
        "longer mentions the concept proves nothing and must be replaced.\n"
        f"HOW: update _OTHER_MECHANISM_FILES.\n    {not_actually_mentioning_it}"
    )

    collisions: list[str] = []
    for rel in _OTHER_MECHANISM_FILES:
        text = _read_text(PROJECT_ROOT / rel)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for literal in _NARROW_LITERALS:
                if literal in line:
                    collisions.append(f"{rel}:{lineno} — {literal!r}")

    assert not collisions, (
        "WHAT: a literal in _NARROW_LITERALS matches text inside a file "
        "that belongs to the UNRELATED AT-completeness/PBT-taxonomy "
        "falsifier-gate mechanism.\n"
        "WHY: this removal must not touch that mechanism (confirmed "
        "distinct, DISCUSS wave-decisions.md 'Facts verified' table) -- a "
        "colliding literal would make `test_no_surface_names_the_"
        "falsifier_gate` fail forever on innocent, correct files.\n"
        "HOW: narrow the offending literal in _NARROW_LITERALS (add "
        "surrounding context, e.g. an exact multi-word phrase) until it "
        "names only mechanism 1.\n"
        "--- collisions ---\n" + "\n".join(collisions)
    )
