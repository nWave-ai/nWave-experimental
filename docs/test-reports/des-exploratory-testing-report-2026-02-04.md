> **Note**: The build pipeline (dist/ide) referenced in this document was eliminated in the build-pipeline-elimination feature. This document is preserved for historical reference only.

# DES Exploratory Testing Report

**Data:** 2026-02-04
**Tester:** Lyra (AI Test Assistant)
**Durata:** 2.5 ore
**Status:** ⚠️ CRITICAL ISSUES FOUND

---

## Executive Summary

È stata condotta una sessione di test esplorativo completa sul DES (Deterministic Execution System) appena installato. I test hanno coperto:
- Installazione e configurazione degli hook
- Comportamento del PreToolUse hook
- Comportamento del SubagentStop hook
- Conformità a requisiti CLAUDE.md per max_turns
- Validazione gates e error handling

### 🚨 CRITICAL FINDINGS

1. **ZERO compliance con requisito max_turns** - TUTTE le 90 invocazioni Task mancano del parametro obbligatorio
2. **PreToolUse hook blocca Task non-DES** - dovrebbe fare passthrough invece
3. **Documentazione TDD_14_PHASES vs TDD_7_PHASES** - inconsistenza nei documenti

### ✅ SUCCESSI

1. Hook correttamente installati e configurati
2. Moduli DES importabili e funzionanti
3. Validazione prompt funziona correttamente
4. Messaggi errore dettagliati e utili
5. Exit codes corretti (0/1/2)

---

## Test Results Summary

| Test ID | Nome Test | Status | Severity | Note |
|---------|-----------|--------|----------|------|
| TC-001 | Hook Configuration | ✅ PASS | - | Settings corretti |
| TC-002 | Module Importability | ✅ PASS | - | Import funzionanti |
| TC-010 | max_turns Compliance | ❌ FAIL | 🔴 CRITICAL | 0% compliance (0/90) |
| TC-011 | max_turns Values | ⏭️ SKIP | - | Nessun valore da validare |
| TC-003 | Hook Activation (WITH marker) | ✅ PASS | - | Validazione eseguita |
| TC-003b | Hook Activation (WITHOUT marker) | ❌ FAIL | 🟡 HIGH | Blocca invece di passthrough |
| TC-004 | Missing Sections Validation | ✅ PASS | - | Rilevazione corretta |

**Summary:**
- ✅ PASS: 4 test
- ❌ FAIL: 2 test
- ⏭️ SKIP: 1 test
- Total: 7 test eseguiti su 16 pianificati

---

## Detailed Test Results

### ✅ TC-001: Hook Configuration - PASS

**Obiettivo:** Verificare installazione hook in settings.local.json

**Verifica:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Task",
      "command": "PYTHONPATH=/home/alexd/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-task"
    }],
    "SubagentStop": [{
      "command": "PYTHONPATH=/home/alexd/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop"
    }]
  }
}
```

**Risultato:**
- ✅ File ~/.claude/settings.local.json esiste
- ✅ Sezione hooks presente
- ✅ PreToolUse hook configurato con matcher "Task"
- ✅ SubagentStop hook configurato
- ✅ PYTHONPATH corretto
- ✅ Comando punta a modulo DES corretto

**Conclusione:** Hook correttamente installati dal processo di installazione.

---

### ✅ TC-002: Module Importability - PASS

**Obiettivo:** Verificare che moduli Python DES siano importabili

**Test eseguito:**
```bash
PYTHONPATH=~/.claude/lib/python python3 -c "
from des.adapters.drivers.hooks.claude_code_hook_adapter import main
print('✅ Module imported successfully')
print(f'✅ main function exists: {callable(main)}')
"
```

**Output:**
```
✅ Module imported successfully
✅ main function exists: True
```

**Risultato:**
- ✅ Modulo des.adapters.drivers.hooks.claude_code_hook_adapter importabile
- ✅ Funzione main() esiste e callable
- ✅ Nessun errore di import
- ✅ PYTHONPATH funziona correttamente

**Conclusione:** Moduli DES correttamente installati e accessibili.

---

### ❌ TC-010: max_turns Compliance - **CRITICAL FAIL**

**Obiettivo:** Verificare che TUTTE le chiamate Task abbiano parametro max_turns esplicito

**Requisito da CLAUDE.md:**
> **CRITICAL**: Always include `max_turns` when invoking the Task tool.

**Scan risultati:**
```
📊 SCAN RESULTS:
Total Task calls found: 90
Calls WITH max_turns: 0
Calls WITHOUT max_turns: 90

