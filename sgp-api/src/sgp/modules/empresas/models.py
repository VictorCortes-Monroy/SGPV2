"""Modelos: empresas y centros de costo."""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sgp.core.database import Base, TimestampMixin


class Empresa(Base, TimestampMixin):
    """Razón social del grupo. Multi-tenant."""

    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    rut: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_corto: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    centros_costo: Mapped[list["CentroCosto"]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )


class CentroCosto(Base, TimestampMixin):
    """Centro de costo de una empresa."""

    __tablename__ = "centros_costo"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    empresa: Mapped[Empresa] = relationship(back_populates="centros_costo")
