"""The K4 paired-quality rubric, canonical and single-sourced.

Until this module existed, the scoring dimensions lived in a checked-in essay
-- `docs/analysis/2026-08-06-k4-lane-c-output-contract.md` -- that no code ever
read. Every campaign re-typed the dimensions by hand into a throwaway
`/tmp/*-review-prompt.md` file, and `blind_review.py` independently hardcoded
just the KEY SET to validate verdict shape. Two campaigns could drift from the
doc, from each other, and from `blind_review.py`'s own idea of how many
criteria exist, and nothing would notice.

This module is the one place the criteria TEXT now lives. `blind_review.py`
imports `CRITERIA_KEYS` from here instead of hardcoding a range; a future
reviewer-prompt generator should render `CRITERIA` instead of hand-copying the
table from the doc; and `tests/scripts/analysis/test_quality_rubric_1a_coverage.py`
is the standing check that this list still answers to the ratified quality
definition, not just to its own inertia.

## Reviewer-facing surface is `dimension` and `question` ONLY

Everything a reviewer prompt renders comes from `Criterion.dimension` and
`Criterion.question`. Both must stay strictly source-blind AND
shape-blind -- no nWave/ADR vocabulary, no mention of Section 1a, of
`DELEGATED_1A`, of internal artefact names. `Criterion.section_1a` and
`Criterion.notes` are code metadata: read by this module's own tests and by a
human auditing the mapping, never interpolated into anything a reviewer sees.
`leaked_reviewer_vocabulary()` is the standing check for that boundary --
found violating it once already (2026-08-18 review, commit 46009810d:
criterion `architecture`'s question named "Section 1a item 10" outright, and
`integration_and_e2e_coverage`'s named `DELEGATED_1A` by its Python
identifier), which is why the check exists as code and not as a habit.

## Equal weight by default

Each Section 1a item is cited by at most one scored criterion. Citing an item
twice does not describe it more thoroughly -- it doubles its contribution to
`total` relative to every singly-cited item, which is weight inflation
smuggled in as detail. `citation_counts()` is the standing check
(`test_every_section_1a_item_is_cited_by_at_most_one_criterion`). Found
violating it once already (2026-08-18 review): item 4 (acceptance tests
decoupled from implementation) was cited by two criteria that asked the same
underlying question from two angles -- merged into one below
(`tests_as_decoupled_specification`). Item 13 (defect escape/rework,
refactorability, maintainability) was cited by both `craftsmanship` and
`living_documentation`; `living_documentation` is now unanchored (still a
useful dimension, just not a Section 1a proxy) so `craftsmanship` alone
carries the citation.

Should a future item genuinely need more than one criterion to be judged at
all -- not merely to be judged more thoroughly -- that is a deliberate
decision, not an accident, and belongs recorded here by name with the reason,
not left for a reader to notice as an unexplained doubled weight.

## Why 17 criteria, not 12

`docs/product/architecture/ADR-SSOT-002-canonical-delivery-model.md` Section 1a
is the ratified, single-citable quality definition -- 13 enumerated items, each
"independently observable", ratified 2026-08-17/18 to end exactly the kind of
drift this module now guards against. The original 12-criterion rubric predates
that consolidation and was built from a different, uncited nine-dimension list;
diffed against Section 1a it left five items with NO rubric criterion at all:
semantic PBT (item 5), algebra-driven design (6), residuality (7),
certainty-by-construction (8), and no-DRY/SSOT-violation (9). The criteria
closing that gap are observable properties of the delivered code and tests,
not of the author's process: algebra-driven design, in particular, is scored
as totality/composability/law-visibility/no-representation-leakage in the
code that shipped, never as "was a design note written before the code" --
squashed delivery diffs (`DELIVERY.patch` against the workspace's own HEAD)
carry no reliable authorship order, and rewarding a note that happens to
exist would bias the score toward documentation habits rather than design
quality.

`integration_and_e2e_coverage` covers the judgable half of item 11
(integration/E2E test presence); item 11's mutation-testing clause is not
judgable from a sealed delivery packet at all (nightly, whole-repo, not part
of any single delivery's diff) and is listed under `DELEGATED_1A` instead.

## What stays delegated, and why

A source-blind reviewer reads a diff and never executes anything
(`blind_review.py`'s own docstring: the reviewer "cannot recover the arm"; the
sealed-bundle prompt: "Do not execute tests"). Some Section 1a items name a
FACT no static read can establish on its own -- and a `DELEGATED_1A` entry is
only honest if it names an instrument that actually runs somewhere in this
repo's K4 pipeline, not merely one that could in principle be built:

* item 1 (accepted outcome): `scripts/analysis/k4/run_acceptance.py`'s
  `examine()` is the real instrument -- it runs the acceptance suite against a
  disposable snapshot of the delivery and is what every K4 campaign actually
  calls. Criterion `verification_residue` scores whatever TRACE of that
  execution the delivery left behind, the nearest a blind reader gets.
* item 10 (no architectural drift) and item 13 (baseline-relative defect
  escape/rework/refactorability/maintainability): no module under
  `scripts/analysis/k4/` runs a DESIGN-authority comparison or tracks
  `defects.md`/`techdebt.md`/a baseline suite per K4 run. Naming
  `nw-solution-architect-reviewer` or those files as "the instrument" here
  would describe an instrument that does not exist inside this pipeline, so
  both are marked `NOT MEASURED in K4 -- INDETERMINATE for this item`
  instead: honest about the gap rather than decorated over it.
* item 12 (Examiner PASS + finalize): the verdict lives in the examine
  ledger and the `nw-finalize` commit, not in the delivery diff itself.
  Criteria `review_residue` and `filesystem_hygiene` score the residue a real
  pass leaves behind.

`DELEGATED_1A` names the instrument for each (or the honest absence of one),
so the coverage test can tell "intentionally out of this instrument's reach"
from "forgotten". A criterion above may still cite a delegated item as a
partial proxy -- delegation and citation are not exclusive.

Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Criterion:
    """One 0-2-scored dimension.

    `dimension` and `question` are the ONLY reviewer-facing fields -- see the
    module docstring, "Reviewer-facing surface is `dimension` and `question`
    ONLY".

    `section_1a` names which Section 1a items this criterion is evidence
    toward; code metadata, never rendered. Empty when the dimension predates
    Section 1a and answers to no single item -- kept for delivery legibility,
    not for quality non-inferiority.

    `notes` is free-text developer commentary (why this wording, what it is
    a proxy for, what it deliberately does not judge) -- also code metadata,
    also never rendered.
    """

    key: str
    dimension: str
    question: str
    section_1a: tuple[int, ...] = ()
    notes: str = ""


CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "1",
        "problem_understanding",
        "Can a reader state what problem this solves, and which cases were "
        "considered and rejected, without asking the author?",
    ),
    Criterion(
        "2",
        "architecture",
        "Are the boundaries and responsibilities discoverable, and is the "
        "reason for them recoverable -- not merely the shape?",
        (10,),
        notes=(
            "Section 1a item 10 proxy only: drift is relative to a DESIGN "
            "decision this reviewer cannot see; this scores internal "
            "coherence, not the DESIGN comparison item 10 actually asks for."
        ),
    ),
    Criterion(
        "3",
        "decisions_and_evolution",
        "For at least one non-obvious choice, can a reader recover the "
        "alternative that was rejected and why?",
    ),
    Criterion(
        "4",
        "tests_as_decoupled_specification",
        "Do the tests state behaviour in terms of commands, contracts and "
        "outcomes a caller would recognise, rather than internal classes, "
        "call order or persistence representation -- such that a "
        "different, correct implementation of the same behaviour would not "
        "require the tests to change?",
        (4,),
        notes=(
            "Merged from two criteria (tests_as_specification, "
            "test_implementation_coupling) that both cited item 4 -- see "
            "'Equal weight by default'."
        ),
    ),
    Criterion(
        "5",
        "craftsmanship",
        "Are naming, decomposition and error handling consistent within "
        "the delivery's own paradigm? Score the paradigm it chose; do not "
        "require OOP or FP.",
        (13,),
    ),
    Criterion(
        "6",
        "reuse_and_conformance",
        "Where existing code could have been extended, was it -- and "
        "where it was not, is the reason visible?",
        (3,),
    ),
    Criterion(
        "7",
        "living_documentation",
        "Does the documentation describe what the code now does, and "
        "would a change to the code make it visibly wrong?",
        notes=(
            "Unanchored, not because it lacks value, but because item 13 is "
            "already carried by `craftsmanship` -- see 'Equal weight by "
            "default'."
        ),
    ),
    Criterion(
        "8",
        "refactoring",
        "Is there evidence of behaviour-preserving improvement, "
        "distinguishable from feature work?",
        (2,),
    ),
    Criterion(
        "9",
        "review_residue",
        "Can a reader find that someone other than the author examined "
        "this, and what they objected to?",
        (12,),
    ),
    Criterion(
        "10",
        "verification_residue",
        "Can a reader determine what was actually executed and what it "
        "observed -- not merely that something passed?",
        (1,),
    ),
    Criterion(
        "11",
        "filesystem_hygiene",
        "Are the delivered files the ones the work needed, with no "
        "abandoned scaffolding?",
    ),
    Criterion(
        "12",
        "semantic_property_based_testing",
        "Do the delivery's property-based tests map generators to "
        "observations across laws, invariants, transitions and the "
        "failure space -- not just one happy-path example dressed as a "
        "property?",
        (5,),
    ),
    Criterion(
        "13",
        "algebra_driven_design",
        "Are the delivery's public operations total over their declared "
        "inputs and composable with each other; are any invariants or laws "
        "they rely on visible as executable tests or as types rather than "
        "only prose; and does the public boundary avoid leaking internal "
        "representation details to its callers?",
        (6,),
        notes=(
            "Reformulated 2026-08-18: the prior wording asked whether an "
            "observation/law was 'named before the implementation', "
            "unjudgeable from a squashed diff with no reliable authorship "
            "order and biased toward deliveries that happen to write a "
            "design note. This version scores properties observable "
            "directly in the shipped code and tests."
        ),
    ),
    Criterion(
        "14",
        "residuality_no_duplication",
        "Where the delivery includes more than one test layer (unit or "
        "acceptance, property-based, integration, end-to-end), does each "
        "layer assert something distinct -- a different input class, "
        "invariant or interaction -- rather than re-asserting the same "
        "scenario at another level?",
        (7,),
        notes="Score 0 if only one layer exists or layers duplicate each other.",
    ),
    Criterion(
        "15",
        "certainty_by_construction",
        "Where the code enforces a data invariant, is it enforced by "
        "construction -- a type, a smart constructor, a sealed or closed "
        "set of cases -- so the invalid state cannot be built, rather than "
        "solely by a runtime check a caller could skip or forget?",
        (8,),
    ),
    Criterion(
        "16",
        "no_dry_ssot_violation",
        "Is there exactly one writable authority for each fact the "
        "delivery introduces or touches -- no dual-write, no duplicated "
        "test class, no copy of logic that already exists elsewhere in "
        "the diff's own scope?",
        (9,),
    ),
    Criterion(
        "17",
        "integration_and_e2e_coverage",
        "Does the delivery exercise real ports at an integration layer "
        "and cover the smallest critical end-to-end path, distinct from "
        "its unit- or acceptance-level tests?",
        (11,),
        notes=(
            "Item 11 also has a mutation-testing clause, not judged here -- "
            "see DELEGATED_1A[11]."
        ),
    ),
)

CRITERIA_BY_KEY: dict[str, Criterion] = {c.key: c for c in CRITERIA}
CRITERIA_KEYS: frozenset[str] = frozenset(CRITERIA_BY_KEY)

#: The 13 items of ADR-SSOT-002 Section 1a, by number, short label only --
#: read the ADR for the full clause and its cross-references. Developer
#: metadata: never rendered to a reviewer.
SECTION_1A_ITEMS: dict[int, str] = {
    1: "Accepted outcome and correctness",
    2: "Prefactoring (GREEN_TO_GREEN, no new behavior through ATD's RED path)",
    3: "Code reuse",
    4: "Acceptance tests decoupled from implementation",
    5: "Semantic property-based testing",
    6: "Algebra-driven design",
    7: "Residuality on its lazy trigger",
    8: "Certainty-by-construction",
    9: "No DRY violation, no SSOT violation",
    10: "No architectural drift",
    11: (
        "Integration tests on real ports plus smallest critical E2E set; "
        "mutation testing as nightly diagnostic"
    ),
    12: "Source-blind single-pass Examiner (Vera) PASS, plus terminal finalize",
    13: (
        "Defect escape/rework, refactorability and maintainability no "
        "worse than baseline"
    ),
}

#: Section 1a items this rubric does not (fully) verdict from a sealed,
#: unexecuted delivery packet, and the instrument that does instead -- or an
#: explicit admission that K4 runs no such instrument at all. See the module
#: docstring, "What stays delegated, and why". Developer metadata: never
#: rendered to a reviewer.
DELEGATED_1A: dict[int, str] = {
    1: (
        "acceptance harness execution -- visible+hidden AT run via "
        "scripts/analysis/k4/run_acceptance.py's examine(), which every K4 "
        "campaign actually calls"
    ),
    10: (
        "NOT MEASURED in K4 -- INDETERMINATE for this item. No module "
        "under scripts/analysis/k4/ runs a DESIGN-authority diff "
        "comparison; a real instrument would need to be built and wired in "
        "before this item could contribute to the aggregate"
    ),
    11: (
        "mutation-testing nightly diagnostic, "
        ".github/workflows/mutation-nightly.yml -- criterion 17 above "
        "scores the judgable integration/E2E half of this item directly"
    ),
    12: (
        "the examine verdict ledger and the nw-finalize terminal commit "
        "(Vera's own PASS/FAIL record)"
    ),
    13: (
        "NOT MEASURED in K4 -- INDETERMINATE for this item. No module "
        "under scripts/analysis/k4/ tracks defects.md, techdebt.md or a "
        "baseline-suite trend per run; a real instrument would need to be "
        "built and wired in before this item could contribute to the "
        "aggregate"
    ),
}

#: Terms whose presence in a reviewer-facing field breaks source- or
#: shape-blindness -- naming an ADR section, an nWave-internal artefact, or
#: this module's own Python identifiers tells a reviewer things about the
#: instrument (and, indirectly, the arm) that a blind review must not carry.
#: Matched case-insensitively at word boundaries (`leaked_reviewer_vocabulary`),
#: not as a raw substring: a raw "vera" substring match false-positived on
#: the ordinary English words "discoverable" and "coverage" the first time
#: this list was checked. Includes both the ADR's own symbol ("§1a") and its
#: spelled-out form ("section 1a") because the form that actually leaked in
#: the 2026-08-18 review was the latter.
_REVIEWER_FACING_DENYLIST: tuple[str, ...] = (
    "§1a",
    "section 1a",
    "delegated",
    "deliverycontract",
    "vera",
    "green_to_green",
    "nwave",
    "adr",
)


def leaked_reviewer_vocabulary() -> list[tuple[str, str]]:
    """`(criterion key, denylisted term)` for every reviewer-facing field
    that leaks nWave/ADR vocabulary. Only `dimension` and `question` are
    checked -- `section_1a` and `notes` are code metadata, exempt by
    definition; see the module docstring.

    Each term is matched at word boundaries, not as a raw substring, so
    "vera" flags the word "Vera" but not "discoverable" or "coverage" --
    `\\w` boundaries handle every plain-word and underscored term in the
    list; the two-symbol terms ("§1a", the space in "section 1a") are rare
    enough that a boundary-free match on them carries no realistic
    collision risk.

    Empty is the only passing state; `test_no_criterion_leaks_nwave_or_adr_
    vocabulary_to_the_reviewer` pins it.
    """
    hits: list[tuple[str, str]] = []
    for c in CRITERIA:
        haystack = f"{c.dimension} {c.question}".lower()
        for term in _REVIEWER_FACING_DENYLIST:
            pattern = r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])"
            if re.search(pattern, haystack):
                hits.append((c.key, term))
    return hits


def citation_counts() -> dict[int, int]:
    """How many CRITERIA (not `DELEGATED_1A` entries) cite each Section 1a
    item -- the weight that item carries in `total` relative to every other
    item. See the module docstring, "Equal weight by default".
    """
    counts: dict[int, int] = dict.fromkeys(SECTION_1A_ITEMS, 0)
    for c in CRITERIA:
        for n in c.section_1a:
            counts[n] += 1
    return counts


def uncovered_1a_items() -> set[int]:
    """Section 1a items with neither a citing criterion nor a delegation.

    Empty is the only passing state; `test_quality_rubric_1a_coverage.py`
    pins it. Anything else is a Section 1a item this instrument would
    silently ignore during scoring.
    """
    cited = {n for c in CRITERIA for n in c.section_1a}
    return set(SECTION_1A_ITEMS) - cited - set(DELEGATED_1A)
