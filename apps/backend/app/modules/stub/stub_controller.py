from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module

router = APIRouter(tags=["Stub"])


# Not in the schema: it is a test seam, and off (404) unless STARK_STUB_RESET=1.
@router.post("/v1/_stub/reset", include_in_schema=False)
def reset(account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.stub.reset(account.id))
