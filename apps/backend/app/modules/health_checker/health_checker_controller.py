from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.decorators.inject_module import Module

router = APIRouter(tags=["Health"])


@router.get("/", summary="Service, version and every route")
def index(request: Request, module: Module) -> JSONResponse:
    routes = sorted(
        f"{method} {route.path}"
        for route in request.app.routes if isinstance(route, APIRoute)
        for method in route.methods
    )
    return JSONResponse({"service": "stark-api", "version": module.config.version,
                         "stub": True, "routes": routes})


@router.get("/health", summary="Liveness")
def health(module: Module) -> JSONResponse:
    return JSONResponse({"status": "ok", "stub": True, "version": module.config.version})
