from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.channel.dtos.phone_link_code_dto import PhoneLinkCodeDto

router = APIRouter(tags=["SMS"])


@router.post("/v1/sms/link/code", response_model=PhoneLinkCodeDto,
             summary="Mint a code that links a phone number (SMS) to this account",
             responses=ApiResponses.errors("unauthorized", "not_configured"))
def link_code(account: AuthUser, module: Module) -> JSONResponse:
    """Single-use, ten minutes; the user texts `link <code>` to the Stark number."""
    return JSONResponse(module.sms.link_code(account.id))


@router.post("/v1/sms/webhook", response_class=Response,
             summary="Twilio's inbound SMS (Twilio calls this, not the app); answers TwiML",
             responses=ApiResponses.errors("webhook_unconfigured", "webhook_unverified"))
async def webhook(
    request: Request,
    module: Module,
    x_twilio_signature: Optional[str] = Header(default=None),
) -> Response:
    """No bearer token: Twilio cannot carry one. The signature is checked in
    constant time before anything in the form is acted on."""
    raw = await request.body()
    twiml = await run_in_threadpool(
        module.sms.webhook, str(request.url), raw, x_twilio_signature
    )
    return Response(content=twiml, media_type="application/xml")
