from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.inject_module import Module
from app.modules.demo.dtos.demo_dto import DemoDto

router = APIRouter(tags=["Demo"])


@router.get("/v1/demo", response_model=DemoDto, summary="A sample account, no sign-in")
def demo(module: Module) -> JSONResponse:
    """Read-only and made up: no account, no database, nothing can be paid from it."""
    return JSONResponse(module.demo.snapshot())
