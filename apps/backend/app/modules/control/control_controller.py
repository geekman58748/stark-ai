from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.control.dtos.controls_dto import ControlsDto

router = APIRouter(prefix="/v1/controls", tags=["Controls"],
                   responses=ApiResponses.errors("unauthorized"))


@router.get("", response_model=ControlsDto, summary="Whether Stark may pay right now")
def controls(account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.controls.status(account.id))


@router.post("/pause", response_model=ControlsDto, summary="Stop every payment")
def pause(account: AuthUser, module: Module) -> JSONResponse:
    """Takes effect on the next payment, from every channel. Questions still work."""
    return JSONResponse(module.controls.pause(account.id))


@router.post("/resume", response_model=ControlsDto, summary="Let Stark pay again")
def resume(account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.controls.resume(account.id))
