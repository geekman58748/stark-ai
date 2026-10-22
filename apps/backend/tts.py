"""Text to speech: the local Kokoro sidecar, or an honest silence.

The OpenAI speech shape, against `STARK_TTS_URL` — the sidecar in
`tts_server.py`. With no URL configured (the default), or a sidecar that
cannot answer, `synthesize` returns `(None, reason)` and the caller falls
back to plain text. Voice never gates a reply: `stt.py` refuses to invent a
transcript, this refuses to invent audio, and both fail the same way — the
answer still arrives, just not spoken.

`voice_note` adds the step Telegram needs: ffmpeg encodes the WAV to
OGG/Opus, the only container `sendVoice` accepts. No ffmpeg → `None` → the
reply goes as text.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import audio

TTS_MODEL = os.environ.get("STARK_TTS_MODEL") or "kokoro"
TTS_VOICE = os.environ.get("STARK_TTS_VOICE") or "af_heart"

OK = "ok"
NO_URL = "no_url"
FAILED = "failed"


def synthesize(text: str, *, url: str | None = None, voice: str | None = None,
               timeout: float = 30.0) -> tuple[bytes | None, str]:
    """Text in, 24 kHz mono WAV out. `(wav, reason)` on every path.

    Reads config at call time (like `stt.transcribe`), so tests and the demo
    can point it elsewhere without rebuilding the server.
    """
    base = url if url is not None else os.environ.get("STARK_TTS_URL")
    if not base:
        return None, NO_URL
    if not text or not text.strip():
        return None, FAILED

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
    sends text instead. Every refusal lands here: no URL, sidecar down,
    empty audio, no ffmpeg."""
    wav, _why = synthesize(text, url=url, voice=voice, timeout=timeout)
    if wav is None:
        return None
    return audio.encode_opus(wav)
