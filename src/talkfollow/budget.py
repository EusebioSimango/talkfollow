"""A SerpApi client wrapper that caps how many credits one run can spend."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Protocol


class SearchClient(Protocol):
    def search(self, params: dict[str, Any]) -> Mapping[str, Any] | str: ...


class SearchFailed(RuntimeError):
    """A search failed; ``str(exc)`` is safe to show and never contains the API key."""


class BudgetExceeded(SearchFailed):
    """Raised instead of sending a request that would go over the credit budget."""


class BudgetedClient:
    """Counts SerpApi calls and refuses any beyond ``max_calls``. Safe across threads."""

    def __init__(self, inner: SearchClient, max_calls: int) -> None:
        self._inner = inner
        self._max_calls = max_calls
        self._engines_called: list[str] = []
        self._lock = threading.Lock()

    @property
    def engines_called(self) -> list[str]:
        with self._lock:
            return list(self._engines_called)

    def search(self, params: dict[str, Any]) -> Mapping[str, Any] | str:
        with self._lock:
            if len(self._engines_called) >= self._max_calls:
                raise BudgetExceeded(
                    f"Skipped: the budget of {self._max_calls} SerpApi searches per run is used up."
                )
            self._engines_called.append(str(params.get("engine", "unknown")))
        try:
            return self._inner.search(params)
        except Exception as exc:
            raise SearchFailed(safe_error_message(exc)) from exc


def safe_error_message(exc: BaseException) -> str:
    # serpapi.HTTPError carries SerpApi's own message. Its str() includes the request URL,
    # which holds the API key, so it must never be shown.
    message = getattr(exc, "error", None)
    status = getattr(exc, "status_code", None)
    if message and status and status > 0:
        return f"SerpApi error {status}: {message}"
    if message:
        return f"SerpApi error: {message}"
    return f"SerpApi request failed ({type(exc).__name__})."
