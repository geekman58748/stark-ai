from __future__ import annotations


class ChannelError(Exception):
    """A webhook refusal, for the service to turn into an `ApiError`."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
