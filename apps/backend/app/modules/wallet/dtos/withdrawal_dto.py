from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.common.dto.contract_field import ContractField


class BankAccountDto(BaseModel):
    bank_code: str = Field(examples=["058"])
    account_number: str = Field(examples=["0123456789"])

    @field_validator("bank_code", "account_number", mode="before")
    @classmethod
    def text(cls, value: Any) -> str:
        return ContractField.text(value)


class WithdrawDto(BankAccountDto):
    amount_ngn: int = Field(default=0, examples=[10000])

    @field_validator("amount_ngn", mode="before")
    @classmethod
    def amount(cls, value: Any) -> int:
        return ContractField.integer(value, "bad_amount", "amount_ngn must be an integer")


class CryptoWithdrawDto(BaseModel):
    amount_ngn: int = Field(default=0, examples=[20000],
                            description="Integer naira, taken from the balance.")
    asset_id: str = Field(
        examples=["nep141:tron-d28a265909efecdcee7c5028585214ea0b96f015.omft.near"],
        description="What to receive: an `asset_id` from GET /v1/wallet/crypto-assets.",
    )
    address: str = Field(examples=["TXYZ..."],
                         description="The user's address on that asset's chain.")

    @field_validator("amount_ngn", mode="before")
    @classmethod
    def amount(cls, value: Any) -> int:
        return ContractField.integer(value, "bad_amount", "amount_ngn must be an integer")

    @field_validator("asset_id", "address", mode="before")
    @classmethod
    def text(cls, value: Any) -> str:
        return ContractField.text(value)


class ResolvedAccountDto(BaseModel):
    account_name: str
    account_number: str
    bank_code: str


class BankDto(BaseModel):
    name: str
    code: str


class CryptoPayoutDto(BaseModel):
    asset: str
    chain: str
    address: str
    amount: str = Field(description="What arrives, as a decimal: quoted, then settled.")
    tx_hash: Optional[str] = Field(description="The treasury's transfer on NEAR, once signed.")


class WithdrawalDto(BaseModel):
    id: str
    method: Literal["bank", "crypto"]
    amount_ngn: int
    status: Literal["reviewing", "sending", "processing", "paid", "returned"]
    note: Optional[str] = Field(description="Why it was returned, when it was.")
    crypto: Optional[CryptoPayoutDto] = Field(description="Set for a crypto withdrawal.")
    created_at: str
    updated_at: str
