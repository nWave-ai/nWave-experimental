"""Language-agnostic AT-mandate rules (ADR-TEST-002 D-A).

slice-01 (created by DISTILL, implemented by DELIVER). Each rule is authored
ONCE over the abstract capabilities the ``TestSuiteAstAdapter`` port exposes —
it MUST NOT ``import ast`` or name any concrete parser API. The Python ``ast``
walk lives entirely in ``des.testarch.adapters.python_ast``.
"""

__SCAFFOLD__ = False
