"""Endpoints de empresas y centros de costo."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import get_current_user
from sgp.core.database import get_db
from sgp.modules.empresas.models import CentroCosto, Empresa
from sgp.modules.empresas.schemas import CentroCostoRead, EmpresaRead
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("", response_model=list[EmpresaRead])
async def list_empresas(
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
) -> list[Empresa]:
    result = await db.execute(select(Empresa).where(Empresa.activo).order_by(Empresa.nombre_corto))
    return list(result.scalars().all())


@router.get("/{empresa_id}/centros-costo", response_model=list[CentroCostoRead])
async def list_centros_costo(
    empresa_id: int,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
) -> list[CentroCosto]:
    result = await db.execute(
        select(CentroCosto)
        .where(CentroCosto.empresa_id == empresa_id, CentroCosto.activo)
        .order_by(CentroCosto.codigo)
    )
    return list(result.scalars().all())
