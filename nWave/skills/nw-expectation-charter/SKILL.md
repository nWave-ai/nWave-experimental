---
name: nw-expectation-charter
description: "Charter-authoring competence for ANY flow (DISCUSS wave, /nw-bugfix, technical fixes that skip DISCUSS) — how to write a user-side, discovery-preserving expectation charter that arms the DELIVER EXAMINE gate. Consult whenever an agent must author or judge a docs/product/expectations/ charter."
user-invocable: false
disable-model-invocation: true
---

# Expectation Charter — Authoring Competence (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference). No forced sequence — consult whenever you are about to author,
or judge, an expectation charter. Composed by `nw-discuss` (native, in-wave) and by any flow
that authors a charter outside DISCUSS (`/nw-bugfix` Phase 3c, ad-hoc technical fixes).

**Owner agent**: `nw-product-owner` (Luna). Any OTHER context that needs a charter dispatches a
FRESH Luna context rather than authoring inline — see the Disqualification Rule.

## Why this exists (Ale-ratified, 2026-07-08)

The expectation charter is the examiner's (Vera, `nw-user-examiner`) half of verification — she
walks the REAL product surface as a non-technical demanding beta tester and does discovery /
exploratory testing, finding what the ATs never thought to ask. That discovery value exists
ONLY if the charter's derivation is uncontaminated.

Empirical failure (this repo, 2026-07-08): a charter authored by the orchestrator right after
designing the fix came out implementation-soaked (`force-include RHS`, function names) and
click-script-shaped ("run these three commands"). The resulting examine was a rubber-stamp —
Vera ran the author's own harness against the author's own precomputed verdict lines. Zero
discovery. Charters born from the proper flow (a fresh, value-side-only context) give latitude
and catch real gaps.

## The Disqualification Rule (read this first)

> If your context contains the feature's design contract or implementation — you designed it,
> dispatched its crafter, or read its diffs — you are DISQUALIFIED from authoring this charter.
> No skill can decontaminate a context. Dispatch a FRESH `nw-product-owner` context instead,
> giving it VALUE-SIDE INPUTS ONLY.

Value-side inputs (the only legal charter sources):
- The human's directive, verbatim (best anchor).
- The bug's observable (for `/nw-bugfix`: what a user sees when it's fixed, in plain language —
  never the diff).
- The feature-delta's Value statement rows (Slice Plan row / user story Elevator Pitch) —
  EXTRACTED, never the whole file.

NEVER these (design-side, disqualifying):
- The design contract sections, ADRs, architecture diffs.
- The implementation, its diffs, its internal names.
- **The whole `feature-delta.md` file.** It accumulates DESIGN/DELIVER sections from later
  waves as the feature progresses — handing the fresh context the entire file re-contaminates
  it even when the intent was to give only the Value statement. Extract and pass ONLY the
  Value-statement rows (or the human directive / bug-observable), never the file itself.
- The ATs as SOURCE — consulted, if at all, only AFTER the charter is drafted, and ONLY as a
  final coverage cross-check ("is every charter observation's territory also AT-covered?"), NEVER
  as the derivation and NEVER before the charter exists. Deriving the charter FROM the ATs
  collapses the two independent derivations into one; the examine becomes tautological (Vera
  would just re-verify what the crafter already proved green).

## Two independent derivations

The acceptance-designer (DISTILL) derives the ATs, and the examiner (via this charter) derives
her walk, from the SAME value statement, INDEPENDENTLY. The crafter authors neither. This is
the structural reason the charter must stay value-side: it is one of two independent readings
of the SAME intent, not a downstream artifact of the other.

## When NOT to write a charter

`@infrastructure` / `@prefactoring` slices with no user-observable value get NO charter —
writing one there is a contract-spec in disguise (the acceptance-designer's job, not the PO's).
The charter belongs to the OBSERVABLE slice (often the wiring slice that finally makes the
infra visible). An infra slice with no charter leaves EXAMINE unarmed for that slice BY DESIGN
— the reviewer audit is the by-design fallback, not a gap to fill.

Positive classification example: a slice titled "wire the config port into the CLI" gets NO
charter (mechanism, no user-observable change alone); the NEXT slice, "operator's CLI command
now reads from the wired config", gets the charter (the observable behavior finally exists).

## How to write a good charter

1. **Path** — `docs/product/expectations/{feature-id}/{intent-name}.md`. `{intent-name}` is
   kebab-case and names the INTENT from the user's side (e.g.
   `a-visitor-confirms-a-seat-and-finds-it-in-their-bookings`), never the implementation. Gate:
   filename reads as a value-outcome, not a mechanism.
2. **Intent** — from the user's side, domain language. Quote the human directive verbatim when
   one exists. Gate: a non-technical reader understands what's accomplished and why it matters.
