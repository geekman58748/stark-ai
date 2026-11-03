"""The WhatsApp door: signature, handshake, gates, and the voice-note download path.

Hermetic like `test_tg.py`: the agent, transcription, speech and the Graph API's
replies are fakes. The real dependencies are `IdentityRepository` on the Neon
database (`DATABASE_URL`, read from `apps/backend/.env`), and — for the download
path — the real `GraphApi` over urllib against a loopback HTTP server, plus
`ffmpeg` when it is installed. Nothing reaches Meta.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import secrets
import threading
import unittest
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from app.filters.http_exception_filter import HttpExceptionFilter
from app.modules.channel import phone_router
from app.modules.channel.channel_error import ChannelError
from app.modules.telegram.identity_repository import IdentityRepository
from app.modules.voice import audio
from app.modules.whatsapp import whatsapp, whatsapp_controller
from app.modules.whatsapp.dtos.whatsapp_webhook_dto import WhatsAppWebhookDto
from app.modules.whatsapp.graph_api import GraphApi
from app.modules.whatsapp.whatsapp import WhatsAppAdapter
from app.modules.whatsapp.whatsapp_config import WhatsAppConfig
from app.modules.whatsapp.whatsapp_service import WhatsAppService
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests import support as test_support

APP_SECRET = "meta-app-secret"
VERIFY_TOKEN = "verify-me"
REPLY = "You've got about 11.4 units left."


def _tiny_wav(seconds: float = 0.05, rate: int = 16000) -> bytes:
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def _sign(raw: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _phone() -> str:
    """A number of this test's own, so link attempts never collide across runs."""
    return f"234{secrets.randbelow(10**10):010d}"


def _payload(
    sender: str,
    *,
    text: str | None = "what's left",
    audio_id: str | None = None,
    message_id: str | None = None,
) -> dict:
    message: dict = {
        "from": sender,
        "id": message_id or f"wamid.{uuid.uuid4().hex}",
        "timestamp": "1762000000",
    }
    if audio_id is not None:
        message.update(
            type="audio",
            audio={
                "id": audio_id,
                "mime_type": "audio/ogg; codecs=opus",
                "voice": True,
            },
        )
    else:
        message.update(type="text", text={"body": text})
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "PNID",
                            },
                            "contacts": [
                                {"profile": {"name": "Tunde"}, "wa_id": sender}
                            ],
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def respond(self, user_id: str, said: str, thread: str):
        self.calls.append((user_id, said, thread))
        return SimpleNamespace(
            reply=REPLY,
            actions=[],
            code=None,
            receipt_id=None,
            token=None,
            conversation=[],
        )


class FakeGraph(GraphApi):
    """Records what would have been sent to Meta."""

    def __init__(self) -> None:
        super().__init__("token", "PNID")
        self.texts: list[tuple[str, str]] = []
        self.audio: list[tuple[str, str]] = []
        self.uploads: list[bytes] = []
        self.clip: bytes | None = _tiny_wav()

    def media(self, media_id: str, *, max_bytes: int) -> bytes | None:
        return self.clip

    def send_text(self, to: str, text: str) -> bool:
        self.texts.append((to, text))
        return True

    def upload_audio(self, ogg: bytes) -> str | None:
        self.uploads.append(ogg)
        return "media-up-1"

    def send_audio(self, to: str, media_id: str) -> bool:
        self.audio.append((to, media_id))
        return True


class AdapterCase(unittest.TestCase):
    def setUp(self) -> None:
        self.account = test_support.TempAccount()
        self.addCleanup(self.account.close)
        self.ids = IdentityRepository(self.account.db)
        self.agent = FakeAgent()
        self.graph = FakeGraph()
        self.phone = _phone()
        self.e164 = f"+{self.phone}"
        self.addCleanup(
            self.account.db.query,
            "DELETE FROM link_attempts WHERE channel = $1 AND channel_user_id = $2",
            [whatsapp.CHANNEL, self.e164],
        )
        self.adapter = WhatsAppAdapter(
            identities=self.ids,
            respond=self.agent.respond,
            graph=self.graph,
            app_secret=APP_SECRET,
            verify_token=VERIFY_TOKEN,
            transcribe=lambda wav: ("hello stark what's left", "ok"),
            speak=lambda text: None,
        )

    def linked(self) -> None:
        code = self.ids.issue_code(self.account.id)
        self.ids.consume_code(code, whatsapp.CHANNEL, self.e164, "Tunde")

    def deliver(self, payload: dict) -> list[str]:
        return self.adapter.handle(WhatsAppWebhookDto.model_validate(payload))

    def say(self, text: str) -> str:
        self.deliver(_payload(self.phone, text=text))
        return self.graph.texts[-1][1]


