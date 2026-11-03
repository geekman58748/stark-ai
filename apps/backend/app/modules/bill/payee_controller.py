from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.bill.dtos.payee_dto import PayeeDto

router = APIRouter(tags=["Bills"], responses=ApiResponses.errors("unauthorized"))


@router.get("/v1/payees", response_model=list[PayeeDto],
            summary="Where Stark may pay, and what each has been paid")
def payees(account: AuthUser, module: Module) -> JSONResponse:
    """One row per saved bill, in the order they were added. Stark can pay nowhere else."""
    return JSONResponse(module.bills.payees(account.id))
