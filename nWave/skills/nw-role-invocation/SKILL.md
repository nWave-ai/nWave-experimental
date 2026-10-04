---
name: nw-role-invocation
description: "KNOWLEDGE — how a wave entrypoint invokes its specialist: the real installed role definition, never a generic persona. Load when a wave delegates to a role."
user-invocable: false
disable-model-invocation: true
---

# nw-role-invocation (KNOWLEDGE)

Reference for wave entrypoints. No sequence; the LLM chooses waves and operations. DES constructs documents/facts and suggests `NEXT`; it never governs progression.

## Rule

Delegate to the exact installed role definition (`nw-<role>`), with its real instructions and mandatory frontmatter skills. Missing mandatory instructions stop delegation; never substitute a generic persona. Conditional skills load on the role's own triggers. The LLM/native host owns model execution, provider/model/effort selection and orchestration. DES never launches a model.

## Invocation forms

For native delegation, select the installed specialist in the host tool:
Claude `Agent(subagent_type="nw-solution-architect", prompt=...)`;
Codex `spawn_agent(agent_type="nw-solution-architect", message=...)`.
Substitute the exact role below, and pass the bounded task and its evidence.
Do not select a generic agent and replace its definition with persona prose.
The host's native tool may be named `Agent` or `Task`; use whichever it
supports to select the exact installed role, with only parameters it supports.
The wave caller invokes the role; the role does the semantic work and returns
facts. If the native delegation tool cannot start that exact role with its
declared tools ceiling, use a supported native CLI invocation or report the
missing capability. Never substitute a generic worker or grant extra tools.

| Need | Exact installed role | Deterministic DES operation after host work |
|---|---|---|
| Product decomposition | `nw-product-owner` | `des po --repo-root ROOT --feature ID --input -` accepts the complete DISCUSS v2 manifest |
| Solution architecture | `nw-solution-architect` | `des design --repo-root ROOT --value N --input -` accepts the complete DESIGN manifest |
| Acceptance oracle | `nw-acceptance-designer` | Host authors the oracle; `des oracle --repo-root ROOT --value N --input -` measures and records it |
| Implementation | `nw-software-crafter` / `nw-functional-software-crafter` | Host authors the change; `des craft --repo-root ROOT --value N --input -` measures GREEN and records it against the current oracle |
| Candidate review / EXAMINE | `nw-software-crafter-reviewer` / `nw-user-examiner` | `des prepare-role`, native role invocation, then `des record-role-result` |
| Operational facts | `nw-platform-architect` | `des devops ... --input -` constructs the supplied facts |

### Selected independent operational review

When the authorized DESIGN or DEVOPS task selects independent platform review, the native wave caller invokes `nw-platform-architect-reviewer` on the actual current operational authority, its bound facts, authorized scope and available observations. Use the existing native invocation form and the reviewer's declared ceiling; no producer judgment substitutes for its result.

This is caller-owned orchestration, not a new review-task payload or a DES operation. Keep the DESIGN/`OperationalDocumentInput` constructor input closed: add no delegation, reviewer or result fields. The caller consumes the actual verdict and findings. An enabled selected review with required revisions or unresolved load-bearing evidence remains incomplete and returns its findings to the platform authority owner. A configured or human-authorized skip is reported as skipped, never approved. Constructor success does not establish review approval or authorize rollout.

Reuse adequate authority without a new producer turn; do not add a review for a no-op when none is selected. Missing exact-role invocation capability is explicit, never a generic substitute or invented result.

Oracle recorder input is `{"structured_output":{"outcome":"accepted","diagnostic":"..."}}`.
Craft additionally requires `"blocked_by":null` for accepted results; a
nonaccepted result names `product`, `design`, or `oracle`. These envelopes
record host work; they do not author files or replace actual RED/GREEN.

For an applicable bound prefactoring decision, the host records actual native
preservation runs with `des craft --repo-root ROOT --value N
--prefactoring-phase before-move` and, after only the declared movement,
`--prefactoring-phase after-move-before-behavior`. These measure preservation
without `--input`; they neither invoke the crafter nor replace the ordinary
feature RED/GREEN record. The advisory `NEXT` names the owed phase before
`des oracle` and a phase refusal retries as that phase; DES executes neither.
Keep the intermediate production and unchanged
oracle/support/runtime identities required by `nw-code-craftsmanship`.

For selected-revision recovery, explicitly select the acceptance designer:
`des prepare-role --repo-root ROOT --role acceptance-designer --task selected-revision-recovery --value N --finding -`.
Pass its exact sealed `INPUT`, required skills and output schema to the native
role. Record the host envelope with `des record-role-result --repo-root ROOT
--role acceptance-designer --task selected-revision-recovery --value N
--prepared-input INPUT --provider {claude,codex} --model MODEL --session-id SESSION
--input -` (no candidate). An accepted result includes the complete
`distill_document` v2. Pass the reported document bytes unchanged to
`des distill --repo-root ROOT --replace-current --input -` only if you choose
that correction. DES does not retry or select a successor.

If the document does not answer the finding, prepare a corrected finding.
Each distinct finding seals a distinct INPUT; invoke the new packet rather
than replaying an obsolete packet or rebuilding the handover.

## Constructors

`des discuss|po|design|distill|devops ... --input -` construct documents from host-supplied semantic facts. They invoke no role. Configuration retains explicit provider/model/effort facts for the native host where supported; it is not a DES executor or fallback policy.
Constructing returned facts never replaces invoking the role: a caller that
authors the facts itself has skipped the specialist. Suitable existing durable
authority may be reused as already allowed; no role turn is added for a no-op.

## Scope

