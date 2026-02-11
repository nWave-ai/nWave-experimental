# DES (Deterministic Execution System) - Piano di Test Esplorativo

**Data:** 2026-02-06
**Versione:** 2.1
**Tester:** Manual / AI-assisted
**Obiettivo:** Verificare funzionamento completo del DES dopo installazione
**Scenario e2e:** audit-log-refactor roadmap (docs/feature/audit-log-refactor/roadmap.yaml)

---

## 1. Obiettivi del Test

### 1.1 Obiettivi Primari
- Verificare che gli hook DES siano correttamente installati e funzionanti
- Validare che PreToolUse hook filtri correttamente le invocazioni Task
- Validare che SubagentStop hook esegua validazioni post-esecuzione
- Verificare conformità: tutte le Task devono avere max_turns esplicito (10-100)
- Testare casi di validazione positiva (dovrebbero passare)
- Testare casi di validazione negativa (dovrebbero fallire)

### 1.2 Aree di Test
1. **Hook Installation & Configuration**
2. **PreToolUse Hook Behavior**
3. **SubagentStop Hook Behavior**
4. **max_turns Compliance**
5. **Validation Gates**
6. **Error Handling & Recovery**
7. **Audit Trail**
8. **E2E: Roadmap Execution**

### 1.3 Architettura DES - Riferimento Rapido

**Schema TDD:** v3.0 - 7 fasi (single source of truth: `nWave/templates/step-tdd-cycle-schema.json`)

**7 Fasi TDD (ordine canonico):**
1. PREPARE
2. RED_ACCEPTANCE
3. RED_UNIT
4. GREEN (combina GREEN_UNIT + GREEN_ACCEPTANCE)
5. REVIEW (include POST_REFACTOR_REVIEW)
6. REFACTOR_CONTINUOUS (combina L1+L2+L3)
7. COMMIT (assorbe FINAL_VALIDATE)

**Protocollo Hook JSON (Claude Code stdin):**
```json
{
  "session_id": "...",
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "...",
    "max_turns": 30,
    "subagent_type": "software-crafter"
  },
  "tool_use_id": "..."
}
```

**Skip Prefixes (permettono commit):**
- `BLOCKED_BY_DEPENDENCY:` - dipendenza esterna mancante
- `NOT_APPLICABLE:` - fase non applicabile
- `APPROVED_SKIP:` - skip approvato da tech lead
- `CHECKPOINT_PENDING:` - commit intermedio

**Skip Prefixes (bloccano commit):**
- `DEFERRED:` - lavoro posticipato (blocca commit)

**Fasi terminali:** COMMIT (deve avere outcome PASS)

---

## 2. Test Suite: Hook Installation & Configuration

### TC-001: Verificare installazione hook in settings
**Obiettivo:** Confermare che gli hook siano configurati in `~/.claude/settings.json`

**Passi:**
1. Leggere `~/.claude/settings.json`
2. Verificare presenza sezione "hooks"
3. Verificare presenza hook "PreToolUse" con matcher "Task"
4. Verificare presenza hook "SubagentStop"

**Criteri di successo:**
- File `settings.json` esiste
- Sezione hooks presente
- PreToolUse hook configurato con matcher "Task"
- SubagentStop hook configurato
- Comandi Python puntano a moduli DES corretti

**Dati attesi:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "PYTHONPATH=/home/alexd/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "PYTHONPATH=/home/alexd/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop"
          }
        ]
      }
    ]
  }
}
```

---

### TC-002: Verificare moduli hook esistono e sono importabili
**Obiettivo:** Confermare che i moduli Python DES siano installati e importabili

**Passi:**
1. Verificare esistenza `~/.claude/lib/python/des/adapters/drivers/hooks/claude_code_hook_adapter.py`
2. Tentare import del modulo
3. Verificare presenza funzioni principali
4. Verificare che template schema sia accessibile

**Criteri di successo:**
- File `claude_code_hook_adapter.py` esiste nella posizione installata
- Modulo importabile senza errori
- Funzioni `handle_pre_tool_use()` e `handle_subagent_stop()` presenti
- Template schema `~/.claude/templates/step-tdd-cycle-schema.json` esiste e leggibile

**Comandi test:**
```bash
# Test import modulo
PYTHONPATH=~/.claude/lib/python python3 -c "from des.adapters.drivers.hooks.claude_code_hook_adapter import handle_pre_tool_use, handle_subagent_stop; print('OK')"

