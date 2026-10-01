"""Sorted, de-duplicated set of berth codes known to the harbour."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable

MAX_CODE_LENGTH = 16


class Catalog:
    """Immutable-ish catalog; membership checks stay O(log n)."""

    def __init__(self, codes: Iterable[str] = ()) -> None:
        normalized = {
            code.strip()
            for code in codes
            if code and len(code.strip()) <= MAX_CODE_LENGTH
        }
        self._codes: tuple[str, ...] = tuple(sorted(normalized))

    def has(self, code: str) -> bool:
        needle = code.strip()
        index = bisect_left(self._codes, needle)
        return index < len(self._codes) and self._codes[index] == needle

    def codes(self) -> list[str]:
        return list(self._codes)

    def count(self) -> int:
        return len(self._codes)

    def first_available(self, is_available) -> str | None:
        """Return the first code for which ``is_available`` is true."""

        for code in self._codes:
            if is_available(code):
                return code
        return None
