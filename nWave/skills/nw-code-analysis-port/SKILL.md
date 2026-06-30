---
name: nw-code-analysis-port
description: "KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact."
user-invocable: false
---

# nw-code-analysis-port (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference / discipline). Consulted whenever you need a fact about code. No forced sequence — load it, obey the resolution rule.

## TRIGGER

Any time you design, write, analyze, or review code or tests and need a code fact — who calls X, where Y is defined or read, the call graph, the blast-radius of a change, or what a file contains — resolve it **through the nWave code-analysis port (`CodeFactPort`)**, not ad-hoc grep.

## The rule (one resolution order, every time)

The port resolves to the best available adapter. You report the answer tagged with which adapter answered.

| Tier | Adapter | Confidence label | When it answers |
|------|---------|------------------|-----------------|
| 1 (best) | Tsunami | `binding-resolved` | installed + probe passes — precise, binding-resolved structural facts |
| 2 | AST | `approx` | any parseable target — structural, per-language |
| 3 (floor / LAST resort) | TextSearch (grep/stdlib `re`) | `noisy` | universal Python-only floor — lexical only |

- Prefer Tsunami when installed (deterministic structural facts). On a plain target Tsunami is ABSENT — the NORMAL case — and the chain skips it LOUDLY and proceeds to AST.
- grep / lexical search is the **last resort**, never the default. Reach for it only when AST and Tsunami cannot answer.

## DEGRADE-LOUD (never silent)

- Always state which adapter answered and at what confidence: `binding-resolved` | `approx` | `noisy`.
- If the answer came from **below** Tsunami, announce the degradation AND its limits. Example: "Tsunami unavailable → grep fallback (`noisy`): may include false positives, miss dynamic/indirect references, and conflate same-named symbols."
- Never silently let grep stand in for the port. A `noisy` answer presented as fact is the failure mode this skill exists to prevent.
- The chain emits `health.gate.code-fact.*` skip events when it skips an absent tier — that event IS the loud signal a gate reads.

## Operations quick-reference (question → port capability)

| Code fact you need | Port capability | Stable-core |
|--------------------|-----------------|-------------|
| Who calls X? | `query.callers-of` | yes |
| Where is Y read / referenced? | `query.reads-of` | yes |
| Is this symbol defined-but-never-wired/used? | `query.never-wired` | yes |
| What atoms (defs/symbols) does this file contain? | `query.atoms-in-file` | yes |
| What does an ADR / design-prose section say? | `query.adr-section` | yes |
| Call graph / change-scope / scope-delta | Tsunami-only capability (e.g. `query.tsunami-call-graph`) — outside the stable-5 core | no |

The five stable-core capabilities answer on any Python-only target (the floor always covers them). A Tsunami-only capability with Tsunami absent has no covering lower tier: the port returns no answer (none faked), records the loud skip, and the work proceeds — do NOT substitute grep and call it the same fact.

## Invocation — how to actually run it

PREFER the Tsunami MCP tools. They are real tools in your toolset (no Bash needed — so reviewers can use them too), and they are the surest way you ACTUALLY use Tsunami instead of defaulting to grep/Read. For ANY structural code fact, reach for these FIRST:

1. **Tier-1 — Tsunami MCP tools** (use FIRST when present in your toolset):
   - Who calls X? → `mcp__tsunami__callers_of`
   - Where is Y read? → `mcp__tsunami__reads_of`
   - Defined-but-never-wired (seam-rot)? → `mcp__tsunami__never_wired`
   - Atoms in a file? → `mcp__tsunami__atoms_in_file`
   - ADR / design-prose section? → `mcp__tsunami__adr_section`
2. **Tier-1 fallback — Tsunami CLI via Bash** (ONLY if you have Bash AND the MCP tools are absent; check `command -v tsunami`): `tsunami query callers-of|reads-of|never-wired|atoms-in-file <arg>`; `tsunami adr-section <file>` (top-level, NOT under `query`).
3. **Tier-2 — AST** when Tsunami is absent or cannot answer (`approx`).
4. **Tier-3 — grep / `re`** ONLY as the LAST resort (`noisy`) — announce the degradation + its limits.

Tag every answer with provider + confidence (`binding-resolved` | `approx` | `noisy`). Defaulting to grep/Read for a structural fact (callers/reads/never-wired/atoms) is the anti-pattern this skill exists to prevent — Tsunami first, grep last. **End-state**: a `des code-fact <capability> <arg>` CLI wrapping `CodeFactChain` (not yet built).


## WHY through the port, not grep

- **Precise vs lexical.** Tsunami/AST resolve bindings; grep matches text. grep over-reports (same-named symbols, comments, strings) and under-reports (dynamic/indirect refs).
- **Confidence is carried, not assumed.** Every answer comes back in a `{provider, confidence, reason_code}` envelope. The confidence label is the honesty signal — a consumer can see whether a fact is `binding-resolved` or merely `noisy`.
- **`reason_code` disambiguates** `live-non-callable` from `absent` — a distinction grep cannot make.
- **One seam, no per-task `import ast`.** Re-deriving a fact through one honest provider beats each agent hand-rolling its own search.

## Where this lives (cite accurately)

Real, on this branch (ADR-LA-001, OSS implementation):
- Port: `src/des/ports/code_fact_port.py` — `CodeFactPort.query(descriptor, request) -> CodeFactResult`; `Provider {tsunami, ast, textsearch}`, `Confidence {binding-resolved, approx, noisy}`, `ReasonCode {live-non-callable, absent}`; 5-capability stable core.
- Resolution chain (the fallback order): `src/des/adapters/driven/codefact/code_fact_chain.py` — `CodeFactChain` walks `Tsunami -> Ast -> TextSearch`, returns the first covering provider, emits `health.gate.code-fact.*` on a LOUD skip.
- Adapters: `tsunami_code_fact_adapter.py` (`binding-resolved`), `ast_code_fact_adapter.py` (`approx`), `text_search_code_fact_adapter.py` (`noisy` floor).
- No user CLI `des code-fact` exists yet — the port is consumed programmatically by gates (e.g. `src/des/cli/gate_g.py`). Until that CLI wraps the chain for you, see **§Invocation**: run the `tsunami` binary directly via Bash (tier-1), fall back to AST then grep, and label confidence yourself. (`des code-fact` wrapping `CodeFactChain` so the adapter resolves the tier behind one entry is the end-state — a follow-up build, not yet present.)

## Scope note

This complements — it does NOT replace — reading the code and tests. Use the port to LOCATE facts (callers, definitions, references, atoms) precisely; then read the located code to understand it. The port answers "where / who / what", not "is this correct".
