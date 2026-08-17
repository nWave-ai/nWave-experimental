---
name: nw-cross-cutting-invariants
description: Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
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

## `gate:design-principles-gdp-1-9` — Gate Design Principles GDP-1..10 (STANDING — canonical definitions)

The design contract EVERY gate, oracle, or error surface must satisfy. This skill is the
SHIPPED home of these definitions: everywhere else in the framework (skills, agents) that
cites "GDP-N" by number resolves against this list. Audit every gate you design against it;
a gap is a plan item to correct that gate. The clause id below retains its original
`gdp-1-9` suffix for citation stability (11+ existing citation sites across agents/skills/ADRs)
even though the list now runs through GDP-10 — GDP-10 is separately registered as
`gate:design-principles-gdp-10-parsimony` for anyone citing it specifically.

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
  all. When an edge case surfaces, the default move is NOT "add a new gate, token, lane, or
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

---

## `check:unfired-is-not-evidence` — a check you have not seen FAIL is not evidence (STANDING)

A passing check has two indistinguishable explanations: the property holds, or the check cannot
detect its violation. Green discriminates between them only AFTER the check has been observed
failing on a constructed violation. Before that, green is a fact about the instrument, not about
the subject.

Binds every instrument, not only tests:

| Instrument | Vacuous when | What earns the trust |
|---|---|---|
| negative test | the corruption is applied where the subject is not | corrupt AT the subject's own locus; watch the assertion fire |
| guard predicate | the pattern accepts the empty case (`^password=` matches an empty value) | feed the empty and near-miss forms; watch both rejected |
| gate | its arming precondition is absent, so it skips | run it on an artifact that violates the rule; watch the refusal |
| oracle inside an AT | the step derives the value it was supposed to read from the output | withhold the field; watch the step fail |

The demonstration is an ACT, never an argument: "this would obviously catch it" is the reasoning
that produced every vacuous check already shipped. Cost asymmetry — constructing the violation
costs one run; a vacuous check ships as coverage and every later reader reads its green as proof.

**Who demonstrates it, and when: the AUTHOR, immediately, with no dispatch.** Whoever writes the
check, tool, gate or script runs it against a constructed violation right after writing it and
watches HOW it fails.

**This clause governs WHO RUNS the demonstration. It says nothing about WHO WRITES the code, and
conflating the two licenses hand-authoring production code.** The two rules are orthogonal and both
bind: authorship of production code follows the dispatch discipline, while the fail-demonstration is
always the author's own act, executed on the spot. So "demonstrate it yourself, no dispatch" is an
instruction about the demonstration only — a dispatched implementer still runs its own
demonstration, and an orchestrator who reads that phrase as permission to write the code has taken
a licence the clause does not grant. Anyone handed the shorter phrasing and noticing the collision
should say so rather than pick a side silently. That is seconds of work at the authoring surface; routing it to an independent
examiner buys nothing here and costs a full handoff, because the question — *can this instrument
fire?* — is decided by execution, and the author is already holding the keyboard. Reserve an
independent reader for the different question: whether the number MEANS what the report claims.

Corollary: the FIRST version of a measuring instrument is suspect BY CONSTRUCTION — it is the only
version written before its author has seen the data, and a test written from that same first reading
inherits the misreading it was built to catch. Green unit tests certify the arithmetic the instrument
was told to do, never that the figure means what the report says it means. The check worth writing is
the one that could embarrass you.

---

## `instrument:a-reading-that-misled-you-is-a-defect-in-the-instrument` — fix the tool, not the conclusion (STANDING)

When a measurement, receipt or status report leads to a wrong action, the finding is not "I should
read it more carefully next time". The instrument is defective and the work is to REPAIR IT — vigilance
does not scale, and the next reader inherits the same trap with less context than you had.

| Step | What it means |
|---|---|
| Name the axis that lied | not "it was wrong" — WHICH signal, and what it actually measures versus what you read it as |
| Repair the instrument | and prefer removing the inference over adding a caveat: a footnote is not a fix |
| Re-run it on the case that fooled you | the repair is verified by the original counterexample reproducing the correct answer, never by the code looking better |
| Keep the counterexample | in the instrument, as a comment or a test, so the next change cannot silently restore the trap |

Two failure shapes this rule exists to stop, both observed:

- **Fixing the conclusion instead of the tool.** Correcting the one wrong verdict and leaving the
  instrument intact guarantees the same wrong verdict, and the second occurrence looks like a fresh
  mistake rather than a known one.
