from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.state.dtos.state_dto import StateDto

router = APIRouter(tags=["State"], responses=ApiResponses.errors("unauthorized"))


@router.get("/v1/state", response_model=StateDto, summary="Everything the dashboard needs")
def state(account: AuthUser, module: Module) -> JSONResponse:
    """One call. Refetch after any payment."""
    return JSONResponse(module.state.snapshot(account.id))
