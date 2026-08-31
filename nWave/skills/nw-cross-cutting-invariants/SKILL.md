---
name: nw-cross-cutting-invariants
description: Cross-cutting normative invariants — lean public routing core for global gate/construction doctrine and on-demand knowledge lenses. Cite clause ids; never re-declare.
user-invocable: false
disable-model-invocation: true
---

# Cross-Cutting Invariants — Recomposition Core

Normative rules hold regardless of paradigm and role. `nw-cross-cutting-invariants` is their
SHIPPED public home: cite a clause id; do not re-declare it. This core owns global
gate/construction doctrine and routes independent KNOWLEDGE lenses; load every applicable lens.

**Reachability precondition.** A pointer works only when the consumer actually loads its referent.
Check what the consumer really loads, not what it ought to; otherwise self-contain the bounded rule.
Cite skills by **NAME**, never vendor filesystem path: a path is a GDP-8 designation that can dangle
on another host.

> **Known correct exception — reviewer family.** The 22 `*-reviewer` agents have no common narrow
> skill; their absence-is-a-claim rule is deliberately inlined. Do not replace it with a dangling
> pointer.

| Phase | Load | Trigger |
|---|---|---|
| Gate or construction design | this core | designing a gate, oracle, error surface, restriction, or a construction alternative |
| Context residency | `nw-cross-cutting-context-residency` | choosing resident versus on-demand context, or repairing compensation prose |
| Evidence and instrumentation | `nw-cross-cutting-evidence-instrumentation` | asserting from a measurement, demonstrating a check, or repairing a misleading instrument/count |
| Input and data contracts | `nw-cross-cutting-input-data-contracts` | adding data, declaring inputs, choosing a join key, or diagnosing ambient reads |

The lenses are independent KNOWLEDGE: no forced sequence and no artificial precedence. A compound
task loads multiple lenses; return here only to route the next concern.

## `construction:design-paradigm-projection` — DESIGN owns the crafter paradigm

Before handing any durable DESIGN authority to DISTILL, its writer records the
resolved functional or object-oriented decision once on a `Paradigm:` line in
the cited section. A specialized domain, system or platform writer preserves
the established application paradigm; when it is absent or contested, return
the decision to `nw-design`/solution architecture. Never default an unspecified
project to object-oriented. `des compile-contract` consumes this projection
directly; root and ATD neither retype nor infer it.

## `gate:self-explaining-what-why-how` — gate and error surfaces state WHAT / WHY / HOW (STANDING)

Every gate, contract check, or error surface you design MUST, on rejection, state **WHAT**
failed (the specific invariant), **WHY** (the cause), and **HOW** to fix (the concrete
remediation, routing to the producing tool that makes the artifact valid). A gate whose
rejection is a bare `FAILED` / exit-code forces the operator to investigate — that is a
DESIGN defect, not an implementation detail. Design the self-explaining surface IN, and put
the affordance inline at the authoring point, not only in the reactive rejection (GDP-3 /
GDP-4 / GDP-2).

---

## `gate:design-principles-gdp-1-9` — Gate Design Principles GDP-0..10 (STANDING — canonical definitions)

The design contract EVERY gate, oracle, or error surface must satisfy. This skill is the
SHIPPED home of these definitions: everywhere else in the framework (skills, agents) that
cites "GDP-N" by number resolves against this list. Audit every gate you design against it;
a gap is a plan item to correct that gate. The clause id below retains its original
`gdp-1-9` suffix for citation stability (11+ existing citation sites across agents/skills/ADRs)
even though the list now runs from GDP-0 through GDP-10 — GDP-0 and GDP-10 have no heading of
their own; cite `gate:design-principles-gdp-1-9` for the whole list, GDP-0 and GDP-10 included.

- **GDP-0 — Representation before validation (STANDING, Ale 2026-08-19).** Gates are the LAST
  RESORT, never the default. Before designing a gate, name the PRODUCER that made the wrong
  state representable, and change IT so the state cannot be built: compile the mechanical
  fields, give the author the check at the moment of authoring, type the invalid value away,
  keep one writer for shared state. A gate is admitted only with a recorded reason why the
  producer cannot change, and ships with a REMOVE falsifier; three checks landing on the same
  artefact is the alarm to redesign the producer, not license to add a fourth check. Gates cost
  wall-clock and tokens at EVERY run; a construction costs once. Anchor (2026-08-19, K4 runs
  4-13): six `des dispatch` validators were added in three days, each a symptom of the
  acceptance designer hand-compiling fields the tree already derived — wall grew from 1886s to
  4553s, and the validators also lied at the language boundary.
  - **Formal-byte boundary.** If an LLM still authors formal bytes, a template, grammar, reviewer,
    or validator is not construction: it checks after the wrong state was representable. Prefer one
    deterministic sole-writer invocation that accepts semantic input and emits the formal bytes. A
    deterministic constructor or compiler counts only when it replaces that LLM formal-byte
    authorship; do not add a validator, grammar, compiler-as-gate, hook, test, mandatory artifact,
    or runtime barrier through this rule.
