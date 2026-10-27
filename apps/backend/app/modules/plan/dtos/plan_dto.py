from __future__ import annotations

from pydantic import BaseModel, Field


class PlanDto(BaseModel):
    kind: str = Field(examples=["data"])
    provider: str = Field(examples=["mtn-data"])
    service_name: str = Field(examples=["MTN Data"])
    plan: str = Field(examples=["mtn-100mb-1000"])
    label: str = Field(description="The vendor's own string; render it as-is.",
                       examples=["N1000 1.5GB - 30 days"])
    price_ngn: int = Field(examples=[1000])
