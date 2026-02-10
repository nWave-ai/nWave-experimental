# DISTILL Wave Quality Checklist

## Overview

Validation checklist for DISTILL wave completion focusing on acceptance test creation with production service integration patterns and Given-When-Then business validation with progressive complexity levels.

---

## 🟢 **BASIC Level - Essential DISTILL Wave Requirements**

### Test Directory Structure (MANDATORY)

- [ ] **Feature type determined**
  - Asked user: "Is this a nWave core feature or a plugin feature?"
  - Correct directory structure selected based on answer

- [ ] **nWave Core Feature** (if applicable)
  ```
  tests/nWave/<feature-name>/acceptance/
  ├── walking-skeleton.feature
  ├── milestone-{N}-{description}.feature
  └── steps/
      ├── conftest.py
      └── {domain}_steps.py
  ```

- [ ] **Plugin Feature** (if applicable)
  ```
  tests/plugins/<plugin-name>/<feature-name>/acceptance/
  ├── walking-skeleton.feature
  ├── milestone-{N}-{description}.feature
  └── steps/
      ├── conftest.py
      └── {domain}_steps.py
  ```

### Walking Skeleton (IMPLEMENT FIRST)

- [ ] **Walking skeleton defined before other scenarios**
  - Minimal E2E path documented in `walking-skeleton.feature`
  - ONE scenario that proves architecture works end-to-end
  - Observable outcome (files created, API response, etc.)
  - Separate file, not mixed with milestone scenarios

- [ ] **Walking skeleton implementation priority**
  - Walking skeleton is FIRST to be implemented
  - All other scenarios tagged with `@skip` or `@pending` until walking skeleton passes
  - Walking skeleton validation before expanding to full suite

### Acceptance Test Foundation

- [ ] **Given-When-Then format acceptance tests created**
  - All user stories have corresponding acceptance tests
  - Tests written in business language understandable by customers
  - Clear Given (context), When (action), Then (outcome) structure

- [ ] **Business-focused test scenarios**
  - Tests focus on business outcomes, not technical implementation
  - Customer workflows accurately represented in test scenarios
  - Business value validation embedded in test expectations

### Production Service Integration Planning

- [ ] **Production service integration patterns defined**
  - Step methods designed to call real production services
  - Dependency injection approach planned for service access
  - Service interfaces identified for test integration

- [ ] **Test environment architecture planned**
  - Test environment supports production service integration
  - Test data management approach defined
  - Service configuration for test execution planned

### One-E2E-at-a-Time Strategy

- [ ] **E2E test prioritization completed**
  - Acceptance tests prioritized by business value and risk
  - One-at-a-time implementation sequence defined
  - Test enabling/disabling strategy planned ([Ignore] attribute usage)

- [ ] **Commit strategy for E2E tests planned**
  - Commit workflow that prevents failing test commits
  - Pre-commit validation process designed
  - Test progression tracking approach defined

---

## 🟡 **INTERMEDIATE Level - Enhanced DISTILL Wave Quality**

### File Organization Standards

- [ ] **Feature files organized by milestone**
  - `walking-skeleton.feature` - Minimal E2E (always first)
  - `milestone-{N}-{description}.feature` - Per milestone
  - `integration-checkpoints.feature` - Cross-milestone validation
  - `error-handling.feature` - Error scenarios (optional, can be in milestone files)

- [ ] **Step definitions organized by domain**
  - `conftest.py` - Pytest fixtures and configuration
  - `{domain}_steps.py` - Domain-specific steps (e.g., `plugin_steps.py`, `installer_steps.py`)
  - `common_steps.py` - Shared/reusable step definitions
  - NO per-feature-file step organization

- [ ] **Step reuse enabled across feature files**
  - Common steps extracted to `common_steps.py`
  - Domain steps usable by multiple feature files
  - No duplicate step definitions

### Implementation Order Tagging

- [ ] **Scenarios tagged for implementation order**
  - `@walking-skeleton` - Implement FIRST
  - `@priority-critical` - Core functionality
  - `@priority-high` - Important features
  - `@priority-medium` - Secondary features
  - `@priority-low` - Nice-to-have features

