"""Voice-note normalisation: whatever Telegram sends → 16 kHz mono WAV.

Whisper wants 16 kHz mono; Telegram voice notes are OGG/Opus, voice messages
from other channels can be MP3 or M4A. `ffmpeg` is the only decoder that reads
all of them, and it is already on this machine (9.0.2, verified 2026-10-22).

The rules that keep this safe:

- **Bounded input.** A file over `max_input_bytes` or `max_seconds` is refused
  before decoding, so a hostile upload cannot eat the process.
- **Failure is loud and cheap.** A decode that fails returns a reason; nothing
  is guessed, no audio is forwarded, and temp files live in a TemporaryDirectory
  that cleans itself up.
- **ffmpeg may be absent.** Then `transcode` says so and the caller replies
  plainly ("send it as text") instead of pretending it heard something.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")

MAX_INPUT_BYTES = 5 * 1024 * 1024   # Telegram voice notes are well under this.
MAX_SECONDS = 60                    # One minute of speech is plenty for a bill.

OK = "ok"
TOO_LARGE = "too_large"
DECODE_FAILED = "decode_failed"
NO_FFMPEG = "no_ffmpeg"


def ffmpeg_available() -> bool:
    return FFMPEG is not None


def transcode(raw: bytes, *, filename: str = "voice.ogg",
              max_input_bytes: int = MAX_INPUT_BYTES,
              max_seconds: int = MAX_SECONDS) -> tuple[bytes | None, str]:
    """Decode `raw` to 16 kHz mono s16 WAV. Returns `(wav, reason)`.

    On failure `wav` is None and `reason` is one of `NO_FFMPEG`, `TOO_LARGE`,
    `DECODE_FAILED`. Nothing is ever partially returned.
    """
    if not raw:
        return None, DECODE_FAILED
    if len(raw) > max_input_bytes:
        return None, TOO_LARGE
    if FFMPEG is None:
        return None, NO_FFMPEG

    with tempfile.TemporaryDirectory(prefix="stark_audio_") as tmp:
        src = Path(tmp) / (Path(filename).name or "voice")
        dst = Path(tmp) / "out.wav"
        src.write_bytes(raw)
        # To a file, not a pipe: ffmpeg cannot seek a pipe and then writes
        # 0xFFFFFFFF sizes into the WAV header, which some decoders reject.
        proc = subprocess.run(
            [
                FFMPEG, "-v", "error", "-y",
                "-i", str(src),
                "-t", str(max_seconds),
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                "-f", "wav", str(dst),
            ],
            capture_output=True,
        )
        wav = dst.read_bytes() if dst.exists() else b""
        if proc.returncode != 0 or len(wav) < 44:
            return None, DECODE_FAILED
        return wav, OK
