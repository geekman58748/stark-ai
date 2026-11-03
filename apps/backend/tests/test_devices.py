#!/usr/bin/env python3
"""Tests for TV on/off (docs/HANDOFF.md §8B): registry, switch, gate, replies.

Zero network for the service and agent cases: the plug is a stub. The three
route cases use `ApiHarness`, so they need `DATABASE_URL` like the rest of the
API suite.

    .venv/bin/python -m unittest tests.test_devices -v
"""

from __future__ import annotations

import unittest

from app.common.api_error import ApiError
from app.modules.agent import agent as agent_mod
from app.modules.device import devices as device_layer
from app.modules.device.device_service import DeviceService
from tests.support import ApiHarness, TempAccount

TV = {"id": "tv-plug-1", "label": "Living room TV", "kind": "tv"}


class FakePlug:
    """Records what it was told, and reports what a plug would read back."""

    def __init__(self, watts_on: float = 46.0) -> None:
        self.on = False
        self.watts_on = watts_on
        self.calls: list[bool] = []

    def set(self, on: bool) -> device_layer.SwitchResult:
        self.calls.append(on)
        self.on = on
        return self.status()

    def status(self) -> device_layer.SwitchResult:
        return device_layer.SwitchResult(
            output=self.on,
            watts=self.watts_on if self.on else 0.0,
            read_back=True,
            simulated=False,
        )


class UnreachablePlug:
    def set(self, on: bool) -> device_layer.SwitchResult:
        raise device_layer.DeviceUnreachable("timed out")


class DevicelessToolbox:
    """The agent's toolbox, with a plug instead of a database behind it."""

    def __init__(self, devices=None, device_service=None) -> None:
        self.service = device_service or DeviceService(FakePlug())
        self.extra_devices = devices
        self.switch_calls: list[tuple[str, bool]] = []

    def list_devices(self):
        if self.extra_devices is not None:
            return list(self.extra_devices)
        return self.service.devices("acct")

    def switch_appliance(self, device_id, on):
        self.switch_calls.append((device_id, on))
        try:
            return self.service.switch("acct", device_id, on)
        except ApiError as err:
            raise agent_mod.PaymentError(err.code, err.message, err.detail) from err

    def get_state(self):
        return {"balance_ngn": 64_200, "spent_ngn": 0, "cap_ngn": 30_000}

    def list_bills(self):
        return []

    def recent_activity(self):
        return []

    def pay(self, bill_id, amount_ngn):  # pragma: no cover - not used here
        raise AssertionError("no payment in a TV test")


def agent_for(toolbox) -> agent_mod.Agent:
    return agent_mod.Agent(
        model=agent_mod.FakeModel(),
        toolbox=toolbox,
        limits=agent_mod.Limits(monthly_cap_ngn=30_000, per_payment_cap_ngn=10_000,
                                allowed_meters=frozenset()),
    )


class RegistryTests(unittest.TestCase):
    def test_the_tv_is_seeded_with_no_state_observed_yet(self):
        service = DeviceService(FakePlug())
        listed = service.devices("acct")
        self.assertEqual([d["id"] for d in listed], ["tv-plug-1"])
        self.assertEqual(listed[0]["label"], "Living room TV")
        # Nothing has read the plug, so there is no state to claim.
        self.assertIsNone(listed[0]["last_status"])

    def test_switching_reads_the_socket_back(self):
        plug = FakePlug()
        service = DeviceService(plug)
        result = service.switch("acct", "tv-plug-1", True)
        self.assertEqual(plug.calls, [True])
        self.assertTrue(result["on"])
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["status"], "on")
        self.assertAlmostEqual(result["watts"], 46.0)
        self.assertFalse(result["simulated"])
        # Remembered for the snapshot, so a later question needs no new switch.
        self.assertEqual(service.devices("acct")[0]["last_status"], "on")

    def test_a_live_socket_with_a_sleeping_set_is_standby(self):
        plug = FakePlug(watts_on=0.4)
        service = DeviceService(plug)
        result = service.switch("acct", "tv-plug-1", True)
        self.assertTrue(result["on"])
        self.assertEqual(result["status"], "standby")

    def test_an_unknown_device_is_a_refusal_not_a_guess(self):
        service = DeviceService(FakePlug())
        with self.assertRaises(ApiError) as caught:
            service.switch("acct", "tv-plug-99", True)
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(caught.exception.code, "unknown_device")

    def test_a_plug_that_does_not_answer_changes_nothing(self):
        service = DeviceService(UnreachablePlug())
        with self.assertRaises(ApiError) as caught:
            service.switch("acct", "tv-plug-1", True)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(caught.exception.code, "device_unreachable")
        # And no state is invented from the attempt.
        self.assertIsNone(service.devices("acct")[0]["last_status"])

    def test_the_simulated_plug_is_marked_simulated(self):
        service = DeviceService(device_layer.SimulatedPlug())
        result = service.switch("acct", "tv-plug-1", True)
        self.assertTrue(result["simulated"])
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["status"], "on")


