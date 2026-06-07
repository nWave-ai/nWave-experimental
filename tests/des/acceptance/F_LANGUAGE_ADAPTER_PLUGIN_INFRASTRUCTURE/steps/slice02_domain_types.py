"""Domain types for the F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-02.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): every domain
noun used in the slice-02 Gherkin is expressed once here as a typed enum.
Step bodies and the composition service consume these typed parameters --
no raw ``str`` where a domain enum exists.

CONTRACT SOURCE (DESIGN feature-delta §Reuse Analysis EXTEND row):
- ``LanguageAdapterPlugin`` ABC at ``src/des/ports/language_adapter_plugin.py``
  (CREATE in slice-02 GREEN) subclasses
  ``scripts.install.plugins.base.InstallationPlugin`` and declares
  target_language / register_adapters / probe / port_coverage / metadata.
- ``ProbeResult`` dataclass (frozen) at the same module path.
- In-tree conformance-fixture plugin registered in the local installable
  wheel's entry-points under group ``nwave.lang.adapter`` provides a witness
  for AT-3 -- slice-05a / slice-07 replace with real language plugins.

Slice-02 ships the ABC + ProbeResult + fixture wiring ONLY (the walking-
skeleton floor). Concrete language plugins (Python in slice-05a, TypeScript
in slice-07) and lies-catalog (slice-05a seed + slice-05b non-vacuity gate)
arrive in later slices per the carpaccio plan.
"""

from __future__ import annotations

from enum import Enum


class AbcContractMember(str, Enum):
    """The four mandatory contract members on the LanguageAdapterPlugin ABC.

    Per DESIGN feature-delta §Reuse Analysis "EXTEND" row, the ABC adds
    these on top of ``InstallationPlugin``'s install/verify contract:

    TARGET_LANGUAGE:   the kebab-case language identifier ("python",
                       "typescript", ...); slice-03 / doctor CLI uses this
                       to build per-target lookups.
    REGISTER_ADAPTERS: the per-port adapter wiring entry point; takes the
                       composition-root adapter registry as argument.
                       slice-05a / slice-07 plugins implement this.
    PROBE:             the Earned-Trust (principle 13) probe contract;
                       returns ``ProbeResult`` per DESIGN §Earned Trust
                       probes required. slice-05a ships the first concrete
                       probe + Python lies catalog.
    PORT_COVERAGE:     per-port coverage matrix (dict[str, AdapterStatus]);
                       doctor CLI cross-products with the SSOT catalog to
                       compute the GAPS report.

    Note: ``metadata`` (maintainer / SLA / semver) is part of the broader
    contract but lands in slice-06 (maintenance commitment slice) -- the
    four members above are the slice-02 walking-skeleton floor.
    """

    TARGET_LANGUAGE = "target_language"
    REGISTER_ADAPTERS = "register_adapters"
    PROBE = "probe"
    PORT_COVERAGE = "port_coverage"


class AbcIntrospectionShape(str, Enum):
    """The user-observable shape facts of the ABC-introspection subprocess.

    Port-exposed observable: subprocess stdout JSON envelope.

    IS_ABSTRACT:  ``inspect.isabstract(cls)`` returns True (or the class
                  has non-empty ``__abstractmethods__``).

    M52 ATD amendment (2026-05-25, friction #43 closure): the original
    second member ``IS_INSTALLATION_PLUGIN_SUBCLASS`` was REMOVED. M44
    architect Option (a) decouples the pure ABC from ``InstallationPlugin``
    (F-D-09 closure). The dual-base contract now lives ONLY on the concrete
    fixture and is mechanically asserted by AT-3's dual-issubclass check at
    the entry-point load site -- not on the ABC itself.
    """

    IS_ABSTRACT = "abstract"


class EntryPointConformanceShape(str, Enum):
    """The two user-observable shape facts of the entry-point conformance subprocess.

    Port-exposed observable: subprocess stdout JSON envelope.

    ALL_CONFORM:        ``all_conform`` field is True -- every discovered
                        plugin loaded successfully AND is-a
                        ``LanguageAdapterPlugin`` subclass AND ≥1 plugin
                        was discovered (in-tree conformance fixture).
    NO_NON_CONFORMING:  ``non_conforming`` list is empty -- no discovered
                        entry-point class failed the issubclass check or
                        the load.
    """

    ALL_CONFORM = "every discovered plugin as conformant"
    NO_NON_CONFORMING = "no non-conforming class"


# --- Phrase -> typed-value lookup tables -------------------------------------
# Mandate-12 criterion 3: the DSL emerges from typed concepts. Each Gherkin
# literal maps to a typed enum here; the parameterized step templates in
# `slice02_common_steps.py` do a single dict lookup, never an `if`-ladder.

ABC_CONTRACT_MEMBER_BY_PHRASE: dict[str, AbcContractMember] = {
    m.value: m for m in AbcContractMember
}

ABC_INTROSPECTION_SHAPE_BY_PHRASE: dict[str, AbcIntrospectionShape] = {
    s.value: s for s in AbcIntrospectionShape
}

ENTRY_POINT_CONFORMANCE_SHAPE_BY_PHRASE: dict[str, EntryPointConformanceShape] = {
    s.value: s for s in EntryPointConformanceShape
}
