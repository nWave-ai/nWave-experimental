---
name: nw-distill
description: "Compile value and architecture authority into a minimal executable oracle and one DeliveryContract. Human and Auto share the same route algebra and quality floor."
user-invocable: true
argument-hint: '[delivery-id]'
---

# DISTILL: executable oracle compilation

ADR-SSOT-002 owns delivery authority and route semantics. This skill owns only
the DISTILL method and points to narrower test-design skills.

## One method for Human and Auto

Human-on-the-loop may pause for an unresolved product or architecture decision;
Auto must return the same gap. Neither path maintains a separate procedure or
artifact family. Both dispatch `nw-acceptance-designer` with an immutable value
seed, permanent architecture locator, repository root, the absolute
installed `thin-delivery-contract.schema.json` locator and one route. That
schema locator is explicit, ephemeral dispatch context resolved before
dispatch — never a contract field, a persistent output or an inferred path.

| Route | Oracle rule | Required observation |
|---|---|---|
| `RED_TO_GREEN` | author one minimal consolidated executable oracle | complete scope fails only for missing promised behavior, established by the crafter's own BASELINE, not by DISTILL |
| `GREEN_TO_GREEN` | bind an existing architecture-named oracle; no test edit | complete scope is green before implementation, established by the crafter's own BASELINE, not by DISTILL |

`applicability.examine` is independent and owned upstream. A PO authors a
charter only when that axis requires one and discovery found no valid charter;
the acceptance designer never reads or writes it.

"Minimal consolidated" means one executable artifact file with cases collapsed
only when they share the same observation; every distinct promised observation
and universal law remains independently falsifiable.

## DESIGN owns the proof protocol; DISTILL compiles it

The permanent DESIGN brief/ADR is the sole authority for the complete proof
protocol: observable law, generator/input domain and invalid boundaries, real
port/observation, the concrete language PBT adapter/framework, final
dependency readiness facts (owner/version plus declared=yes, present=yes),
lifecycle isolation, one oracle target, at most two exact examples,
verification argv, and intended RED. DISTILL is a compiler
over that sealed authority — it first reads the schema locator for
serialization grammar only, then reads the authority and the at most two
named examples, then writes the oracle and one complete DeliveryContract,
assembled from the
already-resolved Seeded facts (`delivery-id`, `outcome`, `repository`,
`budget`, `applicability`, `delivery-route`) and the durable DESIGN facts
(`targets`, `paradigm`, `obligations`, `verification-scope`). DISTILL holds
no `Bash` tool: it never executes the verification command, hashes the
oracle, calls `des validate-delivery-contract` or classifies a result as RED,
GREEN or BROKEN. That execution/hash/validation runs once at the root
dispatch boundary, between DISTILL's `CONTRACT_READY` and the crafter's own
BASELINE, never inside this skill. DISTILL never calls `Skill`, `CodeFact`,
`Glob`, `Grep` or `Task`, and never rediscovers design.

Already compiled by DESIGN and reused here, not re-derived: the Human/Auto
shared method above, `RED_TO_GREEN`/`GREEN_TO_GREEN` route semantics, and the
algebra/certainty/PBT/residuality properties of the proof protocol. DISTILL's
own remaining scope is minimal tests and one complete DeliveryContract — no
extra bureaucracy.

### `des compile-contract` — an optional mechanical skeleton producer