class GateTests(unittest.TestCase):
    def test_a_question_about_the_tv_never_switches_it(self):
        plug = FakePlug()
        toolbox = DevicelessToolbox(device_service=DeviceService(plug))
        reply = agent_for(toolbox).respond("is the TV on?")
        self.assertEqual(plug.calls, [])
        self.assertEqual(toolbox.switch_calls, [])
        self.assertIn("don't know", reply.reply)

    def test_past_tense_is_a_question_too(self):
        toolbox = DevicelessToolbox()
        reply = agent_for(toolbox).respond("did you turn off the TV?")
        self.assertEqual(toolbox.switch_calls, [])
        self.assertIn("don't know", reply.reply)

    def test_an_order_switches_and_says_what_the_plug_read(self):
        toolbox = DevicelessToolbox()
        reply = agent_for(toolbox).respond("turn off the TV")
        self.assertEqual(toolbox.switch_calls, [("tv-plug-1", False)])
        self.assertEqual(reply.reply, "Living room TV is off.")

    def test_permission_still_switches(self):
        toolbox = DevicelessToolbox()
        reply = agent_for(toolbox).respond("can you turn the TV off")
        self.assertEqual(toolbox.switch_calls, [("tv-plug-1", False)])
        self.assertIn("off", reply.reply)

    def test_the_state_is_answered_from_the_last_read_without_switching_again(self):
        plug = FakePlug()
        toolbox = DevicelessToolbox(device_service=DeviceService(plug))
        agent = agent_for(toolbox)
        agent.respond("turn on the TV")
        self.assertEqual(plug.calls, [True])
        reply = agent.respond("is the TV on?")
        self.assertEqual(plug.calls, [True], "a question must not flip the socket again")
        self.assertIn("on", reply.reply)

    def test_a_device_the_registry_does_not_have_is_refused(self):
        toolbox = DevicelessToolbox(devices=[TV])
        refusal = agent_for(toolbox)._switch_appliance(
            {"device_id": "tv-plug-9", "on": True}, "turn on the TV"
        )
        self.assertFalse(refusal["ok"])
        self.assertEqual(refusal["error"]["code"], "unknown_device")
        self.assertEqual(toolbox.switch_calls, [])

    def test_a_plug_that_did_not_answer_is_reported_as_unconfirmed(self):
        toolbox = DevicelessToolbox(device_service=DeviceService(UnreachablePlug()))
        reply = agent_for(toolbox).respond("turn on the TV")
        self.assertIn("didn't answer", reply.reply)

    def test_the_snapshot_carries_the_devices(self):
        toolbox = DevicelessToolbox()
        reply = agent_for(toolbox).respond("turn on the TV")
        snapshot = reply.conversation[0]["content"]
        self.assertIn("tv-plug-1", snapshot)
        self.assertIn("Living room TV", snapshot)

    def test_a_simulated_switch_is_said_to_be_simulated(self):
        toolbox = DevicelessToolbox(device_service=DeviceService(
            device_layer.SimulatedPlug()))
        reply = agent_for(toolbox).respond("turn off the TV")
        self.assertIn("simulated", reply.reply)


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.account = TempAccount()
        self.api = ApiHarness(self.account)

    def tearDown(self) -> None:
        self.account.close()

    def test_listing_and_switching_over_http(self):
        listed = self.api.client.get("/v1/devices")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([d["id"] for d in listed.json()], ["tv-plug-1"])

        switched = self.api.client.post("/v1/devices/tv-plug-1/switch", json={"on": True})
        self.assertEqual(switched.status_code, 200)
        body = switched.json()
        self.assertEqual(body["status"], "on")
        self.assertTrue(body["confirmed"])
        self.assertTrue(body["simulated"])  # no STARK_TV_PLUG_URL in this test run

    def test_an_unknown_device_is_404(self):
        response = self.api.client.post("/v1/devices/tv-plug-9/switch", json={"on": True})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "unknown_device")

    def test_an_unreachable_plug_is_503_and_claims_nothing(self):
        self.api.module.devices.plug = UnreachablePlug()
        response = self.api.client.post("/v1/devices/tv-plug-1/switch", json={"on": False})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "device_unreachable")


if __name__ == "__main__":
    unittest.main()
