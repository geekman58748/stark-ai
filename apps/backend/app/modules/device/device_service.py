"""The device registry, and the one write it allows: switch a socket.

A device is named, never guessed: the agent picks a `device_id` out of the
registry the same way it picks a `bill_id`, and an unknown one is a refusal
(`unknown_device`), not a silent fallback to whatever is first. The id is the
same `device_id` the plug posts telemetry under, so the meter reading and the
switch are provably the same object.

The registry is in memory, seeded per account, exactly like bills and limits
(`docs/HANDOFF.md` §9 records those as not-yet-durable). Nothing here persists a
plug address or a token: those come from `STARK_TV_PLUG_URL` and
`STARK_TV_PLUG_TOKEN`, and never from a client.
"""

from __future__ import annotations

from typing import Any, Optional

from app.common.api_error import ApiError
from app.modules.device.devices import DeviceUnreachable, SwitchResult

# The same id the plug posts `/v1/telemetry` under, so switch and meter are one
# object. One device is seeded because one is what the demo has.
SEEDED_TV = {"id": "tv-plug-1", "label": "Living room TV", "kind": "tv",
             "last_status": None}

# Below this the socket may be live but the set is asleep: webOS (and most sets)
# sit at a fraction of a watt in standby and at tens of watts with the screen on.
STANDBY_WATTS = 5.0


def _status(result: SwitchResult) -> str:
    if not result.output:
        return "off"
    if result.watts is None:
        # The socket is live; whether the screen woke is not knowable from here.
        return "on"
    return "on" if result.watts >= STANDBY_WATTS else "standby"


class DeviceService:
    def __init__(self, plug: Optional[Any] = None) -> None:
        from app.modules.device import devices as device_layer

        self.plug = plug or device_layer.plug_from_env()
        self._registry: dict[str, dict[str, dict[str, Any]]] = {}

    def devices(self, account_id: str) -> list[dict[str, Any]]:
        """What the account can switch, for `GET /v1/devices` and the agent.

        `last_status` is the last state this service observed, not a live read:
        null means nobody has switched it yet, and the agent says that rather
        than offering a guess as a reading.
        """
        return [dict(device) for device in self._for(account_id).values()]

    def get(self, account_id: str, device_id: str) -> dict[str, Any]:
        device = self._for(account_id).get(device_id)
        if device is None:
            raise ApiError(404, "unknown_device", f"No device {device_id}")
        return device

    def switch(self, account_id: str, device_id: str, on: bool) -> dict[str, Any]:
        """Flip one socket and report only what the device read back."""
        device = self.get(account_id, device_id)
        try:
            result = self.plug.set(on)
        except DeviceUnreachable as error:
            # Nothing moved as far as we know, so nothing is claimed. The spoken
            # reply says the plug did not answer; there is no receipt and no money.
            raise ApiError(
                503,
                "device_unreachable",
                f"The {device['label']} didn't answer, so I can't confirm it "
                f"changed.",
                {"device_id": device_id, "reason": str(error)[:200]},
            ) from error
        status = _status(result)
        # Remember it for the snapshot, so "is the TV on?" can be answered from
        # the last real read instead of a new switch.
        device["last_status"] = status if result.read_back else device["last_status"]
        return {
            "device_id": device["id"],
            "label": device["label"],
            "kind": device["kind"],
            "on": result.output,
            "confirmed": result.read_back,
            "watts": result.watts,
            "status": status,
            "simulated": result.simulated,
        }

    def _for(self, account_id: str) -> dict[str, dict[str, Any]]:
        return self._registry.setdefault(account_id, {SEEDED_TV["id"]: dict(SEEDED_TV)})
