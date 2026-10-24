"""Text to speech: ElevenLabs when keyed, the local Kokoro sidecar, or silence.

Two providers, one contract: `synthesize` returns `(wav, reason)` on every path,
so a caller can never mistake "nothing happened" for audio.

1. **ElevenLabs Flash** (`ELEVENLABS_API_KEY`) — preferred when set. Flash v2.5
   answers a Stark-length reply in well under a second against Kokoro's 1.5–2s,
   and it says `₦5,000`, "Ikeja" and dates correctly. Raw 24 kHz mono PCM comes
   back and is wrapped in a WAV here, because the rest of the system — the
   dashboard's `data:` URL, `ffmpeg` for Telegram, the `/v1/speak` contract — is
   spoken to in WAV and changing that is not worth a voice.
2. **The local Kokoro sidecar** (`STARK_TTS_URL`) — offline fallback, and what
   runs today with no ElevenLabs key.

With neither configured, or with everything refusing, the result is
`(None, reason)` and the caller replies in plain text. Voice never gates a
reply: `stt.py` refuses to invent a transcript, this refuses to invent audio.

`voice_note` adds the step Telegram needs: ffmpeg encodes the WAV to
OGG/Opus, the only container `sendVoice` accepts. No ffmpeg → `None` → the
reply goes as text.
"""

from __future__ import annotations

import io
import json
import os
import re
import urllib.error
import urllib.request
import wave

import audio

TTS_MODEL = os.environ.get("STARK_TTS_MODEL") or "kokoro"
TTS_VOICE = os.environ.get("STARK_TTS_VOICE") or "af_heart"

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
# Flash is the fast one. The default voice must be a **premade** one: a free
# key gets HTTP 402 `paid_plan_required` on library/cloned voices over the API
# (measured 2026-10-24, against Rachel `21m00Tcm4TlvDq8ikWAM`).
ELEVENLABS_MODEL = "eleven_flash_v2_5"
ELEVENLABS_VOICE = "onwK4e9ZLuTAKqWW03F9"   # Daniel — steady broadcaster (premade)
ELEVENLABS_PCM_RATE = 24000

OK = "ok"
NO_URL = "no_url"
FAILED = "failed"
ELEVENLABS_FAILED = "elevenlabs_failed"

# The naira sign is not in either voice's pronunciation dictionary. Measured
# 2026-10-24 by synthesising a real reply and transcribing the clip back:
# ElevenLabs and Kokoro both said the letter N — "₦64,200" came back as
# "N64200" — so an amount the user hears has to be written the way a person
# says it: the number, then the word "naira". The text on screen keeps the
# sign; only the voice is spelled to.
_AMOUNT = re.compile(r"₦\s*(\d[\d,]*(?:\.\d+)?)")


def speakable(text: str) -> str:
    """What the voice is asked to say. Never used to change screen copy.

    `₦64,200` → `64,200 naira`; a stray `₦` with no number → `naira`. Everything
    else is passed through untouched, because the reply is already written to
    be read aloud.
    """
    return _AMOUNT.sub(r"\1 naira", text).replace("₦", "naira")


