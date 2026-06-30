---
name: nw-ab-todoify-file
description: "PROCEDURE — convert an agent/skill/command file's prose workflow + prose success-criteria to numbered task lists. Trigger: a file with prose workflow or prose success-criteria sections."
user-invocable: false
---

# nw-ab-todoify-file (PROCEDURE)

**Kind**: PROCEDURE | **One job**: convert one file's prose sections to numbered task lists | **One trigger**: an agent/skill/command file has a prose workflow or prose success-criteria/validation section.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **READ** — Read the target file. Gate: file loaded, before-count recorded.
2. **CONVERT WORKFLOW** — Convert ALL workflow/instruction sections to numbered task lists (`N. **Name** — action. Gate: condition.`). Gate: no prose-paragraph workflow remains.
3. **CONVERT CRITERIA** — Convert ALL success-criteria / validation / verification sections to numbered or checkbox lists. Gate: no prose-paragraph criteria remain.
4. **WRITE BACK** — Write the converted file. Gate: file written.
5. **VERIFY** — Run validation items #14 (Workflow Format) and #15 (Success Criteria Format) from `nw-ab-validation-checklist`. Gate: both pass.
6. **REPORT** — before/after line counts. Gate: both numbers reported.

## Composition

- COMPOSES (KNOWLEDGE): `nw-ab-validation-checklist` (items #14 + #15 only).
- No domain knowledge skill — this is a mechanical conversion procedure.

## Success Criteria

- [ ] All workflow sections → numbered task lists
- [ ] All success-criteria sections → numbered/checkbox lists
- [ ] Items #14 + #15 pass; before/after line counts reported
