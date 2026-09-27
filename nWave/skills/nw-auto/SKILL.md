---
name: nw-auto
description: Evaluates and revises Request S/M/L and delivery choices from evidence, then uses DES steps to deliver it.
user-invocable: true
argument-hint: '<request>'
---

# NW-AUTO

Before creating or inheriting a lane, or finalizing/resuming its cleanup,
apply the worktree lifecycle in `nw-throughput`. If not already loaded, MUST
resolve that skill through the host skill catalog and read its `SKILL.md`.

Before diagnosing or assigning corrections, load `nw-cross-cutting-invariants`
and apply `delivery:trustworthy-baseline-and-repair-scope`. A blocking observation
requires attention; it does not alone authorize an independent repair.


You orchestrate. DES constructs durable facts and, when asked, human-readable
documents. Each DES step measures, constructs, or enacts one operation, then
returns that operation's result. DES records the resulting facts and may report
missing required input, a write conflict, or another result of that single
operation. The LLM evaluates those observations and chooses the next supported
operation. There is no command that runs this loop for you, and a script that
chains the steps is the defect this design removed.

Read `~/.claude/skills/nw-role-invocation/SKILL.md` when delegating to a role:
use the exact installed role natively, or the DES operation in section 2 that
buys it; never a generic fallback. Constructors (`--input`) buy no turn.

## 1. The loop

```bash
des state --repo-root ABSOLUTE_ROOT
```

`des state` reads the open Request and prints advisory `NEXT` suggestions with
their exact invocation forms. Evaluate that evidence with the current Request,
then choose a supported operation; `NEXT` may be ignored. When you use a suggested
command, take its argv from the block rather than memory. Start a Request that
has no state yet:

```bash
printf '%s' "$REQUEST" | des po --repo-root ABSOLUTE_ROOT --feature FEATURE_ID
```

Keep the complete Request on stdin. Send additional scope context separately:

```bash
printf '%s' "$REQUEST" | des po --repo-root ABSOLUTE_ROOT --feature FEATURE_ID --finding "$SCOPE_CONTEXT"
```

`--operational-facts` takes the repository-relative path of the canonical
`OperationalFacts v1` JSON sidecar produced by `des devops`. It does not take
Markdown or a scope note. To correct an existing PO decomposition, put the
finding on stdin and use `des po --finding -`; the stored Request is preserved.

`NEXT` is advisory data, never an execution instruction. DES neither maps a
size label to a route nor invokes a successor; the LLM does both from evidence.

## 2. Public operations

This table describes observed inputs and outputs; it is not a required sequence.

| Step | What it leaves behind |
|---|---|
| `des devops` | operational constraints in the durable authority when that command is applicable. |
| `des po` | the Request stored, cut by the Product Owner into ordered values. |
| `des design --value N` | one architect turn produces and binds typed design facts. |
| `des design --value N --input -` | constructs the DESIGN document and binds facts from the supplied complete JSON manifest; no role turn. |
| `des design --shared --input -` | constructs and binds the common feature contract from a complete DESIGN manifest; no role turn. |
| `des oracle --value N` | the public oracle of value N, written at its locator and executed RED. |
| `des craft --value N` | the change for value N, recorded. |
| `des verify` | one candidate commit and persisted native evidence; the LLM separately invokes reviewer and examiner. |
| `des prepare-role --role reviewer --candidate SHA` | one persisted, candidate-bound reviewer input; it invokes no model and executes no native command. |
| `des prepare-role --role examiner --candidate SHA --observations PATH` | validates and seals caller-captured public observations into one candidate-bound examiner input; it neither captures, selects, nor judges events, and executes no native command. |
| `des record-role-result --role reviewer\|examiner --candidate SHA --input -` | one typed, host-supplied role observation bound to its prepared input; the LLM selected and ran the role. |
| `des invoke-role --role reviewer\|examiner --candidate SHA --provider PROVIDER --input INPUT` | one explicitly selected configured provider invocation for that single role, with no fallback or successor. |
| `des integrate` | the candidate on the destination, and no Request stored. |
| `des state` | nothing. It reads where the Request stands. |
| `des project` | nothing. It renders the human-readable projection. |