❌ Compliance: 0/90 (0%)
```

**Files interessati (sample):**
- dist/ide/commands/nw/develop.md (11 occorrenze)
- dist/ide/commands/nw/execute.md (4 occorrenze)
- dist/ide/commands/nw/finalize.md (7 occorrenze)
- dist/ide/commands/nw/review.md (7 occorrenze)
- dist/ide/commands/nw/roadmap.md (6 occorrenze)
- nWave/tasks/archive/split.md (7 occorrenze)

**Esempio chiamata senza max_turns:**
```python
Task(
    subagent_type="researcher",
    prompt=f'/nw:baseline "{feature_description}"',
    # ❌ MANCANTE: max_turns
)
```

**Esempio chiamata corretta (da CLAUDE.md):**
```python
Task(
    subagent_type="researcher",
    prompt=f'/nw:baseline "{feature_description}"',
    max_turns=35  # ✅ PRESENTE
)
```

**Impatto:**
- 🔴 **CRITICAL**: Violia requisito CLAUDE.md
- 🔴 Agenti potrebbero consumare token eccessivi
- 🔴 Nessun controllo su durata esecuzione
- 🔴 Rischio runaway agents

**Raccomandazione:**
**URGENTE** - Aggiungere max_turns a tutte le 90 chiamate Task con valori appropriati:
- Quick edit → 15
- Background task → 25
- Standard task → 30
- Research → 35
- Complex refactoring → 50

---

### ✅ TC-003: PreToolUse Hook Activation (WITH marker) - PASS

**Obiettivo:** Verificare che hook si attivi per Task CON marker DES

**Test input:**
```json
{
  "tool_input": {
    "prompt": "<!-- DES-VALIDATION: required -->\n<!-- DES-ORIGIN: test -->\n\nFind all Python files",
    "subagent_type": "Explore"
  }
}
```

**Output:**
```json
{
  "decision": "block",
  "reason": "MISSING: Mandatory section 'DES_METADATA' not found; MISSING: Mandatory section 'AGENT_IDENTITY' not found; MISSING: Mandatory section 'TASK_CONTEXT' not found; MISSING: Mandatory section 'TDD_7_PHASES' not found; MISSING: Mandatory section 'QUALITY_GATES' not found; MISSING: Mandatory section 'OUTCOME_RECORDING' not found; MISSING: Mandatory section 'BOUNDARY_RULES' not found; MISSING: Mandatory section 'TIMEOUT_INSTRUCTION' not found; INCOMPLETE: TDD phase 'PREPARE' not mentioned..."
}
```

**Exit code:** 2 (block)

**Risultato:**
- ✅ Hook rileva marker `<!-- DES-VALIDATION: required -->`
- ✅ Hook esegue validazione completa del prompt
- ✅ Hook rileva TUTTE le sezioni mancanti (8 sezioni + 14 fasi)
- ✅ Hook blocca esecuzione con exit code 2
- ✅ Messaggio errore dettagliato e specifico
- ✅ Comportamento fail-safe corretto

**Conclusione:** Validazione funziona perfettamente quando marker DES presente.

---

### ❌ TC-003b: PreToolUse Hook Activation (WITHOUT marker) - **FAIL**

**Obiettivo:** Verificare che hook faccia passthrough per Task SENZA marker DES

**Test input:**
```json
{
  "tool_input": {
    "prompt": "Find all Python files in the project",
    "subagent_type": "Explore"
  }
}
```

**Output:**
```json
{
  "decision": "block",
  "reason": "INVALID_MARKER: DES-VALIDATION marker not found; MISSING: Mandatory section 'DES_METADATA' not found; MISSING: Mandatory section 'AGENT_IDENTITY' not found..."
}
```

**Exit code:** 2 (block)

**Risultato:**
- ❌ **BUG**: Hook blocca anche Task SENZA marker DES
- ❌ Exit code 2 (block) invece di 0 (allow)
- ❌ Comportamento atteso: dovrebbe fare passthrough

**Comportamento atteso (da design doc):**
> Not all Task tool invocations should require validation. We need to distinguish:
> - Command-origin tasks → REQUIRES validation
> - Ad-hoc exploration → NO validation needed

**Impatto:**
- 🟡 **HIGH**: TUTTE le Task verranno bloccate, anche quelle non-DES
- 🟡 Impedisce uso normale di Task tool per ricerca/esplorazione
- 🟡 User experience degradata

**Root Cause:**
Il hook non distingue tra:
1. Task CON marker DES → validare e bloccare se invalido
2. Task SENZA marker DES → permettere passthrough

**Raccomandazione:**
Modificare logica hook:
```python
if "<!-- DES-VALIDATION: required -->" not in prompt:
    # No DES marker = passthrough (allow)
    return {"decision": "allow", "reason": "Not a DES-managed task"}
