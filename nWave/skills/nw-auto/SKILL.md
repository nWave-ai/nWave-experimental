---
name: nw-auto
description: Decides Request size and human-interaction level, then walks the DES steps that deliver it.
user-invocable: true
argument-hint: '<request>'
---

# NW-AUTO

You orchestrate. Each DES step measures, constructs and enacts one thing, then
returns. No software joins them: you invoke one step, read the block it prints,
and invoke the next. This loop is yours, in prose. There is no command that runs
it for you, and a script that chains the steps is the defect this design removed.

## 1. The loop

```bash
des state --repo-root ABSOLUTE_ROOT
```

`des state` reads the open Request and prints `NEXT` — the canonical next step
with its exact invocation form. Invoke that step. Read its block. Invoke the
`NEXT` it prints. Repeat until integration closes the Request. Start a Request
that has no state yet:

```bash
printf '%s' "$REQUEST" | des po --repo-root ABSOLUTE_ROOT
```

Take every argv from the `NEXT` and `HOW-TO-INVOKE` lines of the step you just
ran, never from memory. `NEXT` is data. You may ignore it and invoke another
lawful step; the software acts on it never.

## 2. The nine steps

Seven steps change the state, in this order. Two only read.

| Step | What it leaves behind |
|---|---|
| `des devops` | operational constraints in the durable authority. Runs before `des po`. |
| `des po` | the Request stored, cut by the Product Owner into ordered values. |
| `des design --value N` | the typed design facts of value N, bound. |
| `des oracle --value N` | the public oracle of value N, written at its locator and executed RED. |
| `des craft --value N` | the change for value N, recorded. |
| `des verify` | one candidate commit, reviewed over the whole diff and examined source-blind. |
| `des integrate` | the candidate on the destination, and no Request stored. |

When the judge does not admit a candidate, `des integrate` refuses it as
`CandidateNotAdmitted` and names `--on-my-evidence -`. That form is yours to take
when you hold evidence of your own: it reads your reason from stdin and writes it
into a durable decision record beside the verdict it goes over, so the history
shows a decision and never a silent overwrite.
| `des state` | nothing. It reads where the Request stands. |
| `des project` | nothing. It renders the human-readable projection. |

The order is a property of the state, not of this table: `NEXT` is the first
thing not yet true, in that order. A step invoked on a state that does not admit
it refuses and names what is missing. That refusal is the net under a wrong move
of yours, so read the `HOW` instead of arguing with it.

The floor is never switched off. Craft requires a recorded oracle, and verify
always buys the blind examination. How WIDE the oracle and the examination must
be is measured from what the candidate touched, and printed as a fact.

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
| `Success` | Invoke the `NEXT`. Report the integrated SHA when integration closes. |
| `Retry` | Another step holds the checkout lock. Invoke the same step again. |
| `Indeterminate` | Do the `HOW` exactly as written, then invoke the same step again. |
| `Refusal` | Read `WHAT`. A sequence refusal names the producing step in its `HOW`: invoke it. A content refusal means the state is no longer readable: repair the substrate the `WHY` names. |

Read the outcome for the verdict, never the prose of a role. `DIAGNOSTIC` is the
role's opinion; the rows are the measurement.

**The count of `NEXT` lines is the fork signal.** One `NEXT` means one lawful
move: walk it, with no confirmation. More than one means the step found more
than one lawful move, and choosing is yours.

**A finding is data, never a route.** `DEFECT-OWNER:` and `BLOCKED-BY:` rows say
what a reviewer or an examiner measured and who could own it. Nothing routes
itself on them. You pick the owner and the step, and you may pick neither and go
upstream to a durable authority instead.

Two steps take that finding on stdin and spend a turn answering it:

```bash
printf '%s' "$FINDING" | des oracle --repo-root ABSOLUTE_ROOT --value N --finding -
printf '%s' "$FINDING" | des design --repo-root ABSOLUTE_ROOT --value N --finding -
```

Do not send a finding about the oracle back to the crafter. The crafter may not
edit the oracle and will refuse again. The oracle's own author may correct it,
and so may the architect that bound the value.

Did you follow a `NEXT` because the state named it, or because a role's sentence
sounded like an instruction? Only the first is a measurement.

## 4. Interactive and autonomous are one path

The steps are the same; only who reads between them changes.

- **Autonomous.** You walk each single `NEXT` without stopping, and you stop at
  a fork: more than one `NEXT`, a refusal with two possible owners, an examiner
  that does not admit.
- **Interactive.** The human reads the block between two steps and decides at
  the same forks.

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
what flips the measurement. Read that line rather than assuming: an obligation
reported as silence reads as an obligation met.

## 6. How big one Request is

Yours, with the human. No software decides it.

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

Do you know this Request holds one outcome, or are you starting a wish because
the human said it in one sentence? Name the values you expect before `des po`,
and split the work when the answer is the second.

## 7. Resuming, and what a repeat costs

After any interruption, `des state`. A turn already recorded over the current
bytes is not bought again, so a resume is free and the graph continues where it
stopped. A recorded turn whose bytes then moved is not a record: the step buys
it again, and that is correct.

Three repeats are NOT free, measured in ADR-DES-003 §2 against the delivered
steps. Treat each as a cost you choose:

| Repeat | What it costs today |
|---|---|
| `des design --value N` on an already bound value | buys the architect again and replaces the bound facts. Re-bind deliberately with `--finding -`, and not by accident. |
| `des verify` after a successful verify | rebuilds the candidate and buys the reviewer and the examiner again over unchanged bytes. |
| `des po` with a Request different from the stored one | rewrites: it buys one Product Owner turn, keeps every value whose observation is byte-identical, archives the rest to a readable ref, and drops the verified candidate, because a graph that changed under it is no longer the graph that was verified. The terminal shows `KEPT`, `ARCHIVED` and `NEW`, so you can correct the split. |

## 8. Before each step

- Commit or remove all uncommitted work. Uncommitted bytes have been swept into
  a candidate and refused there.
- Give an absolute repository root.
- Read the `DELIVERY-RUNTIME` line on stderr. It names the entry point, the
  package and the tree that runs. An unexpected value means you drive a copy you
  did not intend.

Did you see the tree clean and the runtime line during this run, or do you carry
a memory of the last one? Measure both again.

## 9. When to go upstream

A refusal for missing authority is not a delivery problem. `/nw-design` or
`/nw-discuss` update the durable authority; then invoke the same step again.
Waves own authority. They are not a pipeline you walk through.

## 10. What this skill never does

It never classifies the work for the software. It never builds a workspace, a
plan, a contract or a ledger. It never asks the human to confirm a passage that
succeeded. It never adds a gate. It never writes a script that invokes one step
after another.
