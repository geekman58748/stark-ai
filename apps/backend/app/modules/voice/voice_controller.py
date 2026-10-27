from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from app.decorators.api_responses import ApiResponses
from app.decorators.auth_user import AuthUser
from app.decorators.inject_module import Module
from app.modules.voice.dtos.speak_dto import SpeakDto
from app.modules.voice.dtos.speech_dto import SpeechDto
from app.modules.voice.dtos.voice_dto import VoiceDto
from app.modules.voice.dtos.voice_reply_dto import VoiceReplyDto
from app.modules.voice.voice_request import VoiceRequest

router = APIRouter(tags=["Voice"], responses=ApiResponses.errors("unauthorized"))

# The body is read raw (a multipart clip's bytes do not survive form decoding), so
# FastAPI cannot infer it; it is documented here instead.
_VOICE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": VoiceDto.model_json_schema()},
            "multipart/form-data": {"schema": {
                "type": "object",
                "properties": {
                    "audio": {"type": "string", "format": "binary"},
                    "audio_type": {"type": "string"},
                    "speak": {"type": "boolean"},
                },
            }},
        },
    },
}


@router.post("/v1/voice", response_model=VoiceReplyDto, openapi_extra=_VOICE_BODY,
             summary="One spoken or typed turn",
             responses=ApiResponses.errors("bad_audio", "audio_too_large"))
async def voice(request: Request, account: AuthUser, module: Module) -> JSONResponse:
    """The wake gate is server-side: no "stark", `ignored: true`. A clip that is not
    understood comes back `stt: failed` with an empty transcript, never a guess.
    Send `speak: false` to get the words first and speak them with `POST /v1/speak`."""
    parsed = VoiceRequest.parse(await request.body(),
                                request.headers.get("content-type", ""))
    return JSONResponse(await run_in_threadpool(module.voice.respond, account.id, parsed))


@router.post("/v1/speak", response_model=SpeechDto, summary="Speak text you already have",
             responses=ApiResponses.errors("bad_text"))
def speak(dto: SpeakDto, _account: AuthUser, module: Module) -> JSONResponse:
    return JSONResponse(module.voice.speak(dto.text))


@router.get("/v1/speak/stream", summary="Speak, streamed as it is produced",
            response_class=StreamingResponse,
            responses={200: {"content": {"audio/mpeg": {}, "audio/wav": {}}},
                       **ApiResponses.errors("bad_text", "no_voice")})
def speak_stream(
    _account: AuthUser,
    module: Module,
    text: str = Query("", examples=["Your light bill is 5,000 naira."]),
    token: str = Query("", description="The session token, for an <audio> element "
                                       "that cannot set a header."),
) -> StreamingResponse:
    """No `Content-Length`: the body is deliberately not buffered."""
    content_type, chunks = module.voice.stream(text)
    return StreamingResponse(chunks, media_type=content_type,
                             headers={"Cache-Control": "no-store"})
