from __future__ import annotations

from pydantic import BaseModel

from app.modules.receipt.dtos.receipt_dto import ReceiptDto
from app.modules.wallet.dtos.wallet_dto import WalletDto


class WalletEntryDto(BaseModel):
    wallet: WalletDto
    entry: ReceiptDto
