"""The money flow end to end: deposit → vault → float → purchase → withdrawal.

Rails are faked at their HTTP clients (chain, Bachs, 1Click, VTpass), so every
state transition runs against the real Postgres schema without a network. What
these do NOT prove: that the live services answer in the modeled shapes. That is
recorded in docs/HANDOFF.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import unittest
from decimal import Decimal

from app.common.api_error import ApiError
from app.modules.bachs import bachs
from app.modules.bachs.bachs import BachsError
from app.modules.bachs.bachs_webhook_service import BachsWebhookService
from app.modules.chain import near_tx, vault_chain
from app.modules.chain.treasury_chain import SignedTransfer
from app.modules.chain.vault_chain import ChainResult, VaultChain
from app.modules.intents.one_click import OneClickError
from app.modules.liquidity.float_service import FloatService, FloatSettings
from app.modules.payment import payment_service
from app.modules.vault.vault_service import AuthorisationFailed, VaultService
from app.modules.vending import vending
from app.modules.wallet.crypto_withdrawal_service import (
    CryptoPayoutSettings,
    CryptoWithdrawalService,
)
from app.modules.wallet.deposit_service import DepositService, FundingSettings
from app.modules.wallet.withdrawal_service import WithdrawalService
from tests import support

KEY = near_tx.KeyPair.from_secret(bytes(range(32)))
AGENT = near_tx.KeyPair.from_secret(bytes(range(1, 33)))
METER = "04512345678"
ELECTRICITY = {"id": "bill_home", "label": "Home meter", "kind": "electricity",
               "reference": METER, "provider": "ikeja-electric", "meter_type": "prepaid"}


# --- fakes ---------------------------------------------------------------------


class FakeChain:
    """Records every chain write; can be told to fail the next call."""

    broadcast = True

    def __init__(self):
        self.calls: list[tuple] = []
        self.fail_with: Exception | None = None
        self.policy = {"monthly_cap_ngn": "30000", "per_payment_cap_ngn": "10000",
                       "allowed_meters": [METER]}
        self.rpc = self
        self.payment_id = 0

    def vault_id(self, account_id):
        return f"u-{account_id[-8:]}.stark-vault.testnet"

    def _maybe_fail(self):
        if self.fail_with is not None:
            err, self.fail_with = self.fail_with, None
            raise err

    def create(self, vault_id, **policy):
        self._maybe_fail()
        self.calls.append(("create", vault_id, policy))
        return ChainResult("ab" * 32, None, True)

    def pay(self, vault_id, meter, amount):
        self._maybe_fail()
        self.payment_id += 1
        self.calls.append(("pay", meter, amount))
        return ChainResult("cd" * 32, {"payment_id": self.payment_id}, True)

    def pay_approved(self, vault_id, meter, amount):
        self._maybe_fail()
        self.payment_id += 1
        self.calls.append(("pay_approved", meter, amount))
        return ChainResult("ef" * 32, {"payment_id": self.payment_id}, True)

    def call(self, vault_id, method, args):
        self._maybe_fail()
        self.calls.append((method, args))
        if method == "set_policy":
            self.policy = args
        return ChainResult("01" * 32, None, True)

    def view(self, vault_id, method, args):
        assert method == "get_policy"
        return self.policy

    def methods(self):
        return [c[0] for c in self.calls]


class FakeVtpass:
    def __init__(self, balance=500_000):
        self.value = balance
        self.reads = 0

    def balance(self):
        self.reads += 1
        return self.value


class FakeBachs:
    def __init__(self):
        self.checkouts: dict[str, dict] = {}
        self.payouts: list[dict] = []
        self.destination_status = {"status": "approved", "is_usable": True}
        self.resolved = True
        self.payout_error: BachsError | None = None

    def create_checkout(self, *, amount_ngn, reference, metadata, success_url,
                        expires_in_minutes):
        checkout = {"checkout_id": f"chk_{reference[-6:]}", "status": "open",
                    "checkout_url": f"https://checkout.bachs.io/c/{reference[-6:]}",
                    "expires_at": "2099-01-01T00:00:00.000Z", "amount": amount_ngn,
                    "metadata": metadata}
        self.checkouts[checkout["checkout_id"]] = checkout
        return checkout

    def get_checkout(self, checkout_id):
        return self.checkouts[checkout_id]

    def banks(self):
        return [{"name": "Guaranty Trust Bank", "code": "058"}]

    def resolve_account(self, bank_code, account_number):
        if not self.resolved:
            return {"resolved": False, "account_name": None}
        return {"resolved": True, "account_name": "ADA OKAFOR",
                "account_number": account_number}

    def create_destination(self, *, bank_code, account_number, name, metadata):
        return {"id": f"pd_{account_number}", "status": "pending_review",
                "is_usable": False, "account_name": name, "bank_name": "Guaranty Trust Bank"}

    def get_destination(self, destination_id):
        return {"id": destination_id, **self.destination_status}

    def create_payout(self, *, destination, amount_ngn, reference, narration):
        if self.payout_error is not None:
            raise self.payout_error
        payout = {"id": f"pay_{reference[-6:]}", "status": "pending",
                  "reference": reference, "amount": amount_ngn, "destination": destination}
        self.payouts.append(payout)
        return payout


class FakeOneClick:
    def __init__(self):
        self.status_reply = {"status": "PENDING_DEPOSIT", "swapDetails": {}}
        self.quotes: list[dict] = []

    def tokens(self):
        return [{"assetId": "nep141:tron-usdt", "symbol": "USDT", "blockchain": "tron"}]

    def quote(self, *, origin_asset, usdc_out, recipient, deadline, dry=False):
        self.quotes.append({"origin": origin_asset, "usdc_out": usdc_out,
                            "recipient": recipient})
        return {"quote": {"depositAddress": "TXdeposit1", "depositMemo": None,
                          "amountIn": "13460000", "amountInFormatted": "13.46",
                          "deadline": deadline}}

    def status(self, address, memo):
        return self.status_reply

    def submit_deposit(self, address, tx_hash, memo):
        return self.status_reply


class FakeAccounts:
    def __init__(self, limits):
        self.limits = limits

    def state(self, account_id):
        class State:
            pass
        state = State()
        state.limits = self.limits
        return state


def limits():
    from app.modules.agent import agent as agent_layer
    return agent_layer.Limits(30_000, 10_000, frozenset({METER}))


class MoneyCase(unittest.TestCase):
    balance = 0

    def setUp(self):
        self.account = support.TempAccount()
        self.db = self.account.db
        self.receipts = self.account.store.raw
        # An opened account always has a wallet row, even at ₦0.
        self.receipts.set_wallet(self.account.id, self.balance, 0)
        self.chain = FakeChain()
        self.vaults = VaultService(self.db, self.chain, FakeAccounts(limits()))

    def tearDown(self):
        self.account.close()

    def wallet(self):
        return self.receipts.wallet(self.account.id)

    def ops(self):
        return self.db.query(
            "SELECT method, status FROM chain_ops WHERE user_id = $1 ORDER BY seq",
            [self.account.id],
        )


# --- the transaction encoders --------------------------------------------------


class ActionEncodingTests(unittest.TestCase):
    def test_function_call_key_is_scoped_to_pay_on_the_vault(self):
        raw = near_tx.add_function_call_key_action(
            AGENT.public, receiver_id="u-1.stark.testnet", method_names=["pay"],
            allowance=5,
        )
        self.assertEqual(raw[0], 5, "Action::AddKey")
        self.assertEqual(raw[1:34], b"\x00" + AGENT.public)
        self.assertEqual(raw[34:42], bytes(8), "access key nonce 0")
        self.assertEqual(raw[42], 0, "AccessKeyPermission::FunctionCall")
        self.assertEqual(raw[43], 1, "Some(allowance)")
        self.assertEqual(int.from_bytes(raw[44:60], "little"), 5)
        self.assertIn(b"u-1.stark.testnet", raw)
        self.assertTrue(raw.endswith(b"\x01\x00\x00\x00\x03\x00\x00\x00pay"))

    def test_full_access_is_never_granted(self):
        raw = near_tx.add_function_call_key_action(
            AGENT.public, receiver_id="v", method_names=["pay"])
        self.assertEqual(raw[42], 0, "never AccessKeyPermission::FullAccess (1)")
        self.assertEqual(raw[43], 0, "None allowance")

    def test_global_contract_actions(self):
        self.assertEqual(near_tx.use_global_contract_action("stark.testnet"),
                         b"\x0a\x01" + b"\x0d\x00\x00\x00stark.testnet")
        self.assertEqual(near_tx.deploy_global_contract_action(b"wasm"),
                         b"\x09\x04\x00\x00\x00wasm\x01")

    def test_pay_encoding_is_unchanged_by_the_generic_encoder(self):
        args = dict(signer_id="a.testnet", public_key=KEY.public, nonce=1,
                    receiver_id="v.testnet", block_hash=bytes(32))
        self.assertEqual(
            near_tx.encode_pay_transaction(meter=METER, amount_ngn=5000, **args),
            near_tx.encode_transaction(actions=[near_tx.function_call_action(
                "pay", near_tx.pay_args(METER, 5000))], **args),
        )

    def test_success_value_decodes_and_panics_become_refusals(self):
        ok = {"status": {"SuccessValue": base64.b64encode(b'{"payment_id":3}').decode()}}
        self.assertEqual(near_tx.success_value(ok), {"payment_id": 3})
        self.assertIsNone(near_tx.success_value({"status": {"SuccessValue": ""}}))
        refused = {"status": {"Failure": {"ActionError": {"kind": {"FunctionCallError": {
            "ExecutionError": "Smart contract panicked: That would go over your monthly limit."
        }}}}}}
        with self.assertRaises(near_tx.ContractRefused) as caught:
            near_tx.success_value(refused)
        self.assertEqual(caught.exception.message, "That would go over your monthly limit.")


class VaultChainTests(unittest.TestCase):
    def chain(self, **overrides):
        settings = dict(rpc=near_tx.NearRpc("http://127.0.0.1:9"), funder_id="stark.testnet",
                        funder_key=KEY, agent_key=AGENT, treasury_id="stark.testnet",
                        code="global:stark.testnet", storage_yocto=10, broadcast=False)
        settings.update(overrides)
        return VaultChain(**settings)

    def test_vault_ids_are_short_lowercase_sub_accounts(self):
        chain = self.chain()
        self.assertEqual(chain.vault_id("acct_0123456789abcdef"),
                         "u-0123456789abcdef.stark.testnet")
        odd = chain.vault_id("test_Has Spaces!")
        self.assertTrue(odd.startswith("u-") and odd.endswith(".stark.testnet"))
        self.assertEqual(odd, odd.lower())

    def test_dry_chain_signs_offline(self):
        result = self.chain().create("u-1.stark.testnet", monthly_cap_ngn=30_000,
                                     per_payment_cap_ngn=10_000, meters=[METER])
        self.assertFalse(result.broadcast)
        self.assertEqual(len(result.tx_hash), 64)

    def test_create_is_one_transaction_of_five_actions(self):
        captured = {}
        original = near_tx.sign_transaction

        def spy(**kwargs):
            captured.update(kwargs)
            return original(**kwargs)

        near_tx.sign_transaction = spy
        try:
            self.chain().create("u-1.stark.testnet", monthly_cap_ngn=30_000,
                                per_payment_cap_ngn=10_000, meters=[METER])
        finally:
            near_tx.sign_transaction = original
        tags = [action[0] for action in captured["actions"]]
        self.assertEqual(tags, [0, 3, 10, 5, 2],
                         "create, fund storage, use code, add the pay key, init")
        self.assertEqual(captured["signer_id"], "stark.testnet")
        self.assertEqual(captured["receiver_id"], "u-1.stark.testnet")
        init = json.loads(captured["actions"][4][1 + 4 + 3 + 4:].split(b"\x00\xe8")[0]
                          .rsplit(b"}", 1)[0] + b"}")
        self.assertEqual(init["funder"], "stark.testnet")
        self.assertEqual(init["allowed_meters"], [METER])

    def test_pay_is_signed_as_the_vault_with_the_agent_key(self):
        captured = {}
        original = near_tx.sign_transaction

        def spy(**kwargs):
            captured.update(kwargs)
            return original(**kwargs)

        near_tx.sign_transaction = spy
        try:
            self.chain().pay("u-1.stark.testnet", METER, 5000)
        finally:
            near_tx.sign_transaction = original
        self.assertEqual(captured["signer_id"], "u-1.stark.testnet")
        self.assertIs(captured["key"], AGENT)

    def test_config_is_all_or_nothing(self):
        self.assertIsNone(vault_chain.chain_from_env({}))
        with self.assertRaises(ValueError):
            vault_chain.chain_from_env({"STARK_FUNDER_ACCOUNT": "stark.testnet"})
        chain = vault_chain.chain_from_env({
            "STARK_FUNDER_ACCOUNT": "stark.testnet",
            "STARK_FUNDER_KEY": "ed25519:" + near_tx.b58encode(bytes(range(32))),
            "STARK_AGENT_KEY": "ed25519:" + near_tx.b58encode(bytes(range(1, 33))),
        })
        self.assertFalse(chain.broadcast)
        self.assertEqual(chain.code, "global:stark.testnet")
        self.assertEqual(chain.storage_yocto, 2 * 10 ** 23)


# --- the vault and Postgres stay in step ------------------------------------------


class VaultServiceTests(MoneyCase):
    def test_a_credit_creates_the_vault_and_lands(self):
        self.vaults.ensure(self.account.id)
        self.vaults.credit(self.account.id, 5000, "dep_1")
        self.assertEqual(self.chain.methods(), ["create", "fund"])
        self.assertEqual(self.ops(), [{"method": "fund", "status": "done"}])

    def test_the_same_reference_is_queued_once(self):
        self.vaults.ensure(self.account.id)
        self.vaults.credit(self.account.id, 5000, "dep_1")
        self.vaults.credit(self.account.id, 5000, "dep_1")
        self.assertEqual(self.chain.methods().count("fund"), 1)

    def test_a_network_failure_stays_pending_and_blocks_payment(self):
        self.vaults.ensure(self.account.id)
        self.chain.fail_with = near_tx.NearRpcError("timeout")
        self.vaults.credit(self.account.id, 5000, "dep_1")
        self.assertEqual(self.ops(), [{"method": "fund", "status": "pending"}])
        self.chain.fail_with = near_tx.NearRpcError("still down")
        with self.assertRaises(AuthorisationFailed):
            self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.assertNotIn("pay", self.chain.methods(),
                         "never sign against a vault that is behind")
        # The network comes back: the deposit lands first, then the payment.
        auth = self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.assertEqual(self.chain.methods()[-2:], ["fund", "pay"])
        self.assertEqual(auth.payment_id, 1)

    def test_a_contract_refusal_is_failed_not_retried(self):
        self.vaults.ensure(self.account.id)
        self.chain.fail_with = near_tx.ContractRefused("That's more than the balance")
        self.vaults.debit(self.account.id, 5000, "wd_1")
        self.assertEqual(self.ops(), [{"method": "debit", "status": "failed"}])
        self.assertEqual(self.vaults.flush(self.account.id), 0)

    def test_a_contract_refusal_on_pay_is_spoken_plainly(self):
        self.chain.fail_with = None
        self.vaults.ensure(self.account.id)
        self.chain.fail_with = near_tx.ContractRefused("That would go over your monthly limit.")
        with self.assertRaises(AuthorisationFailed) as caught:
            self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.assertEqual(caught.exception.message,
                         "That would go over your monthly limit. Nothing was charged.")

    def test_policy_is_synced_before_paying(self):
        self.vaults.ensure(self.account.id)
        self.chain.policy = {"monthly_cap_ngn": "1", "per_payment_cap_ngn": "1",
                             "allowed_meters": []}
        self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.assertEqual(self.chain.methods()[-2:], ["set_policy", "pay"])
        self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.assertEqual(self.chain.methods()[-2:], ["pay", "pay"], "no resync when equal")

    def test_an_approved_payment_uses_the_owner_path(self):
        self.vaults.authorise_payment(self.account.id, METER, 40_000, approved=True)
        self.assertEqual(self.chain.methods()[-1], "pay_approved")

    def test_a_refund_follows_the_recorded_payment(self):
        auth = self.vaults.authorise_payment(self.account.id, METER, 1000)
        self.vaults.record_payment(self.account.id, "rcpt_x", auth.payment_id)
        self.vaults.refund_receipt(self.account.id, "rcpt_x")
        self.vaults.refund_receipt(self.account.id, "rcpt_x")
        self.assertEqual(self.chain.calls[-1], ("refund", {"payment_id": auth.payment_id}))
        self.assertEqual(self.chain.methods().count("refund"), 1)

    def test_no_chain_means_no_writes_and_no_authorisation(self):
        offline = VaultService(self.db, None, FakeAccounts(limits()))
        offline.credit(self.account.id, 5000, "dep_1")
        self.assertIsNone(offline.authorise_payment(self.account.id, METER, 1000))
        self.assertEqual(self.ops(), [])


# --- the float ---------------------------------------------------------------------


class FloatServiceTests(MoneyCase):
    def floats(self, balance=500_000, bachs_client=None, destination=None):
        self.vtpass = FakeVtpass(balance)
        return FloatService(self.db, self.vtpass, bachs_client,
                            FloatSettings(low_water_ngn=100_000, target_ngn=500_000,
                                          funding_destination=destination))

    def tearDown(self):
        self.db.query("DELETE FROM float_refills WHERE id LIKE 'refill_%'"
                      " AND created_at >= $1", [self.started])
        super().tearDown()

    def setUp(self):
        super().setUp()
        self.started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1))
        # Refills are Stark-wide; start each test with none open.
        self.db.query("UPDATE float_refills SET status = 'paid'"
                      " WHERE status IN ('requested', 'sent', 'manual')")

    def test_covers_a_purchase_that_fits(self):
        self.floats().ensure_can_cover(5000)

    def test_refuses_and_refills_when_it_cannot_cover(self):
        floats = self.floats(balance=1000)
        with self.assertRaises(ApiError) as caught:
            floats.ensure_can_cover(5000)
        self.assertEqual(caught.exception.code, "float_low")
        self.assertIn("nothing was charged", caught.exception.message)
        refill = self.db.one("SELECT * FROM float_refills WHERE status = 'manual'"
                             " ORDER BY created_at DESC LIMIT 1")
        self.assertEqual(int(refill["amount_ngn"]), 500_000, "rounded up to ₦10,000")

    def test_pending_purchases_count_as_spent(self):
        floats = self.floats(balance=10_000)
        self.receipts.create(self.account.id, {
            "id": "rcpt_p", "request_id": "req_p", "bill_id": "b", "bill_label": "b",
            "amount_ngn": 8000, "status": "pending", "created_at": "2026-11-03T00:00:00Z",
        })
        self.assertLessEqual(floats.available(), 2000)
        with self.assertRaises(ApiError):
            floats.ensure_can_cover(5000)

    def test_an_automatic_refill_is_a_bachs_payout_and_only_one_is_open(self):
        fake = FakeBachs()
        floats = self.floats(balance=50_000, bachs_client=fake, destination="pd_vtpass")
        first = floats.request_refill()
        second = floats.request_refill()
        self.assertEqual(first["status"], "sent")
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(len(fake.payouts), 1)
        self.assertEqual(fake.payouts[0]["amount"], 450_000)
        self.assertTrue(floats.on_payout(first["id"], paid=True))
        self.assertFalse(floats.on_payout("wd_other", paid=True))

    def test_balance_reads_are_cached(self):
        floats = self.floats()
        floats.balance()
        floats.balance()
        self.assertEqual(self.vtpass.reads, 1)
        floats.balance(fresh=True)
        self.assertEqual(self.vtpass.reads, 2)


# --- a purchase: float, vault, vendor, refund ------------------------------------------


class ScriptedGateway:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.bought = 0

    def buy(self, bill, amount, request_id):
        self.bought += 1
        return self.outcomes.pop(0)

    def requery(self, request_id, amount):
        return self.outcomes.pop(0)


class PaymentPathTests(MoneyCase):
    balance = 64_200

    def service(self, gateway, *, float_balance=500_000):
        floats = FloatService(self.db, FakeVtpass(float_balance), None,
                              FloatSettings(100_000, 500_000, None))
        return payment_service.PaymentService(self.receipts, gateway, vaults=self.vaults,
                                              floats=floats)

    def test_a_delivery_carries_the_vault_tx_and_charges_once(self):
        gateway = ScriptedGateway(vending.VendingOutcome(status=vending.DELIVERED, token="1234"))
        receipt = self.service(gateway).pay(self.account.id, ELECTRICITY, 5000)
        self.assertEqual(receipt["tx_hash"], "cd" * 32)
        self.assertEqual(self.wallet()["balance_ngn"], 59_200)
        self.assertEqual(self.chain.methods()[-1], "pay")

    def test_a_vendor_failure_refunds_the_vault(self):
        gateway = ScriptedGateway(vending.VendingOutcome(status=vending.FAILED, code="016",
                                                         message="bad meter"))
        with self.assertRaises(payment_service.SpendError):
            self.service(gateway).pay(self.account.id, ELECTRICITY, 5000)
        self.assertEqual(self.chain.calls[-1][0], "refund")
        self.assertEqual(self.wallet()["balance_ngn"], 64_200)

    def test_a_low_float_refuses_before_signing_or_recording(self):
        gateway = ScriptedGateway()
        with self.assertRaises(ApiError) as caught:
            self.service(gateway, float_balance=1000).pay(self.account.id, ELECTRICITY, 5000)
        self.assertEqual(caught.exception.code, "float_low")
        self.assertNotIn("pay", self.chain.methods())
        self.assertEqual(gateway.bought, 0)
        self.assertEqual(self.receipts.count(self.account.id), 0)

    def test_a_vault_refusal_stops_the_purchase(self):
        self.vaults.ensure(self.account.id)
        self.chain.fail_with = near_tx.ContractRefused("That meter isn't on your list.")
        gateway = ScriptedGateway()
        with self.assertRaises(payment_service.SpendError) as caught:
            self.service(gateway).pay(self.account.id, ELECTRICITY, 5000)
        self.assertEqual(caught.exception.code, payment_service.AUTHORISATION_FAILED)
        self.assertEqual(gateway.bought, 0)
        self.assertEqual(self.receipts.count(self.account.id), 0)

    def test_a_retry_of_a_pending_purchase_does_not_sign_again(self):
        gateway = ScriptedGateway(
            vending.VendingOutcome(status=vending.PENDING),
            vending.VendingOutcome(status=vending.DELIVERED, token="1234"),
        )
        service = self.service(gateway)
        service.pay(self.account.id, ELECTRICITY, 5000)
        service.pay(self.account.id, ELECTRICITY, 5000)
        self.assertEqual(self.chain.methods().count("pay"), 1)
        self.assertEqual(self.wallet()["balance_ngn"], 59_200)


# --- deposits ---------------------------------------------------------------------------


class DepositTests(MoneyCase):
    def deposits(self, *, bachs_client=None, crypto=True):
        self.bachs = bachs_client or FakeBachs()
        self.one_click = FakeOneClick()
        settings = FundingSettings(app_url="https://app.test",
                                   treasury_account="stark-treasury.near" if crypto else None,
                                   usdc_ngn_rate=Decimal("1500") if crypto else None)
        return DepositService(self.db, self.receipts, self.vaults, self.bachs,
                              self.one_click, settings)

    def test_a_bank_deposit_is_a_checkout_with_our_reference(self):
        deposit = self.deposits().start(self.account.id, 20_000, "bank", None)
        self.assertEqual(deposit["status"], "open")
        self.assertTrue(deposit["pay"]["checkout_url"].startswith("https://checkout"))
        checkout = next(iter(self.bachs.checkouts.values()))
        self.assertEqual(checkout["metadata"]["deposit_id"], deposit["id"])

    def test_the_webhook_credits_once_and_mirrors_to_the_vault(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "bank", None)
        event = {"reference": deposit["id"], "status": "SUCCEEDED"}
        service.on_collection("collection.succeeded", event)
        service.on_collection("collection.succeeded", event)
        self.assertEqual(self.wallet()["balance_ngn"], 20_000)
        self.assertEqual(service.get(self.account.id, deposit["id"])["status"], "credited")
        self.assertEqual([c[0] for c in self.chain.calls].count("fund"), 1)

    def test_a_missed_webhook_is_caught_by_the_poll(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "bank", None)
        next(iter(self.bachs.checkouts.values()))["status"] = "completed"
        service.poll_open()
        service.on_collection("collection.succeeded",
                              {"reference": deposit["id"], "status": "SUCCEEDED"})
        self.assertEqual(self.wallet()["balance_ngn"], 20_000)

    def test_accepted_waits_for_confirmation(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "bank", None)
        service.on_collection("collection.succeeded",
                              {"reference": deposit["id"], "status": "ACCEPTED"})
        self.assertEqual(self.wallet()["balance_ngn"], 0)

    def test_a_crypto_quote_covers_the_naira_at_the_locked_rate(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "crypto", "nep141:tron-usdt")
        self.assertEqual(self.one_click.quotes[0]["usdc_out"], 13_333_334, "rounded up")
        self.assertEqual(self.one_click.quotes[0]["recipient"], "stark-treasury.near")
        self.assertEqual(deposit["pay"]["address"], "TXdeposit1")
        self.assertEqual(deposit["pay"]["amount"], "13.46")

    def test_a_settled_swap_credits_no_more_than_was_asked(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "crypto", "nep141:tron-usdt")
        self.one_click.status_reply = {"status": "SUCCESS",
                                       "swapDetails": {"amountOut": "13333334"}}
        self.assertEqual(service.get(self.account.id, deposit["id"])["credited_ngn"], 20_000)
        self.assertEqual(self.wallet()["balance_ngn"], 20_000)

    def test_a_short_swap_credits_what_arrived(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "crypto", "nep141:tron-usdt")
        self.one_click.status_reply = {"status": "SUCCESS",
                                       "swapDetails": {"amountOut": "10000000"}}
        self.assertEqual(service.get(self.account.id, deposit["id"])["credited_ngn"], 15_000)

    def test_a_refunded_swap_credits_nothing(self):
        service = self.deposits()
        deposit = service.start(self.account.id, 20_000, "crypto", "nep141:tron-usdt")
        self.one_click.status_reply = {"status": "REFUNDED",
                                       "swapDetails": {"refundReason": "PARTIAL_DEPOSIT"}}
        result = service.get(self.account.id, deposit["id"])
        self.assertEqual(result["status"], "refunded")
        self.assertEqual(result["note"], "PARTIAL_DEPOSIT")
        self.assertEqual(self.wallet()["balance_ngn"], 0)

    def test_refusals(self):
        service = self.deposits(crypto=False)
        for args, code in (
            ((50, "bank", None), "bad_amount"),
            ((20_000, "cash", None), "bad_method"),
            ((20_000, "crypto", "x"), "not_available"),
        ):
            with self.assertRaises(ApiError) as caught:
                service.start(self.account.id, *args)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(ApiError) as caught:
            self.deposits().start(self.account.id, 20_000, "crypto", "nep141:unknown")
        self.assertEqual(caught.exception.code, "bad_asset")
        no_bachs = DepositService(self.db, self.receipts, self.vaults, None, FakeOneClick(),
                                  FundingSettings(None, None, None))
        with self.assertRaises(ApiError) as caught:
            no_bachs.start(self.account.id, 20_000, "bank", None)
        self.assertEqual(caught.exception.code, "not_available")


# --- withdrawals -----------------------------------------------------------------------


class WithdrawalTests(MoneyCase):
    balance = 50_000

    def withdrawals(self):
        self.bachs = FakeBachs()
        return WithdrawalService(self.db, self.receipts, self.vaults, self.bachs)

    def test_money_is_held_at_once_and_waits_for_review(self):
        service = self.withdrawals()
        self.bachs.destination_status = {"status": "pending_review", "is_usable": False}
        result = service.request(self.account.id, 10_000, "058", "0123456789")
        self.assertEqual(result["status"], "reviewing")
        self.assertEqual(self.wallet()["balance_ngn"], 40_000)
        self.assertIn(("debit", {"amount_ngn": "10000", "reference": result["id"]}),
                      self.chain.calls)
        self.bachs.destination_status = {"status": "approved", "is_usable": True}
        service.advance_reviewing()
        self.assertEqual(service.recent(self.account.id)[0]["status"], "processing")
        self.assertEqual(self.bachs.payouts[0]["reference"], result["id"])

    def test_a_failed_payout_returns_the_money_once(self):
        service = self.withdrawals()
        result = service.request(self.account.id, 10_000, "058", "0123456789")
        service.on_payout(result["id"], paid=False)
        service.on_payout(result["id"], paid=False)
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)
        self.assertEqual(service.recent(self.account.id)[0]["status"], "returned")
        self.assertEqual([c[0] for c in self.chain.calls].count("fund"), 1)

    def test_a_rejected_bank_account_returns_the_money(self):
        service = self.withdrawals()
        self.bachs.destination_status = {"status": "rejected", "is_usable": False,
                                         "status_reason": "name mismatch"}
        result = service.request(self.account.id, 10_000, "058", "0123456789")
        self.assertEqual(result["status"], "returned")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)

    def test_a_paid_payout_is_final(self):
        service = self.withdrawals()
        result = service.request(self.account.id, 10_000, "058", "0123456789")
        self.assertTrue(service.on_payout(result["id"], paid=True))
        self.assertEqual(service.recent(self.account.id)[0]["status"], "paid")
        self.assertFalse(service.on_payout("refill_x", paid=True))

    def test_refusals_take_nothing(self):
        service = self.withdrawals()
        for args, code in (
            ((10_000, "058", "123"), "bad_account"),
            ((50, "058", "0123456789"), "bad_amount"),
            ((90_000, "058", "0123456789"), "insufficient_balance"),
        ):
            with self.assertRaises(ApiError) as caught:
                service.request(self.account.id, *args)
            self.assertEqual(caught.exception.code, code)
        self.bachs.resolved = False
        with self.assertRaises(ApiError) as caught:
            service.request(self.account.id, 10_000, "058", "0123456789")
        self.assertEqual(caught.exception.code, "bad_account")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)


# --- crypto withdrawals -------------------------------------------------------------------


class FakeTreasury:
    """The treasury's hot key, faked at the chain: signs, sends, reports outcomes."""

    account_id = "stark-treasury.near"

    def __init__(self):
        self.signed: list[tuple[str, int]] = []
        self.sent: list[str] = []
        self.send_error: Exception | None = None
        self.landed: dict | None = None

    def sign_usdc_transfer(self, receiver_id, amount):
        self.signed.append((receiver_id, amount))
        n = len(self.signed)
        return SignedTransfer(f"signed-{n}", f"hash{n}")

    def send(self, transfer):
        self.sent.append(transfer.encoded)
        if self.send_error is not None:
            err, self.send_error = self.send_error, None
            raise err

    def outcome(self, transfer):
        return self.landed