`des compile-contract --repo-root <root> --delivery-id <id>
--architecture-authority <brief-path>#<anchor> [--route ...]` is a
root-invocable, Bash-driven producer (never something DISTILL/ATD itself
calls — DISTILL holds no `Bash`) that derives
`targets.*.candidate/decision/overlap/declared-imports`,
`verification-scope.commands`, `obligations` and `acceptance-tests.locator`
from the architecture authority's own citations, reusing the IDENTICAL
resolvers `des dispatch`'s existing content validators (declared-import
resolution, EXTEND-citation, verification-command, whole-suite-scope)
already run in CHECK mode — this producer runs them in DERIVE mode instead,
so a skeleton it writes passes those validators by construction. Every
field DESIGN/ATD alone can judge (`outcome`, `targets.*.justification`,
every `targets.*.boundary.*`) is left as the literal `<ATD: fill>`
placeholder, which both `des dispatch` and `des validate-delivery-contract`
refuse until replaced with real prose — see `nw-acceptance-designer.md`,
"Compiled skeleton", for ATD's fill-not-author handling when
`CONTRACT-LOCATOR` already resolves to one of these files. The oracle
locator is a CONVENTION this producer decides too (the primary EXTEND
target's own sibling `tests/` directory, else the repository's top-level
`tests/`), not a judgment call root or ATD supplies — ATD `Write`s the
oracle at that exact given path. No discoverable test-directory convention
is a construction refusal (WHAT/WHY/HOW) at the producer, never a guessed
directory.

The six existing `des dispatch` content validators remain in place as
backstops regardless of whether a skeleton was compiled — this producer
narrows how often they fire, it does not replace them (GDP-10: a candidate
for removal only after real runs show zero firings, not on introduction).

An installed PostToolUse hook (`des.adapters.drivers.hooks.
post_write_handler`, `des.domain.oracle_write_classifier`) observes ATD's
own `Write`/`Edit` on the oracle file a compiled skeleton names and
classifies the linked `verification-scope` command's BASE outcome
immediately, relaying it back via `additionalContext` — the same evidence
`des dispatch`'s own BASE red-reason probe proves later, just earlier and
advisory (it never blocks). See `nw-acceptance-designer.md`, "Compiled
skeleton", for the classification labels.

## Spatial portfolio before prose

Compile `state/failure -> input -> real port -> observation -> oracle` before
writing. Minimize tests while preserving distinct business laws and failure
modes: combine shared observations, parameterize equivalent cases and use one
property per genuinely distinct universal law. One subprocess walking skeleton
proves assembled wiring only when the user consumes that assembled surface;
other behavior uses the nearest deterministic honest port.

The architecture brief supplies reusable helpers, fixture/executor lifecycle,
dependency ownership, literal verification command(s), port/selector identity
and the preservation map from a cheap law-bearing seam to the real
observation. Missing facts return to their owner; DISTILL never guesses them.

`verification-scope.commands` is a set, not a slot: it carries the oracle's
own command AND, when the subject workspace's own root `CLAUDE.md` already
states one, the workspace's own whole-suite command — copied verbatim, never
narrowed to only the new oracle (K4 Run 12: an oracle-only scope left a
shared serializer's regressions invisible until 3 reviewer rounds surfaced
them; `des dispatch` now refuses a whole-suite-declaring workspace whose
contract omits it).

## Output

The only persistent outputs are:

- the executable oracle selected by the route;
- one complete DeliveryContract binding the oracle's exact locator plus every
  other Seeded and durable DESIGN fact the schema requires.

Reviewer findings and compositional certificates are ephemeral. No narrative
delivery workspace, persistent progress mechanism or parallel Human carrier is
produced.

Handoff requires a terminal `DISTILL-RESULT: CONTRACT_READY` result from the
acceptance designer plus the explicit physical repository root and the
repo-relative contract locator. The root is ephemeral invocation context,
never a schema field, cwd inference or second authority. Process exit,
timeout or partial prose cannot enable DELIVER.

DISTILL itself never executes, hashes or validates the contract or oracle.
Root dispatches the single provider-neutral CLI boundary — `des dispatch
--repo-root ROOT --delivery-contract PATH` — immediately after
`CONTRACT_READY`; that one call only validates, resolves and hashes the
contract, and its exact two-line stdout is forwarded verbatim to the
selected crafter. RED/GREEN/BROKEN classification is never proven by
`des dispatch`; it is established solely by the crafter's own BASELINE step.
A prose claim of schema or oracle validity is not evidence.