else:
    # DES marker present = validate
    validation_result = orchestrator.validate_prompt(prompt)
    ...
```

---

### ✅ TC-004: Missing Sections Validation - PASS

**Obiettivo:** Verificare rilevamento sezioni mancanti

**Test:** Usato stesso test di TC-003

**Sezioni rilevate come mancanti:**
1. ✅ DES_METADATA
2. ✅ AGENT_IDENTITY
3. ✅ TASK_CONTEXT
4. ✅ TDD_7_PHASES (nota: doc dice TDD_14_PHASES)
5. ✅ QUALITY_GATES
6. ✅ OUTCOME_RECORDING
7. ✅ BOUNDARY_RULES
8. ✅ TIMEOUT_INSTRUCTION

**Fasi TDD rilevate come mancanti (tutte 14):**
PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN_UNIT, CHECK_ACCEPTANCE, GREEN_ACCEPTANCE, REVIEW, REFACTOR_L1, REFACTOR_L2, REFACTOR_L3, REFACTOR_L4, POST_REFACTOR_REVIEW, FINAL_VALIDATE, COMMIT

**Risultato:**
- ✅ Validatore rileva tutte le sezioni obbligatorie
- ✅ Validatore rileva tutte le 14 fasi TDD
- ✅ Messaggi errore specifici e actionable
- ✅ Nessuna falsa positiva

**Nota:** Discrepanza nome sezione:
- Hook cerca `TDD_7_PHASES`
- Design doc specifica `TDD_14_PHASES`

**Conclusione:** Validazione sezioni funziona correttamente, con minor inconsistenza naming.

---

## Issues Found

### 🔴 ISSUE #1: Zero max_turns Compliance (CRITICAL)

**Severity:** CRITICAL
**Component:** All nWave commands
**Description:** TUTTE le 90 invocazioni Task mancano del parametro max_turns obbligatorio

**Evidence:**
- 90 chiamate Task trovate
- 0 chiamate con max_turns (0% compliance)
- Violazione esplicita di CLAUDE.md requirement

**Impact:**
- Agenti possono eseguire indefinitamente
- Consumo token non controllato
- Rischio runaway agents
- Violazione best practices

**Recommendation:**
1. **IMMEDIATE**: Aggiungere max_turns a tutte le chiamate Task
2. Usare valori appropriati per tipo task (15-50)
3. Aggiungere pre-commit hook per enforcement
4. Documentare standard in contributing guide

**Files to Fix:**
- dist/ide/commands/nw/develop.md (11 fixes)
- dist/ide/commands/nw/execute.md (4 fixes)
- dist/ide/commands/nw/finalize.md (7 fixes)
- dist/ide/commands/nw/review.md (7 fixes)
- dist/ide/commands/nw/roadmap.md (6 fixes)
- nWave/tasks/archive/split.md (7 fixes)
- +48 altre occorrenze

**Priority:** P0 - Must fix before production use

---

### 🟡 ISSUE #2: PreToolUse Hook Blocks Non-DES Tasks (HIGH)

**Severity:** HIGH
**Component:** PreToolUse hook
**Description:** Hook blocca TUTTE le Task, anche quelle senza marker DES

**Evidence:**
- Test con prompt senza marker DES → exit code 2 (block)
- Comportamento atteso: exit code 0 (allow passthrough)
- Design doc specifica passthrough per non-DES tasks

**Impact:**
- Impossibile usare Task tool per esplorazione ad-hoc
- User experience degradata
- Rigidità eccessiva del sistema

**Recommendation:**
1. Modificare handle_pre_task() per check marker DES prima di validare
2. Se marker NON presente → return {"decision": "allow"}
3. Se marker presente → eseguire validazione completa
4. Aggiungere test per entrambi i casi

**Code Change Required:**
```python
def handle_pre_task() -> int:
    ...
    prompt = tool_input.get("prompt", "")

    # NEW: Check for DES marker
    if "<!-- DES-VALIDATION: required -->" not in prompt:
        # Not a DES task - allow passthrough
        response = {"decision": "allow", "reason": "Not a DES-managed task"}
        print(json.dumps(response))
        return 0

    # EXISTING: Validate DES-marked tasks
    orchestrator = create_orchestrator()
    validation_result = orchestrator.validate_prompt(prompt)
    ...