- **Fixing the wrong axis.** Diagnose before repairing: an instrument can produce the right complaint
  from the wrong cause, and a plausible repair then leaves the real defect in place while retiring
  the symptom that would have exposed it. Establish which signal failed by reproducing it, not by
  reasoning about which signal COULD have failed — the two diverge, and the second is faster to
  produce and satisfying to believe.

Corollary — **an instrument you run repeatedly is production code.** A report generated on a schedule
or before every decision does not get to live as an unversioned scratch script: it needs a home, a
history, and a test, because a defect in it is a defect in every decision downstream of it.

Corollary — **the guidance corpus is an instrument, and it is usually the one that failed.**
The rows above read naturally as being about measurements and receipts. They are not limited to
them: a skill, mandate, agent spec or command prose that let a defect through is a defective
instrument in exactly the same sense, and the repair is to change that prose — never a resolution
to remember harder next time.

> **After a defect is fixed, which prompt would have prevented it — and did you change that
> prompt, or only the code?** Answering "the fix is obvious now, anyone would catch it" is the
> wrong answer: the next author arrives with less context than you have at this moment, which is
> the only moment the rule is cheap to write. **If no existing rule would have caught it, add or
> sharpen one where its consumer already loads it; if one exists and did not fire, the defect is
> in its phrasing or its placement, and that is what to repair.**

Two constraints keep this from becoming prose inflation, and both come from rules already here:

- **Extend before you mint** (`gate:design-principles-gdp-10-parsimony`). Ask whether a more
  general existing rule already covers the case. A new numbered principle for something a
  corollary can carry is the ceremony that clause exists to refuse.
- **Ship the counterexample with the rule** (row 4 above, applied to prose). A normative sentence
  without the dated case that generated it erodes at the first rewrite: the next editor sees an
  assertion with no cost attached and trims it. The anchor is what makes the rule survive.

This is deliberately blame-free and forward-facing. The question is never who wrote the test or the
component that broke — it is which instruction, had it existed, would have made the class
unwritable. Empirical anchor, 2026-08-06: three CI-only failures across three suites turned out to
be one class (a test inheriting ambient host state rather than declaring it), and the durable
output of that day was not the three fixes but the mandate and the two design clauses that make the
class visible at authoring time.

---

## `contract:declared-inputs-not-ambient-reads` — what does this READ that nobody passed it? (STANDING)

Paradigm-independent, and it applies to a component, a function and a test alike.

> **List everything the behaviour is gated on, then ask which of those it RECEIVES and which it
> goes and reads.** Answering "it works on my machine and in CI" is the wrong answer — that is
> two samples of one environment class, and the gate is invisible in both. **If any gate is read
> rather than received, lift it into the contract** — a parameter, an injected capability, an
> explicit override — and keep the ambient lookup as a default the caller may state, never as the
> only source.

The gates worth walking, as one list so it cannot drift between copies: **host or platform
presence · `$HOME` · a resolved config directory · cwd · `PATH` · environment variables · the
clock · locale · network reachability**.

Why it is not a style preference:

- A component whose result depends on state absent from its inputs takes a different branch in a
  different environment and reports honestly about a question nobody asked it.
- Its tests are the first casualty. They pass on the author's machine, on any machine that
  resembles it, **and because a sibling test created the state first** — which makes them
  order-dependent with nothing in the source saying so. A `tmp_path` fixture is not evidence:
  isolating the filesystem is not isolating the environment.
- A property test cannot reach the cases ambient state is silently fixing, so the generator looks
  thorough while the interesting partition is unreachable.

Empirical anchor, 2026-08-06: `NWaveInstaller.effective_target_platforms` resolves the target host
by ambient detection, lazily at first use. Three separate suites reached a no-host early return on
CI instead of the behaviour they asserted; each was repaired by declaring the platform, and each
took several refuted hypotheses to diagnose, because a component that reads ambient state gives no
signal about WHICH state it read.

Consumers: `nw-code-design-oo` and `nw-code-design-fp` (design-time, per paradigm) and the
Algebraic Analysis Before the Scenario mandate in `nw-test-design-mandates` (authoring-time).
They reference this clause; they do not restate the list.

---

## `provenance:a-count-without-a-sender-is-not-attributable` — name who wrote the record before it becomes evidence (STANDING)

A count extracted from a SHARED log or ledger is a claim about the SENDER of each record, not only
about the event it names. Before a count feeds a ranking, a defect row, or a dispatch decision, the
question is not "how many?" but "who wrote each one, and is that population the one the claim is
about?" A number is not evidence until that second question has an answer.