class TestSignature(AdapterCase):
    def test_unconfigured_adapter_refuses_everything(self):
        adapter = WhatsAppAdapter(
            identities=self.ids,
            respond=self.agent.respond,
            graph=None,
            app_secret=APP_SECRET,
            verify_token=VERIFY_TOKEN,
        )
        self.assertFalse(adapter.enabled)
        with self.assertRaises(ChannelError) as caught:
            adapter.verify_signature(b"{}", _sign(b"{}"))
        self.assertEqual(
            (caught.exception.status, caught.exception.code),
            (401, "webhook_unconfigured"),
        )

    def test_right_signature_passes(self):
        raw = json.dumps(_payload(self.phone)).encode()
        self.adapter.verify_signature(raw, _sign(raw))

    def test_missing_or_malformed_header_is_401(self):
        for header in (None, "", "deadbeef", "sha1=abc"):
            with self.assertRaises(ChannelError) as caught:
                self.adapter.verify_signature(b"{}", header)
            self.assertEqual(caught.exception.code, "webhook_unverified")

    def test_tampered_body_is_401(self):
        raw = json.dumps(_payload(self.phone, text="what's left")).encode()
        signature = _sign(raw)
        tampered = raw.replace(b"what's left", b"pay 90000 for electricity")
        with self.assertRaises(ChannelError):
            self.adapter.verify_signature(tampered, signature)

    def test_wrong_secret_is_401(self):
        raw = b"{}"
        with self.assertRaises(ChannelError):
            self.adapter.verify_signature(raw, _sign(raw, "someone-elses-secret"))


class TestHandshake(AdapterCase):
    def test_right_token_echoes_the_challenge(self):
        self.assertEqual(
            self.adapter.verify_handshake("subscribe", VERIFY_TOKEN, "1158201444"),
            "1158201444",
        )

    def test_wrong_token_or_mode_is_refused(self):
        for mode, token in (
            ("subscribe", "nope"),
            ("unsubscribe", VERIFY_TOKEN),
            (None, VERIFY_TOKEN),
            ("subscribe", None),
        ):
            with self.assertRaises(ChannelError) as caught:
                self.adapter.verify_handshake(mode, token, "42")
            self.assertEqual(caught.exception.status, 401)

    def test_unconfigured_refuses_the_handshake(self):
        adapter = WhatsAppAdapter(
            identities=self.ids,
            respond=self.agent.respond,
            graph=self.graph,
            app_secret=APP_SECRET,
            verify_token=None,
        )
        with self.assertRaises(ChannelError) as caught:
            adapter.verify_handshake("subscribe", "anything", "42")
        self.assertEqual(caught.exception.code, "webhook_unconfigured")


