"""SSOT for the git-subcommand literals duplicated across the git adapters.

techdebt `git-string-constants-ssot`: ``"rev-parse"`` and ``"HEAD"`` were raw
string literals repeated at matching call slots across the git adapters
(`duplicated_constant` score 1.0/0.91). This module is the one canonical home
for those two literals; every adapter that shells a `git rev-parse` or refers
to the `HEAD` ref imports from here instead of re-typing the literal.

Scope is the driven-adapter layer (``src/des/adapters/driven/``) -- the layer
the techdebt entry names. The ``src/des/cli/`` call sites keep their inline
literals: the CLI is a different layer with its own local ``_git`` helpers, and
reaching into an adapter-private constants module from there would trade one
duplication for a worse coupling.

Behavior-preserving only: the values are byte-identical to the strings they
replace, this is pure string interning, not a git-behavior change.
"""

from typing import Final


GIT_REV_PARSE: Final = "rev-parse"
GIT_HEAD: Final = "HEAD"
