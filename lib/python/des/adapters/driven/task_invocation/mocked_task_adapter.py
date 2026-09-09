"""In-repository test double for :class:`TaskInvocationPort` (ADR 13d.7).

The double follows the evolved port signature and returns :class:`ModelRun`, or
the port would have two shapes and a passing test would be evidence about the
double rather than about the product.  In particular it can return the SAME
typed shape a failing production run returns -- a non-zero exit status and its
provider-neutral retry fact -- and never a shape production could not produce.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from des.ports.driven_ports.task_invocation_port import (
    ModelOutcome,
    ModelRun,
    ProductValue,
    TaskInvocationPort,
)


class MockedTaskAdapter(TaskInvocationPort):
    """Return scripted :class:`ModelRun` values without spawning anything."""

    def __init__(
        self,
        predefined_result: ModelRun | None = None,
        results_queue: list[ModelRun] | None = None,
    ) -> None:
        """Script a single result for every turn, or a queue consumed in order."""
        self.predefined_result = predefined_result
        self._queue: deque[ModelRun] = deque(results_queue or ())
        self.invocation_count = 0
        #: Every ``(role_id, prompt, cwd, max_product_values, defect_values)``
        #: this double was asked to run, so a test can observe WHAT was
        #: requested -- the replacement window and the values a review may
        #: charge a defect to -- and not only what was returned.
        self.invocations: list[tuple[str, str, Path, int | None, tuple[str, ...]]] = []

    @property
    def results_queue(self) -> list[ModelRun]:
        """The results still to be returned, in order."""
        return list(self._queue)

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        """Return the next scripted run, recording the request that asked for it."""
        self.invocation_count += 1
        self.invocations.append(
            (role_id, prompt, Path(cwd), max_product_values, defect_values)
        )
        if self._queue:
            return self._queue.popleft()
        if self.predefined_result is not None:
            return self.predefined_result
        values = ()
        if role_id == "nw-product-owner":
            request = prompt.partition("request: ")[2].splitlines()[0]
            try:
                import json

                observation = json.loads(request)
            except (json.JSONDecodeError, TypeError):
                observation = request
            values = (ProductValue(str(observation)),)

        return ModelRun(
            outcome=ModelOutcome.Accepted,
            diagnostic="",
            exit_status=0,
            retry_safe=False,
            product_values=values,
        )
