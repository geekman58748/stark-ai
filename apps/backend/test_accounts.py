"""A real account's data is its own: no artboard seed, nothing lost on restart.

Runs the server's handlers against a throwaway account on the real database
(`test_support.TempAccount`), so it needs `DATABASE_URL` like the store tests.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

import test_support


class AccountDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server

    def setUp(self):
        self.account = test_support.TempAccount()
        self.addCleanup(self.account.close)
        self.addCleanup(self.server.ACCOUNTS.pop, self.account.id, None)
        test_support.enter_server_account(self.server, self.account)

    def restart(self):
        """Forget the in-process copy, as a fresh server process would."""
        self.server.ACCOUNTS.pop(self.account.id, None)
        self.server._prepare_account(self.account.id, seeded=True)  # noqa: SLF001

    def test_a_new_account_opens_empty(self):
        self.server.ACCOUNTS.pop(self.account.id, None)
        self.server._prepare_account(self.account.id)  # noqa: SLF001 - first sight
        _, state = self.server.h_state(None)
        self.assertEqual(state["bills"], [])
        self.assertEqual(state["balance_ngn"], 0)
        self.assertIsNone(state["units_left"])
        self.assertIsNone(state["days_left"])
        _, activity = self.server.h_activity(None)
        self.assertEqual(activity, [])

    def test_bills_and_limits_survive_a_restart(self):
        _, bill = self.server.h_bill_add({
            "kind": "airtime", "provider": "MTN", "reference": "08030000001",
            "label": "Test line",
        })
        self.server.h_bill_update({"label": "Renamed"}, {"bill_id": bill["id"]})
        self.server.h_limits_patch({"monthly_cap_ngn": 40_000, "per_payment_cap_ngn": 8_000})

        self.restart()

        _, bills = self.server.h_bills(None)
        self.assertEqual([(b["id"], b["label"]) for b in bills], [(bill["id"], "Renamed")])
        _, caps = self.server.h_limits()
        self.assertEqual((caps["monthly_cap_ngn"], caps["per_payment_cap_ngn"]),
                         (40_000, 8_000))

        self.server.h_bill_delete({"bill_id": bill["id"]})
        self.restart()
        self.assertEqual(self.server.h_bills(None)[1], [])

    def test_a_reading_is_stamped_with_server_time(self):
        self.server.h_telemetry({"device_id": "ac", "watts": 900, "ts": "2001-01-01T00:00:00Z"})
        rows = self.server.READINGS.since(self.account.id, "2000-01-01T00:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["ts"].startswith("20"))
        self.assertNotEqual(rows[0]["ts"], "2001-01-01T00:00:00Z")

    def test_negative_watts_are_refused(self):
        with self.assertRaises(self.server.ApiError):
            self.server.h_telemetry({"device_id": "ac", "watts": -5})

    def test_reset_is_off_unless_switched_on(self):
        with mock.patch.dict(os.environ, {"STARK_STUB_RESET": ""}):
            with self.assertRaises(self.server.ApiError) as raised:
                self.server.h_reset()
        self.assertEqual(raised.exception.status, 404)

    def test_withdraw_refuses_and_takes_nothing(self):
        self.account.store.set_wallet(5_000, 0)
        with self.assertRaises(self.server.ApiError) as raised:
            self.server.h_wallet_withdraw({"amount_ngn": 1_000})
        self.assertEqual(raised.exception.status, 501)
        self.assertEqual(self.account.store.wallet()["balance_ngn"], 5_000)

    def test_top_up_is_labelled_test_money(self):
        self.account.store.set_wallet(0, 0)
        _, moved = self.server.h_wallet_topup({"amount_ngn": 2_000, "source": "Bank transfer"})
        self.assertEqual(moved["entry"]["source"], "Test money")
        self.assertEqual(moved["wallet"]["balance_ngn"], 2_000)


if __name__ == "__main__":
    unittest.main()
