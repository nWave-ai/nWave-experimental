---
name: nw-bugfix
description: Routes an observed defect request into the DES steps that deliver the fix.
user-invocable: true
argument-hint: '<observed defect>'
---
# NW-BUGFIX
Set the observed defect as `$REQUEST`:
Interactive, one step at a time:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
For this bugfix, the LLM evaluates and revises an evidence-based S/M/L assessment, decides applicable waves or an upstream authority correction, and chooses each supported operation. `NEXT` is advisory and may be ignored; DES never maps size to a route or invokes it. A command may refuse when its required input or recorded data is absent, so a fix uses its observed refusal evidence before changing code. The source-blind EXAMINE lives inside `des verify` and is never skipped: a fix no one observed working is not a fix. `nw-auto` owns that guidance. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.
