"""Typed domain vocabulary for f-attest-bundled-slice slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum / frozen value, so the composition
methods consume typed parameters (no raw ``str`` where an enum exists). These
types are TEST-LOCAL -- they never import production code; the ATs drive the SUT
only through the composition-root driving port (Mandate-13, Layer 3 subprocess).

slice-01 surface: the CLI SCAFFOLD + the shared-core extraction. The observables
are the dispatcher's recognition of the ``attest-bundled-slice`` subcommand, the
``--reason required=True`` argparse posture, the presence + identity of the new
``src/des/cli/_reverify_core.py`` shared core, and the BEHAVIOURAL preservation of
``des reverify-slice-commit`` (its existing acceptance suite re-runs green AND its
core helpers now resolve to the shared module).
"""

from __future__ import annotations

from enum import Enum


class AttestExit(Enum):
    """The operator-visible exit-code contract slice-01 drives ON.

    The seam the AT asserts on (the process exit code the command ships), never a
    line number. Values are the literal process exit codes the DESIGN
    ``des attest-bundled-slice`` CLI contract table (feature-delta sec.4) pins for
    the slice-01 scaffold surface.
    """

    # Success path -- not reachable in slice-01 (gates/preconditions land in
    # slices 02-04); named for vocabulary completeness across the shared steps.
    SUCCESS = 0
    # A precondition refusal (e.g. empty/whitespace --reason -> SliceAttestRefused).
    REFUSED = 1
    # Malformed input (bad --slice-id) OR argparse usage error (missing --reason).
    # Both surface as exit 2 -- the floor untouched, no ledger/audit write.
    USAGE_OR_MALFORMED = 2


class CoreSymbol(Enum):
    """The reverify helpers slice-01 extracts into ``src/des/cli/_reverify_core.py``.

    The shared core BOTH ``reverify_slice_commit.py`` AND ``attest_bundled_slice.py``
    import verbatim (feature-delta sec.3 reuse mandate). The AT proves the module
    exposes these symbols AND that reverify's own CLI now resolves them FROM the
    shared core (identity), not a private copy -- the no-parallel-attestation-path
    guarantee (the ``F-DES-LEDGER-BYPASS-GATE`` failure class).
    """

    COMPOSE_GATES = "_compose_gates"
    RECORD_OUTCOME = "_record_outcome"
    RUN_GATE = "_run_gate"
    IN_COMMIT_AT_PRESENCE = "_in_commit_at_presence"
    TRACKED_BEFORE_AT_PRESENCE = "_tracked_before_at_presence"
    PATH_IN_COMMIT_TREE = "_path_in_commit_tree"
    PREDECESSOR_VERIFIED = "_predecessor_verified"
    ORPHAN_STATE = "_orphan_state"
    EMIT = "_emit"
    REFUSED = "_refused"
    MALFORMED_INPUT = "_malformed_input"