Current commands can report missing required input or recorded data, a write
conflict, or the result of the single operation they performed. Their
`WHAT`, `WHY`, and `HOW` lines describe that runtime result; they do not choose
a route. The LLM decides whether to gather more evidence, select another
supported operation, or correct upstream authority.

`des integrate` performs only recorded candidate identity checks, compare-and-swap,
and cleanup mechanics. Reviewer and examiner observations do not admit or block
that operation; the LLM decides whether its evidence justifies invoking it.

The floor is never switched off. Craft requires the appropriate recorded oracle.
The LLM obtains independent review and source-blind EXAMINE through the separate role commands after native verify. How WIDE the oracle and examination must be is
measured from what the candidate touched, and printed as a fact.

## 3. Reading the block

```text
DELIVERY-OUTCOME: Success | Refusal | Retry | Indeterminate
<LABEL>: <fact>            -- zero or more measured rows
WHAT / WHY / HOW           -- present when the outcome is not Success
ORCHESTRATOR: ...          -- derived from the rows above, never authored
DIAGNOSTIC: ...            -- a role's own words, when a role spoke
NEXT: <invocation>         -- one, or more than one
HOW-TO-INVOKE: ...
```

| Outcome | What you do |
|---|---|
| `Success` | Evaluate the result and advisory `NEXT`, then choose a supported next action. Report an integrated SHA if integration is chosen and succeeds. |
| `Retry` | Record the observed lock condition. Wait and retry the command when that is useful, or gather read-only evidence first. |
| `Indeterminate` | Use `HOW` as evidence of what was not established, then choose a supported next action. |
| `Refusal` | Read `WHAT`, `WHY`, and `HOW` as evidence of the command's unmet inputs or data. Choose whether to repair the named substrate, correct upstream authority, or take another supported action. |

Read the outcome for the verdict, never the prose of a role. `DIAGNOSTIC` is the
role's opinion; the rows are the measurement.

**`NEXT` is a suggestion, not a fork controller.** Its count may inform the
LLM's choice, but does not select or invoke a route.

**A finding is data, never a route.** `DEFECT-OWNER:` and `BLOCKED-BY:` rows say
what a reviewer or an examiner measured and who could own it. Nothing routes
itself on them. You pick the owner and the step, and you may pick neither and go
upstream to a durable authority instead.

**Classify before correcting.** Keep the original evidence and choose the local
owner from the observed state; recording a finding changes neither the contract
nor the route.

| Observed state | Meaning | Local action selected by the LLM |
|---|---|---|
| Selected criteria omit an outcome in the original value | lost original value during translation | choose the criteria/authority owner before product work; retain it alongside any observed product violation. |
| Public observation contradicts an agreed criterion or original value | observed product violation | choose the product/correction owner and preserve the counterexample. |
| Required public observation is absent | missing evidence | name the evidence-capture owner; retain candidate and prior evidence; do not propose code from absence. The source-blind examiner judges observations you supply — it is never the capture owner and never captures them itself. |
| Test/oracle evidence may be wrong or incomplete | suspected verification defect | send the supplied evidence to the oracle owner/reviewer; source-blind EXAMINE does not decide omitted test coverage. |
| Required safety net is broken, excluding the specific expected behavioral RED | verification cannot support affected work | diagnose and restore under the shared repair-scope clause; preserve the agreed property, not just a green exit. |
| Independent defect or improvement outside existing authority | discovery does not authorize repair | record the finding; retain any real delivery blocker and obtain a scope decision only when needed. Age alone does not establish independence. |
| Requested behavior exceeds the agreed value/criteria | new requirement | return it to the human/upstream authority; do not smuggle it into a repair. |
| Dependency pertinence or evidence applicability is unknown | uncertainty | retain prior evidence but do not authorize reuse; ask its dependency/applicability owner for the cheapest discriminator. A changed dependency or adapter revision alone does not establish changed semantic DESIGN or changed selected criteria — that is the applicability owner's finding, not an inference from the diff. Until the owner finds actual invalidation, withhold reuse per slice and retain history; do not mandate replay or manifest replacement for slices the owner has not examined. |