MEASURED 2026-08-03: an audit counted 225 `DES_MARKERS_MISSING` block records from a shared PreToolUse
log and concluded a re-fire pattern existed across four step-ids, ranking a detector as the top fix
candidate. The count was real; the attribution was not checked. 224 of the 225 records were written by
the project's OWN acceptance suite — two test files pointed the tool at the real repo instead of an
isolated one, defeating an isolation fixture, and every test run deposited identical records into the
SAME shared log a real dispatch would write to. The suite and the product were indistinguishable in
the log, because the log carries no field that reliably separates them (`run_context`/`subagent_type`
were checked and do not discriminate). Cost of the unattributed count: a fix was dispatched against a
defect that did not exist, and a downstream ranking (which mechanism to fix first) was wrong until the
attribution was checked.

**The check that actually discriminates, when the log has no reliable sender field**: cluster by
BURST, not by a fixed count threshold. Machine-generated repetition (a test loop, a retry storm) fires
at machine cadence — sub-second gaps, tight clusters of near-identical size — while independent
real-world events do not share that rhythm. Measured: 263 records clustered into 102 bursts by a
<500ms gap boundary; bursts of 5-7 records were, without exception, the SAME reason repeated at a
median 30ms internal gap, concentrated on a handful of calendar days — the signature of a test loop,
not of an agent retrying a blocked dispatch. The singletons left over after excluding bursts were the
population the original claim should have been about.

Corollary — **a shared substrate that a test suite writes into by design, and mitigates only by
SERIALIZING (never isolating), keeps producing this trap indefinitely.** If ~N test suites are
documented as deliberately pointing a tool at the real, shared state (not a fixture copy) because
isolating them was harder than serializing their access, then every count taken from that shared
state carries an unknown contamination fraction FOREVER, not just once — the fix is not re-deriving
the attribution each time a number is needed, it is closing the shared-write path itself (see
`des-acceptance-suite-writes-into-the-production-audit-trail` /
`observability-substrate-does-not-separate-production-from-test-writes` in this project's
`defects.md` for the concrete instance).

---

## `join-key:shape-conformance-over-uniqueness` — a borrowed identifier is not a key until its shape is declared (STANDING)

A field supplied by an external producer — a platform, a harness, another team's payload — is
not a join key until EVERY value in the population conforms to a declared id shape. A single
non-conforming value disqualifies the field, however rare. The tempting weaker test is
"measure whether it is unique": that test passes on exactly the fields that hurt most, because
the usual defect is not a field that collides often but a field that is a well-formed
identifier almost everywhere and carries a hardcoded literal — a lifecycle-event name, a
placeholder, a fallback string — in a small minority of records. Rarity is not safety here; it
is the reason the field survived every informal check that came before. A join keyed on such a
field silently folds unrelated records together, and a reader that takes first-wins or MAX over
the group discards the rest without reporting anything.

Two properties make shape the right test rather than a proxy for uniqueness. It is
LOCALLY DECIDABLE: a checker holding one record can decide whether that record's value is
well-formed, whereas uniqueness is a property of a population the checker usually never sees —
a rule that cannot be executed at the point it is needed is not a control. And it is
DISCOVERABLE WITHOUT FOREKNOWLEDGE: conformance finds the offending values in one pass without
anyone knowing in advance which literal to look for, while a sampling check must draw the rare
value AND notice it collides.

**A key must be exercised at N≥2, and a one-occurrence suite cannot test one at all.** Ask what the
candidate is addressed BY: an EVENT key is unique per occurrence; a CONTENT key is unique per
payload, and the two are indistinguishable until two occurrences carry the same payload. Measured
instance: a hook's stdout digest was adopted as the parent↔child join, and the hook's stdout is a
module constant — two firings produced 2 parents and exactly **1** distinct digest, so every child
joined BOTH parents and the reader emitted a silent cross product. Every scenario that had validated
that key fired exactly ONCE, which is why the whole suite was green: a single-firing test makes the
defect structurally unreachable, so it was never a weak test but a test of the wrong thing. The
remedy is not more assertions, it is a second occurrence — and where a content key must be carried
anyway (it is often the only value both sides can compute), it carries a mandatory
`join_key_collision` third state, and the collision must be COUNTED and reported rather than
resolved by picking one of N.

The shape itself must be written down LITERALLY — the accepted pattern, and which
near-miss forms are excluded. "Conforms to an id shape" is not a specification: two honest
implementers will resolve an ambiguous form differently and reach opposite verdicts on the same
data, which reproduces the original silent-wrong one level up. Where a borrowed field must be
carried for a best-effort correlation it cannot guarantee, carry it as an ATTRIBUTE and mint
the structural key yourself: a key you generate is one whose uniqueness you own rather than
assume. When a value fails the shape check, the record degrades to the third state with a
reason naming the field — never to a silent drop, and never to a guess at which group it
belonged to.