# Test schema accessibile
PYTHONPATH=~/.claude/lib/python python3 -c "from des.domain.tdd_schema import get_tdd_schema; s = get_tdd_schema(); print(f'Schema v{s.schema_version}: {len(s.tdd_phases)} phases: {s.tdd_phases}')"
```

**Output atteso:**
```
OK
Schema v3.0: 7 phases: ('PREPARE', 'RED_ACCEPTANCE', 'RED_UNIT', 'GREEN', 'REVIEW', 'REFACTOR_CONTINUOUS', 'COMMIT')
```

---

## 3. Test Suite: PreToolUse Hook Behavior

### TC-003: Hook attivazione con/senza marker DES
**Obiettivo:** Verificare che PreToolUse hook distingua task DES da task normali

**Scenario 1: Task SENZA marker DES (ad-hoc task - dovrebbe passare con solo max_turns check)**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"Find all Python files","max_turns":15,"subagent_type":"Explore"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Scenario 2: Task CON marker DES (dovrebbe richiedere validazione completa)**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"<!-- DES-VALIDATION: required -->\nFind files","max_turns":15,"subagent_type":"Explore"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Scenario 3: Task CON marker orchestrator (dovrebbe passare con validazione rilassata)**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"<!-- DES-VALIDATION: required -->\n<!-- DES-MODE: orchestrator -->\nOrchestrate step","max_turns":30,"subagent_type":"software-crafter"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Criteri di successo:**
- Scenario 1: `{"decision": "allow"}`, exit 0 (non-DES, max_turns OK)
- Scenario 2: `{"decision": "block"}`, exit 2 (DES ma sezioni mancanti)
- Scenario 3: `{"decision": "allow"}`, exit 0 (orchestrator mode, rilassato)

---

### TC-004: Validazione prompt DES con sezioni mancanti
**Obiettivo:** Verificare che hook blocchi Task con prompt DES incompleti

**8 Sezioni mandatorie:**
1. `# DES_METADATA`
2. `# AGENT_IDENTITY`
3. `# TASK_CONTEXT`
4. `# TDD_7_PHASES`
5. `# QUALITY_GATES`
6. `# OUTCOME_RECORDING`
7. `# BOUNDARY_RULES`
8. `# TIMEOUT_INSTRUCTION`

**Test: prompt con sezione mancante (TIMEOUT_INSTRUCTION)**
```bash
PROMPT='<!-- DES-VALIDATION: required -->
# DES_METADATA
step: test
# AGENT_IDENTITY
You are a test agent
# TASK_CONTEXT
Test task
# TDD_7_PHASES
PREPARE RED_ACCEPTANCE RED_UNIT GREEN REVIEW REFACTOR_CONTINUOUS COMMIT
# QUALITY_GATES
Tests pass
# OUTCOME_RECORDING
Log results
# BOUNDARY_RULES
Only touch test files'

echo "{\"tool_name\":\"Task\",\"tool_input\":{\"prompt\":\"$PROMPT\",\"max_turns\":30,\"subagent_type\":\"software-crafter\"}}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Criteri di successo:**
- Hook rileva sezione mancante (TIMEOUT_INSTRUCTION)
- Task bloccata con `{"decision": "block"}`
- Messaggio errore indica sezione mancante: `MISSING: Mandatory section 'TIMEOUT_INSTRUCTION' not found`

---

### TC-005: Validazione fasi TDD mancanti nel prompt
**Obiettivo:** Verificare che prompt DES contenga tutte e 7 le fasi

**Test: prompt con 6 fasi (manca REFACTOR_CONTINUOUS)**
```bash
# Prompt con tutte le sezioni ma manca una fase TDD
echo '{"tool_name":"Task","tool_input":{"prompt":"<!-- DES-VALIDATION: required -->\n# DES_METADATA\ntest\n# AGENT_IDENTITY\nagent\n# TASK_CONTEXT\ncontext\n# TDD_7_PHASES\nPREPARE RED_ACCEPTANCE RED_UNIT GREEN REVIEW COMMIT\n# QUALITY_GATES\ngates\n# OUTCOME_RECORDING\nrecord\n# BOUNDARY_RULES\nrules\n# TIMEOUT_INSTRUCTION\ntimeout","max_turns":30,"subagent_type":"software-crafter"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Criteri di successo:**
- Hook rileva fase mancante (REFACTOR_CONTINUOUS)
- Task bloccata
- Errore: `INCOMPLETE: TDD phase 'REFACTOR_CONTINUOUS' not mentioned`

---

## 4. Test Suite: SubagentStop Hook Behavior

### TC-006: SubagentStop con dati validi
**Obiettivo:** Verificare che SubagentStop accetti step completato correttamente

**Prerequisito:** Creare execution-log.yaml temporaneo con tutte le 7 fasi completate

