"""Modelos: Solicitud de Compra y sus líneas."""

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sgp.core.database import Base, TimestampMixin
from sgp.modules.solicitudes.state_machine import SCStatus


class TipoCompra(str, enum.Enum):
    BIEN = "BIEN"
    SERVICIO = "SERVICIO"


class Urgencia(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENTE = "URGENTE"
    CRITICA = "CRITICA"


class SolicitudCompra(Base, TimestampMixin):
    """Solicitud de Compra (SC). Encabezado.

    Sigue el ciclo de vida de la state_machine. El estado actual está en `status`.
    """

    __tablename__ = "solicitudes_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Scope organizacional
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False
    )
    centro_costo_id: Mapped[int] = mapped_column(
        ForeignKey("centros_costo.id", ondelete="RESTRICT"), nullable=False
    )
    solicitante_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )

    # Datos de la SC
    tipo: Mapped[TipoCompra] = mapped_column(Enum(TipoCompra, name="tipo_compra_enum"), nullable=False)
    urgencia: Mapped[Urgencia] = mapped_column(
        Enum(Urgencia, name="urgencia_enum"), default=Urgencia.NORMAL, nullable=False
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_estimado: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    fecha_requerida: Mapped[date] = mapped_column(Date, nullable=False)

    # Estado del workflow
    status: Mapped[SCStatus] = mapped_column(
        Enum(SCStatus, name="sc_status_enum"), default=SCStatus.DRAFT, nullable=False, index=True
    )
    recotization_cycles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Trazabilidad de aprobaciones (denormalizado para queries rápidas)
    approved_by_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )

    # Relaciones
    lineas: Mapped[list["SolicitudCompraLinea"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", lazy="selectin"
    )
    solicitante: Mapped["Usuario"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[solicitante_id], lazy="joined"
    )

    def snapshot(self) -> dict:
        """Snapshot serializable para el audit_log."""
        return {
            "id": self.id,
            "numero": self.numero,
            "status": self.status.value if self.status else None,
            "monto_estimado": str(self.monto_estimado) if self.monto_estimado else None,
            "recotization_cycles": self.recotization_cycles,
            "centro_costo_id": self.centro_costo_id,
            "tipo": self.tipo.value if self.tipo else None,
            "urgencia": self.urgencia.value if self.urgencia else None,
        }


class SolicitudCompraLinea(Base, TimestampMixin):
    """Línea de una Solicitud de Compra. Vinculada al catálogo maestro (RN7)."""

    __tablename__ = "solicitudes_compra_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitudes_compra.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("catalogo_items.id", ondelete="RESTRICT"), nullable=False
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    especificacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    solicitud: Mapped[SolicitudCompra] = relationship(back_populates="lineas")
    item: Mapped["CatalogoItem"] = relationship(lazy="joined")  # type: ignore[name-defined]


# Imports diferidos para evitar circulares
from sgp.modules.catalogo.models import CatalogoItem  # noqa: E402, F401
from sgp.modules.usuarios.models import Usuario  # noqa: E402, F401
