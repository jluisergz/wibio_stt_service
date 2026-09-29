# 🎙️ Wibio STT Service (Speech-to-Text)

Microservicio ligero y optimizado dedicado a la transcripción de audio a texto (**Speech-to-Text**) en español, exponiendo una API REST HTTP moderna con **FastAPI** y utilizando **Wyoming Whisper** como motor de transcripción.

---

## 🏗️ Arquitectura del Servicio

```text
                                  +---------------------------------------+
                                  |            Cliente / App              |
                                  |    (Laravel, Node.js, Python, etc.)   |
                                  +---------------------------------------+
                                                     │
                                                     │ HTTP POST /api/v1/stt
                                                     │ (Multipart: file + X-API-Key)
                                                     ▼
+─────────────────────────────────────────────────────────────────────────────────────────────────+
│                                     Wibio STT Microservice                                      │
│                                                                                                 │
│  +───────────────────────────────────────────────────────────────────────────────────────────+  │
│  │                              API Gateway (FastAPI) - Puerto 8005                          │  │
│  │                                                                                           │  │
│  │  1. Valida API Key (X-API-Key / Bearer Token)                                            │  │
│  │  2. Convierte audio universal en memoria (FFmpeg -> PCM 16kHz s16le mono)                 │  │
│  │  3. Envía flujo asíncrono en chunks TCP a Wyoming                                         │  │
│  +───────────────────────────────────────────────────────────────────────────────────────────+  │
│                                                     │                                           │
│                                                     │ TCP Wyoming Protocol (Puerto 10300)       │
│                                                     ▼                                           │
│  +───────────────────────────────────────────────────────────────────────────────────────────+  │
│  │                         Motor STT (Wyoming Whisper - tiny / es)                           │  │
│  │                                                                                           │  │
│  │  - Procesa inferencia de audio y genera transcripción de texto                            │  │
│  │  - Cache persistente de modelos en volumen Docker (`wibio-stt-data`)                      │  │
│  +───────────────────────────────────────────────────────────────────────────────────────────+  │
+─────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 🚀 Características Principales

- **Bajo Consumo de Recursos:** Configurado con modelo `tiny` por defecto (~0.6 CPU total y ~500 MB RAM total: 350 MB STT Engine + 150 MB Gateway).
- **Conversión Universal de Audio:** Soporta **cualquier formato** sin tocar disco (`WAV`, `MP3`, `OGG Opus`, `WebM`, `M4A`, `AAC`, `FLAC`, `AMR`, audios de WhatsApp/Telegram).
- **Seguridad Integrada:** Autenticación por `X-API-Key` o `Authorization: Bearer <TOKEN>`.
- **Streaming Asíncrono:** Comunicación TCP eficiente en fragmentos de 2048 bytes con el motor Wyoming.
- **Health Checks:** Endpoints para monitorear el estado del API y la conectividad con el motor STT (`/health` y `/api/v1/health`).
- **Documentación Swagger / OpenAPI:** Documentación interactiva autogenerada en `/docs` y `/redoc`.

---

## 🔗 Rutas Rápidas y Endpoints

| Endpoint | Método | Autenticación | Descripción |
|---|---|---|---|
| [`/docs`](http://localhost:8005/docs) | `GET` | No | **Swagger UI** interactivo para probar la API desde el navegador. |
| [`/redoc`](http://localhost:8005/redoc) | `GET` | No | **ReDoc** con especificación OpenAPI detallada. |
| [`/openapi.json`](http://localhost:8005/openapi.json) | `GET` | No | Esquema OpenAPI en formato JSON. |
| [`/health`](http://localhost:8005/health) | `GET` | No | **Health Check** básico del Gateway y conectividad con Wyoming STT. |
| [`/api/v1/health`](http://localhost:8005/api/v1/health) | `GET` | No | **Health Check v1** con estado detallado del motor de transcripción. |
| [`/api/v1/stt`](http://localhost:8005/api/v1/stt) | `POST` | `X-API-Key` o `Bearer` | **Speech-to-Text**: Recibe audio (`multipart/form-data`) y devuelve transcripción. |

## 📁 Estructura del Proyecto

```text
wibio_stt_service/
├── .env.example              # Plantilla de variables de entorno
├── .env                      # Variables de entorno activas
├── docker-compose.yml        # Orquestación de servicios (stt-engine + gateway)
├── README.md                 # Documentación técnica y manual de uso
└── gateway/
    ├── Dockerfile            # Imagen base Python 3.11 Slim + FFmpeg
    ├── requirements.txt      # Dependencias Python (FastAPI, Wyoming, Uvicorn)
    └── main.py               # Lógica del API Gateway, autenticación y cliente Wyoming
