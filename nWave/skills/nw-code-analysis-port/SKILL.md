---
name: nw-code-analysis-port
description: "KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact."
user-invocable: false
---

# nw-code-analysis-port (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference / discipline). Consulted whenever you need a fact about code. No forced sequence — load it, obey the resolution rule.

## TRIGGER

Any time you design, write, analyze, or review code or tests and need a code fact — who calls X, where Y is defined or read, the call graph, the blast-radius of a change, or what a file contains — resolve it **through the vendor-neutral `des code-fact` CLI**, not ad-hoc grep.

## Public CLI — available now

The five-capability public stable core is wrapped in the production CLI:

```bash
des code-fact query.callers-of SYMBOL --root ROOT
des code-fact query.reads-of SYMBOL --root ROOT
des code-fact query.never-wired SYMBOL --root ROOT
des code-fact query.atoms-in-file --root FILE_OR_ROOT
des code-fact query.adr-section ANCHOR --root ROOT
```

The CLI returns JSON: `{ provider, confidence, payload, trace }`. Agents consume that envelope and degrade LOUD; they never probe/install/select an analyzer themselves.

## The resolution rule (one order, every time)

The CLI delegates to the best available bundled adapter. You report the answer tagged with which adapter answered.

| Rank | Adapter | Confidence label | When it answers |
|------|---------|------------------|-----------------|
| 1 (best) | AST | `approx` | any parseable Python target — structural, deterministic |
| 2 (floor / LAST resort) | TextSearch (grep/stdlib `re`) | `noisy` | universal floor — lexical only |

- AST gives `approx` confidence (structural, per-language) on any parseable target.
- grep / lexical search is the **last resort**, never the default. Reach for it only when AST cannot answer.

## DEGRADE-LOUD (never silent)

- Always state which adapter answered and at what confidence: `approx` | `noisy`.
- If the answer came from **TextSearch (grep)**, announce the degradation AND its limits. Example: "AST unavailable → grep fallback (`noisy`): may include false positives, miss dynamic/indirect references, and conflate same-named symbols."
- Never silently let grep stand in for the port. A `noisy` answer presented as fact is the failure mode this skill exists to prevent.
- The CLI's `trace` array names which provider answered and its scan-scope honesty (`complete` | `filtered` | `unfiltered`) — that per-query record is the loud announcement a gate reads.

## Operations quick-reference (question → CLI command)

| Code fact you need | CLI command | Stable |
|--------------------|-------------|--------|
| Who calls X? | `des code-fact query.callers-of SYMBOL --root ROOT` | yes |
| Where is Y read / referenced? | `des code-fact query.reads-of SYMBOL --root ROOT` | yes |
| Is this symbol defined-but-never-wired/used? | `des code-fact query.never-wired SYMBOL --root ROOT` | yes |
| What atoms (defs/symbols) does this file contain? | `des code-fact query.atoms-in-file --root FILE_OR_ROOT` | yes |
| What does an ADR / design-prose section say? | `des code-fact query.adr-section ANCHOR --root ROOT` | yes |
| Call graph / change-scope / scope-delta | **unsupported by stable CLI** — use bounded stable queries + manual inspection with explicit limitation note | no |

The five stable-core capabilities answer on any Python-only target. A capability with no covering adapter returns no answer (none faked), records the honest failure in `trace`, and the work proceeds — do NOT substitute grep and call it the same fact.

## Invocation — how to use the CLI

For ANY structural code fact, call the CLI directly:

1. **Stable-core queries** — use `des code-fact query.<capability>` with the exact form above.
   - The CLI parses JSON and emits it; consume the `provider`, `confidence`, and `payload` fields.
   - Inspect `trace` for the answering provider + scan-scope honesty (AST unavailable → TextSearch fallback).
2. **Beyond the five capabilities** — feature-level change-scope / call-graph analysis has no stable CLI today.
   Say so and take the fallback: bounded stable queries (e.g. `query.callers-of` per known seams) + manual inspection + explicit limitation note.
3. **Bundled additive tool** — `des find-similar-responsibility --scope ROOT --name NAME` is a purpose-specific addition to `des code-fact`, not an external provider dependency.

Tag every answer with provider + confidence (`approx` | `noisy`). Defaulting to grep/Read for a structural fact (callers/reads/never-wired/atoms) is the anti-pattern this skill exists to prevent — CLI first, grep last.


## WHY through the CLI, not grep

- **Structural vs lexical.** AST is structural and reports `approx` confidence; TextSearch (grep) is lexical and reports `noisy` confidence. grep over-reports (same-named symbols, comments, strings) and under-reports (dynamic/indirect refs).
- **Confidence is carried, not assumed.** Every answer comes back in a `{provider, confidence, payload, trace}` envelope. The confidence label is the honesty signal — a consumer can see whether a fact is `approx` or merely `noisy`.
- **`reason_code` disambiguates** `live-non-callable` from `absent` inside a capability's own `payload` (e.g. `query.never-wired`) — a distinction grep cannot make. Degrade signals — which adapter answered, and its scan-scope honesty — live in the envelope's `trace`: per-query entries carrying `provider_id`, `event`, `fault_count` and `scope`.
- **One seam, no per-task `import ast`.** Re-deriving a fact through one honest provider beats each agent hand-rolling its own search.

## Implementation (internal reference)

The public CLI wraps:
- Port: `src/des/ports/code_fact_port.py` — `CodeFactPort.query(descriptor, request) -> CodeFactResult`; `Confidence {approx, noisy}`, `ReasonCode {live-non-callable, absent}`; 5-capability stable core; `resolve_through_fold` is the resolution algebra (`Resolution = Answered | Unsupported | Failed`, each with a bounded `trace`).
- Resolution chain (the fallback order): `src/des/adapters/driven/codefact/code_fact_chain.py` — `CodeFactChain` is a stateless `Ast -> TextSearch` fold (ADR-LA-001 D6-R1: the retired paid precision seam was a fabricated stub no production caller ever wired — deleted, not shipped in OSS); `src/des/cli/code_fact.py` renders the winning `Answered.payload` + the bounded `Resolution.trace` as JSON.
- Bundled adapters: `ast_code_fact_adapter.py` (`approx`), `text_search_code_fact_adapter.py` (`noisy` floor).

## Scope note

This complements — it does NOT replace — reading the code and tests. Use the port to LOCATE facts (callers, definitions, references, atoms) precisely; then read the located code to understand it. The port answers "where / who / what", not "is this correct".