class FakePayoutOneClick(FakeOneClick):
    def __init__(self):
        super().__init__()
        self.payout_quotes: list[dict] = []
        self.quote_error: OneClickError | None = None
        self.submitted: list[str] = []

    def quote_withdrawal(self, *, destination_asset, usdc_in, recipient, treasury, deadline):
        if self.quote_error is not None:
            raise self.quote_error
        self.payout_quotes.append({"asset": destination_asset, "usdc_in": usdc_in,
                                   "recipient": recipient, "treasury": treasury})
        return {"quote": {"depositAddress": "a1b2" * 16, "amountOutFormatted": "13.21",
                          "deadline": deadline}}

    def submit_deposit(self, address, tx_hash, memo):
        self.submitted.append(tx_hash)
        return self.status_reply


LANDED = {"status": {"SuccessValue": ""}}
ADDRESS = "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"


class CryptoWithdrawalTests(MoneyCase):
    balance = 50_000

    def service(self, *, treasury=True, max_ngn=200_000, daily_ngn=10**12):
        self.one_click = FakePayoutOneClick()
        self.treasury = FakeTreasury() if treasury else None
        deposits = DepositService(self.db, self.receipts, self.vaults, None, self.one_click,
                                  FundingSettings(None, "stark-treasury.near",
                                                  Decimal("1500")))
        ledger = WithdrawalService(self.db, self.receipts, self.vaults, None)
        self.payouts = CryptoWithdrawalService(
            self.db, ledger, self.vaults, deposits, self.one_click, self.treasury,
            CryptoPayoutSettings(Decimal("1500"), max_ngn, daily_ngn),
        )
        return self.payouts

    def request(self, amount=20_000, asset="nep141:tron-usdt", address=ADDRESS):
        return self.payouts.request(self.account.id, amount, asset, address)

    def test_money_is_held_converted_down_and_sent_once(self):
        self.service()
        result = self.request()
        self.assertEqual(result["method"], "crypto")
        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["crypto"], {"asset": "USDT", "chain": "tron",
                                            "address": ADDRESS, "amount": "13.21",
                                            "tx_hash": "hash1"})
        self.assertEqual(self.wallet()["balance_ngn"], 30_000)
        # ₦20,000 at ₦1,500 is 13.333333 USDC: rounded down, never up.
        self.assertEqual(self.one_click.payout_quotes[0],
                         {"asset": "nep141:tron-usdt", "usdc_in": 13_333_333,
                          "recipient": ADDRESS, "treasury": "stark-treasury.near"})
        self.assertEqual(self.treasury.signed, [("a1b2" * 16, 13_333_333)])
        self.assertEqual(self.one_click.submitted, ["hash1"])
        self.assertIn(("debit", {"amount_ngn": "20000", "reference": result["id"]}),
                      self.chain.calls)

    def test_a_settled_swap_is_paid_with_what_arrived(self):
        self.service()
        self.request()
        self.one_click.status_reply = {"status": "SUCCESS",
                                       "swapDetails": {"amountOutFormatted": "13.19"}}
        self.payouts.advance()
        latest = self.payouts.ledger.recent(self.account.id)[0]
        self.assertEqual(latest["status"], "paid")
        self.assertEqual(latest["crypto"]["amount"], "13.19")
        self.assertEqual(self.wallet()["balance_ngn"], 30_000)

    def test_a_refunded_swap_returns_the_money_once(self):
        self.service()
        result = self.request()
        self.one_click.status_reply = {"status": "REFUNDED",
                                       "swapDetails": {"refundReason": "no liquidity"}}
        self.payouts.advance()
        self.payouts.advance()
        latest = self.payouts.ledger.recent(self.account.id)[0]
        self.assertEqual(latest["status"], "returned")
        self.assertEqual(latest["note"], "no liquidity")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)
        self.assertEqual([c for c in self.chain.calls if c[0] == "fund"],
                         [("fund", {"amount_ngn": "20000", "reference": f"{result['id']}-r"})])

    def test_a_timeout_that_landed_is_not_sent_again(self):
        self.service()
        self.treasury.send_error = near_tx.NearRpcError("timeout")
        self.treasury.landed = LANDED
        result = self.request()
        self.assertEqual(result["status"], "processing")
        self.assertEqual(len(self.treasury.signed), 1)
        self.assertEqual(len(self.treasury.sent), 1)

    def test_a_timeout_the_chain_never_saw_resends_the_same_bytes(self):
        self.service()
        self.treasury.send_error = near_tx.NearRpcError("timeout")
        result = self.request()
        self.assertEqual(result["status"], "sending")
        self.payouts.advance()
        self.assertEqual(self.treasury.signed, [("a1b2" * 16, 13_333_333)])
        self.assertEqual(self.treasury.sent, ["signed-1", "signed-1"])
        self.assertEqual(self.payouts.ledger.recent(self.account.id)[0]["status"],
                         "processing")

    def test_an_expired_transaction_is_signed_afresh(self):
        self.service()
        self.treasury.send_error = near_tx.NearRpcError("tx rejected",
                                                        {"data": "Expired"})
        self.request()
        self.payouts.advance()
        self.assertEqual(len(self.treasury.signed), 2)
        self.assertEqual(self.treasury.sent, ["signed-1", "signed-2"])

    def test_a_refused_transfer_returns_the_money(self):
        self.service()
        self.treasury.send_error = near_tx.ContractRefused("The account doesn't have "
                                                           "enough balance")
        result = self.request()
        self.assertEqual(result["status"], "returned")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)

    def test_refusals_take_nothing(self):
        self.service()
        for args, code in (
            ({"amount": 500}, "bad_amount"),
            ({"amount": 300_000}, "over_limit"),
            ({"asset": "nep141:unknown"}, "bad_asset"),
            ({"address": "not an address"}, "bad_address"),
            ({"amount": 60_000}, "insufficient_balance"),
        ):
            with self.assertRaises(ApiError) as caught:
                self.request(**args)
            self.assertEqual(caught.exception.code, code)
        self.one_click.quote_error = OneClickError(400, "recipient is not a valid address")
        with self.assertRaises(ApiError) as caught:
            self.request()
        self.assertEqual(caught.exception.code, "bad_address")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)
        self.assertEqual(self.treasury.signed, [])

    def test_without_a_treasury_key_it_is_not_available(self):
        self.service(treasury=False)
        self.assertFalse(self.payouts.available())
        with self.assertRaises(ApiError) as caught:
            self.request()
        self.assertEqual(caught.exception.code, "not_available")
        self.assertEqual(self.wallet()["balance_ngn"], 50_000)

    def test_the_daily_limit_counts_what_was_not_returned(self):
        baseline = self.service()._sent_today()
        self.service(daily_ngn=baseline + 25_000)
        self.request(10_000)
        with self.assertRaises(ApiError) as caught:
            self.request(20_000)
        self.assertEqual(caught.exception.code, "daily_limit")
        self.assertEqual(self.wallet()["balance_ngn"], 40_000)


