"""Typed domain concepts for the dormant-seam runtime gate (slice-01).

Mandate-12 (SSOT via types): the domain nouns the Gherkin speaks -- the verdict
the gate reaches for a net-new effectful symbol, whether that symbol is wired to
a production call-site, and the loud-emission channel -- are expressed once here
as typed enums, so the composition root consumes typed parameters rather than
raw strings.

slice-01 scope: only the syntactic-call-site verdicts are modelled (a net-new
effectful symbol is DORMANT when no production call-site reaches it -> warn-loud;
WIRED when >=1 production call-site reaches it -> clean). The two never-silent
escapes (a `# dormant-ok: <F-id>` owned-residue marker), the binding-resolved
precision verdicts (entry-point-dispatched -> wired), and the net-new-delta
scoping verdicts (pre-existing-static-tree -> ineligible) are slice-02/03/04
concerns -- intentionally absent here, per per-slice JIT.
"""

from __future__ import annotations

from enum import Enum


class SeamVerdict(str, Enum):
    """Per-symbol verdict the dormant-seam gate reaches (slice-01)."""

    # A net-new effectful public symbol that no production call-site reaches
    # -> the gate fires a loud INDETERMINATE warning naming it (non-halting).
    DORMANT_NO_CALL_SITE = "dormant-no-call-site"
    # A net-new effectful public symbol that >=1 production call-site reaches
    # -> clean, no warning. The non-vacuity control pole.
    WIRED = "wired"


class CallSiteWiring(str, Enum):
    """Whether (and how) a net-new effectful symbol is reached by production code.

    slice-01 modelled NONE and DIRECT (a bare-name call through a
    ``from X import name`` binding). slice-02 adds INDIRECT -- the attribute-call
    wiring form (``import module; module.symbol()``), the floor of escape (a)
    "a real call-site INCLUDING ... wiring counts" (D5/D-4). slice-03 adds
    ENTRY_POINT -- the registry / entry-point dispatch form (a
    ``[project.entry-points."nwave.lang.adapter"]`` registration in pyproject,
    the anchor the real ``discovery.py`` resolve-and-probe seam reads), where the
    symbol has NO direct/attribute source call-site BY DESIGN; the gate must
    resolve the registration INTO the call-site set (binding-resolved, D6/D-3) so
    a dispatched symbol is NOT false-flagged dormant.
    """

    # No production module (outside the symbol's own module / tests) calls it.
    NONE = "none"
    # At least one production module calls it directly (bare-name, from-import).
    DIRECT = "direct"
    # A production module calls it via an attribute on the imported module
    # (``import module; module.symbol()``) -- the indirect-wiring floor (slice-02).
    INDIRECT = "indirect"
    # The symbol is wired ONLY by an entry-point / registry registration
    # (``[project.entry-points."nwave.lang.adapter"]`` -> ``module:Symbol``) with
    # NO source call-site -- the binding-resolved precision anchor (slice-03). The
    # gate must resolve the registration into a call-site so the symbol clears.
    ENTRY_POINT = "entry-point"


class SeamEscape(str, Enum):
    """How a flagged dormant seam is honestly cleared -- never silently (D5).

    Both escapes are LOUD/visible. A real call-site (escape a) makes the symbol
    not-dormant, so it never enters the flagged set. The owned-residue marker
    (escape b) clears an OTHERWISE-dormant symbol but RECORDS the clearing in the
    verdict surface (the F-id naming the owner) -- an auditable owned residue,
    not a hidden suppression.
    """

    # escape (a): a real production call-site (direct OR indirect wiring).
    CALL_SITE = "call-site"
    # escape (b): a `# dormant-ok: <F-id>` owned-residue marker on the symbol.
    DORMANT_OK_MARKER = "dormant-ok"


class SeamIdentity(str, Enum):
    """Which of two same-named symbols a fixture is asserting about (slice-03).

    The name-collision non-false-negation control: two distinct ``main`` symbols
    in different modules are distinct identities (module-qualified). A call to one
    must NOT count as a call-site for the other. ``WIRED`` is the one a production
    call-site reaches (must clear); ``DORMANT`` is the same-named one with no
    call-site (must still be flagged, by module-qualified identity, not bare name).
    """

    # The same-named symbol that a production call-site reaches -> must clear.
    WIRED = "wired"
    # The same-named symbol with no call-site -> must still be flagged dormant
    # (the call to its namesake does NOT cover it; module-qualified identity).
    DORMANT = "dormant"


class DeltaScope(str, Enum):
    """Whether a symbol belongs to the feature's net-new delta (slice-04).

    The net-new-delta-scoping control (DISCUSS D3 -- zero retroactive blast).
    The gate evaluates ONLY the feature's net-new delta (the files ADDED since the
    base ref, ``git diff --diff-filter=A``); a symbol that already lived on the
    static tree is OUT of the delta and is NEVER retroactively flagged -- turning
    the gate on does not warn about the whole existing codebase.

    OQ-1 (DESIGN D-2) granularity floor RESOLVED to ``ADDED_FILE``: a symbol is in
    the delta iff it lives in an ADDED file. A symbol added to a MODIFIED file
    (a file that already existed on the static tree) is NOT in the delta at the
    added-FILE floor -- ``--diff-filter=A`` returns added files only, so a modified
    file (and any net-new symbol it carries) is out of scope. ``MODIFIED_FILE_ADD``
    pins that explicit, honestly-named limitation (a slice-04 OQ-1 contract, not a
    bug; added-LINE resolution is a future hardening concern).
    """

    # The symbol lives in a file ADDED in the net-new delta -> eligible for
    # flagging (a net-new dormant one warns; the recall control).
    NET_NEW_ADDED_FILE = "net-new-added-file"
    # The symbol already lived on the static tree (committed in the base ref,
    # not re-added) -> OUT of the delta -> NEVER retroactively flagged.
    PRE_EXISTING_STATIC_TREE = "pre-existing-static-tree"
    # A net-new symbol added to a MODIFIED (pre-existing) file -> OUT of the
    # delta at the added-FILE granularity floor (OQ-1 resolution).
    MODIFIED_FILE_ADD = "modified-file-add"


class EmissionChannel(str, Enum):
    """Where the gate's loud INDETERMINATE warning is observable."""

    # OSS hooks-only invariant: the warning is loud on stderr, non-halting.
    STDERR = "stderr"
