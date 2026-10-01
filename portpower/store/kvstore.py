"""A tiny JSON document store where one key maps to one file."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SUFFIX = ".json"
_FORBIDDEN = ("/", "\\", "..", "\x00")


class StoreKeyError(KeyError):
    """Raised when a key is not usable as a file name."""


def encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def decode(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def validate_key(key: str) -> str:
    trimmed = key.strip()
    if not trimmed:
        raise StoreKeyError("store key is empty")
    for fragment in _FORBIDDEN:
        if fragment in trimmed:
            raise StoreKeyError(f"store key contains {fragment!r}: {key!r}")
    return trimmed


class RecordStore:
    """Thread-safe key/value store persisted as ``<key>.json`` files."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self._dir = Path(directory)
        self._data: dict[str, bytes] = {}
        self._lock = threading.RLock()

    def load(self) -> None:
        """Read every ``*.json`` file already present in the directory."""

        self._dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._data.clear()
            for path in sorted(self._dir.glob(f"*{_SUFFIX}")):
                if not path.is_file():
                    continue
                key = path.name[: -len(_SUFFIX)]
                self._data[key] = path.read_bytes()

    def put(self, key: str, payload: bytes) -> None:
        name = validate_key(key)
        with self._lock:
            self._write(name, payload)

    def put_json(self, key: str, value: Any) -> None:
        self.put(key, encode(value))

    def get(self, key: str) -> bytes | None:
        with self._lock:
            return self._data.get(key)

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return decode(raw)
        except ValueError:
            return None

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def delete(self, key: str) -> None:
        name = validate_key(key)
        with self._lock:
            self._data.pop(name, None)
            path = self._path_for(name)
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def update_json(
        self,
        key: str,
        mutator: Callable[[Any], tuple[Any, Any]],
    ) -> Any:
        """Atomically read-modify-write a JSON document.

        ``mutator`` receives the current document (or ``None``) and returns a
        ``(new_document, result)`` pair. The new document is only written when
        the mutator asks for a change by returning something other than ``None``.
        """

        name = validate_key(key)
        with self._lock:
            current_raw = self._data.get(name)
            current: Any = None
            if current_raw is not None:
                try:
                    current = decode(current_raw)
                except ValueError:
                    current = None
            new_document, result = mutator(current)
            if new_document is not None:
                self._write(name, encode(new_document))
            return result

    def _path_for(self, key: str) -> Path:
        return self._dir / f"{key}{_SUFFIX}"

    def _write(self, key: str, payload: bytes) -> None:
        path = self._path_for(key)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(payload)
        os.replace(tmp, path)
        self._data[key] = payload

    @contextmanager
    def transaction(self) -> Iterator[dict[str, bytes]]:
        """Hold the write lock while callers walk the in-memory snapshot."""

        with self._lock:
            yield self._data
