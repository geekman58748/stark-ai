from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.channel.dtos.channel_webhook_result_dto import ChannelWebhookResultDto
from app.modules.channel.dtos.phone_link_code_dto import PhoneLinkCodeDto

router = APIRouter(tags=["WhatsApp"])


@router.post("/v1/whatsapp/link/code", response_model=PhoneLinkCodeDto,
             summary="Mint a code that links a WhatsApp number to this account",
             responses=ApiResponses.errors("unauthorized", "not_configured"))
def link_code(account: AuthUser, module: Module) -> JSONResponse:
    """Single-use, ten minutes; the user sends `link <code>` from WhatsApp."""
    return JSONResponse(module.whatsapp.link_code(account.id))


@router.get("/v1/whatsapp/webhook", response_class=PlainTextResponse,
            summary="Meta's subscribe handshake (Meta calls this, not the app)",
            responses=ApiResponses.errors("webhook_unconfigured", "webhook_unverified"))
def handshake(
    module: Module,
    mode: Optional[str] = Query(default=None, alias="hub.mode"),
    token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    return PlainTextResponse(module.whatsapp.handshake(mode, token, challenge))


@router.post("/v1/whatsapp/webhook", response_model=ChannelWebhookResultDto,
             summary="Meta's message push (Meta calls this, not the app)",
             responses=ApiResponses.errors("webhook_unconfigured", "webhook_unverified",
                                           "bad_update"))
async def webhook(
    request: Request,
    module: Module,
    x_hub_signature_256: Optional[str] = Header(default=None),
) -> JSONResponse:
    """No bearer token: Meta cannot carry one. The HMAC of the raw body is checked
    in constant time **before** it is parsed."""
    raw = await request.body()
    return JSONResponse(await run_in_threadpool(
        module.whatsapp.webhook, raw, x_hub_signature_256
    ))
