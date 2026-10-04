"""Every independent defect of one closed input, refused together.

A closed-input decoder that stops at its first defect makes a producer with two
independent mistakes submit twice.  Decoders instead record each defect of an
independent field or list item and refuse once, naming all of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")


class InputDefects(ValueError):
    """One refused closed input: each defect names its field and its rule."""

    def __init__(self, *defects: str) -> None:
        self.defects: tuple[str, ...] = defects
        super().__init__(
            defects[0]
            if len(defects) == 1
            else f"{len(defects)} independent defects: "
            + "; ".join(
                f"{position}. {defect}"
                for position, defect in enumerate(defects, start=1)
            )
        )

    def how(self, fix: str) -> str:
        """The HOW of a refusal: one defect keeps ``fix``; several ask for all."""
        if len(self.defects) < 2:
            return fix
        return (
            "fix every numbered defect in WHY, then resubmit the whole input "
            f"once; {fix}"
        )


class Defects:
    """Collects the independent defects of one input, then refuses once."""

    def __init__(self, error_type: type[InputDefects]) -> None:
        self._error_type = error_type
        self._defects: list[str] = []

    def take(self, decode: Callable[[], T]) -> T | None:
        """``decode()``'s value, or ``None`` after recording its defects."""
        try:
            return decode()
        except InputDefects as error:
            for defect in error.defects:
                self.add(defect)
            return None

    def add(self, defect: str) -> None:
        self._defects.append(defect)

    def close(self) -> None:
        """Refuse with every recorded defect; return when there is none."""
        if self._defects:
            raise self._error_type(*self._defects)
