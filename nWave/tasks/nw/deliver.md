---
description: Routes one strict Request into the DES steps - decomposition, design facts, public oracle, craft, independent whole-diff review with source-blind examination, and integration.
argument-hint: '[request]'
---
# NW-DELIVER

Interactive: invoke the first step, read its terminal, follow its `NEXT`.

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```

Autonomous: one composed run of the same path.

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
Then invoke the step each block names in its `NEXT` line, until integration closes the Request. The source-blind EXAMINE inside `des verify` is never skipped. Each step returns only `Success`, `Refusal`, `Retry`, or `Indeterminate`. No command composes them; the loop is the caller's, and `nw-auto` owns it.
