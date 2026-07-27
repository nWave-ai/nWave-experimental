"""Forward-typing backport shim for Python 3.10 compatibility.

Designated location for typing-3.11+ symbols backported for Python 3.10.
Add new symbols here using the same try/except pattern (``Never``,
``assert_type``, ``LiteralString``, ``Required``, ``NotRequired``,
``TypeVarTuple``, ``Unpack``, etc.) -- this module, not a per-call-site
duplicate, is the ONE place that pattern lives.

The pattern is intentional: import from the stdlib first so static type
checkers and IDEs follow the canonical definition on 3.11+, then fall
back to a vendored, stdlib-only shim on 3.10 where the symbol is not yet
in the stdlib. The fallback deliberately does NOT import
``typing_extensions``: ADR-PLAT-007 (bundle-stdlib-only-runtime) requires
the bundled DES runtime to depend on nothing but Python on the target
machine, and ``typing_extensions`` is a PyPI package, not stdlib -- a
target running bare Python 3.10 with no ``typing_extensions`` installed
would otherwise crash on every DES hook invocation.

The vendored fallback below builds ``Self`` the same way ``typing``
itself builds its own special forms (``ClassVar``, ``Final``, ...) and
the same way ``typing_extensions`` builds its pre-3.11 ``Self``:
``typing._SpecialForm`` is a stable, long-standing private API of the
stdlib ``typing`` module (present since Python 3.7), not a new dependency.

References
----------
* Issue: https://github.com/nWave-ai/nWave/issues/43 — ``nwave-ai install``
  failed on Python 3.10 because ``src/des/domain/value_objects.py`` did
  ``from typing import Self`` unconditionally; ``typing.Self`` lands in
  the stdlib only at 3.11 (PEP 673). The repo declares
  ``requires-python = ">=3.10"``, so this module backports the symbol.
* techdebt.md id
  ``typing-extensions-import-escapes-bundle-stdlib-only-enforcement-gate`` —
  the original ``typing_extensions`` fallback was itself a live instance
  of the ADR's own documented gap (a fixed package blocklist, not an
  allowlist) letting a non-stdlib import reach the bundle undetected.
* PEP 673 — ``Self`` type, added to stdlib ``typing`` in Python 3.11
"""

import sys
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Static type-checkers (mypy runs with python_version = "3.10", so it
    # always evaluates THIS branch, never the runtime branches below) get
    # the real PEP-673 Self semantics from typing_extensions's stub -- a
    # dev-only, type-checking-time concern, never a runtime import.
    from typing_extensions import Self
elif sys.version_info >= (3, 11):
    from typing import Self
else:
    # At runtime on a bare Python 3.10 target, do NOT import
    # typing_extensions (a PyPI package, not stdlib -- see module
    # docstring). Vendor Self the same way typing/typing_extensions
    # build it: typing._SpecialForm is a stable, long-standing
    # private API of the stdlib typing module (since Python 3.7).
    # mypy statically excludes this branch under python_version = "3.10"
    # (sys.version_info >= (3, 11) is a check it understands and treats
    # as False for that target), same as the TYPE_CHECKING branch above.
    from typing import _SpecialForm  # type: ignore[attr-defined]

    @_SpecialForm
    def Self(self, params):  # type: ignore[misc]
        """Used to spell the type of "self" in classes (PEP 673).

        Vendored stdlib-only fallback for Python 3.10, where
        ``typing.Self`` does not yet exist. See the module docstring.
        """
        raise TypeError(f"{self} is not subscriptable")


__all__ = ["Self"]
