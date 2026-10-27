"""Live-path tests: real HTTP over loopback sockets.

The rest of the suite mocks `_http` and `urlopen`, so the wire is never
exercised — auth headers, JSON bodies, multipart encoding and JSON-RPC framing
are only proven against fixtures. These tests start a real `http.server` on
127.0.0.1 and point each client at it, so the code that will run with
credentials is tested without any credentials and without leaving the machine.

Covered:
  * VTpass      GET /service-variations, POST /merchant-verify, /pay, /requery
  * NEAR AI     POST /v1/chat/completions (tool calls) and /v1/audio/transcriptions
  * NEAR RPC    block, view_access_key, broadcast_tx_commit, plus a borsh
                round-trip of the signed `pay()` envelope

Hermetic: every server binds 127.0.0.1 on port 0 and is stopped in tearDown.
"""

from __future__ import annotations

import base64
import io
import json
import os
import threading
import unittest
import wave
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from app.modules.voice import audio
from app.modules.chain import near_tx
from app.modules.voice import stt
from app.modules.agent.agent import NEAR_AI_MODEL, NearAiModel
from app.modules.chain.vault_signer import VaultSigner
from app.modules.vending.vtpass import VtpassClient, VtpassError

# --- harness ----------------------------------------------------------------


@dataclass
class Recorded:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes

    @property
    def json(self) -> dict:
        return json.loads(self.body.decode())

    def header(self, name: str) -> str | None:
        """Case-insensitive lookup: HTTP header names are not case sensitive."""
        target = name.lower()
        for key, value in self.headers.items():
            if key.lower() == target:
                return value
        return None

    @property
    def boundary(self) -> str | None:
        value = self.header("Content-Type") or ""
        if "boundary=" not in value:
            return None
        return value.split("boundary=", 1)[1]


def json_response(payload: object, status: int = 200) -> tuple[int, dict, bytes]:
    return status, {"Content-Type": "application/json"}, json.dumps(payload).encode()


def raw_response(body: bytes, status: int = 200) -> tuple[int, dict, bytes]:
    return status, {"Content-Type": "application/json"}, body


class FakeServer:
    """A real HTTP server that records requests and replays one responder."""

    def __init__(self, responder):
        self.requests: list[Recorded] = []
        self.responder = responder

        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                record = Recorded(
                    method=self.command,
                    path=self.path,
                    headers={k: v for k, v in self.headers.items()},
                    body=body,
                )
                outer.requests.append(record)
                status, headers, payload = outer.responder(record)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, *_args):  # keep the test output clean
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.stop()


class ServerTest(unittest.TestCase):
    responder = None

    def setUp(self):
        self.server = FakeServer(self._responder())

    def tearDown(self):
        self.server.stop()

    def _responder(self):
        """The class-level responder, or a 404 for tests that set their own."""
        make = self.responder
        if make is None:
            return lambda req: raw_response(b"{}", 404)
        return make()

    def restart(self, responder):
        """Replace the running server so a test can change its behaviour."""
        self.server.stop()
        self.server = FakeServer(responder)


# --- VTpass live transport --------------------------------------------------


def vtpass_responder():
    """One responder that routes on path, so a test can assert each call."""

    def respond(req: Recorded):
        path = req.path.split("?", 1)[0]
        if path == "/service-variations":
            return json_response(
                {
                    "code": "000",
                    "content": {
                        # VTpass misspells this; the client accepts both.
                        "varations": [
                            {"variation_code": "prepaid", "name": "Prepaid"},
                            {"variation_code": "postpaid", "name": "Postpaid"},
                        ]
                    },
                }
            )
        if path == "/merchant-verify":
            return json_response(
                {
                    "code": "000",
                    "content": {"Customer_Name": "TUNDE ADEYEMI", "Meter_Number": "04512345678"},
                }
            )
        if path == "/pay":
            return json_response(
                {
                    "code": "000",
                    "response_description": "TRANSACTION SUCCESSFUL",
                    "requestId": req.json.get("request_id"),
                    "amount": req.json.get("amount"),
                    "content": {
                        "transactions": {
                            "status": "delivered",
                            "token": "4821 0937 5512 8846 3019",
                            "units": "23.92",
                        }
                    },
                }
            )
        if path == "/requery":
            return json_response(
                {
                    "code": "000",
                    "requestId": req.json.get("request_id"),
                    "content": {
                        "transactions": {
                            "status": "delivered",
                            "token": "1111 2222 3333 4444 5555",
                        }
                    },
                }
            )
        return json_response({"code": "012", "response_description": "no such route"}, 404)

    return respond


