"""AT-mandate mechanical-enforcement architecture (ADR-TEST-002).

slice-01 (created by DISTILL, implemented by DELIVER) of
``at-mandate-mechanical-enforcement``. Houses the rule/mechanism split:

  * ``ports.py``            — the ``TestSuiteAstAdapter`` driven port (Protocol)
  * ``capabilities.py``     — the adapter-capability-registry SSOT (skeleton)
  * ``adapters/python_ast`` — the reference Python stdlib-``ast`` adapter
  * ``rules/``              — language-agnostic rules over the port (no ``ast``)

The rule layer dispatches through the port and names abstract node-kinds only;
it never imports ``ast`` (genericità, ADR-TEST-002 D-A). Only
``adapters/python_ast.py`` is permitted to ``import ast``.
"""

__SCAFFOLD__ = False
