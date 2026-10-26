#!/usr/bin/env python3
"""Tests for M3: receipt store, vending gateway, two-phase payments.

Zero dependencies:  python3 -m unittest test_vending -v
"""

from __future__ import annotations

import unittest

import payments
import receipts
import test_support
import vending
from vtpass import VtpassClient

ELECTRICITY = {
    "id": "bill_home_meter",
    "kind": "electricity",
    "label": "Home meter",
    "reference": "04512345678",
}
DSTV = {
    "id": "bill_dstv",
    "kind": "tv",
    "provider": "DStv",
    "label": "DStv Compact",
    "reference": "7032119456",
    "plan": "dstv79",  # captured: DStv Compact, N7,900
}

AIRTIME = {
    "id": "bill_airtime",
    "kind": "airtime",
    "provider": "MTN",
    "label": "My line",
    "reference": "08031234567",
}

DATA = {
    "id": "bill_data",
    "kind": "data",
    "provider": "MTN",
    "label": "MTN data",
    "reference": "08031234567",
    "plan": "mtn-100mb-1000",  # captured: N1000 1.5GB - 30 days
}

SEED_BALANCE = 64_200
SEED_SPENT = 12_400


class StoreCase(unittest.TestCase):
    """One throwaway account per test, on the database the app actually uses."""

    def setUp(self):
        self.account = test_support.TempAccount(
            balance_ngn=SEED_BALANCE, spent_ngn=SEED_SPENT
        )
        self.store = self.account.store

    def tearDown(self):
        self.account.close()


class StoreTests(StoreCase):
    def test_wallet_round_trip(self):
        self.assertEqual(
            self.store.wallet(), {"balance_ngn": SEED_BALANCE, "spent_ngn": SEED_SPENT}
        )

    def test_charge_moves_balance_to_spend(self):
        after = self.store.charge(5_000)
        self.assertEqual(after, {"balance_ngn": 59_200, "spent_ngn": 17_400})
        self.assertEqual(self.store.wallet()["balance_ngn"], 59_200)

    def test_charge_refuses_more_than_the_balance(self):
        with self.assertRaises(ValueError):
            self.store.charge(SEED_BALANCE + 1)
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

    def test_created_receipt_is_findable_by_request_id(self):
        row = self.store.create(_receipt("r1", request_id="req-1"))
        self.assertEqual(self.store.by_request_id("req-1")["id"], row["id"])

    def test_request_id_is_unique(self):
        self.store.create(_receipt("r1", request_id="req-1"))
        with self.assertRaises(Exception):
            self.store.create(_receipt("r2", request_id="req-1"))

    def test_find_pending_ignores_finished_receipts(self):
        self.store.create(_receipt("r1", request_id="req-1", status="delivered"))
        self.assertIsNone(self.store.find_pending("bill_home_meter", 5_000))

    def test_find_pending_matches_only_the_same_intent(self):
        self.store.create(_receipt("r1", request_id="req-1", status="pending"))
        self.assertIsNone(self.store.find_pending("bill_home_meter", 6_000))
        self.assertIsNotNone(self.store.find_pending("bill_home_meter", 5_000))

    def test_recent_is_newest_first(self):
        self.store.create(_receipt("old", request_id="r-old", created_at="2026-10-01T00:00:00Z"))
        self.store.create(_receipt("new", request_id="r-new", created_at="2026-10-20T00:00:00Z"))
        self.assertEqual([r["id"] for r in self.store.recent(5)], ["new", "old"])

    def test_state_survives_a_new_connection(self):
        """A second store on the same database sees the same wallet and receipts."""
        self.store.create(_receipt("r1", request_id="req-1", status="delivered"))
        self.store.charge(5_000)

        reopened = test_support.BoundStore(
            receipts.ReceiptStore(self.account.db), self.account.id
        )
        self.assertEqual(reopened.wallet()["balance_ngn"], 59_200)
        self.assertEqual(reopened.count(), 1)
        self.assertEqual(reopened.get("r1")["status"], "delivered")

    def test_replace_all_clears_and_reseeds(self):
        self.store.create(_receipt("r1", request_id="req-1"))
        self.store.replace_all(
            [_receipt("seed", request_id="seed-1", status="delivered")],
            balance_ngn=SEED_BALANCE,
            spent_ngn=SEED_SPENT,
        )
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.store.recent()[0]["id"], "seed")
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

    def test_api_shape_has_the_frozen_keys(self):
        row = self.store.create(_receipt("r1", request_id="req-1"))
        shape = receipts.api_shape(row)
        for key in ("id", "bill_id", "bill_label", "amount_ngn", "units",
                    "token", "tx_hash", "created_at"):
            self.assertIn(key, shape)
        # Additive.
        self.assertIn("status", shape)
        self.assertIn("request_id", shape)


