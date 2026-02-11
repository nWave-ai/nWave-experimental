> **Note**: The build pipeline (BUILD:INJECT, dist/ide) referenced in this document was eliminated in the build-pipeline-elimination feature. This document is preserved for historical reference only.

# Agent Compression: software-crafter

## Stato: Iterazione 1 completata - defect rilevato nel test A/B

---

## Obiettivo
Ridurre il token footprint al 10% preservando TUTTA la conoscenza metodologica.
Build pipeline invariato (BUILD:INJECT attivo) → risultato riproducibile ad ogni build.

## Principio guida
La conoscenza è il differenziatore. Comprimere il FORMATO, non il CONTENUTO:
1. **Deduplicazione**: ogni topic 1 volta (oggi 2-4 volte tra source YAML, embed, template, checklist)
2. **Strip overhead ricerca**: ~60% degli embed è formato ricerca senza valore esecutivo
3. **Formato denso**: prose verbose → regole strutturate per comprensione agente

---

## Build pipeline (NON modificare)

```
source: nWave/agents/software-crafter.md
  |
  +--> extract_yaml_block() → YAML config
  +--> process_embed_injections() → sostituisce BUILD:INJECT con contenuto file embed
  +--> process_dependencies() → appende template, checklist, data dal YAML config
  +--> generate_frontmatter() → crea YAML front matter
  +--> rebuild_yaml_block() → appende YAML ricostruito
  |
  v
dist: dist/ide/agents/nw/software-crafter.md
```

Build command: `cd tools && python3 -m core.build_ide_bundle`

Token count: `python3 -c "import tiktoken; e=tiktoken.encoding_for_model('gpt-4'); print(len(e.encode(open('dist/ide/agents/nw/software-crafter.md').read())))"`

---

## Mappa ridondanza originale (499KB dist → 76,260 token)

| Fonte iniezione | Bytes nel dist | Content |
|---|---|---|
| BUILD:INJECT embed (7 file) | ~170K | Knowledge files con overhead ricerca |
| dependencies.templates (2 file) | ~56K | TDD template + methodology (DUPLICA embeds) |
| dependencies.checklists (4 file) | ~52K | Checklist (DUPLICA embeds + source quality gates) |
| dependencies.data (3 file) | ~50K | Reference docs (DUPLICA embeds) |
| Source YAML PART 1-3 | ~50K | TDD + Mikado + Refactoring (DUPLICA embeds) |
| Source YAML PART 4-7 | ~20K | Quality + Workflow + OpenSource + Collaboration |
| Source Production Frameworks | ~35K | Meta-framework non eseguibili |
| Source config/persona/commands | ~15K | Core agent identity |
| Generated frontmatter + YAML rebuild | ~5K | Auto-generated |

---

## Strategia file-by-file

### A. File embed COMPRESSI in place (4 file + 1 merge)

| File | Prima | Dopo | Tecnica |
|---|---|---|---|
| `outside-in-tdd-methodology.md` | 31,734 | ~3,200 | Strip research overhead, formato denso |
| `mikado-method-progressive-refactoring.md` | 32,202 | ~3,300 | Idem |
| `refactoring-patterns-catalog.md` | 34,185 | ~4,800 | Idem + MERGE con test-refactoring-guide |
| `property-based-mutation-testing.md` | 30,737 | ~3,000 | Idem |
| `test-refactoring-guide.md` | 11,559 | ~3,700 | Riscritta come quick reference con code examples |
| **Totale embed** | **140,417** | **~18,000** | **~7.8x compressione** |

### B. File embed RIMOSSI dal BUILD:INJECT

| File | Motivo |
|---|---|
| `README.md` | Indice ricerca, zero valore esecutivo |
| `critique-dimensions.md` | Appartiene al reviewer, non al crafter |

### C. Dependencies RIMOSSE dal source YAML

Tutte le templates, checklists, data rimosse (contenuto coperto dagli embed compressi).
File restano su disco per uso on-demand via comandi.