class TestVtpassLiveTransport(ServerTest):
    responder = staticmethod(vtpass_responder)

    def client(self, **kwargs) -> VtpassClient:
        client = VtpassClient(
            env="sandbox",
            dry_run=False,
            username="stark-user",
            password="stark-pass",
            **kwargs,
        )
        client.base = self.server.base
        return client

    def test_verify_posts_expected_body_and_basic_auth(self):
        info = self.client().verify_meter("04512345678")

        self.assertEqual(info["Customer_Name"], "TUNDE ADEYEMI")
        self.assertEqual(len(self.server.requests), 1)
        req = self.server.requests[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.path, "/merchant-verify")
        self.assertEqual(
            req.json,
            {"billersCode": "04512345678", "serviceID": "ikeja-electric", "type": "prepaid"},
        )
        expected = base64.b64encode(b"stark-user:stark-pass").decode()
        self.assertEqual(req.header("Authorization"), f"Basic {expected}")
        self.assertEqual(req.header("Accept"), "application/json")

    def test_a_code_000_wrong_meter_is_a_refusal(self):
        """The live sandbox returns code 000 with WrongBillersCode: true."""
        self.restart(
            lambda req: json_response(
                {
                    "code": "000",
                    "content": {
                        "WrongBillersCode": True,
                        "error": "This meter is not correct or is not a valid "
                        "Ikeja Electric prepaid meter. Please check and try again",
                    },
                }
            )
        )

        with self.assertRaises(VtpassError) as caught:
            self.client().verify_meter("04512345678")
        self.assertEqual(caught.exception.code, "016")

    def test_variations_is_a_get_with_a_query_string(self):
        variations = self.client().list_variations("ikeja-electric")

        self.assertEqual([v["variation_code"] for v in variations], ["prepaid", "postpaid"])
        req = self.server.requests[0]
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.path, "/service-variations?serviceID=ikeja-electric")
        self.assertEqual(req.body, b"")

    def test_buy_sends_the_documented_payload_and_reads_the_token(self):
        result = self.client().buy(
            service_id="ikeja-electric",
            reference="04512345678",
            amount_ngn=5000,
            phone="08031234567",
            variation_code="prepaid",
            request_id="202610221200abcdef12",
        )

        self.assertTrue(result.delivered)
        self.assertEqual(result.token, "48210937551288463019")
        self.assertEqual(result.units, "23.92")
        self.assertEqual(result.amount_ngn, 5000)

        req = self.server.requests[0]
        self.assertEqual(req.path, "/pay")
        self.assertEqual(
            req.json,
            {
                "request_id": "202610221200abcdef12",
                "serviceID": "ikeja-electric",
                "billersCode": "04512345678",
                "amount": 5000,
                "phone": "08031234567",
                "variation_code": "prepaid",
            },
        )
        # Money is an integer on the wire, never a string or a float.
        self.assertIsInstance(req.json["amount"], int)

    def test_airtime_omits_variation_code_entirely(self):
        self.client().buy(
            service_id="mtn",
            reference="08031234567",
            amount_ngn=1000,
            phone="08031234567",
        )
        self.assertNotIn("variation_code", self.server.requests[0].json)

    def test_retry_reuses_the_same_request_id_on_the_wire(self):
        client = self.client()
        client.buy(
            service_id="ikeja-electric",
            reference="04512345678",
            amount_ngn=5000,
            phone="08031234567",
            request_id="same-intent-0001",
        )
        client.buy(
            service_id="ikeja-electric",
            reference="04512345678",
            amount_ngn=5000,
            phone="08031234567",
            request_id="same-intent-0001",
        )

        sent = [r.json["request_id"] for r in self.server.requests]
        self.assertEqual(sent, ["same-intent-0001", "same-intent-0001"])

    def test_requery_posts_the_request_id(self):
        result = self.client().query_transaction("202610221200abcdef12")

        self.assertTrue(result.delivered)
        self.assertEqual(result.token, "11112222333344445555")
        req = self.server.requests[0]
        self.assertEqual(req.path, "/requery")
        self.assertEqual(req.json, {"request_id": "202610221200abcdef12"})

    def test_api_key_headers_are_sent_when_configured(self):
        client = VtpassClient(
            env="sandbox",
            dry_run=False,
            api_key="api",
            public_key="pub",
            secret_key="sec",
        )
        client.base = self.server.base
        client.verify_meter("04512345678")

        req = self.server.requests[0]
        self.assertEqual(req.header("api-key"), "api")
        self.assertEqual(req.header("public-key"), "pub")
        self.assertEqual(req.header("secret-key"), "sec")