class AttestEvent(Enum):
    """The terminal stdout JSON ``event`` names the attest CLI emits.

    slice-02 drives ON the precondition-refusal vocabulary (feature-delta
    sec.4 / sec.5): the REUSED preconditions P1/P3/P5/P6 each fail-closed with
    ``SliceAttestRefused`` (exit 1). The slice-01 SCAFFOLD marker
    ``BundledSliceAttestNotApplicable`` is the active-RED hook: at HEAD the
    scaffold emits it (exit 0) for EVERY invocation, ignoring the preconditions
    entirely -- so a fixture that MUST refuse currently gets NotApplicable, and
    the refusal assertion fires until slice-02 DELIVER wires the preconditions.

    P3's corrupt-ledger -> ``LedgerIntegrityViolation`` branch is INHERITED
    VERBATIM from ``_reverify_core`` and already covered by reverify's own
    acceptance suite, so it is NOT re-tested (and thus NOT vocabularised) at
    attest slice-02 -- no duplication.

    These are TEST-LOCAL string constants of the observable event names, never
    a production import -- the AT drives the SUT only through the dispatcher
    subprocess (Mandate-13, Layer 3).
    """

    # A REUSED precondition (P1/P3/P5/P6) fail-closed refusal -- exit 1.
    REFUSED = "SliceAttestRefused"
    # The slice-01 scaffold marker -- the active-RED hook (preconditions
    # un-wired at HEAD, so EVERY invocation emits this regardless of fixture).
    NOT_APPLICABLE = "BundledSliceAttestNotApplicable"
    # The slice-02 proceed-past seam (every reused precondition cleared). At HEAD
    # an all-precondition-clear A2 fixture (valid trailer, AT present, buried,
    # predecessor-clear) reaches THIS event (exit 0) because the slice-03 A2
    # evidence check + gate composition are not yet wired -- the active-RED hook
    # for the A2.c deferred-scenario refusal AT (slice-03 / sec.11 row 3). It is
    # ALSO the slice-04 active-RED hook: at HEAD a fully-clear fixture reaches
    # THIS placeholder (exit 0) WITHOUT running the gates or touching the ledger,
    # so the slice-04 success/block/ledger assertions all fire until DELIVER
    # replaces the placeholder with the gate composition + ledger emit.
    PRECONDITIONS_CLEARED = "BundledSliceAttestPreconditionsCleared"
    # The slice-04 success terminal -- emitted to stdout when both gates (E1+E2)
    # pass: the run appended a genuine SliceCommitVerified record AND the adjacent
    # SliceAttestedFromBundle provenance record, exit 0 (feature-delta sec.4 /
    # sec.5 step 7). At HEAD main() stops at PRECONDITIONS_CLEARED, so this is
    # never emitted -- the active-RED hook for the success ATs.
    ATTESTED_FROM_BUNDLE = "SliceAttestedFromBundle"
    # The slice-04 gate-fail terminal -- emitted when a gate (E1 or E2) fails:
    # the run appended one SliceCommitBlocked and emitted SliceAttestBlocked
    # naming the failing gate, exit 1, and NO SliceCommitVerified (the
    # anti-theater guarantee -- red ATs are never attested). Never emitted at
    # HEAD (the placeholder runs no gate) -- the active-RED hook for the block AT.
    ATTEST_BLOCKED = "SliceAttestBlocked"


class LedgerEvent(Enum):
    """The ledger-record ``event`` names the slice-04 success/block paths APPEND.

    Distinct from ``AttestEvent`` (the terminal stdout JSON the CLI emits): these
    are the HMAC-chained records ``_record_outcome`` appends to the AT-completion
    ledger ``.jsonl`` file. slice-04 reads the ledger file AS DATA (raw JSON
    lines), never importing ``AtCompletionLedger`` -- the driving-port-only
    boundary (Self-Review item 13 / F-005 / slice-02 RC-2). The data assertions
    key on these literal event strings.

    The success path appends TWO adjacent records (feature-delta sec.4):
      1. ``SliceCommitVerified`` -- the origin-blind, M8-visible, scorecard-counted
         record, byte-shape-identical to a U2-/reverify-minted one. This is the
         record that makes the bundled slice COUNTABLE.
      2. ``SliceAttestedFromBundle`` -- the LOUD provenance audit marker carrying
         ``{slice_id, bundle_commit, reason, timestamp}``; M8-/scorecard-ignored,
         but a ledger audit reader can trace which verifications came through the
         bundle path and on whose stated authority.

    The gate-fail path appends ONE ``SliceCommitBlocked`` record (reverify
    vocabulary) and -- critically -- NO ``SliceCommitVerified`` (the anti-theater
    guarantee).
    """

    # The origin-blind, scorecard-counted verification record (success path).
    SLICE_COMMIT_VERIFIED = "SliceCommitVerified"
    # The loud provenance audit marker (success path), carrying reason+bundle_commit.
    SLICE_ATTESTED_FROM_BUNDLE = "SliceAttestedFromBundle"
    # The gate-fail block record (block path) -- NOT a verification.
    SLICE_COMMIT_BLOCKED = "SliceCommitBlocked"


