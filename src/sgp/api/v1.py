"""API v1 — agrega todos los routers de los módulos."""

from fastapi import APIRouter

from sgp.modules.adjuntos.router import router as adjuntos_router
from sgp.modules.auditoria.router import router as auditoria_router
from sgp.modules.catalogo.router import router as catalogo_router
from sgp.modules.empresas.router import router as empresas_router
from sgp.modules.gastos.router import router as gastos_router
from sgp.modules.solicitudes.router import router as solicitudes_router
from sgp.modules.usuarios.router import router as usuarios_router

api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(usuarios_router)
api_v1.include_router(empresas_router)
api_v1.include_router(catalogo_router)
api_v1.include_router(solicitudes_router)
api_v1.include_router(adjuntos_router)
api_v1.include_router(gastos_router)
api_v1.include_router(auditoria_router)