```bash
# Creare execution log temporaneo
TMP_LOG=$(mktemp -d)/execution-log.yaml
cat > "$TMP_LOG" << 'EOF'
project_id: "test-project"
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-06T10:00:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|PASS|2026-02-06T10:05:00Z"
  - "01-01|RED_UNIT|EXECUTED|PASS|2026-02-06T10:10:00Z"
  - "01-01|GREEN|EXECUTED|PASS|2026-02-06T10:20:00Z"
  - "01-01|REVIEW|EXECUTED|PASS|2026-02-06T10:30:00Z"
  - "01-01|REFACTOR_CONTINUOUS|SKIPPED|CHECKPOINT_PENDING: Minimal change|2026-02-06T10:35:00Z"
  - "01-01|COMMIT|EXECUTED|PASS|2026-02-06T11:00:00Z"
EOF

echo "{\"executionLogPath\":\"$TMP_LOG\",\"projectId\":\"test-project\",\"stepId\":\"01-01\"}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop

echo "Exit code: $?"
rm -rf "$(dirname $TMP_LOG)"
```

**Criteri di successo:**
- `{"decision": "allow"}`, exit 0
- Audit log registra `HOOK_SUBAGENT_STOP_PASSED`

---

### TC-007: SubagentStop con fasi mancanti
**Obiettivo:** Verificare rilevamento fasi mancanti nell'execution log

```bash
TMP_LOG=$(mktemp -d)/execution-log.yaml
cat > "$TMP_LOG" << 'EOF'
project_id: "test-project"
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-06T10:00:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|PASS|2026-02-06T10:05:00Z"
  - "01-01|RED_UNIT|EXECUTED|PASS|2026-02-06T10:10:00Z"
  - "01-01|GREEN|EXECUTED|PASS|2026-02-06T10:20:00Z"
  - "01-01|COMMIT|EXECUTED|PASS|2026-02-06T11:00:00Z"
EOF

echo "{\"executionLogPath\":\"$TMP_LOG\",\"projectId\":\"test-project\",\"stepId\":\"01-01\"}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop

echo "Exit code: $?"
rm -rf "$(dirname $TMP_LOG)"
```

**Criteri di successo:**
- `{"decision": "block"}`, exit 2
- Errore indica fasi mancanti: REVIEW, REFACTOR_CONTINUOUS
- Recovery suggestions incluse nella risposta

---

### TC-008: SubagentStop con COMMIT FAIL (fase terminale)
**Obiettivo:** Verificare che fasi terminali richiedano outcome PASS

```bash
TMP_LOG=$(mktemp -d)/execution-log.yaml
cat > "$TMP_LOG" << 'EOF'
project_id: "test-project"
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-06T10:00:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|PASS|2026-02-06T10:05:00Z"
  - "01-01|RED_UNIT|EXECUTED|PASS|2026-02-06T10:10:00Z"
  - "01-01|GREEN|EXECUTED|PASS|2026-02-06T10:20:00Z"
  - "01-01|REVIEW|EXECUTED|PASS|2026-02-06T10:30:00Z"
  - "01-01|REFACTOR_CONTINUOUS|EXECUTED|PASS|2026-02-06T10:35:00Z"
  - "01-01|COMMIT|EXECUTED|FAIL|2026-02-06T11:00:00Z"
EOF

echo "{\"executionLogPath\":\"$TMP_LOG\",\"projectId\":\"test-project\",\"stepId\":\"01-01\"}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop

echo "Exit code: $?"
rm -rf "$(dirname $TMP_LOG)"
```

**Criteri di successo:**
- `{"decision": "block"}`, exit 2
- Errore indica COMMIT non puo' avere outcome FAIL (fase terminale)

---

### TC-009: SubagentStop con SKIPPED + prefisso bloccante
**Obiettivo:** Verificare che skip con `DEFERRED:` blocchi il commit

**Scenario 1: SKIPPED con prefisso valido (CHECKPOINT_PENDING)**
```bash
# ... execution log con:
- "01-01|REFACTOR_CONTINUOUS|SKIPPED|CHECKPOINT_PENDING: Will complete later|..."
```
**Atteso:** `{"decision": "allow"}` (CHECKPOINT_PENDING permette commit)

**Scenario 2: SKIPPED con prefisso bloccante (DEFERRED)**
```bash
# ... execution log con:
- "01-01|REFACTOR_CONTINUOUS|SKIPPED|DEFERRED: Will do later|..."
```
**Atteso:** `{"decision": "block"}` (DEFERRED blocca commit)

---

## 5. Test Suite: max_turns Compliance

### TC-010: PreToolUse blocca Task senza max_turns
**Obiettivo:** Verificare che max_turns sia obbligatorio