class TestVtpassLiveFailures(ServerTest):
    def test_pending_is_not_success_and_does_not_raise(self):
        self.restart(
            lambda req: json_response(
                {
                    "code": "099",
                    "response_description": "TRANSACTION PROCESSING",
                    "requestId": req.json.get("request_id"),
                    "content": {"transactions": {"status": "pending"}},
                }
            )
        )

        client = VtpassClient(dry_run=False, username="u", password="p")
        client.base = self.server.base
        result = client.buy(
            service_id="ikeja-electric",
            reference="04512345678",
            amount_ngn=5000,
            phone="08031234567",
            request_id="pending-0001",
        )

        self.assertFalse(result.delivered)
        self.assertTrue(result.pending)
        self.assertIsNone(result.token)

    def test_bad_meter_code_raises_with_speakable_copy(self):
        self.restart(
            lambda req: json_response(
                {"code": "016", "response_description": "INVALID METER NUMBER"}
            )
        )

        client = VtpassClient(dry_run=False, username="u", password="p")
        client.base = self.server.base
        with self.assertRaises(VtpassError) as caught:
            client.buy(
                service_id="ikeja-electric",
                reference="00000000000",
                amount_ngn=5000,
                phone="08031234567",
            )

        self.assertEqual(caught.exception.code, "016")
        self.assertIn("meter", caught.exception.user_message)
        self.assertFalse(caught.exception.retryable)

    def test_unreachable_biller_is_retryable(self):
        self.restart(
            lambda req: json_response({"code": "030", "response_description": "UNREACHABLE"})
        )

        client = VtpassClient(dry_run=False, username="u", password="p")
        client.base = self.server.base
        with self.assertRaises(VtpassError) as caught:
            client.buy(
                service_id="ikeja-electric",
                reference="04512345678",
                amount_ngn=5000,
                phone="08031234567",
            )
        self.assertTrue(caught.exception.retryable)

    def test_a_bare_string_401_is_invalid_credentials(self):
        self.restart(lambda req: raw_response(b'"Invalid Credentials."', 401))

        client = VtpassClient(dry_run=False, username="u", password="wrong")
        client.base = self.server.base
        with self.assertRaises(VtpassError) as caught:
            client.verify_meter("04512345678")

        self.assertEqual(caught.exception.code, "invalid_credentials")
        self.assertEqual(caught.exception.http_status, 401)

    def test_non_json_body_does_not_crash(self):
        self.restart(lambda req: raw_response(b"<html>gateway</html>", 502))

        client = VtpassClient(dry_run=False, username="u", password="p")
        client.base = self.server.base
        with self.assertRaises(VtpassError) as caught:
            client.verify_meter("04512345678")

        self.assertEqual(caught.exception.code, "invalid_response")
        self.assertEqual(caught.exception.http_status, 502)


# --- NEAR AI model ----------------------------------------------------------


