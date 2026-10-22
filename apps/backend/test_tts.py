"""TTS tests: the client's fail-closed rules, the sidecar's request handling,
and the ffmpeg voice-note encode — all against a fake sidecar.

Hermetic by design. `tts_server` imports kokoro lazily, which is exactly what
lets these tests import it in the standard-library-only test env — no torch,
no model, no keys. The only real dependency exercised is `ffmpeg`, and only to
encode a WAV this test builds itself.
"""

from __future__ import annotations

import io
import json
import os
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import audio
import tts
import tts_server


def _tiny_wav(seconds: float = 0.05, rate: int = 16000) -> bytes:
    """A valid WAV built in memory — enough for ffmpeg to decode."""
    frames = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class FakeSidecar:
    """A real HTTP server speaking the OpenAI speech shape, with canned bytes."""

    def __init__(self, payload: bytes = b"RIFF" + b"\x00" * 60, status: int = 200):
        self.payload = payload
        self.status = status
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - required name
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                outer.requests.append(json.loads(raw or b"{}"))
                self.send_response(outer.status)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(outer.payload)))
                self.end_headers()
                self.wfile.write(outer.payload)

            def log_message(self, fmt, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class ClientCase(unittest.TestCase):
    """`tts` reads STARK_TTS_URL at call time, so the tests own the env."""

    def setUp(self):
        self.saved = os.environ.pop("STARK_TTS_URL", None)

    def tearDown(self):
        if self.saved is not None:
            os.environ["STARK_TTS_URL"] = self.saved

    def test_no_url_is_a_refusal_not_a_guess(self):
        wav, why = tts.synthesize("hello stark")
        self.assertIsNone(wav)
        self.assertEqual(why, tts.NO_URL)

    def test_no_url_means_no_voice_note(self):
        self.assertIsNone(tts.voice_note("hello stark"))

    def test_empty_text_is_failed_not_a_request(self):
        side = FakeSidecar()
        try:
            wav, why = tts.synthesize("   ", url=side.url)
        finally:
            side.close()
        self.assertIsNone(wav)
        self.assertEqual(why, tts.FAILED)
        self.assertEqual(side.requests, [])

    def test_round_trip_sends_the_openai_shape(self):
        canned = b"RIFF" + b"\x00" * 60
        side = FakeSidecar(payload=canned)
        try:
            wav, why = tts.synthesize("hello stark", url=side.url)
        finally:
            side.close()
        self.assertEqual(why, tts.OK)
        self.assertEqual(wav, canned)

        sent = side.requests[0]
        self.assertEqual(sent["input"], "hello stark")
        self.assertEqual(sent["response_format"], "wav")
        self.assertTrue(sent["model"])
        self.assertTrue(sent["voice"])

    def test_sidecar_error_is_failed_not_empty_audio(self):
        side = FakeSidecar(payload=b"boom", status=500)
        try:
            wav, why = tts.synthesize("hello stark", url=side.url)
        finally:
            side.close()
        self.assertIsNone(wav)
        self.assertEqual(why, tts.FAILED)

    def test_tiny_response_is_failed_not_audio(self):
        side = FakeSidecar(payload=b"no")
        try:
            wav, why = tts.synthesize("hello stark", url=side.url)
        finally:
            side.close()
        self.assertIsNone(wav)
        self.assertEqual(why, tts.FAILED)

    def test_sidecar_down_is_failed(self):
        # A port nothing is listening on: the refusal must be immediate and quiet.
        wav, why = tts.synthesize("hello stark", url="http://127.0.0.1:1",
                                  timeout=2.0)
        self.assertIsNone(wav)
        self.assertEqual(why, tts.FAILED)

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_voice_note_is_ogg_opus(self):
        side = FakeSidecar(payload=_tiny_wav())
        try:
            note = tts.voice_note("hello stark", url=side.url)
        finally:
            side.close()
        self.assertIsNotNone(note)
        self.assertTrue(note.startswith(b"OggS"), note[:8] if note else None)


class FakeSynth:
    def __init__(self, wav: bytes = b"RIFF" + b"\x00" * 60, boom: bool = False):
        self.wav = wav
        self.boom = boom

    def synthesize(self, text: str, voice: str) -> bytes:
        if self.boom:
            raise RuntimeError("model on fire")
        return self.wav


class SidecarCase(unittest.TestCase):
    """`build_response` is pure, so the sidecar is testable without torch."""

    def body_of(self, payload, synth: FakeSynth | None = None) -> tuple[int, str, bytes]:
        return tts_server.build_response(payload, synth or FakeSynth())

    def error_message(self, body: bytes) -> str:
        return json.loads(body)["error"]["message"]

    def test_good_request_serves_wav(self):
        status, ctype, body = self.body_of({"input": "hello stark"})
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "audio/wav")
        self.assertTrue(body.startswith(b"RIFF"))

    def test_defaults_voice_and_format(self):
        status, _, _ = self.body_of({"input": "hello"})
        self.assertEqual(status, 200)   # no voice / response_format keys needed

    def test_missing_input_is_400(self):
        status, _, body = self.body_of({})
        self.assertEqual(status, 400)
        self.assertIn("input", self.error_message(body))

    def test_blank_or_non_string_input_is_400(self):
        for payload in ({"input": "   "}, {"input": 7}, {"input": ["hello"]}):
            status, _, _ = self.body_of(payload)
            self.assertEqual(status, 400, payload)

    def test_overlong_input_is_400(self):
        status, _, _ = self.body_of({"input": "x" * (tts_server.MAX_INPUT_CHARS + 1)})
        self.assertEqual(status, 400)

    def test_only_wav_is_served(self):
        status, _, body = self.body_of({"input": "hi", "response_format": "mp3"})
        self.assertEqual(status, 400)
        self.assertIn("wav", self.error_message(body))

    def test_bad_voice_is_400_before_any_synthesis(self):
        for voice in ("af;rm -rf", "../heart", "AF_HEART", "dropin", ""):
            if not voice:
                continue   # empty falls back to the default voice, by design
            status, _, _ = self.body_of({"input": "hi", "voice": voice})
            self.assertEqual(status, 400, voice)

    def test_non_object_body_is_400(self):
        for payload in ("hello", ["input"], 7, None):
            status, _, _ = self.body_of(payload)
            self.assertEqual(status, 400, payload)

    def test_synth_failure_is_500_not_partial_audio(self):
        status, ctype, body = self.body_of({"input": "hi"}, FakeSynth(boom=True))
        self.assertEqual(status, 500)
        self.assertEqual(ctype, "application/json")
        self.assertIn("server_error", body.decode())

    def test_empty_synthesis_is_500(self):
        status, _, _ = self.body_of({"input": "hi"}, FakeSynth(wav=b""))
        self.assertEqual(status, 500)


class TestOpusEncode(unittest.TestCase):
    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_wav_encodes_to_ogg(self):
        out = audio.encode_opus(_tiny_wav())
        self.assertIsNotNone(out)
        self.assertTrue(out.startswith(b"OggS"))

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_garbage_is_refused_not_guessed(self):
        self.assertIsNone(audio.encode_opus(b"this is not audio at all" * 20))

    def test_tiny_and_oversized_inputs_are_refused(self):
        self.assertIsNone(audio.encode_opus(b""))
        self.assertIsNone(audio.encode_opus(_tiny_wav(), max_input_bytes=10))


if __name__ == "__main__":
    unittest.main()