```bash
# Task senza max_turns
echo '{"tool_name":"Task","tool_input":{"prompt":"test","subagent_type":"Explore"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

**Criteri di successo:**
- `{"decision": "block", "reason": "MISSING_MAX_TURNS: ..."}`
- Exit code 2

---

### TC-011: Validazione range max_turns (10-100)
**Obiettivo:** Verificare che valori fuori range siano bloccati

**Test values:**

| Valore | Atteso |
|--------|--------|
| `null` (assente) | BLOCK - MISSING_MAX_TURNS |
| `5` | BLOCK - INVALID_MAX_TURNS (< 10) |
| `10` | ALLOW (minimo) |
| `30` | ALLOW (standard) |
| `100` | ALLOW (massimo) |
| `150` | BLOCK - INVALID_MAX_TURNS (> 100) |
| `"thirty"` | BLOCK - INVALID_MAX_TURNS (non intero) |

**Comando per testare valore specifico:**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"test","max_turns":5,"subagent_type":"Explore"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```

---

## 6. Test Suite: Validation Gates (Matrice Completa)

### TC-012: Gate 1 - Pre-Invocation Validation (PreToolUse)

| Test ID | max_turns | Marker DES | Sezioni | Fasi TDD | Mode | Atteso |
|---------|-----------|------------|---------|----------|------|--------|
| G1-01 | 30 | No | N/A | N/A | N/A | ALLOW (ad-hoc task) |
| G1-02 | None | No | N/A | N/A | N/A | BLOCK (MISSING_MAX_TURNS) |
| G1-03 | 30 | Yes | 8/8 | 7/7 | exec | ALLOW (DES validato) |
| G1-04 | 30 | Yes | 7/8 | 7/7 | exec | BLOCK (sezione mancante) |
| G1-05 | 30 | Yes | 8/8 | 6/7 | exec | BLOCK (fase mancante) |
| G1-06 | 30 | Yes | N/A | N/A | orch | ALLOW (orchestrator mode) |

---

### TC-013: Gate 2 - SubagentStop Validation

| Test ID | Execution Log | Project ID | 7 Fasi | Outcome | Skip Prefix | Atteso |
|---------|--------------|------------|--------|---------|-------------|--------|
| G2-01 | Valido | Match | 7/7 | Tutti PASS | N/A | ALLOW |
| G2-02 | Non trovato | N/A | N/A | N/A | N/A | BLOCK (file not found) |
| G2-03 | Valido | Mismatch | N/A | N/A | N/A | BLOCK (project mismatch) |
| G2-04 | Valido | Match | 5/7 | PASS | N/A | BLOCK (fasi mancanti) |
| G2-05 | Valido | Match | 7/7 | COMMIT=FAIL | N/A | BLOCK (terminale FAIL) |
| G2-06 | Valido | Match | 7/7 | PASS | DEFERRED: | BLOCK (prefix bloccante) |
| G2-07 | Valido | Match | 7/7 | PASS | CHECKPOINT_PENDING: | ALLOW |
| G2-08 | YAML invalido | N/A | N/A | N/A | N/A | BLOCK (corrupted) |

---

## 7. Test Suite: Error Handling & Recovery

### TC-014: Gestione stdin vuoto
**Obiettivo:** Verificare fail-closed con input mancante

```bash
echo '' | PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
echo "Exit code: $?"
```

**Criteri di successo:**
- `{"status": "error", "reason": "Missing stdin input"}`
- Exit code 1 (fail-closed)

---

### TC-015: Gestione JSON invalido
**Obiettivo:** Verificare parsing robusto

```bash
echo 'not valid json {{{' | PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
echo "Exit code: $?"
```

**Criteri di successo:**
- `{"status": "error", "reason": "Invalid JSON: ..."}`
- Exit code 1 (fail-closed)
- Hook non crasha

---

### TC-015b: SubagentStop con campi mancanti
**Obiettivo:** Verificare validazione campi obbligatori

```bash
# Manca stepId
echo '{"executionLogPath":"/tmp/log.yaml","projectId":"test"}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop
echo "Exit code: $?"
```

**Criteri di successo:**
- `{"status": "error", "reason": "Missing required fields: ..."}`
- Exit code 1

---

## 8. Test Suite: Audit Trail

### TC-016: Creazione audit logs
**Obiettivo:** Verificare che eventi siano loggati in formato JSONL

**Eventi da verificare:**

| Evento | Quando |
|--------|--------|
| `HOOK_PRE_TOOL_USE_ALLOWED` | Task permessa (con context: non_des_task / orchestrator_mode / des_validated) |
| `HOOK_PRE_TOOL_USE_BLOCKED` | Task bloccata (con reason: MISSING_MAX_TURNS / INVALID_MAX_TURNS / errori validazione) |
| `HOOK_SUBAGENT_STOP_PASSED` | Step completato correttamente (con step_id) |
| `HOOK_SUBAGENT_STOP_FAILED` | Step fallito validazione (con step_id, validation_errors) |
| `SCOPE_VIOLATION` | File fuori scope modificato (warning, non blocca) |