class GateOutcomeFixture(Enum):
    """The slice-04 gate-composition + ledger-mutation fixtures.

    slice-04 composes the two REAL gates (E1 ``check_slice_at_completeness`` +
    E2 ``run_contract_gate``) via the shared ``_compose_gates`` and records the
    outcome via ``_record_outcome``. Each fixture names a temp-git repo whose
    bundle slice's ATs genuinely PASS or FAIL the contract gate -- the
    load-bearing realism: E2 runs the real suite, so the fixture must carry a
    real contract-marked test that really goes green (success) or red (block).
    """

    # Both gates pass: a buried bundle slice carrying the @slice-NN .feature AT,
    # a valid Slice-Id trailer, AND a GREEN contract-marked test so E2's real
    # whole-tree suite run exits 0. The success path: SliceCommitVerified +
    # SliceAttestedFromBundle appended, exit 0.
    GREEN_BUNDLE_SLICE = "green_bundle_slice"
    # E2 fails: the same buried bundle slice shape but carrying a RED
    # contract-marked test, so E2's real suite run exits non-zero. The block
    # path: SliceCommitBlocked appended, SliceAttestBlocked emitted, exit 1, and
    # NO SliceCommitVerified (the anti-theater guarantee).
    RED_CONTRACT_SUITE = "red_contract_suite"


class AttestFixture(Enum):
    """The slice-02 precondition fixtures, one per REUSED precondition refusal.

    Each names a temp-git repo / ledger shape that the corresponding REUSED
    ``_reverify_core`` precondition MUST refuse once slice-02 DELIVER wires it.
    The fifth fixture is the all-clear shape (P1/P3/P5/P6 all satisfiable) the
    command must PROCEED past, never refusing on a precondition.
    """

    # P1 -- the bundle commit is NOT an ancestor of HEAD (a side-branch commit).
    NON_ANCESTOR = "non_ancestor"
    # P3 -- the slice already carries a SliceCommitVerified ledger record.
    ALREADY_VERIFIED = "already_verified"
    # P5 -- the bundle commit IS HEAD (not strictly buried).
    STILL_HEAD = "still_head"
    # P6 -- slice-03 whose predecessor slice-02 carries no verified record.
    PREDECESSOR_UNVERIFIED = "predecessor_unverified"
    # all-clear -- P1/P3/P5/P6 all pass; the command proceeds past them.
    ALL_PRECONDITIONS_CLEAR = "all_preconditions_clear"


