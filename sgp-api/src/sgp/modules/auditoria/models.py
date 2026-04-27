"""Modelo del audit_log.

Esta tabla es append-only. La inmutabilidad se garantiza:
1. No exponemos UPDATE/DELETE en este módulo.
2. Un trigger PL/pgSQL definido en la migración inicial impide
   cualquier UPDATE o DELETE a nivel de DB.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sgp.core.database import Base


class AuditLog(Base):
    """Registro inmutable de una acción auditable.

    No usa TimestampMixin porque solo importa `timestamp` (creación);
    nunca se modifica.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Qué entidad fue afectada
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Qué acción se ejecutó
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Quién la ejecutó
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Cambio de estado
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Comentario libre del actor
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
