#!/usr/bin/env python3
"""Tests for the VTpass client. Zero dependencies.

    python3 -m unittest test_vtpass -v
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import unittest
from unittest import mock

from app.modules.vending import vtpass
from app.modules.vending.vtpass import VtpassClient, VtpassError, extract_token, new_request_id

METER = "04512345678"


def client(**kwargs) -> VtpassClient:
    """A dry-run client, pinned to the sandbox so tests never depend on env."""
    kwargs.setdefault("dry_run", True)
    kwargs.setdefault("env", "sandbox")
    return VtpassClient(**kwargs)


class TestRequestId(unittest.TestCase):
    def test_format_matches_vtpass_convention(self):
        rid = new_request_id()
        self.assertRegex(rid, r"^\d{12}[0-9a-f]{8}$")
        self.assertEqual(len(rid), 20)

    def test_ids_are_unique(self):
        ids = {new_request_id() for _ in range(200)}
        self.assertEqual(len(ids), 200, "request_id collision — retries would duplicate")


class TestVariations(unittest.TestCase):
    def test_reads_captured_live_response(self):
        variations = client().list_variations()
        codes = {v["variation_code"] for v in variations}
        self.assertEqual(codes, {"prepaid", "postpaid"})

    def test_tolerates_vtpass_misspelling(self):
        """Their API returns 'varations' as well as 'variations'."""
        payload = {"content": {"varations": [{"variation_code": "prepaid"}]}}
        with mock.patch.object(VtpassClient, "_fixture", return_value=payload):
            variations = client().list_variations()
        self.assertEqual(variations[0]["variation_code"], "prepaid")

    def test_empty_variations_raises(self):
        with mock.patch.object(VtpassClient, "_fixture", return_value={"content": {}}):
            with self.assertRaises(VtpassError) as ctx:
                client().list_variations()
        self.assertEqual(ctx.exception.code, "no_variations")


class TestVerify(unittest.TestCase):
    def test_returns_customer_details(self):
        """Captured live 2026-10-22 with the sandbox test meter."""
        info = client().verify_meter(METER)
        self.assertEqual(info["Customer_Name"], "TESTMETER1")
        self.assertEqual(info["Meter_Number"], "68100017372")
        self.assertIs(info["WrongBillersCode"], False)

    def test_code_000_with_wrong_billers_code_is_a_refusal(self):
        """VTpass returns code "000" for a meter it could not resolve.

        Captured live 2026-10-22: a wrong meter is HTTP 200, code "000", and
        `WrongBillersCode: true` inside `content`. Trusting the envelope would
        let the agent buy for a meter the vendor already rejected.
        """
        with self.assertRaises(VtpassError) as ctx:
            client(fixture="merchant-verify_wrong.json").verify_meter(METER)
        self.assertEqual(ctx.exception.code, "016")
        self.assertIn("not a valid", ctx.exception.description)
        self.assertIn("couldn't find that meter", ctx.exception.user_message)

    def test_non_zero_code_raises(self):
        payload = {"code": "016", "response_description": "INVALID METER NUMBER"}
        with mock.patch.object(VtpassClient, "_fixture", return_value=payload):
            with self.assertRaises(VtpassError) as ctx:
                client().verify_meter(METER)
        self.assertEqual(ctx.exception.code, "016")
        self.assertIn("couldn't find that meter", ctx.exception.user_message)


class TestBuy(unittest.TestCase):
    def test_delivered_token(self):
        res = client().buy_electricity(METER, 5000, "08031234567")
        self.assertTrue(res.delivered)
        self.assertFalse(res.pending)
        self.assertEqual(res.units, "23.92")
        self.assertEqual(res.token, "48210937551288463019")

    def test_pending_is_not_success(self):
        res = client(fixture="pay_pending.json").buy_electricity(METER, 5000, "08031234567")
        self.assertFalse(res.delivered, "pending must never report as delivered")
        self.assertTrue(res.pending)
        self.assertIsNone(res.token)

    def test_low_balance_raises_with_speakable_message(self):
        with self.assertRaises(VtpassError) as ctx:
            client(fixture="pay_low_balance.json").buy_electricity(METER, 5000, "08031234567")
        err = ctx.exception
        self.assertEqual(err.code, "018")
        self.assertFalse(err.retryable)
        self.assertIn("float is low", err.user_message)

    def test_duplicate_raises_and_is_not_retryable(self):
        with self.assertRaises(VtpassError) as ctx:
            client(fixture="pay_duplicate.json").buy_electricity(METER, 5000, "08031234567")
        self.assertEqual(ctx.exception.code, "019")
        self.assertFalse(ctx.exception.retryable)

    def test_biller_unreachable_is_retryable(self):
        err = VtpassError("030")
        self.assertTrue(err.retryable)

    def test_rejects_under_minimum(self):
        with self.assertRaises(ValueError):
            client().buy_electricity(METER, 499, "08031234567")

    def test_reads_the_top_level_token_and_units_shape(self):
        """The shape documented for a real vend: token and units at the top level."""
        payload = {
            "code": "000",
            "response_description": "TRANSACTION SUCCESSFUL",
            "requestId": "2025031013366434255",
            "amount": 2000,
            "purchased_code": "Token : 26362054405982757802",
            "token": "Token : 26362054405982757802",
            "units": "79.9 kWh",
            "content": {"transactions": {"status": "delivered"}},
        }
        live = VtpassClient(dry_run=False, env="sandbox")
        with mock.patch.object(VtpassClient, "_http", return_value=payload):
            res = live.buy_electricity(METER, 2000, "08031234567")

        self.assertTrue(res.delivered)
        self.assertEqual(res.token, "26362054405982757802")
        self.assertEqual(res.units, "79.9 kWh")
        self.assertEqual(res.amount_ngn, 2000)

    def test_not_whitelisted_is_a_clear_refusal(self):
        """Captured live 2026-10-22: a sandbox account without the product enabled."""
        with self.assertRaises(VtpassError) as ctx:
            client(fixture="pay_not_whitelisted.json").buy_electricity(
                METER, 5000, "08031234567"
            )
        err = ctx.exception
        self.assertEqual(err.code, "028")
        self.assertFalse(err.retryable)
        self.assertIn("NOT WHITELISTED", err.description)

    def test_reuses_supplied_request_id_on_the_wire(self):
        """A retry must post the same request_id, or VTpass books a second sale."""
        sent: dict = {}

        def fake_http(*args, **kwargs):
            sent["payload"] = args[2] if len(args) > 2 else kwargs.get("payload")
            return {
                "code": "000",
                "response_description": "TRANSACTION SUCCESSFUL",
                "content": {
                    "transactions": {
                        "status": "delivered",
                        "token": "4821 0937 5512 8846 3019",
                        "units": "23.92",
                    }
                },
            }

        live = VtpassClient(dry_run=False, env="sandbox")
        with mock.patch.object(VtpassClient, "_http", side_effect=fake_http):
            res = live.buy_electricity(METER, 5000, "08031234567", request_id="fixed-abc")

        payload = sent["payload"]
        self.assertEqual(payload["request_id"], "fixed-abc")
        self.assertEqual(res.request_id, "fixed-abc", "must fall back to the id we sent")
        # The wire shape VTpass expects, per their SDK.
        self.assertEqual(payload["serviceID"], "ikeja-electric")
        self.assertEqual(payload["billersCode"], METER)
        self.assertEqual(payload["variation_code"], "prepaid")
        self.assertEqual(payload["amount"], 5000)
        self.assertEqual(payload["phone"], "08031234567")


class TestTokenExtraction(unittest.TestCase):
    def test_prefers_content_transactions_token(self):
        raw = {"content": {"transactions": {"token": "4821 0937 5512 8846 3019"}}}
        self.assertEqual(extract_token(raw), "48210937551288463019")

    def test_falls_back_to_purchased_code(self):
        raw = {"purchased_code": "Token : 1234 5678 9012 3456 7890"}
        self.assertEqual(extract_token(raw), "12345678901234567890")

    def test_returns_none_when_absent(self):
        self.assertIsNone(extract_token({"content": {"transactions": {"token": None}}}))


class TestParsing(unittest.TestCase):
    def test_bare_json_string_on_401(self):
        """The real sandbox returns '"Invalid Credentials."' — a JSON string."""
        with self.assertRaises(VtpassError) as ctx:
            VtpassClient._parse(b'"Invalid Credentials."', 401)
        self.assertEqual(ctx.exception.code, "invalid_credentials")
        self.assertEqual(ctx.exception.http_status, 401)

    def test_non_json_body_does_not_crash(self):
        with self.assertRaises(VtpassError) as ctx:
            VtpassClient._parse(b"<html>502 Bad Gateway</html>", 502)
        self.assertEqual(ctx.exception.code, "invalid_response")

    def test_normal_body_passes_through(self):
        self.assertEqual(VtpassClient._parse(b'{"code":"000"}', 200), {"code": "000"})


class TestDryRunSafety(unittest.TestCase):
    def test_dry_run_never_touches_the_network(self):
        boom = AssertionError("dry run opened a network connection")
        with mock.patch("urllib.request.urlopen", side_effect=boom):
            client().list_variations()
            client().verify_meter(METER)
            client().buy_electricity(METER, 5000, "08031234567")

    def test_live_mode_without_credentials_raises_cleanly(self):
        live = VtpassClient(dry_run=False, env="sandbox", username="", password="")
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.status = 401
            urlopen.return_value.__enter__.return_value.read.return_value = (
                b'"Invalid Credentials."'
            )
            with self.assertRaises(VtpassError) as ctx:
                live.verify_meter(METER)
        self.assertEqual(ctx.exception.code, "invalid_credentials")


class TestCli(unittest.TestCase):
    """End-to-end wiring. The unit tests above cannot see argparse mistakes."""

    def run_cli(self, *argv: str) -> int:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return vtpass.main(list(argv))

    def test_variations(self):
        self.assertEqual(self.run_cli("variations"), 0)

    def test_variations_accepts_service(self):
        self.assertEqual(self.run_cli("variations", "--service", "eko-electric"), 0)

    def test_verify(self):
        self.assertEqual(self.run_cli("verify", "--meter", METER), 0)

    def test_buy_delivered(self):
        self.assertEqual(
            self.run_cli("buy", "--meter", METER, "--amount", "5000",
                         "--phone", "08031234567"),
            0,
        )

    def test_fixture_flag_works_after_subcommand(self):
        """Regression: --fixture used to be rejected after the subcommand."""
        self.assertEqual(
            self.run_cli("buy", "--meter", METER, "--amount", "5000",
                         "--phone", "08031234567", "--fixture", "pay_pending.json"),
            0,
        )

    def test_live_flag_accepted_after_subcommand(self):
        rc = self.run_cli("variations", "--live")
        self.assertIn(rc, (0, 1), "--live must parse; network outcome may vary")

    def test_low_balance_exits_1(self):
        self.assertEqual(
            self.run_cli("buy", "--meter", METER, "--amount", "5000",
                         "--phone", "08031234567", "--fixture", "pay_low_balance.json"),
            1,
        )

    def test_below_minimum_exits_2_without_traceback(self):
        """Regression: ValueError used to escape as an uncaught traceback."""
        self.assertEqual(
            self.run_cli("buy", "--meter", METER, "--amount", "200",
                         "--phone", "08031234567"),
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
