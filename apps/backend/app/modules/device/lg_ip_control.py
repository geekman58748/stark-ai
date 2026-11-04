"""The TV itself as a switchable device, over LG's IP Control channel.

A plug reports the socket; this reports the set. Verified against the real
43UT73006LA on 2026-11-03: `POWER off` -> `Power Status: activeStandby` ->
magic packet -> `Power Status: active`.

Three things about the protocol are worth knowing before touching this:

* **Port 9761, not 3000.** 3000 is SSAP, which accepts connections and hangs up
  without a word on this set. 9761 is the channel the TV's *IP Control* setting
  opens, and its eight-character key is the password to your television — it
  comes from env and never from a client.
* **Every message is encrypted.** The frame is `AES-ECB(key, IV)` followed by
  `AES-CBC(key, IV, "COMMAND\\r" + padding)`, where the key is PBKDF2 over the
  key code with LG's fixed salt. The reply is framed the same way and carries
  its own IV, which is why `unframe` decrypts the first block with ECB first.
* **It can switch the TV off but not on.** `POWER on` does not exist; a set in
  standby is only woken by a magic packet. Hence `STARK_TV_MAC` — and the Wi-Fi
  adapter only listens for that packet when the TV's *General -> Devices -> TV
  On With Mobile -> Turn on via Wi-Fi* is enabled.

**The read-back after `POWER off` races the shutdown.** Measured on the real set:
it answers `active` for a second or two after acknowledging, so a single read right
after the command reports the TV as still on — which is exactly how Stark once said
"Living room TV is on" while the screen was going black. `set` therefore waits for
the state to actually leave `active` before it reports anything.

An unreadable reply or a set that never wakes is `DeviceUnreachable`, which the
service turns into `503 device_unreachable` rather than a confident sentence.
"""

from __future__ import annotations

import hashlib
import os
import re
import socket
import time
from typing import Optional

from app.modules.device.aes import cbc_decrypt, cbc_encrypt, ecb_decrypt, ecb_encrypt
from app.modules.device.devices import DeviceUnreachable, SwitchResult

PORT = 9761
BLOCK = 16
ACTIVE = "active"
STANDBY = "activeStandby"

# LG's salt, from its IP Control guide. Fixed, not secret.
_MAC = re.compile(r"[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}")

_SALT = bytes([
    0x63, 0x61, 0xB8, 0x0E, 0x9B, 0xDC, 0xA6, 0x63,
    0x8D, 0x07, 0x20, 0xF2, 0xCC, 0x56, 0x8F, 0xB9,
])


def derive_key(key_code: str) -> bytes:
    """The AES-128 key: first 16 bytes of PBKDF2(code, sha256, LG's salt, 2**14)."""
    return hashlib.pbkdf2_hmac("sha256", key_code.encode("utf-8"), _SALT, 1 << 14, dklen=16)


def _pad(body: bytes) -> bytes:
    pad = BLOCK - (len(body) % BLOCK)
    return body + bytes([pad]) * pad


def _unpad(body: bytes) -> bytes:
    if not body:
        return body
    pad = body[-1]
    return body[:-pad] if 0 < pad <= BLOCK else body


def broadcast_for(host: str) -> str:
    """The /24 broadcast a magic packet should go to for a given TV address."""
    parts = host.split(".")
    return ".".join(parts[:3] + ["255"]) if len(parts) == 4 else "255.255.255.255"


