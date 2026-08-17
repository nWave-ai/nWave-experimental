---
name: nw-tdd-review-enforcement
description: Contract-bound review rules for immutable-oracle integrity, driving-port behavior, test economy, architecture boundaries, and terminal delivery evidence.
user-invocable: false
disable-model-invocation: true
---

# TDD Review Enforcement

Apply these laws in the repository's native language and test framework.

## Observable specification

- Acceptance tests assert domain-visible results through real driving ports.
- One deliberate installed-surface walking skeleton proves reachability.
- Internal classes, private call counts and source/AST shape are not behavioral
  acceptance oracles.
- Broad state, sequence and failure spaces use property-based tests when the
  language supports them; each below-port law maps to the promised observation.

## Immutable oracle

The accepted oracle locator and digest come from the validated
`DeliveryContract`. The crafter may read and execute it but never modify,
replace, skip or weaken it. An oracle defect returns to DISTILL; an
implementation defect returns to DELIVER.

## Scope and architecture

Compare the actual candidate diff with contract targets and boundaries. Reject
undeclared production paths, changed dependency direction, bypassed ports,
duplicated responsibility and public contract drift. For `GREEN_TO_GREEN`,
require complement equality over the relevant observation universe; for
`RED_TO_GREEN`, require the diagnosed/new behavior to fail then pass for the
right reason.

## Test portfolio

Minimize tests while preserving distinguishable user/business behaviors,
cross-layer failure handling and mutation value. Duplicate scenarios,
parameter inflation, language-guarantee checks and implementation-coupled pins
are findings. Coverage percentage alone neither proves nor replaces the oracle.

## Evidence

Run the exact literal command vectors declared by the contract through the
declared interpreter. Terminal exit plus captured observation is evidence;
timeout, partial narration, ambient interpreter substitution or an unexecuted
command is `INDETERMINATE`.

Review joins by contract, oracle and candidate identity with `PASS` as identity,
`FAIL` as absorbing and missing/stale evidence preventing PASS. Whole-delivery
source-blind EXAMINE is independent of technical test review.
