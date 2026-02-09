# NW-START: Initialize nWave Workflow

**Wave**: CROSS_WAVE (project initialization)
**Agent**: Riley (nw-product-owner)

## Overview

Initialize nWave methodology with project brief creation, stakeholder alignment, and workspace preparation. Establishes project foundation before entering the wave sequence: DISCOVER > DISCUSS > DESIGN > DEVOP > DISTILL > DELIVER.

## Agent Invocation

@nw-product-owner

Execute \*gather-requirements for project initialization.

**Configuration:**

- template: greenfield | brownfield
- scope: small | medium | large
- output_directory: docs/

## Success Criteria

- [ ] Project brief created and validated
- [ ] Stakeholders identified and roles defined
- [ ] Success criteria established
- [ ] Workspace structure prepared
- [ ] Ready to proceed to DISCOVER wave

## Next Wave

**Handoff To**: DISCOVER wave (evidence-based product discovery)
**Deliverables**: Project brief and workspace foundation

## Examples

### Example 1: Greenfield project initialization
```
/nw:start invoice-automation --template=greenfield --scope=medium
```
Riley creates project brief, identifies stakeholders, establishes success criteria, and prepares the workspace for DISCOVER wave.

## Expected Outputs

```
docs/
  project-brief.md
  stakeholders.yaml
  architecture/constraints.md
```
