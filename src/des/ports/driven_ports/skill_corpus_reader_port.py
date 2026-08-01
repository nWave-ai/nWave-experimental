"""SkillCorpusReaderPort -- driven port: read the normative-clause manifest + assets.

Feature: gate-ratchet-skill-normative (Mikado D86).

Structural (`typing.Protocol`), not nominal: `SkillCorpusReader` (working-tree
adapter, `adapters/driven/skill_corpus_reader.py`) and `HeadSkillCorpusReader`
(HEAD git-blob adapter, `adapters/driven/git/head_skill_corpus_reader.py`) both
satisfy this port by shape alone, so `SkillNormativeGateService` can be handed
either one without either adapter declaring inheritance. This is what lets the
gate's own ratchet baseline reuse `SkillNormativeGateService.evaluate()`
UNMODIFIED against a PAST corpus (HEAD's blobs) with zero duplication of the
matching logic -- the service does not know or care whether `read_asset` reads
today's working tree or a blob frozen at a past commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol


if TYPE_CHECKING:
    from pathlib import Path


class SkillCorpusReaderPort(Protocol):
    """Read-only driven port: the manifest JSON, and one skill asset's text."""

    def read_manifest(self, manifest_path: Path) -> dict[str, Any]: ...

    def read_asset(self, asset_path: Path) -> str: ...