```

**Priority:** P1 - Fix in next sprint

---

### 🟢 ISSUE #3: TDD Phases Naming Inconsistency (LOW)

**Severity:** LOW
**Component:** Documentation/Validation
**Description:** Inconsistenza tra nome sezione nella validazione e nella documentazione

**Evidence:**
- Hook cerca sezione `TDD_7_PHASES`
- Design doc specifica `TDD_14_PHASES`
- Entrambi validano 14 fasi (PREPARE → COMMIT)

**Impact:**
- Confusion per sviluppatori
- Possibili errori in template creation

**Recommendation:**
1. Standardizzare su `TDD_14_PHASES` (più accurato)
2. Aggiornare codice validazione
3. Aggiornare tutti template
4. Aggiornare documentazione

**Priority:** P2 - Clean up when convenient

---

## Tests Not Executed

Per limiti di tempo, i seguenti test non sono stati eseguiti:

- **TC-005**: Step file path validation
- **TC-006**: SubagentStop hook activation
- **TC-007**: IN_PROGRESS phase detection
- **TC-008**: EXECUTED without outcome
- **TC-009**: SKIPPED validation
- **TC-012**: Gate 1 matrix test
- **TC-013**: Gate 2 matrix test
- **TC-014**: Invalid transcript handling
- **TC-015**: Invalid JSON handling
- **TC-016**: Audit trail logging

**Reason:** Issue #1 (max_turns compliance) richiede fix urgente prima di procedere con test di integrazione.

---

## Recommendations

### Immediate Actions (P0)

1. **Fix max_turns Compliance**
   - Aggiungere max_turns a tutte le 90 chiamate Task
   - Valori suggeriti:
     - baseline/roadmap: 35
     - execute: 50
     - review: 25
     - finalize: 30
   - Tempo stimato: 2-3 ore

2. **Fix PreToolUse Passthrough**
   - Modificare handle_pre_task() per permettere passthrough
   - Aggiungere test per entrambi i casi (con/senza marker)
   - Tempo stimato: 1 ora

### Short Term (P1)

3. **Complete Test Suite**
   - Eseguire TC-005 → TC-016
   - Verificare SubagentStop hook behavior
   - Testare audit logging
   - Tempo stimato: 4 ore

4. **Add Pre-Commit max_turns Enforcement**
   - Hook che verifica max_turns in Task calls
   - Blocca commit se mancante
   - Tempo stimato: 2 ore

### Medium Term (P2)

5. **Standardize TDD Phases Naming**
   - TDD_14_PHASES everywhere
   - Update all templates
   - Update documentation
   - Tempo stimato: 1 ora

6. **Create Automated Test Suite**
   - pytest suite per DES hooks
   - CI/CD integration
   - Coverage target: 80%
   - Tempo stimato: 8 ore

---

## Conclusion

Il sistema DES è **parzialmente funzionante** ma presenta **2 issue critici** che devono essere risolti prima dell'uso in produzione:

### ✅ Cosa Funziona
- Hook installation & configuration
- Module imports & dependencies
- Prompt validation logic
- Error messages & reporting
- Fail-safe behavior

### ❌ Cosa NON Funziona
- max_turns compliance (0%)
- PreToolUse passthrough per non-DES tasks

### ⚠️ Rischi
- **HIGH**: Senza max_turns, agenti possono consumare token eccessivi
- **MEDIUM**: Hook troppo restrittivo impedisce uso normale di Task tool

### 📊 Overall Status
**Status:** ⚠️ NOT PRODUCTION READY

**Blocker issues:** 2 (ISSUE #1, ISSUE #2)

**Next Steps:**
1. Fix ISSUE #1 (max_turns) - URGENT
2. Fix ISSUE #2 (passthrough) - HIGH
3. Complete test suite (TC-005 → TC-016)
4. Re-test after fixes
5. Production readiness review

---

**Report compiled by:** Lyra (AI Test Assistant)
**Date:** 2026-02-04
**Review status:** Ready for review
**Approvers:** TBD
