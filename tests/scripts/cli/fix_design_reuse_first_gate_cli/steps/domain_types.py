"""Domain types for the reuse-first design CLI acceptance slice-01.

F-DESIGN-REUSE-FIRST-GATE-CLI (DDD-1..DDD-7), Mandate-12 criterion 1. Every
domain noun used in the Gherkin is expressed once here as a typed enum or
NewType. Step bodies and the composition service consume these typed
parameters -- no raw ``str`` where a domain enum exists.

Walking-skeleton scope: three NEW-component-vs-Reuse-Analysis-section shapes,
two verdicts, one preservation universe (Mandate 8). The vocabulary is the
SSOT shared between the .feature file phrases and the composition fixtures.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "reuse-first-cli-demo").
FeatureId = NewType("FeatureId", str)


class ReuseFirstVerdict(str, Enum):
    """User-observable verdict of one check_reuse_first_design CLI invocation.

    The CLI emits a single-line stdout token:

        ``reuse_first feature=<id> new_components=<n> justified=<m> verdict=<PASS|FAIL>``

    The verdict is read from the STRUCTURED token, never from free-text
    stdout substrings (DDD-4).

    Accepted verdict (exit 0):
    PASS              -- every NEW component class introduced in the feature's
                         git diff range is named in the feature-delta's Reuse
                         Analysis section AND that row has a non-empty
                         Justification cell (DDD-5 / DDD-6).

    Rejected verdict (exit 1):
    FAIL              -- one or more NEW components is absent from the Reuse
                         Analysis section (or its row has an empty
                         Justification cell) (DDD-5 / DDD-6).

    Error verdict (exit 2):
    MALFORMED         -- the feature-delta is missing or unparseable; the
                         feature directory does not exist (DDD-5).

    UNRECOGNISED_INVOCATION -- NO stdout token at all: the CLI did not
                         produce its single-line contract output. On master
                         the production CLI does not exist (or is a RED
                         scaffold raising AssertionError before printing), so
                         the invocation lands here. NOT a real verdict --
                         it is the RED-for-the-right-reason signal.
    """

    PASS = "pass"
    FAIL = "fail"
    MALFORMED = "malformed"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


class FeatureShape(str, Enum):
    """The shape of the feature under check.

    Three walking-skeleton shapes covering the slice-01 decision-table
    (3 cells: GREEN-justified, FAIL-unjustified, PRESERVATION-read-only).

    ONE_NEW_COMPONENT_JUSTIFIED   -- one NEW class ``WidgetService`` is added
                                     in the feature's diff scope; the feature
                                     -delta carries a Reuse Analysis section
                                     row naming ``WidgetService`` with a
                                     non-empty Justification cell. The
                                     GREEN-PASS happy path.
    ONE_NEW_COMPONENT_UNJUSTIFIED -- one NEW class ``OrphanService`` is added
                                     in the feature's diff scope; the
                                     feature-delta carries a Reuse Analysis
                                     section that does NOT name
                                     ``OrphanService`` in any row. The
                                     FAIL sad path.
    """

    ONE_NEW_COMPONENT_JUSTIFIED = "one_new_component_justified"
    ONE_NEW_COMPONENT_UNJUSTIFIED = "one_new_component_unjustified"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step
# body a single typed lookup + a single composition call (Mandate-12
# criterion 3: no control flow in step bodies).

FEATURE_SHAPE_BY_PHRASE: dict[str, FeatureShape] = {
    "one NEW component named in its Reuse Analysis section": (
        FeatureShape.ONE_NEW_COMPONENT_JUSTIFIED
    ),
    "one NEW component absent from its Reuse Analysis section": (
        FeatureShape.ONE_NEW_COMPONENT_UNJUSTIFIED
    ),
}

VERDICT_BY_PHRASE: dict[str, ReuseFirstVerdict] = {
    "passes the reuse-first check": ReuseFirstVerdict.PASS,
    "is rejected by the reuse-first check": ReuseFirstVerdict.FAIL,
}

# The exit code each verdict maps to, per DDD-5. The Then-step reads the
# observable exit code against this typed mapping (no inline number literals
# in step bodies -- Mandate-12 criterion 3).
EXIT_CODE_BY_VERDICT: dict[ReuseFirstVerdict, int] = {
    ReuseFirstVerdict.PASS: 0,
    ReuseFirstVerdict.FAIL: 1,
    ReuseFirstVerdict.MALFORMED: 2,
}


# ---------------------------------------------------------------------------
# slice-02 domain types: real git-diff-driven NEW component detection.
#
# slice-02 promotes the detector from the slice-01 fixture-injected name list
# to the feature's real commit range (DDD-7): NEW components are read from the
# diff name-status of the feature branch vs its base branch, scoped to a path
# kind. New domain nouns: base branch, scoped path, added-path kind, NEW
# component cardinality. Each is expressed once here (Mandate-12 criterion 1).
# ---------------------------------------------------------------------------


# A git branch name the feature diverged from (e.g. "master", "trunk").
BaseBranch = NewType("BaseBranch", str)

# A repo-relative path-prefix the detector scopes NEW component detection to
# (e.g. "src"). A component added outside the scoped path is not a feature
# component.
ScopedPath = NewType("ScopedPath", str)


class AddedPathKind(str, Enum):
    """The repo-relative directory the feature's commits add a component under.

    SOURCE_TREE  -- the component is added under ``src`` (the default scoped
                    path); it is a feature component and requires a Reuse
                    Analysis row.
    OUTSIDE_TREE -- the component is added under ``tools`` (outside the default
                    ``src`` scope); it is NOT a feature component and requires
                    no Reuse Analysis row even when unnamed.
    """

    SOURCE_TREE = "src"
    OUTSIDE_TREE = "tools"


# Gherkin-phrase -> typed-value lookups for slice-02. Module-level dicts keep
# each step body a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

ADDED_PATH_KIND_BY_PHRASE: dict[str, AddedPathKind] = {
    "src": AddedPathKind.SOURCE_TREE,
    "tools": AddedPathKind.OUTSIDE_TREE,
}

# The NEW component count each cardinality phrase denotes. The Then-step reads
# the observable count against this typed mapping (no inline number literals
# in step bodies -- Mandate-12 criterion 3).
COMPONENT_COUNT_BY_PHRASE: dict[str, int] = {
    "zero": 0,
    "one": 1,
}

# The verdict each scoped-detection outcome phrase denotes (Scenario Outline
# ``<verdict>`` column). Distinct from VERDICT_BY_PHRASE (which keys on the
# slice-01 "the feature {verdict_phrase}" full clause); these key on the bare
# outcome verb used in the slice-02 outline.
VERDICT_BY_OUTCOME_PHRASE: dict[str, ReuseFirstVerdict] = {
    "passes": ReuseFirstVerdict.PASS,
    "is rejected by": ReuseFirstVerdict.FAIL,
}


# ---------------------------------------------------------------------------
# slice-03 domain types: methodology file-component detection (DDD-8..DDD-11).
#
# slice-03 adds a SECOND detection unit alongside the class-component unit
# (DDD-7). An added file under a methodology-path kind (``nWave/data/**``,
# ``nWave/skills/**``, ``scripts/cli/**``) is ITSELF a NEW component keyed by
# its repo-relative path/stem -- NOT by ``^class`` grep. The two units compose;
# ``new_components`` is the UNION (DDD-11). Each new domain noun is expressed
# once here (Mandate-12 criterion 1).
# ---------------------------------------------------------------------------


class MethodologyPathKind(str, Enum):
    """A methodology-path kind whose added files are file-components (DDD-9).

    An added file whose repo-relative path matches one of these kinds is a NEW
    methodology component keyed by path/stem (file-component mode, DDD-10), NOT
    grepped for ``^class`` declarations. The detection unit is dispatched by
    path kind: ``src/**`` -> class-component mode; these -> file-component mode.

    DATA_SSOT   -- ``nWave/data/**``: JSON/YAML methodology SSOT artifacts
                   (e.g. ``nWave/data/dor-items.yaml``). The canonical
                   vacuous-PASS blind spot the slice targets: a new data SSOT
                   ships unchallenged under the class-grep-only detector.
    SKILL_PROSE -- ``nWave/skills/**``: skill prose (``SKILL.md``).
    CLI_GATE    -- ``scripts/cli/**``: new standalone gate scripts.
    """

    DATA_SSOT = "nWave/data"
    SKILL_PROSE = "nWave/skills"
    CLI_GATE = "scripts/cli"


# Gherkin-phrase -> typed-value lookup for slice-03 methodology-path kinds.
# Keys are the human-facing methodology-path phrases used in the Scenario
# Outline ``<methodology_path>`` column. Module-level dict keeps each step
# body a single typed lookup + a single composition call (Mandate-12
# criterion 3: no control flow in step bodies).

METHODOLOGY_PATH_KIND_BY_PHRASE: dict[str, MethodologyPathKind] = {
    "nWave/data": MethodologyPathKind.DATA_SSOT,
    "nWave/skills": MethodologyPathKind.SKILL_PROSE,
    "scripts/cli": MethodologyPathKind.CLI_GATE,
}

# The NEW component count each cardinality phrase denotes, extended for the
# slice-03 union count (DDD-11). The Then-step reads the observable count
# against this typed mapping (no inline number literals in step bodies --
# Mandate-12 criterion 3).
COMPONENT_COUNT_BY_PHRASE.update({"two": 2})


# ---------------------------------------------------------------------------
# slice-05 domain types: skill scope extension (DDD-12).
#
# slice-05 closes the seam at the PRODUCING end: the nw-design skill is the
# upstream artifact-producing copy that tells an architect WHICH components to
# declare in the Reuse Analysis table. Today its Reuse-first exit-gate prose
# scopes only NEW *classes* under `src/`; the gate's methodology file-component
# unit (slice-03) is therefore non-vacuous only if the skill instructs the
# architect to declare methodology components too. The slice-05 nouns name the
# skill's two surfaces and the recursive-dogfood verdict legs. Each is
# expressed once here (Mandate-12 criterion 1).
# ---------------------------------------------------------------------------


class SkillSurface(str, Enum):
    """A surface of the nw-design skill the slice-05 cross-artifact ATs inspect.

    REUSE_FIRST_EXIT_GATE_PROSE -- the "### Reuse-first DESIGN exit gate" prose
                                   block (today: "For each NEW class declared
                                   under the feature's scoped-path (default
                                   `src/`)"). slice-05 extends it to instruct the
                                   architect to declare methodology components.
    LENIENT_MATCH_NOTE          -- the "**Lenient match ...**" note inside the
                                   exit-gate prose (today: "the NEW class name
                                   appearing anywhere..."). slice-05 adds the
                                   file-component path/stem form.
    """

    REUSE_FIRST_EXIT_GATE_PROSE = "reuse_first_exit_gate_prose"
    LENIENT_MATCH_NOTE = "lenient_match_note"


# The methodology-path kinds the skill's reuse-first exit-gate prose MUST name
# for the gate's file-component unit (slice-03) to be non-vacuous. These are the
# EXACT defaults the production CLI's --methodology-path flag documents
# (MethodologyPathKind values) -- the coherence binding between the skill
# guidance and the gate (DDD-12). Each appears once (Mandate-12 criterion 1).
SKILL_NAMED_METHODOLOGY_PATHS: tuple[str, ...] = (
    MethodologyPathKind.DATA_SSOT.value,  # nWave/data
    MethodologyPathKind.SKILL_PROSE.value,  # nWave/skills
    MethodologyPathKind.CLI_GATE.value,  # scripts/cli
)


class FileComponentMatchForm(str, Enum):
    """A form the skill's lenient-match note documents for file-components.

    PATH -- the file-component's repo-relative path (e.g.
            ``nWave/data/dor-items.yaml``) named in an Existing Component cell.
    STEM -- the file-component's stem (e.g. ``dor-items``) named in an Existing
            Component cell.

    slice-05 requires the lenient-match note to document BOTH forms (DDD-10:
    path-form and stem-form are both accepted by the gate).
    """

    PATH = "path"
    STEM = "stem"


# Gherkin-phrase -> typed-value lookup for the slice-05 recursive-dogfood
# Scenario Outline. The dogfood proves the end-to-end loop closes: a fixture
# feature-delta adding a methodology file under a skill-named path PASSes when a
# Reuse Analysis row names it, FAILs when absent. Keyed on the bare outcome verb
# used in the outline (distinct from VERDICT_BY_OUTCOME_PHRASE which the
# slice-03 outline already binds). Module-level dict keeps each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3).
DOGFOOD_VERDICT_BY_NAMING_PHRASE: dict[str, ReuseFirstVerdict] = {
    "names": ReuseFirstVerdict.PASS,
    "omits": ReuseFirstVerdict.FAIL,
}
