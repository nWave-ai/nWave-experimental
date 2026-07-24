"""PlaintextVerbLoader — loads protocol-surface verb lists from text files."""

from __future__ import annotations

import re
from pathlib import Path

from nwave_ai.feature_delta.adapters.refusal import refuse_startup
from nwave_ai.feature_delta.resources import packaged_resource


# The framework verb lists are PACKAGE RESOURCES: they travel with the install.
# They used to be resolved by walking four `.parent` hops OUT of the package to
# `nWave/data/`, which exists in a source checkout and on NO distribution
# channel — so from any install `en.txt` was unreadable and probe() died on a
# bare assert (a raw traceback, exit 1) instead of reporting on the document.
_VERB_DIR = packaged_resource("data", "protocol-verbs")
_SUBSTANTIVE_VERB_DIR = packaged_resource("data", "substantive-verbs")

# Per-repo override path (relative to the working directory / project root).
_OVERRIDE_RELPATH = ".nwave/protocol-verbs.txt"

# ReDoS detection: patterns containing nested unbounded quantifiers are rejected
# at startup. We scan for the structural signature of catastrophic backtracking:
#   - (A+)+, (A*)*, (A+)*, (A*)+ — a group with + or * followed by + or *
_REDOS_NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*][^)]*\)[+*?]*[+*]")


class ReDoSError(ValueError):
    """Raised when a user-supplied verb pattern contains a ReDoS-prone construct."""


class PlaintextVerbLoader:
    """Load protocol-surface and substantive verb lists from .txt files.

    Args:
        cwd_root: the project root to search for the per-repo override at
            ``.nwave/protocol-verbs.txt``. Defaults to the current working
            directory — the maintainer's own project, which is what the CLI
            passes explicitly (``cli.py``) and the only thing the override can
            sensibly mean. Pass ``tmp_path`` in tests to provide an isolated
            override without altering the framework verb data.
    """

    def __init__(
        self, cwd_root: Path | None = None, repo_root: Path | None = None
    ) -> None:
        # repo_root is accepted as an alias for cwd_root for backwards compatibility
        # with tests that used the old parameter name.
        resolved_cwd = cwd_root if cwd_root is not None else repo_root
        self._cwd_root = resolved_cwd if resolved_cwd is not None else Path.cwd()

    def load_protocol_verbs(self, lang: str = "en") -> tuple[str, ...]:
        """Return protocol-surface verbs for ``lang``.

        Loads framework defaults from the packaged resource
        ``nwave_ai/feature_delta/data/protocol-verbs/{lang}.txt``. If a per-repo
        override exists at ``.nwave/protocol-verbs.txt`` relative to
        ``cwd_root``, its patterns are unioned with the framework defaults.
        """
        framework_verbs = self._load(_VERB_DIR / f"{lang}.txt")

        override_path = self._cwd_root / _OVERRIDE_RELPATH
        if not override_path.exists():
            return framework_verbs

        override_verbs = self._load(override_path)
        # Union: framework defaults first, then per-repo additions.
        seen: dict[str, None] = {}
        for verb in framework_verbs:
            seen[verb] = None
        for verb in override_verbs:
            seen[verb] = None
        return tuple(seen.keys())

    def load_substantive_verbs(self, lang: str = "en") -> tuple[str, ...]:
        """Return substantive consequence verbs for ``lang``."""
        return self._load(_SUBSTANTIVE_VERB_DIR / f"{lang}.txt")

    def probe(self) -> None:
        """Startup health check — verify en.txt is accessible and non-empty.

        The tool's OWN missing file is refused LOUDLY and identically to every
        other adapter (D-6a): the structured ``health.startup.refused`` event,
        naming this adapter, the unreadable resource, and the cure — then exit
        70. It used to be a bare ``assert``, whose ``AssertionError`` escaped
        ``cli.py`` (which catches only ``ReDoSError``) as a raw traceback: output
        the maintainer cannot act on, and what the published product does today.

        Also scans any per-repo override at ``.nwave/protocol-verbs.txt`` for
        ReDoS-prone patterns (US-13 AC-4/AC-6, ADR-01). Raises ``ReDoSError``
        (caller maps to exit 70) when a pathological pattern is detected — the
        maintainer's OWN pattern is their problem to fix, not a damaged install,
        so it stays a distinct, catchable failure.
        """
        verbs = self.load_protocol_verbs("en")
        if not verbs:
            refuse_startup(
                "PlaintextVerbLoader",
                _VERB_DIR / "en.txt",
                "protocol-verb list is empty or missing",
            )

        override_path = self._cwd_root / _OVERRIDE_RELPATH
        if override_path.exists():
            override_verbs = self._load(override_path)
            for pattern in override_verbs:
                _check_redos(pattern)

    def _load(self, path: Path) -> tuple[str, ...]:
        if not path.is_file():
            return ()
        lines = path.read_text(encoding="utf-8").splitlines()
        return tuple(
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        )


def _check_redos(pattern: str) -> None:
    """Raise ``ReDoSError`` if ``pattern`` contains a nested-unbounded-quantifier.

    Detects the structural signature of catastrophic backtracking:
    a capturing group that itself contains ``+`` or ``*``, followed by ``+`` or ``*``.
    Examples rejected: ``(a+)+b``, ``(a*)*$``, ``(a+)*``.
    """
    if _REDOS_NESTED_QUANTIFIER.search(pattern):
        raise ReDoSError(
            f"health.startup.refused: pattern '{pattern}' contains a nested "
            "unbounded quantifier that may cause catastrophic backtracking (ReDoS). "
            "Use a literal string or a bounded quantifier instead."
        )
