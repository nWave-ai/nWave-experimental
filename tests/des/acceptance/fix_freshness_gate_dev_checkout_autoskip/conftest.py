"""Composition root + shared fixtures for fix-freshness-gate-dev-checkout-autoskip.

Pillar 3 (App as in production): the SUT is wired through the PRODUCTION
composition root — the real `des.cli/__init__.py` → `assert_fresh_or_explain()`
gate invoked at import time inside a subprocess. Only the filesystem witnesses
(installed tree, dev-checkout adjacency directory) are tmp_path-scoped.

Mandate-12 criterion 2/3 (SSOT via Types + Services + DSL): the
`FreshnessAutoskipFixture` class below is the single source of truth for ALL
business logic the step methods need. Step bodies in `steps_freshness.py`
delegate here — each step body is ≤2 statements ending in a single
`fixture.<method>(...)` call, with no control flow inline.

DISTILL-authored RED scaffold (ADR-025): the production module
`src/des/runtime/freshness.py` ALREADY EXISTS — the RED comes from the NEW
behavior (CWD `.git/` adjacency auto-skip + `autoskipped` event) which the
current code does NOT implement. AT-01 + AT-03 assert the new behavior; both
RED-fail with assertion mismatch (NOT import error → Mandate-7 RED-vs-BROKEN
distinction preserved). AT-02 GREEN-passes today (regression-pin — verifies
the fix does not regress the customer topology).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# The feature directory uses snake_case (this tree); inject the feature root
# onto sys.path so `from freshness_steps.domain_types import ...` resolves
# locally. The package is named `freshness_steps` (not `steps`) to avoid a
# top-level package-name collision with
# `tests/installer/acceptance/fix-des-self-hosted-gate-sync/steps/` — both
# feature trees prepend their feature root onto sys.path, and a generic
# `steps` name would let whichever path got prepended first shadow the
# other's `domain_types` module across the whole test session.
_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from freshness_steps.domain_types import (  # noqa: E402
    CheckoutAdjacency,
    CheckoutProbe,
    GateInvocationOutcome,
    GateVerdict,
    InstalledTreeProbe,
)


# Repo root = .../nWave-dev (this file lives 5 dirs deep under tests/...)
_REPO_ROOT = _FEATURE_ROOT.parents[3]
_REAL_DES_SRC = _REPO_ROOT / "src" / "des"


# The minimum set of production files that comprise the freshness chain.
# Copying ONLY these keeps each AT spawn fast AND skips the heavyweight
# `des/__init__.py` re-export soup. Mirrors the precedent in
# tests/installer/acceptance/fix-des-self-hosted-gate-sync/conftest.py — when
# the freshness chain's file graph changes, this list and the sibling's stay
# in sync (single SSOT is `src/des/runtime/freshness.py` + its imports).
_FRESHNESS_PRODUCTION_FILES = (
    Path("runtime") / "freshness.py",
    Path("runtime") / "tree_hash.py",
    Path("ports") / "driven_ports" / "freshness_port.py",
    Path("adapters") / "driven" / "freshness" / "__init__.py",
    Path("adapters") / "driven" / "freshness" / "repo_source_probe.py",
    Path("adapters") / "driven" / "freshness" / "null_probe.py",
)


# Package-marker `__init__.py` files for the synthetic des/ tree.
_PACKAGE_MARKERS = (
    Path("__init__.py"),
    Path("cli") / "__init__.py",  # OVERWRITTEN below with composition-root call
    Path("runtime") / "__init__.py",
    Path("ports") / "__init__.py",
    Path("ports") / "driven_ports" / "__init__.py",
    Path("adapters") / "__init__.py",
    Path("adapters") / "driven" / "__init__.py",
)


# Composition root contents — MUST stay byte-identical to src/des/cli/__init__.py
# so the test exercises the same import-time wiring as production.
_COMPOSITION_ROOT_INIT = (
    '"""des.cli — composition root for every ``python -m des.cli.*`` invocation.\n\n'
    "Synthesised under tmp_path for the freshness-gate auto-skip ATs; matches\n"
    "src/des/cli/__init__.py byte-for-byte.\n"
    '"""\n\n'
    "from des.runtime.freshness import assert_fresh_or_explain\n\n\n"
    "assert_fresh_or_explain()\n"
)


def _parse_structured_event_line(stderr_text: str) -> str | None:
    """Extract `event` from the first structured JSON line on stderr.

    The gate emits one JSON-per-line; this helper finds the first parseable
    line whose `event` starts with `des.runtime.freshness.` and returns it.
    Returns None when no such line is present. Pure function.
    """
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = payload.get("event")
        if isinstance(event, str) and event.startswith("des.runtime.freshness."):
            return event
    return None


