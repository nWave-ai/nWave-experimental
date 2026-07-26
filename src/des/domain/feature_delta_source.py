"""The feature-delta read seam -- one reader, three DISTINGUISHED outcomes.

WHY-NEW-FILE: src/des/domain/feature_delta_source.py
  CLOSEST-EXISTING: src/des/adapters/driven/filesystem/feature_delta_filesystem_reader.py
  EXTENSION-COST: that adapter implements the `FeatureDeltaReader` DRIVEN PORT
    whose contract is `str | None` -- the very collapse this module exists to
    undo. Widening it to a discriminated outcome changes an abstract port and
    breaks every in-memory double implementing it tree-wide.
  PARALLEL-RATIONALE: incompatible return contract on a published port
    (`str | None` vs a three-outcome record) plus a different consumer set --
    the port serves `DiscussGateOut.evaluate`, which only needs
    content-or-INDETERMINATE, while a GATE must tell the operator WHICH of
    three causes fired because each one routes to a DIFFERENT action.

Three causes, three operator actions -- and today's readiness gate collapsed
the first two into the second, reporting an ABSENT file as one that "could not
be read as UTF-8 text":

  * ABSENT       -> create it (or the path/tree is wrong); the HOW invokes the
                    PRODUCING TOOL (`des feature-delta-schema inject`,
                    `des feature-delta-doctor`), never advice about encodings.
  * UNDECODABLE  -> re-encode it as UTF-8. Nothing is missing; the bytes are.
  * PRESENT      -> the content is in hand; a failing invariant from here on is
                    a MISSING SECTION, and the action is to write that section.

The path layout `{repo_root}/docs/feature/{feature_id}/feature-delta.md` is the
same DESIGN-PINNED location the driven adapter reads (git-free, stdlib only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


#: Cause tokens carried on a gate's per-invariant record so a DOWNSTREAM
#: reader (e.g. the hook's refusal formatter) can branch on WHICH of the three
#: states fired instead of re-parsing prose.
FEATURE_DELTA_ABSENT = "feature-delta-absent"
FEATURE_DELTA_UNDECODABLE = "feature-delta-undecodable"
#: The delta WAS read; an invariant then found its own section missing.
FEATURE_DELTA_SECTION_MISSING = "feature-delta-section-missing"

_FEATURE_REL_DIR = ("docs", "feature")
_FEATURE_DELTA_FILE = "feature-delta.md"


def feature_delta_path(repo_root: Path, feature_id: str) -> Path:
    """The DESIGN-PINNED feature-delta location under ``repo_root``."""
    return repo_root.joinpath(*_FEATURE_REL_DIR, feature_id, _FEATURE_DELTA_FILE)


@dataclass(frozen=True)
class FeatureDeltaRead:
    """The outcome of one feature-delta read.

    ``content`` is non-None exactly when the read succeeded; ``cause`` and
    ``detail`` are empty exactly then. The two are never both meaningful --
    a reader that answers "here is the text" and "here is why there is no
    text" at once is the collapse this record exists to prevent.
    """

    path: Path
    content: str | None
    cause: str
    detail: str

    @property
    def is_present(self) -> bool:
        return self.content is not None


def _absent_detail(path: Path, repo_root: Path) -> str:
    return (
        f"what: no feature-delta.md exists at {path} / "
        f"why: the file is ABSENT (this is not an encoding problem -- nothing "
        f"was there to decode); the tree this gate read is {repo_root} / "
        f"how: if that tree is the wrong one, re-dispatch declaring the right "
        f"project root (`des dispatch --repo-root <project-root>`, which stamps "
        f"the DES-PROJECT-ROOT marker the gate resolves against). If the tree is "
        f"right, GENERATE the document, do not retype it: `des "
        f"feature-delta-schema inject --wave <wave>` emits the canonical "
        f"headings, then `des feature-delta-doctor {path}` names every remaining "
        f"structural gap in one pass"
    )


def _undecodable_detail(path: Path) -> str:
    return (
        f"what: the feature-delta at {path} EXISTS but its bytes are not valid "
        f"UTF-8 / why: an encoding fault -- no section is missing, the file "
        f"cannot be decoded at all / how: re-encode the file as UTF-8 (e.g. "
        f"`iconv -f <source-encoding> -t UTF-8`) and re-run this gate; do NOT "
        f"regenerate the document, its content is not in question"
    )


def read_feature_delta(repo_root: Path, feature_id: str) -> FeatureDeltaRead:
    """Read the feature-delta, distinguishing ABSENT from UNDECODABLE.

    Never raises: an unreadable artefact degrades LOUD into a record naming the
    cause + the remediation for THAT cause, so a gate can refuse with an
    actionable WHAT/WHY/HOW instead of a single mis-attributing sentence.
    """
    path = feature_delta_path(repo_root, feature_id)
    if not path.is_file():
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_ABSENT,
            detail=_absent_detail(path, repo_root),
        )
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_UNDECODABLE,
            detail=_undecodable_detail(path),
        )
    except OSError as exc:
        # Present-but-unopenable (permissions, a broken symlink target, an I/O
        # error). Neither "absent" nor "bad encoding" -- say what actually
        # happened rather than borrowing one of the other two causes.
        return FeatureDeltaRead(
            path=path,
            content=None,
            cause=FEATURE_DELTA_UNDECODABLE,
            detail=(
                f"what: the feature-delta at {path} exists but could not be "
                f"opened ({exc.strerror or exc}) / why: a filesystem-level read "
                f"error, not a missing document and not an encoding fault / "
                f"how: fix the file's permissions or the broken link at that "
                f"path, then re-run this gate"
            ),
        )
    return FeatureDeltaRead(path=path, content=content, cause="", detail="")
