"""Regression for AD-59 (ARCH_TECH_DEBT.md): the §5.3 verify core is fold-shared.

scripts/cli/verify_coverage_map.py used to redefine 9 members of the §5.3
verify core (a constant tuple + 8 pure functions), byte-for-byte identical to
``des.application.coverage_map_verify_service`` -- multiple representations of
the same contract with nothing holding them equal (AD-59, ARCH_TECH_DEBT.md:527,
~172 LOC). The AD-59 fold re-pointed the CLI at the service for every member it
actually reads; this file pins the fold three ways, because the 9 members split
into three groups with three DIFFERENT correct properties -- getting the group
wrong for even one member is a real defect (see the HISTORY note below, where
this file's own first draft got one wrong).

  1. **Shared identity** (``_SHARED_CORE_FUNCTION_NAMES``, 5 names) -- the
     functions the CLI's OWN logic actually calls: ``_check_structural_
     completeness``, ``_extract_recorded_digest``, ``_compute_canonical_
     digest``, ``_load_omission_class_ids``, ``_extract_attested_class_ids``
     (call sites: ``scripts/cli/verify_coverage_map.py:251,258,267,280,296,444``).
     For these, the CLI must import the SAME object the service defines --
     identity (``is``), never equality-of-behaviour: two independently
     maintained functions can behave identically today and silently diverge on
     the next edit to either copy; a behavioural-equality test only catches
     that divergence AFTER it has shipped. Pinning ``is`` makes the drift
     STRUCTURALLY IMPOSSIBLE -- there is only ONE function object, so there is
     nothing left for two "copies" to disagree about.
  2. **Absence** (``_UNUSED_CORE_NAMES``, 4 names) -- ``_MANDATORY_SECTIONS_
     IN_ORDER``, ``_collapse_blank_runs``, ``_select_signed_sections``,
     ``_sort_feature_surface_lines``. The CLI's own logic has ZERO real call
     sites for any of these four (the three functions are internal helpers
     ``_compute_canonical_digest`` calls, entirely inside the service; the
     tuple is read by exactly the two functions the fold moved into the
     service -- see the HISTORY note). For a name the CLI does not need, "same
     object as the service's" is the WEAKER, wrong-shaped property -- it only
     detects a re-copy once one exists, AND it requires a module-level alias
     assignment to exist purely so the assertion has something to compare
     (test-induced design damage: production surface existing only to be
     asserted on). The stronger property for the CLI is: it does not define
     the name AT ALL -- absence makes a re-copy structurally impossible rather
     than merely re-detectable.
  3. **Deliberately NOT shared** (``_default_omission_classes_path``) -- the
     one member the CLI DOES need its own divergent copy of. It resolves the
     repo root relative to its OWN file's location (``scripts/cli/`` uses
     ``parents[2]``, ``src/des/application/`` uses ``parents[3]``), so the two
     copies MUST differ -- sharing one object here would silently break path
     resolution on one side. The negative test below pins that this one
     function is NOT the same object, guarding against a future over-eager
     fold collapsing it.

HISTORY (why this matters -- the constant used to belong to group 1, not
group 2): commit ``4eae945b7`` authored ``test_cli_mandatory_sections_is_the_
same_object_as_the_service_core`` as an identity pin, correctly, because at
that time the CLI's OWN ``_check_structural_completeness`` and ``_select_
signed_sections`` genuinely read ``_MANDATORY_SECTIONS_IN_ORDER``. The AD-59
fold moved BOTH of those functions into the service, which silently removed
the CLI's last real reader of the tuple too -- verified empirically:
``grep -n "_MANDATORY_SECTIONS_IN_ORDER" scripts/cli/verify_coverage_map.py``
returns only a comment and the alias assignment (zero call sites), and
``grep -rn "verify_coverage_map._MANDATORY_SECTIONS_IN_ORDER" --include=*.py .``
across the whole repo returns exactly ONE match: this file's own (now-removed)
identity assertion. Once the CLI has no reader, "same object" is the wrong
property for the SAME reason it is wrong for the three helpers -- the
identity pin was correct when authored and became the wrong-shaped pin the
moment the fold removed its last justification. The property tracks WHO
READS THE NAME, not which release introduced it; this docstring is deliberately
explicit about that so a future reader can derive which group a new AD-59-class
name belongs in without asking anyone: does the CLI's OWN logic have a real
call site for it? If yes -> group 1. If no, and no divergent-behaviour reason
to keep a second copy -> group 2. If no, but a real reason forces a second,
different implementation -> group 3 (today, exactly one member).

Absence-check honesty, verified empirically (not assumed): for a plain module
with no ``__getattr__`` hook (confirmed by inspection --
``scripts/cli/verify_coverage_map.py`` defines none), ``hasattr(module, name)``
is answered purely from the module's own ``__dict__`` -- it agrees exactly with
``name in vars(module)``. There is no class-inheritance MRO to fool the check
the way there would be on an instance. So ``not hasattr(cli_module, name)`` is
the honest test of "the CLI's own source binds no name by this spelling", not a
weaker proxy for it. This holds for a constant tuple exactly as it holds for a
function -- ``hasattr`` does not care what kind of object the name is bound to.
"""

