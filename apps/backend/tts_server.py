"""The voice: Kokoro-82M behind an OpenAI-compatible `/v1/audio/speech`.

A sidecar, deliberately. `server.py` promises standard-library-only, and Kokoro
needs torch — so it runs in its own interpreter (`apps/backend/../../.venv-tts`)
and speaks the OpenAI speech shape over localhost HTTP. This is `stt.py`'s
mirror image: same fail-closed contract, other direction.

Run it:

    cd apps/backend
    ../../.venv-tts/bin/python tts_server.py        # http://127.0.0.1:8010

Then point the main server at it with `STARK_TTS_URL=http://127.0.0.1:8010`.
With the URL unset (the default), or this process down, replies are text —
voice is an enhancement, never a dependency.

Verified live 2026-10-22 on an M1 Pro: RTF ~0.25 on MPS and ~0.31 on CPU,
i.e. speech arrives faster than it plays on both. The pipeline is loaded and
pre-warmed **before** the socket opens, so the first customer never pays the
one-off voice-pack download (~13s).

What it accepts: `{"model", "input", "voice", "response_format"}` — the OpenAI
speech shape. Only `wav` is served (`response_format` defaults to it); other
formats are refused with an OpenAI-shaped error, because guessing a codec is
how players end up with silence.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("STARK_TTS_HOST", "127.0.0.1")
PORT = int(os.environ.get("STARK_TTS_PORT", "8010"))
DEFAULT_VOICE = os.environ.get("STARK_TTS_VOICE", "af_heart")
# Kokoro English voices look like `af_heart` / `am_michael`. Anything else is
# refused before it can reach HF and come back with a download error.
VOICE_RE = re.compile(r"^[a-z]{2}_[a-z0-9_]{2,}$")
MAX_INPUT_CHARS = 2000          # an agent reply is 1-3 sentences; this is generous.
MAX_BODY_BYTES = 64 * 1024      # JSON in, so 2000 chars has room to spare.

OK = "ok"


def pick_device(explicit: str | None = None) -> str:
    """MPS when it exists, else CPU. `torch` will not choose MPS on its own."""
    if explicit:
        return explicit
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class Synthesizer:
    """One pipeline, one lock. Kokoro's model is not documented as thread-safe,
    and two demo speakers are not worth a race."""

    def __init__(self, device: str | None = None, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self.device = device
        self._pipe = None
        self._lock = threading.Lock()

    def load(self) -> None:
        """Build the pipeline and pre-warm the default voice. Called once,
        before the socket opens."""
        if self._pipe is not None:
            return
        from kokoro import KPipeline

        device = pick_device(self.device)
        started = time.perf_counter()
        pipe = KPipeline(lang_code="a", device=device)
        # Warm: pays the voice-pack download and kernel setup now, not later.
        list(pipe("Warm.", voice=self.voice, speed=1.0))
        self._pipe = pipe
        print(
            f"  kokoro ready on {device} in {time.perf_counter() - started:.1f}s "
            f"(voice {self.voice})"
        )

    def synthesize(self, text: str, voice: str) -> bytes:
        """Text in, 24 kHz mono WAV out. Raises on failure — the HTTP layer
        turns that into a refusal, never into silence."""
        self.load()
        import numpy as np
        import soundfile as sf

        with self._lock:
            chunks = [
                a for _, _, a in self._pipe(text, voice=voice, speed=1.0)
            ]
        if not chunks:
            raise RuntimeError("pipeline produced no audio")
        audio = np.concatenate(
            [c.detach().cpu().numpy() if hasattr(c, "detach") else np.asarray(c)
             for c in chunks]
        )
        # soundfile to memory: no temp files, no cleanup to get wrong.
        import io

        buf = io.BytesIO()
        sf.write(buf, audio, 24000, format="WAV")
        return buf.getvalue()


def build_response(payload, synth: Synthesizer) -> tuple[int, str, bytes]:
    """Pure request logic, so tests do not need torch or a socket.

    Returns `(status, content_type, body)` — WAV on success, an OpenAI-shaped
    JSON error otherwise.
    """

    def error(status: int, message: str, err_type: str = "invalid_request_error"):
        body = json.dumps(
            {"error": {"message": message, "type": err_type}}
        ).encode()
        return status, "application/json", body

    if not isinstance(payload, dict):
        return error(400, "Body must be a JSON object.")

    text = payload.get("input")
    if not isinstance(text, str) or not text.strip():
        return error(400, "`input` must be a non-empty string.")
    if len(text) > MAX_INPUT_CHARS:
        return error(400, f"`input` exceeds {MAX_INPUT_CHARS} characters.")

    fmt = payload.get("response_format") or "wav"
    if fmt != "wav":
        return error(400, f"Only response_format=wav is served, got {fmt!r}.")

    voice = payload.get("voice") or DEFAULT_VOICE
    if not isinstance(voice, str) or not VOICE_RE.match(voice):
        return error(400, f"Unknown voice {voice!r} — expected e.g. af_heart.")

    try:
        wav = synth.synthesize(text.strip(), voice)
    except Exception as err:  # a bad voice or a dead model: refuse, don't guess
        return error(500, str(err), "server_error")
    if not wav:
        return error(500, "Synthesis produced no audio.", "server_error")
    return 200, "audio/wav", wav


def make_handler(synth: Synthesizer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "StarkTTS/1"

        def _reply(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - required name
            if self.path == "/health":
                body = json.dumps(
                    {"ok": synth._pipe is not None, "voice": synth.voice}
                ).encode()
                self._reply(200, "application/json", body)
            else:
                self._reply(404, "application/json",
                            b'{"error":{"message":"Not found.","type":"invalid_request_error"}}')

        def do_POST(self):  # noqa: N802 - required name
            if self.path != "/v1/audio/speech":
                self._reply(404, "application/json",
                            b'{"error":{"message":"Not found.","type":"invalid_request_error"}}')
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._reply(413, "application/json",
                            b'{"error":{"message":"Body too large.","type":"invalid_request_error"}}')
                return
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._reply(400, "application/json",
                            b'{"error":{"message":"Body is not JSON.","type":"invalid_request_error"}}')
                return
            status, content_type, body = build_response(payload, synth)
            self._reply(status, content_type, body)

        def log_message(self, fmt: str, *args) -> None:
            print(f"  tts {fmt % args}")

    return Handler


def main() -> None:
    synth = Synthesizer()
    print(f"Stark TTS sidecar (Kokoro-82M) — loading…")
    synth.load()
    print(f"  http://{HOST}:{PORT}/v1/audio/speech  (POST, OpenAI shape)")
    print("  Ctrl-C to stop.\n")
    ThreadingHTTPServer((HOST, PORT), make_handler(synth)).serve_forever()


if __name__ == "__main__":
    main()
