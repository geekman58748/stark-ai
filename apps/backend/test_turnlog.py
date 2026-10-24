"""turnlog — the conversation log, and the handlers that write to it.

Two layers, because a log nobody actually emits is not a log:

  * **The module**: the entry shapes, the files it writes, and the rule that a
    failing log never fails the request it is watching.
  * **The wire**: `server.h_voice` and `server.h_speak` append a line for every
    exit — answered, asleep, unheard — with the stage timings a person reads
    afterwards. The agent and the synthesiser are faked, so no model call is
    made and no state moves: only the logging is under test.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import turnlog
from agent import AgentReply


class EntryShapeTests(unittest.TestCase):
    def test_turn_carries_what_the_agent_did(self) -> None:
        entry = turnlog.turn(
            outcome="answered", heard="hello stark pay 5000", said="Stark, pay 5000",
            reply="Paid.", actions=["pay_bill"], receipt_id="r_1", token="4821",
            speak=False, model="google/gemini-2.5-flash-lite",
            ms={"total": 900, "agent": 800},
        )
        self.assertEqual(entry["kind"], "turn")
        self.assertEqual(entry["outcome"], "answered")
        self.assertEqual(entry["actions"], ["pay_bill"])
        self.assertEqual(entry["receipt_id"], "r_1")
        self.assertFalse(entry["speak_requested"])
        self.assertEqual(entry["ms"]["agent"], 800)

    def test_turn_defaults_are_empty_not_missing(self) -> None:
        entry = turnlog.turn(outcome="asleep")
        self.assertEqual(entry["heard"], "")
        self.assertIsNone(entry["said"])
        self.assertEqual(entry["actions"], [])
        self.assertEqual(entry["ms"], {})

    def test_speak_records_what_the_voice_was_given(self) -> None:
        entry = turnlog.speak(text="You have ₦64,200.", ms=420, reason="ok",
                              stream=True, provider="elevenlabs")
        self.assertEqual(entry["kind"], "speak")
        # The words on screen keep the sign; the provider gets the spoken form.
        self.assertEqual(entry["spoken"], "You have 64,200 naira.")
        self.assertEqual(entry["text"], "You have ₦64,200.")
        self.assertTrue(entry["stream"])
        self.assertEqual(entry["ms"], 420)


class RecordingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"STARK_TURN_LOG": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = Path(self.tmp.name)

    def test_records_one_json_line_per_call(self) -> None:
        turnlog.record(turnlog.turn(outcome="answered", heard="hello stark"))
        turnlog.record(turnlog.turn(outcome="asleep", heard="what time is it"))
        entries = turnlog.lines(self.folder)
        self.assertEqual([e["outcome"] for e in entries], ["answered", "asleep"])
        self.assertTrue(all(e["ts"] for e in entries))
        self.assertTrue(all(e["kind"] == "turn" for e in entries))

    def test_clip_is_saved_beside_the_log_and_referenced(self) -> None:
        clip = b"RIFF" + b"\x00" * 32
        turnlog.record(turnlog.turn(outcome="answered"), clip=clip,
                       mime="audio/webm;codecs=opus")
        entry = turnlog.lines(self.folder)[0]
        self.assertEqual(entry["mime"], "audio/webm;codecs=opus")
        self.assertEqual(entry["audio_bytes"], len(clip))
        saved = self.folder / entry["audio"]
        self.assertTrue(saved.exists(), entry["audio"])
        self.assertEqual(saved.suffix, ".webm")
        self.assertEqual(saved.read_bytes(), clip)

    def test_unknown_mime_falls_back_to_bin(self) -> None:
        turnlog.record(turnlog.turn(outcome="answered"), clip=b"x", mime="application/x")
        entry = turnlog.lines(self.folder)[0]
        self.assertTrue(entry["audio"].endswith(".bin"))

    def test_lines_survives_a_ragged_file(self) -> None:
        target = self.folder / turnlog.LOG_NAME
        self.folder.mkdir(parents=True, exist_ok=True)
        target.write_text('{"kind": "turn"}\nnot json at all\n\n', encoding="utf-8")
        self.assertEqual([e["kind"] for e in turnlog.lines(self.folder)], ["turn"])

    def test_off_by_default_writes_nothing(self) -> None:
        with mock.patch.dict(os.environ, {"STARK_TURN_LOG": "0"}):
            turnlog.record(turnlog.turn(outcome="answered"))
        self.assertFalse((self.folder / turnlog.LOG_NAME).exists())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(turnlog.enabled())

    def test_flag_1_means_the_default_directory(self) -> None:
        with mock.patch.dict(os.environ, {"STARK_TURN_LOG": "1"}):
            self.assertTrue(turnlog.enabled())
            self.assertEqual(turnlog.log_dir().name, "turns")
            self.assertEqual(turnlog.log_dir().parent,
                             Path(turnlog.__file__).resolve().parent / "logs")

    def test_an_unwritable_target_never_raises(self) -> None:
        # A path that is already a file: `mkdir` will fail on it, which is
        # exactly the kind of failure that must not reach the request.
        blocker = self.folder / "blocked"
        blocker.write_text("x", encoding="utf-8")
        with mock.patch.dict(os.environ, {"STARK_TURN_LOG": str(blocker)}):
            turnlog.record(turnlog.turn(outcome="answered"), clip=b"RIFF")
        self.assertIsNone(turnlog.record(turnlog.turn(outcome="answered")))


class _FakeAgent:
    """Stands in for the built agent: no model call, no state, no network."""

    model = SimpleNamespace(model="test-model", name="fake")

    def __init__(self) -> None:
        self.seen: list[str] = []

    def respond(self, said: str) -> AgentReply:
        self.seen.append(said)
        return AgentReply(reply="Your balance is 64,200 naira.")


class ServerTurnLogTests(unittest.TestCase):
    """The wire: every exit of `h_voice` leaves a line behind."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"STARK_TURN_LOG": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)

        import server
        self.server = server
        self.agent = _FakeAgent()
        agent_patch = mock.patch.object(server, "AGENT", self.agent)
        agent_patch.start()
        self.addCleanup(agent_patch.stop)
        # `speak: true` is exercised too, so synthesis must not reach a provider.
        tts_patch = mock.patch.object(server.tts, "synthesize",
                                      return_value=(b"RIFF" + b"\x00" * 8, "ok"))
        tts_patch.start()
        self.addCleanup(tts_patch.stop)
        self.folder = Path(self.tmp.name)

    def test_answered_turn_logs_transcript_reply_and_timings(self) -> None:
        status, payload = self.server.h_voice(
            {"transcript_hint": "hello stark what's my balance", "speak": "false"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["reply"], "Your balance is 64,200 naira.")
        entry = [e for e in turnlog.lines(self.folder) if e["kind"] == "turn"][0]
        self.assertEqual(entry["outcome"], "answered")
        self.assertEqual(entry["heard"], "hello stark what's my balance")
        self.assertEqual(entry["said"], "hello stark what's my balance")
        self.assertEqual(entry["reply"], "Your balance is 64,200 naira.")
        self.assertEqual(entry["model"], "test-model")
        self.assertFalse(entry["speak_requested"])
        # A missing stage key means "this stage did not run" — no clip, no
        # synthesis — rather than a stage that finished in 0 ms.
        self.assertIn("total", entry["ms"])
        self.assertIn("agent", entry["ms"])
        self.assertNotIn("stt", entry["ms"])
        self.assertNotIn("tts", entry["ms"])
        self.assertNotIn("audio", entry)

    def test_speak_true_records_the_synthesis_time(self) -> None:
        self.server.h_voice({"transcript_hint": "hello stark what's my balance"})
        entry = [e for e in turnlog.lines(self.folder) if e["kind"] == "turn"][0]
        self.assertTrue(entry["speak_requested"])
        self.assertIn("tts", entry["ms"])

    def test_wake_gate_refusal_is_logged_not_silent(self) -> None:
        status, payload = self.server.h_voice(
            {"transcript_hint": "tell me a joke", "speak": "false"})

        self.assertEqual(status, 200)
        self.assertTrue(payload["ignored"])
        self.assertEqual(self.agent.seen, [])          # the agent was not asked
        entry = [e for e in turnlog.lines(self.folder) if e["kind"] == "turn"][0]
        self.assertEqual(entry["outcome"], "asleep")
        self.assertEqual(entry["heard"], "tell me a joke")
        self.assertIsNone(entry["said"])
        self.assertIsNone(entry["reply"])

    def test_a_failing_log_does_not_fail_the_turn(self) -> None:
        with mock.patch.object(turnlog, "_append", side_effect=OSError("disk full")):
            status, payload = self.server.h_voice(
                {"transcript_hint": "hello stark what's my balance", "speak": "false"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["reply"], "Your balance is 64,200 naira.")

    def test_speak_handler_logs_provider_and_spoken_text(self) -> None:
        status, payload = self.server.h_speak({"text": "You have ₦64,200."})

        self.assertEqual(status, 200)
        self.assertIsNotNone(payload["audio"])
        entry = [e for e in turnlog.lines(self.folder) if e["kind"] == "speak"][0]
        self.assertEqual(entry["text"], "You have ₦64,200.")
        self.assertEqual(entry["spoken"], "You have 64,200 naira.")
        self.assertFalse(entry["stream"])
        self.assertEqual(entry["tts"], "ok")
        self.assertIn(entry["provider"], {"elevenlabs", "kokoro"})
        self.assertIsInstance(entry["ms"], int)


if __name__ == "__main__":
    unittest.main()
