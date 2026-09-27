---
name: nw-role-invocation
description: "KNOWLEDGE — how a wave entrypoint invokes its specialist: the real installed role definition, never a generic persona. Load when a wave delegates to a role."
user-invocable: false
disable-model-invocation: true
---

# nw-role-invocation (KNOWLEDGE)

Reference for wave entrypoints. No sequence; the LLM chooses waves and operations. DES constructs documents/facts and suggests `NEXT`; it never governs progression.

## Rule

Delegate to the exact installed role definition (`nw-<role>`), which carries its real instructions and declared frontmatter skills. Never write "act as an architect" or any generic fallback. Claude and Codex share role frontmatter skills through `load_role_instructions`; a mandatory declared skill that is missing fails before a paid turn. Conditional skills load on the role's own triggers.

## Invocation forms

For native delegation, select the installed specialist in the host tool:
Claude `Agent(subagent_type="nw-solution-architect", prompt=...)`;
Codex `spawn_agent(agent_type="nw-solution-architect", message=...)`.
Substitute the exact role below, and pass the bounded task and its evidence.
Do not select a generic agent and replace its definition with persona prose.
The host's native tool may be named `Agent` or `Task`; use whichever it
supports to select the exact installed role, with only parameters it supports.
The wave caller invokes the role; the role does the semantic work and returns
facts. If the named role is unavailable, use its supported DES operation or report
the missing installation; never silently substitute a generic worker.

| Need | Native host | DES role-buying operation (when host cannot select the exact role) |
|---|---|---|
| Product Owner decomposition | `nw-product-owner` | `des po --repo-root ROOT --feature ID` (or the scope flag) — decomposition only |
| Solution architect | `nw-solution-architect` | `des design --repo-root ROOT --value N` |
| Acceptance oracle (ATD) | `nw-acceptance-designer` | `des oracle --repo-root ROOT --value N` (authors the executable oracle after a corrected selection; cannot recover an incomplete/misaligned one) |
| DISTILL v2 manifest recovery (`SelectedRevisionIncomplete`/`RealignmentNeeded`) | `nw-acceptance-designer`, returns full manifest | `des prepare-role --role acceptance-designer --task selected-revision-recovery --value N --finding -`, then caller-selected `des invoke-role` with its exact INPUT |
| Crafter (OOP/FP per bound paradigm) | `nw-software-crafter` / `nw-functional-software-crafter` | `des craft --repo-root ROOT --value N` |
| Candidate reviewer / examiner | `nw-software-crafter-reviewer` / `nw-user-examiner` | `des prepare-role`, then `des invoke-role` (flags from `des invoke-role --help`) |
| DISCUSS, DEVOPS semantic facts | `nw-product-owner`, `nw-platform-architect` (native host) | none: their constructors take `--input` |

For recovery, the LLM explicitly selects `acceptance-designer`, provider and the
closed task. `prepare-role` seals current B, current DESIGN and the complete
finding; `invoke-role` buys exactly one installed-role turn and persists a v2
document only on `accepted`. DES does not select any of these inputs, retry,
run a test, or call DISTILL. The caller may pass the reported document bytes
unchanged to `des distill --replace-current --input -`. Reviewer and examiner
retain their candidate-bound contracts.

If the returned document does not answer the finding, do not replay the same
INPUT and do not rebuild the handover: submit a corrected finding with
`des prepare-role --role acceptance-designer --task selected-revision-recovery
--value N --finding -`. A different finding for the same authority binding
seals its own distinct INPUT (both are kept), so `des invoke-role` runs the
new INPUT the corrected preparation just printed.

## Constructors

`des discuss|design|distill|devops ... --input -` construct documents from semantic facts and buy no role turn. A native-host role returns the facts; the constructor writes the bytes.
Constructing returned facts never replaces invoking the role: a caller that
authors the facts itself has skipped the specialist. Suitable existing durable
authority may be reused as already allowed; no role turn is added for a no-op.

## Scope

DISCUSS, PO and DEVOPS require exactly one of `--project`, `--epic ID`, `--feature ID`, `--slice FEATURE_ID SLICE_ID`. DESIGN and DISTILL inherit the persisted scope. Output paths come from configuration and the constructor's report; hardcode none.

## Reviewer and examiner boundaries

For DISTILL before-code alignment, MUST read
`~/.claude/skills/nw-at-completeness-check/SKILL.md`. When the original value,
selected contract, and prior adequate alignment are unchanged with no new
finding, reuse it without another preimplementation assessment or ATD review.
Only for new, changed, or unresolved semantics, invoke the installed
`nw-user-examiner` natively with an explicit preimplementation assessment task
and only the original Request plus the same selected behavioral contract bytes
supplied to ATD. Keep its tools empty apart from structured output; provide
neither oracle/production source nor test-derived expectations. Return its
independent expectations to the existing ATD reviewer for the shared review.
An alignment verdict concerns observation feasibility and ambiguity, not runtime
acceptance; unavailable implementation evidence is not a failure of alignment.

Current DES examiner preparation requires a verified candidate. It projects the
selected DISTILL acceptance as source-blind ordered criterion id, stimulus,
expected observation, revision identity, and locator-withholding markers. Its
inputs are content-addressed revisions; corrected observations retain prior
inputs and results. It cannot serve a preimplementation assessment because no
verified candidate exists yet: use the native installed examiner for that task.
For final EXAMINE, use the prepared selected-acceptance projection; report a gap
only when that actual projection is unavailable, never by treating the broad
Request as equivalent. Invent no CLI flag, replace no sealed evidence, and make
no production edit just to obtain a new candidate. DES remains the durable
document writer; the LLM selects invocations.

Check the selected role's `tools` declaration. A tools-empty role, including
`nw-user-examiner`, cannot read paths: supply its permitted evidence bytes.
For EXAMINE, the caller first captures selected public stimuli, responses and
state snapshots for the verified candidate, then runs
`des prepare-role --repo-root ROOT --role examiner --candidate SHA --observations PATH`.
DES seals the caller-supplied packet after grammar, candidate, size and
known-path checks. It does not capture or select events, verify the packet's
declared substrate, or judge the observations. Use the exact `INPUT` it prints:

```bash
des invoke-role --repo-root ROOT --role examiner --candidate SHA \
  --provider PROVIDER --input INPUT
```

For a host-supplied examiner result, bind that same content-addressed revision:

```bash
printf '%s' "$RESULT" | des record-role-result --repo-root ROOT --role examiner \
  --candidate SHA --provider PROVIDER --model MODEL --session-id SESSION \
  --input - --prepared-input INPUT
```

`--prepared-input` belongs to `record-role-result`, not `invoke-role`; it
selects the precise prepared revision rather than guessing the newest packet.
The examiner reads the packet, its provenance and any native-detail withholding
markers; it returns `INDETERMINATE` for behavior that lacks an observation. The
reviewer is unaffected and receives its existing full evidence. The examiner
receives observations and the original value/Request, never production source
or oracle source. An oracle reviewer receives the oracle bytes; a code reviewer
with `Read` can inspect the candidate at its supplied paths. Absent evidence is
`INDETERMINATE`; adding tools is not the repair.

## Human interaction

Offer interaction per `nw-human-collaboration`; honor an already chosen mode.
