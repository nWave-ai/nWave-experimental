# CONTEXT DRIFT ANALYSIS: Numerazione User Stories vs Implementazione

**Date**: 2026-01-25
**Severity**: CRITICAL
**Issue**: Grave confusione nella numerazione tra User Stories e Project Folders

---

## PROBLEMA IDENTIFICATO

### User Stories (Source of Truth: docs/feature/des/discuss/user-stories.md)

| ID | Title | Priority | Definizione |
|----|-------|----------|-------------|
| US-001 | Command-Origin Task Filtering | P0 | DES markers per distinguere command vs ad-hoc |
| US-002 | Pre-Invocation Template Validation | P0 | Validazione 8 sezioni + 14 fasi TDD |
| US-003 | Post-Execution State Validation | P0 | SubagentStop hook validation |
| **US-004** | **Audit Trail for Compliance Verification** | **P0** | **Append-only daily audit logs** |
| US-005 | Failure Recovery Guidance | P1 | Recovery suggestions |
| **US-006** | **Turn Discipline Without max_turns** | **P0** | **TIMEOUT_INSTRUCTION prompt** |
| US-007 | Boundary Rules for Scope Enforcement | P1 | BOUNDARY_RULES section |
| US-008 | Session-Scoped Stale Execution Detection | P1 | Pre-execution stale check |
| US-009 | Learning Feedback for TDD Phase Execution | P1 | Educational notes |

### Project Folders Implementati

| Folder | Goal Dichiarato | REALE US |
|--------|-----------------|----------|
| ~~des-us001~~ | ❓ | US-001 (FINALIZED) |
| ~~des-us002~~ | ❓ | US-002 (FINALIZED) |
| **des-us006** | **"Implement DES timeout and turn discipline..."** | **US-006!** |

---

## MAPPING CORRETTO

### ✅ IMPLEMENTATO (Evolution Documents Confermati)

| Evolution Doc | Contenuto | User Story Vera |
|---------------|-----------|-----------------|
| des-us001-evolution.md | Command-origin filtering | ✅ US-001 |
| des-us002-evolution.md | Template validation (8 sections + 14 phases) | ✅ US-002 |

### ❌ CONFUSIONE CRITICA

**Folder `des-us006`** sta implementando:
- ✅ Turn Counter (turn_count tracking)
- ✅ Timeout Monitor (elapsed time tracking)
- ✅ Timeout Warnings (threshold-based alerts)
- ❌ Extension API (RIMOSSA - out of scope)

**Questo è US-006: "Turn Discipline Without max_turns"**

**US-004 VERA ("Audit Trail") NON è implementata!**

---

## USER STORIES NON IMPLEMENTATE

| US | Title | Priority | Status |
|----|-------|----------|--------|
| US-003 | Post-Execution State Validation | P0 | ❌ NOT_STARTED |
| **US-004** | **Audit Trail for Compliance Verification** | **P0** | **❌ NOT_STARTED** |
| US-005 | Failure Recovery Guidance | P1 | ❌ NOT_STARTED |
| US-007 | Boundary Rules | P1 | ❌ NOT_STARTED |
| US-008 | Stale Execution Detection | P1 | ❌ NOT_STARTED |
| US-009 | Learning Feedback | P1 | ❌ NOT_STARTED |

---

## INFRASTRUCTURE US

**Presenti nelle user stories ma probabilmente non rilevanti per DES core:**

| US-INF | Title | Note |
|--------|-------|------|
| US-INF-001 | Database Schema Migration Without Tests | ⚠️ Sembra essere un esempio generico, non specifico per DES |
| US-INF-002 | Environment Variable Configuration | ⚠️ Esempio generico |
| US-INF-003 | Third-Party Service Provisioning | ⚠️ Esempio generico (Stripe, Auth0) |

**Ipotesi**: Queste US-INF sono esempi di "configuration_setup workflow" menzionato nella sezione Infrastructure, ma NON sono feature da implementare per DES.

---

## ACCEPTANCE CRITERIA ANALYSIS

### US-006: Turn Discipline (attualmente in des-us006)

**Richiesto nelle user stories:**
- AC-006.1: All DES-validated prompts include TIMEOUT_INSTRUCTION section
- AC-006.2: Turn budget (~50) specified in instructions
- AC-006.3: Progress checkpoints defined (turn ~10, ~25, ~40, ~50)
- AC-006.4: Early exit protocol documented in prompt
- AC-006.5: Prompt instructs agent to log turn count at phase transition

