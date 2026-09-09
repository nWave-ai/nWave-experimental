"""Which projection of DES is running, declared before a delivery step works.

MIGRATED FROM THE RETIRED COMPOSED RUN, not invented here. `des dispatch`
declared this on stderr before it read its Request, and five acceptance
scenarios asserted the property (census 2026-09-06, rows «a run names the entry
point and the tree it executes», «two projections declare different
identities», «the declaration never becomes a gate», «a run killed before it
reads its Request still names its tree»). ADR-DES-003 Section 11 sorts it to
the MODEL: it is stated over ONE invocation, so it survives the composer on
every step that buys a turn.

Three projections of DES coexist -- an editable checkout, a global install and
a per-campaign wheel -- and a consumer selects one implicitly, through PATH, a
runtime pointer or a venv. None of them said so, so a Software Factory run
rediscovered a defect the source had closed seventeen minutes earlier and
nobody saw it during the run. Naming both is what makes a divergence readable
at the moment it matters.
"""

from __future__ import annotations

import sys
from pathlib import Path

import des
from des.runtime.tree_hash import canonical_tree_hash


def projection() -> dict[str, str]:
    """The entry point invoked and the code tree it actually imported.

    `rewrite_imports=True` normalises the pre-rewrite checkout to the
    post-rewrite installed form, and is a no-op on an already-installed tree, so
    one commit hashes the same through every projection. Measured on this repo:
    ~60 ms over 195 files on local disk, ~900 ms when the tree is on a Windows
    mount, against a delivery whose cheapest observed run was 19.9 s.
    """
    package = Path(des.__file__).resolve().parent
    try:
        tree = canonical_tree_hash(package, rewrite_imports=True)
    except (OSError, UnicodeDecodeError) as exc:
        # Degrade LOUD: an unreadable tree is reported in the same field, never
        # omitted and never silently replaced by a plausible-looking digest.
        tree = f"unreadable({exc.__class__.__name__})"
    return {"entry": sys.argv[0], "package": str(package), "tree": tree}


def declare(identity: dict[str, str] | None = None) -> dict[str, str]:
    """Announce the running projection on stderr, whatever the outcome follows.

    stderr, because a step's terminal owns stdout: ADR-DES-003 Section 3 G1
    fixes one block on one stream, and a runtime line printed into it would be a
    row the grammar does not carry. The declaration is made BEFORE the work, so
    an interrupted or killed step still says which tree it was -- the 09-04
    diagnosis needed this DURING the run, not after it.

    It never becomes a gate: it returns the identity it printed and decides
    nothing, so an unreadable tree cannot change any step's outcome.
    """
    identity = projection() if identity is None else identity
    print(
        "DELIVERY-RUNTIME: "
        + " ".join(f"{key}={value}" for key, value in identity.items()),
        file=sys.stderr,
    )
    return identity
