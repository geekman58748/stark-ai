"""The relay behind a device: the TV itself, a Shelly plug, or a simulation.

This is the only place that touches hardware, and it is deliberately tiny: a
plug is a switch with a power reading, nothing more. `docs/HANDOFF.md` §8B makes
the honesty rule explicit — a 200 from the plug proves the *socket* is live, not
that the TV is awake — so every result carries `output`, the `watts` read back
and whether that read-back actually happened (`read_back`).

`STARK_TV_PLUG_URL` unset means a simulated plug: the registry still lists a
device, the endpoint still answers, and the agent still runs the whole path, so
everything is exercised without hardware. The reply says it was simulated; a
simulation must never be spoken as a real socket moving.

Three real paths exist, chosen by env in `plug_from_env`:

  * `STARK_TV_IP` + `STARK_TV_IP_CONTROL_KEY` — the TV's own IP Control channel
    (port 9761), in `lg_ip_control.py`. Verified against the real set on
    2026-11-03; it reports the *screen*, not the socket.
  * `STARK_TV_BRIDGE_URL` — the TV through `apps/backend/tv_bridge.py`, a small
    HTTP server running on the set's own LAN that calls the same IP-control
    code there. For the deployed backend, which cannot open a LAN socket from
    a data centre and therefore reaches the television only over a tunnel.
  * `STARK_TV_PLUG_URL` — a Shelly Gen2+ plug over HTTP (`/rpc/Switch.Set`,
    `/rpc/Switch.GetStatus`), a Plus Plug UK, 13 A, local API on by default.

None of them set means a simulated plug, described above.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


class DeviceUnreachable(Exception):
    """The plug did not answer, so nothing can be claimed about the socket."""


@dataclass(frozen=True)
class SwitchResult:
    """What the device reported, never what it was asked to do."""

    output: bool          # the socket is live
    watts: Optional[float]  # `apower`, when the plug can read it
    read_back: bool       # a real status read followed the command
    simulated: bool


class SimulatedPlug:
    """A plug that exists only in this process. Reports itself as simulated."""

    def __init__(self, on: bool = False, watts_on: float = 46.0) -> None:
        self._on = on
        self._watts_on = watts_on

    def set(self, on: bool) -> SwitchResult:
        self._on = on
        return self.status()

    def status(self) -> SwitchResult:
        return SwitchResult(
            output=self._on,
            watts=self._watts_on if self._on else 0.0,
            read_back=True,
            simulated=True,
        )


class BridgeTvPlug:
    """The TV, driven through a bridge that lives on the TV's own LAN.

    The backend never sees the LAN: it answers HTTP to a bridge process that
    runs beside the TV and owns the IP-control socket and the wake packets.
    This exists because a deployed backend has no route into a home network —
    the honest alternative is a simulated plug, and a simulated plug is a
    sentence that must be spoken ("That was the simulated plug."). With the
    bridge, the live site can say "TV is off" because the set really turned
    off; but if the bridge or the tunnel is down, the same honesty rules
    apply: an unanswered bridge is `device_unreachable`, never a confident
    claim.

    Address and token come from `STARK_TV_BRIDGE_URL` and
    `STARK_TV_BRIDGE_TOKEN`; never from a client.
    """

    def __init__(self, base_url: str, token: str = "", timeout: float = 90.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout

    def set(self, on: bool) -> SwitchResult:
        body = self._call(f"/{'on' if on else 'off'}")
        return self._result(body)

    def status(self) -> SwitchResult:
        return self._result(self._call("/status"))

    def _call(self, path: str) -> dict:
        # `/status` is a read; `/on` and `/off` are the writes. One Request per
        # call, tagged with the method, and the bridge returns JSON either way.
        write = path in ("/on", "/off")
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=b"" if write else None,
            method="POST" if write else "GET",
        )
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise DeviceUnreachable(str(error)) from error

    def _result(self, body: dict) -> SwitchResult:
        output = bool(body.get("output"))
        watts = body.get("watts")
        return SwitchResult(
            output=output,
            watts=float(watts) if isinstance(watts, (int, float)) else None,
            read_back=bool(body.get("read_back")),
            simulated=bool(body.get("simulated")),
        )


class ShellyPlug:
    """A Shelly Gen2+ plug on the LAN, over its local RPC.

    One fixed address, one fixed id: the address comes from env and never from a
    client, so no request can point this at another host. `_call` raises
    `DeviceUnreachable` on any timeout, connection error or non-JSON body — the
    service turns that into a 503 rather than a confident sentence.
    """

    def __init__(self, base_url: str, token: str = "", timeout: float = 4.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout

    def set(self, on: bool) -> SwitchResult:
        self._call(f"/rpc/Switch.Set?id=0&on={'true' if on else 'false'}")
        try:
            return self.status()
        except DeviceUnreachable:
            # The command may well have landed; we just cannot prove it, and an
            # unproven switch is exactly what the reply must not claim.
            return SwitchResult(output=on, watts=None, read_back=False, simulated=False)

    def status(self) -> SwitchResult:
        body = self._call("/rpc/Switch.GetStatus?id=0")
        output = bool(body.get("output"))
        watts = body.get("apower")
        return SwitchResult(
            output=output,
            watts=float(watts) if isinstance(watts, (int, float)) else None,
            read_back=True,
            simulated=False,
        )

    def _call(self, path: str) -> dict:
        request = urllib.request.Request(f"{self.base_url}{path}")
        if self.token:
            # A local Shelly uses Basic auth with `user:password`; a token
            # without a colon is passed as a bearer. Untested against hardware.
            if ":" in self.token:
                encoded = base64.b64encode(self.token.encode()).decode()
                request.add_header("Authorization", f"Basic {encoded}")
            else:
                request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise DeviceUnreachable(str(error)) from error


def plug_from_env():
    """The TV's own IP control, the LAN bridge, a Shelly, or the simulated stub.

    Kept as one function so nothing else has to know which hardware is present.
    The selector lives in `lg_ip_control` because that module knows the order
    (TV first, bridge second, plug third) and imports the plug classes lazily
    to stay acyclic.
    """
    from app.modules.device.lg_ip_control import plug_from_env as choose

    return choose()