from __future__ import annotations

import pytest

import scripts.cli.verify_coverage_map as verify_coverage_map_cli
from des.application import coverage_map_verify_service


# The 5 pure functions of the §5.3 verify core that the CLI's OWN logic calls
# (scripts/cli/verify_coverage_map.py:251,258,267,280,296,444) and that AD-59
# found byte-identical against src/des/application/coverage_map_verify_service.py
# (normalised-AST comparison, docstrings + the constant-alias name factored
# out). The CLI must import each from the service rather than maintain its own
# definition.
_SHARED_CORE_FUNCTION_NAMES = (
    "_compute_canonical_digest",
    "_extract_attested_class_ids",
    "_extract_recorded_digest",
    "_load_omission_class_ids",
    "_check_structural_completeness",
)

# The 4 AD-59 members (1 constant tuple + 3 functions) that the CLI's OWN
# logic never calls. The 3 functions are internal helpers of
# ``_compute_canonical_digest``, used entirely inside the service.
# ``_MANDATORY_SECTIONS_IN_ORDER`` was genuinely read by the CLI's own
# ``_check_structural_completeness``/``_select_signed_sections`` before the
# AD-59 fold moved BOTH of those readers into the service -- see the HISTORY
# note above for why the correct property flipped from identity to absence.
# The CLI must not define -- and must not alias -- any of these four names;
# see the absence-check reasoning above.
_UNUSED_CORE_NAMES = (
    "_MANDATORY_SECTIONS_IN_ORDER",
    "_collapse_blank_runs",
    "_select_signed_sections",
    "_sort_feature_surface_lines",
)


@pytest.mark.parametrize("name", _SHARED_CORE_FUNCTION_NAMES)
def test_cli_shares_verify_core_function_identity_with_the_service(
    name: str,
) -> None:
    """AD-59: each §5.3 core function must be the SAME object on both sides.

    Identity, not equality-of-behaviour: two independently maintained
    functions can agree on every example today and diverge on the next edit to
    either copy. Pinning ``is`` makes that drift structurally impossible --
    there is only one function object left to disagree with itself.
    """
    cli_function = getattr(verify_coverage_map_cli, name)
    service_function = getattr(coverage_map_verify_service, name)
    assert cli_function is service_function, (
        f"{name!r} must be imported by the CLI from "
        "des.application.coverage_map_verify_service, not redefined locally "
        "-- the two currently resolve to distinct function objects, which is "
        "exactly the AD-59 drift-risk this test exists to close."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("name", _UNUSED_CORE_NAMES)
def test_cli_does_not_define_unused_verify_core_members(name: str) -> None:
    """The CLI must have NO binding at all for a member it never reads.

    ``is``-identity is the right property for a name the CLI's own logic
    calls (see ``test_cli_shares_verify_core_function_identity_with_the_
    service``) -- but for a name the CLI does NOT call, asserting identity
    is the WRONG-SHAPED, weaker property: it only pins the CLI against
    re-*defining* the name, and it actively requires a module-level alias
    assignment to exist so the assertion has something to compare (test-
    induced production surface that exists purely to be asserted on). The
    stronger, correctly-shaped property for an unused member is ABSENCE: the
    CLI module binds no name by this spelling whatsoever -- no copy, no
    alias, nothing for a future re-copy to attach to.
    """
    assert not hasattr(verify_coverage_map_cli, name), (
        f"{name!r} must NOT be defined or aliased in the CLI at all -- the "
        "CLI's own logic has zero real readers of this member (it is used "
        "only inside des.application.coverage_map_verify_service); a binding "
        "under this name in the CLI module is dead surface kept alive purely "
        "to satisfy a test."
    )


@pytest.mark.negative_at
def test_cli_default_omission_classes_path_is_deliberately_NOT_shared() -> None:
    """``_default_omission_classes_path`` must stay two distinct functions.

    It resolves the repo root relative to ITS OWN file's location -- the CLI
    copy walks up from ``scripts/cli/`` (``parents[2]``), the service copy
    walks up from ``src/des/application/`` (``parents[3]``). Folding these
    into one shared object would silently break path resolution on whichever
    side no longer matches its own file depth. This negative assertion guards
    against a future over-eager fold collapsing the one function that must NOT
    be collapsed.
    """
    assert (
        verify_coverage_map_cli._default_omission_classes_path
        is not coverage_map_verify_service._default_omission_classes_path
    )
