---
name: nw-buddy-command-catalog
description: Current public nWave delivery commands.
user-invocable: false
disable-model-invocation: true
---
# Command Catalog
| Need | Command |
|---|---|
| Start any delivery request | `printf '%s' "$REQUEST" \| des po --repo-root ROOT` |
| Continue, or resume after an interruption | `des state --repo-root ROOT`, then have the LLM assess the advisory `NEXT` and current evidence before choosing a supported operation |
| Read the state as a person | `des project --repo-root ROOT` |
| Select an explicit Codex or Claude model for DES | Use `nw-rigor`, then run its matching `nwave-ai model set --provider PROVIDER --model MODEL [--role ROLE] [--project]` command |

Every step returns `Success`, `Refusal`, `Retry`, or `Indeterminate`, and may name a successor as advisory data in `NEXT`. For features and bugfixes, the LLM evaluates and revises S/M/L and chooses applicable waves or upstream correction from evidence; DES neither maps size to a route nor executes `NEXT`. No command composes the steps into a sequence.
