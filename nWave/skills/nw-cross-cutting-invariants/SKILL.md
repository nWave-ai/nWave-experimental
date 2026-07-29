---
name: nw-cross-cutting-invariants
description: Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..8, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
user-invocable: false
disable-model-invocation: true
---

# Cross-Cutting Invariants

Normative rules that hold **regardless of paradigm** (object-oriented or functional) and
**regardless of role** (architect, crafter, designer). They live here once so that a citation
elsewhere resolves to one definition instead of drifting copies.

**This skill is the SHIPPED home of these definitions.** Anywhere in the framework that cites a
clause id below resolves against this file. Do not re-declare a clause in another asset — cite it.

**Reachability precondition, and it has bitten before.** Collapsing a rule here and pointing at
it works ONLY if the consuming context actually LOADS this skill. A pointer from an asset whose
agent never loads this file is a designation with no reachable referent — the exact GDP-8 disease,
reintroduced by the remedy. Before replacing any rule with a pointer, check which skills the
consuming agent really loads, not which it ought to. A consumer that cannot load this skill must
**self-contain** the rule (bounded, deliberate duplication), never carry a dangling pointer.

**Reachability has TWO axes — the second is the host.** *Does the agent load this skill?* is only
half the question. The other half is *can it resolve the reference on the host it is running on?*
Cite a skill by **NAME** (`nw-cross-cutting-invariants`), never by a vendor-specific filesystem
path: an installed asset runs on hosts whose skill directory is not the one the author had
(`.claude/`, and the Codex / Copilot / OpenCode equivalents). A path-shaped citation resolves for
the author and dangles everywhere else — a designation that stands for a location instead of the
artifact, GDP-8 one layer down. Name-shaped citations let each host's own resolution do its job.

> **Known and correct exception — the reviewer family.** The 22 `*-reviewer` agents each load a
> different, narrow skill set with no common member. The absence-is-a-claim rule
> (ABSENT-VERIFIED vs NOT-FOUND-IN-MY-SCOPE, coverage as a fraction) is therefore **inlined in
> each reviewer spec on purpose**. That duplication is the correct treatment under the
> reachability precondition above — do NOT "fix" it by replacing those copies with a pointer
> here; doing so silently disarms the rule in all 22.

---

## `data:consumer-known-before-produced` — a datum is produced because we already know who needs it (STANDING)

**A datum is justified only by a named consumer.** Before adding a field, an event, a config key,
an artifact section, or a telemetry record, name **who reads it** and **through which mechanism**.
No named reader → the datum is unjustified and must not be added. This is not bookkeeping
hygiene: unread data is what makes a system incoherent, because every future reader must decide
whether it means something and none can tell.

**Second half, and it is the one that gets forgotten: name the JOIN KEY.** Knowing who reads a
datum is not enough — it must be indexable against what the reader already holds. Two data both
faithfully consumed, indexed on keys that do not meet, cannot be related: the information exists
and is unusable. State the key the consumer will join on, at the moment you declare the field.

Measured instances of the failure, all in this repository:

| Datum | Declared | Consumed |
|---|---|---|
| `inline_in_feature_delta` | was 4 wave contracts + 1 schema | **0** reads — REMOVED 2026-07-28 once measured; kept here as the worked example |
| `adr-refs` (`RefList`) | its own definition | **0** dereferences |
| `skill_tracking` | full transcript-mining service exists | default **`"disabled"`** |
| `RedObserved` / `SliceCommitVerified` | both genuinely consumed | **no common key** — duration not computable from either ledger |

The last one is the instructive case: both data are read by someone. They still cannot answer
"how long did this slice take to go green", because one is keyed by feature+slice+time and the
other by test-file content hash. A consumer was known; the join was not.

**Corollary — instrumentation that must be switched on is not instrumentation.** A datum whose
producer defaults to off (see `skill_tracking`) is unjustified in the same way as one with no
reader: on the machine where it matters, nobody enabled it. Default it on, or do not claim the
measurement exists.

---

## `context:pay-on-demand-not-every-session` — resident context is paid every session (STANDING)

**Whoever needs it loads it; whoever does not need it must not pay for it in every session.**
Context injected at session start is a per-session tax on every reader, including the readers who
will never touch that subject. Detail belongs where it is needed, at the moment it is needed — not
resident.

Three residency classes; classify before you inject anything:

- **MUST-BE-RESIDENT** — if it is absent from context, it does not happen. The load-bearing case is
  a **trigger**: an instruction to arm, to check, to refuse. Nobody goes looking for what they do not
  know exists, so a trigger cannot be made reachable-on-demand — its absence is silent. Same for a
  safety warning whose omission causes harm before anyone would think to consult it.
