---
name: nw-buddy-command-catalog
description: Current public nWave delivery commands.
user-invocable: false
disable-model-invocation: true
---
# Command Catalog
| Need | Command |
|---|---|
| Choose or change interactive collaboration, final human review, or full delegation | `/nw-mode-select` reuses `nw-human-collaboration`; preserves an existing choice and adds no DES gate |
| Start any delivery request | Native Product Owner supplies full DISCUSS v2; `printf '%s' "$DISCUSS_MANIFEST" \| des po --repo-root ROOT --feature FEATURE_ID --input -` |
| Continue, or resume after an interruption | `des state --repo-root ROOT`, then have the LLM assess the advisory `NEXT` and current evidence before choosing a supported operation |
| Read the state as a person | `des project --repo-root ROOT` |
| Construct reviewer input after native verify | `des prepare-role --repo-root ROOT --role reviewer --candidate SHA` |
| Construct examiner input from caller-captured public observations | `des prepare-role --repo-root ROOT --role examiner --candidate SHA --observations PATH` |
| Record an LLM-hosted role result | `des record-role-result --repo-root ROOT --role reviewer\|examiner --candidate SHA --prepared-input INPUT --provider {claude,codex} --model MODEL --session-id SESSION --input -`; use the exact `INPUT` returned by preparation |
| Invoke an independent reviewer or examiner | Native host selects the exact installed role and sealed input; follow `nw-role-invocation`, then `des record-role-result` |
| Select explicit host-consumable Codex or Claude model facts | Use `nw-rigor`, then its `nwave-ai model set --provider PROVIDER --model MODEL [--role ROLE] [--project]` command; DES never launches the model |

Every step returns `Success`, `Refusal`, `Retry`, or `Indeterminate`, and may name a successor as advisory data in `NEXT`. For features and bugfixes, the LLM evaluates and revises S/M/L and chooses applicable waves or upstream correction from evidence; DES neither maps size to a route nor executes `NEXT`. No command composes the steps into a sequence.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.

## Verification Workspace Configuration

Repository `.nwave/config.json` owns `verification.reuse.outputs` and
`verification.reuse.workspace`. Global configuration cannot relocate project
workspaces. `workspace.root` defaults to `lanes`; lane work, cold candidates
(`.des-candidate`) and the reusable checkout (`.des-verification`) stay beneath
that configured project directory. Paths must be repository-relative, without
symlink escapes or overlap with declared generated outputs.

`workspace.cache_limit_bytes` sets the local cache budget. Without a limit,
automatic maintenance does not evict caches for size. `workspace.automatic`
defaults to `true`; `false` disables automatic eviction, not the configured
budget check. An unmet or unobservable configured budget refuses new workspace
growth.

Only inactive DES-owned materializations are eligible for automatic eviction.
Unknown content, tracked or staged source, interrupted runs and unproven writers
are preserved. `workspace.adopt_outputs` explicitly authorizes ownership of
listed declared `outputs`; declare a path first, then adopt it only when it is
an exclusive DES cache with no other writers. Do not adopt shared or live caches.

Native process-group quiescence requires POSIX support. On non-POSIX platforms,
cold commands can execute, but the candidate remains non-idle and is retained
with a named recovery reason; portable automatic cleanup is not claimed.