```

---

## ⚙️ Variables de Entorno (`.env`)

| Variable | Descripción | Valor por Defecto |
|---|---|---|
| `PORT` | Puerto expuesto en el host para la API REST | `8005` |
| `API_KEY` | Token secreto requerido para autenticar peticiones | `wibio_stt_secret_token_change_me` |
| `WYOMING_HOST` | Host o nombre del contenedor del motor Wyoming | `stt-engine` (en Docker) / `localhost` (en Local) |
| `WYOMING_PORT` | Puerto TCP de Wyoming | `10300` |
| `WHISPER_MODEL` | Modelo Whisper (`tiny`, `base`, `small`, `medium`) | `tiny` |
| `WHISPER_LANGUAGE` | Idioma de transcripción predeterminado | `es` |

---

## 🐳 Modo 1: Ejecución con Docker (Recomendado para Producción)

Docker orquesta automáticamente tanto el motor Wyoming Whisper como el Gateway FastAPI con FFmpeg.

### 1. Requisitos Previos:
- Docker y Docker Compose instalados.

### 2. Iniciar el servicio:
```powershell
docker compose up -d --build
```

### 3. Verificar estado de los contenedores:
```powershell
docker compose ps
```

### 4. Ver logs en tiempo real:
```powershell
docker compose logs -f
```

### 5. Detener el servicio:
```powershell
docker compose down
```

---

## 💻 Modo 2: Ejecución en Entorno Local (Desarrollo sin Docker)

Si prefieres ejecutar el Gateway directamente en tu sistema operativo:

### 1. Requisitos Previos:
- **Python 3.10 o superior**.
- **FFmpeg** instalado y disponible en el `PATH` del sistema:
  - **Windows (Chocolatey / Scoop / Winget):** `winget install Gyan.FFmpeg`
  - **Linux (Ubuntu/Debian):** `sudo apt-get install -y ffmpeg`
  - **macOS (Homebrew):** `brew install ffmpeg`
- **Motor Wyoming Whisper** corriendo localmente o en Docker (puerto `10300`).

### 2. Configurar el Entorno Virtual:
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux/macOS:
source venv/bin/activate

# Instalar dependencias
pip install -r gateway/requirements.txt
```

### 3. Iniciar el Motor Wyoming Whisper (si no lo tienes en Docker):
```bash
# Puedes correr solo el motor STT en Docker:
docker run -d -p 10300:10300 rhasspy/wyoming-whisper --model tiny --language es --uri tcp://0.0.0.0:10300
```

### 4. Iniciar el API Gateway en Local:
```bash
# Configurar variables (o crear tu archivo .env local)
export WYOMING_HOST="localhost"
export WYOMING_PORT="10300"
export API_KEY="wibio_stt_secret_token_change_me"

# Ejecutar el servidor con recarga en caliente (hot-reload)
cd gateway
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

---

## 🧪 Referencia y Pruebas de la API

### 1. Health Check
Verifica que el Gateway esté activo y con conexión TCP funcional al motor STT.

```bash
curl -X GET http://localhost:8005/api/v1/health
```

**Respuesta Exitosa (HTTP 200):**
```json
{
  "status": "ok",
  "stt_engine": "connected",
  "wyoming_host": "stt-engine",
  "wyoming_port": 10300
}
```

---

### 2. Transcribir Audio (POST `/api/v1/stt`)

- **Método:** `POST`
- **URL:** `http://localhost:8005/api/v1/stt`
- **Headers:** `X-API-Key: <TU_API_KEY>` (o `Authorization: Bearer <TU_API_KEY>`)
- **Body:** `multipart/form-data` con campo `file` conteniendo el audio.
- **Query Params (Opcional):** `?language=es`

#### Ejemplo con cURL (cualquier formato de audio):
```bash
curl -X POST http://localhost:8005/api/v1/stt \
  -H "X-API-Key: wibio_stt_secret_token_change_me" \
  -F "file=@/ruta/a/tu/audio.ogg"
```

**Respuesta Exitosa (HTTP 200):**
```json
{
  "success": true,
  "text": "Hola, este es un mensaje de audio transcrito correctamente."
}
```

---

## 🔌 Ejemplos de Integración

### En Laravel (PHP)

```php
use Illuminate\Support\Facades\Http;

$response = Http::withHeaders([
    'X-API-Key' => env('STT_API_KEY', 'wibio_stt_secret_token_change_me'),
])
->timeout(60)
->attach('file', file_get_contents($rutaArchivo), 'audio.ogg')
->post('http://localhost:8005/api/v1/stt');

if ($response->successful()) {
    $texto = $response->json('text');
}
```

### En Python (`httpx` / `requests`)

```python
import httpx

async def transcribir(audio_path: str) -> str:
    headers = {"X-API-Key": "wibio_stt_secret_token_change_me"}
    with open(audio_path, "rb") as f:
        files = {"file": ("audio.mp3", f, "audio/mpeg")}
        async with httpx.AsyncClient() as client:
            res = await client.post("http://localhost:8005/api/v1/stt", headers=headers, files=files, timeout=60.0)
            res.raise_for_status()
            return res.json()["text"]
```

### En Node.js (Fetch nativo)

```javascript
import fs from 'fs';
import FormData from 'form-data';

const form = new FormData();
form.append('file', fs.createReadStream('./audio.ogg'));

const res = await fetch('http://localhost:8005/api/v1/stt', {
  method: 'POST',
  headers: {
    'X-API-Key': 'wibio_stt_secret_token_change_me',
    ...form.getHeaders()
  },
  body: form
});

const data = await res.json();
console.log(data.text);
```

---

## 📖 Documentación Interactiva y Health Checks

Con el servicio en ejecución (puerto `8005`), puedes acceder a:

- 📘 **Swagger UI:** [http://localhost:8005/docs](http://localhost:8005/docs) *(Interfaz interactiva para probar envíos de audio y autenticación en vivo)*
- 📕 **ReDoc:** [http://localhost:8005/redoc](http://localhost:8005/redoc) *(Documentación técnica visual estructurada)*
- 📄 **OpenAPI Schema (JSON):** [http://localhost:8005/openapi.json](http://localhost:8005/openapi.json)
- 🩺 **Health Check:** [http://localhost:8005/health](http://localhost:8005/health) o [http://localhost:8005/api/v1/health](http://localhost:8005/api/v1/health) *(Verifica conectividad con el motor Wyoming Whisper)*
