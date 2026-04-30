"""SGP API — Aplicación FastAPI principal."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
@app.get("/", tags=["root"])
async def root():
    return {
        "name": "SGP API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["root"])
async def health():
    """Healthcheck para Railway / Docker / load balancers."""
    return {"status": "ok", "version": __version__}


# ===== Routers =====
app.include_router(api_v1)