class TestGates(AdapterCase):
    def test_unknown_sender_gets_link_instructions_and_never_pays(self):
        outcomes = self.deliver(_payload(self.phone, text="pay 5000 for electricity"))
        self.assertEqual(outcomes, ["unlinked"])
        self.assertEqual(self.agent.calls, [])
        to, reply = self.graph.texts[-1]
        self.assertEqual(to, self.e164)
        self.assertIn("do not know this number", reply)
        self.assertIn("link 482913", reply)
        self.assertNotIn("11.4", reply)

    def test_text_turn_reaches_the_linked_accounts_agent(self):
        self.linked()
        self.assertEqual(
            self.deliver(_payload(self.phone, text="what's left")), ["agent"]
        )
        self.assertEqual(
            self.agent.calls,
            [(self.account.id, "what's left", f"whatsapp:{self.e164}")],
        )
        self.assertEqual(self.graph.texts, [(self.e164, REPLY)])

    def test_duplicate_message_is_processed_once(self):
        self.linked()
        payload = _payload(self.phone, message_id=f"wamid.{uuid.uuid4().hex}")
        self.assertEqual(self.deliver(payload), ["agent"])
        self.assertEqual(self.deliver(payload), ["duplicate"])
        self.assertEqual(len(self.agent.calls), 1)
        self.assertEqual(len(self.graph.texts), 1)

    def test_status_only_delivery_is_ignored_quietly(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [{"id": "wamid.x", "status": "read"}]
                            },
                        }
                    ]
                }
            ],
        }
        self.assertEqual(self.deliver(payload), [])
        self.assertEqual(self.graph.texts, [])

    def test_sender_that_is_not_a_phone_number_is_ignored(self):
        self.assertEqual(self.deliver(_payload("not-a-number")), ["ignored"])
        self.assertEqual(self.graph.texts, [])


class TestLinking(AdapterCase):
    def test_link_binds_and_bad_codes_are_refused(self):
        self.assertIn("did not work", self.say("link 999999"))
        code = self.ids.issue_code(self.account.id)
        self.assertIn("Linked", self.say(f"link {code}"))
        self.assertEqual(self.ids.resolve(whatsapp.CHANNEL, self.e164), self.account.id)

    def test_slash_form_works_too(self):
        code = self.ids.issue_code(self.account.id)
        self.assertIn("Linked", self.say(f"/link {code}"))

    def test_whoami_and_unlink(self):
        self.assertEqual(self.say("whoami"), "Not linked.")
        self.linked()
        self.assertIn(self.account.id, self.say("whoami"))
        self.assertIn("Unlinked", self.say("unlink"))
        self.assertIsNone(self.ids.resolve(whatsapp.CHANNEL, self.e164))
        self.assertEqual(self.say("unlink"), "This number was not linked.")

    def test_a_code_never_rebinds_a_linked_number(self):
        self.linked()
        code = self.ids.issue_code(self.account.id)
        self.assertIn("already linked", self.say(f"link {code}"))

    def test_a_sentence_that_starts_with_a_command_word_is_a_request(self):
        self.linked()
        self.say("pause my airtime top-up")
        self.assertEqual(self.agent.calls[-1][1], "pause my airtime top-up")

    def test_help_is_a_command_not_an_agent_turn(self):
        self.assertEqual(self.say("help"), phone_router.HELP_TEXT)
        self.assertEqual(self.agent.calls, [])


class TestVoice(AdapterCase):
    def test_voice_note_with_wake_word_reaches_the_agent(self):
        self.linked()
        self.assertEqual(self.deliver(_payload(self.phone, audio_id="m1")), ["agent"])
        self.assertEqual(self.agent.calls[0][1], "hello stark what's left")

    def test_voice_note_without_wake_word_stays_asleep(self):
        self.linked()
        self.adapter.transcribe = lambda wav: ("what's the weather", "ok")
        self.assertEqual(self.deliver(_payload(self.phone, audio_id="m1")), ["asleep"])
        self.assertEqual(self.agent.calls, [])

    def test_undownloadable_note_is_answered_honestly(self):
        self.linked()
        self.graph.clip = None
        self.assertEqual(
            self.deliver(_payload(self.phone, audio_id="m1")), ["voice_unheard"]
        )
        self.assertIn("cannot hear voice notes", self.graph.texts[-1][1])

    def test_voice_note_from_unknown_sender_is_never_downloaded(self):
        fetched: list[str] = []
        self.graph.media = lambda media_id, max_bytes: fetched.append(media_id)
        self.assertEqual(
            self.deliver(_payload(self.phone, audio_id="m1")), ["unlinked"]
        )
        self.assertEqual(fetched, [])

    def test_voice_question_gets_a_voice_note_back(self):
        self.linked()
        self.adapter.speak = lambda text: b"OggS-fake"
        self.deliver(_payload(self.phone, audio_id="m1"))
        self.assertEqual(self.graph.uploads, [b"OggS-fake"])
        self.assertEqual(self.graph.audio, [(self.e164, "media-up-1")])
        self.assertEqual(self.graph.texts, [])

    def test_no_speech_falls_back_to_text(self):
        self.linked()
        self.deliver(_payload(self.phone, audio_id="m1"))
        self.assertEqual(self.graph.audio, [])
        self.assertEqual(self.graph.texts, [(self.e164, REPLY)])

    def test_typed_message_never_gets_a_voice_reply(self):
        self.linked()
        self.adapter.speak = lambda text: b"OggS-fake"
        self.deliver(_payload(self.phone, text="what's left"))
        self.assertEqual(self.graph.uploads, [])
        self.assertEqual(self.graph.texts, [(self.e164, REPLY)])


