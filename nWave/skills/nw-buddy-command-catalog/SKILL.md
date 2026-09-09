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
| Continue, or resume after an interruption | `des state --repo-root ROOT`, then the step its `NEXT` line names |
| Read the state as a person | `des project --repo-root ROOT` |
| Select an explicit Codex or Claude model for DES | Use `nw-rigor`, then run its matching `nwave-ai model set --provider PROVIDER --model MODEL [--role ROLE] [--project]` command |

Every step returns `Success`, `Refusal`, `Retry`, or `Indeterminate`, and names its canonical successor as data in `NEXT`. No command composes the steps into a sequence.
