from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.app_module import AppModule


def _module(request: Request) -> AppModule:
    return request.app.state.module


Module = Annotated[AppModule, Depends(_module)]
