---
description: Routes one observed defect Request into the DES steps.
argument-hint: '[observed defect]'
---
# NW-BUGFIX

Load `nw-bugfix`, `nw-auto` and `nw-role-invocation`. Report the affected baseline
before authoring the regression oracle or changing production code.

Invoke the native installed Product Owner with the observed defect verbatim.
Construct its complete DISCUSS v2 manifest:

```bash
printf '%s' "$DISCUSS_MANIFEST" | des po --repo-root ROOT --feature FEATURE_ID --input -
```

Choose the explicit persisted scope. Applicable typed constructors write
DISCUSS, DESIGN, DEVOPS and DISTILL authorities; roles supply semantic facts,
not handwritten authority Markdown. Keep the defect and regression obligation
on the same public observation. The native acceptance designer authors the
oracle, then first `des oracle --value N --baseline <original pre-fix commit> --input -`
measures current oracle/support bytes as RED in the existing disposable checkout.
Do not use HEAD if the fix is already committed. Later corrections reuse the
recorded baseline without the flag; no source yields `OracleBaselineMissing`
with WHAT/WHY/HOW, never workspace measurement. The native crafter
implements the fix, then `des craft --value N --input -` measures GREEN.

The LLM evaluates advisory `NEXT`; DES neither chooses a route nor launches
models. After native `des verify`, independently invoke the installed reviewer
and fresh source-blind examiner on prepared evidence, then record their actual
host results and provenance. EXAMINE is not inside verify and cannot be skipped.
Public results remain `Success`, `Refusal`, `Retry`, and `Indeterminate`.
