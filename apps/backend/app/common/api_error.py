"""The one error the API raises on purpose.

Its body is the frozen `{code, message, detail}` shape (`docs/API.md`), and `code`
is what clients branch on. `filters/http_exception_filter.py` turns it into the
response; nothing else should build an error body by hand.
"""

from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str,
                 detail: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail or {}

    @property
    def body(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}
