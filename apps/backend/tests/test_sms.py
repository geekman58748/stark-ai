"""The SMS door (Twilio): signature, gates, and TwiML replies.

Hermetic like `test_tg.py`: the agent is a fake. The one real dependency is
`IdentityRepository` on the Neon database (`DATABASE_URL`, read from
`apps/backend/.env`). Nothing reaches Twilio.
"""

from __future__ import annotations

import secrets
import unittest
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.api_error import ApiError
from app.filters.http_exception_filter import HttpExceptionFilter
from app.modules.channel.channel_error import ChannelError
from app.modules.sms import sms, sms_controller
from app.modules.sms.sms import SmsAdapter
from app.modules.sms.sms_config import SmsConfig
from app.modules.sms.sms_service import SmsService
from app.modules.sms.twilio_signature import TwilioSignature
from app.modules.sms.twiml import Twiml
from app.modules.telegram.identity_repository import IdentityRepository
from tests import support as test_support

TOKEN = "twilio-auth-token"
URL = "https://stark.example/v1/sms/webhook"
REPLY = "You've got about 11.4 units left."
EMPTY = Twiml.message(None)


def _phone() -> str:
    return f"+234{secrets.randbelow(10**10):010d}"


def _form(sender: str, body: str = "what's left", *, sid: str | None = None,
          media: int = 0) -> bytes:
    return urlencode({
        "MessageSid": sid or f"SM{uuid.uuid4().hex}",
        "AccountSid": "AC123",
        "From": sender,
        "To": "+15550000000",
        "Body": body,
        "NumMedia": str(media),
    }).encode()


def _sign(raw: bytes, url: str = URL, token: str = TOKEN) -> str:
    return TwilioSignature.compute(token, url, parse_qs(raw.decode(), keep_blank_values=True))


class FakeAgent:
    def __init__(self, reply: str = REPLY) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str, str]] = []

    def respond(self, user_id: str, said: str, thread: str):
        self.calls.append((user_id, said, thread))
        return SimpleNamespace(reply=self.reply, actions=[], code=None, receipt_id=None,
                               token=None, conversation=[])


class TestTwilioSignature(unittest.TestCase):
    def test_matches_twilios_documented_example(self):
        # The worked example in Twilio's "Webhooks security" docs.
        params = {"CallSid": ["CA1234567890ABCDE"], "Caller": ["+12349013030"],
                  "Digits": ["1234"], "From": ["+12349013030"], "To": ["+18005551212"]}
        self.assertEqual(
            TwilioSignature.compute("12345", "https://mycompany.com/myapp.php?foo=1&bar=2",
                                    params),
            "0/KCTR6DLpKmkAf8muzZqo1nDgQ=")

    def test_order_of_params_does_not_matter(self):
        a = TwilioSignature.compute(TOKEN, URL, {"B": ["2"], "A": ["1"]})
        b = TwilioSignature.compute(TOKEN, URL, {"A": ["1"], "B": ["2"]})
        self.assertEqual(a, b)