class LoopbackGraph:
    """A stand-in for graph.facebook.com and Meta's media CDN, on 127.0.0.1."""

    def __init__(self, clip: bytes, *, reported_size: int | None = None) -> None:
        self.requests: list[tuple[str, str, str | None]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append(
                    ("GET", self.path, self.headers.get("Authorization"))
                )
                if self.path == "/v21.0/media-123":
                    body = json.dumps(
                        {
                            "url": f"{outer.base}/cdn/voice.ogg",
                            "mime_type": "audio/ogg; codecs=opus",
                            "file_size": (
                                reported_size
                                if reported_size is not None
                                else len(clip)
                            ),
                            "id": "media-123",
                            "messaging_product": "whatsapp",
                        }
                    ).encode()
                elif self.path == "/cdn/voice.ogg":
                    body = clip
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class TestGraphDownload(unittest.TestCase):
    """The real `GraphApi` over urllib: media id → URL → bytes, bearer on both hops."""

    def serve(self, clip: bytes, **kwargs) -> tuple[LoopbackGraph, GraphApi]:
        server = LoopbackGraph(clip, **kwargs)
        self.addCleanup(server.close)
        return server, GraphApi(
            "tok-123", "PNID", base=f"{server.base}/v21.0", timeout=5
        )

    def test_media_is_fetched_with_the_bearer_token_on_both_hops(self):
        clip = _tiny_wav()
        server, graph = self.serve(clip)
        self.assertEqual(
            graph.media("media-123", max_bytes=audio.MAX_INPUT_BYTES), clip
        )
        self.assertEqual(
            server.requests,
            [
                ("GET", "/v21.0/media-123", "Bearer tok-123"),
                ("GET", "/cdn/voice.ogg", "Bearer tok-123"),
            ],
        )

    def test_oversized_media_is_refused_before_download(self):
        server, graph = self.serve(b"x" * 10, reported_size=audio.MAX_INPUT_BYTES + 1)
        self.assertIsNone(graph.media("media-123", max_bytes=audio.MAX_INPUT_BYTES))
        self.assertEqual([path for _, path, _ in server.requests], ["/v21.0/media-123"])

    def test_media_larger_than_reported_is_still_capped(self):
        server, graph = self.serve(b"x" * 200, reported_size=10)
        self.assertIsNone(graph.media("media-123", max_bytes=100))

    def test_unknown_media_is_none_not_an_exception(self):
        _server, graph = self.serve(b"")
        self.assertIsNone(graph.media("missing", max_bytes=100))

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_voice_note_travels_download_decode_transcribe_agent(self):
        server, graph = self.serve(_tiny_wav())
        account = test_support.TempAccount()
        self.addCleanup(account.close)
        ids = IdentityRepository(account.db)
        phone = _phone()
        ids.consume_code(
            ids.issue_code(account.id), whatsapp.CHANNEL, f"+{phone}", None
        )
        heard: list[bytes] = []
        agent = FakeAgent()
        sent: list[tuple[str, str]] = []
        graph.send_text = lambda to, text: sent.append((to, text)) or True
        adapter = WhatsAppAdapter(
            identities=ids,
            respond=agent.respond,
            graph=graph,
            app_secret=APP_SECRET,
            verify_token=VERIFY_TOKEN,
            transcribe=lambda wav: heard.append(wav)
            or ("hello stark what's left", "ok"),
            speak=lambda text: None,
        )
        outcomes = adapter.handle(
            WhatsAppWebhookDto.model_validate(_payload(phone, audio_id="media-123"))
        )
        self.assertEqual(outcomes, ["agent"])
        self.assertTrue(heard[0].startswith(b"RIFF"))  # normalised to WAV for Whisper
        self.assertEqual(agent.calls[0][1], "hello stark what's left")
        self.assertEqual(sent, [(f"+{phone}", REPLY)])


class FakeAccounts:
    def __init__(self, agent: FakeAgent) -> None:
        self.agent = agent

    def state(self, user_id: str):
        return SimpleNamespace(
            agent=SimpleNamespace(
                respond=lambda said, thread: self.agent.respond(user_id, said, thread)
            )
        )


class TestHttp(unittest.TestCase):
    """The routes, on an app holding only this router: the wiring is not touched."""

    def build(self, config: WhatsAppConfig) -> TestClient:
        self.account = test_support.TempAccount()
        self.addCleanup(self.account.close)
        self.agent = FakeAgent()
        self.service = WhatsAppService(
            config,
            IdentityRepository(self.account.db),
            FakeAccounts(self.agent),
            controls=None,
        )
        self.graph = FakeGraph()
        if (
            self.service.adapter.graph is not None
        ):  # an unconfigured door stays unconfigured
            self.service.adapter.graph = self.graph
        self.service.adapter.on_turn = None
        app = FastAPI()
        HttpExceptionFilter.register(app)
        app.include_router(whatsapp_controller.router)
        app.state.module = SimpleNamespace(whatsapp=self.service)
        return TestClient(app)

    def configured(self) -> TestClient:
        return self.build(
            WhatsAppConfig(
                access_token="tok",
                phone_number_id="PNID",
                app_secret=APP_SECRET,
                verify_token=VERIFY_TOKEN,
            )
        )

    def post(self, client: TestClient, raw: bytes, signature: str | None):
        headers = {"Content-Type": "application/json"}
        if signature is not None:
            headers["X-Hub-Signature-256"] = signature
        return client.post("/v1/whatsapp/webhook", content=raw, headers=headers)

    def test_handshake_echoes_challenge_as_plain_text(self):
        client = self.configured()
        res = client.get(
            "/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "8675309",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.text, "8675309")
        bad = client.get(
            "/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "1",
            },
        )
        self.assertEqual(bad.status_code, 401)

    def test_tampered_body_is_401_and_nothing_is_processed(self):
        client = self.configured()
        phone = _phone()
        raw = json.dumps(_payload(phone, text="what's left")).encode()
        res = self.post(client, raw.replace(b"what's left", b"pay 90000"), _sign(raw))
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "webhook_unverified")
        self.assertEqual(self.graph.texts, [])
        self.assertEqual(self.agent.calls, [])

    def test_signed_delivery_is_handled(self):
        client = self.configured()
        raw = json.dumps(_payload(_phone(), text="hello")).encode()
        res = self.post(client, raw, _sign(raw))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True, "handled": ["unlinked"]})

    def test_signed_garbage_is_400(self):
        client = self.configured()
        raw = b'{"not": "a webhook"}'
        self.assertEqual(self.post(client, raw, _sign(raw)).status_code, 400)

    def test_unconfigured_server_refuses_every_request(self):
        client = self.build(
            WhatsAppConfig(
                access_token=None,
                phone_number_id=None,
                app_secret=APP_SECRET,
                verify_token=VERIFY_TOKEN,
            )
        )
        raw = json.dumps(_payload(_phone())).encode()
        res = self.post(client, raw, _sign(raw))
        self.assertEqual(
            (res.status_code, res.json()["code"]), (401, "webhook_unconfigured")
        )
        hs = client.get(
            "/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "1",
            },
        )
        self.assertEqual(hs.status_code, 401)

    def test_link_code_is_issued_for_the_calling_account(self):
        self.configured()
        payload = self.service.link_code(self.account.id)
        self.assertRegex(payload["code"], r"^\d{6}$")
        self.assertEqual(
            (payload["channel"], payload["user_id"]), ("whatsapp", self.account.id)
        )


if __name__ == "__main__":
    unittest.main()
