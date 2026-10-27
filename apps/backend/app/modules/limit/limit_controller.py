from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.limit.dtos.limits_dto import LimitsDto
from app.modules.limit.dtos.update_limits_dto import UpdateLimitsDto

router = APIRouter(prefix="/v1/limits", tags=["Limits"],
                   responses=ApiResponses.errors("unauthorized"))


@router.get("", response_model=LimitsDto, summary="Spending caps and this month's spend")
def limits(account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.limits.summary(account.id))


@router.patch("", response_model=LimitsDto, summary="Change the caps",
              responses=ApiResponses.errors("bad_limits"))
def update_limits(dto: UpdateLimitsDto, account: AuthUser, module: Module) -> JSONResponse:
    """Takes effect immediately, for the agent as well as REST payments, and is
    stored per account."""
    return JSONResponse(module.limits.update(account.id, dto))
