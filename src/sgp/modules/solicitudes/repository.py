"""Repositorio de Solicitudes de Compra."""

from datetime import UTC, datetime

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

    async def list_by_status(
        self,
        status: SCStatus | None = None,
        solicitante_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SolicitudCompra]:
        stmt = select(SolicitudCompra)
        if status is not None:
            stmt = stmt.where(SolicitudCompra.status == status)
        if solicitante_id is not None:
            stmt = stmt.where(SolicitudCompra.solicitante_id == solicitante_id)
        stmt = stmt.order_by(SolicitudCompra.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

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
