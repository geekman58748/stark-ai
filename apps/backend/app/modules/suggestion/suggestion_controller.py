from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.suggestion.dtos.suggestion_dto import SuggestionDto

router = APIRouter(tags=["Suggestions"], responses=ApiResponses.errors("unauthorized"))


@router.get("/v1/suggestions", response_model=list[SuggestionDto],
            summary="What Stark noticed")
def suggestions(account: AuthUser, module: Module) -> JSONResponse:
    """Computed from state the server holds, worst news first, at most 4. An empty
    list is a normal answer."""
    return JSONResponse(module.suggestions.suggestions(account.id))
