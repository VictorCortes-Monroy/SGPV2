"""SGP API — Aplicación FastAPI principal."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sgp import __version__
from sgp.api.v1 import api_v1
from sgp.core.config import get_settings
from sgp.core.exceptions import SGPError

settings = get_settings()

# Logging básico
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("sgp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de startup/shutdown."""
    logger.info(f"SGP API v{__version__} iniciando — env={settings.app_env}")
    yield
    logger.info("SGP API cerrando")


app = FastAPI(
    title="SGP — Sistema de Gestión de Compras",
    version=__version__,
    description="API del Sistema de Gestión de Compras (SGP).",
    lifespan=lifespan,
    # Swagger / OpenAPI bajo /api/* para que / quede libre para el frontend.
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# CORS
# Si la lista incluye "*", la CORS spec PROHIBE allow_credentials=True
# (los browsers rechazan la respuesta silenciosamente con "Failed to fetch").
# Auto-flip a credentials=False cuando se usa wildcard. Para producción
# con Clerk + cookies, usar lista explícita de orígenes y queda credentials=True.
_cors_origins = settings.cors_origins_list
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Manejo global de excepciones =====
@app.exception_handler(SGPError)
async def sgp_error_handler(request: Request, exc: SGPError) -> JSONResponse:
    """Convierte SGPError → respuesta HTTP estructurada."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


# ===== Endpoints raíz =====
@app.get("/health", tags=["root"])
async def health():
    """Healthcheck para Railway / Docker / load balancers."""
    return {"status": "ok", "version": __version__}


# ===== Routers de la API =====
# IMPORTANTE: incluir routers ANTES del mount de StaticFiles, para que
# /api/v1/* y /health tengan prioridad sobre el catch-all del frontend.
app.include_router(api_v1)


# ===== Frontend estático =====
# Sirve la SPA del prototipo en /. StaticFiles con html=True hace que / mapee
# a index.html y que rutas no resueltas devuelvan 404 (no es SPA con
# client-side routing — es un single-page sin rutas anidadas).
# Si el directorio no existe (entorno de tests sin frontend buildeado), se
# omite el mount silenciosamente.
_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
else:
    logger.warning(
        f"Carpeta frontend no encontrada en {_frontend_dir}; "
        "la API servirá solo endpoints (sin SPA)."
    )