class TestNearAiModelLive(ServerTest):
    def model(self) -> NearAiModel:
        return NearAiModel(api_key="test-key", base_url=self.server.base)

    def test_turn_posts_openai_shaped_request_and_parses_tool_calls(self):
        self.restart(
            lambda req: json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_abc",
                                        "type": "function",
                                        "function": {
                                            "name": "pay_bill",
                                            "arguments": json.dumps(
                                                {
                                                    "bill_id": "bill_home_meter",
                                                    "amount_ngn": 5000,
                                                }
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            )
        )

        turn = self.model().turn([{"role": "user", "content": "top up"}], [{"type": "function"}])

        self.assertIsNone(turn.content)
        self.assertEqual(len(turn.tool_calls), 1)
        call = turn.tool_calls[0]
        self.assertEqual(call.name, "pay_bill")
        self.assertEqual(call.id, "call_abc")
        self.assertEqual(call.arguments, {"bill_id": "bill_home_meter", "amount_ngn": 5000})

        req = self.server.requests[0]
        self.assertEqual(req.path, "/v1/chat/completions")
        self.assertEqual(req.header("Authorization"), "Bearer test-key")
        self.assertEqual(
            req.json,
            {
                "model": NEAR_AI_MODEL,
                "messages": [{"role": "user", "content": "top up"}],
                "tools": [{"type": "function"}],
                "tool_choice": "auto",
                "temperature": 0,
            },
        )

    def test_plain_text_reply_has_no_tool_calls(self):
        self.restart(
            lambda req: json_response(
                {"choices": [{"message": {"content": "You have 64,200 naira."}}]}
            )
        )

        turn = self.model().turn([{"role": "user", "content": "balance"}], [])
        self.assertEqual(turn.content, "You have 64,200 naira.")
        self.assertEqual(turn.tool_calls, [])

    def test_tool_arguments_that_are_not_json_do_not_crash(self):
        self.restart(
            lambda req: json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {"function": {"name": "x", "arguments": "not json"}}
                                ]
                            }
                        }
                    ]
                }
            )
        )

        turn = self.model().turn([{"role": "user", "content": "?"}], [])
        self.assertEqual(turn.tool_calls[0].arguments, {})
        self.assertTrue(turn.tool_calls[0].id.startswith("call_"))

    def test_no_choices_raises(self):
        self.restart(lambda req: json_response({"choices": []}))
        with self.assertRaises(RuntimeError):
            self.model().turn([{"role": "user", "content": "?"}], [])

    def test_http_error_includes_status_and_body(self):
        self.restart(lambda req: raw_response(b'{"error":"rate limited"}', 429))
        with self.assertRaises(RuntimeError) as caught:
            self.model().turn([{"role": "user", "content": "?"}], [])
        self.assertIn("429", str(caught.exception))

    def test_missing_key_refuses_before_any_request(self):
        with mock.patch.dict(os.environ, {"NEAR_AI_API_KEY": ""}, clear=False):
            with self.assertRaises(ValueError):
                NearAiModel(api_key=None)
        self.assertEqual(self.server.requests, [])


# --- Whisper STT ------------------------------------------------------------


