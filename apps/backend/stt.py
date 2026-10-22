"""Speech to text: NEAR AI's Whisper, or an honest refusal.

`GET cloud-api.near.ai/v1/models` confirmed `openai/whisper-large-v3` is hosted
there and `POST /v1/audio/transcriptions` exists (2026-10-22). **That response
was a 401 without a key, so this client has never seen a real transcript** —
the request is written from the documented OpenAI-compatible shape, exactly
like `agent.NearAiModel`. Treat the parsing as unproven until the first live
turn (HANDOFF §10).

No key configured → `transcribe` returns `(None, "no_key")` and the caller
answers with a plain sentence. It never invents a transcript, because a
hallucinated one would be read back as something the user "said".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

NEAR_AI_BASE = os.environ.get("NEAR_AI_BASE_URL") or "https://cloud-api.near.ai"
NEAR_AI_STT_MODEL = os.environ.get("NEAR_AI_STT_MODEL") or "openai/whisper-large-v3"

OK = "ok"
NO_KEY = "no_key"
FAILED = "failed"

_BOUNDARY = f"----stark{uuid.uuid4().hex}"


def _multipart(fields: dict[str, str], file_field: str, filename: str,
               data: bytes, content_type: str = "audio/wav") -> bytes:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (f"--{_BOUNDARY}\r\n"
             f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
             f"{value}\r\n").encode()
        )
    parts.append(
        (f"--{_BOUNDARY}\r\n"
         f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
         f"Content-Type: {content_type}\r\n\r\n").encode()
        + data + b"\r\n"
    )
    parts.append(f"--{_BOUNDARY}--\r\n".encode())
    return b"".join(parts)


def transcribe(wav: bytes, *, api_key: str | None = None,
               timeout: float = 30.0) -> tuple[str | None, str]:
    """16 kHz mono WAV in, transcript out. `(text, reason)` on every path."""
    key = api_key if api_key is not None else os.environ.get("NEAR_AI_API_KEY")
    if not key:
        return None, NO_KEY

    body = _multipart({"model": NEAR_AI_STT_MODEL}, "file", "audio.wav", wav)
    req = urllib.request.Request(
        f"{NEAR_AI_BASE}/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as err:
        err.close()
        return None, FAILED
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None, FAILED

    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None, FAILED
    return text.strip(), OK
