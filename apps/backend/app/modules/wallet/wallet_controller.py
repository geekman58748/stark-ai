from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.wallet.dtos.top_up_dto import TopUpDto
from app.modules.wallet.dtos.wallet_dto import WalletDto
from app.modules.wallet.dtos.wallet_entry_dto import WalletEntryDto

router = APIRouter(prefix="/v1/wallet", tags=["Wallet"],
                   responses=ApiResponses.errors("unauthorized"))


@router.get("", response_model=WalletDto, summary="Balance and this month's spend")
def wallet(account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.wallet.summary(account.id))


@router.post("/topup", status_code=201, response_model=WalletEntryDto,
             summary="Add test money", responses=ApiResponses.errors("bad_amount"))
def top_up(dto: TopUpDto, account: AuthUser, module: Module) -> JSONResponse:
    """Nothing is collected: there is no payment provider yet. A repeated
    `request_id` returns **200** with the original entry and credits nothing."""
    status, payload = module.wallet.top_up(account.id, dto)
    return JSONResponse(payload, status_code=status)


@router.post("/withdraw", summary="Not available yet",
             responses=ApiResponses.errors("not_available"))
def withdraw(_account: AuthUser, module: Module) -> None:
    """Always **501** `not_available`, and takes nothing, until a payout provider exists."""
    module.wallet.withdraw()