- [ ] **Phase tagging for milestone tracking**
  - `@phase-{N}` - Corresponding implementation phase
  - `@milestone-{N}` - Corresponding journey milestone
  - `@integration-checkpoint` - Cross-milestone validation

### Advanced Acceptance Test Design

- [ ] **Comprehensive scenario coverage**
  - Happy path scenarios fully covered
  - Alternative paths and edge cases identified and tested
  - Error conditions and exception handling scenarios included

- [ ] **Business validation criteria established**
  - Success metrics for each acceptance test defined
  - Business KPIs integration with test validation
  - Customer satisfaction measures embedded in tests

### Production Service Integration Design

- [ ] **Service provider pattern implementation**
  - \_serviceProvider.GetRequiredService<T>() pattern established
  - Production service registration in test configuration
  - Service interface contracts defined for test integration

- [ ] **Anti-pattern prevention measures**
  - Test infrastructure business logic prevention
  - Excessive mocking avoidance strategies
  - Step method production service call validation

### Test Automation Architecture

- [ ] **Test execution framework established**
  - Acceptance test execution framework configured
  - Test reporting and results management
  - Test environment management and cleanup

- [ ] **Continuous integration planning**
  - CI/CD pipeline integration for acceptance tests
  - Automated test execution triggers
  - Test failure handling and notification

### Business Language Preservation

- [ ] **Ubiquitous language in tests**
  - Domain language consistently used throughout tests
  - Business terminology preserved from requirements to tests
  - Technical jargon avoided in test descriptions and assertions

- [ ] **Customer comprehension validation**
  - Tests reviewable and understandable by business stakeholders
  - Customer can validate test scenarios represent their needs
  - Business stakeholder sign-off on acceptance test scenarios

---

## 🔴 **ADVANCED Level - Comprehensive DISTILL Wave Excellence**

### Sophisticated Test Design

- [ ] **Property-based test integration planning**
  - Property-based tests planned for complex business rules
  - Test generation strategies for edge case discovery
  - Integration with acceptance test suite

- [ ] **Model-based testing approach**
  - State machine modeling for complex business processes
  - Model-based test generation for comprehensive coverage
  - Integration with Given-When-Then acceptance tests

### Advanced Production Integration

- [ ] **Real system integration validation**
  - Integration with actual databases and external services
  - Production-like data scenarios and management
  - Service virtualization for unavailable external dependencies

- [ ] **Performance testing integration**
  - Performance criteria embedded in acceptance tests
  - Load testing scenarios derived from acceptance tests
  - Performance regression prevention through acceptance tests

### Enterprise Test Management

- [ ] **Test data management strategy**
  - Test data generation and management approach
  - Data privacy and security in test environments
  - Test data versioning and lifecycle management

- [ ] **Regulatory compliance testing**
  - Compliance requirements embedded in acceptance tests
  - Audit trail and evidence collection through tests
  - Regulatory reporting automation through test results

### Advanced Automation Patterns

- [ ] **Visual testing integration**
  - UI/UX validation embedded in acceptance tests
  - Visual regression testing for user interfaces
  - Accessibility testing automation integration

- [ ] **Cross-browser and cross-platform testing**
  - Multi-environment test execution strategy
  - Platform-specific acceptance test variations
  - Compatibility validation automation

### Stakeholder Collaboration Enhancement

- [ ] **Living documentation approach**
  - Acceptance tests serve as up-to-date system documentation
  - Stakeholder access to test results and system behavior
  - Documentation generation from acceptance test results

- [ ] **Collaborative test refinement process**
  - Regular stakeholder review of acceptance test scenarios
  - Test scenario refinement based on stakeholder feedback
  - Continuous improvement of test quality and business alignment

---

## 🎯 **DISTILL Wave Completion Criteria**

### Mandatory Completion Requirements

- [ ] **All BASIC level requirements completed**
- [ ] **At least 80% of INTERMEDIATE level requirements completed**
- [ ] **Stakeholder approval of acceptance test scenarios**
- [ ] **DELIVER wave readiness confirmed**

### ATDD Methodology Validation

