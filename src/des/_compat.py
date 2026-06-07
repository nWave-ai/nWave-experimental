"""Forward-typing backport shim for Python 3.10 compatibility.

Designated location for typing-3.11+ symbols backported via
``typing_extensions``. Add new symbols here using the same try/except
pattern (``Never``, ``assert_type``, ``LiteralString``, ``Required``,
``NotRequired``, ``TypeVarTuple``, ``Unpack``, etc.).

The pattern is intentional: import from the stdlib first so static type
checkers and IDEs follow the canonical definition on 3.11+, then fall
back to ``typing_extensions`` on 3.10 where the symbol is not yet in
the stdlib.

References
----------
* Issue: https://github.com/nWave-ai/nWave/issues/43 — ``nwave-ai install``
  failed on Python 3.10 because ``src/des/domain/value_objects.py`` did
  ``from typing import Self`` unconditionally; ``typing.Self`` lands in
  the stdlib only at 3.11 (PEP 673). The repo declares
  ``requires-python = ">=3.10"``, so this module backports the symbol.
* PEP 673 — ``Self`` type, added to stdlib ``typing`` in Python 3.11
"""

try:
    from typing import Self
except ImportError:  # pragma: no cover — only hit on Python 3.10
    from typing_extensions import Self


__all__ = ["Self"]
