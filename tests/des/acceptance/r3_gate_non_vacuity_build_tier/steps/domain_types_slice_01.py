"""Domain types for r3-gate-non-vacuity-build-tier slice-01 (Mandate-12 criterion 1).

slice-01 (walking skeleton) -- the per-slice exit gate
(`des run-contract-gate --feature-id <f> --entering-slice <s>`) must cover the
ARCHITECTURE TIER, not just the feature's own `.feature` scope. Today the
feature-scoped mode narrows collection to the feature's `.feature` PARENT dirs
(`run_contract_gate.py:894`), STRUCTURALLY EXCLUDING `tests/build/**` -- where
the architecture-boundary invariant tests live (the F-D-09 forbidden-roots gate,
the inline-interpreter-spawn ban). So a slice can break a `tests/build/`-class
arch invariant, pass its narrower-than-contract feature-scoped run GREEN, and
earn a `SliceCommitVerified` record -- while the whole-tree pre-push gate (which
DOES run `tests/build/`) would have BLOCKED it. That is the
"narrower-than-contract green by construction" non-vacuity hole.

MECHANISM (verified-from-source at HEAD 479adf700, corrected per feature-delta
§6 ADDENDUM -- Form A): the keystone threat is a RUN-TIME architecture
invariant. The real F-D-09 arch gate `tests/build/test_des_no_dev_root_imports.py`
is a self-contained AST scanner: it reads each `src/des/**/*.py` as TEXT and
`ast.parse`s it (`:42`); it NEVER `import`s the scanned subject. The forbidden
import surfaces only when the assertion (`:78` `assert not all_violations`)
EXECUTES at run-time -- collection imports only `ast`/`pathlib`/`pytest` (`:15-20`).
The `--feature-id` mode is COLLECT-ONLY (`_collect_scope_worker.py:135` hard
`--collect-only`), so it can NEVER catch a scans-not-imports run-time arch
failure. The corrected gate (DDD-1 §6.2) collect-AND-RUNs the arch-invariant set
via a `--run` worker branch; a broken arch tier is therefore a tier that PASSES
collection and FAILS at run-time.

(The earlier "Reading A" collection-crash seed -- a forbidden import that some
in-scope test directly imports, surfacing as a collection-time ImportError --
proved an ADJACENT sub-class, NOT the keystone's scans-not-imports run-time
threat; superseded by Form A per the §6 ADDENDUM.)

OQ-1 ratified for slice-01: the architecture-invariant set membership is the
`tests/build/**` GLOB (the walking-skeleton contract). A dedicated
`@pytest.mark.arch` marker convention is deferred to slice-02 hardening.

Every domain noun used in the Gherkin is expressed once here as a typed enum /
NewType. Step bodies and the composition service consume these typed parameters
-- no raw `str` where a domain enum exists (criterion 1 + 2).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A feature id that the `@feature-{id}` Gherkin tag binds a `.feature` file to.
# The SYNTHETIC fixture's feature id is DISTINCT from the AT's own feature id so
# the SUT never resolves the AT's own `.feature` file (plane separation).
FeatureId = NewType("FeatureId", str)

# A `@slice-NN` carpaccio slice tag (anchored `@slice-\d+`, no letter suffix).
SliceTag = NewType("SliceTag", str)


class ArchViolationShape(str, Enum):
    """The SHAPE of the seeded architecture-tier invariant violation (Form A).

    The keystone hole is a CLASS of failure, not one literal. The gate must
    refuse the slice for ANY of these arch-violation shapes -- proving it
    catches the architecture tier as a category, not one hard-coded test.

    CRITICAL (Form A): EVERY shape PASSES COLLECTION and FAILS AT RUN-TIME --
    this is the keystone's actual threat (a scans-not-imports AST arch gate). A
    collect-only gate is structurally blind to all of them; only the
    collect-AND-RUN fix (`--run` worker branch, DDD-1 §6.2) observes them.

    * FORBIDDEN_DEV_ROOT_IMPORT -- the canonical F-D-09 member. A `src/des/**`
      module carries `from scripts...` that NO in-scope test imports (so
      collection passes); a `tests/build/`-class AST scanner test reads that
      module as TEXT and asserts no forbidden roots -> FAILS at run-time. This
      is the EXACT shape of the real `test_des_no_dev_root_imports.py`.
    * INLINE_INTERPRETER_SPAWN -- a `src/des/**` module carries a raw
      `subprocess.run(["python3", ...])` spawn (the F-21 bug shape); a
      `tests/build/`-class AST scanner asserts no inline spawn -> FAILS at
      run-time. Mirrors the real `test_no_inline_interpreter_spawn.py`.
    * SEEDED_RUNTIME_ASSERTION -- a generic `tests/build/`-class arch test that
      collects cleanly and `assert`s False at run-time, proving the gate catches
      the arch tier GENERICALLY, not only the two named project invariants.
    """

    FORBIDDEN_DEV_ROOT_IMPORT = "forbidden_dev_root_import"
    INLINE_INTERPRETER_SPAWN = "inline_interpreter_spawn"
    SEEDED_RUNTIME_ASSERTION = "seeded_runtime_assertion"


class ArchTierState(str, Enum):
    """Whether the synthetic repo's architecture tier is clean or broken.

    The slice-01 property quantifies over this domain together with
    `ArchViolationShape`: for EVERY synthetic repo whose feature `.feature`
    scope is all-clean, the feature-scoped verdict must be REFUSED when the
    arch tier is BROKEN (run-time arch failure), and CLEARED when the arch tier
    is CLEAN. Today the verdict is CLEARED in BOTH states (the arch tier is
    never even run, let alone collected) -- that is the RED witness.
    """

    CLEAN = "clean"  # tests/build/** runs GREEN
    BROKEN = "broken"  # tests/build/** collects, then FAILS at run-time


class GateVerdict(str, Enum):
    """How `des run-contract-gate --feature-id` resolves, EXIT-CODE-EXACT.

    The feature-scoped contract, RE-ALLOCATED by
    fix-e2-whole-tree-scope-blocks-unrelated-slices:

    * CLEARED  -- exit 0, emits `FeatureScopeCleared`. The feature scope
      collected non-vacuously. The whole-tree architecture tier is DEFERRED to
      feature-end (announced LOUD via `BuildTierWholeTreeDeferred`), so an
      unrelated concurrent lane's in-flight RED can no longer hold this slice
      hostage.
    * REFUSED  -- exit 2, emits `FeatureScopeMalformed`. The feature-scope
      non-vacuity floor tripped (`zero-collected` / `empty-intersection` /
      `collection-failed`) -- always something inside the entering slice's OWN
      scope, never another lane's file.
    * UNEXPECTED -- any OTHER non-zero exit (argparse error, uncaught crash) --
      a WRONG failure mode, so a REFUSED assertion never passes for the wrong
      reason.

    The `arch-invariant-failed` / `arch-scope-zero-collected` refusals this
    feature originally pinned HERE now live on `WholeTreeVerdict` (the
    feature-end whole-tree run). The protection relocated; it was not dropped.
    """

    CLEARED = "cleared"  # exit 0 -- FeatureScopeCleared
    REFUSED = (
        "refused"  # exit 2 -- FeatureScopeMalformed (floor OR arch-invariant-failed)
    )
    UNEXPECTED = "unexpected"  # any other non-zero -- a WRONG failure mode


class WholeTreeVerdict(str, Enum):
    """How the WHOLE-TREE architecture run resolves, EXIT-CODE-EXACT.

    RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices): the
    keystone protection ("a slice must not earn a verified record while
    breaking an architecture boundary") is NOT deleted -- it MOVES off the
    per-slice gate and onto the whole-tree run at feature-end. This enum is the
    verdict vocabulary of that relocated surface.

    * CLEARED -- exit 0, emits `BuildTierVerified` (a non-vacuous tier that ran
      GREEN) or `BuildTierNotApplicable` (a target carrying no arch tier).
    * REFUSED -- exit 1, emits `BuildTierRefused` -- reason
      `arch-invariant-failed` (a run-time arch invariant FAILED) or
      `arch-scope-zero-collected` (a PRESENT-but-vacuous tier).
    * UNEXPECTED -- any OTHER non-zero exit, so a REFUSED assertion never
      passes for the wrong reason.
    """

    CLEARED = "cleared"  # exit 0 -- BuildTierVerified / BuildTierNotApplicable
    REFUSED = "refused"  # exit 1 -- BuildTierRefused
    UNEXPECTED = "unexpected"  # any other non-zero -- a WRONG failure mode


# The malformed `reason` the gate emits when a run-time arch invariant FAILS.
# After the re-allocation this reason is observed on the WHOLE-TREE run
# (`BuildTierRefused`), no longer on the per-slice feature-scoped verdict.
ARCH_INVARIANT_FAILED_REASON = "arch-invariant-failed"

# The whole-tree architecture-run verdict events (verified-from-source:
# `run_contract_gate.py` `build_tier_exit_verdict`).
BUILD_TIER_REFUSED_EVENT = "BuildTierRefused"
BUILD_TIER_VERIFIED_EVENT = "BuildTierVerified"
BUILD_TIER_NOT_APPLICABLE_EVENT = "BuildTierNotApplicable"

# The LOUD per-slice deferral record (GDP-6, no silent-wrong): the per-slice
# gate must ANNOUNCE that it deferred the whole-tree tier, and NAME where the
# coverage moved to -- a narrowing that says nothing is indistinguishable from
# a coverage drop.
BUILD_TIER_WHOLE_TREE_DEFERRED_EVENT = "BuildTierWholeTreeDeferred"
DEFERRED_TO_FEATURE_END = "feature-end"


# The synthetic fixture's feature id -- DISTINCT from this AT's own feature id
# (`r3-gate-non-vacuity-build-tier`). The SUT resolves the SYNTHETIC `.feature`
# tagged `@feature-arch-probe-fixture`, never the AT's own file (plane
# separation -- dispatch invariant 3).
ARCH_PROBE_FEATURE_ID = FeatureId("arch-probe-fixture")

# The `@slice-NN` tag the synthetic fixture's `.feature` carries and the entering
# slice the SUT is driven with. A well-formed `@slice-01` (anchored `@slice-\d+`,
# no letter suffix).
PROBE_SLICE_TAG = SliceTag("slice-01")

# The structured verdict events the SUT emits (verified-from-source:
# `run_contract_gate.py:917` FeatureScopeCleared, `:841` FeatureScopeMalformed).
FEATURE_SCOPE_CLEARED_EVENT = "FeatureScopeCleared"
FEATURE_SCOPE_MALFORMED_EVENT = "FeatureScopeMalformed"
