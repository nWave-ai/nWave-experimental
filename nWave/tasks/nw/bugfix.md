---
description: Routes one observed defect Request into the DES steps.
argument-hint: '[observed defect]'
---
# NW-BUGFIX

Interactive: invoke the first step, read its terminal, follow its `NEXT`.

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```

Autonomous: one composed run of the same path.

```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT
```
Then invoke the step each block names in its `NEXT` line. The floor holds for a fix as for anything else: `des craft` refuses a value whose oracle is not recorded, and the source-blind EXAMINE inside `des verify` is never skipped. Each step returns only `Success`, `Refusal`, `Retry`, or `Indeterminate`.
