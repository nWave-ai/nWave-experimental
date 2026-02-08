# NW-RESEARCH: Evidence-Driven Knowledge Research

**Wave**: CROSS_WAVE
**Agent**: Nova (nw-researcher)
**Command**: `*research`

## Overview

Execute systematic evidence-based research with source verification. Cross-wave support providing research-backed insights for any nWave phase using trusted academic, official, and industry sources.

Optional `--embed-for={agent-name}` flag distills research into a practitioner-focused embed file for a specific agent.

## Context Files Required

- nWave/data/trusted-source-domains.yaml - Source reputation validation

## Agent Invocation

@nw-researcher

Execute \*research on {topic} [--embed-for={agent-name}].

**Context Files:**

- nWave/data/trusted-source-domains.yaml

**Configuration:**

- research_depth: detailed # overview/detailed/comprehensive/deep-dive
- source_preferences: ["academic", "official", "technical_docs"]
- output_directory: docs/research/
- embed_for: {agent-name} # Optional: distilled embed for specified agent
- embed_output_directory: nWave/data/embed/{agent-name}/

## Success Criteria

Refer to Nova's quality gates in nWave/agents/nw-researcher.md.

**Research:**

- [ ] All sources from trusted-source-domains.yaml
- [ ] Cross-reference performed (3+ sources per major claim)
- [ ] Research file created in docs/research/
- [ ] Citation coverage > 95%
- [ ] Average source reputation >= 0.80

**Distillation (if --embed-for specified):**

- [ ] Embed file created in nWave/data/embed/{agent-name}/
- [ ] 100% essential concepts preserved
- [ ] Self-contained with no external references
- [ ] Token budget respected (<5000 tokens per embed)

## Next Wave

**Handoff To**: Invoking workflow
**Deliverables**: Research document + optional embed file

## Examples

### Example 1: Standalone research
```
/nw:research "event sourcing patterns" --research_depth=detailed
```
Nova researches event sourcing from trusted sources, cross-references 3+ sources per claim, produces a comprehensive research document.

### Example 2: Research with agent embed
```
/nw:research "mutation testing methodologies" --embed-for=software-crafter
```
Nova researches mutation testing, then distills findings into a practitioner-focused embed file at nWave/data/embed/software-crafter/.

## Expected Outputs

```
data/research/{category}/{topic}-comprehensive-research.md
nWave/data/embed/{agent}/{topic}-methodology.md    (if --embed-for)
```