- [ ] **Customer-developer-tester collaboration operational**
  - Regular collaboration sessions established and functional
  - All three roles actively participating in acceptance test creation
  - Feedback loops operational for test refinement

- [ ] **Business language preservation validated**
  - Tests written in language understandable by business stakeholders
  - Domain terminology consistently used throughout test suite
  - Customer can validate and approve test scenarios

### Production Service Integration Readiness

- [ ] **Step method production service pattern established**
  - All step methods designed to call real production services
  - Service provider pattern implemented and tested
  - Production service interfaces available for implementation

- [ ] **Test environment production-like validation**
  - Test environment mirrors production service architecture
  - Production service integration patterns proven feasible
  - Test data and configuration support production service testing

---

## 📊 **Success Metrics**

### Quantitative Measures

- **Test Coverage**: 100% of user stories have corresponding acceptance tests
- **Business Language**: ≥95% of test content uses domain language
- **Stakeholder Approval**: 100% of acceptance test scenarios stakeholder-approved
- **Production Integration**: 100% of step methods call production services

### Qualitative Measures

- **Customer Comprehension**: Customers can understand and validate test scenarios
- **Business Value Focus**: Tests clearly validate business outcomes
- **Production Readiness**: Tests will validate real system behavior
- **Team Confidence**: Development team confident in test-driven implementation approach

---

## 🚨 **Red Flags - Immediate Attention Required**

- **Customer Disconnection**: Customers unable to understand or validate test scenarios
- **Technical Language Creep**: Tests becoming too technical for business stakeholders
- **Production Service Gaps**: Step methods not designed to call real production services
- **Test Infrastructure Business Logic**: Business logic implemented in test infrastructure
- **Excessive Mocking**: Over-reliance on mocks instead of real service integration
- **Incomplete Scenarios**: Major user workflows not covered by acceptance tests
- **E2E Test Overload**: Multiple failing E2E tests blocking development progress
- **Stakeholder Disengagement**: Business stakeholders not participating in test validation

---

## 🧪 **Production Service Integration Quality Gates**

### Step Method Validation

- [ ] **Production service invocation pattern**
  - All step methods contain \_serviceProvider.GetRequiredService<T>() calls
  - No business logic implementation in step methods
  - Step methods delegate all business operations to production services

- [ ] **Service registration validation**
  - Production services properly registered in test dependency injection
  - Service implementations available for test execution
  - Service configuration appropriate for test environment

### Anti-Pattern Prevention

- [ ] **Test infrastructure boundary enforcement**
  - Test infrastructure limited to setup/teardown operations only
  - No business logic in test environment or infrastructure classes
  - Clear separation between test support and production business logic

- [ ] **Mocking limitation validation**
  - Mocking limited to external system boundaries only
  - Internal application services use real implementations
  - Service integration tested with actual implementations

### Real System Integration

- [ ] **End-to-end system validation**
  - Acceptance tests exercise complete system workflows
  - Database operations use real database interactions
  - External service integration patterns validated

- [ ] **Production code path coverage**
  - Step methods invoke actual production code paths
  - No test-only code paths that bypass production implementation
  - Production service interfaces exercised through acceptance tests

---

## 📋 **Checklist Usage Guidelines**

### For Acceptance Designers (Quinn)

- Use this checklist to ensure comprehensive acceptance test coverage
- Focus on business language preservation and customer collaboration
- Validate production service integration patterns throughout test design

### For Luna (nw-product-owner)

- Support acceptance test validation from business perspective
- Ensure customer collaboration and stakeholder engagement
- Validate business language and domain terminology in tests

### For Test-First Developers (Devon)

- Review checklist to understand expected acceptance test quality
- Prepare for Outside-In TDD implementation guided by acceptance tests
- Validate production service integration approach before implementation

### For Stakeholders

- Use BASIC level items to understand expected participation in test validation
- Review acceptance test scenarios for business accuracy and completeness
- Provide feedback on test comprehension and business value validation

### Quality Assurance Teams

- Use checklist for acceptance test quality review
- Validate ATDD methodology compliance
- Ensure production service integration patterns prevent test infrastructure deception