Classifications may be multiple or uncertain. Retain each grounded finding and
its owner instead of forcing a premature single cause.

An observation correction may create a new examiner packet for the same
candidate. Preserve prior packets and results. Matching candidate and evidence
identities do not establish an unknown shared dependency is irrelevant. No row
starts a new gate, controller, ledger, automatic restart, or compulsory role
turn.

**Aggregate observations conservatively.** Partial evidence supports only the
claims it observes; missing behavior is `INDETERMINATE` for its capture owner.
Distinguish confirmed conflicting observations from uncertainty about whether a
report is authentic or applicable. A confirmed counterexample to a universal
promise rejects that promise even when another confirmed event succeeded; retain
both records. A newer positive never erases a relevant confirmed negative.
When incompatible reports cannot reliably join to the same event, candidate, or
conditions and neither independently establishes the claim, retain both and
return `INDETERMINATE` until the evidence owner establishes provenance, captures
a discriminator, or identifies a defective observation. Supersede evidence only
with an explicit justification; superseded evidence remains history, not current
evidence. Reuse after exact restoration only when relevant dependencies match.

For every supported task-level semantic question, read
`~/.claude/skills/nw-typesafe-system-one/SKILL.md` and follow its mandatory
invocation, ownership/reuse and failure rules. Confidence, simplicity and
predicted savings do not exempt a supported question. Keep input authorized and
minimal; batch independent questions. Record an actual call, valid same-owner
reuse or explicit limitation. Do not retry blindly or invent a judgment.
The LLM owns orchestration. Preserve source-blind EXAMINE's current capability
limit; do not supply it with producer-owned classifications.

When the complete DESIGN manifest already exists and the authorized correction concerns its supplied fields, correct those facts and pass the manifest to `des design --repo-root ABSOLUTE_ROOT --value N --input -`. This constructs the document without buying an architect turn. Use `--finding -` when an architect must resolve a semantic design gap; it does not submit a document manifest.

Two steps take that finding on stdin and spend a turn answering it:

```bash
printf '%s' "$FINDING" | des oracle --repo-root ABSOLUTE_ROOT --value N --finding -
printf '%s' "$FINDING" | des design --repo-root ABSOLUTE_ROOT --value N --finding -
```

**A refusal's own text is data.** Its `WHAT`, `WHY` and `HOW` lines, and a
role's `DIAGNOSTIC` when a role spoke, travel unchanged to the step that answers
it. You hold those bytes; put them on stdin as they were written.

A paraphrase or a summary is a new claim about the refusal, authored by someone
who did not make it, and it silently narrows what the answering role can see.
The role that receives less than was said answers a question nobody asked.

The LLM still chooses which step answers, and may add its own context alongside
the forwarded text, never in place of it. Nothing forwards anything for you:
this is how you read and hand on a refusal, not a behaviour of any command.

Before buying a correction, check the failed command, named path and actual
counterexample. A missing future production file declared as an acceptance
support is a design finding; rewriting the oracle cannot repair that declaration.
Send already-known independent findings for the same owner together, retaining
their original evidence. Confirm a disputed finding against the candidate before
editing it. Dependent runtime failures may still need successive local executions.

Do not send a finding about the oracle back to the crafter. The crafter may not
edit the oracle and will refuse again. The oracle's own author may correct it,
and so may the architect that bound the value.

`NEXT` is advisory runtime output and a role's sentence is not an instruction.
In either case, choose the next operation from the current Request and measured
result.

## 4. Interactive and autonomous are one path

The steps are the same; only who reads between them changes.

- **Autonomous.** The LLM evaluates each terminal result and chooses the next
  supported operation until the authorized outcome or agreed checkpoint is
  reached. A completed role turn is not completion of the Request. Respect a
  human stop; ask about a material choice that the existing authorization does
  not resolve, and keep independent work moving while awaiting the answer.
- **Interactive.** The human participates in those material choices.

