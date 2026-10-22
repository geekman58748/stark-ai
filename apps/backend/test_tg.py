"""M4 tests: the Telegram door, its gates, and the audio path.

Hermetic by design — the agent, identity store, file download, transcription
and sending are all injected fakes. The only real dependencies exercised are
`identities.IdentityStore` (a temp SQLite file) and, when `ffmpeg` is present,
`audio.transcode` on a WAV this test generates itself. No network, no keys.
"""

from __future__ import annotations

import io
import tempfile
import unittest
import wave
from pathlib import Path

import audio
import identities
import stt
import telegram
from telegram import TelegramAdapter, TelegramError


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


class FakeAgent:
    def __init__(self):
        self.transcripts: list[str] = []

    def respond(self, transcript: str):
        self.transcripts.append(transcript)

        class Reply:
            reply = "You've got about 11.4 units left."
        return Reply()


class FakeIdentities(identities.IdentityStore):
    def __init__(self):
        super().__init__(Path(tempfile.mkdtemp()) / "test.db")


def _update(chat_id=42, text="hello stark what's left", message_id=1,
            update_id=100, first_name="Tunde", voice=None):
    message = {
        "message_id": message_id,
        "chat": {"id": chat_id},
        "from": {"id": chat_id, "first_name": first_name},
    }
    if text is not None:
        message["text"] = text
    if voice is not None:
        message["voice"] = voice
    return {"update_id": update_id, "message": message}


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.agent = FakeAgent()
        self.ids = FakeIdentities()
        self.sent: list[tuple[int, str]] = []
        self.adapter = TelegramAdapter(
            agent=self.agent,
            identities=self.ids,
            bot_token="123:TEST",
            secret="s3cret",
            send=lambda chat_id, text: self.sent.append((chat_id, text)) or True,
        )

    def linked(self, chat_id=42):
        code = self.ids.issue_code("user_tunde")
        self.ids.consume_code(code, telegram.CHANNEL, str(chat_id), "Tunde")


class TestWebhookSecret(AdapterCase):
    def test_unconfigured_adapter_refuses_everything(self):
        adapter = TelegramAdapter(agent=self.agent, identities=self.ids)
        self.assertFalse(adapter.enabled)
        with self.assertRaises(TelegramError) as caught:
            adapter.verify_secret("anything")
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(caught.exception.code, "webhook_unconfigured")

    def test_missing_secret_header_is_401(self):
        with self.assertRaises(TelegramError) as caught:
            self.adapter.verify_secret(None)
        self.assertEqual(caught.exception.code, "webhook_unverified")

    def test_wrong_secret_is_401(self):
        with self.assertRaises(TelegramError):
            self.adapter.verify_secret("not-the-secret")

    def test_right_secret_passes(self):
        self.adapter.verify_secret("s3cret")   # no exception


class TestIdentityGate(AdapterCase):
    def test_unlinked_sender_never_reaches_the_agent(self):
        reply = self.adapter._route(_update(text="hello stark pay 5000").get("message"),
                                    "hello stark pay 5000", "42", "Tunde", 42)
        # The agent was never called, and the reply is only linking instructions.
        self.assertEqual(self.agent.transcripts, [])
        self.assertIn("do not know this chat", (reply or "").lower())
        self.assertIn("link", (reply or "").lower())
        self.assertNotIn("11.4", (reply or ""))   # no state leaked

    def test_link_then_ask(self):
        self.linked()
        result = self.adapter.handle_update(_update(text="hello stark what's left"))
        self.assertEqual(result["handled"], "agent")
        self.assertEqual(self.agent.transcripts, ["hello stark what's left"])

    def test_link_command_binds_and_rejects_bad_codes(self):
        code = self.ids.issue_code("user_tunde")
        bad = self.adapter._route(_update(text="/link 999999").get("message"),
                                  "/link 999999", "42", None, 42)
        self.assertIn("did not work", bad)
        good = self.adapter._route(_update(text=f"/link {code}").get("message"),
                                   f"/link {code}", "42", "Tunde", 42)
        self.assertIn("Linked", good)
        self.assertEqual(self.ids.resolve(telegram.CHANNEL, "42"), "user_tunde")

    def test_whoami_and_unlink(self):
        self.linked()
        self.assertIn("user_tunde", self.adapter._route(_update(text="/whoami").get("message"),
                                                        "/whoami", "42", None, 42))
        self.adapter._route(_update(text="/unlink").get("message"), "/unlink", "42", None, 42)
        self.assertIsNone(self.ids.resolve(telegram.CHANNEL, "42"))

    def test_duplicate_update_is_processed_once(self):
        self.linked()
        self.adapter.handle_update(_update(message_id=7, update_id=7))
        self.adapter.handle_update(_update(message_id=7, update_id=7))
        self.assertEqual(len(self.agent.transcripts), 1)
        self.assertEqual(self.adapter.stats["duplicates"], 1)


class TestVoice(AdapterCase):
    def setUp(self):
        super().setUp()
        self.wav = _tiny_wav()
        self.adapter.download = lambda file_id: self.wav
        self.linked()

    def test_voice_with_wake_word_is_transcribed_and_answered(self):
        self.adapter.transcribe = lambda wav: ("hello stark what's left", "ok")
        result = self.adapter.handle_update(
            _update(text=None, voice={"file_id": "f1"}))
        self.assertEqual(result["handled"], "agent")
        self.assertEqual(self.agent.transcripts, ["hello stark what's left"])

    def test_voice_without_wake_word_stays_silent(self):
        self.adapter.transcribe = lambda wav: ("what's the weather", "ok")
        result = self.adapter.handle_update(
            _update(text=None, voice={"file_id": "f1"}))
        self.assertEqual(result["handled"], "asleep")
        self.assertEqual(self.agent.transcripts, [])

    def test_no_speech_backend_says_so_instead_of_guessing(self):
        self.adapter.transcribe = stt.transcribe   # no key in the environment
        result = self.adapter.handle_update(
            _update(text=None, voice={"file_id": "f1"}))
        self.assertEqual(result["handled"], "voice_unheard")
        self.assertEqual(self.agent.transcripts, [])
        self.assertIn("cannot hear voice notes", self.sent[-1][1])

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_real_decode_of_generated_wav(self):
        wav, why = audio.transcode(self.wav)
        self.assertEqual(why, audio.OK)
        self.assertTrue(wav.startswith(b"RIFF"))


class TestSttFallback(unittest.TestCase):
    def test_no_key_is_honest_not_hallucinated(self):
        text, why = stt.transcribe(_tiny_wav(), api_key="")
        self.assertIsNone(text)
        self.assertEqual(why, stt.NO_KEY)


class TestAudioGuards(unittest.TestCase):
    def test_empty_and_oversized_inputs_are_refused(self):
        self.assertEqual(audio.transcode(b"")[1], audio.DECODE_FAILED)
        self.assertEqual(audio.transcode(b"x" * 100, max_input_bytes=10)[1], audio.TOO_LARGE)

    @unittest.skipUnless(audio.ffmpeg_available(), "ffmpeg not installed")
    def test_garbage_is_refused_not_guessed(self):
        self.assertEqual(audio.transcode(b"this is not audio at all" * 20)[1],
                         audio.DECODE_FAILED)


if __name__ == "__main__":
    unittest.main()
