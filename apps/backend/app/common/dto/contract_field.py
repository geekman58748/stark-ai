"""Field coercion for request DTOs that fails with the contract's own error codes.

The contract promises specific codes for bad input (`bad_amount`, `bad_limits`,
`bad_watts`, …), and clients branch on them, so a DTO cannot answer with
pydantic's generic `int_parsing`. These run as `mode="before"` validators: they
accept exactly what the API has always accepted (a number, or a string of one) and
raise a `PydanticCustomError` carrying the contract code, which
`filters/http_exception_filter.py` turns into the `{code, message, detail}` body.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic_core import PydanticCustomError

# Marks an error as one of ours, so the filter knows its `type` is a contract code.
CONTRACT = "contract"


class ContractField:
    @staticmethod
    def fail(code: str, message: str) -> PydanticCustomError:
        return PydanticCustomError(code, message, {CONTRACT: True})

    @staticmethod
    def integer(value: Any, code: str, message: str) -> int:
        if isinstance(value, bool):
            raise ContractField.fail(code, message)
        try:
            return int(str(value).strip())
        except ValueError:
            raise ContractField.fail(code, message) from None

    @staticmethod
    def optional_integer(value: Any, code: str, message: str) -> Optional[int]:
        """`None` and `""` mean "not sent", which `PATCH` bodies rely on."""
        if value is None or value == "":
            return None
        return ContractField.integer(value, code, message)

    @staticmethod
    def number(value: Any, code: str, message: str) -> float:
        if isinstance(value, bool):
            raise ContractField.fail(code, message)
        try:
            return float(str(value).strip())
        except ValueError:
            raise ContractField.fail(code, message) from None

    @staticmethod
    def text(value: Any) -> str:
        """A scalar as text: a meter number sent as a JSON number is still a meter."""
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            raise ContractField.fail("bad_request", "Expected text, got an object.")
        return str(value)
