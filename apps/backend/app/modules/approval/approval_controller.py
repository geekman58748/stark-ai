from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.approval.dtos.payment_request_dto import (
    ApprovedPaymentDto,
    PaymentRequestDto,
)

router = APIRouter(prefix="/v1/approvals", tags=["Approvals"],
                   responses=ApiResponses.errors("unauthorized"))


def _public(request: dict) -> dict:
    return {key: request[key] for key in PaymentRequestDto.model_fields}


@router.get("", response_model=list[PaymentRequestDto],
            summary="Requests over a limit, newest first")
def approvals(account: AuthUser, module: Module) -> JSONResponse:
    """Lapsed requests read `expired`. Only `pending` ones can still be decided."""
    return JSONResponse([_public(r) for r in module.approvals.recent(account.id)])


@router.post("/{request_id}/approve", response_model=ApprovedPaymentDto,
             summary="Pay this one request past the limit it broke",
             responses=ApiResponses.errors(
                 "unknown_request", "request_closed", "paused", "unknown_bill",
                 "insufficient_balance", "vendor_failed",
             ))
def approve(request_id: str, account: AuthUser, module: Module) -> JSONResponse:
    """Only from the signed-in app, never from a chat. If the payment cannot go
    through, nothing is charged and the request stays pending until it expires."""
    approved = module.approvals.approve(account.id, request_id)
    return JSONResponse({"request": _public(approved["request"]),
                         "receipt": approved["receipt"]})


@router.post("/{request_id}/deny", response_model=PaymentRequestDto,
             summary="Refuse it", responses=ApiResponses.errors(
                 "unknown_request", "request_closed"))
def deny(request_id: str, account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(_public(module.approvals.deny(account.id, request_id)))