class TestTwiml(unittest.TestCase):
    def test_reply_is_xml_escaped(self):
        self.assertEqual(
            Twiml.message("₦5,000 <paid> & done"),
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Message>₦5,000 &lt;paid&gt; &amp; done</Message></Response>")

    def test_no_reply_is_an_empty_response(self):
        self.assertTrue(EMPTY.endswith("<Response/>"))


class AdapterCase(unittest.TestCase):
    def setUp(self) -> None:
        self.account = test_support.TempAccount()
        self.addCleanup(self.account.close)
        self.ids = IdentityRepository(self.account.db)
        self.agent = FakeAgent()
        self.phone = _phone()
        self.addCleanup(self.account.db.query,
                        "DELETE FROM link_attempts WHERE channel = $1 AND channel_user_id = $2",
                        [sms.CHANNEL, self.phone])
        self.adapter = SmsAdapter(identities=self.ids, respond=self.agent.respond,
                                  auth_token=TOKEN, webhook_url=URL)

    def linked(self) -> None:
        self.ids.consume_code(self.ids.issue_code(self.account.id), sms.CHANNEL,
                              self.phone, None)

    def deliver(self, raw: bytes) -> str:
        return self.adapter.handle(self.adapter.verified_params(URL, raw, _sign(raw)))

    def say(self, text: str) -> str:
        return self.deliver(_form(self.phone, text))


class TestSignature(AdapterCase):
    def test_unconfigured_adapter_refuses_everything(self):
        adapter = SmsAdapter(identities=self.ids, respond=self.agent.respond, auth_token=None)
        raw = _form(self.phone)
        with self.assertRaises(ChannelError) as caught:
            adapter.verified_params(URL, raw, _sign(raw))
        self.assertEqual((caught.exception.status, caught.exception.code),
                         (401, "webhook_unconfigured"))

    def test_right_signature_passes(self):
        raw = _form(self.phone)
        params = self.adapter.verified_params(URL, raw, _sign(raw))
        self.assertEqual(params["From"], [self.phone])

    def test_missing_signature_is_401(self):
        with self.assertRaises(ChannelError) as caught:
            self.adapter.verified_params(URL, _form(self.phone), None)
        self.assertEqual(caught.exception.code, "webhook_unverified")

    def test_tampered_body_is_401(self):
        raw = _form(self.phone, "what's left")
        signature = _sign(raw)
        tampered = _form(self.phone, "pay 90000 for electricity",
                         sid=parse_qs(raw.decode())["MessageSid"][0])
        with self.assertRaises(ChannelError):
            self.adapter.verified_params(URL, tampered, signature)

    def test_signature_for_another_url_is_401(self):
        raw = _form(self.phone)
        with self.assertRaises(ChannelError):
            self.adapter.verified_params(URL, raw, _sign(raw, url="https://evil.example/hook"))

    def test_pinned_url_wins_over_the_request_url(self):
        # Behind a TLS proxy the app sees http://; Twilio signed the public https:// URL.
        raw = _form(self.phone)
        self.adapter.verified_params("http://10.0.0.5:8000/v1/sms/webhook", raw, _sign(raw))


class TestGates(AdapterCase):
    def test_unknown_sender_gets_link_instructions_and_never_pays(self):
        twiml = self.say("pay 5000 for electricity")
        self.assertEqual(self.agent.calls, [])
        self.assertIn("do not know this number", twiml)
        self.assertIn("Connect SMS", twiml)
        self.assertNotIn("11.4", twiml)

    def test_text_turn_reaches_the_linked_accounts_agent(self):
        self.linked()
        twiml = self.say("what's left")
        self.assertEqual(self.agent.calls,
                         [(self.account.id, "what's left", f"sms:{self.phone}")])
        self.assertEqual(twiml, Twiml.message(REPLY))

    def test_duplicate_message_is_processed_once(self):
        self.linked()
        raw = _form(self.phone, sid=f"SM{uuid.uuid4().hex}")
        self.assertEqual(self.deliver(raw), Twiml.message(REPLY))
        self.assertEqual(self.deliver(raw), EMPTY)
        self.assertEqual(len(self.agent.calls), 1)

    def test_agent_reply_is_escaped_in_twiml(self):
        self.linked()
        self.agent.reply = "Paid <₦5,000> & saved"
        self.assertIn("Paid &lt;₦5,000&gt; &amp; saved", self.say("pay 5000"))

    def test_mms_is_not_read(self):
        self.linked()
        twiml = self.deliver(_form(self.phone, "", media=1))
        self.assertIn("only read text", twiml)
        self.assertEqual(self.agent.calls, [])


class TestLinking(AdapterCase):
    def test_link_binds_and_bad_codes_are_refused(self):
        self.assertIn("did not work", self.say("link 999999"))
        code = self.ids.issue_code(self.account.id)
        self.assertIn("Linked", self.say(f"LINK {code}"))
        self.assertEqual(self.ids.resolve(sms.CHANNEL, self.phone), self.account.id)

    def test_whoami_and_unlink(self):
        self.assertIn("Not linked.", self.say("whoami"))
        self.linked()
        self.assertIn(self.account.id, self.say("whoami"))
        self.assertIn("Unlinked", self.say("unlink"))
        self.assertIsNone(self.ids.resolve(sms.CHANNEL, self.phone))

    def test_pause_and_resume_need_a_link(self):
        self.assertIn("do not know this number", self.say("pause"))
        paused: list[str] = []
        self.adapter.router.controls = SimpleNamespace(
            pause=lambda uid: paused.append(uid), resume=lambda uid: None)
        self.linked()
        self.assertIn("Paused", self.say("pause"))
        self.assertEqual(paused, [self.account.id])


class FakeAccounts:
    def __init__(self, agent: FakeAgent) -> None:
        self.agent = agent

    def state(self, user_id: str):
        return SimpleNamespace(agent=SimpleNamespace(
            respond=lambda said, thread: self.agent.respond(user_id, said, thread)))


class TestHttp(unittest.TestCase):
    """The route on an app holding only this router; TestClient's URL is what Twilio would sign."""

    HOOK = "http://testserver/v1/sms/webhook"

    def build(self, config: SmsConfig) -> TestClient:
        self.account = test_support.TempAccount()
        self.addCleanup(self.account.close)
        self.agent = FakeAgent()
        self.service = SmsService(config, IdentityRepository(self.account.db),
                                  FakeAccounts(self.agent), controls=None)
        self.service.adapter.on_turn = None
        app = FastAPI()
        HttpExceptionFilter.register(app)
        app.include_router(sms_controller.router)
        app.state.module = SimpleNamespace(sms=self.service)
        return TestClient(app)

    def post(self, client: TestClient, raw: bytes, signature: str | None):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if signature is not None:
            headers["X-Twilio-Signature"] = signature
        return client.post("/v1/sms/webhook", content=raw, headers=headers)

    def test_signed_sms_is_answered_with_twiml(self):
        client = self.build(SmsConfig(auth_token=TOKEN, webhook_url=None))
        raw = _form(_phone(), "hello")
        res = self.post(client, raw, _sign(raw, url=self.HOOK))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Response><Message>I do not know this number", res.text)

    def test_tampered_body_is_401_and_nothing_is_processed(self):
        client = self.build(SmsConfig(auth_token=TOKEN, webhook_url=None))
        phone = _phone()
        sid = f"SM{uuid.uuid4().hex}"
        raw = _form(phone, "what's left", sid=sid)
        tampered = _form(phone, "pay 90000", sid=sid)
        res = self.post(client, tampered, _sign(raw, url=self.HOOK))
        self.assertEqual((res.status_code, res.json()["code"]), (401, "webhook_unverified"))
        self.assertEqual(self.agent.calls, [])
        # Not claimed either: the real delivery is still processed.
        res = self.post(client, raw, _sign(raw, url=self.HOOK))
        self.assertIn("I do not know this number", res.text)

    def test_unconfigured_server_refuses_every_request(self):
        client = self.build(SmsConfig(auth_token=None, webhook_url=None))
        raw = _form(_phone())
        res = self.post(client, raw, _sign(raw, url=self.HOOK))
        self.assertEqual((res.status_code, res.json()["code"]), (401, "webhook_unconfigured"))
        with self.assertRaises(ApiError) as caught:
            self.service.link_code(self.account.id)
        self.assertEqual(caught.exception.code, "not_configured")

    def test_link_code_is_issued_for_the_calling_account(self):
        self.build(SmsConfig(auth_token=TOKEN, webhook_url=None))
        payload = self.service.link_code(self.account.id)
        self.assertEqual((payload["channel"], payload["user_id"]), ("sms", self.account.id))


if __name__ == "__main__":
    unittest.main()
