"""Endpoints HTTP de Solicitudes de Compra."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import get_current_user
from sgp.core.database import get_db
from sgp.modules.solicitudes.repository import SolicitudCompraRepository
from sgp.modules.solicitudes.schemas import (
    LineaRead,
    SolicitudCompraCreate,
    SolicitudCompraRead,
    TransitionRequest,
)
from sgp.modules.solicitudes.service import SolicitudCompraService
from sgp.modules.solicitudes.state_machine import SCStatus, available_actions
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


def _serialize_sc(sc) -> SolicitudCompraRead:
    """Convierte SC ORM → SolicitudCompraRead enriquecido con líneas y acciones disponibles."""
    return SolicitudCompraRead(
        id=sc.id,
        numero=sc.numero,
        empresa_id=sc.empresa_id,
        centro_costo_id=sc.centro_costo_id,
        solicitante_id=sc.solicitante_id,
        tipo=sc.tipo,
        urgencia=sc.urgencia,
        descripcion=sc.descripcion,
        justificacion=sc.justificacion,
        monto_estimado=sc.monto_estimado,
        fecha_requerida=sc.fecha_requerida,
        status=sc.status,
        recotization_cycles=sc.recotization_cycles,
        current_assignee_role=sc.current_assignee_role,
        expected_resolution_at=sc.expected_resolution_at,
        created_at=sc.created_at,
        updated_at=sc.updated_at,
        lineas=[
            LineaRead(
                id=l.id,
                item_id=l.item_id,
                item_sku=l.item.sku if l.item else "",
                item_nombre=l.item.nombre if l.item else "",
                cantidad=l.cantidad,
                especificacion=l.especificacion,
            )
            for l in sc.lineas
        ],
        available_actions=available_actions(sc.status),
    )


@router.post("", response_model=SolicitudCompraRead, status_code=201)
async def create_solicitud(
    payload: SolicitudCompraCreate,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Crea una nueva SC en estado DRAFT."""
    service = SolicitudCompraService(db)
    sc = await service.create(payload, user)
    # Recargar con relaciones
    repo = SolicitudCompraRepository(db)
    sc_full = await repo.get(sc.id)
    return _serialize_sc(sc_full)


@router.get("", response_model=list[SolicitudCompraRead])
async def list_solicitudes(  # noqa: PLR0913 — filtros HTTP, todos opcionales
    status: SCStatus | None = Query(None, description="Filtra por estado del workflow"),
    mias: bool = Query(False, description="Solo las creadas por el usuario actual"),
    empresa_id: int | None = Query(None, gt=0),
    centro_costo_id: int | None = Query(None, gt=0),
    fecha_desde: date | None = Query(None, description="fecha_requerida >= (incluido)"),
    fecha_hasta: date | None = Query(None, description="fecha_requerida <= (incluido)"),
    monto_min: Decimal | None = Query(None, ge=0, description="monto_estimado >= (incluido)"),
    monto_max: Decimal | None = Query(None, ge=0, description="monto_estimado <= (incluido)"),
    numero: str | None = Query(None, description="Búsqueda por substring del número de SC"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    repo = SolicitudCompraRepository(db)
    scs = await repo.list_(
        status=status,
        solicitante_id=user.id if mias else None,
        empresa_id=empresa_id,
        centro_costo_id=centro_costo_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        monto_min=monto_min,
        monto_max=monto_max,
        numero=numero,
        limit=limit,
        offset=offset,
    )
    return [_serialize_sc(sc) for sc in scs]


@router.get("/{sc_id}", response_model=SolicitudCompraRead)
async def get_solicitud(
    sc_id: int,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    repo = SolicitudCompraRepository(db)
    sc = await repo.get(sc_id)
    if not sc:
        from sgp.core.exceptions import NotFoundError
        raise NotFoundError(f"SC {sc_id} no encontrada")
    return _serialize_sc(sc)


@router.post("/{sc_id}/transitions", response_model=SolicitudCompraRead)
async def apply_transition(
    sc_id: int,
    request: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Aplica una acción del workflow sobre una SC.

    El conjunto de acciones permitidas en el estado actual se obtiene
    en el campo `available_actions` del response de GET /solicitudes/{id}.
    """
    service = SolicitudCompraService(db)
    sc = await service.apply_transition(sc_id, request, user)
    return _serialize_sc(sc)