- **MAP-ONLY** — the reader must know THAT a thing exists and roughly WHEN to reach for it. Not how
  it works. A name plus a one-line "reach for this when…" is the whole resident cost.
- **REFERENCEABLE** — pure detail, needed only by whoever is doing that specific thing.

**Density is a second axis, independent of residency.** Normative content cannot be GENERATED from
code, but it can be COMPRESSED: doctrine is usually rules — subject · condition · action — written
as narrative. A table says the same thing in a fraction of the bytes and reads better. Do not confuse
"not derivable" with "not compressible"; measuring the first tells you nothing about the second.

**The failure this clause prevents**: a projection that ADDS instead of REPLACING. Retiring a
duplicate is a saving; generating a new view beside a surviving hand-written one is a new divergence
surface AND a bigger payload.

## `context:resident-doctrine-can-be-compensation-debt` — resident prose that patches bad guidance is debt (STANDING)

When a body of resident context exists to compensate for guidance that **fails to arrive at the point
of need**, that context is not doctrine — it is **debt**, and it is the SECOND cost of a defect whose
first cost is already being paid at the gate.

The chain: a gate refuses reactively instead of guiding at the authoring surface (the GDP-2 emission
corollary) → readers keep getting caught → someone compensates by injecting standing prose into
every session → now everyone pays, every session, for a message that should have arrived once, in
place, to the one person who needed it.

**So, before adding anything to a resident payload, ask: is the real gap a MESSAGE that fails to
guide?** If yes, fix the message; the resident need dissolves rather than being served. And the
converse is the practical lever: **as guidance moves to the point of need, resident doctrine can thin
without losing anything** — the two workstreams compose, and the thinning is only safe in that order.

**Do not thin first.** Removing resident prose while the corresponding guidance still arrives too
late removes the compensation and keeps the defect.

## `gate:self-explaining-what-why-how` — gate and error surfaces state WHAT / WHY / HOW (STANDING)

Every gate, contract check, or error surface you design MUST, on rejection, state **WHAT**
failed (the specific invariant), **WHY** (the cause), and **HOW** to fix (the concrete
remediation, routing to the producing tool that makes the artifact valid). A gate whose
rejection is a bare `FAILED` / exit-code forces the operator to investigate — that is a
DESIGN defect, not an implementation detail. Design the self-explaining surface IN, and put
the affordance inline at the authoring point, not only in the reactive rejection (GDP-3 /
GDP-4 / GDP-2).

---

## `gate:design-principles-gdp-1-8` — Gate Design Principles GDP-1..8 (STANDING — canonical definitions)

The design contract EVERY gate, oracle, or error surface must satisfy. This skill is the
SHIPPED home of these definitions: everywhere else in the framework (skills, agents) that
cites "GDP-N" by number resolves against this list. Audit every gate you design against it;
a gap is a plan item to correct that gate.

- **GDP-1 — Intercept EARLY (timing).** Fire at the earliest point the defect is detectable —
  BEFORE the effort it guards is spent and the value delivered. A gate that fires after
  delivery only COMMENTS, it cannot prevent. Efficacy ladder: **proactive-inline ≫
  reactive-before-completion ≫ advisory-after-completion**.
- **GDP-2 — Proactive INLINE affordance.** Pair the reactive gate with guidance inline at the
  authoring surface, so the block is rarely reached — a gate that fires is already too late to
  teach. Keep the gate, ADD the inline guidance.
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
  constructor call sites anywhere in the codebase). `des verify-declared-events` mechanizes this
  check across shipped prose (skills, agents, commands, CLAUDE.md, permanent ADRs): every claimed
  event/record name is cross-checked against a producer registry scanned from source,
  PASS/FAIL/INDETERMINATE — never a silent pass over a phantom name.

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

## `claim:falsify-before-asserting` — the cheapest check precedes the conclusion (STANDING)

Before concluding that something cannot work, is missing, or is broken, run the cheapest check
that would falsify that conclusion, then state only what the check showed. Name a cause only if
you observed it — never infer one from a shared symptom. Absence in one place is not absence in
the tree: measure on the scope the claim is actually ABOUT, not the subset you happened to look
at (the enumerator gap above is the architectural form of this same failure). The asymmetry that
justifies the discipline: the check costs seconds; an unfalsified conclusion, once acted on,
costs an order of magnitude more to undo.
