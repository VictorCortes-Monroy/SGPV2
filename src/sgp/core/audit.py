"""Helper para escribir el audit log de forma consistente.

El audit_log es append-only (RN5). La inmutabilidad se garantiza
adicionalmente con un trigger PL/pgSQL definido en la migración.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sgp.modules.auditoria.models import AuditLog


class AuditService:
    """Servicio para registrar acciones auditables en el sistema."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        *,
        entity_type: str,
        entity_id: int | str,
        action: str,
        actor_id: int | None,
        actor_role: str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        comment: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Registra una acción en el audit_log.

        No commitea: se asume que el caller lo hace dentro de una transacción mayor.
        """
        log = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            before_state=before,
            after_state=after,
            comment=comment,
            ip_address=ip_address,
            timestamp=datetime.now(UTC),
        )
        self.db.add(log)
        await self.db.flush()
        return log
