# Quick Reference: Validation and Testing Infrastructure

**Quick Start Guide** for nWave production validation and testing

---

## Quick Commands

### 1. Run Compliance Validation
```bash
python3 scripts/validate-agent-compliance.py
```
**Output**: `docs/COMPLIANCE_VALIDATION_REPORT.md`
**Pass Criteria**: 12/12 agents with all 5 frameworks

### 2. Generate Adversarial Test Definitions
```bash
python3 scripts/run-adversarial-tests.py
```
**Output**:
- `docs/ADVERSARIAL_TEST_REPORT.md` (1716 lines)
- `docs/ADVERSARIAL_TEST_REPORT.json` (117 KB)

### 3. View Compliance Status
```bash
cat docs/COMPLIANCE_VALIDATION_REPORT.md
```

### 4. Check Next Steps
```bash
cat docs/NEXT_STEPS_WEEK2-3.md
```

---

## Current Status (2025-10-05)

### Compliance Validation Results
- **Total Agents**: 12
- **Pass Rate**: 0/12 (0.0%)
- **Reason**: Frameworks in template, not yet propagated to agents

### Framework Status

| Framework | In Template | In Agents | Status |
|-----------|-------------|-----------|--------|
| Contract | ✅ | 11/12 | 91.7% |
| Safety | ✅ | 0/12 | 0.0% |
| Testing | ✅ | 0/12 | 0.0% |
| Observability | ✅ | 0/12 | 0.0% |
| Error Recovery | ✅ | 0/12 | 0.0% |

### Adversarial Testing
- **Test Cases Defined**: 258
- **Agent Security Tests**: 16 per agent (universal)
- **Adversarial Output Tests**: 0-8 per agent (agent-type-specific)
- **Execution Status**: Pending (requires agent runtime environment)

---

## Files Created

### Scripts (Automation)
1. `scripts/validate-agent-compliance.py` (13 KB) - Automated compliance validation
2. `scripts/validate-agent-compliance.sh` (12 KB) - Bash backup version
3. `scripts/run-adversarial-tests.py` (29 KB) - Adversarial test suite

### Reports (Documentation)
1. `docs/COMPLIANCE_VALIDATION_REPORT.md` (4.2 KB) - Current compliance status
2. `docs/ADVERSARIAL_TEST_REPORT.md` (1716 lines) - Test definitions
3. `docs/ADVERSARIAL_TEST_REPORT.json` (117 KB) - Machine-readable test data
4. `docs/NEXT_STEPS_WEEK2-3.md` (16 KB) - Implementation roadmap
5. `docs/VALIDATION_IMPLEMENTATION_SUMMARY.md` (23 KB) - Complete summary

---

## Week 2 Immediate Actions

### Priority 1: Framework Propagation (HIGH)
**Goal**: Add missing frameworks to all 12 agent files

**Steps**:
1. Create `scripts/add-frameworks-to-agents.py` (automated propagation)
2. Test on 1 agent (business-analyst)
3. Validate: `python3 scripts/validate-agent-compliance.py`
4. Batch propagate to remaining 11 agents
5. Final validation: 12/12 pass

**Timeline**: 5-7 days
**Success Criteria**: 12/12 agents pass compliance validation

### Priority 2: Peer Reviewer Agents (MEDIUM)
**Goal**: Implement Layer 4 testing (adversarial verification via peer review)

**Steps**:
1. Create peer reviewer agents (business-analyst-reviewer, etc.)
2. Implement review workflow (production → review → revision → approval)
3. Test with 1-2 agent pairs
4. Document review process

**Timeline**: 7-10 days
**Dependencies**: Priority 1 complete

### Priority 3: Observability Infrastructure (MEDIUM)
**Goal**: Deploy structured logging, metrics, alerting

**Steps**:
1. Set up structured logging (JSON format)
2. Deploy metrics collection (Prometheus + Grafana)
3. Configure alerting (PagerDuty, Slack)

**Timeline**: 5-7 days
**Dependencies**: Priority 1 complete

---

## Key Metrics

### Validation Coverage
- Agents Validated: **12/12 (100%)**
- Frameworks per Agent: **7**
- Total Checks: **84**
- Current Pass Rate: **0.0%**
- Target Pass Rate: **100%**

### Adversarial Testing
- Total Test Cases: **258**
- Universal Security: **192 tests** (16 per agent)
- Agent-Specific Output: **66 tests** (0-8 per agent)
- Agent Types: **5** (document, code, research, tool, orchestrator)
- Test Categories: **10**

### Implementation Timeline
- **Week 2**: Framework propagation + peer reviewers
- **Week 3**: Observability + adversarial verification testing
- **Month 2**: Production pilot
- **Month 3**: Full production rollout

---

## Framework Descriptions

### 1. Contract Framework
**Purpose**: Define explicit input/output contract
**Required**: `inputs`, `outputs`, `side_effects`, `error_handling`

### 2. Safety Framework
**Purpose**: Multi-layer security and safety validation
**Required**: 4 validation layers + 7 enterprise security layers

### 3. Testing Framework
**Purpose**: Comprehensive testing from unit to adversarial
**Required**: All 5 layers (Unit, Integration, Adversarial Output, Adversarial Verification)

### 4. Observability Framework
**Purpose**: Production monitoring and debugging
**Required**: `structured_logging`, `metrics`, `alerting`

### 5. Error Recovery Framework
**Purpose**: Graceful error handling and resilience
**Required**: `retry_strategies`, `circuit_breakers`, `degraded_mode`

---

## Troubleshooting

### Compliance Validation Fails
```bash
# Check which frameworks are missing
python3 scripts/validate-agent-compliance.py

# View detailed report
cat docs/COMPLIANCE_VALIDATION_REPORT.md

# Fix: Add missing frameworks to agent files
```

### Adversarial Test Generation Fails
```bash
# Check Python version (requires 3.x)
python3 --version

# Re-run test generation
python3 scripts/run-adversarial-tests.py

# View generated tests
cat docs/ADVERSARIAL_TEST_REPORT.md
```

### Framework Propagation Issues
```bash
# Validate agent file structure
grep -A 5 "^contract:" nWave/agents/business-analyst.md

# Check YAML frontmatter
head -20 nWave/agents/business-analyst.md | grep -A 10 "^---$"
```

---

## References

- **Full Summary**: `docs/VALIDATION_IMPLEMENTATION_SUMMARY.md`
- **Implementation Plan**: `docs/NEXT_STEPS_WEEK2-3.md`
- **Compliance Report**: `docs/COMPLIANCE_VALIDATION_REPORT.md`
- **Adversarial Tests**: `docs/ADVERSARIAL_TEST_REPORT.md`
- **Template**: `nWave/templates/AGENT_TEMPLATE.yaml`

---

**Last Updated**: 2025-10-05
**Version**: 1.5.2
