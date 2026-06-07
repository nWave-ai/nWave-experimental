"""Domain types for the F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-01.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): every domain
noun used in the Gherkin is expressed once here as a typed enum / NewType.
Step bodies and the composition service consume these typed parameters -- no
raw ``str`` where a domain enum exists.

CONTRACT SOURCE (DESIGN ratified Option C, ADR-031/032):
- Port catalog SSOT lives at ``nWave/data/language-adapter-ports.yaml``
  (machine-readable distillation of ``docs/architecture/language-adapter-catalog.md``).
- Catalog schema at ``nWave/schemas/language-adapter-ports.schema.json``
  (JSON Schema Draft 2020-12).
- Dry-run discovery CLI is ``des doctor --target-language=<lang>``
  (routes through ``src/des/cli/doctor.py``).
- Plugin discovery via ``importlib.metadata.entry_points(group="nwave.lang.adapter")``.

Slice-01 ships ONLY the walking-skeleton floor of these. Subsequent slices
extend with the LanguageAdapterPlugin ABC (slice-02), gap-report JSON shape
(slice-03), install-time gap UX (slice-04), per-port extraction (slice-05a/b),
maintenance contract (slice-06), TS plugin walking-skeleton (slice-07), PRR
D8 scoring + F-D-06 supply-chain mitigation (slice-08).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case language identifier ("python", "typescript", "go", "rust").
# Unbounded at the trust boundary (any user-supplied string); the catalog
# enumerates the supported set + the resolver normalizes casing / aliases.
TargetLanguage = NewType("TargetLanguage", str)


class PortClassification(str, Enum):
    """The four port classifications the SSOT catalog enumerates.

    Per Nova audit (``docs/architecture/language-adapter-catalog.md`` §Classification
    Taxonomy):
    - LANGUAGE_BOUND: customer-facing surface assuming language-specific tooling;
      MUST be extracted as port + per-language plugin.
    - SEMI_BOUND: customer-facing surface mostly neutral with a language-bound leg;
      the bound leg extracts, the neutral core stays in the framework.
    - LANGUAGE_NEUTRAL: customer-facing surface relying only on universal artifacts
      (git, Markdown, JSON, YAML, Gherkin, HMAC, SHA-256). No extraction needed.
    - NWAVE_INTERNAL: framework code, dev-machine resident, customer never executes.
      Python acceptable indefinitely.
    """

    LANGUAGE_BOUND = "LANGUAGE_BOUND"
    SEMI_BOUND = "SEMI_BOUND"
    LANGUAGE_NEUTRAL = "LANGUAGE_NEUTRAL"
    NWAVE_INTERNAL = "NWAVE_INTERNAL"


class CatalogValidationOutcome(str, Enum):
    """The two user-observable outcomes of the catalog-validator CLI.

    Port-exposed observable: validator exit code + structured stdout report.
    """

    VALID = "valid"
    INVALID = "invalid"


class DoctorReportShape(str, Enum):
    """The three user-observable outcomes of ``des doctor --target-language=X``.

    Port-exposed observable: CLI exit code + JSON report shape on stdout.

    READY:   target language is fully covered (every LANGUAGE_BOUND port has a
             registered plugin adapter). Exit 0.
    GAPS:    target language is partially covered (≥1 LANGUAGE_BOUND port lacks
             an adapter; report enumerates missing ports). Exit 0 (informational;
             slice-04 raises to non-zero install-time when --target= is set).
    UNKNOWN: target language is NOT in the catalog's supported-languages set
             (user supplied an unrecognized identifier). Exit 2.
    """

    READY = "ready"
    GAPS = "gaps"
    UNKNOWN = "unknown"


class CatalogPresence(str, Enum):
    """Whether the SSOT port catalog file exists on disk and is well-formed."""

    ABSENT = "absent"
    PRESENT_WELL_FORMED = "present and well-formed"
    PRESENT_MALFORMED = "present but malformed"


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12 criterion 3: the DSL emerges from typed concepts. Each Gherkin
# literal maps to a typed enum here; the parameterized step templates in
# `common_steps.py` do a single dict lookup, never an `if`-ladder.

CATALOG_PRESENCE_BY_PHRASE: dict[str, CatalogPresence] = {
    p.value: p for p in CatalogPresence
}

DOCTOR_SHAPE_BY_PHRASE: dict[str, DoctorReportShape] = {
    s.value: s for s in DoctorReportShape
}

CATALOG_OUTCOME_BY_PHRASE: dict[str, CatalogValidationOutcome] = {
    o.value: o for o in CatalogValidationOutcome
}
