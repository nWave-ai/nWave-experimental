# Expectation Charter — canonical template

One expectation = one file at `docs/product/expectations/<feature-id>/<intent-name>.md`. The
filename is a human sentence describing the intent (e.g.
`visitor-holds-two-seats-and-sees-countdown.md`), nested under the feature-id it belongs to.
**One page, hard limit.** This is a re-executable product artifact, not process exhaust: the
session log is the only part that grows, and a template that grows sections is regression to
the disease.

**Charter, not script**: intent + oracle, never click-by-click steps — each examiner derives
its probes independently (independence survives re-execution), and N examiners can walk the
same charter in swarm, with divergence between session logs as signal.

## Template

```markdown
# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

> **Name the tree, or the examine measures the wrong build.** A machine can hold the
> trunk checkout, several worktrees, and an installed copy at once. The same script
> exists in all of them, runs, and prints a perfectly formed verdict from whichever one
> the path happened to resolve against — silent-wrong at the one step whose whole point
> is independent observation, and the examiner cannot catch it because she is required
> not to read the source.
> `uv run --project <dir>` selects the ENVIRONMENT, not the root a relative script path
> resolves against; it does not protect you here.
> The start recipe MUST: (1) `cd` into the tree under test, (2) give every script an
> ABSOLUTE path, (3) tell the examiner that a free witness exists — every `des`
> invocation prints `des.runtime.freshness.autoskipped` naming the root it resolved —
> and that an observation whose root is not the tree under test must be DISCARDED and
> re-run, never reported.
> Note the asymmetry, because it says where to look first: BEFORE the feature is merged,
> a PASS is self-authenticating (the other trees lack the feature, so they cannot produce
> one), while a FAIL is ambiguous between "the code is broken" and "I looked where the
> code is not". On a failed pre-merge examine, suspect the tree before the code. After
> the merge the asymmetry disappears and both verdicts need the witness.

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
```

## Example (filled)

```markdown
# Visitor holds two seats and sees a countdown
ID: EXP-seat-booking-3 · Spec rows: R12, R37 · Persona: a visitor booking seats for an event

## Intent
A visitor picks two seats for an event and both are held for them while they decide; a
visible countdown tells them how long the hold lasts, so they never lose held seats
without warning.

## Preconditions
`npm install && npm run seed:demo && npm run dev` → app at `http://localhost:3000`.
Seed: one event ("Spring Gala"), all seats available.

## Charter
Explore seat selection and holding via the browser to verify that holding two seats
works and that its time limit is visible to the visitor.

## Expected observations (oracle)
- Selecting two seats marks both as held for me, visibly distinct from free and sold seats.
- A countdown appears when the hold starts and visibly decreases.
- Negative: a second visitor (separate session) must NOT be able to select my held seats.
- Negative: after the countdown expires, the seats must NOT remain held — they return
  to available.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
| 2026-07-03 | nw-user-examiner | PASS | Held A4+A5, both turned amber "held by you"; countdown 5:00→4:57 visible; second browser context could not select A4 (tooltip "held"); after expiry both reselectable. Feedback: the countdown sits top-right, away from the seat map — easy to miss while choosing. |
```

## Example (filled — a CLI / gate outcome, not a UI)

The format is **medium-agnostic** — it holds up when the "surface" is a `des` command and the
"observation" is an exit code + a JSON event + the ABSENCE of a ledger record, not a visual
state. Infra / gate / observability outcomes use this shape (dogfood-validated 2026-07-03).

```markdown
# A production file never executed during the feature blocks feature-done
ID: EXP-wire-p0-gates-2 · Spec rows: slice-02 · Persona: the nWave maintainer running DELIVER

## Intent
When I run the feature-end cycle on a feature whose verification never executed a shipped
production file, the cycle must REFUSE to declare the feature done, so a never-run code path
cannot ship as "delivered".

## Preconditions
A scratch repo fixture: a committed tree with a production file that has ZERO coverage in the
feature's Cobertura XML. Run: `des feature-end run --feature-id <id>` from the fixture root.

## Charter
Drive the feature-end cycle via the `des` CLI to verify a never-executed production file
blocks feature-done and does so LOUD.

## Expected observations (oracle)
- The cycle exits non-zero and prints an execution-reach refusal naming the never-run file.
- Negative: the cycle must NOT print a "feature done" / sign+emit success while a file was
  never executed (no false-done).
- Negative: NO `FeatureEnd` / sign record must appear in the ledger after the refused run.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
```