# --- the webhook ---------------------------------------------------------------------------


def signed(body: bytes, secret: str, *, at: int | None = None, v2: bool = True) -> dict:
    timestamp = str(at or int(time.time()))
    sig = hmac.new(secret.encode(), f"{timestamp}.".encode() + body,
                   hashlib.sha256).hexdigest()
    if v2:
        return {"x-bachs-signature-v2": f"t={timestamp},v1=deadbeef,v1={sig}"}
    return {"x-bachs-signature": sig, "x-bachs-timestamp": timestamp}


class SignatureTests(unittest.TestCase):
    def test_v2_with_a_rotated_secret_and_v1(self):
        body = b'{"id":"evt_1"}'
        self.assertTrue(bachs.verify_signature(body, signed(body, "s"), "s"))
        self.assertTrue(bachs.verify_signature(body, signed(body, "s", v2=False), "s"))

    def test_tampered_stale_or_unsigned_bodies_are_refused(self):
        body = b'{"id":"evt_1"}'
        self.assertFalse(bachs.verify_signature(b'{"id":"evt_2"}', signed(body, "s"), "s"))
        self.assertFalse(bachs.verify_signature(body, signed(body, "other"), "s"))
        self.assertFalse(bachs.verify_signature(body, signed(body, "s",
                                                             at=int(time.time()) - 301), "s"))
        self.assertFalse(bachs.verify_signature(body, {}, "s"))
        self.assertFalse(bachs.verify_signature(body, signed(body, "s"), ""))

    def test_amounts_are_naira_strings(self):
        self.assertEqual(bachs.naira(5000), "5000.00")
        self.assertEqual(bachs.whole_naira("249700.99"), 249_700)

    def test_key_prefix_picks_the_host(self):
        self.assertIsNone(bachs.client_from_env({}))
        self.assertEqual(bachs.client_from_env({"BACHS_SECRET_KEY": "sk_sandbox_x"}).base_url,
                         bachs.SANDBOX_URL)
        self.assertEqual(bachs.client_from_env({"BACHS_SECRET_KEY": "sk_live_x"}).base_url,
                         bachs.LIVE_URL)
        with self.assertRaises(ValueError):
            bachs.client_from_env({"BACHS_SECRET_KEY": "pk_x"})


