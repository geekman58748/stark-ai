"""Payees: the saved bills, with what each has actually been paid."""

from __future__ import annotations

import unittest

from tests import support as test_support


class PayeesTest(unittest.TestCase):
    def setUp(self):
        self.account = test_support.TempAccount(balance_ngn=50_000)
        self.addCleanup(self.account.close)
        self.api = test_support.ApiHarness(self.account)
        self.addCleanup(self.api.restart)
        self.client = self.api.client

    def test_only_delivered_payments_count(self):
        bill = self.client.post("/v1/bills", json={
            "kind": "airtime", "provider": "MTN", "reference": "08030000004",
            "label": "Test line",
        }).json()
        self.assertEqual(self.client.get("/v1/payees").json(), [{
            "bill_id": bill["id"], "label": "Test line", "kind": "airtime",
            "provider": "MTN", "reference": "08030000004", "paid_this_month_ngn": 0,
            "paid_total_ngn": 0, "payments": 0, "last_paid_at": None,
        }])

        self.client.post("/v1/payments", json={"bill_id": bill["id"], "amount_ngn": 500})
        self.api.module.bill_payments.record_declined(
            self.account.id, bill["id"], "Test line", 700, "Not this one.")

        [payee] = self.client.get("/v1/payees").json()
        delivered = [r for r in self.client.get("/v1/activity").json()
                     if r["status"] == "delivered"]
        paid = sum(r["amount_ngn"] for r in delivered)
        self.assertEqual((payee["paid_total_ngn"], payee["payments"]), (paid, len(delivered)))
        self.assertEqual(payee["paid_this_month_ngn"], paid)


if __name__ == "__main__":
    unittest.main()