- **GDP-1 — Intercept EARLY (timing).** Fire at the earliest point the defect is detectable —
  BEFORE the effort it guards is spent and the value delivered. A gate that fires after
  delivery only COMMENTS, it cannot prevent. Efficacy ladder: **proactive-inline ≫
  reactive-before-completion ≫ advisory-after-completion**.
- **GDP-2 — Proactive INLINE affordance.** Only after GDP-0 admits a reactive gate, pair it with
  guidance inline at the authoring surface, so the block is rarely reached — a gate that fires is
  already too late to teach. If GDP-0 rejects the gate, remove it; do not wrap guidance around it.
  - **Emission corollary (the audit direction).** Read the pairing BACKWARDS to make it
    checkable: **a rejection you actually observe being emitted IS, by construction, evidence
    that its preventive twin is missing or too weak.** Prevention beats cure; where cure is
    unavoidable, detect early so the cure stays cheap. So an emitted rejection is not merely
    an operator's problem to fix — it is a named GDP-2 gap, and the set of rejections a system
    emits in practice is its prevention backlog, already prioritised by frequency. A rejection
    whose own text explains the COMMON CAUSE ("this usually means X was hand-assembled") is
    the sharpest case: the system knows the cause well enough to have said it BEFORE the
    effort was spent.
- **GDP-3 — Self-explaining (WHAT/WHY/HOW).** Every rejection states WHAT failed, WHY, and HOW
  to fix — directly, no investigation needed. A bare `FAILED`/exit-code is itself a defect.
  - **Omission corollary (the checkable form).** A message must not withhold a fact the
    emitting code ALREADY HOLDS. The test is mechanical: for every fact the operator needs in
    order to act, ask whether the rejecting code computed or read it before deciding to
    reject. If it did and the message omits it, that omission hands the operator an
    investigation the producer had already finished — the purest form of GDP-5's inverted
    cost. Naming a state without naming WHERE it lives, or labelling a provenance
    (`inferred`, `derived`, `default`) without naming what it was inferred FROM, are the two
    recurring shapes: a label whose antecedent is missing is not information.
- **GDP-4 — The HOW invokes the PRODUCING TOOL.** The HOW routes to the system tool that
  produces the valid artifact, never manual repair. No producing tool yet → the gate is the
  signal to build one.
- **GDP-5 — Cost on the SYSTEM.** The system produces/generates the checked artifact (hook
  injects / script generates / gate verifies); the operator never hand-assembles it.
  System-pays = capability; operator-pays = ceremony. The fix relocates the production, never
  removes the check.
- **GDP-6 — Reliability: NO silent-wrong.** Degrade-LOUD / INDETERMINATE, never false-green
  nor silently-wrong. Silent-wrong destroys trust worse than loud-fail; fix correctness before
  pushing adoption.
- **GDP-7 — Agnostic + execution-observing.** Language-agnostic (no external-tool hard-dep in
  gate logic — behind an optional degrade-loud port); where it can, OBSERVE real execution (the
  fixed floor), not merely asserted state.
