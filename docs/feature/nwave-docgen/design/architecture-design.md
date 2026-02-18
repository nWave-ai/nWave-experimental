# nwave-docgen Architecture Design

## Pipeline: scan → extract → enrich → render → write

### Stage 1: Scan
Discovers artifact files grouped by type from `nWave/` directory tree.
- Agents: `nWave/agents/*.md`
- Commands: `nWave/tasks/nw/*.md`
- Skills: `nWave/skills/**/*.md`
- Templates: `nWave/templates/*.yaml`

### Stage 2: Extract
Parses YAML front-matter from each file into typed dicts (`Agent`, `Command`, `Skill`, `Template`). Skills without front-matter have name/description inferred from H1 heading and first paragraph.

### Stage 3: Enrich
Validates cross-references:
- Agent→Skill: each skill ref in agent front-matter must exist (supports both `skill-name` and `agent-dir/skill-name` forms)
- Skill→Agent: each skill's parent directory must match an agent name

### Stage 4: Render
Generates Markdown pages using string formatting (no Jinja dependency).

### Stage 5: Write
Writes pages to `docs/generated/` or checks for staleness (`--check` mode).

## Output Structure

```
docs/generated/
  index.md                    # Master index with counts
  agents/index.md             # Table: name | description | skills | tools
  agents/{agent-name}.md      # Detail page with skill links
  commands/index.md           # Table: command | description | arguments
  skills/index.md             # Grouped by agent directory
  templates/index.md          # Table: name | type | description
```

## Error Handling

All errors are blocking — `DocgenError` raised for malformed YAML, missing fields, or broken cross-references.

## CLI

```bash
python scripts/docgen.py                    # Generate docs/generated/
python scripts/docgen.py --output-dir=path  # Custom output
python scripts/docgen.py --check            # CI: exit 1 if stale
```
