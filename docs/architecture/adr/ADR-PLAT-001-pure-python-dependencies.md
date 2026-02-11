# ADR-PLAT-001: Pure Python Dependencies

## Status

**Accepted**

## Context

The versioning and release management feature requires operations that are traditionally performed by external command-line tools:

| Operation | Traditional Tool |
|-----------|------------------|
| HTTP requests | curl, wget |
| Archive extraction | tar |
| Checksum validation | shasum, sha256sum |
| File downloads | curl, wget |

The solution architecture (Morgan) initially listed these as optional dependencies. However, this creates several challenges:

1. **Cross-platform inconsistency**: Windows doesn't have curl/wget/tar/shasum by default
2. **Tool detection complexity**: Need to detect which tools are available
3. **Behavior differences**: curl vs wget have different flags and behaviors
4. **CI/CD portability**: Different GitHub Actions runners have different tools
5. **User friction**: Users may need to install additional tools

Mike's platform decision: **Pure Python only** for maximum cross-platform compatibility.

## Decision

**Use Python standard library and well-established packages for all operations instead of external tools.**

### Implementation Mapping

| Operation | External Tool | Python Alternative |
|-----------|---------------|-------------------|
| HTTP GET requests | curl, wget | `requests` library |
| Download with progress | curl --progress | `requests` + chunked download |
| Archive extraction | tar -xzf | `tarfile` module (stdlib) |
| Archive creation | tar -czf | `tarfile` module (stdlib) |
| SHA256 checksum | shasum -a 256 | `hashlib` module (stdlib) |
| JSON parsing | jq | `json` module (stdlib) |
| YAML parsing | yq | `pyyaml` library |
| Path operations | Various | `pathlib` module (stdlib) |
| Directory copy | cp -r | `shutil` module (stdlib) |

### Dependency List

**Standard Library (no installation needed)**:
- `tarfile` - Archive operations
- `hashlib` - Checksum generation/validation
- `json` - JSON parsing
- `pathlib` - Path operations
- `shutil` - File/directory operations
- `tempfile` - Temporary file handling
- `urllib.parse` - URL parsing

**Third-party (already in project dependencies)**:
- `requests` - HTTP operations (already used)
- `pyyaml` - YAML parsing (already used)

## Consequences

### Positive

1. **True cross-platform**: Works identically on Windows, macOS, Linux
2. **No tool detection**: No need to check for curl vs wget
3. **Consistent behavior**: Same code path on all platforms
4. **Simpler testing**: No need to mock external tools
5. **No installation friction**: Users need only Python 3
6. **CI/CD simplicity**: No tool installation in GitHub Actions

### Negative

1. **Larger download**: `requests` library adds some overhead
2. **No shell integration**: Can't pipe to other tools (but not needed)
3. **Progress display**: Need custom implementation (simple text-based)

### Neutral

1. **Performance**: Python is slightly slower than native tools, but difference is negligible for our use case (downloading a few MB)
2. **Code complexity**: Slightly more Python code, but more maintainable

## Implementation Examples

### HTTP Download with Checksum Validation

```python
import hashlib
import requests
from pathlib import Path

def download_with_checksum(url: str, target: Path, expected_sha256: str) -> bool:
    """Download file and validate SHA256 checksum."""
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    sha256 = hashlib.sha256()
    with open(target, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            sha256.update(chunk)
            f.write(chunk)

    actual = sha256.hexdigest()
    if actual != expected_sha256:
        target.unlink()  # Delete corrupted file
        return False

    return True
```

### Archive Extraction

```python
import tarfile
from pathlib import Path

def extract_archive(archive: Path, target_dir: Path) -> None:
    """Extract tar.gz archive to target directory."""
    with tarfile.open(archive, 'r:gz') as tar:
        # Security: prevent path traversal
        for member in tar.getmembers():
            if member.name.startswith('/') or '..' in member.name:
                raise ValueError(f"Unsafe path in archive: {member.name}")
        tar.extractall(target_dir)
```

### Checksum Generation

```python
import hashlib
from pathlib import Path

def generate_sha256(file_path: Path) -> str:
    """Generate SHA256 checksum for a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

## Alternatives Considered

### Alternative 1: External Tools with Detection

Detect available tools and use them:

```python
def get_download_command():
    if shutil.which('curl'):
        return ['curl', '-L', '-o']
    elif shutil.which('wget'):
        return ['wget', '-O']
    else:
        raise RuntimeError("Neither curl nor wget found")
```

**Rejected because**: Still fails on Windows without additional installation, adds complexity.

### Alternative 2: Hybrid Approach

Use Python for Windows, external tools for Unix:

```python
if platform.system() == 'Windows':
    use_python_implementation()
else:
    use_external_tools()
```

**Rejected because**: Two code paths doubles testing burden, inconsistent behavior.

### Alternative 3: Require External Tools

Document curl/wget/tar/shasum as required prerequisites.

**Rejected because**: Contradicts "minimal prerequisites" design goal, user friction.

## References

- Python `requests` library: https://docs.python-requests.org/
- Python `tarfile` module: https://docs.python.org/3/library/tarfile.html
- Python `hashlib` module: https://docs.python.org/3/library/hashlib.html
- Mike's platform decision: Pure Python for cross-platform compatibility

## Decision Record

| Field | Value |
|-------|-------|
| Decision | ADR-PLAT-001 |
| Date | 2026-01-28 |
| Author | Apex (platform-architect) |
| Status | Accepted |
| Deciders | Mike (stakeholder) |