- **GDP-8 — Decide on the PROPERTY, never the DESIGNATION.** A gate must key on the verifiable
  property the object HAS (what it *is* / *does* / *resolves to*), never on a name, form,
  string-pattern, or hash that merely *stands for* it. A designation matches itself, not its
  referent, so a designation-check is blind exactly where they diverge — and they diverge by
  construction (a rebase changes the SHA not the content; `python -m pytest` is named `python`;
  `..%2f` is traversal without the `../` form; `/var/tmp` is a temp dir `gettempdir()` never
  returns). Before comparing a symbol, name the property it represents and test THAT: a property
  can be stated and falsified with a known negative case; a name cannot. **Corollary — arity:**
  every outcome has ≥3 values (pass / fail / could-not-verify), and the third must reach the
  AGGREGATE (the summary line the reader sees), never collapse into pass/empty — a `10/10` while
  one check could not look, an allow-list that persists only approvals, are GDP-8 violations.
  **Corollary — witness:** the checker is not exempt from the class it checks (a form-grep for
  bare failures finds its own false positives; an examiner given one axis develops a stable
  blind spot). When the property is not locally inspectable, verification requires a SECOND AXIS
  — a different question or a differently-lensed witness, not a better single checker.
  **Corollary — authoring (declared-vs-emitted, the same disease one step upstream):** GDP-8
  guards the CHECKER against trusting a designation; this guards the WRITER against MINTING one.
  Before you name an event, record, or artifact as the basis of a rule, a contract, or a resume
  cue, ask: **does this name have a PRODUCER?** If you cannot point at the code that emits it,
  say so explicitly ("not yet built", "DESIGNED-NOT-BUILT") — a bare present-tense claim ("the
  ledger records `Foo`") is a designation with no referent, and the reader designs on top of what
  you wrote, not on what actually runs. Confirmed instances found by manual audit before this
  corollary existed: `FeatureEnd` (a repo's own DONE-definition named a ledger record with zero
  producers), `FeatureEndCycleComplete`/`Refused`/`Indeterminate` (a design doc assumed these
  were durable ledger events; they were CLI-stdout-only), `FeatureEndCheckpoint` (four shipped
  files described it as a firing resume-signal that was never implemented), and
  `DocumentationDensityEvent` (eleven citation sites claimed a telemetry event with zero
  constructor call sites anywhere in the codebase). Preserve the executable property: every
  claimed event or record must name a reachable producer and a falsifier; otherwise label it
  explicitly as designed-not-built. A prose name or catalog entry alone is never evidence.

- **Wiring corollary — CATALOGUED is not WIRED.** A module's presence in a catalog, registry,
  manifest or import list says it EXISTS; it never says it FIRES. Existence is a designation and
  firing is a property, decided only by executing the surface that should invoke it and observing
  the difference. The failure is silent by construction: the catalog entry, the passing unit tests
  and the green import all remain true of a module nothing calls. So when a fix consists of adding
  a capability, the demonstration is the CONSUMER's behaviour changing — not the capability's own
  tests going green. Read a gate's third state (`UNVERIFIABLE` / `INDETERMINATE`) as a candidate
  wiring gap before reading it as environmental: it is frequently the reachable surface reporting,
  correctly, that the thing meant to answer was never connected to it.
- **GDP-9 — Interrogative framing forces self-audit; imperative alone invites ritual
  compliance.** Phrase a standing check as a question that names the lazy alternative as the
  wrong answer ("did you just re-run X THIS turn, or are you about to restate a prior turn's
  result?"), paired with an explicit imperative for the branch where the honest answer is no
  ("if you have not just done it, do it now before answering"). An imperative alone ("always
  reverify X before answering") is followed as a rule recalled from memory, and recall decays
  into ritual compliance — the reader can believe it is complying while only pattern-matching
  to yesterday's answer, because nothing in the instruction's SHAPE forces a live check. A
  question forces the reader to evaluate a present-tense claim (did I, or didn't I, in this
  turn) before answering it, which is a different cognitive operation than executing a stored
  directive — evaluating a claim resists being satisfied by memory alone the way executing a
  rule does not. Neither half is sufficient alone: a question with no imperative fallback risks
  a literal, un-inferred answer that misses the implied correct one and fails silently (the
  reader can honestly answer "no, from memory, and that's fine" without recognizing the
  question as a trap); an imperative with no question is the ritual-compliance failure this
  principle exists to catch in the first place. Pair them. Measured across dozens of standing
  self-audit firings in one overnight session (2026-08-02): the question-plus-imperative
  pairing consistently produced a genuinely fresh re-check (a re-run `git status`, a re-issued
  grep, a re-read mtime) rather than a restated prior-turn answer, in a setting where the
  underlying facts (worktree state, ToC mention counts) DO change between firings and a
  memory-recalled answer would have gone stale silently.
- **GDP-10 — Parsimony: prefer removing/relaxing over adding a special case (STANDING, Ale
  2026-08-03 — "simplicity is the ultimate sophistication").** GDP-1..9 govern the QUALITY of a
  gate once it is justified; GDP-10 governs whether it should exist, or exist in that form, at
  all. Parsimony PRESUPPOSES GDP-0: first ask whether the producer can make the gate vacuous —
  a gate that guards a state the producer no longer permits is a special case with zero
  remaining risk, GDP-10's own paradigm case. When an edge case surfaces, the default move is
  NOT "add a new gate, token, lane, or
  scope-recognition rule to cover it" — it is to ask whether an EXISTING, more general rule
  already covers the risk, or whether the risk is small enough that a MORE PERMISSIVE answer is
  correct. Every new named exception multiplies the surface every other gate, reader, and future
  agent must reconcile against; N special cases compound combinatorially while the risk any
  single one prevents stays additive — past some point the system spends more on ceremony than
  the incidents it prevents are worth. Measured 2026-08-03: 4 Slice-Plan annotation tokens
  (`@coupled`/`@walking-skeleton`/`@infrastructure`/`@prefactoring`), 275 open rows in
  `defects.md`, and a Tier-2 AT-completeness invariant (S8, causal-sensitivity) removed the same
  day for blocking a collaborator with a value not worth its friction — the accumulation is not
  hypothetical.
  - **Corollary — name the incident before adding the restriction.** Before shipping a new
    gate/token/exception, name the SPECIFIC incident or measured risk it prevents and its
    frequency; if you cannot, the restriction is precautionary ceremony, not a fix, and the
    parsimonious default (do not add it) wins.
  - **Corollary — ceremony proportional to blast radius.** The rigor a change goes through must
    scale with what it actually risks, not with the anxiety of the moment the gap was found in —
    a zero-behavior docstring commit does not need the same examine cycle as a production
    behavior change; a bugfix to a one-off dev script does not need a full
    DISCUSS→DESIGN→DISTILL cycle merely because the spine CAN run one.
  - **Corollary — reversible removal beats irreversible accumulation.** When genuinely unsure
    whether a check earns its cost, removing it is the better default: an absent check that
    later proves load-bearing is cheap to re-add, now backed by a real incident instead of a
    hypothetical one; a check that never earns its keep is not cheap to notice or remove once a
    wave of later rules has grown to assume it is there.
  - **Corollary — existing constraints are removal candidates too, but removal needs a
    challenge.** GDP-10 is not only about resisting NEW restrictions — it licenses actively
    auditing EXISTING gates/tokens/lanes/annotations for removal, preferably against DATA (has
    this gate ever fired on a REAL defect? check the ledger/telemetry for actual catches versus
    rejections that were false-positives or pure ceremony) rather than impression. But "we
    probably don't need this" must survive a genuine CHALLENGE before removal lands — an
    adversarial pass that argues FOR keeping the constraint, citing the strongest incident it
    would have caught and the worst case if it is gone — never a rubber-stamped "seems safe,
    remove it." Skipping the challenge makes "prefer removing" decay into the SAME failure this
    principle exists to prevent, pointed the other way: a removal rubber-stamped without real
    scrutiny is agility-THEATER, not agility, and costs the system the next time the removed
    check would have caught something real. The asymmetry that justifies the extra step: adding
    ceremony wastes time repeatedly, every time the gate fires; removing a load-bearing check
    wrongly can cost far more, once, silently, later.

---

## `gate:reject-all-at-once` — one pass reports EVERY independent problem, not the first (STANDING)

**Reject-all-at-once (Ale, 2026-08-22).** A validator that stops at the FIRST problem offloads
onto its caller N cycles where one would do: every round is a full dispatch of the upstream
producer. A gate collects every INDEPENDENT problem in ONE pass and reports them together,
numbered, each carrying its own WHAT/WHY/HOW; checks that genuinely DEPEND on another stay
sequential, but the report declares which ones it could not run and why (GDP-6: the third state
reaches the aggregate). Corollary of GDP-3 (self-explaining rejection — a rejection naming one
of three defects is telling the truth about a third of the state) and of GDP-5 (cost on the
SYSTEM — N rounds of producer dispatch is exactly cost pushed onto the operator).

Anchor: `des compile-contract`, three sequential refusals on ADR-AUM-001 (2026-08-22) and four
on ADR-CFG-001 (2026-08-21) — each round a consult with the architect to fix one defect and
re-run, only to be told about the next.

**How to satisfy it.** Accumulate `problems` and `unrun` across the pass instead of returning at
the first; keep the single-problem rendering byte-identical to what it always was, so no reader
pays for the multi-problem affordance; lead a multi-problem refusal with HOW MANY, then one
numbered, independently actionable block per problem, then the checks that could not run.

**Falsifier**: one authority carrying N independent defects produces ONE refusal that lists all
N. If a second run surfaces a defect the first could have seen, this clause is violated.

**The failure this clause prevents**: a "green-by-exhaustion" loop where the producer is
re-dispatched once per defect and the operator mistakes refusal count for progress.

---

## `construction:moves-catalogue` — the six ways to make a wrong state unrepresentable, before reaching for a gate (KNOWLEDGE)

GDP-0 says the producer, not a gate, is the default fix. This catalogues the concrete moves —
each with one verified repo example, so "construct it away" is not left abstract. Before
proposing a gate/guard/hook/validator, check whether one of these already applies.

- **Compile the derivable fields.** If a value can be computed from what the system already
  knows, generate it — never let an author hand-type it. *Example*: `des dispatch` validates one
  `DeliveryContract` and emits the DELIVER handoff mechanically (`src/des/cli/dispatch.py`);
  CLAUDE.md: "Pass the `des dispatch` envelope VERBATIM — specifics belong in `--intent`, never
  in hand-edited envelope prose."
- **Give the author the check at authoring time.** Move the validation to the moment of writing,
  not a later gate. *Example*: `des charter-scaffold` copies the valid template shape into place
  and fails closed with `missing-charter-template` / `invalid-delivery-id` at scaffold time — the
  author never gets the chance to originate a malformed charter (`src/des/cli/charter_scaffold.py`).
- **Type the invalid value away.** Replace a string/bool status with a closed variant an
  exhaustiveness check enforces. *Example*: the `_Author | _Reuse | _Block | _Skip` charter-
  resolution outcome in `des.cli._charter_resolution` (shared by `resolve-charters` and
  `dispatch`) — an unhandled branch is a type error via `_assert_never`, never a silent
  fallthrough.
- **One writer for shared state.** Concurrent writers make "who last wrote this" unrepresentable
  as a single fact; give the state exactly one writer instead of a lock/check. *Example*: this
  project's own rule — "Trunk (`feature/atdd-pure-staging`) has exactly ONE writer: the
  orchestrator" (CLAUDE.md, Swarm & the shared box).
- **Pristine environments.** Let accumulated state contaminate the run and every green becomes
  unfalsifiable; run from a clean substrate instead of checking for contamination after the
  fact. *Example*: `des verify-fresh-clone` replays `DeliveryContract` verification on a clean
  checkout, so worktree-accumulated state cannot masquerade as passing evidence.
- **Producer-emitted envelope.** A human-assembled envelope can drift from what the system
  actually resolved; have the resolving tool print the envelope instead of describing it in
  prose. *Example*: `des resolve-charters` prints "one JSON line describing the closed
  EXAMINE/charter precondition" — read-only, machine-emitted, never hand-typed
  (`src/des/cli/resolve_charters.py`).

A gate is admitted only when none of these six apply and the reason is recorded (GDP-0).

---

## `gate:predicate-needs-its-own-enumerator` — a predicate without an enumerator forces every caller to invent its own population (STANDING)

A decision predicate ("is THIS one X?") and the enumerator over the population it ranges over
("which ones exist to ask about?") are two DIFFERENT responsibilities. When only the predicate
ships and no enumerator does, every caller that needs the AGGREGATE answer ("how many, or
which, of the whole set are X?") is forced to invent its own population — filtering on a
naming convention, a directory listing it happens to have on hand, or whatever subset it
already touches for an unrelated reason. An invented population is usually WRONG: it silently
under- or over-covers the real set, and the gap stays invisible because nothing computes the
true population anywhere to compare against — a caller checking 3 of 36 candidates reports
"nothing to flag" with the same confidence as a caller that checked all 36. This is a
population-scope instance of the GDP-1 timing failure: without a sweep, the predicate can only
fire reactively, at the single moment one caller happens to ask about one target — never
proactively, across the whole set, at the earliest point a defect is detectable.

Fix: when a decision is meant to apply across a set, the ENUMERATION of that set is part of the
CONTROL, not the caller's job to reconstruct. Ship the enumerator alongside the predicate (or
reuse an EXISTING one — do not build a second listing implementation for a population another
port already lists), or explicitly scope the predicate to single-target use only and say so in
its own contract. A predicate whose docs describe periodic, whole-set behavior but whose only
shipped caller queries one target at a time is a claim with no producer for the AGGREGATE case
— the GDP-8 authoring corollary above, one level up: the population itself needs a producer,
not only the per-item verdict.

---
