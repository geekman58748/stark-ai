from __future__ import annotations

from enum import Enum


class BillKind(str, Enum):
    ELECTRICITY = "electricity"
    AIRTIME = "airtime"
    DATA = "data"
    TV = "tv"
    INTERNET = "internet"
    WATER = "water"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(kind.value for kind in cls)


# Sold as a plan (a vendor variation code), not as a free amount.
PLAN_KINDS = (BillKind.DATA.value, BillKind.TV.value)
