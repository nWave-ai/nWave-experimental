---
name: roadmap-design
description: Roadmap concision rules, step decomposition efficiency, AC abstraction guidelines, and step-to-scenario mapping. Load when creating implementation roadmaps.
---

# Roadmap Design

## Canonical Format

Use ONLY compact nested format. See `nWave/templates/roadmap-schema.yaml` for fields/validation. Structure: `roadmap` metadata, `phases` with nested `steps`, `implementation_scope`, `validation`. Phase IDs: two digits (`"01"`). Step IDs: `"NN-MM"`.

## Concision Requirements

Token efficiency: crafter reads roadmap ~35 times (7 phases x 5 steps). 5000-token x 35 = 175k tokens. 1000-token x 35 = 35k (80% savings).

### Quantitative Limits
- Step description: max 50 words | AC per step: max 5 | Each AC: max 30 words
- Step notes: max 100 words
- Target: small (1-3 steps) = 500, medium (4-8) = 1500, large (9-15) = 3000 tokens

### Include
WHAT to build (one sentence) | WHY (brief business value) | Observable outcomes (testable AC) | Architectural constraints | Integration points

### Exclude
HOW to implement | code snippets/class names | algorithm descriptions | step-by-step instructions | tech tutorials | testing strategy (TDD standard) | motivational language | redundancy | examples when description clear

### Compression Techniques
Bullets over prose | eliminate qualifiers | assume expertise | active voice | omit obvious

## Acceptance Criteria Abstraction

AC describe observable outcomes, never internal implementation.

### Rules
Describe WHAT (behavior) not HOW (implementation) | Never reference private methods (underscore prefix) | Never reference internal class decomposition | Never prescribe signatures/params/return types | Crafter decides structure during GREEN + REFACTOR

### Good AC Examples
- "DES module importable from installation target after install"
- "DES utility scripts present and executable in scripts directory"
- "Installation uses backup before overwriting existing components"

### Bad AC Examples (implementation-coupled)
- "_install_des_module() copies src/des/ to ~/.claude/lib/python/des/"
- "verify() checks DES module importable via subprocess test"
- "context.installation_verifier._check_agents() called for verification"

## Step Decomposition Efficiency

### Step Ratio Check
Rule: `steps_count / estimated_production_files <= 2.5`
Violation = over-decomposition. Action: merge steps targeting same file.

### Identical Pattern Detection
Rule: if N steps differ only by substitution variable, batch into 1 step. Threshold: 3+ identical-pattern steps must batch.
Bad: 4 separate steps for AgentsPlugin, CommandsPlugin, TemplatesPlugin, UtilitiesPlugin
Good: 1 step creating all 4

### No-Op Prevention
Each step must add production code. Validation-only steps are not steps.
Bad: "Step 02-05: Validate extraction with integration tests"
Good: validation is part of preceding step's REVIEW phase

## Step-to-Scenario Mapping

For roadmaps feeding DELIVER wave:
1. Read acceptance tests (tests/acceptance/test_*.py) before creating roadmap
2. Count scenarios (def test_*) | 3. ~1 step per scenario (flexibility for infra steps)
4. Mark infra steps: "type: infrastructure" | 5. Principle: 1 Scenario = 1 Step = 1 TDD Cycle

## Measure Before Plan Gate

Before any roadmap, verify: 1. Timing data shows WHERE time spent | 2. Impact ranking shows MOST contributing component | 3. Target validation provides evidence

Missing data: halt, request measurement, offer to help. Gate is blocking.

## Simplest Solution Gate

Before multi-phase (>3 steps), document rejected alternatives:

### Alternatives to Consider
1. Configuration-only (no code) | 2. Single-file change | 3. Existing tool/library | 4. Partial (solve 80% simply)

### Documentation Format
```markdown
## Rejected Simple Alternatives

### Alternative 1: {simplest approach}
- What: {description}
- Expected Impact: {% of problem solved}
- Why Insufficient: {evidence-based reason}

### Why Complex Solution Necessary
1. Simple alternatives fail due to: {specific reason with evidence}
2. Complexity justified by: {benefit simple solutions cannot achieve}
```

Min 2 alternatives. Each: specific description, expected impact, evidence-based rejection.
