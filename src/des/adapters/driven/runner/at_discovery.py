"""Shared AT-discovery scan primitive (fix-runner-scope-discover-dedup, slice-01).

The ONE ``strip_line_comments`` + ONE ``discover_ats_by_regex`` shared
primitive every per-language ``discover_*_ats`` wrapper delegates to,
matching the package convention set by ``tool_discovery.py`` /
``runner_json.py`` / ``reentrancy_guard.py`` -- each one narrow shared
concern.

Consolidates the line/regex-scan discovery logic previously duplicated
byte-identically (modulo docstring) across
``cargo_runner.discover_cargo_ats``, ``csharp_runner.discover_csharp_ats``,
``java_runner.discover_java_ats``, and ``kotlin_runner.discover_kotlin_ats``:
read the regression file's raw bytes, decode as UTF-8, strip ``//``-to-EOL
line comments, then scan with the caller-supplied compiled regex. Each
per-language wrapper supplies ONLY its own compiled pattern and its own
zero-found noun (e.g. ``"#[test] functions"`` / ``"[Fact] methods"``);
degrade-LOUD (``RunnerAdapterUnavailable``, never a silently-empty
discovery) on an unreadable file, an undecodable file, or zero matches.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from des.ports.test_runner_port import AtDiscoveryResult, RunnerAdapterUnavailable


if TYPE_CHECKING:
    import re
    from pathlib import Path

    from des.ports.test_runner_port import RunnerAdapter


def strip_line_comments(source: str) -> str:
    """Strip ``//``-to-EOL line comments before attribute/annotation matching.

    Minimal robust line-scan (no per-language parser, no block-comment /
    string-literal awareness -- deliberately out of scope): a test marker
    occurring only inside a ``//`` line comment is text, never a real
    attribute/annotation, and must never satisfy a language's test-marker
    regex. Newlines are preserved so multi-line attribute-then-declaration
    matching is unaffected.
    """
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def discover_ats_by_regex(
    adapter: RunnerAdapter,
    regression_test_file: Path,
    pattern: re.Pattern[str],
    zero_found_noun: str,
) -> AtDiscoveryResult:
    """Discover the AT identities ``regression_test_file`` carries via ``pattern``.

    The shared line/regex-scan primitive (no per-language parser) every
    ``discover_*_ats`` per-language wrapper delegates to: read raw bytes,
    decode as UTF-8, strip ``//`` line comments, then run the caller-supplied
    compiled ``pattern`` over the stripped text. Degrade-LOUD
    (``RunnerAdapterUnavailable``, never a silently-empty discovery) when the
    file cannot be read, cannot be decoded, or yields zero matches -- the
    zero-match refusal names the caller's OWN ``zero_found_noun`` (never
    another language's), so consolidation cannot flatten each language's
    distinct wording.
    """
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name, reason=f"cannot read {regression_test_file}: {exc}"
        ) from exc
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"cannot read/decode {regression_test_file}: malformed "
                f"(not valid UTF-8): {exc}"
            ),
        ) from exc
    at_ids = pattern.findall(strip_line_comments(text))
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero {zero_found_noun} found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = ["discover_ats_by_regex", "strip_line_comments"]