class WebhookTests(DepositTests):
    def webhooks(self, deposits):
        floats = FloatService(self.db, FakeVtpass(), None, FloatSettings(1, 2, None))
        withdrawals = WithdrawalService(self.db, self.receipts, self.vaults, self.bachs)
        return BachsWebhookService(self.db, "whsec", deposits, withdrawals, floats)

    def test_a_signed_collection_credits_and_a_redelivery_does_not(self):
        deposits = self.deposits()
        deposit = deposits.start(self.account.id, 20_000, "bank", None)
        event_id = f"evt_{deposit['id']}"
        body = json.dumps({"id": event_id, "type": "collection.succeeded",
                           "data": {"reference": deposit["id"], "status": "SUCCEEDED"}}).encode()
        hook = self.webhooks(deposits)
        try:
            self.assertFalse(hook.handle(body, signed(body, "whsec"))["duplicate"])
            self.assertTrue(hook.handle(body, signed(body, "whsec"))["duplicate"])
        finally:
            self.db.query("DELETE FROM processed_messages WHERE message_id = $1", [event_id])
        self.assertEqual(self.wallet()["balance_ngn"], 20_000)

    def test_an_unsigned_or_unconfigured_webhook_is_refused(self):
        body = b'{"id":"evt_x","type":"collection.succeeded","data":{}}'
        hook = self.webhooks(self.deposits())
        with self.assertRaises(ApiError) as caught:
            hook.handle(body, {})
        self.assertEqual(caught.exception.code, "webhook_unverified")
        hook.secret = None
        with self.assertRaises(ApiError) as caught:
            hook.handle(body, signed(body, "whsec"))
        self.assertEqual(caught.exception.code, "webhook_unconfigured")


