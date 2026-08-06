---
name: nw-review
description: "Dispatches an expert reviewer for a baseline, feature delta, task, or implementation. Use before relying on an artifact's quality verdict."
user-invocable: true
argument-hint: '[agent] [artifact-type] [artifact-path] - Example: @<base-agent> feature-delta "docs/feature-delta.md"'
---

# NW-REVIEW: Expert Critique

**Wave**: CROSS_WAVE | **Agent**: Dynamic (`nw-*-reviewer`)

## Invocation Contract

```
/nw-review @{agent-name} {artifact-type} "{artifact-path}" [--dimensions=rpp] [--from=1] [--to=3]
```

- `{artifact-type}` is exactly one of: `baseline`, `feature-delta`, `task`, `implementation`.
- `{artifact-path}` resolves to an existing absolute path.
- `--dimensions=rpp` adds the RPP code-smell scan; `--from` / `--to` select its L1-L6 range.

## Review Standard

Every review applies Radical Candor: care personally, challenge directly, ground findings in evidence and consequence, and critique the work rather than its author. Include at least one genuine `praise:`; filler praise does not satisfy this contract.

Use Conventional Comments. Order findings: blocking issues, suggestions, then nitpicks and praise.

| Label | Meaning |
|---|---|
| `praise:` | Genuine strength; at least one required |
| `issue (blocking):` | Must change before proceeding |
| `issue (blocking, security):` | Security risk requiring direct action |
| `suggestion:` | Improvement, marked blocking or non-blocking |
| `nitpick (non-blocking):`, `question (non-blocking):`, `thought (non-blocking):` | Advisory feedback |

End with exactly one verdict:

| Verdict | Meaning |
|---|---|
| `APPROVED` | Zero blocking issues; non-blocking feedback is advisory |
| `NEEDS_REVISION` | Correctable blocking issues exist; enumerate each one |
| `REJECTED` | Fundamental or unsafe problems require substantial rework |

## Dispatch

1. **Validate** — Resolve the base agent, artifact type, and artifact path. Gate: a matching reviewer and existing artifact are available.
2. **Apply rigor** — Read `.nwave/des-config.json` `rigor`; default to standard settings. Skip when `review_enabled=false` or `reviewer_model=skip`; otherwise use `reviewer_model` or Haiku. Gate: review decision is explicit.
3. **Invoke** — Call `{agent-name}-reviewer` with the absolute artifact path, type, selected rigor, and requested RPP range. Gate: reviewer owns the critique.
4. **Report** — Return its Conventional Comments and verdict; the review owner records the result where that artifact's workflow defines. Gate: outcome is actionable.

## Reviewer Derivation

| User provides | Reviewer invoked |
|---|---|
| `@nw-software-crafter` | `nw-software-crafter-reviewer` |
| `@nw-solution-architect` | `nw-solution-architect-reviewer` |
| `@nw-platform-architect` | `nw-platform-architect-reviewer` |

## Examples

```
/nw-review @nw-solution-architect feature-delta "docs/feature/auth-upgrade/delta.md"
/nw-review @nw-software-crafter task "docs/feature/auth-upgrade/slice-01.md"
/nw-review @nw-platform-architect implementation "src/" --dimensions=rpp --from=1 --to=3
```
