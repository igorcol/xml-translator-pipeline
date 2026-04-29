from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging, sys, os
from src.config.version import __version__

# Força o Python a reconhecer a pasta 'src' como raiz de módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import de rotas
from api.routes import router as translate_router

# Configuração de log da API
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

API_VERSION = __version__

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

# Conecta as rotas
app.include_router(translate_router)

# Health check
@app.get("/", tags=["Sistema"])
async def health_check():
    return {
        "status": "online",
        "service": "IDML Translator Engine",
        "version": API_VERSION
    }