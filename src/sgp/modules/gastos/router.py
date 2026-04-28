"""Endpoints de resumen de gasto. Solo finanzas y admin."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import require_role
from sgp.core.database import get_db
from sgp.modules.gastos.schemas import ResumenGastos
from sgp.modules.gastos.service import GastosService
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/gastos", tags=["gastos"])


@router.get(
    "/resumen",
    response_model=ResumenGastos,
    summary="Resumen de gasto comprometido vs ejecutado por CC",
)
async def resumen_gastos(
    empresa_id: int = Query(..., gt=0, description="Empresa de la que se mide gasto"),
    periodo_desde: date = Query(..., description="Inicio del periodo (incluido)"),
    periodo_hasta: date = Query(..., description="Fin del periodo (incluido)"),
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(require_role("finanzas")),
):
    """Agrega `monto_estimado` de las SCs filtradas por `created_at` en el
    periodo, separando:
    - **comprometido**: todas excepto DRAFT/REJECTED/CANCELLED/NON_CONFORMING.
    - **ejecutado**: CLOSED.

    Solo finanzas y admin pueden acceder. No bloquea el workflow — es solo
    medición / visualización.
    """
    service = GastosService(db)
    return await service.resumen(
        empresa_id=empresa_id,
        periodo_desde=periodo_desde,
        periodo_hasta=periodo_hasta,
    )
