from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configuração de log da API
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

API_VERSION = "1.0.0-alpha.1"

# Inicializa o App
app = FastAPI(
    title="IDML Translator API",
    description="Pipeline assíncrono de tradução de arquivos InDesign (.idml) com memória de cache local.",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Health check
@app.get("/", tags=["Sistema"])
async def health_check():
    return {
        "status": "online",
        "service": "IDML Translator Engine",
        "version": API_VERSION
    }