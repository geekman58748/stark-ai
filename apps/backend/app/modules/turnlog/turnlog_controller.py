from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.common.api_error import ApiError
from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.modules.turnlog import turnlog
from app.modules.turnlog.dtos.turn_log_dto import TurnLogDto

router = APIRouter(tags=["Debug"], responses=ApiResponses.errors("unauthorized"))


@router.get("/v1/turnlog", response_model=TurnLogDto, summary="Read the conversation log",
            responses=ApiResponses.errors("turnlog_off"))
def read(
    _account: AuthUser,
    limit: str = Query("100", description="Newest N entries; 0 for the whole file. "
                                          "Not a number falls back to 100."),
) -> JSONResponse:
    """Debug route, not part of the product contract. 404 while `STARK_TURN_LOG` is
    off, so a box that was not asked to log does not claim to have a log. The log
    holds what people said: treat it as user data."""
    if not turnlog.enabled():
        raise ApiError(404, "turnlog_off", "The turn log is off. Set STARK_TURN_LOG.")
    try:
        newest = int(limit.strip())
    except ValueError:
        newest = 100
    entries = turnlog.lines()
    if newest > 0:
        entries = entries[-newest:]
    return JSONResponse({"enabled": True, "count": len(entries), "entries": entries})
