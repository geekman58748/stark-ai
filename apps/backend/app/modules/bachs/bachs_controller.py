from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.inject_module import Module

router = APIRouter(tags=["Bachs"])


@router.post(
    "/v1/bachs/webhook",
    summary="Bachs's event push (Bachs calls this, not the app)",
    responses=ApiResponses.errors(
        "webhook_unconfigured", "webhook_unverified", "bad_update"
    ),
)
async def webhook(request: Request, module: Module) -> JSONResponse:
    """No bearer token: the `X-Bachs-Signature-V2` HMAC is checked on the raw body
    before it is parsed. Every event is refused while `BACHS_WEBHOOK_SECRET` is unset.
    """
    raw = await request.body()
    return JSONResponse(
        await run_in_threadpool(module.bachs_webhooks.handle, raw, request.headers)
    )