### D. Sezioni source RIMOSSE (duplicate con embeds)

PART 1-3, Production Frameworks 1-5, Anti-Patterns verbose, Build/Test Protocol.

### E. Sezioni source MANTENUTE (compresse)

Config, persona, 7-Phase TDD, commands (ridotti da 24 a 17), quality, workflow, collaboration, safety.

---

## Formato compressione embed

### DA (formato ricerca originale — ~60% overhead):
```markdown
# Research: Outside-In TDD Methodology
**Date**: 2025-10-09  **Researcher**: researcher (Nova)  **Confidence**: High
## Research Methodology
**Search Strategy**: Systematic search for authoritative sources...
## Findings
### Finding 1: Double Loop TDD Structure
**Evidence**: "Double loop TDD uses an outer loop..."
**Source**: [SammanCoaching](https://...) - Accessed 2025-10-09
**Confidence**: High
**Verification**: Cross-referenced with: [Emily Bache], [CeKrem]
**Analysis**: The double-loop pattern provides two distinct rhythms...
---
## Source Analysis  ## Knowledge Gaps  ## Citations  ## Research Metadata
```

### A (formato denso per agente — solo conoscenza esecutiva):
```markdown
# Outside-In TDD Knowledge

## Double-Loop TDD
outer=ATDD(business behavior, hours-days to green)
inner=UTDD(implementation, minutes to green, RED->GREEN->REFACTOR)
Outer stays red while inner cycles. Outer drives WHAT, inner drives HOW.
Never build components not needed by actual user scenarios.
```

---

## Risultati Iterazione 1

### Metriche compressione

| Metrica | Heavy | Light | Delta |
|---|---|---|---|
| Token prompt | 76,260 | 7,615 | **-90.0%** |
| Bytes dist | 373,750 | 33,633 | **-91.0%** |
| Context liberato | — | 68,645 token | **+55% spazio lavoro** |

### Test A/B: Step 01-03 "Add audit logging to SubagentStop hook"

| Metrica | Heavy (76K tok) | Light (7.6K tok) |
|---|---|---|
| AC compliance | **7/7 ✅** | **6/7 ⚠️** |
| LOC impl (real_hook.py) | +78 righe | +18 righe |
| Unit tests | 6 test (220 righe) | 5 test (153 righe) |
| Token esecuzione | ~180K | ~200K (+11%) |
| Tempo esecuzione | ~70 min | ~72 min (+2%) |

### Defect trovato: TimeProvider

**AC violato:** "All timestamps produced by TimeProvider.now_utc()"

- **Heavy**: ✅ `SystemTimeProvider().now_utc().isoformat()` — esplicito
- **Light**: ❌ `log_audit_event()` → internamente usa `datetime.now()` — NON usa TimeProvider

**Root cause analysis:**
1. Light ha scelto `log_audit_event()` helper (codice più pulito, DRY)
2. NON ha verificato che l'helper rispetti l'AC (assumption non validata)
3. NON ha scritto il test `test_uses_time_provider_for_timestamp` (copertura mancante)
4. Senza quel test, il defect è sfuggito

### Cosa ha funzionato (95% preservato)
- ✅ Outside-In TDD methodology (7 fasi)
- ✅ Test-first discipline (RED → GREEN → REFACTOR)
- ✅ Port-boundary test doubles (mock solo ai confini)
- ✅ Minimal implementation (YAGNI)
- ✅ Code quality e leggibilità

### Cosa NON ha funzionato (5% perso)
- ❌ Attenzione ai requisiti espliciti di dependency injection
- ❌ Test coverage per TimeProvider usage pattern
- ❌ Validazione assunzioni su infrastruttura esistente

---

## Lessons Learned per Iterazione 2

### L1: Regole esplicite > conoscenza implicita
Il crafter light ha la conoscenza su TimeProvider ma NON ha la regola esplicita
"verifica OGNI AC punto per punto prima di considerare il task completo".
**Fix**: Aggiungere sezione `ac_verification_protocol` nel source YAML.

