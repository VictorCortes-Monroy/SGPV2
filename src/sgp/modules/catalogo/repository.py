"""Repositorio del catálogo maestro."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sgp.modules.catalogo.models import CatalogoItem, Familia


class CatalogoRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_item(self, item_id: int) -> CatalogoItem | None:
        result = await self.db.execute(
            select(CatalogoItem)
            .where(CatalogoItem.id == item_id)
            .options(selectinload(CatalogoItem.familia))
        )
        return result.scalar_one_or_none()

    async def search_items(
        self,
        query: str,
        *,
        centro_costo_id: int | None = None,
        limit: int = 20,
    ) -> list[CatalogoItem]:
        """Búsqueda predictiva por SKU o nombre.

        Si `centro_costo_id` se provee, filtra solo items vinculados a ese CC.
        Es el caso típico desde el form de SC: solo se muestran items del CC
        de la solicitud (RN-CAT-CC).
        """
        like = f"%{query}%"
        stmt = (
            select(CatalogoItem)
            .where(
                CatalogoItem.activo,
                or_(CatalogoItem.sku.ilike(like), CatalogoItem.nombre.ilike(like)),
            )
            .options(selectinload(CatalogoItem.familia))
            .order_by(CatalogoItem.nombre)
            .limit(limit)
        )
        if centro_costo_id is not None:
            stmt = stmt.where(CatalogoItem.centro_costo_id == centro_costo_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_familias(self) -> list[Familia]:
        result = await self.db.execute(
            select(Familia).where(Familia.activo).order_by(Familia.nivel, Familia.nombre)
        )
        return list(result.scalars().all())

    async def create_item(self, data: dict) -> CatalogoItem:
        item = CatalogoItem(**data)
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item, ["familia"])
        return item
