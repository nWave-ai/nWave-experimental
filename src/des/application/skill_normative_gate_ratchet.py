"""Ratchet the skill-normative gate's INDETERMINATE population (Mikado D86).

Feature: gate-ratchet-skill-normative.
Layer: Application (orchestration; owns no matching logic of its own).

`des skill-normative-gate` exits INDETERMINATE (4) on any could-not-verify
clause -- an absent/undecodable skill asset, or a non-discriminating marker --
and the PreToolUse Write/Edit intercept blocks on any non-zero exit. One
could-not-verify clause therefore locked EVERY edit under `nWave/skills/**`,
including the edit that would repair the very asset the gate names (Mikado
D86, mirrors `validate_mikado_tree_coherence.py`'s own 2026-07-30 incident,
commit 4a84eba0e -- the precedent this module extends the pattern to).

The fix routes the INDETERMINATE exit-code DECISION through the EXISTING
gate-agnostic ratchet (`des.domain.gate_ratchet.decide_ratchet` /
`undecidable_baseline`), never re-implemented here:
  - findings still print, still count, verdict still reads INDETERMINATE;
  - growth in the could-not-verify population REFUSES, naming the new claim;
  - no growth ALLOWS, saying in words this is NOT a clean pass;
  - FAIL is never reached here -- the CLI only calls this on INDETERMINATE;
  - an unreadable baseline REFUSES (fail-closed), never permits.

The baseline is RECOMPUTED from HEAD's own blobs (manifest + every clause's
skill asset), in THIS process against THIS object store, never stored --
reusing `SkillNormativeGateService.evaluate()` UNMODIFIED against a
`HeadSkillCorpusReader` (HEAD-git-blob-backed) instead of the working-tree
`SkillCorpusReader`. Zero duplication of the clause-matching logic.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from des.adapters.driven.git.head_skill_corpus_reader import (
    HeadBlobUnreadable,
    HeadSkillCorpusReader,
)
from des.application.skill_normative_gate_service import SkillNormativeGateService
from des.domain.gate_ratchet import (
    RatchetDecision,
    decide_ratchet,
    undecidable_baseline,
)
from des.domain.skill_normative_clause import (
    ManifestAssetAbsent,
    ManifestAssetUndecodable,
    UnreadableClause,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.adapters.driven.git.git_commit_contents import CommitContentsPort
    from des.adapters.driven.git.git_commit_reachability import (
        CommitReachabilityPort,
    )
    from des.domain.skill_normative_clause import NormativeVerdict


def third_state_keys(verdict: NormativeVerdict) -> tuple[str, ...]:
    """One identity per INDETERMINATE finding: `<kind> · <skill> · <clause_id>`.

    Compared as a MULTISET by `decide_ratchet` -- never deduplicated, and
    never the rendered text (which carries a path/detail that can change
    without the finding's own identity changing).
    """
    keys: list[str] = []
    for finding in verdict.indeterminate:
        kind = (
            "asset-unreadable"
            if isinstance(finding, UnreadableClause)
            else "marker-non-discriminating"
        )
        keys.append(f"{kind} · {finding.skill} · {finding.clause_id}")
    return tuple(keys)


def baseline_indeterminate_keys(
    *,
    root: Path,
    manifest_path: Path,
    contents: CommitContentsPort,
    reachability: CommitReachabilityPort,
) -> tuple[tuple[str, ...] | None, str]:
    """This gate's INDETERMINATE population over HEAD's own manifest + assets.

    `(keys, provenance)` when HEAD's state could be measured; `(None, reason)`
    when it could not -- the caller MUST treat `None` as a refusal, never as
    permission (fail-closed). Mirrors
    `validate_mikado_tree_coherence.baseline_findings` (commit 4a84eba0e).
    """
    head = reachability.resolve_head()
    if head is None:
        return None, f"HEAD does not resolve in `{root}`"

    reader = HeadSkillCorpusReader(contents, head, root)
    service = SkillNormativeGateService(reader, root)
    try:
        previous = service.evaluate(manifest_path)
    except ManifestAssetAbsent:
        # Only the MANIFEST's own read reaches here uncaught (a clause-level
        # ABSENT asset is caught INSIDE evaluate() and becomes a counted
        # UnreadableClause finding -- the intended asymmetry). The manifest
        # itself absent at HEAD means the document is new: nothing to compare
        # against, so every current finding is introduced here.
        return (), (
            f"HEAD `{head[:9]}` does not record the manifest at all, so it is "
            "new and every finding in it is introduced here"
        )
    except (ManifestAssetUndecodable, HeadBlobUnreadable) as exc:
        return None, f"the previous manifest state is unreadable: {exc}"

    rel_manifest = _relative_to_root(manifest_path, root)
    provenance = (
        f"HEAD `{head[:9]}` · `{rel_manifest}` "
        f"(check it: git rev-parse {head[:9]}:{rel_manifest})"
    )
    return third_state_keys(previous), provenance


def ratchet_decision(
    verdict: NormativeVerdict,
    *,
    root: Path,
    manifest_path: Path,
    repo: Path,
    contents: CommitContentsPort,
    reachability: CommitReachabilityPort,
) -> RatchetDecision:
    """Decide the EXIT CODE for an INDETERMINATE verdict, on the DELTA.

    Callers MUST reach this ONLY when `verdict` is already INDETERMINATE (the
    cost -- a second pass over git history -- must not be paid by a PASS or a
    FAIL run), and MUST NOT call it for a FAIL verdict (FAIL is never
    ratcheted, at any count).
    """
    current = third_state_keys(verdict)
    baseline, note = baseline_indeterminate_keys(
        root=root,
        manifest_path=manifest_path,
        contents=contents,
        reachability=reachability,
    )
    if baseline is None:
        return undecidable_baseline(current, note)
    decision = decide_ratchet(current, baseline, note)
    if not decision.introduced:
        return decision
    first_kind, first_skill, first_clause = decision.introduced[0][0].split(" · ", 2)
    return replace(
        decision,
        how=(
            f"re-run `des skill-normative-gate --root {repo}` to see the "
            f"current finding for `{first_skill}` — `{first_clause}` "
            f"({first_kind}); restore the marker/asset it names, or add the "
            "clause's asset back, then re-run the gate."
        ),
    )


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
