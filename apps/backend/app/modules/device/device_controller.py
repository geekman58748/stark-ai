from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.device.dtos.device_dto import DeviceDto
from app.modules.device.dtos.switch_device_dto import SwitchDeviceDto, SwitchedDeviceDto

router = APIRouter(tags=["Devices"], responses=ApiResponses.errors("unauthorized"))


@router.get("/v1/devices", response_model=list[DeviceDto],
            summary="List switchable devices")
def list_devices(account: AuthUser, module: Module) -> JSONResponse:
    """What the agent may switch, by id. Seeded with the living room TV."""
    return JSONResponse(module.devices.devices(account.id))


@router.post("/v1/devices/{device_id}/switch", response_model=SwitchedDeviceDto,
             summary="Switch a device on or off",
             responses=ApiResponses.errors("unknown_device", "device_unreachable"))
def switch_device(device_id: str, dto: SwitchDeviceDto, account: AuthUser,
                  module: Module) -> JSONResponse:
    """The address of the plug never comes from the client, only from env.

    `confirmed: true` means a status read followed the command. A plug that does
    not answer is `503 device_unreachable`, and the reply says the device did not
    change — a named device that did not respond is not an error to paper over.
    """
    return JSONResponse(module.devices.switch(account.id, device_id, dto.on))
