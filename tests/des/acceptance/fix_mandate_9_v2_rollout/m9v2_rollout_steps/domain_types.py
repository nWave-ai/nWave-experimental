"""Domain types for fix-mandate-9-v2-rollout slice-01 acceptance tests.

Mandate-12 criterion 1 (SSOT + Zero Duplication via Types + Services + DSL).
Every domain noun used in the Gherkin is expressed once here as a typed enum
or NewType. Step bodies and the slice-01 composition consume these typed
parameters — no raw `str` where a domain enum exists.

The slice ships three surfaces under test:
  - `framework-catalog.yaml` carries a `slice_kinds` enum vocabulary with
    `adapter-integration` as new first-class entry (DD-2)
  - `carpaccio_slice_gate` emits a `MandateNineTagMismatch` warning when
    a scenario carries `@real-io` but its composition root uses only
    mock/stub adapters (DD-4 structured stderr event)
  - `docs/architecture/at-real-io-audit-2026-05-27.md` retro-audit artifact
    scaffold with 5-column table schema (DD-3)
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A slice-kind identifier as registered in `framework-catalog.yaml` under the
# `slice_kinds:` vocabulary section. The closed catalog after slice-01:
# `walking_skeleton`, `coupled`, `regression-pin`, `adapter-integration`.
SliceKindId = NewType("SliceKindId", str)


# An asserted tag declared on a Gherkin scenario header (e.g. `@real-io`,
# `@in-memory`, `@mixed`). Kept as a NewType to make composition signatures
# self-documenting at the test boundary.
AssertedTag = NewType("AssertedTag", str)


# An adapter constructor identifier observed in a composition root
# (e.g. "MockAdapter", "StubAdapter", "RealFileSystem", "JsonlLogAdapter").
# The detector compares observed identifiers against the Adapter Criticality
# table to determine real-vs-mock status.
AdapterCtorName = NewType("AdapterCtorName", str)


class WarningSeverity(str, Enum):
    """The structured-event severity field per DD-4 contract.

    WARNING -- slice-01 non-blocking baseline (carpaccio gate exit stays 0).
    BLOCKING -- slice-03 promotion after F-AT-REAL-IO-TAG-MECHANICAL-AUDIT closes.
    """

    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class TagCompositionVerdict(str, Enum):
    """The detector verdict for a (tag, composition) pair per DD-4.

    CONSISTENT  -- tag-asserted matches composition observed (no warning).
    MISMATCH    -- tag-asserted disagrees with composition observed
                   (warning emitted to stderr).
    """

    CONSISTENT = "consistent"
    MISMATCH = "mismatch"


class AuditTableColumn(str, Enum):
    """The 5-column schema of `at-real-io-audit-2026-05-27.md` per DD-3.

    Each enum member is the literal column header text the scaffold renders.
    Reviewer verifies header row matches this closed vocabulary.
    """

    SCENARIO_FILE_LINE = "scenario file:line"
    TAG_ASSERTED = "tag asserted"
    COMPOSITION_EVIDENCE = "composition evidence"
    VERDICT = "verdict"
    RE_TAG_ACTION = "re-tag action"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep step bodies
# at one typed lookup + one composition call (Mandate-12 criterion 3 -- no
# control flow in step bodies).

SEVERITY_BY_PHRASE: dict[str, WarningSeverity] = {
    "warning": WarningSeverity.WARNING,
    "blocking": WarningSeverity.BLOCKING,
}

VERDICT_BY_PHRASE: dict[str, TagCompositionVerdict] = {
    "consistent": TagCompositionVerdict.CONSISTENT,
    "mismatch": TagCompositionVerdict.MISMATCH,
}


# --- slice-02 domain types ------------------------------------------------
#
# Slice-02 verifies behavioural skill / agent / reviewer surfaces carry the
# expected section headings + tokens + checklist steps per spike v2 §6
# surfaces 2, 4, 10. Production .md files act as the SUT; the driving-port
# read is `pathlib.Path.read_text(...)` on the live skill/agent paths.


class SkillAgentDoc(str, Enum):
    """The three behavioural surfaces under test in slice-02.

    Each enum member identifies one production document whose body must
    carry the slice-02 contract tokens. The composition resolves the enum
    member to the repo-relative path via a SSOT lookup (no path literals
    duplicated in step bodies per Mandate-12).
    """

    NW_DISTILL = "nw-distill"
    NW_ACCEPTANCE_DESIGNER_REVIEWER = "nw-acceptance-designer-reviewer"
    NW_TDD_METHODOLOGY = "nw-tdd-methodology"


# Repo-relative paths for each behavioural document under test. Lookup is
# the single source of truth -- step bodies + composition refer to the
# SkillAgentDoc enum, never the raw paths.
SKILL_AGENT_DOC_PATHS: dict[SkillAgentDoc, str] = {
    SkillAgentDoc.NW_DISTILL: "nWave/skills/nw-distill/SKILL.md",
    SkillAgentDoc.NW_ACCEPTANCE_DESIGNER_REVIEWER: (
        "nWave/agents/nw-acceptance-designer-reviewer.md"
    ),
    SkillAgentDoc.NW_TDD_METHODOLOGY: "nWave/skills/nw-tdd-methodology/SKILL.md",
}


# A section heading text expected to appear as a Markdown H2/H3 in the
# loaded skill/agent document. Kept as NewType so composition signatures
# accept only the typed value at the slice-02 boundary.
SectionHeading = NewType("SectionHeading", str)


# A literal property-matrix row name (one of the 10 properties per spike
# v2 §5 expanded matrix). NewType-wrapped so step bodies pass typed values
# to the composition's enumeration check.
PropertyMatrixRow = NewType("PropertyMatrixRow", str)


class VerdictVocabularyToken(str, Enum):
    """Per-property declaration vocabulary per spike v2 §5 ADD-M4.

    Slice plan rows must declare each property as EXERCISED / N/A / DEFERRED;
    the distill skill MUST enumerate these three tokens.
    """

    EXERCISED = "EXERCISED"
    NA = "N/A"
    DEFERRED = "DEFERRED"


# A reviewer critique vector name (e.g. "S3 mock-tag consistency"). NewType
# wraps the literal so step bodies and composition share the same typed
# vocabulary at the slice-02 boundary.
CritiqueVectorName = NewType("CritiqueVectorName", str)


# A mechanical checklist step phrase per spike v2 §5 AUTH-2. Each phrase
# must appear in the reviewer agent body so Sentinel knows the verification
# steps mechanically.
ChecklistStepPhrase = NewType("ChecklistStepPhrase", str)


# A RED-phase mode phrase per spike v2 §6 surface #10. The TDD-methodology
# skill body MUST mention each mode to distinguish acceptance RED from
# adapter-integration RED. NewType-wrapped for typed boundary.
RedPhaseModePhrase = NewType("RedPhaseModePhrase", str)


# A distinguishing token the TDD methodology body must carry so the
# acceptance vs adapter-integration RED-phase semantics are differentiated.
# Spike v2 surface #10 cites "property-matrix row contract" as the key
# distinction; the composition asserts the token is present in the section
# body.
RedPhaseDistinguishingToken = NewType("RedPhaseDistinguishingToken", str)


# --- slice-03 domain types ------------------------------------------------
#
# Slice-03 closes the Mandate 9 v2 rollout: the retro-audit artifact body is
# populated with verdict rows (≥1 per audit closure trigger), the carpaccio
# gate's MandateNineTagMismatch detector is promoted from non-blocking
# WARNING to BLOCKING (exit code 44 on mismatch), and the project-local
# `docs/architecture/atdd-infrastructure-policy.md` carries the new
# `## Adapter Criticality` section with ≥1 (Port, Adapter) row classified.


class AuditRowVerdict(str, Enum):
    """The closed-vocabulary verdict literal for a populated retro-audit row.

    DD-3 declares the audit doc's verdict column as one of three literals.
    Slice-03 closure requires that the populated rows carry only these
    values; any other token at the verdict column is a malformed row.
    """

    CORRECT = "CORRECT"
    MISLABEL = "MISLABEL"
    MIXED = "MIXED"


# Lookup from phrase token -> typed verdict. Keeps step bodies at one typed
# lookup + one composition call (Mandate-12 criterion 3 — no control flow).
VERDICT_BY_AUDIT_PHRASE: dict[str, AuditRowVerdict] = {
    "CORRECT": AuditRowVerdict.CORRECT,
    "MISLABEL": AuditRowVerdict.MISLABEL,
    "MIXED": AuditRowVerdict.MIXED,
}


# A column literal in the `## Adapter Criticality` table per the project
# infrastructure policy section added in slice-03. NewType-wrapped at the
# slice-03 boundary so composition signatures accept only the typed value.
AdapterCriticalityColumn = NewType("AdapterCriticalityColumn", str)


class AdapterCriticalityLevel(str, Enum):
    """The 3-way classification per spike v2 §4 attached to (Port, Adapter) pairs.

    CRITICAL — audit-trail / recovery / irreversibility / process-spawning /
               security predicate fires; adapter-integration slice required.
    STANDARD — real OS/library primitives but no CRITICAL predicate fires;
               adapter-integration slice required only when used inside a
               CRITICAL composition root (promotion rule).
    TRIVIAL  — in-memory test infrastructure (fakes, stubs); adapter-
               integration slice optional or N/A.
    """

    CRITICAL = "CRITICAL"
    STANDARD = "STANDARD"
    TRIVIAL = "TRIVIAL"


# Lookup from phrase token -> typed criticality literal. One typed lookup
# at the step-body boundary keeps Mandate-12 criterion 3 satisfied (no
# branching on string literals inside step bodies).
CRITICALITY_BY_PHRASE: dict[str, AdapterCriticalityLevel] = {
    "CRITICAL": AdapterCriticalityLevel.CRITICAL,
    "STANDARD": AdapterCriticalityLevel.STANDARD,
    "TRIVIAL": AdapterCriticalityLevel.TRIVIAL,
}


# The repo-relative path to the project infrastructure policy document.
# SSOT lookup -- step bodies + composition share this constant; no string
# literals duplicated in step bodies (Mandate-12 criterion 3).
ATDD_INFRASTRUCTURE_POLICY_PATH: str = "docs/architecture/atdd-infrastructure-policy.md"


# The repo-relative path to the retro-audit artifact (DD-3). Same SSOT
# discipline -- the slice-03 composition reads from this single constant.
RETRO_AUDIT_ARTIFACT_PATH: str = "docs/architecture/at-real-io-audit-2026-05-27.md"
