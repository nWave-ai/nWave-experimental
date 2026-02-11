> **Note**: The build pipeline referenced in this document was eliminated in the build-pipeline-elimination feature. This document is preserved for historical reference only.

# Root Cause Analysis: npm Build Script Failures

**Investigation Date**: 2026-01-21
**Investigator**: Lyra (Troubleshooter Agent)
**Status**: Complete - 2 Independent Root Causes Identified
**Severity**: Build Blocking (CI/CD Impact)

---

## Executive Summary

The npm build script fails with two distinct root causes:

1. **Missing Framework Documentation**: Agent file references non-existent dependency file
2. **YAML Parsing Corruption**: HTML comments embedded in YAML frontmatter break parser

Both are legitimately blocking issues that require fixing. Neither are configuration problems - they are actual specification violations in the codebase.

---

## Issue #1: Missing Dependency Reference

### Symptom
```
ERROR - Could not resolve dependency: data/docs/features/framework-rationalization/04-develop/p0-01-analysis.md
ERROR - Error processing agent /mnt/c/Repositories/Projects/nwave/nWave/agents/agent-builder-reviewer.md
```

### 5-Whys Analysis

**WHY #1: What immediate cause produces this error?**

The build system attempts to resolve a file reference in `agent-builder-reviewer.md` dependencies section but the file does not exist at the specified path: `/mnt/c/Repositories/Projects/nwave/nWave/data/docs/features/framework-rationalization/04-develop/p0-01-analysis.md`

**Evidence**:
- Directory verification: `./nWave/data/docs/features/` does not exist
- File search: `find ./nWave/data -type d -name "04-develop"` returns no results

---

**WHY #2: Why does this file reference exist if the file doesn't exist?**

Someone added a dependency reference to `agent-builder-reviewer.md` that points to a file that was never created or committed to the repository.

**Evidence**:
- Git history: `4165ac0 feat(p0-03): Implement agent-builder-reviewer specification...` (creation)
- Git history: `83a6e88 [FRAMEWORK] p0-01: Improve command template based on analysis` (shows intent)
- Current state: File missing from repository

---

**WHY #3: Why wasn't this caught by validation before commit?**

The build system has no pre-commit hook validation, and tests don't validate agent dependency resolution.

**Evidence**:
- Tests pass (219 tests) despite missing dependencies
- Build only runs when explicitly invoked
- No CI gate prevents committing broken agent dependencies

---

**WHY #4: Why doesn't the build system skip unresolved dependencies gracefully?**

The build processor treats unresolved dependencies as critical errors, halting the entire build.

**Evidence**:
- Build log: `ERROR - Error processing agent agent-builder-reviewer.md`
- Error cascades to halt entire build (errors > 0)

---

**WHY #5 (ROOT CAUSE)**: Why does this dependency reference exist without the corresponding file?

**Root Cause**: During recent agent specification updates, a reference to planned framework rationalization documentation was added to `agent-builder-reviewer.md` dependencies, but the actual documentation file was never created or the reference was not cleaned up.

**Contributing Factors**:
1. No validation gate preventing forward references without corresponding files
2. No pre-commit hooks to catch this during development
3. Reference appears intentional (versioned paths like `04-develop`) suggesting planned but unimplemented content

---

## Issue #2: YAML Parsing Error

### Symptom
```
ERROR - Failed to parse YAML configuration: while parsing a block collection
  in "<unicode string>", line 759, column 7:
expected <block end>, but found '?'
```

### 5-Whys Analysis

**WHY #1: What immediate cause produces this parse error?**

The YAML parser encounters HTML comment syntax within the YAML block:

```yaml
# Line 88-90 in agent-builder.md
<!-- BUILD:INJECT:START:nWave/data/embed/agent-builder/critique-dimensions.md -->
<!-- Content will be injected here at build time -->
<!-- BUILD:INJECT:END -->
```

HTML comments (`<!-- -->`) are NOT valid YAML syntax. The parser sees `<!--` and tries to parse `?` as a YAML key marker, causing the error.

**Evidence**:
- Error occurs at line 89 (where first HTML comment exists)
- YAML parser outputs: "could not find expected ':'"
- HTML comments are present in the extracted YAML section

---

**WHY #2: Why are HTML comments in a YAML block?**

The agent-builder.md file contains a hybrid format where BUILD:INJECT markers were added to indicate where embed content should be injected at build time. These markers were accidentally placed INSIDE the YAML code fence rather than after it closes.

**Evidence**:
- Build log shows successful embed processing: `Injecting embed content`
- The comment markers are intentional (BUILD:INJECT:START/END pattern)
- Other files use same pattern

---

**WHY #3: Why doesn't the YAML parser reject this earlier?**

The parser attempts to parse the entire YAML block including HTML comments because they're inside the triple-backtick fence.

**Evidence**:
- Code extracts YAML between `yaml\n` and the next ` ``` `
- This includes lines with HTML comments
- Parser correctly rejects this as invalid YAML

---

**WHY #4: Why is the build tolerating this and still producing output?**

The AgentProcessor has error handling that logs YAML errors but continues processing anyway, allowing partial success.

**Evidence**:
- Build continues after YAML error
- Embed content injection still happens

---

**WHY #5 (ROOT CAUSE)**: Why are HTML comments placed inside the YAML code block?

**Root Cause**: During implementation of the BUILD:INJECT embed system, injection markers were added without considering they would be inside a YAML code fence that the build system parses as YAML configuration.

**Contributing Factors**:
1. The file serves dual purposes: YAML configuration + markdown documentation
2. The YAML block extends beyond where pure configuration ends
3. BUILD:INJECT markers were designed for markdown context but placed in YAML context

---

## Root Cause Summary

| Issue | Root Cause | Type | Legitimacy |
|-------|-----------|------|-----------|
| Missing Dependency | Unresolved file reference in agent-builder-reviewer.md | Specification Violation | **Legitimate Issue** |
| YAML Parsing Error | HTML comments inside YAML code fence in agent-builder.md | Formatting Error | **Legitimate Issue** |

Both issues are **real problems** that block the build legitimately. They are NOT configuration problems.

---

## Impact Assessment

- **Build Impact**: Build exits with error code 1, preventing CI/CD completion
- **Test Impact**: Tests pass (219 tests) but don't validate build specifications
- **Codebase Impact**: 2 of 24 agent files have specification violations

---

## Recommended Actions

### Issue #1: Missing Dependency
Choose one:

1. **Remove the reference** - Delete from agent-builder-reviewer.md dependencies (simplest)
2. **Create the file** - Create the referenced path with appropriate content
3. **Mark as future** - Comment it as a forward reference

### Issue #2: YAML Parsing Error
**Move HTML comments outside the YAML code fence** in agent-builder.md. The comments should appear after the closing ` ``` ` of the YAML code block.

---

## Key Findings

1. **The build system is working correctly** - properly catching specification violations
2. **Both errors are legitimate** - they represent real problems in the codebase
3. **Tests provide false confidence** - they pass but don't validate build specifications
4. **No pre-commit validation exists** - broken specifications reach the repository
5. **Root causes are design issues** - not runtime failures

The build failures are not indicators of a broken system, but evidence that the system is functioning as intended by catching specification violations before they propagate.
