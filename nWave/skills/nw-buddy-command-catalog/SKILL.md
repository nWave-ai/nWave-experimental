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
| Start any delivery request | `printf '%s' "$REQUEST" \| des po --repo-root ROOT --feature FEATURE_ID` |
| Continue, or resume after an interruption | `des state --repo-root ROOT`, then have the LLM assess the advisory `NEXT` and current evidence before choosing a supported operation |
| Read the state as a person | `des project --repo-root ROOT` |
| Construct reviewer input after native verify | `des prepare-role --repo-root ROOT --role reviewer --candidate SHA` |
| Construct examiner input from caller-captured public observations | `des prepare-role --repo-root ROOT --role examiner --candidate SHA --observations PATH` |
| Record an LLM-hosted role result | `des record-role-result --repo-root ROOT --role reviewer\|examiner --candidate SHA --provider PROVIDER --model MODEL --session-id SESSION --input -` |
| Explicitly invoke one configured reviewer or examiner | `des invoke-role --repo-root ROOT --role reviewer\|examiner --candidate SHA --provider PROVIDER --input INPUT` |
| Select an explicit Codex or Claude model for DES | Use `nw-rigor`, then run its matching `nwave-ai model set --provider PROVIDER --model MODEL [--role ROLE] [--project]` command |

Every step returns `Success`, `Refusal`, `Retry`, or `Indeterminate`, and may name a successor as advisory data in `NEXT`. For features and bugfixes, the LLM evaluates and revises S/M/L and chooses applicable waves or upstream correction from evidence; DES neither maps size to a route nor executes `NEXT`. No command composes the steps into a sequence.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.