**Implementato in des-us006:**
- ✅ Turn Counter component
- ✅ Timeout Monitor component
- ✅ Timeout warnings in prompts
- ✅ Turn count tracking in phase_execution_log
- ❌ Extension API (rimossa - non richiesta)
- ❓ Progress checkpoints? (DA VERIFICARE)
- ❓ Early exit protocol? (DA VERIFICARE)
- ❓ TIMEOUT_INSTRUCTION section nel prompt? (DA VERIFICARE)

### US-004: Audit Trail (NON implementata)

**Richiesto:**
- AC-004.1: All state transitions logged with ISO timestamp
- AC-004.2: Audit log append-only
- AC-004.3: Event types: TASK_INVOCATION_*, PHASE_*, SUBAGENT_STOP_*, COMMIT_*
- AC-004.4: Each entry includes step file path and event data
- AC-004.5: Human-readable JSONL format
- AC-004.6: Daily rotation (audit-YYYY-MM-DD.log)

**Implementato:**
- ❌ Nessun audit log trovato
- ❌ Nessun file `audit-*.log` generato

---

## ROOT CAUSE

### Come è successo?

1. **Project Naming Inconsistency**
   - Qualcuno ha creato `des-us006` per implementare "timeout and turn discipline"
   - Ma questa è US-006 nella user story, non US-004
   - US-004 vera è "Audit Trail"

2. **Nessun Cross-Reference**
   - Roadmap.yaml NON riporta quale User Story sta implementando
   - Nessun campo `implements_user_story: "US-006"`
   - Impossible verificare la corrispondenza

3. **Automatic Step Generation**
   - Il solution-architect ha generato roadmap e step senza verificare il mapping
   - Ha espanso lo scope con Extension API non richiesta
   - Nessun gate di validazione "questa feature è richiesta?"

---

## RACCOMANDAZIONI

### Immediate (da fare ORA)

1. **Rinominare des-us006 → des-us006**
   ```bash
   mv docs/feature/des-us006 docs/feature/des-us006
   # Update tutti i riferimenti interni
   ```

2. **Aggiungere campo traceability**
   ```yaml
   # In ogni roadmap.yaml
   implements_user_story: "US-006"
   user_story_title: "Turn Discipline Without max_turns"
   acceptance_criteria_mapping:
     - roadmap_phase: "01-Turn Limit Infrastructure"
       maps_to: ["AC-006.5"]
     - roadmap_phase: "03-Timeout Warning System"
       maps_to: ["AC-006.1", "AC-006.2"]
   ```

3. **Creare progetti mancanti**
   - des-us003: Post-Execution State Validation
   - des-us006: Audit Trail for Compliance Verification
   - des-us005: Failure Recovery Guidance
   - des-us007: Boundary Rules
   - des-us008: Stale Execution Detection
   - des-us009: Learning Feedback

### Breve termine

4. **Gate di validazione roadmap**
   - Dopo roadmap generation, verificare campo `implements_user_story`
   - Bloccare approval se manca o se non corrisponde a una US definita

5. **Traceability matrix**
   - Ogni step deve avere `maps_to_ac: ["AC-006.1", "AC-006.2"]`
   - Sistema automatico che verifica coverage

### Lungo termine

6. **Naming convention forzata**
   - Project folder DEVE usare user story ID
   - Se US-006, folder DEVE essere `des-us006`
   - Validazione automatica nel create script

---

## DOMANDE PER IL PRODUCT OWNER

1. **US-INF-001, 002, 003**: Sono esempi generici o feature da implementare per DES?
   - Se sono esempi: rimuoverli dalle user stories
   - Se sono feature: creare progetti dedicati

2. **des-us006 attuale**: Rinominare in des-us006?
   - Completare US-006 con AC mancanti (checkpoints, early exit)
   - Poi creare vera US-004 (Audit Trail)

3. **Priority**: Quale implementare prima?
   - Sprint 1 (P0): US-001 ✅, US-002 ✅, US-006 ⏸️ (rinominare da us004)
   - Sprint 2 (P0): US-003 ❌, US-004 ❌

---

## CONCLUSION

Il "context drifting" identificato è:
1. **Numerazione errata**: des-us006 implementa US-006, non US-004
2. **US mancanti**: US-003, US-004 vera, US-005, US-007, US-008, US-009 NON implementate
3. **Scope creep**: Extension API aggiunta senza richiesta (già rimossa)
4. **US-INF ambigue**: Non chiaro se sono esempi o feature da implementare

**Azione richiesta**: Decisione del PO su come procedere con la rinumerazione e implementazione delle US realmente mancanti.