3. **Preconditions** — heading text is exactly `## Preconditions` (no suffix — see Parser
   dialect below). Content: the start recipe — how to launch + WHICH REAL SURFACE (CLI, HTTP,
   browser, a fresh venv install...). Names the surface only. Gate: never pre-computes an
   observation,
   never hands over a purpose-built harness with verdict lines — the examiner derives her own
   probes from the recipe.
   Pins the TARGET PROJECT's language-specific execution surface explicitly (e.g. "run `cargo
   test` / the Rust binary in <dir>", "run `des <subcommand>` via the Python CLI", "run `npm
   test` / the vitest runner") — never leaves the runtime/language for the examiner to assume.
   Gate: the examiner has zero latitude on which language/runtime to use, all latitude on what
   to observe; a language-agnostic recipe lets her default-guess (bias toward Python/pytest) and
   examine the WRONG runtime — a false-FAIL on a correct product (observed cross-instance on a
   Rust repo: pytest-style checks run against a cargo project).
4. **Charter body = what to EXPLORE, not a click-script** — an outcome to observe, never a
   keystroke/command sequence. Gate: independence survives re-execution; a different examiner
   (or a swarm) walking the same charter produces comparable but not identical logs —
   divergence is signal, not noise. Explicitly invite discovery: hostile inputs, boundary
   cases, "what would a paying user try?".
5. **Expected observations (the oracle)** — including AT LEAST ONE NEGATIVE observation (the
   system must NOT claim success while the outcome is absent). Gate: ≥1 positive + ≥1 negative
   observation present.
6. **Session log** — append-only, `date | examiner | verdict | observations` table. Gate: never
   edited retroactively, only appended.
7. **Arming check** — writing the charter under `docs/product/expectations/{feature-id}/` is
   what ARMS the DELIVER EXAMINE step + the commit-slice examine-verdict gate for that
   slice/feature. Gate: the charter path's `{feature-id}` matches what the gate expects, or the
   arming silently misses.

Template + full worked examples (a browser-UI charter, and a CLI/gate-outcome charter — the
format is medium-agnostic): `nWave/templates/expectation-charter.md`.

## Parser dialect (verify-charter-filled) — the exact form the gate greps

`des verify-charter-filled` (`src/des/cli/verify_charter_filled.py`) is a mechanical grepper,
not a semantic reader. Content-perfect prose still bounces if the literal form is off. Three
rules:

1. **Preconditions heading is an EXACT line match** — the line must be exactly `## Preconditions`.
   No suffix, no rename (`## Preconditions / start-recipe` is invisible to the parser).
2. **Oracle heading is a PREFIX match** — must START WITH `## Expected observations` (a suffix
   is tolerated, e.g. `## Expected observations (oracle)`; the prefix is not negotiable).
3. **Negative observations are LINES starting with `Negative:`** (case-insensitive) inside the
   oracle section, e.g. `- Negative: ...`. A `### NEGATIVE` sub-heading or a bold bullet
   (`**N-1**: ...`) is NOT recognized — the gate finds zero negative observations and fails.

Start from `nWave/templates/expectation-charter.md` — it already embodies this exact dialect
when available; copy its heading/bullet shape rather than reinventing one.

Empirical anchor: a content-perfect charter (one positive + two negative observations) was
REJECTED by `verify-charter-filled` on 2026-07-12 for dialect, not content — it used
`## Preconditions / start-recipe` and a `### NEGATIVE` subsection with `**N-1**` bullets, both
invisible to the parser.

## Gate-promise charters

