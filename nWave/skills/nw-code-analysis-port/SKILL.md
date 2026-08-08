---
name: nw-code-analysis-port
description: "KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring graphify (Tsunami temporarily disabled), then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact."
user-invocable: false
---

# nw-code-analysis-port (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference / discipline). Consulted whenever you need a fact about code. No forced sequence — load it, obey the resolution rule.

## TRIGGER

Any time you design, write, analyze, or review code or tests and need a code fact — who calls X, where Y is defined or read, the call graph, the blast-radius of a change, or what a file contains — resolve it **through the nWave code-analysis port (`CodeFactPort`)**, not ad-hoc grep.

## TEMPORARY — Tsunami is disabled, graphify holds tier 1 (2026-08-07)

Ale's standing instruction of 2026-08-06, made operational on 2026-08-07: **all
code analysis goes through graphify until Tsunami returns.** The `tsunami` MCP
server has been moved out of `mcpServers` in `~/.claude/mcp.json`, so the
`mcp__tsunami__*` tools no longer mount. **Do not reach for them** — they fail
by absence, which is a rejection with no message.

This is a change of ADAPTER, not of DISCIPLINE. Everything below still holds:
resolve structural facts through the port, tag the provider and confidence,
degrade LOUD, and never let grep stand in silently. `CodeFactChain` in `src/`
is unchanged and needs no change — with Tsunami unmounted it does exactly what
it was built to do, skipping the absent tier LOUDLY and proceeding to AST.

**Reversal is one rename**: move the entry back from
`_disabled_2026_08_07_tsunami_redirected_to_graphify` into `mcpServers`, then
restore the tier-1 rows here and in `des.cli.dispatch._DEFAULT_SKILL_LOADING`.

## The rule (one resolution order, every time)

The port resolves to the best available adapter. You report the answer tagged with which adapter answered.

| Tier | Adapter | Confidence label | When it answers |
|------|---------|------------------|-----------------|
| 1 (best, CURRENT) | graphify | `binding-resolved` | a graph is built (`graphify-out/graph.json`) — extracted, binding-resolved edges |
| 1 (SUSPENDED) | Tsunami | `binding-resolved` | temporarily disabled — see the section above; do not call `mcp__tsunami__*` |
| 2 | AST | `approx` | any parseable target — structural, per-language |
| 3 (floor / LAST resort) | TextSearch (grep/stdlib `re`) | `noisy` | universal Python-only floor — lexical only |

- Prefer graphify when a graph exists (deterministic, extracted structural facts). On a target with no `graphify-out/graph.json` the tier is ABSENT — the NORMAL case — and you skip it LOUDLY and proceed to AST.
- grep / lexical search is the **last resort**, never the default. Reach for it only when AST and graphify cannot answer.

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
| Call graph / change-scope / scope-delta | outside the stable-5 core — today `graphify path` / `explain` answers it; historically `query.tsunami-call-graph` | no |

The five stable-core capabilities answer on any Python-only target (the floor always covers them). A Tsunami-only capability with Tsunami absent has no covering lower tier: the port returns no answer (none faked), records the loud skip, and the work proceeds — do NOT substitute grep and call it the same fact.

## Invocation — how to actually run it

graphify is a CLI, so it needs Bash. Check `command -v graphify` and that
`graphify-out/graph.json` exists; if either is missing, that tier is absent —
say so and drop to AST. For ANY structural code fact, reach for these FIRST:

1. **Tier-1 — graphify CLI via Bash** (use FIRST):
   - Who calls X? Where is Y read? → `graphify explain "<symbol>"` — it prints the
     node plus every incoming/outgoing edge, labelled (`[calls]`, `[contains]`,
     `[rationale_for]`), each with its source file and line. Verified on this
     repo 2026-08-07: `graphify explain "build_guard_command"` returned the one
     real caller, `_plugin_guard_command()` at `scripts/build_plugin.py:L505`.
   - How does A reach B? → `graphify path "A" "B"` (shortest path in the graph).
   - Same-endpoint edge-collapse risk in the graph itself → `graphify diagnose multigraph`.
   - Defaults to `graphify-out/graph.json`; override with `--graph <path>`.
2. **Tier-1 note — `never-wired` and `adr-section` have no graphify equivalent.**
   Do not fake them from `explain` output. Treat them as unanswered at tier 1,
   say so, and drop to AST — an absent capability with no covering tier returns
   NO answer, never a substituted one.
3. **Tier-2 — AST** when graphify is absent or cannot answer (`approx`).
4. **Tier-3 — grep / `re`** ONLY as the LAST resort (`noisy`) — announce the degradation + its limits.

Reviewers without Bash cannot reach tier 1 at all while Tsunami is disabled —
the MCP tools were what made tier 1 reachable without a shell. Give a reviewer
that needs structural facts Bash, or accept an `approx` answer and say so.

Tag every answer with provider + confidence (`binding-resolved` | `approx` | `noisy`). Defaulting to grep/Read for a structural fact (callers/reads/never-wired/atoms) is the anti-pattern this skill exists to prevent — port first, grep last. **End-state**: a `des code-fact <capability> <arg>` CLI wrapping `CodeFactChain` (not yet built).


## WHY through the port, not grep

- **Precise vs lexical.** graphify/Tsunami/AST resolve bindings; grep matches text. grep over-reports (same-named symbols, comments, strings) and under-reports (dynamic/indirect refs).
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