class A2Fixture(Enum):
    """The slice-03 A2 bundle-evidence fixtures (the P2 replacement).

    slice-03 replaces reverify's inherited P2 (trailer-name-must-CONTAIN-slice)
    with A2 = A2.a real-AT presence (P4 promoted to binding evidence) + A2.b
    TWO-BRANCH carpaccio/wave-trailer presence + A2.c no-``@skip``/``@xfail`` scan.
    Each fixture names a temp-git repo shape the A2 conjunction must refuse OR
    pass. The shapes are built so each AT is active-RED for the RIGHT semantic
    reason against HEAD's slice-02 ``main()`` (which still composes the strict
    inherited P2/P4 via ``_preconditions``) -- see the per-fixture builder.
    """

    # A2.a refusal -- the bundle commit (and commit~1) carry NO @slice-NN AT,
    # yet a valid Slice-Id: trailer NAMES the slice. Once P2 is replaced by A2,
    # the ONLY refusal ground is A2.a (absent AT). At HEAD the inherited P4
    # refuses too, but with the reverify-vocabulary diagnosis -- the oracle
    # discriminates the A2.a diagnosis from the inherited P4 text.
    NO_SLICE_AT = "no_slice_at"
    # A2.b refusal -- the bundle commit carries the @slice-NN AT but has NEITHER
    # a Slice-Id: NOR a Step-Id: trailer line (an arbitrary non-spine hotfix).
    # Both A2.b branches fail -> refused. At HEAD inherited P2 also refuses but
    # with its reverify-vocabulary text -- the oracle discriminates.
    NO_TRAILER = "no_trailer"
    # A2.b branch-2 PASS (THE CRUX) -- a Step-Id: <feature>-design-only bundle
    # commit (extract_slice_ids -> [], but a raw Step-Id: line IS present),
    # carrying the @slice-NN AT. branch 2 (_has_step_id_line) passes -> the run
    # is NOT refused on the trailer ground; it proceeds to the gate/ledger tail
    # (slice-04). At HEAD inherited P2 REFUSES it (slice ∉ extract_slice_ids) --
    # so the proceed assertion is active-RED.
    STEP_ID_ONLY = "step_id_only"
    # A2.b branch-1 PRESENCE / THE CANONICAL BUNDLE CASE (feature-delta sec.11
    # row 3) -- a Slice-Id: trailer naming a DIFFERENT slice (slice-99) while the
    # commit carries THIS slice's (@slice-01) AT. The f-deliver-wave-migration
    # shape (bundle 18b1930f5 with `Slice-Id: slice-01` covering slices 02+).
    # extract_slice_ids -> ['slice-99'], so A2.b branch 1 is bool(['slice-99'])
    # = True (PRESENCE, NOT slice ∈ membership) -> NOT refused on the trailer
    # ground. This pins A2.b branch 1 as PRESENCE: a DELIVER implementing
    # MEMBERSHIP (slice_id in extract_slice_ids) would pass STEP_ID_ONLY + the
    # three refusals yet REFUSE this canonical case -> break f-deliver's unblock.
    # At HEAD inherited P2 REFUSES it ('slice-01' not in ['slice-99']) -> the
    # proceed assertion is active-RED.
    DIFFERENT_SLICE_TRAILER = "different_slice_trailer"
    # A2.c refusal -- the @slice-NN scenario carries an @xfail tag (deferred /
    # expected-fail theater). A2.c scans the matched .feature for
    # @skip/@xfail/@wip and refuses. At HEAD all of P1-P6 pass (valid trailer,
    # AT present, buried, predecessor-clear) -> the run PROCEEDS past the
    # preconditions (exit 0) -- so the A2.c refusal assertion is active-RED.
    XFAIL_SCENARIO = "xfail_scenario"


# The reverify-vocabulary refusal-diagnosis fragments the INHERITED P2/P4
# emit at HEAD. slice-03's A2.a / A2.b refusals MUST carry an A2-specific
# diagnosis instead -- these fragments are the discriminating oracle: present
# in the HEAD (inherited-precondition) refusal text, ABSENT once A2 replaces
# P2/P4. An A2.a / A2.b refusal whose error still quotes these is the HEAD
# scaffold, not the wired A2 -- the active-RED hook for AT1 + AT3.
#
# P2 (trailer-name) refusal text -- _reverify_core._preconditions:159-162.
REVERIFY_P2_DIAGNOSIS: str = "is not in the commit's trailer set"
# P4 (in-commit AT presence) refusal text -- _reverify_core._in_commit_at_presence:285-289.
REVERIFY_P4_DIAGNOSIS: str = (
    "the slice's acceptance tests must live in the commit itself"
)


# The literal sanctioned subcommand name slice-01 registers in the dispatcher
# _REGISTRY. At HEAD this name is UNREGISTERED -- the real ``des`` dispatcher
# rejects it with ``invalid choice: 'attest-bundled-slice'`` (exit 2), the
# active-RED command-not-found signal.
ATTEST_SUBCOMMAND: str = "attest-bundled-slice"

# The mandatory human-GO argument (argparse ``required=True``, the wave-clear
# precedent). A genuine missing-``--reason`` usage error NAMES this argument in
# stderr; the HEAD unregistered-subcommand error does NOT -- the discriminating
# oracle that keeps AT2 RED at HEAD and GREEN only once the CLI exists.
REASON_ARGUMENT: str = "--reason"
