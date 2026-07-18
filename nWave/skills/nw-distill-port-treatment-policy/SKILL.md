---
name: nw-distill-port-treatment-policy
description: "Port-to-port acceptance criteria + the Architecture of Reference (port-class → test treatment) + the Project Infrastructure Policy (concrete mechanism per port) + the walking-skeleton canonical definition and not-applicable exemptions. Consult while classifying a port's test treatment and the concrete mechanism for this codebase."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Port Treatment + Infrastructure Policy (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are classifying a port → test treatment (real vs fake) and choosing the concrete mechanism for THIS codebase (Testcontainers vs dedicated env vs in-memory; which fake class), or determining walking-skeleton applicability. Composed by `nw-distill`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Acceptance Criteria: Port-to-Port Principle

Every AC MUST name the driving port (entry point) exercising the behavior → port-to-port ATs → TBU (Tested But Unwired) defects structurally impossible.

Each AC:
1. **Observable outcome**: what user/system sees
2. **Driving port**: entry point triggering the behavior (service, handler, endpoint, CLI command)

No driving port → crafter can write correct code never wired into the system.

**Features**: "When user {action} via {driving_port}, {observable_outcome}"
**Bug fixes**: "When {trigger}, {modified_code_path} produces {correct_outcome} instead of {current_broken_behavior}"

## Architecture of Reference (ports & adapters — project-level defaults)

Three port classes, each with default test treatment. Table = PROJECT-LEVEL: decided once per project (DESIGN of first feature, or framework adoption). NOT renegotiated per feature. Agent applies defaults; per-feature decision = MECHANISM (Project Infrastructure Policy below), not treatment.

| Port type | Examples | Default in test |
|---|---|---|
| **Driving** (entry point) | HTTP API, CLI, in-process call, hook | **In-process via the `OutputPort`** — drive the real entry (`cli main(argv)` / application-service method) IN-PROCESS with a fake output port, no interpreter fork. **subprocess-e2e ONLY for `@walking_skeleton`** (ONE scenario per FEATURE that proves the installed artifact is wired). |
| **Driven internal** (shared state) | Repository, read model, application cache | **In-memory fake by DEFAULT** (config-switch row below); a config parameter selects the real/prod-like mechanism (Testcontainers / dedicated env) for the CI-or-local prod-like run declared in the project Infrastructure Policy. |
| **Driven external / non-deterministic** | Clock, email, SMS, push, payment, LLM, third-party API | Fake/stub with output capture (so a `Then` can observe the side effect) |

Replaces the earlier per-feature Walking Skeleton Strategy A/B/C/D choice. Decision is structural — port CLASS implies port TREATMENT; per-project Infrastructure Policy specializes the mechanism per treatment.

Port unclassifiable by agent → ask the user with a soft prompt. Do NOT improvise the classification.

### The inverted Driving default — in-process, not subprocess (the speed default)

The Driving default INVERTS the old "CLI = subprocess runner" assumption. A new acceptance test drives the entry point **in-process** by default: it calls the real `cli main(argv)` (or an application-service method) directly, threading a fake `OutputPort` that captures the terminal output a `Then` asserts on. No `subprocess.run([sys.executable, ...])` fork — the same Mandate-13 driving-port semantics, 10–100× faster. (Language-agnostic: the rule is "call the shipped entry in-process with a captured output sink"; the `cli main(argv)` form is the Python illustration.)

**subprocess-e2e is reserved for `@walking_skeleton` — ONE per FEATURE.** Only the feature's single walking-skeleton scenario legitimately proves the installed CLI/artifact is wired end-to-end (real fork, real terminal). EVERY other AT defaults to in-process/in-memory. A non-`@walking_skeleton` AT that forks an interpreter is a speed regression flagged by the subprocess-overuse gate. Wiring coverage beyond the single WS is carried by Vera's EXAMINE (every charter observable exercised through the REAL surface) + the feature-end cycle (env-e2e + full-suite + deep-review) — never by multiplying E2E scenarios.

### The "CLI = e2e by construction" caveat is DISSOLVED

The old caveat held that a CLI command can only be tested end-to-end (subprocess) because the terminal is intrinsic to the command. That conflation dissolves under the hexagonal cure: **the terminal is an external system behind the `OutputPort`.** The CLI surface SPLITS into two:

| Facet | What it proves | Default treatment |
|---|---|---|
| **output-content / behaviour** | the command computes + emits the right output | **in-process** via the `OutputPort` (captured, asserted on the fake's buffer) |
| **terminal-wiring** | the installed binary actually reaches a real terminal | **exactly one `@walking_skeleton`** per FEATURE (subprocess-e2e) |

The content facet (the bulk of the ATs) drives in-process; the wiring facet is the single WS. A FEATURE therefore needs ONE subprocess AT (its WS), not one per scenario, slice, or command — a feature spanning multiple commands routes its single WS through the primary user journey, and the remaining commands' wiring is covered by Vera's real-surface EXAMINE + feature-end env-e2e.

### Config-switch — in-memory local default / testcontainers prod-like

Driven-internal ports default to an **in-memory fake** (fast, local). A config parameter selects the prod-like mechanism (Testcontainers / dedicated env) for a CI-or-local run that exercises the real adapter. The switch resolves from the project Infrastructure Policy (`docs/architecture/atdd-infrastructure-policy.md`) per port:

- **`@in-memory`** (default) — the in-memory double; runs everywhere, no container runtime needed.
- **`@real-io` / prod-like** — Testcontainers or a dedicated env; opt-in via the config parameter. When no container runtime is present the prod-like leg degrades-LOUD to INDETERMINATE (`@requires_external`, skip-if-absent) — never silent-pass, never a hard-block on a container-less target. The gate asserts the switch EXISTS and the in-memory path runs; the prod-like path is exercised when the runtime is available.

This keeps the local loop fast (in-memory) while guaranteeing the prod-like path is reachable and exercised where the infrastructure exists.

## Project Infrastructure Policy

Architecture of Reference fixes **port class → test treatment** defaults. Project Infrastructure Policy specializes them with the **concrete mechanism** for THIS codebase. **Once per project, not per feature**.

### File location and structure

Lives at `docs/architecture/atdd-infrastructure-policy.md` (project-local). Three tables, one per port class, columns: `Port | Mechanism | Note`.

```markdown
# ATDD Infrastructure Policy

## Driving
| Port | Mechanism | Note |
|---|---|---|
| HTTP API | WebApplicationFactory<Program> | |
| CLI | subprocess from tmp_path | |

## Driven internal (real)
| Port | Mechanism | Note |
|---|---|---|
| IUserRepository (MongoDB) | Testcontainers.MongoDb, fresh db per test class | |

## Driven external / non-deterministic (fake)
| Port | Fake | Note |
|---|---|---|
| IClock | FakeClock | manual advance |
| IEmailSender | FakeEmailSender | in-memory capture |
```

`Note` column optional — one-line clarification only.

### Apply-if-exists / write-if-absent

| Case | Action |
|---|---|
| File exists (default `--policy=inherit`) | read policy, apply recorded decisions; no renegotiation for ports already in table |
| In-scope port missing from policy | soft prompt per missing port (`which mechanism for {port}?`) → **append row to policy** before generating scenarios; policy grows by accretion |
| File absent | create empty skeleton, three section headers (`policy-bootstrap-template` expansion); treat every in-scope port as missing (row above) |

Edited in place. No per-row versioning — git history = audit trail.

### `--policy=fresh` flag

`--policy=fresh`: ignore existing file this run; every in-scope port = missing (soft prompt per port); on completion rewrite file from scratch with newly agreed decisions. `fresh` = major refactors (stack swap, test-strategy overhaul). Otherwise `inherit`.

### Relationship to the Architecture of Reference

Architecture of Reference: "what kind of treatment for this port class?" (real vs fake). Project Policy: "which concrete implementation for that treatment?" (Testcontainers vs dedicated env, which fake class).

Policy CANNOT override port-class defaults: a driven-internal port cannot become fake via policy (requires an explicit waiver in `distill/wave-decisions.md`). Policy records **mechanism** per default treatment only.

### Expansion `policy-bootstrap-template`

Emitted on first DISTILL in a project (file absent):

```markdown
# ATDD Infrastructure Policy

Per `nw-distill-port-treatment-policy`. One file per project. Apply-if-exists; write-if-absent; rewrite with `--policy=fresh`. Git history is the audit trail.

## Driving
| Port | Mechanism | Note |
|---|---|---|

## Driven internal (real)
| Port | Mechanism | Note |
|---|---|---|

## Driven external / non-deterministic (fake)
| Port | Fake | Note |
|---|---|---|
```

## Walking Skeleton Strategy + canonical definition

The 4-way per-feature choice (Strategy A/B/C/D) is REPLACED by two structural decisions: the Architecture of Reference (port-class treatment, once per project) + the Project Infrastructure Policy (concrete mechanism, once per project). Per-feature, DISTILL reads policy (`--policy=inherit` default), appends missing rows, or rewrites (`--policy=fresh`).

### Canonical definition (Cockburn / GOOS)

A walking skeleton is the **thinnest slice of real functionality that runs end-to-end** — from the real entry point through the real architectural components to a terminal on real data — and which can be **automatically built, deployed, and tested** (Cockburn, *Crystal Clear*, paraphrase). In GOOS (Freeman & Pryce) the consequence is operative: **the first acceptance test IS the walking skeleton**, written outside-in before any production code. Because the test drives the real entry point and asserts a real terminal effect, fixture-theater is impossible **by construction** (cross-ref the protocol-driver contract in `nw-test-design-mandates-composition-contract`, the SSOT for the tautological-test anti-pattern).

Default: **every feature is applicable** — it has a real entry point and a real terminal. Only three honest cases exempt a feature, and the declared exemption is **verified by inspecting the feature's changeset** (filesystem inspection of changed files, NOT a mechanical git invocation — gates depend only on Python + filesystem):

| # | "Not applicable" case | Condition | Delta check |
|---|---|---|---|
| 1 | Pure library, no entry point | adds only importable functions/types; no CLI/HTTP/hook/composition entry | no new driving adapter or `__main__`/subcommand in delta |
| 2 | Internal refactor, no new public interface | behavior-preserving restructure; existing ATs cover the surface | no net-new public symbol reachable from an entry point |
| 3 | Config-or-docs-only | change is markdown/yaml/config; no executable behavior path | delta touches only `*.md` / `*.yaml` / config, zero `src/` behavior |

Declaring not-applicable requires naming the case (1/2/3) in `wave-decisions.md`; a delta that contradicts the declaration (e.g. a new subcommand under case 1) is a BLOCKER. Reference: `docs/research/walking-skeleton-atdd-best-practices-2026-06-12.md` (findings A1–A6).

Survives from the old section:

- **Walking-skeleton SCENARIO**: still required (unless a case 1/2/3 exemption is declared and delta-verified). One per feature, tagged `@walking_skeleton @driving_port`, closing the end-to-end loop through the production composition root. Litmus: a non-technical stakeholder confirms "yes, that is what users need."
- **Tagging convention** (unchanged):
  - `@real-io` — scenario uses real adapters (driving + driven-internal per Architecture of Reference)
  - `@in-memory` — scenario uses in-memory doubles (Tier B state-machine PBT, or in-memory acceptance per Mandate 10)
  - `@requires_external` — scenario needs an external system not in the project policy; skip if absent
  - Walking-skeleton scenarios MUST carry `@walking_skeleton @driving_port` and use the production composition root.

**Migration note**: existing features naming Strategy A/B/C/D in `wave-decisions.md` still validate — historical record. NEW features express the same intent via Architecture of Reference defaults + per-port project-policy entry.
