---
name: nw-deliver
description: Routes one strict Request into the DES steps that deliver it.
user-invocable: true
argument-hint: '<request>'
---
# NW-DELIVER
Interactive, one step at a time:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
Then invoke the step each block names in its `NEXT` line, until integration closes the Request. Each step owns one thing — the Product Owner decomposition, the design facts, the public oracle, the change, the candidate with its independent review and source-blind examination, which is never skipped, the integration — and returns. The sequence is yours; no command composes it. `nw-auto` owns that loop. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.
