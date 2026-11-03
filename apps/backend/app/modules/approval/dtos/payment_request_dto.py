from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.modules.receipt.dtos.receipt_dto import ReceiptDto


class PaymentRequestDto(BaseModel):
    """A payment Stark may not make alone, waiting for the owner."""

    id: str = Field(examples=["req_3f9a1c2b4d"])
    bill_id: str = Field(examples=["bill_home_meter"])
    bill_label: str = Field(examples=["Home electricity"])
    amount_ngn: int = Field(examples=[15000])
    reason: str = Field(description="The limit it broke: over_per_payment_cap | over_cap",
                        examples=["over_per_payment_cap"])
    status: str = Field(description="pending | approved | denied | expired",
                        examples=["pending"])
    created_at: str = Field(examples=["2026-11-03T09:12:00Z"])
    expires_at: str = Field(description="After this it pays nothing.",
                            examples=["2026-11-03T10:12:00Z"])
    decided_at: Optional[str] = Field(examples=[None])
    receipt_id: Optional[str] = Field(description="The payment an approval became.",
                                      examples=[None])


class ApprovedPaymentDto(BaseModel):
    request: PaymentRequestDto
    receipt: ReceiptDto
