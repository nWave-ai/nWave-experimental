"""``CodeFactPort`` driven adapters (OSS tier, ADR-LA-001).

The code-fact provider family behind :class:`des.ports.code_fact_port.CodeFactPort`:

* :class:`~des.adapters.driven.codefact.text_search_code_fact_adapter.TextSearchAdapter`
  — the pure-Python ``re``/``pathlib`` universal floor (``noisy`` confidence,
  always answers on any Python-only target).
* :class:`~des.adapters.driven.codefact.ast_code_fact_adapter.AstAdapter`
  — the per-language structural tier (``approx`` confidence); delegates to the
  sole testarch parser (NO second ``import ast``).
* :class:`~des.adapters.driven.codefact.code_fact_chain.CodeFactChain`
  — the negotiation that walks ``Ast -> TextSearch`` top-down and tags the
  answer.

ADR-LA-001 D6-R1: the paid ``TsunamiAdapter`` precision seam was a fabricated
tier (no production caller ever wired it; a ``binding-resolved`` answer
requires a real ``TransportWitness``, LA1-L7) — deleted, not shipped in OSS.
"""