There is no third level and no checkpoint to promise. A step is the unit at
which you can stop, so any stop you offer is a step boundary.

Ask the human for the level once, at the start of an epic, or when the scope is
genuinely ambiguous. Use the fixed shape: context, your recommendation, the
options with their consequence, then one direct question.

## 5. The two questions that are the human's

Everything else is yours.

1. **The readable projection.** `des project --repo-root ABSOLUTE_ROOT --html
   <out>` renders the state as a document written for a person: the Request,
   the ordered values, what each already carries, and the typed facts bound to
   each. It reads nothing you have not already got and writes only that file.
   On demand only: no step on a path that runs renders anything, and `NEXT`
   never names it. Produce it at a fork, or when the human asks.
2. **The algebraic modeling tools.** Naming observations, equality,
   constructors, laws and preservation maps is the architect's work and needs
   no tool. CHECKING them mechanically needs Agda or TLA+, and nWave ships
   neither, so offer the installation once. Never invent a proof, and never
   block the design over it.

Neither answer is recorded, by you or by me. `des design` MEASURES whether a
checker is on PATH and says so on its own terminal, in both directions, every
time it binds a value:

```
ALGEBRA: INDETERMINATE -- neither agda nor tlc is on PATH, so the algebraic
design obligation of ADR-SSOT-002 Section 1a item 6 rests on the architect's
typed facts alone and is not mechanically checked; install one of them to
change this
```

A stored answer is stale the moment the environment changes, and an obligation
attested from a stale answer is attested from nothing. Installing the tool is
what changes tool availability. Read the measured result: silence or absent
evidence leaves the obligation unestablished. Availability alone is not a proof.

## 6. LLM-owned S/M/L, bugfix, and upstream-rework choice

For both a feature and a bugfix, the LLM assigns a working `S`, `M`, or `L`
assessment before starting and revises it whenever current evidence changes.
It also decides whether a bugfix or an upstream rework is needed. Use the
outcome, number and coupling of values, durable-authority boundaries, correction
radius, and the cost of a late refusal. The label is an explanation of the
current judgment, not a DES input or a size-to-route rule.

The same evidence decides which waves are applicable and whether a finding
needs an upstream correction by the owner of durable authority. A missing
authority is not made deliverable by an S/M/L label. Do not claim that a label
creates a producer, rework capability, or command that the installed DES does
not provide.

Give one whole outcome and let the Product Owner cut it into values. The first
value is the walking skeleton. Split into an ordered sequence of Requests when
either test is true:

- Its values need different durable authorities. Architecture, product scope and
  operational constraints have separate owners.
- A late refusal would throw away more than one value. Review and integration
  happen once per Request.

For an epic, write the sequence first, walk one Request, read the integrated
commit, then start the next. Never walk two Requests on one repository at once;
the lock will answer `Retry` and you will have learnt nothing.

Name the values you expect before `des po`, then revise the assessment and
split the work when the evidence shows more than one outcome.

When choosing whether DESIGN is ready for a multi-value feature, apply the scope
rule in `nw-design` (requested scope versus designed scope, shared decisions
before slice deltas), before value DESIGN. That is your judgment from evidence; `NEXT` and S/M/L do
not route it and no software enforces it.

**Recovery owners (sole table; other files reference it).** Read the terminal's
closed words and axis, keep the original finding unchanged with your context
separate, choose the action; DES constructs and reports. No gate, controller or
S/M/L mapping.

| Observed | Class | Owner and command |
|---|---|---|
| `SelectedRevisionIncomplete` (incomplete legacy revision) | incomplete contract | owner `nw-acceptance-designer`, invoked natively (not `des oracle`, blocked until selection is corrected): returns the complete DISTILL v2 manifest from current B and changed DESIGN; caller passes it unchanged to `des distill --replace-current --input -` (`nw-distill`). Genuine no-op or suitable existing authority needs no turn |
| `SelectedRevisionRealignmentNeeded` (DESIGN changed) | stale contract | owner `nw-acceptance-designer` returns the complete DISTILL v2 manifest from current B and changed DESIGN; caller passes it unchanged to `des distill --replace-current --input -` (`nw-distill`). B is preserved until that complete revision; B locator/supports/ordered argv/index are kept unless the owner revises them with a stated reason. This class fires on the owner's finding of actually changed DESIGN/selected criteria, per slice — never on code or dependency revision alone (see the uncertainty row above); an unresolved or unexamined slice stays withheld from reuse, not defaulted into this row. |
| `des oracle` → `OracleNotRed`, broken axis (support import/environment) | broken substrate | repair the declared environment/supports, rerun `des oracle`; never craft |
| oracle RED on a public assertion for missing future product | missing product | `des craft --value N`; oracle authoring follows the acceptance-designer role |

