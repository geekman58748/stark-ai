"""The public sample account: readable without a session, and never a real one."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.demo.demo_service import DemoService
from app.modules.demo.dtos.demo_dto import DemoDto
from tests import support as test_support


class DemoTest(unittest.TestCase):
    def test_the_snapshot_matches_its_contract(self):
        DemoDto.model_validate(DemoService().snapshot())

    def test_it_shows_a_request_waiting_and_no_declined_attempt(self):
        snapshot = DemoService().snapshot()
        [request] = snapshot["approvals"]
        self.assertEqual(request["status"], "pending")
        self.assertGreater(request["expires_at"], snapshot["state"]["as_of"])
        self.assertNotIn("declined", {r["status"] for r in snapshot["activity"]})
        self.assertTrue(snapshot["state"]["due_soon"])

    def test_it_needs_no_sign_in(self):
        account = test_support.TempAccount()
        self.addCleanup(account.close)
        harness = test_support.ApiHarness(account)
        # A client with no auth override at all: the route must not ask for one.
        client = TestClient(create_app(harness.module))
        response = client.get("/v1/demo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["user_id"], "demo")
        self.assertEqual(client.get("/v1/state").status_code, 401)


if __name__ == "__main__":
    unittest.main()