**Passi:**
1. Eseguire una sequenza di test (TC-003, TC-006)
2. Cercare file audit: `ls ~/.claude/des/logs/audit-*.log` o `.nwave/des/logs/audit-*.log`
3. Verificare formato JSONL

**Formato atteso (ogni riga):**
```json
{"event":"HOOK_PRE_TOOL_USE_ALLOWED","timestamp":"2026-02-06T...","context":"non_des_task"}
```

**Criteri di successo:**
- File `audit-YYYY-MM-DD.log` creato
- Ogni riga e' JSON valido
- Ogni evento ha campo `event` e `timestamp`
- Eventi corrispondono alle azioni eseguite

---

## 9. Test Suite: E2E con Roadmap audit-log-refactor

### TC-017: Esecuzione step reale con DES enforcement
**Obiettivo:** Verificare DES end-to-end usando un roadmap step reale

**Roadmap:** `docs/feature/audit-log-refactor/roadmap.yaml`
**Step da eseguire:** Phase 01, Step 01-02 (Update JsonlAuditLogWriter)

**Flow atteso:**
```
1. Utente invoca /nw:execute @software-crafter "steps/01-02.json"
2. nWave genera prompt con marker DES:
   <!-- DES-VALIDATION: required -->
   <!-- DES-PROJECT-ID: audit-log-refactor -->
   <!-- DES-STEP-ID: 01-02 -->
3. Claude Code intercetta con PreToolUse hook
4. Hook valida: max_turns presente, prompt DES completo
5. Hook permette: {"decision": "allow"}
6. Subagent esegue 7 fasi TDD
7. Al completamento, SubagentStop hook si attiva
8. Hook legge execution-log.yaml
9. Hook valida: tutte le 7 fasi presenti, COMMIT=PASS
10. Hook permette: {"decision": "allow"}
11. Step completato
```

**Criteri di successo:**
- PreToolUse permette l'invocazione (exit 0)
- Subagent esegue tutte le 7 fasi TDD
- Execution log aggiornato con tutti gli eventi
- SubagentStop valida e permette (exit 0)
- Audit trail registra entrambi gli eventi (ALLOWED + PASSED)
- Commit effettuato con messaggio descrittivo

**Verifiche post-esecuzione:**
```bash
# 1. Verificare execution log
cat docs/feature/audit-log-refactor/execution-log.yaml | grep "01-02"

# 2. Verificare audit trail
cat ~/.claude/des/logs/audit-$(date +%Y-%m-%d).log | grep -i "01-02"

# 3. Verificare commit git
git log --oneline -1
```

---

### TC-018: SubagentStop blocca step incompleto
**Obiettivo:** Verificare che DES blocchi un subagent che completa senza tutte le fasi

**Scenario:** Subagent termina dopo solo 4 fasi (manca REVIEW, REFACTOR_CONTINUOUS, COMMIT)

**Criteri di successo:**
- SubagentStop hook rileva fasi mancanti
- Hook blocca con `{"decision": "block"}`
- Messaggio di recovery spiega quali fasi mancano
- Claude riceve feedback e puo' correggere

---

## 10. Test Suite: Hook Activation in Claude Code (Live)

### TC-019: PreToolUse hook si attiva per Task ad-hoc
**Obiettivo:** Verificare che il PreToolUse hook si attivi per ogni Task invocata in Claude Code

**Passi:**
1. Invocare un Task semplice in Claude Code (es. Explore agent)
2. Controllare audit log per evento HOOK_PRE_TOOL_USE_ALLOWED

**Comando di verifica:**
```bash
# Prima del test: contare eventi
wc -l .nwave/des/logs/audit-$(date +%Y-%m-%d).log

# Eseguire un Task in Claude Code (ad-hoc, senza marker DES)
# ... Task(subagent_type="Explore", prompt="list files", max_turns=10)

# Dopo il test: verificare nuovo evento
tail -5 .nwave/des/logs/audit-$(date +%Y-%m-%d).log
```

**Criteri di successo:**
- Audit log contiene nuovo evento `HOOK_PRE_TOOL_USE_ALLOWED`
- Context = `non_des_task` (nessun marker DES nel prompt)
- Nessun blocco (Task esegue normalmente)

---

### TC-020: PreToolUse hook distingue 3 context di allow
**Obiettivo:** Verificare che il hook registri il context corretto per ogni tipo di Task

**3 Context possibili:**

| Context | Quando | Marker nel prompt |
|---------|--------|-------------------|
| `non_des_task` | Task senza marker DES | Nessuno |
| `orchestrator_mode` | Task con marker DES + orchestrator | `<!-- DES-VALIDATION: required -->` + `<!-- DES-MODE: orchestrator -->` |
| `des_validated` | Task con marker DES + prompt completo | `<!-- DES-VALIDATION: required -->` + tutte 8 sezioni + 7 fasi |