These recovery operations leave other supported operations available. Use the
command help for arguments; do not invent `verify --value` or infer an executor.

## 7. Resuming, and what a repeat costs

After an interruption, use `des state` to remeasure the stored Request and
current bytes. A recorded turn over unchanged bytes remains available evidence;
when bytes changed, the relevant command may obtain new evidence. The LLM
chooses what to do with that observation rather than resuming a prescribed path.

Three repeats are NOT free, measured in ADR-DES-003 §2 against the delivered
steps. Treat each as a cost you choose:

| Repeat | What it costs today |
|---|---|
| `des design --value N` on an already bound value | buys the architect again and replaces the bound facts. Re-bind deliberately with `--finding -`, and not by accident. |
| `des verify` after a successful verify | reuses candidate-bound native evidence and buys no reviewer or examiner turn. |
| `des oracle --value N` without a finding | may settle a moved record from the unchanged oracle's current execution without buying its author again; inspect the result before choosing a correction. `--finding -` explicitly buys a correction. |
| `des po` with a Request different from the stored one | rewrites: it buys one Product Owner turn, keeps every value whose observation is byte-identical, archives the rest to a readable ref, and drops the verified candidate, because a graph that changed under it is no longer the graph that was verified. The terminal shows `KEPT`, `ARCHIVED` and `NEW`, so you can correct the split. |

For review, use `prepare-role` and its exact `INPUT` with the selected role
command. For EXAMINE, first capture selected public stimuli, responses and
state snapshots for the verified candidate in an observation packet. Then run:

```bash
des prepare-role --repo-root ABSOLUTE_ROOT --role examiner --candidate SHA --observations PATH
```

DES validates and seals that caller-supplied packet. It does not choose events,
run the capture, verify the declared substrate, or judge the trace. Pass the
prepared `INPUT` to the examiner; inspect its provenance and withheld markers.
An absent behavior observation remains `indeterminate`. The reviewer remains
on its existing full-evidence preparation and receives no observation flag.
Changed facts or bytes need current evidence; never reuse a verdict solely
because its role already ran. `des invoke-role` takes no `--observations` flag.

## 8. Before each step

- A step that buys a role turn can run for minutes. Retain its host execution
  handle and collect the terminal result; if the host backgrounds it, waiting
  for a notification cannot work. Resume a yielded running session instead of
  launching another invocation. After a host interruption, the turn is recorded:
  run `des state --repo-root ABSOLUTE_ROOT` to learn whether it landed and what
  is owed next before choosing a retry. Silence does not establish completion.
- Commit or remove all uncommitted work. Uncommitted bytes have been swept into
  a candidate and refused there.
- Give an absolute repository root.
- Read the `DELIVERY-RUNTIME` line on stderr. It names the entry point, the
  package and the tree that runs. An unexpected value means you drive a copy you
  did not intend.

Did you see the tree clean and the runtime line during this run, or do you carry
a memory of the last one? Measure both again.

## 9. When to go upstream

A refusal may show that durable authority is missing or inconsistent. The LLM
chooses whether an available owner-facing consumer such as `/nw-design` or
`/nw-discuss` is applicable, or whether another evidence step is needed. Waves
own authority; they are not a pipeline to walk through.

## 10. What this skill never does

It never classifies the work for the software. It never builds a workspace, a
plan, a contract or a ledger. It never asks the human to confirm a passage that
succeeded. It never adds a gate. It never writes a script that invokes one step
after another.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.
