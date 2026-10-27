from __future__ import annotations

from pydantic import BaseModel


class LoggedOutDto(BaseModel):
    logged_out: bool = True