When a gate's rejection MESSAGE names an escape, override, or designed path (e.g. `@coupled`, a
`--flag`, a lane exemption), that promise is an untested user surface — the gate says the path
exists, but nothing proves the code honors it. Author a charter with two legs: a POSITIVE
observation proving the promised path, followed literally, actually works; and a NEGATIVE
observation proving the gate still bites when the path is NOT followed. A gate message that
promises a path must have a Vera charter proving the path — one leg alone is not enough (positive
without negative can't tell "the escape works" from "the gate never fired"; negative without
positive can't tell "the escape doesn't work" from "nobody tried it").

Empirical anchor: the `@coupled`-for-pytest override was promised in the carpaccio-ceiling gate's
own rejection message, but the gate's code ignored it — the escape silently didn't work, for two
days, unexamined (2026-07-10).

## Absence vs. incapacity (Ale-ratified, 2026-07-12)

When the examined surface CAN be incapable of looking (analysis tools, grounding gates,
aggregators with optional legs), the oracle MUST include the honest-incapacity observation: the
surface DECLARES it could not look (naming what/why), and never asserts absence/cleanliness in
that case.

> "non basta dare una ragione — la ragione deve distinguere l'assenza dall'incapacità. Una
> ragione troppo grossolana è un falso negativo con l'alibi di essere degradato."

Litmus for the PO: does "I looked and it's clean" produce the same output as "I never looked"?
If the charter doesn't force that distinction, the oracle is incomplete.

Empirical anchors: a code-analysis tool answered `unknown_symbol` for an enum that EXISTS (it
cannot index types — incapacity reported as absence); an analysis envelope reported zero
findings at confidence 1.0 over a tree it had never read; a certification aggregate emitted
Complete with zero legs observed.

**Partial capability, not just total incapacity (fifth-floor refinement, Ale-ratified, 2026-07-12).**
`capable(tier)` is an ill-posed question; the right one is `capable(tier, CATEGORY)`. A
PARTIALLY-capable surface is MORE dangerous than an incapable one — its partial competence buys
it credibility across the whole domain, so it says "I know, and it's not there" instead of the
honest "I don't know". When the examined surface may be capable in SOME categories but not
others (analyzers, detectors, grounding tiers), the oracle must force the per-category
differential: not "does it detect X" but "does it detect X of every kind X can take". Concrete
pattern: a single fixture holding one instance of each category the surface claims to cover
(e.g. a function, a class, a constant, in one file), each cited/probed individually, so that
passing on one category cannot mask a blind spot in another.

Empirical anchor: our own Python-AST tier PARSES a `.py` file (so it registers as capable, it
DID look) but is BLIND to the class category — a real `class RealThing:` was branded
"phantom/invented" identically to a genuinely-absent symbol.

## Invocation per flow

| Flow | Who authors | Input given to the fresh context | Charter path |
|---|---|---|---|
| DISCUSS (native) | `nw-product-owner`, in-wave Phase 6/7 | Slice Plan Value statement rows | `docs/product/expectations/{feature-id}/{intent-name}.md` |
| `/nw-bugfix` Phase 3c | a FRESH `nw-product-owner` dispatch — never the bugfix orchestrator inline | the RCA's bug observable (plain language, no diff) + the human's bug description verbatim | `docs/product/expectations/fix-{bug-summary}/{intent-name}.md` |
| Ad-hoc technical fix (skips DISCUSS) | a FRESH `nw-product-owner` dispatch | the human's directive verbatim | `docs/product/expectations/{feature-id}/{intent-name}.md` |

## GOOD vs BAD (compact pair)

| | Shape | Why |
|---|---|---|
| GOOD | "A contributor whose codebase is Python runs the nWave contract gate and it routes their suite THROUGH the registered adapter — the gate reports the adapter's own real verdict, not a canned pass." | User-side, outcome-anchored, explorable — Vera can probe adapter-absent, adapter-broken, multi-language cases without a script. |
| BAD | "After `patch_pyproject`, the force-include map includes `nWave/nWave/<x>`... Run these three commands and read the VERDICT-INPUT lines." | Names internals (`patch_pyproject`, the force-include map), pre-computes the verdict, zero discovery latitude — Vera becomes a script-runner, not an examiner. |

## The corpus's double value

`docs/product/expectations/` accumulates two things at once: (a) the re-executable examine
suite Vera (or a swarm) re-walks over time, and (b) the raw material of a USER MANUAL — each
charter is "what you can do + what you'll see", written from the user's side. Write every
charter knowing a future USER reads it, not only Vera. (Follow-up backlog idea: a `des`
generator turning the expectations corpus into a manual — not built yet.)

## Success Criteria

1. - [ ] Disqualification Rule honored — author's context holds VALUE-side inputs only (human
   directive / bug observable / Value statement), never design/implementation/diffs.
2. - [ ] ATs used, if at all, only as a coverage cross-check AFTER the charter is drafted —
   never as the charter's source.
3. - [ ] Path + intent name are from the user's side, kebab-case, no implementation terms.
4. - [ ] Preconditions name a real surface, contain zero pre-computed observations or verdict
   lines.
5. - [ ] Preconditions pin the target project's language-specific execution surface
   (cargo/pytest/npm/...), never leaving the runtime for the examiner to assume.
6. - [ ] Charter body describes outcomes to explore, contains zero keystroke/command scripts.
7. - [ ] Oracle has ≥1 positive AND ≥1 negative observation.
8. - [ ] Session log is append-only.
9. - [ ] `@infrastructure`/`@prefactoring` slices carry NO charter; the first observable-value
   slice does.
10. - [ ] Charter path's `{feature-id}` matches what the DELIVER EXAMINE gate / commit-slice
   gate expects (arming confirmed).
11. - [ ] For any surface with an incapable/optional leg (analysis tool, grounding gate,
   aggregator), oracle includes a distinct "declares its own incapacity" observation — "I
   looked and it's clean" is not the same claim as "I never looked".

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not
padding. State the conclusion, then the supporting evidence; never bury the verdict under
exposition.
