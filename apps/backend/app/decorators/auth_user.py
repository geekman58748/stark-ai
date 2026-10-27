from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.guards.auth_guard import AuthGuard
from app.modules.account.account import Account

# The instance is the dependency key: a test overrides exactly this one.
auth_guard = AuthGuard()

AuthUser = Annotated[Account, Depends(auth_guard)]
