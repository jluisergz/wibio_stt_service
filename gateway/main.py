import os
import asyncio
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioStart, AudioStop, AudioChunk
from wyoming.client import AsyncTcpClient

# Configuración desde variables de entorno
API_KEY = os.getenv("API_KEY", "wibio_stt_secret_token_change_me")
WYOMING_HOST = os.getenv("WYOMING_HOST", "stt-engine")
WYOMING_PORT = int(os.getenv("WYOMING_PORT", "10300"))
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")

app = FastAPI(
    title="Wibio STT API Gateway",
    description="Microservicio REST HTTP para transcripción de audio a texto usando Wyoming Whisper",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Esquemas de Respuesta
class STTResponse(BaseModel):
    success: bool
    text: str

class HealthResponse(BaseModel):
    status: str
    stt_engine: str
    wyoming_host: str
    wyoming_port: int


# Dependencia de Autenticación
async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
):
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            token = authorization

    if not token or token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: API Key ausente o inválida"
        )
    return token


async def convert_audio_to_pcm(audio_bytes: bytes) -> bytes:
    """
    Convierte cualquier formato de audio de entrada (WAV, MP3, WebM, OGG, M4A, FLAC, etc.)
    a PCM crudo (16000Hz, 16-bit little-endian mono) usando streaming en memoria con FFmpeg.
    """
    # ponytail: FFmpeg en subprocess sin tocar disco para mínima latencia y bajo consumo I/O
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-nostdin",
        "-threads", "1",
        "-i", "pipe:0",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input=audio_bytes), timeout=60.0)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Tiempo de espera agotado al decodificar el audio."
        )

    if process.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Formato de audio no reconocido o corrupto: {err_msg.strip()[-200:]}"
        )

    return stdout


async def transcribe_with_wyoming(pcm_bytes: bytes, language: str) -> str:
    """
    Envía flujo de audio PCM al motor Wyoming Whisper mediante TCP asíncrono y recolecta la transcripción.
    """
    try:
        async with AsyncTcpClient(WYOMING_HOST, WYOMING_PORT) as client:
            # 1. Enviar solicitud de transcripción
            await client.write_event(Transcribe(language=language).event())

            # 2. Iniciar flujo de audio (16kHz, 16-bit mono)
            await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())

            # 3. Transmitir bloques de audio en chunks de 2048 bytes
            chunk_size = 2048
            for i in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[i:i + chunk_size]
                await client.write_event(AudioChunk(audio=chunk, rate=16000, width=2, channels=1).event())

            # 4. Finalizar flujo de audio
            await client.write_event(AudioStop().event())

            # 5. Esperar evento de transcripción
            while True:
                event = await asyncio.wait_for(client.read_event(), timeout=120.0)
                if event is None:
                    break

                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event)
                    return transcript.text.strip()

            return ""

    except (ConnectionRefusedError, OSError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El motor STT (Wyoming Whisper) no está disponible o aún está iniciando."
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Tiempo de espera agotado mientras el motor STT procesaba la transcripción."
        )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Verifica el estado del servicio y la conectividad TCP con el contenedor STT Wyoming.
    """
    stt_status = "connected"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(WYOMING_HOST, WYOMING_PORT),
            timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
    except Exception:
        stt_status = "unreachable"

    return HealthResponse(
        status="ok" if stt_status == "connected" else "degraded",
        stt_engine=stt_status,
        wyoming_host=WYOMING_HOST,
        wyoming_port=WYOMING_PORT
    )


@app.post("/api/v1/stt", response_model=STTResponse, tags=["STT"])
async def speech_to_text(
    file: UploadFile = File(..., description="Archivo de audio en cualquier formato (WAV, MP3, WebM, OGG, M4A, FLAC)"),
    language: Optional[str] = None,
    _: str = Depends(verify_api_key)
):
    """
    Endpoint principal para transcribir audio a texto.
    Acepta cualquier formato compatible con FFmpeg y lo procesa con Wyoming Whisper.
    """
    # Validar archivo
    audio_content = await file.read()
    if not audio_content or len(audio_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de audio enviado está vacío."
        )

    # 1. Convertir audio a PCM 16kHz s16le mono
    pcm_bytes = await convert_audio_to_pcm(audio_content)

    if not pcm_bytes or len(pcm_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo extraer contenido de audio legible del archivo."
        )

    # 2. Enviar a Wyoming Whisper
    target_language = language if language else DEFAULT_LANGUAGE
    transcription = await transcribe_with_wyoming(pcm_bytes, target_language)

    return STTResponse(
        success=True,
        text=transcription
    )
