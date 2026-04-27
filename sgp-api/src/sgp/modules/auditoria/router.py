"""Endpoints de consulta del audit log (solo lectura)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sgp.core.auth import get_current_user
from sgp.core.database import get_db
from sgp.modules.auditoria.models import AuditLog
from sgp.modules.usuarios.models import Usuario

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    entity_type: str
    entity_id: str
    action: str
    actor_id: int | None
    actor_role: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    comment: str | None


@router.get("/", response_model=list[AuditLogRead])
async def list_audit_logs(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    actor_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    """Lista entradas del audit_log con filtros opcionales."""
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