### L2: Test coverage come guardrail
Heavy aveva 6 test (incluso TimeProvider), Light 5 (senza).
La compressione ha rimosso la ridondanza che fungeva da safety net.
**Fix**: Aggiungere regola esplicita "scrivi 1 test per OGNI AC" nel 7-phase TDD.

### L3: Assumption validation
Light ha assunto che `log_audit_event()` fosse compliant senza verificare.
**Fix**: Aggiungere regola "verifica implementazione di helper riusati contro AC".

### L4: La velocità non migliora con meno token prompt
Token prompt (-90%) ≠ velocità (+2% più lento). Il beneficio reale è context budget.
**Fix**: Non promettere velocità, promuovere context budget come vantaggio.

### L5: Code examples nei test embed guidano il comportamento
Il file `test-refactoring-guide.md` (riscritta dall'utente con code examples)
potrebbe migliorare la qualità dei test scritti dall'agent.
**Fix**: Valutare se i code examples aumentano o riducono la compliance AC.

---

## Piano Iterazione 2

### Obiettivo
100% AC compliance mantenendo ~10% token footprint (~8-10K token).

### Modifiche pianificate al source YAML

1. **Aggiungere `ac_verification_protocol`:**
```yaml
ac_verification_protocol:
  rule: "Before marking any phase COMPLETE, verify EVERY AC literally"
  steps:
    - "Read each AC word by word"
    - "For each AC, identify the SPECIFIC technical requirement"
    - "Verify implementation satisfies the LITERAL requirement (not a paraphrase)"
    - "Write at least 1 test per AC"
  anti_pattern: "Assuming existing helpers/infrastructure satisfy AC without verification"
```

2. **Aggiungere regola in 7-Phase TDD fase RED_UNIT:**
```yaml
unit_test_rule: "Write minimum 1 unit test per acceptance criterion. If AC mentions a specific mechanism (e.g., TimeProvider), write a test that VERIFIES that mechanism is used."
```

3. **Rafforzare test_doubles_policy con regola verification:**
```yaml
infrastructure_assumption_rule: "When reusing existing helpers (log_audit_event, etc.), VERIFY their implementation matches AC requirements. Do NOT assume compliance."
```

### Token budget aggiornato
- Aggiunte stimate: ~300 token (3 regole)
- Nuovo totale: ~7,900 token (~10.4% di heavy)
- Ancora dentro target 10%

### Test A/B Iterazione 2
Stesso step 01-03, stesso worktree, stesse condizioni.
Success criteria: 7/7 AC ✅

---

## File di riferimento

| File | Ruolo |
|---|---|
| `nWave/agents/software-crafter.md` | Source compresso (versione attiva) |
| `nWave/agents/software-crafter-heavy.md` | Backup originale (fallback) |
| `nWave/data/embed/software-crafter/*.md` | 5 embed compressi |
| `dist/ide/agents/nw/software-crafter.md` | Dist generato (caricato da Claude Code) |
| `dist/ide/agents/nw/software-crafter-heavy.md` | Dist heavy (per confronto) |
| `/tmp/.../heavy-vs-light-comparison.md` | Report test A/B dettagliato (volatile) |

---

## Processo replicabile per altri agenti

1. Analisi token: `tiktoken` sul dist attuale
2. Mappa ridondanza: identificare duplicazioni tra embed/template/checklist/data/source
3. Comprimi embed: strip research overhead, formato denso
4. Rimuovi duplicati: dependencies che replicano embeds
5. Comprimi source: sezioni verbose → regole strutturate
6. Rebuild: `cd tools && python3 -m core.build_ide_bundle`
7. Misura token: target 10% dell'originale
8. Test A/B: stesso task, confronto quality
9. Itera: fix defect, ri-test

**Candidati prioritari:**
- `data-engineer`: 801,740 bytes → potenzialmente SUPERA context window
- `software-crafter-reviewer`: 117,653 bytes → secondo più grande
