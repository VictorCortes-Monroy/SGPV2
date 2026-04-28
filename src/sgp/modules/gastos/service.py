"""Servicio de resumen de gastos: agrega `monto_estimado` de SCs por
empresa/CC/periodo, separando comprometido (en proceso) y ejecutado (CLOSED).

No mantiene tabla de presupuestos: solo mide gasto a partir de las SCs
existentes. El consumo es informativo, no bloquea el workflow.
"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.exceptions import NotFoundError
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.gastos.schemas import GastoPorCentroCosto, ResumenGastos
from sgp.modules.solicitudes.models import SolicitudCompra
from sgp.modules.solicitudes.state_machine import SCStatus

# Estados que NO suman al comprometido (la SC no llegó a generar expectativa
# de gasto): el draft del solicitante y los rechazos/cancelaciones.
ESTADOS_SIN_GASTO: set[SCStatus] = {
    SCStatus.DRAFT,
    SCStatus.REJECTED,
    SCStatus.CANCELLED,
    SCStatus.NON_CONFORMING,
}


class GastosService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resumen(
        self,
        *,
        empresa_id: int,
        periodo_desde: date,
        periodo_hasta: date,
    ) -> ResumenGastos:
        """Devuelve el resumen de gasto agregado por CC para un periodo.

        El periodo filtra por `created_at` de la SC: una SC creada el 2026-04-15
        cuenta para abril aunque se cierre en mayo.
        """
        empresa = await self._get_empresa_or_404(empresa_id)

        # Convertir a datetime UTC inclusivo (00:00 del primer día - 23:59:59 del último)
        ts_desde = datetime.combine(periodo_desde, time.min)
        ts_hasta = datetime.combine(periodo_hasta, time.max)

        # Lista de status (.value) que NO computan
        ids_sin_gasto = [s.value for s in ESTADOS_SIN_GASTO]

        # Status comprometido = todos menos ESTADOS_SIN_GASTO
        # Status ejecutado = CLOSED
        is_comprometido = ~SolicitudCompra.status.in_(ids_sin_gasto)
        is_ejecutado = SolicitudCompra.status == SCStatus.CLOSED

        # Agregación por CC
        comp_amount = func.coalesce(
            func.sum(case((is_comprometido, SolicitudCompra.monto_estimado), else_=0)),
            0,
        )
        exec_amount = func.coalesce(
            func.sum(case((is_ejecutado, SolicitudCompra.monto_estimado), else_=0)),
            0,
        )
        comp_count = func.coalesce(
            func.sum(case((is_comprometido, 1), else_=0)),
            0,
        )
        exec_count = func.coalesce(
            func.sum(case((is_ejecutado, 1), else_=0)),
            0,
        )

        stmt = (
            select(
                CentroCosto.id,
                CentroCosto.codigo,
                CentroCosto.nombre,
                comp_amount.label("comprometido"),
                exec_amount.label("ejecutado"),
                comp_count.label("scs_comprometidas"),
                exec_count.label("scs_ejecutadas"),
            )
            .select_from(CentroCosto)
            .outerjoin(
                SolicitudCompra,
                (SolicitudCompra.centro_costo_id == CentroCosto.id)
                & (SolicitudCompra.created_at >= ts_desde)
                & (SolicitudCompra.created_at <= ts_hasta),
            )
            .where(CentroCosto.empresa_id == empresa_id)
            .group_by(CentroCosto.id, CentroCosto.codigo, CentroCosto.nombre)
            .order_by(CentroCosto.codigo)
        )
        rows = (await self.db.execute(stmt)).all()

        por_cc: list[GastoPorCentroCosto] = [
            GastoPorCentroCosto(
                centro_costo_id=r.id,
                centro_costo_codigo=r.codigo,
                centro_costo_nombre=r.nombre,
                comprometido=Decimal(r.comprometido),
                ejecutado=Decimal(r.ejecutado),
                scs_comprometidas=int(r.scs_comprometidas),
                scs_ejecutadas=int(r.scs_ejecutadas),
            )
            for r in rows
        ]

        comp_total = sum((c.comprometido for c in por_cc), Decimal(0))
        exec_total = sum((c.ejecutado for c in por_cc), Decimal(0))
        comp_count_total = sum(c.scs_comprometidas for c in por_cc)
        exec_count_total = sum(c.scs_ejecutadas for c in por_cc)

        return ResumenGastos(
            empresa_id=empresa.id,
            empresa_nombre=empresa.razon_social,
            periodo_desde=periodo_desde,
            periodo_hasta=periodo_hasta,
            comprometido_total=comp_total,
            ejecutado_total=exec_total,
            scs_comprometidas_total=comp_count_total,
            scs_ejecutadas_total=exec_count_total,
            por_centro_costo=por_cc,
        )

    async def _get_empresa_or_404(self, empresa_id: int) -> Empresa:
        result = await self.db.execute(
            select(Empresa).where(Empresa.id == empresa_id)
        )
        emp = result.scalar_one_or_none()
        if emp is None:
            raise NotFoundError(f"Empresa {empresa_id} no encontrada")
        return emp
