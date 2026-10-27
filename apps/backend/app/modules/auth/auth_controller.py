from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.auth.dtos.logged_out_dto import LoggedOutDto

router = APIRouter(tags=["Auth"], responses=ApiResponses.errors("unauthorized"))


@router.post("/v1/auth/logout", response_model=LoggedOutDto, summary="End this session")
def logout(account: AuthUser, module: Module) -> JSONResponse:
    """Deletes the provider's session row, so the token stops working everywhere —
    not just in the browser that forgot it."""
    module.auth.logout(account.token)
    return JSONResponse({"logged_out": True})
