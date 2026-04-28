"""Repositorio de Solicitudes de Compra."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sgp.modules.solicitudes.models import SolicitudCompra
from sgp.modules.solicitudes.state_machine import SCStatus


class SolicitudCompraRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, sc_id: int) -> SolicitudCompra | None:
        result = await self.db.execute(
            select(SolicitudCompra)
            .where(SolicitudCompra.id == sc_id)
            .options(selectinload(SolicitudCompra.lineas))
        )
        return result.scalar_one_or_none()

    async def get_by_numero(self, numero: str) -> SolicitudCompra | None:
        result = await self.db.execute(
            select(SolicitudCompra).where(SolicitudCompra.numero == numero)
        )
        return result.scalar_one_or_none()

    async def list_(  # noqa: PLR0913 — los filtros son keyword-only y con default
        self,
        *,
        status: SCStatus | None = None,
        solicitante_id: int | None = None,
        empresa_id: int | None = None,
        centro_costo_id: int | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        monto_min: Decimal | None = None,
        monto_max: Decimal | None = None,
        numero: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SolicitudCompra]:
        """Lista SCs filtradas. Todos los argumentos son keyword-only.

        - `numero`: búsqueda por substring (case-insensitive).
        - `fecha_desde` / `fecha_hasta`: rango sobre `fecha_requerida` (inclusivos).
        - `monto_min` / `monto_max`: rango sobre `monto_estimado` (inclusivos).
        """
        stmt = select(SolicitudCompra)
        if status is not None:
            stmt = stmt.where(SolicitudCompra.status == status)
        if solicitante_id is not None:
            stmt = stmt.where(SolicitudCompra.solicitante_id == solicitante_id)
        if empresa_id is not None:
            stmt = stmt.where(SolicitudCompra.empresa_id == empresa_id)
        if centro_costo_id is not None:
            stmt = stmt.where(SolicitudCompra.centro_costo_id == centro_costo_id)
        if fecha_desde is not None:
            stmt = stmt.where(SolicitudCompra.fecha_requerida >= fecha_desde)
        if fecha_hasta is not None:
            stmt = stmt.where(SolicitudCompra.fecha_requerida <= fecha_hasta)
        if monto_min is not None:
            stmt = stmt.where(SolicitudCompra.monto_estimado >= monto_min)
        if monto_max is not None:
            stmt = stmt.where(SolicitudCompra.monto_estimado <= monto_max)
        if numero is not None and numero.strip():
            stmt = stmt.where(SolicitudCompra.numero.ilike(f"%{numero.strip()}%"))
        stmt = stmt.order_by(SolicitudCompra.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # Alias retro-compatible: el código viejo llamaba list_by_status(...)
    async def list_by_status(
        self,
        status: SCStatus | None = None,
        solicitante_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SolicitudCompra]:
        return await self.list_(
            status=status,
            solicitante_id=solicitante_id,
            limit=limit,
            offset=offset,
        )

    async def add(self, sc: SolicitudCompra) -> None:
        self.db.add(sc)
        await self.db.flush()

    async def generate_next_numero(self) -> str:
        """Genera el siguiente número correlativo de SC en formato SC-YYYY-NNNNNN."""
        year = datetime.now(UTC).year
        prefix = f"SC-{year}-"
        result = await self.db.execute(
            select(func.count(SolicitudCompra.id)).where(
                SolicitudCompra.numero.startswith(prefix)
            )
        )
        count = result.scalar_one() or 0
        return f"{prefix}{count + 1:06d}"