# --- the HTTP surface -------------------------------------------------------------------------


class WalletRouteTests(unittest.TestCase):
    def setUp(self):
        self.account = support.TempAccount()
        self.api = support.ApiHarness(self.account)

    def tearDown(self):
        self.account.close()

    def test_methods_report_what_is_switched_on(self):
        body = self.api.client.get("/v1/wallet/methods").json()
        self.assertEqual(set(body), {"bank", "crypto", "test_money", "withdraw"})
        self.assertEqual(set(body["withdraw"]), {"bank", "crypto"})

    def test_test_money_is_refused_once_a_rail_exists(self):
        self.api.module.wallet.test_money = False
        response = self.api.client.post("/v1/wallet/topup", json={"amount_ngn": 5000})
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["code"], "not_available")

    def test_withdraw_without_bachs_is_not_available_and_takes_nothing(self):
        self.api.module.withdrawals.bachs = None
        response = self.api.client.post("/v1/wallet/withdraw", json={
            "amount_ngn": 5000, "bank_code": "058", "account_number": "0123456789"})
        self.assertEqual(response.status_code, 501)

    def test_the_bachs_webhook_refuses_unsigned_requests(self):
        self.api.module.bachs_webhooks.secret = "whsec"
        response = self.api.client.post("/v1/bachs/webhook", content=b"{}")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
