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
`des po` writes no durable authority. The documents a bugfix owes come from
the same typed producers a feature uses -- `des discuss`, `des design`,
`des devops`, `des distill` -- under global configuration with project
overrides, and the LLM writes none of them by hand. Keep the observed defect
verbatim in the DISCUSS authority, keep the DISTILL obligation on the same
observation the regression oracle answers, and keep the correction behind the
oracle `des oracle` measured RED against the defect. Every wave stays optional.

Then invoke the step each block names in its `NEXT` line. The floor holds for a fix as for anything else: `des craft` refuses a value whose oracle is not recorded, and the source-blind EXAMINE inside `des verify` is never skipped. Each step returns only `Success`, `Refusal`, `Retry`, or `Indeterminate`.
