"""Endpoints del catálogo maestro."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import get_current_user, require_role
from sgp.core.database import get_db
from sgp.core.exceptions import NotFoundError
from sgp.modules.catalogo.models import CatalogoItem
from sgp.modules.catalogo.repository import CatalogoRepository
from sgp.modules.catalogo.schemas import (
    CatalogoItemCreate,
    CatalogoItemRead,
    CatalogoItemSearch,
    FamiliaRead,
)
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("/familias", response_model=list[FamiliaRead])
async def list_familias(
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    repo = CatalogoRepository(db)
    return await repo.list_familias()


@router.get("/items/search", response_model=list[CatalogoItemSearch])
async def search_items(
    q: str = Query(..., min_length=2, description="Query de búsqueda (SKU o nombre)"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    """Búsqueda predictiva. Usado en formulario de creación de SC."""
    repo = CatalogoRepository(db)
    items = await repo.search_items(q, limit)
    return [
        CatalogoItemSearch(
            id=i.id,
            sku=i.sku,
            nombre=i.nombre,
            familia_nombre=i.familia.nombre,
            unidad_medida=i.unidad_medida,
        )
        for i in items
    ]


@router.get("/items/{item_id}", response_model=CatalogoItemRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    repo = CatalogoRepository(db)
    item = await repo.get_item(item_id)
    if not item:
        raise NotFoundError(f"Item {item_id} no encontrado")
    return item


@router.post(
    "/items",
    response_model=CatalogoItemRead,
    status_code=201,
    dependencies=[Depends(require_role("admin", "abastecimiento"))],
)
async def create_item(
    payload: CatalogoItemCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = CatalogoRepository(db)
    item = await repo.create_item(payload.model_dump())
    return item