def _pcm_to_wav(pcm: bytes, rate: int = ELEVENLABS_PCM_RATE) -> bytes:
    """Raw 16-bit mono PCM → a WAV, since nothing here accepts loose PCM."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _elevenlabs_speech(text: str, *, base: str | None = None,
                       timeout: float = 10.0) -> tuple[bytes | None, str]:
    """Text in, WAV out — `(None, reason)` on anything that goes wrong.

    Reads config at call time, so a key can appear without a restart. The
    timeout is short on purpose: a slow voice must fall through to the local
    sidecar rather than hold the reply hostage.
    """
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return None, NO_URL
    base = base or os.environ.get("ELEVENLABS_API_URL") or ELEVENLABS_API
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or ELEVENLABS_VOICE
    model_id = os.environ.get("ELEVENLABS_MODEL_ID") or ELEVENLABS_MODEL

    body = json.dumps({
        "text": text.strip(),
        "model_id": model_id,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
    }).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/text-to-speech/{voice_id}?output_format=pcm_24000",
        data=body, method="POST",
        headers={"Content-Type": "application/json", "xi-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            pcm = res.read()
    except urllib.error.HTTPError as err:
        err.close()
        return None, ELEVENLABS_FAILED
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ELEVENLABS_FAILED

    if not pcm or len(pcm) < 2:
        return None, ELEVENLABS_FAILED
    return _pcm_to_wav(pcm), OK


def stream_elevenlabs(text: str, *, base: str | None = None,
                      timeout: float = 20.0):
    """Yield MP3 chunks as ElevenLabs produces them — a generator, not bytes.

    The point is time-to-first-sound: the buffered path waits the whole ~1.4s
    for synthesis before the client can start playing, this sends whatever has
    arrived and lets the player start on the first few kilobytes. No key, or a
    refusal, yields nothing at all and the caller falls back to a whole reply.
    """
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or not text or not text.strip():
        return
    text = speakable(text)
    base = base or os.environ.get("ELEVENLABS_API_URL") or ELEVENLABS_API
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or ELEVENLABS_VOICE
    model_id = os.environ.get("ELEVENLABS_MODEL_ID") or ELEVENLABS_MODEL

    body = json.dumps({
        "text": text.strip(),
        "model_id": model_id,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
    }).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/text-to-speech/{voice_id}/stream"
        "?output_format=mp3_44100_128",
        data=body, method="POST",
        headers={"Content-Type": "application/json", "xi-api-key": key},
    )
    try:
        res = urllib.request.urlopen(req, timeout=timeout)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return  # the caller falls back; a refusal here is not an error to 500 on
    try:
        with res:
            # read1, not read: `read` fills the whole buffer before returning
            # and would sit on the socket until the clip was finished — the
            # one thing this function exists to avoid.
            reader = getattr(res, "read1", None) or res.read
            while True:
                chunk = reader(16384)
                if not chunk:
                    break
                yield chunk
    except (TimeoutError, OSError):  # a dropped stream plays what it already said
        return


def synthesize(text: str, *, url: str | None = None, voice: str | None = None,
               timeout: float = 30.0) -> tuple[bytes | None, str]:
    """Text in, 24 kHz mono WAV out. `(wav, reason)` on every path.

    ElevenLabs first when a key exists, then the sidecar, then nothing. Reads
    config at call time (like `stt.transcribe`), so tests and the demo can
    point it elsewhere without rebuilding the server.
    """
    if not text or not text.strip():
        return None, FAILED
    text = speakable(text)

    if os.environ.get("ELEVENLABS_API_KEY"):
        wav, why = _elevenlabs_speech(text, timeout=min(timeout, 10.0))
        if wav is not None:
            return wav, OK
        # ElevenLabs down or unpaid: the sidecar is next, not silence.

    base = url if url is not None else os.environ.get("STARK_TTS_URL")
    if not base:
        # Nothing configured: no_key/no_url. If ElevenLabs was attempted and
        # only then did we find nothing to fall back to, say so honestly.
        return None, (ELEVENLABS_FAILED if os.environ.get("ELEVENLABS_API_KEY")
                      else NO_URL)

    body = json.dumps({
        "model": TTS_MODEL,
        "input": text.strip(),
        "voice": voice or TTS_VOICE,
        "response_format": "wav",
    }).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/v1/audio/speech",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            wav = res.read()
    except urllib.error.HTTPError as err:
        err.close()
        return None, FAILED
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, FAILED

    if not wav or len(wav) < 44:
        return None, FAILED
    return wav, OK


def voice_note(text: str, *, url: str | None = None, voice: str | None = None,
               timeout: float = 30.0) -> bytes | None:
    """Text in, OGG/Opus voice-note bytes out — or `None`, so the caller
    sends text instead. Every refusal lands here: no provider, both providers
    down, empty audio, no ffmpeg."""
    wav, _why = synthesize(text, url=url, voice=voice, timeout=timeout)
    if wav is None:
        return None
    return audio.encode_opus(wav)
