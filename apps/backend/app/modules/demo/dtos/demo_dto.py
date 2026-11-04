from __future__ import annotations

from pydantic import BaseModel

from app.modules.approval.dtos.payment_request_dto import PaymentRequestDto
from app.modules.receipt.dtos.receipt_dto import ReceiptDto
from app.modules.state.dtos.state_dto import StateDto


class DemoLimitsDto(BaseModel):
    monthly_cap_ngn: int
    per_payment_cap_ngn: int


class DemoDto(BaseModel):
    """A made-up account, for the public sample page. Nothing here is real."""

    state: StateDto
    activity: list[ReceiptDto]
    approvals: list[PaymentRequestDto]
    limits: DemoLimitsDto