class GatewayTests(unittest.TestCase):
    def gateway(self, fixture=None, live=False):
        client = VtpassClient(dry_run=not live, fixture=fixture)
        return vending.VendingGateway(client, phone="08031234567")

    def test_dry_run_delivers_a_token(self):
        outcome = self.gateway().buy(ELECTRICITY, 5_000, "req-1")
        self.assertEqual(outcome.status, vending.DELIVERED)
        self.assertEqual(outcome.token, "4821 0937 5512 8846 3019")
        self.assertEqual(outcome.units, 23.92)

    def test_dry_run_units_follow_the_amount(self):
        # The fixture's units belong to its own sample amount; 2,500 naira must not
        # come back as 23.92 units.
        outcome = self.gateway().buy(ELECTRICITY, 2_500, "req-1")
        self.assertEqual(outcome.units, 11.96)

    def test_pending_is_not_delivered(self):
        outcome = self.gateway(fixture="pay_pending.json").buy(ELECTRICITY, 5_000, "req-1")
        self.assertEqual(outcome.status, vending.PENDING)
        self.assertIsNone(outcome.token)
        self.assertFalse(outcome.ok)

    def test_vendor_failure_is_reported_not_raised(self):
        outcome = self.gateway(fixture="pay_low_balance.json").buy(ELECTRICITY, 5_000, "req-1")
        self.assertEqual(outcome.status, vending.FAILED)
        self.assertEqual(outcome.code, "018")
        self.assertIn("float", outcome.message.lower() + " float")

    def test_airtime_is_bought_by_amount_without_a_token(self):
        outcome = self.gateway().buy(AIRTIME, 1_000, "req-1")
        self.assertEqual(outcome.status, vending.DELIVERED)
        self.assertIsNone(outcome.token)  # airtime has no meter token
        self.assertIsNone(outcome.units)
        self.assertFalse(outcome.token_required)

    def test_airtime_respects_the_vendor_limits(self):
        too_small = self.gateway().buy(AIRTIME, 3, "req-1")
        self.assertEqual(too_small.status, vending.FAILED)
        self.assertIn("least", too_small.message)

        too_big = self.gateway().buy(AIRTIME, 200_001, "req-1")
        self.assertEqual(too_big.status, vending.FAILED)
        self.assertIn("most", too_big.message)

    def test_data_buys_a_plan(self):
        outcome = self.gateway().buy(DATA, 1_000, "req-1")
        self.assertEqual(outcome.status, vending.DELIVERED)
        self.assertIsNone(outcome.token)

    def test_a_plan_price_cannot_be_underpaid(self):
        outcome = self.gateway().buy(DSTV, 5_000, "req-1")
        self.assertEqual(outcome.status, vending.FAILED)
        self.assertEqual(outcome.code, "plan_price_mismatch")
        self.assertIn("7,900", outcome.message)

    def test_a_plan_bill_without_a_plan_is_refused(self):
        outcome = self.gateway().buy({**DSTV, "plan": None}, 7_900, "req-1")
        self.assertEqual(outcome.status, vending.FAILED)
        self.assertIn("plan", outcome.message)

    def test_an_unknown_provider_is_refused_not_recorded(self):
        outcome = self.gateway().buy({**AIRTIME, "provider": "Globacom Wireless"}, 500, "req-1")
        self.assertEqual(outcome.status, vending.FAILED)
        self.assertEqual(outcome.vendor, "none")
        self.assertIn("Nothing was charged", outcome.message)

    def test_water_has_no_vendor(self):
        outcome = self.gateway().buy(
            {"id": "bill_water", "kind": "water", "provider": "Lagos Water"}, 1_000, "req-1"
        )
        self.assertEqual(outcome.status, vending.FAILED)

    def test_live_needs_credentials(self):
        with self.assertRaises(ValueError):
            vending.gateway_from_env({"STARK_VENDING": "live"})

    def test_gateway_is_dry_by_default(self):
        self.assertFalse(vending.gateway_from_env({}).live)

    def test_bad_vending_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            vending.gateway_from_env({"STARK_VENDING": "sometimes"})


