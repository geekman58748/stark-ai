#!/usr/bin/env python3
"""Tests for the agent layer (M2): policy parity, signing, routing, the cap gate.

Zero dependencies:  python3 -m unittest test_agent -v
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import unittest

import agent as agent_mod
import near_tx
import policy as policy_rules

ROOT = pathlib.Path(__file__).resolve().parent
POLICY_RS = ROOT.parent / "contracts" / "vault" / "src" / "policy.rs"

ELECTRICITY = {
    "id": "bill_home_meter",
    "kind": "electricity",
    "provider": "Ikeja Electric",
    "label": "Home meter",
    "reference": "04512345678",
}
DSTV = {
    "id": "bill_dstv",
    "kind": "tv",
    "provider": "DStv",
    "label": "DStv Compact",
    "reference": "7032119456",
    "plan": "dstv79",
    "plan_price_ngn": 7_900,
}
BILLS = [ELECTRICITY, DSTV]

MONTHLY = 30_000
PER_PAYMENT = 5_000
ALLOWED = frozenset({ELECTRICITY["reference"], DSTV["reference"]})


# --- test doubles ------------------------------------------------------------


class FakeToolbox:
    def __init__(self, balance=64_200, spent=12_400, bills=None):
        self.balance = balance
        self.spent = spent
        self.bills = list(BILLS if bills is None else bills)
        self.pay_calls: list[tuple[str, int]] = []
        self.receipts: list[dict] = []

    def get_state(self):
        return {
            "balance_ngn": self.balance,
            "spent_ngn": self.spent,
            "cap_ngn": MONTHLY,
            "units_left": 11.4,
            "days_left": 4,
        }

    def list_bills(self):
        return list(self.bills)

    def recent_activity(self):
        return list(self.receipts)

    def pay(self, bill_id, amount_ngn):
        self.pay_calls.append((bill_id, amount_ngn))
        bill = next(b for b in self.bills if b["id"] == bill_id)
        receipt = {
            "id": f"rcpt_{len(self.receipts) + 1}",
            "bill_id": bill_id,
            "bill_label": bill["label"],
            "amount_ngn": amount_ngn,
            "units": round(amount_ngn / 209, 2) if bill["kind"] == "electricity" else None,
            "token": "4821 0937 5512 8846 3019" if bill["kind"] == "electricity" else None,
            "tx_hash": "ab" * 32,
        }
        self.receipts.insert(0, receipt)
        self.balance -= amount_ngn
        self.spent += amount_ngn
        return receipt


class RecordingSigner:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def sign_pay(self, meter, amount_ngn):
        self.calls.append((meter, amount_ngn))
        return {"tx_hash": "cd" * 32}


class ScriptedModel:
    """A model that does whatever the test tells it to — used to prove the gate
    holds even when the model ignores every rule in the prompt."""

    name = "scripted"

    def __init__(self, calls: list[agent_mod.ToolCall]):
        self.calls = calls
        self.turns = 0

    def turn(self, messages, tools):
        if self.turns < len(self.calls):
            call = self.calls[self.turns]
            self.turns += 1
            return agent_mod.ModelTurn(tool_calls=[call])
        return agent_mod.ModelTurn(content="Understood.")


def make_agent(toolbox=None, signer=None, limits=None, model=None):
    return agent_mod.Agent(
        model=model or agent_mod.FakeModel(),
        toolbox=toolbox or FakeToolbox(),
        limits=limits
        or agent_mod.Limits(
            monthly_cap_ngn=MONTHLY,
            per_payment_cap_ngn=PER_PAYMENT,
            allowed_meters=ALLOWED,
        ),
        signer=signer,
    )


# --- policy parity -----------------------------------------------------------


class PolicyTests(unittest.TestCase):
    def ok(self, spent, balance, amount, allowed=True):
        return policy_rules.check_payment(
            MONTHLY, PER_PAYMENT, spent, balance, amount, allowed
        )

    def test_allows_a_payment_within_every_limit(self):
        self.assertIsNone(self.ok(0, 64_200, 5_000))

    def test_rejects_zero_amount(self):
        rejection = self.ok(0, 64_200, 0)
        self.assertEqual(rejection.code, policy_rules.BAD_AMOUNT)

    def test_rejects_over_per_payment_cap(self):
        rejection = self.ok(0, 64_200, 5_001)
        self.assertEqual(rejection.code, policy_rules.OVER_PER_PAYMENT_CAP)
        self.assertEqual(rejection.detail, {"amount_ngn": 5_001, "cap_ngn": PER_PAYMENT})

    def test_allows_exactly_the_per_payment_cap(self):
        self.assertIsNone(self.ok(0, 64_200, PER_PAYMENT))

    def test_rejects_over_monthly_cap(self):
        rejection = self.ok(25_000, 64_200, 5_000 + 1_000)
        self.assertEqual(rejection.code, policy_rules.OVER_PER_PAYMENT_CAP)

    def test_rejects_over_monthly_cap_within_per_payment(self):
        rejection = policy_rules.check_payment(30_000, 30_000, 28_000, 64_200, 5_000, True)
        self.assertEqual(rejection.code, policy_rules.OVER_CAP)
        self.assertEqual(rejection.detail["remaining_ngn"], 2_000)

    def test_allows_exactly_the_monthly_cap(self):
        self.assertIsNone(
            policy_rules.check_payment(30_000, 30_000, 25_000, 64_200, 5_000, True)
        )

    def test_rejects_an_unlisted_meter(self):
        self.assertEqual(self.ok(0, 64_200, 1_000, False).code,
                         policy_rules.METER_NOT_ALLOWED)

    def test_policy_violation_beats_balance(self):
        rejection = policy_rules.check_payment(30_000, 300_000, 29_000, 100, 9_000, False)
        self.assertEqual(rejection.code, policy_rules.OVER_CAP)

    def test_allowlist_beats_balance(self):
        rejection = policy_rules.check_payment(30_000, 30_000, 0, 100, 1_000, False)
        self.assertEqual(rejection.code, policy_rules.METER_NOT_ALLOWED)

    def test_rejects_when_balance_is_short(self):
        rejection = self.ok(0, 4_000, 5_000)
        self.assertEqual(rejection.code, policy_rules.INSUFFICIENT_BALANCE)
        self.assertEqual(rejection.detail, {"need_ngn": 5_000, "have_ngn": 4_000})

    def test_huge_spent_is_refused_not_clamped(self):
        rejection = policy_rules.check_payment(
            10**30, 10**30, 10**30, 10**30, 1_000, True
        )
        self.assertEqual(rejection.code, policy_rules.OVER_CAP)

    def test_remaining_cap_never_goes_negative(self):
        self.assertEqual(policy_rules.remaining_cap(30_000, 12_400), 17_600)
        self.assertEqual(policy_rules.remaining_cap(30_000, 99_999), 0)

    def test_period_key_is_a_calendar_month(self):
        self.assertEqual(policy_rules.period_key(1_792_454_400 * 10**9), "2026-10")

    def test_period_key_rolls_over_at_the_month_boundary(self):
        self.assertEqual(policy_rules.period_key(1_793_491_199 * 10**9), "2026-10")
        self.assertEqual(policy_rules.period_key(1_793_491_200 * 10**9), "2026-11")

    def test_period_key_handles_leap_day(self):
        self.assertEqual(policy_rules.period_key(1_709_208_000 * 10**9), "2024-02")

    def test_messages_have_no_crypto_jargon(self):
        banned = ("vault", "usdc", "usdt", "onchain", "blockchain", "contract", "wallet")
        for code in policy_rules.ALL_CODES:
            message = policy_rules.MESSAGES[code].lower()
            for word in banned:
                self.assertNotIn(word, message, f"{code} leaked {word!r}")

    @unittest.skipUnless(POLICY_RS.exists(), "contract source not present")
    def test_codes_and_messages_match_the_rust_contract(self):
        """Guards the one drift that would matter: the chain refusing a payment
        the agent thought was fine, or vice versa."""
        rust = POLICY_RS.read_text()
        for code in policy_rules.ALL_CODES:
            self.assertIn(f'"{code}"', rust, f"code {code} missing from policy.rs")
        for code, message in policy_rules.MESSAGES.items():
            self.assertIn(message.replace('"', '\\"'), rust,
                          f"message for {code} drifted from policy.rs")


# --- ed25519 and borsh -------------------------------------------------------


class Ed25519Tests(unittest.TestCase):
    # RFC 8032 §7.1, test vectors 1-3.
    VECTORS = [
        (
            "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
            "",
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        ),
        (
            "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
            "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
            "72",
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        ),
        (
            "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
            "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
            "af82",
            "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
            "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
        ),
    ]

    def test_rfc8032_vectors(self):
        for secret_hex, public_hex, message_hex, signature_hex in self.VECTORS:
            secret = bytes.fromhex(secret_hex)
            message = bytes.fromhex(message_hex)
            with self.subTest(vector=secret_hex[:8]):
                self.assertEqual(near_tx.ed25519_public(secret).hex(), public_hex)
                signature = near_tx.ed25519_sign(secret, message)
                self.assertEqual(signature.hex(), signature_hex)
                self.assertTrue(
                    near_tx.ed25519_verify(bytes.fromhex(public_hex), message, signature)
                )

    def test_tampered_signature_is_rejected(self):
        secret = bytes.fromhex(self.VECTORS[0][0])
        public = near_tx.ed25519_public(secret)
        signature = bytearray(near_tx.ed25519_sign(secret, b"stark"))
        signature[0] ^= 0x01
        self.assertFalse(near_tx.ed25519_verify(public, b"stark", bytes(signature)))

    def test_signature_does_not_transfer_to_another_message(self):
        secret = bytes.fromhex(self.VECTORS[0][0])
        public = near_tx.ed25519_public(secret)
        signature = near_tx.ed25519_sign(secret, b"pay 5000")
        self.assertFalse(near_tx.ed25519_verify(public, b"pay 50000", signature))

    def test_base58_round_trip(self):
        for raw in (b"", b"\x00", b"\x00\x00", b"hello world", b"\xff" * 32):
            self.assertEqual(near_tx.b58decode(near_tx.b58encode(raw)), raw)

    def test_base58_known_vectors(self):
        self.assertEqual(near_tx.b58encode(b""), "")
        self.assertEqual(near_tx.b58encode(b"\x00"), "1")
        self.assertEqual(near_tx.b58encode(b"hello world"), "StV1DL6CwTryKyV")

    def test_keypair_from_near_style_string(self):
        key = near_tx.KeyPair.from_secret(bytes(range(32)))
        restored = near_tx.KeyPair.from_string(key.public_b58.replace(
            near_tx.b58encode(key.public),
            near_tx.b58encode(key.secret + key.public),
        ))
        self.assertEqual(restored.public, key.public)

    def test_keypair_rejects_mismatched_public_half(self):
        with self.assertRaises(ValueError):
            near_tx.KeyPair.from_secret(bytes(range(32)) + b"\x00" * 32)


class BorshTests(unittest.TestCase):
    SIGNER = "agent.testnet"
    RECEIVER = "vault.testnet"
    PUBKEY = bytes(range(32))
    BLOCK_HASH = b"\x11" * 32

    def build(self, amount_ngn=5_000):
        return near_tx.encode_pay_transaction(
            signer_id=self.SIGNER,
            public_key=self.PUBKEY,
            nonce=7,
            receiver_id=self.RECEIVER,
            block_hash=self.BLOCK_HASH,
            meter="04512345678",
            amount_ngn=amount_ngn,
        )

    def test_transaction_prefix_layout(self):
        tx = self.build()
        offset = 0

        self.assertEqual(tx[offset], 0)  # TransactionV0
        offset += 1
        # Borsh strings are a u32 byte length, then the bytes.
        self.assertEqual(tx[offset:offset + 4], len(self.SIGNER).to_bytes(4, "little"))
        offset += 4
        self.assertEqual(tx[offset:offset + len(self.SIGNER)], self.SIGNER.encode())
        offset += len(self.SIGNER)
        self.assertEqual(tx[offset], 0)  # PublicKey::ED25519
        offset += 1
        self.assertEqual(tx[offset:offset + 32], self.PUBKEY)
        offset += 32
        self.assertEqual(int.from_bytes(tx[offset:offset + 8], "little"), 7)
        offset += 8
        self.assertEqual(tx[offset:offset + 4], len(self.RECEIVER).to_bytes(4, "little"))
        offset += 4
        self.assertEqual(tx[offset:offset + len(self.RECEIVER)], self.RECEIVER.encode())
        offset += len(self.RECEIVER)
        self.assertEqual(tx[offset:offset + 32], self.BLOCK_HASH)
        offset += 32
        self.assertEqual(int.from_bytes(tx[offset:offset + 4], "little"), 1)  # one action
        offset += 4
        self.assertEqual(tx[offset], 2)  # Action::FunctionCall
        offset += 1
        self.assertEqual(tx[offset:offset + 4], (3).to_bytes(4, "little"))
        offset += 4
        self.assertEqual(tx[offset:offset + 3], b"pay")
        offset += 3

        args_len = int.from_bytes(tx[offset:offset + 4], "little")
        offset += 4
        args = tx[offset:offset + args_len]
        offset += args_len
        self.assertIn(b'"amount_ngn":"5000"', args)
        self.assertIn(b'"meter":"04512345678"', args)

        self.assertEqual(int.from_bytes(tx[offset:offset + 8], "little"),
                         100_000_000_000_000)  # gas, 100 Tgas
        offset += 8
        self.assertEqual(tx[offset:offset + 16], b"\x00" * 16)  # deposit
        offset += 16
        self.assertEqual(offset, len(tx))

    def test_amount_is_a_string_over_the_wire(self):
        # near-sdk serialises U128 as a string; a bare number is rejected onchain.
        args = json.loads(near_tx.pay_args("04512345678", 5_000))
        self.assertIsInstance(args["amount_ngn"], str)
        self.assertEqual(args["amount_ngn"], "5000")

    def test_hash_is_sha256_of_the_unsigned_transaction(self):
        tx = self.build()
        self.assertEqual(near_tx.transaction_hash(tx), hashlib.sha256(tx).digest())

    def test_signed_transaction_is_tx_then_signature(self):
        key = near_tx.KeyPair.from_secret(bytes(range(32)))
        signed = near_tx.sign_pay(
            key=key,
            signer_id=self.SIGNER,
            receiver_id=self.RECEIVER,
            nonce=7,
            block_hash=self.BLOCK_HASH,
            meter="04512345678",
            amount_ngn=5_000,
        )
        import base64

        raw = base64.b64decode(signed.base64)
        self.assertEqual(raw[:-64], signed.tx_bytes)
        self.assertTrue(
            near_tx.ed25519_verify(key.public, signed.tx_hash, raw[-64:])
        )
        self.assertEqual(signed.hash_hex, signed.tx_hash.hex())

    def test_amount_changes_the_hash(self):
        self.assertNotEqual(self.build(5_000), self.build(6_000))


class RpcTests(unittest.TestCase):
    def test_signing_context_increments_the_nonce(self):
        class FakeRpc:
            def access_key(self, account_id, public_key_b58):
                return {"nonce": 41, "block_hash": near_tx.b58encode(b"\x22" * 32)}

        key = near_tx.KeyPair.from_secret(bytes(range(32)))
        context = near_tx.fetch_signing_context(
            FakeRpc(), signer_id="agent.testnet", receiver_id="vault.testnet", key=key
        )
        self.assertEqual(context.nonce, 42)
        self.assertEqual(context.block_hash, b"\x22" * 32)


# --- agent routing and the gate ---------------------------------------------


class AgentTests(unittest.TestCase):
    def test_bill_question_reads_state_and_speaks_units(self):
        reply = make_agent().respond("hello stark what's my light bill")
        self.assertIn("units left", reply.reply)
        self.assertIn("64,200", reply.reply)
        self.assertIn("get_state", reply.actions)
        self.assertIsNone(reply.token)

    def test_pay_defaults_to_the_meter_and_returns_the_token(self):
        toolbox = FakeToolbox()
        reply = make_agent(toolbox).respond("hello stark top it up")
        self.assertEqual(toolbox.pay_calls, [("bill_home_meter", 5_000)])
        self.assertEqual(reply.token, "4821 0937 5512 8846 3019")
        self.assertIsNotNone(reply.receipt_id)
        self.assertEqual(reply.actions, ["list_bills", "pay_bill"])

    def test_paying_the_tv_targets_the_tv_bill_at_its_plan_price(self):
        # The demo's per-payment cap must cover a real bouquet (see server.py).
        limits = agent_mod.Limits(MONTHLY, 10_000, ALLOWED)
        toolbox = FakeToolbox()
        reply = make_agent(toolbox, limits=limits).respond("stark pay my dstv")
        self.assertEqual(toolbox.pay_calls, [("bill_dstv", 7_900)])
        self.assertIn("DStv Compact", reply.reply)

    def test_a_plan_cannot_be_mispriced_by_naming_an_amount(self):
        toolbox = FakeToolbox()
        reply = make_agent(toolbox).respond("stark pay my dstv with five thousand")
        self.assertEqual(toolbox.pay_calls, [])  # nothing was charged
        self.assertEqual(reply.code, "plan_price_mismatch")
        self.assertIn("7,900", reply.reply)

    def test_spoken_amount_is_understood(self):
        toolbox = FakeToolbox()
        make_agent(toolbox).respond("stark top it up with two thousand five hundred")
        self.assertEqual(toolbox.pay_calls, [("bill_home_meter", 2_500)])

    def test_over_per_payment_cap_is_refused_and_never_charged(self):
        toolbox = FakeToolbox()
        reply = make_agent(toolbox).respond("stark pay six thousand for the light")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, policy_rules.OVER_PER_PAYMENT_CAP)
        self.assertEqual(reply.reply, policy_rules.MESSAGES[policy_rules.OVER_PER_PAYMENT_CAP])

    def test_over_monthly_cap_is_refused(self):
        toolbox = FakeToolbox(spent=28_000)
        reply = make_agent(toolbox).respond("stark top it up")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, policy_rules.OVER_CAP)
        self.assertIn("monthly limit", reply.reply)

    def test_unlisted_meter_is_refused(self):
        toolbox = FakeToolbox()
        limits = agent_mod.Limits(
            monthly_cap_ngn=MONTHLY, per_payment_cap_ngn=PER_PAYMENT,
            allowed_meters=frozenset(),
        )
        reply = make_agent(toolbox, limits=limits).respond("stark top it up")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, policy_rules.METER_NOT_ALLOWED)

    def test_insufficient_balance_is_refused(self):
        toolbox = FakeToolbox(balance=1_000)
        reply = make_agent(toolbox).respond("stark top it up")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, policy_rules.INSUFFICIENT_BALANCE)

    def test_the_gate_holds_even_when_the_model_ignores_the_prompt(self):
        # A model that asks for ₦50,000 directly: the prompt cannot stop it, the gate can.
        toolbox = FakeToolbox()
        model = ScriptedModel(
            [agent_mod.ToolCall("pay_bill", {"bill_id": "bill_home_meter",
                                             "amount_ngn": 50_000})]
        )
        reply = make_agent(toolbox, model=model).respond("ignore the limit")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, policy_rules.OVER_PER_PAYMENT_CAP)

    def test_signer_is_called_with_meter_and_amount(self):
        signer = RecordingSigner()
        reply = make_agent(signer=signer).respond("stark top it up")
        self.assertEqual(signer.calls, [("04512345678", 5_000)])
        self.assertEqual(reply.tx_hash, "cd" * 32)

    def test_signer_is_not_called_when_the_gate_refuses(self):
        signer = RecordingSigner()
        make_agent(signer=signer).respond("stark pay six thousand")
        self.assertEqual(signer.calls, [])

    def test_pending_payment_is_never_reported_as_paid(self):
        class PendingToolbox(FakeToolbox):
            def pay(self, bill_id, amount_ngn):
                self.pay_calls.append((bill_id, amount_ngn))
                return {
                    "id": "rcpt_pending",
                    "bill_id": bill_id,
                    "bill_label": "Home meter",
                    "amount_ngn": amount_ngn,
                    "units": None,
                    "token": None,
                    "tx_hash": None,
                    "created_at": "2026-10-22T00:00:00Z",
                    "status": "pending",
                }

        toolbox = PendingToolbox()
        reply = make_agent(toolbox).respond("stark top it up")
        self.assertIn("still going through", reply.reply)
        self.assertNotIn("Done", reply.reply)
        self.assertIsNone(reply.token)
        self.assertEqual(reply.receipt_id, "rcpt_pending")

    def test_activity_route(self):
        toolbox = FakeToolbox()
        toolbox.pay("bill_home_meter", 5_000)
        reply = make_agent(toolbox).respond("stark what was my last payment")
        self.assertIn("Home meter", reply.reply)
        self.assertEqual(reply.actions, ["recent_activity"])

    def test_bills_route(self):
        reply = make_agent().respond("stark what bills do I have")
        self.assertIn("DStv Compact", reply.reply)

    def test_unknown_tool_is_reported_to_the_model(self):
        agent_ = make_agent()
        result = agent_._run_tool(agent_mod.ToolCall("wire_money", {}), {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "unknown_tool")

    def test_unknown_tool_does_not_crash_the_loop(self):
        model = ScriptedModel([agent_mod.ToolCall("wire_money", {})])
        reply = make_agent(model=model).respond("stark send everything")
        self.assertEqual(reply.actions, ["wire_money"])
        self.assertTrue(reply.reply)

    def test_max_turns_still_returns_a_sentence(self):
        class Loop:
            name = "loop"

            def turn(self, messages, tools):
                return agent_mod.ModelTurn(
                    tool_calls=[agent_mod.ToolCall("get_state", {})]
                )

        reply = make_agent(model=Loop()).respond("stark hello")
        self.assertTrue(reply.reply)

    def test_payment_without_an_electricity_bill_is_refused(self):
        # Naming the light must never fall through to whatever bill is first.
        toolbox = FakeToolbox(bills=[DSTV])
        reply = make_agent(toolbox).respond("stark top up my light")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertIn("don't have a bill saved", reply.reply)

    def test_naming_data_without_a_data_bill_does_not_pay_electricity(self):
        toolbox = FakeToolbox()
        reply = make_agent(toolbox).respond("stark buy me data")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertIn("don't have a bill saved", reply.reply)
        self.assertIsNone(reply.token)

    def test_replies_have_no_crypto_jargon(self):
        # "wallet" is this product's own word for the balance (see docs/API.md),
        # so it is not on the banned list — the chain words are.
        banned = ("vault", "usdc", "usdt", "onchain", "blockchain", "contract")
        toolbox = FakeToolbox()
        agent_ = make_agent(toolbox)
        for phrase in (
            "hello stark what's my light bill",
            "stark top it up",
            "stark what bills do I have",
            "stark what was my last payment",
            "stark pay six thousand",
        ):
            reply = agent_.respond(phrase).reply.lower()
            for word in banned:
                self.assertNotIn(word, reply, f"{phrase!r} leaked {word!r}")

    def test_voice_payload_keeps_the_frozen_shape(self):
        payload = make_agent().respond("stark what's my bill").as_voice_payload("said")
        for key in ("transcript", "ignored", "reply", "token", "receipt_id"):
            self.assertIn(key, payload)
        self.assertFalse(payload["ignored"])
        self.assertEqual(payload["transcript"], "said")

    def test_build_agent_falls_back_to_the_fake_model(self):
        limits = agent_mod.Limits(MONTHLY, PER_PAYMENT, ALLOWED)
        agent_ = agent_mod.build_agent(FakeToolbox(), limits)
        self.assertEqual(agent_.model.name, "fake")


class SignerTests(unittest.TestCase):
    def test_a_failed_signature_refuses_the_payment(self):
        class BrokenSigner:
            def sign_pay(self, meter, amount_ngn):
                raise RuntimeError("rpc unreachable")

        toolbox = FakeToolbox()
        reply = make_agent(toolbox, signer=BrokenSigner()).respond("stark top it up")
        self.assertEqual(toolbox.pay_calls, [])
        self.assertEqual(reply.code, "authorisation_failed")
        self.assertIn("Nothing was charged", reply.reply)

    def test_vault_signer_builds_and_does_not_broadcast_by_default(self):
        import vault_signer

        class FakeRpc:
            def __init__(self):
                self.broadcasts = 0

            def access_key(self, account_id, public_key_b58):
                return {"nonce": 9, "block_hash": near_tx.b58encode(b"\x33" * 32)}

            def broadcast(self, signed):
                self.broadcasts += 1
                return {"status": {"SuccessValue": ""}}

        rpc = FakeRpc()
        signer = vault_signer.VaultSigner(
            key=near_tx.KeyPair.from_secret(bytes(range(32))),
            signer_id="agent.testnet",
            receiver_id="vault.testnet",
            rpc=rpc,
        )
        result = signer.sign_pay("04512345678", 5_000)
        self.assertTrue(result["signed"])
        self.assertFalse(result["broadcast"])
        self.assertEqual(rpc.broadcasts, 0)
        self.assertEqual(len(result["tx_hash"]), 64)

    def test_signer_is_none_without_config(self):
        import vault_signer

        self.assertIsNone(vault_signer.signer_from_env({}))
        self.assertIsNone(
            vault_signer.signer_from_env({"STARK_SIGNER_KEY": "ed25519:abc"})
        )

    def test_signer_config_is_wired_from_env(self):
        import vault_signer

        env = {
            # The env var must carry a secret, not a public key.
            "STARK_SIGNER_KEY": "ed25519:"
            + near_tx.b58encode(
                bytes(range(32)) + near_tx.ed25519_public(bytes(range(32)))
            ),
            "STARK_SIGNER_ACCOUNT": "agent.testnet",
            "STARK_VAULT_ACCOUNT": "vault.testnet",
            "STARK_NETWORK": "mainnet",
            "STARK_BROADCAST": "1",
        }
        signer = vault_signer.signer_from_env(env)
        self.assertEqual(signer.signer_id, "agent.testnet")
        self.assertEqual(signer.receiver_id, "vault.testnet")
        self.assertTrue(signer.broadcast)
        self.assertEqual(signer.rpc.base_url, near_tx.MAINNET_RPC)


class AmountParsingTests(unittest.TestCase):
    CASES = [
        ("top it up with 5000", 5_000),
        ("top it up with ₦5,000", 5_000),
        ("top it up with 5k", 5_000),
        ("top it up with 1.5k", 1_500),
        ("top it up with five thousand", 5_000),
        ("top it up with two thousand five hundred", 2_500),
        ("top it up with twenty five thousand", 25_000),
        ("top it up", None),
        ("what's my light bill", None),
    ]

    def test_amounts(self):
        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(agent_mod.parse_amount(text), expected)


if __name__ == "__main__":
    unittest.main()
