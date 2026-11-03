#!/usr/bin/env python3
"""Tests for the LG IP Control adapter (docs/HANDOFF.md §8B).

The AES block plus framing is pinned to the FIPS-197 vector and to a round trip
through the same code path the TV uses, so a mistake in the cipher fails here
rather than at 23:00 on a real television. Everything else runs against a fake
TV that decrypts what we send — zero network, zero hardware.

    .venv/bin/python -m unittest tests.test_lg_ip_control -v
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from app.modules.device import aes, lg_ip_control as lg
from app.modules.device import devices as device_layer
from app.modules.device.device_service import DeviceService

# Fake credentials: the real key code and MAC belong in .env, never in the repo.
KEY_CODE = "ZQ7K2M9P"
MAC = "aa:bb:cc:dd:ee:ff"


class AesTests(unittest.TestCase):
    def test_fips_197_vector(self):
        # FIPS-197 C.1: key 000102...0f, plaintext 00112233...ff.
        key = bytes(range(16))
        block = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.assertEqual(aes.ecb_encrypt(key, block).hex(),
                         "69c4e0d86a7b0430d8cdb78070b4c55a")

    def test_decryption_inverts_encryption(self):
        key = bytes(range(16))
        block = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.assertEqual(aes.ecb_decrypt(key, aes.ecb_encrypt(key, block)), block)

    def test_cbc_round_trip_spans_several_blocks(self):
        key = lg.derive_key(KEY_CODE)
        iv = bytes(range(16))
        plain = b"POWER_STATUS\r" + b"\x03" * 3
        self.assertEqual(aes.cbc_decrypt(key, iv, aes.cbc_encrypt(key, iv, plain)), plain)

    def test_a_short_key_is_refused(self):
        with self.assertRaises(ValueError):
            aes.ecb_encrypt(b"too short", bytes(16))


class FakeTv(lg.LgTvPlug):
    """A television that decrypts what it is sent and answers in a frame."""

    def __init__(self, state: str = lg.ACTIVE, answers: bool = True,
                 lag: int = 0) -> None:
        super().__init__("10.0.0.5", KEY_CODE, mac=MAC, poll_seconds=0.01,
                         settle_seconds=0.5)
        self.state = state
        self.answers = answers
        self.lag = lag           # reads that still say `active` after POWER off
        self.pending = 0
        self.commands: list[str] = []
        self.wake_calls = 0

    def _exchange(self, payload: bytes) -> bytes:
        if not self.answers:
            raise device_layer.DeviceUnreachable("no answer")
        command = self.unframe(payload).rstrip("\r")   # decrypts the real frame
        self.commands.append(command)
        if command.lower() == "power off":
            if self.lag:
                self.pending = self.lag      # the real set does not flip instantly
            else:
                self.state = lg.STANDBY
        if command.startswith("POWER_STATUS"):
            shown = self.state
            if self.pending:
                self.pending -= 1
                shown = lg.ACTIVE
            elif self.lag:
                self.state = lg.STANDBY
            text = f"Power Status: {shown}\r"
        elif command.startswith("GET_MACADDRESS"):
            text = f"MAC Address: {MAC.upper()}\r"
        else:
            text = "OK\r"
        iv = os.urandom(16)
        return aes.ecb_encrypt(self._key, iv) + aes.cbc_encrypt(
            self._key, iv, lg._pad(text.encode()))

    def _wake(self) -> None:            # no real magic packets in a test
        self.wake_calls += 1
        self.state = lg.ACTIVE


class SilentTv(lg.LgTvPlug):
    """A TV with no MAC configured and nothing listening: cannot be woken."""

    def __init__(self) -> None:
        super().__init__("10.0.0.6", KEY_CODE)

    def _exchange(self, payload: bytes) -> bytes:
        raise device_layer.DeviceUnreachable("no answer")


class FramingTests(unittest.TestCase):
    def test_a_command_survives_a_round_trip_through_the_tv(self):
        tv = FakeTv()
        self.assertEqual(tv.ask("POWER_STATUS"), "Power Status: active")

    def test_the_key_is_derived_from_the_eight_characters(self):
        self.assertEqual(lg.derive_key(KEY_CODE).hex(), "7a4e491118e82ca0c37ffdaa1932196f")

    def test_the_broadcast_defaults_to_the_tvs_slash_24(self):
        self.assertEqual(lg.broadcast_for("192.168.100.28"), "192.168.100.255")


class SwitchTests(unittest.TestCase):
    def test_off_is_confirmed_by_a_state_read(self):
        tv = FakeTv()
        result = tv.set(False)
        self.assertIn("POWER off", tv.commands)
        self.assertFalse(result.output)
        self.assertTrue(result.read_back)
        self.assertFalse(result.simulated)
        self.assertIsNone(result.watts)      # a TV reports state, not draw
        self.assertEqual(tv.state, lg.STANDBY)

    def test_off_waits_out_the_shutdown_race(self):
        # Measured on the real set: it keeps answering `active` for a moment, so a
        # single read right after `POWER off` would report the TV as still on.
        tv = FakeTv(lag=3)
        result = tv.set(False)
        self.assertFalse(result.output)
        self.assertTrue(result.read_back)
        self.assertGreaterEqual(len([c for c in tv.commands if c.startswith("POWER_STATUS")]), 3)

    def test_on_sends_a_magic_packet_and_reads_the_state(self):
        tv = FakeTv(state=lg.STANDBY)
        result = tv.set(True)
        self.assertEqual(tv.wake_calls, 1)
        self.assertTrue(result.output)
        self.assertTrue(result.read_back)

    def test_a_tv_that_says_nothing_is_unreachable(self):
        tv = FakeTv(answers=False)
        with self.assertRaises(device_layer.DeviceUnreachable):
            tv.set(False)

    def test_no_mac_means_the_tv_cannot_be_woken(self):
        tv = SilentTv()                  # real _wake, so the mac check is exercised
        with self.assertRaises(device_layer.DeviceUnreachable):
            tv.set(True)

    def test_switching_off_learns_the_mac_for_a_later_wake(self):
        tv = FakeTv()
        tv.mac = None
        tv.set(False)
        self.assertEqual(tv.mac, MAC.upper())


class ServiceTests(unittest.TestCase):
    def test_the_tv_maps_onto_the_same_result_the_agent_already_speaks(self):
        service = DeviceService(FakeTv())
        off = service.switch("acct", "tv-plug-1", False)
        self.assertEqual(off["status"], "off")
        self.assertTrue(off["confirmed"])
        self.assertFalse(off["simulated"])
        self.assertEqual(service.devices("acct")[0]["last_status"], "off")

        on = service.switch("acct", "tv-plug-1", True)
        self.assertEqual(on["status"], "on")
        self.assertTrue(on["on"])


class SelectionTests(unittest.TestCase):
    def test_the_tv_wins_when_its_ip_control_is_configured(self):
        env = {"STARK_TV_IP": "192.168.100.28", "STARK_TV_IP_CONTROL_KEY": KEY_CODE,
               "STARK_TV_MAC": MAC.upper()}
        with mock.patch.dict(os.environ, env, clear=True):
            plug = device_layer.plug_from_env()
        self.assertIsInstance(plug, lg.LgTvPlug)
        self.assertEqual(plug.mac, MAC.upper())

    def test_a_half_configured_tv_falls_back_rather_than_guessing(self):
        with mock.patch.dict(os.environ, {"STARK_TV_IP": "192.168.100.28"}, clear=True):
            plug = device_layer.plug_from_env()
        self.assertIsInstance(plug, device_layer.SimulatedPlug)

    def test_a_shelly_still_wins_when_only_the_plug_is_configured(self):
        with mock.patch.dict(os.environ, {"STARK_TV_PLUG_URL": "http://192.168.1.50"},
                             clear=True):
            plug = device_layer.plug_from_env()
        self.assertIsInstance(plug, device_layer.ShellyPlug)

    def test_nothing_configured_is_still_the_stub(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            plug = device_layer.plug_from_env()
        self.assertIsInstance(plug, device_layer.SimulatedPlug)


if __name__ == "__main__":
    unittest.main()