**Scenario 1: non_des_task**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"simple task","max_turns":15,"subagent_type":"Explore"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```
Atteso: `{"decision":"allow"}` + audit log context = `non_des_task`

**Scenario 2: orchestrator_mode**
```bash
echo '{"tool_name":"Task","tool_input":{"prompt":"<!-- DES-VALIDATION: required -->\n<!-- DES-MODE: orchestrator -->\nOrchestrate","max_turns":30,"subagent_type":"software-crafter"}}' | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task
```
Atteso: `{"decision":"allow"}` + audit log context = `orchestrator_mode`

**Scenario 3: des_validated** (richiede prompt completo con 8 sezioni + 7 fasi)

Atteso: `{"decision":"allow"}` + audit log context = `des_validated`

---

## 11. Test Suite: Reminder Marker DES per /nw:develop e /nw:execute

### TC-021: /nw:develop include marker DES nei prompt dei sub-agent
**Obiettivo:** Verificare che `/nw:develop` generi prompt con marker DES per tutti i sub-agent

**Contesto architetturale:**
`/nw:develop` e' l'orchestrator che delega a sub-agent via Task tool. Ogni Task DEVE includere:
```html
<!-- DES-VALIDATION: required -->
<!-- DES-MODE: orchestrator -->
<!-- DES-STEP-FILE: docs/feature/{project-id}/... -->
<!-- DES-ORIGIN: command:/nw:develop -->
```

**Passi:**
1. Leggere `~/.claude/commands/nw/develop.md`
2. Cercare tutti i pattern `Task(` nel file
3. Verificare che OGNI Task includa i marker DES nel prompt

**Comando verifica:**
```bash
# Contare Task invocations
grep -c "Task(" ~/.claude/commands/nw/develop.md

# Contare marker DES
grep -c "DES-VALIDATION: required" ~/.claude/commands/nw/develop.md

# I numeri devono corrispondere
```

**Criteri di successo:**
- OGNI invocazione Task nel template di `/nw:develop` contiene `<!-- DES-VALIDATION: required -->`
- OGNI invocazione Task contiene `<!-- DES-MODE: orchestrator -->`
- OGNI invocazione Task contiene `<!-- DES-ORIGIN: command:/nw:develop -->`
- Nessun Task senza marker DES

---

### TC-022: /nw:execute include marker DES nel prompt del sub-agent
**Obiettivo:** Verificare che `/nw:execute` generi prompt con marker DES completi

**Contesto architetturale:**
`/nw:execute` genera un prompt per il software-crafter con tutte le 8 sezioni mandatorie + 7 fasi TDD. Deve includere:
```html
<!-- DES-VALIDATION: required -->
<!-- DES-STEP-FILE: docs/feature/{project-id}/steps/{step-id}.json -->
<!-- DES-ORIGIN: command:/nw:execute -->
```

**Passi:**
1. Leggere `~/.claude/commands/nw/execute.md`
2. Verificare il template prompt Task
3. Verificare che contenga tutti i marker DES
4. Verificare che contenga tutte le 8 sezioni mandatorie

**8 Sezioni mandatorie da verificare nel template:**
```bash
grep -c "# DES_METADATA" ~/.claude/commands/nw/execute.md
grep -c "# AGENT_IDENTITY" ~/.claude/commands/nw/execute.md
grep -c "# TASK_CONTEXT" ~/.claude/commands/nw/execute.md
grep -c "# TDD_7_PHASES" ~/.claude/commands/nw/execute.md
grep -c "# QUALITY_GATES" ~/.claude/commands/nw/execute.md
grep -c "# OUTCOME_RECORDING" ~/.claude/commands/nw/execute.md
grep -c "# BOUNDARY_RULES" ~/.claude/commands/nw/execute.md
grep -c "# TIMEOUT_INSTRUCTION" ~/.claude/commands/nw/execute.md
```

**Criteri di successo:**
- Marker DES presenti nel template prompt
- Tutte le 8 sezioni mandatorie presenti
- 7 fasi TDD elencate nella sezione TDD_7_PHASES
- Il prompt generato passerebbe la validazione PreToolUse (contesto `des_validated`)

---

### TC-023: Task senza marker DES viene permessa ma loggata come non_des_task
**Obiettivo:** Verificare il comportamento "reminder" quando i marker DES mancano

**Contesto:**
Quando un utente invoca un Task manualmente (senza usare `/nw:develop` o `/nw:execute`), il prompt non contiene marker DES. Il PreToolUse hook DEVE:
- Permettere l'esecuzione (non bloccare)
- Loggare come `non_des_task` nell'audit trail
- Non effettuare validazione prompt (sezioni/fasi)

Questo e' un "reminder silenzioso": guardando l'audit trail si vedra' che il task non era DES-managed.

**Passi:**
1. Invocare un Task senza marker DES (come fatto nel test TC-019)
2. Verificare audit log: context = `non_des_task`
3. Confrontare con un task DES dove context = `des_validated` o `orchestrator_mode`

**Verifica audit trail:**
```bash
# Contare task non-DES vs DES
grep -c "non_des_task" .nwave/des/logs/audit-$(date +%Y-%m-%d).log
grep -c "orchestrator_mode" .nwave/des/logs/audit-$(date +%Y-%m-%d).log
grep -c "des_validated" .nwave/des/logs/audit-$(date +%Y-%m-%d).log
```

**Criteri di successo:**
- Task senza marker viene permessa (non bloccata)
- Audit log registra context = `non_des_task`
- L'audit trail permette di distinguere task DES da task ad-hoc

---

## 12. Test Suite: Context Injection quando execution-log non aggiornato

### TC-024: SubagentStop blocca quando execution-log non viene aggiornato
**Obiettivo:** Verificare che SubagentStop rilevi quando un sub-agent completa senza aggiornare l'execution-log

**Contesto architetturale:**
Ogni sub-agent DEVE appendere eventi a `execution-log.yaml` dopo ogni fase TDD. Se il sub-agent termina senza scrivere nell'execution-log (o scrivendo solo alcune fasi), il SubagentStop hook DEVE:
1. Rilevare le fasi mancanti (ABANDONED_PHASE o SILENT_COMPLETION)
2. Bloccare con `{"decision": "block"}`
3. Iniettare context di recovery nel messaggio di risposta

**Scenario: Sub-agent termina senza aggiornare execution-log (0 eventi)**
```bash
TMP_LOG=$(mktemp -d)/execution-log.yaml
cat > "$TMP_LOG" << 'EOF'
project_id: "test-project"
events: []
EOF

echo "{\"executionLogPath\":\"$TMP_LOG\",\"projectId\":\"test-project\",\"stepId\":\"01-01\"}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop

echo "Exit code: $?"
rm -rf "$(dirname $TMP_LOG)"
```

**Criteri di successo:**
- `{"decision": "block"}`, exit 2
- Errore tipo: SILENT_COMPLETION (nessun evento per lo step)
- Recovery suggestions incluse nella risposta

---

### TC-025: SubagentStop inietta context di recovery nella risposta
**Obiettivo:** Verificare che il messaggio di blocco contenga informazioni utili per il recovery

**Contesto architetturale:**
Quando SubagentStop blocca, la risposta JSON include `hookSpecificOutput` con:
- `hookEventName`: "SubagentStop"
- `additionalContext`: messaggio dettagliato con step, errore, e passi di recovery
- `systemMessage`: sommario dell'errore

Questo context viene iniettato nella conversazione Claude per guidare il recovery.

**Scenario: Step con fasi mancanti**
```bash
TMP_LOG=$(mktemp -d)/execution-log.yaml
cat > "$TMP_LOG" << 'EOF'
project_id: "test-project"
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-06T10:00:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|FAIL|2026-02-06T10:05:00Z"
EOF

echo "{\"executionLogPath\":\"$TMP_LOG\",\"projectId\":\"test-project\",\"stepId\":\"01-01\"}" | \
  PYTHONPATH=~/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop

echo "Exit code: $?"
rm -rf "$(dirname $TMP_LOG)"
```

**Campi da verificare nella risposta JSON:**
```json
{
  "decision": "block",
  "reason": "...",
  "hookSpecificOutput": {
    "hookEventName": "SubagentStop",
    "additionalContext": "STOP HOOK VALIDATION FAILED\n\nStep: test-project/01-01\n..."
  },
  "systemMessage": "Validation failed: ..."
}
```

**Criteri di successo:**
- Risposta contiene `hookSpecificOutput.additionalContext` con dettagli step
- Risposta contiene `hookSpecificOutput.hookEventName` = "SubagentStop"
- Risposta contiene `systemMessage` con sommario errore
- `additionalContext` include "RECOVERY REQUIRED" con passi concreti
- Le fasi mancanti sono elencate (RED_UNIT, GREEN, REVIEW, REFACTOR_CONTINUOUS, COMMIT)

---

### TC-026: Context injection end-to-end con /nw:execute
**Obiettivo:** Verificare il flusso completo di context injection in uno scenario reale

**Scenario:**
1. Eseguire uno step via `/nw:execute` con un sub-agent che NON aggiorna l'execution-log
2. SubagentStop blocca e inietta context di recovery
3. Claude riceve il context e puo' tentare il recovery

**Nota:** Questo test richiede un'esecuzione reale in Claude Code. Non puo' essere simulato via CLI perche' il flusso di context injection dipende da Claude Code che legge `hookSpecificOutput` e lo inietta nella conversazione.

**Verifica indiretta:**
```bash
# Dopo un tentativo fallito, controllare audit log
grep "HOOK_SUBAGENT_STOP_FAILED" .nwave/des/logs/audit-$(date +%Y-%m-%d).log | tail -1

# Verificare che il recovery context sia stato generato
# (il context appare nel response JSON del hook, non nell'audit log)
```

**Criteri di successo:**
- SubagentStop genera response con `hookSpecificOutput`
- Claude riceve il context e mostra messaggio di recovery
- L'utente vede chiaramente quale step e' fallito e perche'
- Le recovery suggestions sono actionable (passi concreti)

---

## 13. Execution Plan

### Fase 1: Verifiche Statiche (15 min)
1. TC-001: Hook configuration in settings.json
2. TC-002: Module importability + schema loading

### Fase 2: Test CLI PreToolUse (20 min)
3. TC-003: Hook activation (3 scenari)
4. TC-004: Missing sections
5. TC-005: Missing TDD phases
6. TC-010: max_turns obbligatorio
7. TC-011: max_turns range validation

### Fase 3: Test CLI SubagentStop (20 min)
8. TC-006: Valid completion
9. TC-007: Missing phases
10. TC-008: Terminal phase FAIL
11. TC-009: Skip prefixes

### Fase 4: Error Handling (10 min)
12. TC-014: Empty stdin
13. TC-015: Invalid JSON
14. TC-015b: Missing required fields

### Fase 5: Validation Gates (15 min)
15. TC-012: PreToolUse gate matrix
16. TC-013: SubagentStop gate matrix

### Fase 6: Audit Trail (10 min)
17. TC-016: Log creation and format

### Fase 7: E2E con Roadmap (30+ min)
18. TC-017: Esecuzione step reale (audit-log-refactor 01-02)
19. TC-018: Test blocco step incompleto

### Fase 8: Hook Activation Live (15 min)
20. TC-019: PreToolUse hook attivazione per task ad-hoc
21. TC-020: PreToolUse distingue 3 context di allow

### Fase 9: Marker DES per /nw:develop e /nw:execute (15 min)
22. TC-021: /nw:develop include marker DES
23. TC-022: /nw:execute include marker DES
24. TC-023: Task senza marker permessa ma loggata come non_des_task

### Fase 10: Context Injection execution-log (20 min)
25. TC-024: SubagentStop blocca quando execution-log non aggiornato
26. TC-025: SubagentStop inietta context di recovery nella risposta
27. TC-026: Context injection e2e con /nw:execute

**Tempo totale stimato:** ~3 ore

---

## 11. Report Template

### Per ogni test completato:

```markdown
## TC-XXX: [Nome Test]
**Status:** PASS / FAIL / WARNING
**Data esecuzione:** YYYY-MM-DD HH:MM
**Comando:** [comando eseguito]

### Risultato
[Output effettivo]

### Atteso vs Effettivo
- Atteso: [...]
- Effettivo: [...]
- Match: SI/NO

### Issues trovati
- [Issue 1]

### Note
[Osservazioni]
```

---

## 12. Exit Criteria

Il test e' considerato completato quando:
- Tutti i test TC-001 a TC-026 sono stati eseguiti
- Almeno 90% dei test critici PASS
- Tutti i FAIL sono documentati con root cause
- Test E2E (TC-017) completato con successo
- Hook activation verificata in Claude Code (TC-019, TC-020)
- Marker DES presenti in /nw:develop e /nw:execute (TC-021, TC-022)
- Context injection SubagentStop verificata (TC-024, TC-025)
- Audit trail verificato per tutti gli eventi

---

## 13. Known Issues / Limitations

1. **Pre-commit hook**: Runs ALL project tests (2600+) con molti fallimenti pre-esistenti nei test CLI installer. Usare `--no-verify` quando i fallimenti sono pre-esistenti.

2. **Bytecode cache**: Dopo reinstallazione DES, i file `.pyc` possono impedire l'uso del codice aggiornato. Pulire con: `find ~/.claude/lib/python/des -name "__pycache__" -type d -exec rm -rf {} +`

3. **Session reset**: Dopo reinstallazione hook, e' necessario `/exit` e restart della sessione Claude Code.

4. **WSL path resolution**: Su WSL, `~/.claude` e' symlink a `/mnt/c/Users/user/.claude`. Il codice DES normalizza i path con `.replace("\\", "/")` per compatibilita' cross-platform.

---

**Prepared by:** Claude (AI Assistant)
**Versione schema TDD:** 3.0 (7 fasi)
**Versione hook protocol:** tool_name/tool_input (top-level)