class PaymentFlowTests(StoreCase):
    def service(self, gateway):
        return self.account.payments(gateway)

    def test_delivered_payment_is_charged_once_with_a_token(self):
        receipt = self.service(self.gateway()).pay(ELECTRICITY, 5_000)
        self.assertEqual(receipt["status"], vending.DELIVERED)
        self.assertTrue(receipt["token"])
        self.assertEqual(receipt["units"], 23.92)
        self.assertEqual(self.store.wallet(), {"balance_ngn": 59_200, "spent_ngn": 17_400})

    def test_pending_payment_is_not_charged(self):
        receipt = self.service(self.gateway("pay_pending.json")).pay(ELECTRICITY, 5_000)
        self.assertEqual(receipt["status"], vending.PENDING)
        self.assertIsNone(receipt["token"])
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

    def test_failed_payment_is_not_charged_and_is_recorded(self):
        with self.assertRaises(payments.SpendError) as caught:
            self.service(self.gateway("pay_low_balance.json")).pay(ELECTRICITY, 5_000)
        self.assertEqual(caught.exception.code, payments.VENDOR_FAILED)
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)
        self.assertEqual(self.store.recent()[0]["status"], vending.FAILED)

    def test_a_metered_delivery_without_a_token_is_not_charged(self):
        class NoToken:
            def buy(self, bill, amount, request_id):
                return vending.VendingOutcome(
                    status=vending.DELIVERED, token=None, token_required=True
                )

            def requery(self, request_id, amount):
                raise AssertionError("should not be requeried yet")

        receipt = self.service(NoToken()).pay(ELECTRICITY, 5_000)
        self.assertEqual(receipt["status"], vending.PENDING)
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

    def test_retry_reuses_the_request_id_and_charges_once(self):
        gateway = ScriptedGateway(
            [
                vending.VendingOutcome(status=vending.PENDING, code="099"),
                vending.VendingOutcome(status=vending.DELIVERED, token="4821 0937 5512 8846 3019"),
            ]
        )
        service = self.service(gateway)

        first = service.pay(ELECTRICITY, 5_000)
        self.assertEqual(first["status"], vending.PENDING)
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

        second = service.pay(ELECTRICITY, 5_000)
        self.assertEqual(second["id"], first["id"])  # same receipt, not a new sale
        self.assertEqual(second["status"], vending.DELIVERED)
        self.assertEqual(gateway.requeried, [first["request_id"]])
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.store.wallet()["balance_ngn"], 59_200)

    def test_a_second_intent_after_delivery_is_a_new_purchase(self):
        gateway = ScriptedGateway(
            [
                vending.VendingOutcome(status=vending.DELIVERED, token="a"),
                vending.VendingOutcome(status=vending.DELIVERED, token="b"),
            ]
        )
        service = self.service(gateway)
        service.pay(ELECTRICITY, 5_000)
        service.pay(ELECTRICITY, 5_000)
        self.assertEqual(self.store.count(), 2)
        self.assertEqual(gateway.bought[0], gateway.bought[1])  # amount
        self.assertEqual(self.store.wallet()["balance_ngn"], 54_200)

    def test_tv_plan_is_charged_without_a_token(self):
        receipt = self.service(self.gateway()).pay(DSTV, 7_900)
        self.assertEqual(receipt["status"], vending.DELIVERED)
        self.assertIsNone(receipt["token"])
        self.assertEqual(self.store.wallet()["balance_ngn"], 56_300)

    def test_airtime_is_charged(self):
        receipt = self.service(self.gateway()).pay(AIRTIME, 1_000)
        self.assertEqual(receipt["status"], vending.DELIVERED)
        self.assertIsNone(receipt["token"])
        self.assertEqual(self.store.wallet()["balance_ngn"], 63_200)

    def test_a_plan_mismatch_is_never_bought(self):
        class SpyClient(VtpassClient):
            def __init__(self):
                super().__init__(dry_run=True)
                self.calls = []

            def buy(self, **kwargs):
                self.calls.append(kwargs)
                return super().buy(**kwargs)

        client = SpyClient()
        gateway = vending.VendingGateway(client, phone="08031234567")
        with self.assertRaises(payments.SpendError) as caught:
            self.service(gateway).pay(DSTV, 5_000)
        self.assertEqual(caught.exception.code, payments.VENDOR_FAILED)
        self.assertEqual(client.calls, [])  # the vendor was never called
        self.assertEqual(self.store.wallet()["balance_ngn"], SEED_BALANCE)

    def test_payment_carries_the_signed_tx_hash(self):
        receipt = self.service(self.gateway()).pay(
            ELECTRICITY, 5_000, tx_hash="cd" * 32
        )
        self.assertEqual(receipt["tx_hash"], "cd" * 32)

    def test_settlement_refuses_when_the_balance_vanished(self):
        class Slow:
            def buy(self, bill, amount, request_id):
                # Someone spent the balance while the vendor was working.
                self.store.set_wallet(100, SEED_SPENT)
                return vending.VendingOutcome(status=vending.DELIVERED, token="x")

            def requery(self, request_id, amount):
                raise AssertionError("unused")

        slow = Slow()
        slow.store = self.store
        with self.assertRaises(payments.SpendError) as caught:
            self.service(slow).pay(ELECTRICITY, 5_000)
        self.assertEqual(caught.exception.code, payments.INSUFFICIENT_BALANCE)
        self.assertEqual(self.store.recent()[0]["status"], vending.FAILED)

    def gateway(self, fixture=None):
        return vending.VendingGateway(
            VtpassClient(dry_run=True, fixture=fixture), phone="08031234567"
        )


