#!/usr/bin/env python3
"""The TV's bridge: an HTTP face for the switch that lives beside the set.

The deployed backend cannot open a socket on the home LAN, so this small
server runs on a machine that can and advertises the television over a
tunnel. It wraps the very same `plug_from_env()` this repo's backend uses —
the LG IP-control channel, magic-packet wake included — so no protocol logic
is duplicated and nothing on the TV itself changes. `BridgeTvPlug`
(`app/modules/device/devices.py`) is its client.

Endpoints, all JSON, none of them ever a confident lie:

  GET  /health    {"ok": true}                token NOT required
  GET  /status    a plug result body          Bearer token required
  POST /on        a plug result body after wake
  POST /off       a plug result body after settle

An unreachable set is `503 {"error": "device_unreachable"}`; a missing or
wrong token is 401. Nothing else answers.

Env:
  * `STARK_TV_BRIDGE_TOKEN` — required. The tunnel is public; turning the
    television off from someone else's phone is not the demo.
  * The usual device vars (`STARK_TV_IP`, `STARK_TV_IP_CONTROL_KEY`,
    `STARK_TV_MAC`, …) — loaded from this directory's `.env` unless already
    set in the process, exactly like the backend reads them.

Run it from `apps/backend` with the backend's own interpreter:

    .venv/bin/python tv_bridge.py          # 127.0.0.1:9762 by default

It binds the loopback: only the tunnel on this machine should reach it.
"""

from __future__ import annotations

import hmac
import http.server
import json
import os
import sys
from pathlib import Path

from app.modules.device import devices as device_layer
from app.modules.device.devices import DeviceUnreachable

HOST = "127.0.0.1"
PORT = 9762


def load_env(path: Path) -> None:
    """A `.env` reader good enough for this process, not a dependency.

    Real environment wins: `os.environ.setdefault` is the rule, the same way
    the backend's own launcher does `set -a; . ./.env; set +a`.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _read_status(plug):
    """Read the state under the name this plug's class exposes.

    `SimulatedPlug` and `ShellyPlug` speak in `SwitchResult` via `status()`; the
    LG television speaks a bare state string via `power_state()` — map it here
    so the HTTP face is one shape whatever is behind it.
    """
    if hasattr(plug, "power_state"):
        state = plug.power_state()
        return device_layer.SwitchResult(
            output=state == "active", watts=None, read_back=True, simulated=False)
    return plug.status()


def plug_body(plug, on: bool | None) -> tuple[int, dict]:
    """Run one switch or one status and translate it to an HTTP answer."""
    try:
        result = _read_status(plug) if on is None else plug.set(on)
    except DeviceUnreachable as error:
        return 503, {"error": "device_unreachable", "detail": str(error)[:200]}
    return 200, {
        "output": result.output,
        "watts": result.watts,
        "read_back": result.read_back,
        "simulated": result.simulated,
    }


class Handler(http.server.BaseHTTPRequestHandler):
    gate = ""  # the shared secret, set in `main`

    def _authorised(self) -> bool:
        header = self.headers.get("Authorization", "")
        return hmac.compare_digest(header, f"Bearer {self.gate}")

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"ok": True})
            return
        if not self._authorised():
            self._send(401, {"error": "unauthorised"})
            return
        if self.path == "/status":
            status, body = plug_body(self.server.plug, None)
            self._send(status, body)
            return
        self._send(404, {"error": "unknown_path"})

    def do_POST(self) -> None:
        if self.path not in ("/on", "/off"):
            self._send(404, {"error": "unknown_path"})
            return
        if not self._authorised():
            self._send(401, {"error": "unauthorised"})
            return
        status, body = plug_body(self.server.plug, self.path == "/on")
        self._send(status, body)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            f"tv_bridge: {self.address_string()} {fmt % args}\n")


def main() -> None:
    load_env(Path(__file__).with_name(".env"))
    gate = (os.environ.get("STARK_TV_BRIDGE_TOKEN") or "").strip()
    if not gate:
        sys.exit(
            "tv_bridge: STARK_TV_BRIDGE_TOKEN is not set — refusing to serve a "
            "switch anyone could reach."
        )
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    Handler.gate = gate            # the check itself keeps its 401 until this is set
    server.plug = device_layer.plug_from_env()  # the real TV, woken from here
    print(f"tv_bridge: serving on http://{HOST}:{PORT} (token required)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
