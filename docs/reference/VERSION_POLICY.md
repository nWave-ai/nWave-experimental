# nWave Framework Version Policy

**Version**: 1.5.2
**Date**: 2026-01-22
**Status**: Mandatory Policy

## Single Source of Truth

**ALL documentation and artifacts MUST use the framework version from `nWave/framework-catalog.yaml`.**

### Rationale

- Eliminates version confusion and drift
- Ensures documentation stays synchronized with framework releases
- Simplifies version management (one source, one truth)
- Pre-commit hooks enforce automatic compliance

## Version Format

```yaml
# nWave/framework-catalog.yaml
version: "X.Y.Z"  # Semantic versioning (MAJOR.MINOR.PATCH)
```

This version applies to:
- **ALL documentation files** (docs/*)
- **ALL markdown files with version fields**
- **Release artifacts**
- **Package metadata**

## Per-Document Versioning is PROHIBITED

❌ **WRONG**:
```markdown
# Document Title
**Version**: 1.5.2
**Framework Version**: 1.5.2
```

✅ **CORRECT**:
```markdown
# Document Title
**Version**: 1.5.2
**Date**: 2026-01-22
```

## Enforcement

### Pre-Commit Hooks

The `docs-version-validation` pre-commit hook automatically:
1. Reads version from `nWave/framework-catalog.yaml`
2. Checks all documents with version fields
3. **BLOCKS commits** if any document version ≠ framework version
4. Provides clear error messages with fix instructions

### Example Error

```
❌ COMMIT BLOCKED: Documentation version validation failed

File: docs/guides/example.md
Current version: 1.4.3
Framework version: 1.5.2

Fix: Update version field from '1.4.3' to '1.5.2'
```

## Version Update Procedure

### When to Bump Version

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR (X.0.0)**: Breaking changes, incompatible API changes
- **MINOR (X.Y.0)**: New features, backward-compatible functionality
- **PATCH (X.Y.Z)**: Bug fixes, backward-compatible corrections

### How to Update

1. **Update framework version** in `nWave/framework-catalog.yaml`:
   ```yaml
   version: "1.6.0"  # Example: minor version bump
   ```

2. **Pre-commit hook automatically updates** all document versions during commit

3. **No manual synchronization needed** - hooks handle it

### Manual Override (Emergency Only)

```bash
# Only use with explicit approval
git commit --no-verify
```

**WARNING**: Creates version drift and audit trail. Use sparingly.

## Version Field Format

All documentation with version metadata MUST use this format:

```markdown
**Version**: 1.5.2
**Date**: YYYY-MM-DD
**Status**: [Draft|Review|Production Ready|Deprecated]
```

**Required**:
- `Version`: Exactly matches framework-catalog.yaml version
- `Date`: ISO 8601 date (YYYY-MM-DD)

**Optional**:
- `Status`: Document lifecycle state

## Special Cases

### Non-Documentation Files

Files without version fields (README, guides without metadata, etc.):
- No version enforcement
- Implicitly use framework version
- Update as needed

### External Dependencies

Third-party documentation or vendored code:
- Keep original versioning
- Clearly mark as external
- Document source and version separately

## FAQ

### Q: What if my document changes but framework doesn't?

**A**: Update framework version (PATCH bump) and commit. All documents get synchronized.

### Q: Can I version documents independently?

**A**: No. Use framework version or no version field.

### Q: What if I forget to update version?

**A**: Pre-commit hook catches it and blocks the commit with fix instructions.

### Q: How do I version experimental documents?

**A**: Use framework version with `Status: Draft` instead of separate versioning.

## Compliance

This policy is **MANDATORY** and **AUTOMATICALLY ENFORCED**.

- ✅ Pre-commit hooks validate on every commit
- ✅ CI/CD validates during builds
- ✅ Clear error messages guide fixes
- ✅ No exceptions without --no-verify (audited)

## History

- 2026-01-22: Initial policy created (version 1.5.2)
  - Mandate single-source version from framework-catalog.yaml
  - Prohibit per-document versioning
  - Enforce via pre-commit hooks
