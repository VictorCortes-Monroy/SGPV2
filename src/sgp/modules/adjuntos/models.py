"""Modelo: adjuntos de Solicitudes de Compra."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sgp.core.database import Base, TimestampMixin


class SolicitudAdjunto(Base, TimestampMixin):
    """Documento de respaldo asociado a una SC.

    `stored_path` es relativo al root del backend de storage; el archivo real
    vive en disco (Railway volume) o eventualmente en blob storage. Es el
    backend (sgp.core.storage) quien sabe cómo resolver el path absoluto.

    Soft delete (`deleted_at`): por defecto los DELETE marcan timestamp en vez
    de borrar la fila, para preservar trazabilidad. El archivo sí se borra
    del disco. La fila queda visible en audit pero no en list endpoints.
    """

    __tablename__ = "solicitud_adjuntos"

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitudes_compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Soft-delete: cuando se borra el adjunto el archivo se elimina del disco
    # pero la fila queda con timestamp (auditoría / forense).
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    uploaded_by = relationship("Usuario", foreign_keys=[uploaded_by_id], lazy="joined")