class LgTvPlug:
    """One fixed TV, addressed from env, switched over its IP Control channel."""

    def __init__(self, host: str, key_code: str, mac: Optional[str] = None,
                 broadcast: Optional[str] = None, port: int = PORT, timeout: float = 4.0,
                 wake_seconds: float = 40.0, settle_seconds: float = 6.0,
                 poll_seconds: float = 0.2) -> None:
        self.host = host.strip()
        self.port = port
        self.timeout = timeout
        self.wake_seconds = wake_seconds
        self.settle_seconds = settle_seconds
        self.poll_seconds = poll_seconds
        self.mac = (mac or "").strip() or None
        self.broadcast = (broadcast or "").strip() or broadcast_for(self.host)
        self._key = derive_key(key_code.strip())

    # --- framing -----------------------------------------------------------

    def frame(self, command: str) -> bytes:
        iv = os.urandom(BLOCK)
        body = _pad(command.encode("utf-8") + b"\r")
        return ecb_encrypt(self._key, iv) + cbc_encrypt(self._key, iv, body)

    def _unframe_raw(self, data: bytes) -> str:
        """The reply's text with its padding removed and its CR kept."""
        if len(data) <= BLOCK:
            return ""
        iv = ecb_decrypt(self._key, data[:BLOCK])
        return _unpad(cbc_decrypt(self._key, iv, data[BLOCK:])).decode("utf-8", "replace")

    def unframe(self, data: bytes) -> str:
        return self._unframe_raw(data).strip()

    def _is_complete_frame(self, data: bytes) -> bool:
        """True once what is on the wire is a whole reply.

        The set sends its frame and then **leaves the socket open**, so a read
        loop that waits for EOF waits out the entire timeout — measured 4.5s per
        command on 2026-11-03, which is the whole reason Stark went quiet for
        seconds after the screen was already black. Every reply unpads to
        printable text ending in the protocol's CR, so the first block that does
        is the end of it; anything else is a partial frame and keeps reading.
        """
        if len(data) <= BLOCK or len(data) % BLOCK:
            return False
        try:
            raw = self._unframe_raw(data)
        except Exception:
            return False
        # The real set terminates with LF, not CR (measured 2026-11-04 against
        # 43UT73006LA): it answers ``Power Status: activeStandby\n``. Checking for
        # CR alone made every reply look partial, which is the same 4s wait by
        # another route — accept either line ending.
        if not raw.endswith(("\r", "\n")):
            return False
        return bool(raw[:-1]) and all(32 <= ord(ch) < 127 for ch in raw[:-1])

    def _exchange(self, payload: bytes) -> bytes:
        """Send one frame and read the reply. Split out so tests need no socket."""
        data = b""
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as conn:
                conn.sendall(payload)
                conn.settimeout(self.timeout)
                try:
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        data += chunk
                        if self._is_complete_frame(data):
                            break
                except socket.timeout:
                    pass
                return data
        except OSError as error:
            raise DeviceUnreachable(str(error)) from error

    def ask(self, command: str) -> str:
        data = self._exchange(self.frame(command))
        if not data:
            raise DeviceUnreachable("the TV answered nothing")
        return self.unframe(data)

    # --- state -------------------------------------------------------------

    def power_state(self) -> str:
        """`active`, `activeStandby`, or whatever LG decides to call it next."""
        reply = self.ask("POWER_STATUS")
        return reply.split(":", 1)[-1].strip() if ":" in reply else reply.strip()

    def _learn_mac(self) -> None:
        """Ask the TV for its Wi-Fi MAC while it is still awake enough to answer.

        The real set answers with the bare address (``aa:bb:cc:dd:ee:ff``), so
        this searches for a MAC rather than splitting on the first colon — the
        address is full of colons.
        """
        try:
            reply = self.ask("GET_MACADDRESS wifi")
        except DeviceUnreachable:
            return
        found = _MAC.search(reply)
        if found:
            self.mac = found.group(0).replace("-", ":")

    def _wake(self) -> None:
        if not self.mac:
            raise DeviceUnreachable(
                "no MAC configured, so the TV cannot be woken; set STARK_TV_MAC"
            )
        address = bytes.fromhex(self.mac.replace(":", "").replace("-", ""))
        packet = b"\xff" * 6 + address * 16
        deadline = time.time() + self.wake_seconds
        sent = False
        while time.time() < deadline:
            if not sent or int(time.time()) % 4 == 0:
                for destination in ((self.broadcast, 9), (self.broadcast, 4343),
                                    (self.host, 4343)):
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                            sock.sendto(packet, destination)
                    except OSError:
                        pass
                sent = True
            time.sleep(1.0)
            try:
                if self.power_state() == ACTIVE:
                    return
            except DeviceUnreachable:
                continue
        raise DeviceUnreachable("the TV did not wake; check 'Turn on via Wi-Fi'")

    def _settle(self, done, seconds: Optional[float] = None) -> Optional[str]:
        """Read the state until `done` is true or the deadline passes.

        Returns the last state it managed to read, or None when the set never
        answered at all — which the caller must not turn into a confident claim.
        """
        deadline = time.time() + (self.settle_seconds if seconds is None else seconds)
        state: Optional[str] = None
        while True:
            try:
                state = self.power_state()
            except DeviceUnreachable:
                state = None
            if state is not None and done(state):
                return state
            if time.time() >= deadline:
                return state
            time.sleep(self.poll_seconds)

    def set(self, on: bool) -> SwitchResult:
        read_back = True
        if on:
            self._wake()                 # already polled until the set said `active`
            state: Optional[str] = ACTIVE
        else:
            if not self.mac:
                self._learn_mac()
            self.ask("POWER off")
            # The set says `active` for a moment after acknowledging, so one read
            # here would report the opposite of what is happening on screen.
            state = self._settle(lambda seen: seen != ACTIVE)
            read_back = state is not None
        if state is None:
            return SwitchResult(output=on, watts=None, read_back=False, simulated=False)
        return SwitchResult(
            output=state == ACTIVE,
            watts=None,          # a TV reports its state, not its draw
            read_back=read_back,
            simulated=False,
        )


def plug_from_env():
    """The TV when its IP control is configured, a Shelly, or the stub."""
    host = (os.environ.get("STARK_TV_IP") or "").strip()
    code = (os.environ.get("STARK_TV_IP_CONTROL_KEY") or "").strip()
    if host and code:
        return LgTvPlug(
            host,
            code,
            mac=(os.environ.get("STARK_TV_MAC") or "").strip() or None,
            broadcast=(os.environ.get("STARK_TV_BROADCAST") or "").strip() or None,
        )
    from app.modules.device.devices import ShellyPlug, SimulatedPlug

    url = (os.environ.get("STARK_TV_PLUG_URL") or "").strip()
    if not url:
        return SimulatedPlug()
    return ShellyPlug(url, os.environ.get("STARK_TV_PLUG_TOKEN") or "")
