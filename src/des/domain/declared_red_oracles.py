"""The ONE definition of "this RED was declared by a delivery contract".

WHY THIS MODULE EXISTS (defect D-EXPECTED-RED-PER-GATE-PATCH, 2026-08-23)
------------------------------------------------------------------------
On the ``atdd_pure`` spine a ``RED_TO_GREEN`` contract's acceptance oracle is
authored BEFORE the code it verifies, so at the moment it is committed the
module under test does not exist and pytest cannot even COLLECT the file. Every
consumer that collects the tree therefore scores the mainline DISTILL commit as
a failure. The population is not one gate, it is three, measured 2026-08-23:

* ``pytest-touched-files``  (``scripts/hooks/pytest_touched_files.py``)
* ``pytest-fast-gate``      (``.pre-commit-config.yaml``, ``pytest -m fast_gate``,
  whole-tree collection)
* ``pytest-quick-tiers`` and CI, which collect the tree for the same reason.

The first occurrence was repaired inside the touched-file gate alone. The
SECOND occurrence (pytest-fast-gate, same commit, same oracle) is what proves
the repair belonged at the shared point instead: a third per-gate patch would
have been a third copy of the discrimination, and the copies would drift. So
the discrimination lives here, ONCE, and the consumers import it:

* ``tests/conftest.py`` translates a contract-declared collection ERROR into a
  SKIP at ``pytest_make_collect_report`` -- which covers EVERY pytest-driven
  consumer, present and future, because they all load the root conftest.
* ``scripts/hooks/pytest_touched_files.py`` re-exports these functions for its
  own operator-facing EXPECTED-RED report, and adds no second rule of its own.

THE DISCRIMINATION -- a DECLARED property, never a convention
-------------------------------------------------------------
"Skip any test that fails to import" would be a sieve, strictly worse than the
defect it replaces. There is no filename convention here, no marker in the
test, and no hand-kept allow-list. The declaration lives in the delivery
contract -- the artefact that already states the route, the oracle and the
targets -- and all THREE conjuncts must hold:

1. the file is the ``acceptance-tests.locator`` of a contract under
   ``docs/delivery-contracts/`` whose ``delivery-route`` is ``RED_TO_GREEN``;
2. that contract is still OPEN -- at least one declared ``target`` is absent
   from disk. Every target present means the work landed, the oracle owes
   GREEN, and no exemption exists for it;
3. the observed collection error is a ``ModuleNotFoundError`` naming ONLY
   modules that ARE those absent declared targets. The reason is CHECKED
   against the contract, never assumed from the failure's shape.

Every state this module cannot settle returns ``None``, which means "run it /
keep blocking". An unknown always degrades into the blocking path (GDP-6).

DECLARED LIMITS, left fail-closed (GDP-10: no incident, no mechanism)
---------------------------------------------------------------------
* the missing module is matched EXACTLY. If a whole absent package makes pytest
  report the ANCESTOR (``des.cli`` rather than ``des.cli.update``), no
  exemption is granted and the commit blocks.
* only ``ModuleNotFoundError`` is covered. An oracle whose declared target
  EXISTS but does not yet export the symbol the oracle imports raises
  ``ImportError: cannot import name`` and still blocks -- widening to that case
  would mask a real regression deleting a symbol from an EXTEND target.

See also ``des.domain.oracle_execution_classifier``, which answers a DIFFERENT
question (is a running command's nonzero exit the contract's missing-feature
reason?) with a deliberately looser, language-agnostic token match. This module
answers only the collection question, and answers it strictly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


#: The declaration surface. A directory of contracts -- not a naming rule.
DELIVERY_CONTRACTS_DIR = "docs/delivery-contracts"

#: The only route that authors an oracle ahead of the code it verifies.
RED_TO_GREEN = "RED_TO_GREEN"

_MISSING_MODULE_RE = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


def module_names(rel_path: str) -> set[str]:
    """Dotted module spellings a Python file could be imported as.

    ``__init__.py`` yields nothing: its package name (``des``) is so coarse it
    matches every test file, which is how a first attempt at the touched-file
    selector silently degenerated into a full-suite run. This repo's
    ``pyproject.toml`` sets ``pythonpath = ["src", "."]``, so a file under
    ``src/`` is importable BOTH ways and a real ``ModuleNotFoundError`` may
    name either spelling.
    """
    if not rel_path.endswith(".py"):
        return set()
    parts = rel_path[:-3].split("/")
    if parts[-1] == "__init__":
        return set()
    names = {".".join(parts)}
    if parts[0] == "src":
        names.add(".".join(parts[1:]))
    return {name for name in names if name.count(".") >= 1}


def declared_red_oracles(root: Path) -> dict[str, tuple[str, set[str]]]:
    """``locator -> (delivery-id, modules of declared targets ABSENT on disk)``.

    Conjuncts 1 and 2. Only OPEN ``RED_TO_GREEN`` contracts appear: a contract
    whose every declared target already exists on disk has landed, so its
    oracle owes GREEN and is entitled to no exemption at all. A locator claimed
    by two contracts keeps the union of both absent-target module sets, because
    either contract's RED is a declared one.
    """
    declared: dict[str, tuple[str, set[str]]] = {}
    contracts_dir = Path(root) / DELIVERY_CONTRACTS_DIR
    if not contracts_dir.is_dir():
        return declared

    for path in sorted(contracts_dir.glob("*.json")):
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # An unreadable contract declares nothing. Fail CLOSED: its oracle
            # simply keeps the normal blocking behaviour.
            continue
        if not isinstance(contract, dict):
            continue
        if contract.get("delivery-route") != RED_TO_GREEN:
            continue

        acceptance = contract.get("acceptance-tests")
        locator = acceptance.get("locator") if isinstance(acceptance, dict) else None
        targets = contract.get("targets")
        if not isinstance(locator, str) or not locator or not isinstance(targets, dict):
            continue

        absent: set[str] = set()
        for target in targets:
            rel_target = str(target).replace("\\", "/")
            if not (Path(root) / rel_target).exists():
                absent |= module_names(rel_target)
        if not absent:
            continue

        locator = locator.replace("\\", "/")
        delivery_id = str(contract.get("delivery-id") or path.stem)
        previous = declared.get(locator)
        if previous is None:
            declared[locator] = (delivery_id, absent)
        else:
            declared[locator] = (f"{previous[0]}+{delivery_id}", previous[1] | absent)
    return declared


def expected_red_reason(
    rel_path: str,
    collection_error: str,
    declared: dict[str, tuple[str, set[str]]],
) -> str | None:
    """The declared reason this file does not collect, or ``None``.

    ``None`` means "no declaration covers this" -- the caller keeps its normal
    blocking behaviour. Conjunct 3 lives here: ``collection_error`` is the text
    the tool ACTUALLY produced (pytest's own collect-report ``longrepr``, or a
    ``--collect-only`` transcript), never a guess about what it would say.
    """
    entry = declared.get(rel_path)
    if entry is None:
        return None  # not a declared oracle of an open RED_TO_GREEN contract

    delivery_id, absent_modules = entry
    reported = set(_MISSING_MODULE_RE.findall(collection_error))
    if not reported:
        return None  # a SyntaxError or any other collection error: not declared
    if any(module not in absent_modules for module in reported):
        return None  # red for a module NO contract declares absent

    return (
        f"declared oracle of contract {delivery_id} (delivery-route "
        f"{RED_TO_GREEN}); it does not collect solely because "
        f"{', '.join(sorted(reported))} is a declared target still absent from "
        f"disk. The oracle precedes its implementation by design -- this RED is "
        f"the contract's, not a regression."
    )