class TestSttLive(ServerTest):
    WAV = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 16

    @staticmethod
    def real_wav(seconds: float = 0.2) -> bytes:
        """A decodable clip for the paths that must actually go through ffmpeg."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(b"\x00\x00" * int(16000 * seconds))
        return buf.getvalue()

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(stt, "NEAR_AI_BASE", self.server.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def restart(self, responder):
        super().restart(responder)
        # `transcribe` reads the module global at call time, so follow the server.
        stt.NEAR_AI_BASE = self.server.base

    def test_transcribe_posts_multipart_and_reads_text(self):
        self.restart(lambda req: json_response({"text": "  top up the house  "}))

        text, reason = stt.transcribe(self.WAV, api_key="test-key")

        self.assertEqual((text, reason), ("top up the house", stt.OK))
        req = self.server.requests[0]
        self.assertEqual(req.path, "/v1/audio/transcriptions")
        self.assertEqual(req.header("Authorization"), "Bearer test-key")
        self.assertIsNotNone(req.boundary)
        self.assertTrue(req.body.startswith(f"--{req.boundary}\r\n".encode()))
        self.assertIn(b'name="model"', req.body)
        self.assertIn(stt.NEAR_AI_STT_MODEL.encode(), req.body)
        self.assertIn(b'filename="audio.wav"', req.body)
        self.assertIn(b"Content-Type: audio/wav", req.body)
        self.assertIn(self.WAV, req.body)

    def test_transcribe_names_what_the_clip_really_is(self):
        self.restart(lambda req: json_response({"text": "top up the house"}))

        text, reason = stt.transcribe(self.WAV, api_key="k", mime="audio/webm")

        self.assertEqual((text, reason), ("top up the house", stt.OK))
        req = self.server.requests[0]
        self.assertIn(b'filename="audio.webm"', req.body)
        self.assertIn(b"Content-Type: audio/webm", req.body)

    def test_a_messy_mime_header_still_names_the_clip(self):
        self.restart(lambda req: json_response({"text": "hello"}))

        stt.transcribe(self.WAV, api_key="k", mime="audio/ogg; codecs=opus")

        req = self.server.requests[0]
        self.assertIn(b'filename="audio.ogg"', req.body)
        self.assertIn(b"Content-Type: audio/ogg\r\n", req.body)

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_a_browser_webm_is_decoded_before_it_is_sent(self):
        # Measured 2026-10-24: the provider refuses WebM as a container (400
        # "Audio could not be processed"), whatever the filename says. The
        # dashboard records WebM, so `hear` must decode it to WAV — and what
        # goes on the wire must be named WAV, or Whisper refuses it again.
        self.restart(lambda req: json_response({"text": "top up the house"}))

        text, reason = stt.hear(self.real_wav(), api_key="k", mime="audio/webm")

        self.assertEqual((text, reason), ("top up the house", stt.OK))
        req = self.server.requests[0]
        self.assertIn(b'filename="audio.wav"', req.body)
        self.assertIn(b"Content-Type: audio/wav", req.body)
        self.assertTrue(req.body.split(b"\r\n\r\n")[-1].startswith(b"RIFF"))

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_a_clip_ffmpeg_cannot_read_still_goes_to_whisper_unchanged(self):
        # Decoding failure must not fabricate words *or* silently drop the clip:
        # the provider sees exactly what the client sent and says it cannot hear
        # it, which is the honest answer.
        self.restart(lambda req: raw_response(b"not audio", 400))

        text, reason = stt.hear(b"this is not audio at all", api_key="k",
                                mime="audio/webm")

        self.assertEqual((text, reason), (None, stt.FAILED))
        req = self.server.requests[0]
        self.assertIn(b'filename="audio.webm"', req.body)

    def test_wav_is_sent_as_it_arrived(self):
        # The common path pays no ffmpeg cost at all.
        self.restart(lambda req: json_response({"text": "hello"}))

        stt.hear(self.WAV, api_key="k", mime="audio/wav")

        self.assertIn(b'filename="audio.wav"', self.server.requests[0].body)

    def test_empty_transcript_is_a_failure_not_a_guess(self):
        self.restart(lambda req: json_response({"text": "   "}))
        self.assertEqual(stt.transcribe(self.WAV, api_key="k"), (None, stt.FAILED))

    def test_unreachable_or_malformed_returns_failed(self):
        self.restart(lambda req: raw_response(b"not json", 500))
        self.assertEqual(stt.transcribe(self.WAV, api_key="k"), (None, stt.FAILED))

    def test_no_key_makes_no_network_call(self):
        with mock.patch.dict(os.environ, {"NEAR_AI_API_KEY": ""}, clear=False):
            self.assertEqual(stt.transcribe(self.WAV), (None, stt.NO_KEY))
        self.assertEqual(self.server.requests, [])


# --- NEAR RPC and the signed pay() round trip -------------------------------

BLOCK_HASH = bytes(range(32))
SIGNER = "agent.testnet"
VAULT = "vault.testnet"
SECRET = bytes(range(32))
KEY = near_tx.KeyPair.from_secret(SECRET)


class Reader:
    """A tiny borsh reader, so the encoder is checked against its own bytes."""

    def __init__(self, raw: bytes):
        self.raw = raw
        self.i = 0

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.raw):
            raise AssertionError(f"truncated at {self.i}, wanted {n} more bytes")
        out = self.raw[self.i : self.i + n]
        self.i += n
        return out

    def u8(self) -> int:
        return self.take(1)[0]

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "little")

    def u64(self) -> int:
        return int.from_bytes(self.take(8), "little")

    def u128(self) -> int:
        return int.from_bytes(self.take(16), "little")

    def string(self) -> str:
        return self.take(self.u32()).decode()

    def byte_vec(self) -> bytes:
        return self.take(self.u32())


def rpc_responder():
    def respond(req: Recorded):
        method = req.json["method"]
        if method == "block":
            return json_response(
                {
                    "jsonrpc": "2.0",
                    "id": "stark",
                    "result": {"header": {"hash": near_tx.b58encode(BLOCK_HASH)}},
                }
            )
        if method == "query":
            return json_response(
                {
                    "jsonrpc": "2.0",
                    "id": "stark",
                    "result": {"nonce": 41, "block_hash": near_tx.b58encode(BLOCK_HASH)},
                }
            )
        if method == "broadcast_tx_commit":
            return json_response(
                {
                    "jsonrpc": "2.0",
                    "id": "stark",
                    "result": {"status": {"SuccessValue": "AQ=="}},
                }
            )
        return json_response({"jsonrpc": "2.0", "id": "stark", "error": {"message": "?"}})

    return respond


class TestNearRpcLive(ServerTest):
    responder = staticmethod(rpc_responder)

    def rpc(self) -> near_tx.NearRpc:
        return near_tx.NearRpc(base_url=self.server.base)

    def test_signing_context_uses_the_access_key_nonce_plus_one(self):
        context = near_tx.fetch_signing_context(
            self.rpc(), signer_id=SIGNER, receiver_id=VAULT, key=KEY
        )

        self.assertEqual(context.nonce, 42)
        self.assertEqual(context.block_hash, BLOCK_HASH)
        query = self.server.requests[0]
        self.assertEqual(query.path, "/")
        self.assertEqual(query.json["jsonrpc"], "2.0")
        self.assertEqual(query.json["id"], "stark")
        self.assertEqual(query.json["method"], "query")
        self.assertEqual(
            query.json["params"],
            {
                "request_type": "view_access_key",
                "finality": "final",
                "account_id": SIGNER,
                "public_key": KEY.public_b58,
            },
        )

    def test_broadcast_sends_base64_of_signed_transaction(self):
        signer = VaultSigner(
            key=KEY,
            signer_id=SIGNER,
            receiver_id=VAULT,
            rpc=self.rpc(),
            broadcast=True,
        )

        summary = signer.sign_pay("04512345678", 5000)

        self.assertTrue(summary["signed"])
        self.assertTrue(summary["broadcast"])
        self.assertEqual(len(summary["tx_hash"]), 64)
        self.assertEqual(summary["outcome"], "AQ==")

        broadcast = [r for r in self.server.requests if r.json["method"] == "broadcast_tx_commit"]
        self.assertEqual(len(broadcast), 1)
        signed = base64.b64decode(broadcast[0].json["params"][0])

        # Signature is { key_type: KeyType, signature: [u8; 64] }, so the envelope is
        # tx + one key-type byte + 64 signature bytes.
        tx_bytes, signature = signed[:-65], signed[-64:]
        self.assertEqual(signed[-65], 0, "Signature::ED25519 key type")
        self.assertEqual(len(signature), 64)
        self.assertTrue(
            near_tx.ed25519_verify(KEY.public, near_tx.transaction_hash(tx_bytes), signature)
        )

        # Decode the exact envelope `near-primitives` expects and pin every field.
        # There is no version tag: V0 starts straight at the signer id length.
        r = Reader(tx_bytes)
        self.assertEqual(r.u32(), len(SIGNER), "signer id length is the first field")
        r.i -= 4
        self.assertEqual(r.string(), SIGNER)
        self.assertEqual(r.u8(), 0, "PublicKey::ED25519 variant")
        self.assertEqual(r.take(32), KEY.public)
        self.assertEqual(r.u64(), 42)
        self.assertEqual(r.string(), VAULT)
        self.assertEqual(r.take(32), BLOCK_HASH)
        self.assertEqual(r.u32(), 1, "one action")
        self.assertEqual(r.u8(), 2, "Action::FunctionCall variant")
        self.assertEqual(r.string(), "pay")
        args = json.loads(r.byte_vec())
        self.assertEqual(args, {"meter": "04512345678", "amount_ngn": "5000"})
        self.assertEqual(r.u64(), 100_000_000_000_000, "100 Tgas")
        self.assertEqual(r.u128(), 0, "no attached deposit")
        self.assertEqual(r.i, len(tx_bytes), "no trailing bytes before the signature")

    def test_dry_signer_never_broadcasts(self):
        signer = VaultSigner(
            key=KEY,
            signer_id=SIGNER,
            receiver_id=VAULT,
            rpc=self.rpc(),
            broadcast=False,
        )

        summary = signer.sign_pay("04512345678", 5000)

        self.assertTrue(summary["signed"])
        self.assertFalse(summary["broadcast"])
        self.assertNotIn("outcome", summary)
        methods = [r.json["method"] for r in self.server.requests]
        self.assertNotIn("broadcast_tx_commit", methods)

    def test_rpc_error_is_raised_with_detail(self):
        self.restart(
            lambda req: json_response(
                {"jsonrpc": "2.0", "id": "stark", "error": {"message": "Unknown access key"}}
            )
        )
        with self.assertRaises(near_tx.NearRpcError) as caught:
            self.rpc().access_key(SIGNER, KEY.public_b58)
        self.assertIn("Unknown access key", str(caught.exception))

    def test_access_key_without_nonce_is_an_error(self):
        self.restart(lambda req: json_response({"result": {}}))
        with self.assertRaises(near_tx.NearRpcError):
            self.rpc().access_key(SIGNER, KEY.public_b58)


if __name__ == "__main__":
    unittest.main()