class FreshnessAutoskipFixture:
    """Composition-root service for fix-freshness-gate-dev-checkout-autoskip ATs.

    Pillar 3: invokes the SAME `assert_fresh_or_explain()` wired by the
    production `des.cli/__init__.py` composition root, against a synthetic
    installed tree under tmp_path. The auto-skip detection the bugfix adds
    fires inside that gate function; the AT observes its decision via the
    process exit code + the structured stderr event.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing
    more.
    """

    def build_installed_tree(
        self,
        tmp_path: Path,
        *,
        with_manifest: bool,
    ) -> InstalledTreeProbe:
        """Lay out a synthetic `lib/python/des/` package under tmp_path.

        Mirrors the real installer layout: `tmp_path/lib/python/des/` is the
        package root the gate inspects. The freshness chain is copied verbatim
        from `src/des/` (production SSOT); empty package markers stand in for
        the rest of `des/` so `import des.cli` runs the composition root
        WITHOUT triggering the heavyweight re-exports of the real
        `des/__init__.py`.
        """
        lib_python = tmp_path / "lib" / "python"
        des_root = lib_python / "des"
        des_root.mkdir(parents=True, exist_ok=True)

        for marker in _PACKAGE_MARKERS:
            target = des_root / marker
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

        # Overwrite the cli __init__ with the production composition-root call.
        (des_root / "cli" / "__init__.py").write_text(
            _COMPOSITION_ROOT_INIT, encoding="utf-8"
        )

        # Copy the freshness production files verbatim from src/des/. Any
        # future change to the gate flows through the AT automatically.
        for relpath in _FRESHNESS_PRODUCTION_FILES:
            src = _REAL_DES_SRC / relpath
            dst = des_root / relpath
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

        if with_manifest:
            # AT scope does NOT exercise the with_manifest path — AT-01/02/03
            # all stage a DEGRADED (no manifest) tree because the bugfix's
            # short-circuit must fire BEFORE the manifest probe. Future ATs
            # extending the auto-skip semantics may need a manifest.
            raise NotImplementedError(
                "AT scope only exercises with_manifest=False — extend if a "
                "future AT needs a manifest under the auto-skip path"
            )

        return InstalledTreeProbe(root=des_root, has_manifest=False)

    def build_checkout_probe(
        self,
        tmp_path: Path,
        *,
        adjacency: CheckoutAdjacency,
    ) -> CheckoutProbe:
        """Lay out a synthetic CWD with the requested `.git/` adjacency.

        DEV_CHECKOUT: creates a `tmp_path/dev-checkout/.git/` directory so the
        bugfix's CWD-adjacency probe detects the structural marker.
        CUSTOMER_HOST: returns a plain tmp_path subdirectory with no `.git/`
        adjacency — the regression-pin baseline.
        """
        cwd = tmp_path / "operator-cwd"
        cwd.mkdir(parents=True, exist_ok=True)
        if adjacency is CheckoutAdjacency.DEV_CHECKOUT:
            (cwd / ".git").mkdir(parents=True, exist_ok=True)
        return CheckoutProbe(cwd=cwd, adjacency=adjacency)

    def spawn_gate_against(
        self,
        installed: InstalledTreeProbe,
        checkout: CheckoutProbe,
    ) -> GateInvocationOutcome:
        """Run `python -c "import des.cli"` against the synthetic installed tree.

        PYTHONPATH points at the installed tree's parent so `import des.cli`
        resolves there. CWD is set to `checkout.cwd` so the bugfix's
        adjacency probe sees (or does not see) the `.git/` marker.

        Returns a GateInvocationOutcome capturing the port-exposed observables:
        exit code, stderr text, parsed structured event, verdict.
        """
        lib_python = installed.root.parent  # …/lib/python (parent of `des/`)

        # Build a hermetic env: only PATH (so the interpreter resolves
        # supporting binaries) and PYTHONPATH (so `import des` lands in the
        # synthetic tree). NWAVE_FRESHNESS is INTENTIONALLY UNSET — the
        # bugfix's auto-skip path must work WITHOUT the operator-set bypass,
        # else the daily-friction-closure semantics are not exercised.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(lib_python),
        }
        for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
            if var in os.environ:
                env[var] = os.environ[var]

        completed = subprocess.run(
            [sys.executable, "-c", "import des.cli"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(checkout.cwd),
            timeout=30,
        )
        stderr_text = completed.stderr
        event = _parse_structured_event_line(stderr_text)
        verdict = (
            GateVerdict.REFUSE if completed.returncode != 0 else GateVerdict.PROCEED
        )
        return GateInvocationOutcome(
            exit_code=completed.returncode,
            stderr_text=stderr_text,
            stderr_event=event,
            verdict=verdict,
        )


@pytest.fixture
def autoskip_fixture() -> FreshnessAutoskipFixture:
    """The single composition-root service all step methods delegate to."""
    return FreshnessAutoskipFixture()


@pytest.fixture
def state() -> dict:
    """Per-scenario scratchpad: `installed`, `checkout`, `outcome`, `before`."""
    return {}


__all__ = [
    "FreshnessAutoskipFixture",
]