DISCUSS, PO and DEVOPS require exactly one of `--project`, `--epic ID`, `--feature ID`, `--slice FEATURE_ID SLICE_ID`. DESIGN and DISTILL inherit the persisted scope. Output paths come from configuration and the constructor's report; hardcode none.

Resolve effective configured destinations, bound section headings, repository
naming/discovery conventions and scope once and pass them to all affected roles.
Include the original Request, authorized human exclusions/amendments and their
provenance in ordinary role/review handoffs; producer-only scope reduction is
not authorization. Do not ask the human to repeat a known configuration rule.
EXAMINE gets only the authorized behavioral contract within its source-blind
boundary, never architecture, oracle, selectors or producer classifications.

Supply canonical constructor grammar, exact task and actual tool ceiling. A
Read-only PO cannot run `des ... --describe-input`: the host retrieves and passes
the grammar and immutable supplied facts, then constructs the role's returned
manifest unchanged. StructuredOutput is available only if the native host
actually supports it. Consume all field/chunk views and authenticate their
reconstruction against the independently retained `INPUT-SHA256`, not a digest
inside the mutable views manifest. Record against the sealed original `INPUT`.
Truncated diff prose is not complete review. Caller-supplied free-text scope
context stays on the ordinary reviewer side; EXAMINE uses only its permitted
behavioral contract and public observations.
Reference `nw-typesafe-system-one` for role-owned unchanged-request relay;
a skill mention is not evidence of client/caller-exchange capability.

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

The preimplementation acceptance reviewer receives the dedicated host-supplied
packet defined by `nw-at-completeness-check`, including oracle/support evidence
and authorized scope. A candidate reviewer `prepare-role` packet is not that
packet and must not be advertised as available before implementation.

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
declared substrate, or judge the observations. Use the exact `INPUT` it prints.
Successful preparation also prints `ROLE-ID` and `RESULT-SCHEMA` (compact JSON
Schema). Supply that exact schema to native structured output: reviewer defect
values are packet-bound, examiner output is payload-free, and recovery uses its
closed semantic-task schema. Wrap the returned object as `{"structured_output":
RESULT_OBJECT}` for `record-role-result`; preserve actual host provenance.

A tools-empty examiner must receive the permitted packet bytes in a fresh
source-blind context, not repository access or a path it cannot read. On the
current Claude host, native Agent cannot start a tools-empty role; use the
native CLI with `--agent nw-user-examiner --tools '' --allowedTools
StructuredOutput --json-schema SCHEMA`, supplying its mandatory skills,
bound packet and required output schema. Keep production/oracle sources
unmounted and absent from the prompt. Do not add Read to repair this limit.
The code reviewer retains its normal declared Read capability.

Bind each reviewer or examiner result to its exact content-addressed input revision:

```bash
printf '%s' "$RESULT" | des record-role-result --repo-root ROOT --role examiner \
  --candidate SHA --provider {claude,codex} --model MODEL --session-id SESSION \
  --input - --prepared-input INPUT
```

`--prepared-input` selects the precise prepared revision rather than guessing
the newest packet; it is required for reviewer, examiner and recovery recording.
The examiner reads the packet, its provenance and any native-detail withholding
markers; it returns `INDETERMINATE` for behavior that lacks an observation. The
reviewer is unaffected and receives its existing full evidence. The examiner
receives observations and the original value/Request, never production source
or oracle source. An oracle reviewer receives the oracle bytes; a code reviewer
with `Read` can inspect the candidate at its supplied paths. Absent evidence is
`INDETERMINATE`; adding tools is not the repair.

## Currentness and candidate lifecycle

Read current state before choosing the next host action. Reuse unchanged adequate
semantic authority/alignment selectively by value and consumed prerequisites;
native remeasurement is not automatic reauthoring or transitive role replay.
Source identity alone is insufficient when contract/oracle/runtime changed.
Distinguish missing facts, graph drift, owned/upstream bytes drift and destination
drift and route their concrete causes to the owner. A step's Success does not
close the authorized Request; continue until real obligations and integration
are current, stopping for a genuine human checkpoint/choice, not a recoverable
mechanical fact.

Agree commit/staging/install lifecycle before craft, retain actual before/after
revisions, and preserve candidate snapshots/evidence when disposable execution
workspaces are removed. Owned source/test/support/authority edits after VERIFY
need a new candidate/current independent review; never restamp an old approval.
Archived graphs remain historical, not automatically reactivated. Destination CAS,
foreign bytes and staging are preserved; no reset recipe or cleanup of user WIP.
Probes use invocation-local disposable scope or declared nonowned output, retain
their receipt and remove only their own files. Preflight actual native processes,
ports, writable build/temp/cache and separate space/inode requirements; provider
auth/quota/timeout, machine/setup failure and product rejection stay distinct.

Reuse native execution evidence only when source, oracle/supports, argv/cwd,
environment/toolchain/substrate, consumed contracts and purpose remain identical
and the assurance permits it. Independent review and stress have distinct
purposes; neither is a producer cache. Require authentic native attribution of
assertion versus setup/build/import failure where observable, otherwise
INDETERMINATE. Missing counts/reporters or unknown code-fact radius never become
zero. Accounting uses actual timeline overlap, root/child session dedup and
returned provider/Jev usage; interrupted or missing cost is unknown, not zero.

## Waiting

For native model subagents, use host completion notifications or their actual
completion handle. For a long-running native CLI/process, retain and resume its
real process handle until terminal output arrives. Never use fixed sleeps,
silence, or an invented notification as evidence of completion; never launch a
duplicate invocation while the first remains active.

## Human interaction

Offer interaction per `nw-human-collaboration`; honor an already chosen mode.