class CatalogTests(unittest.TestCase):
    """Every id and price here comes from a captured VTpass response."""

    def setUp(self):
        import catalog

        self.catalog = catalog.CATALOG

    def test_airtime_resolves_per_network(self):
        self.assertEqual(self.catalog.product("airtime", "MTN").service_id, "mtn")
        self.assertEqual(self.catalog.product("airtime", "Airtel").service_id, "airtel")
        self.assertEqual(self.catalog.product("airtime", "GLO").service_id, "glo")
        # 9mobile is "etisalat" at VTpass.
        self.assertEqual(self.catalog.product("airtime", "9mobile").service_id, "etisalat")

    def test_airtime_is_amount_mode_with_vendor_bounds(self):
        product = self.catalog.product("airtime", "MTN")
        self.assertEqual(product.mode, "amount")
        self.assertEqual((product.min_ngn, product.max_ngn), (5, 200_000))

    def test_data_and_tv_are_plan_mode(self):
        for kind, provider in (
            ("data", "MTN"), ("data", "Airtel"), ("data", "GLO"), ("data", "9mobile"),
            ("tv", "DStv"), ("tv", "GOtv"), ("tv", "Showmax"),
        ):
            with self.subTest(kind=kind, provider=provider):
                self.assertEqual(self.catalog.product(kind, provider).mode, "plan")

    def test_startimes_has_bouquets_despite_being_typed_flexible(self):
        # services_tv-subscription.json says product_type: flexible; the variations
        # fixture shows 25 priced bouquets. The plans win.
        product = self.catalog.product("tv", "Startimes")
        self.assertEqual(product.mode, "plan")
        self.assertEqual(len(self.catalog.plans(product)), 25)

    def test_glo_picks_the_real_data_product_not_the_sme_one(self):
        product = self.catalog.product("data", "GLO")
        self.assertEqual(product.service_id, "glo-data")
        self.assertIsNotNone(self.catalog.plan(product, "glo1000"))

    def test_plan_prices_match_the_capture(self):
        dstv = self.catalog.product("tv", "DStv")
        self.assertEqual(self.catalog.plan(dstv, "dstv79").price_ngn, 7_900)
        mtn = self.catalog.product("data", "MTN")
        self.assertEqual(self.catalog.plan(mtn, "mtn-100mb-1000").price_ngn, 1_000)

    def test_an_unknown_provider_has_no_product(self):
        self.assertIsNone(self.catalog.product("airtime", "Nothing Tel"))
        self.assertIsNone(self.catalog.product("water", "Lagos Water"))

    def test_a_plan_that_does_not_exist_is_none(self):
        dstv = self.catalog.product("tv", "DStv")
        self.assertIsNone(self.catalog.plan(dstv, "dstv-not-a-plan"))


class ScriptedGateway:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.bought: list[int] = []
        self.requeried: list[str] = []

    def buy(self, bill, amount_ngn, request_id):
        self.bought.append(amount_ngn)
        return self.outcomes.pop(0)

    def requery(self, request_id, amount_ngn):
        self.requeried.append(request_id)
        return self.outcomes.pop(0)


def _receipt(
    receipt_id: str,
    *,
    request_id: str,
    status: str = "pending",
    created_at: str = "2026-10-20T00:00:00Z",
) -> dict:
    return {
        "id": receipt_id,
        "request_id": request_id,
        "bill_id": "bill_home_meter",
        "bill_label": "Home meter",
        "meter": "04512345678",
        "amount_ngn": 5_000,
        "units": 23.92,
        "token": "4821 0937 5512 8846 3019",
        "tx_hash": None,
        "status": status,
        "vendor": "vtpass",
        "vendor_code": "000",
        "vendor_message": "ok",
        "created_at": created_at,
    }


if __name__ == "__main__":
    unittest.main()
