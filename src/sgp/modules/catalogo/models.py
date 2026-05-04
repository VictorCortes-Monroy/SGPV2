"""Modelos: catálogo maestro de ítems y taxonomía jerárquica."""

import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sgp.core.database import Base, TimestampMixin


class UnidadMedida(str, enum.Enum):
    UN = "UN"     # Unidad
    KG = "KG"     # Kilogramo
    LT = "LT"     # Litro
    M = "M"       # Metro
    M2 = "M2"     # Metro cuadrado
    M3 = "M3"     # Metro cúbico
    HR = "HR"     # Hora
    SVC = "SVC"   # Servicio (sin medida cuantitativa)


class Criticidad(str, enum.Enum):
    CRITICO = "CRITICO"
    ESTANDAR = "ESTANDAR"
    GENERICO = "GENERICO"


class Familia(Base, TimestampMixin):
    """Taxonomía jerárquica de gasto. Auto-referencial vía parent_id."""

    __tablename__ = "familias"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("familias.id", ondelete="RESTRICT"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=Macro, 2=Cat, 3=Subcat, 4=...
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent: Mapped["Familia | None"] = relationship(remote_side="Familia.id", back_populates="hijos")
    hijos: Mapped[list["Familia"]] = relationship(back_populates="parent")


class CatalogoItem(Base, TimestampMixin):
    """SKU del catálogo maestro. Cada línea de SC, OC y Factura referencia uno.

    RN-CAT-CC: cada item pertenece a un único centro de costo. El mismo
    producto físico en CCs distintos se modela como ítems separados con
    IDs distintos. El SKU es único *por CC* — el mismo SKU puede repetirse
    en otros centros de costo.
    """

    __tablename__ = "catalogo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    familia_id: Mapped[int] = mapped_column(
        ForeignKey("familias.id", ondelete="RESTRICT"), nullable=False
    )
    centro_costo_id: Mapped[int] = mapped_column(
        ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unidad_medida: Mapped[UnidadMedida] = mapped_column(
        Enum(UnidadMedida, name="unidad_medida_enum"), nullable=False
    )
    especificacion_tecnica: Mapped[str | None] = mapped_column(Text, nullable=True)
    criticidad: Mapped[Criticidad] = mapped_column(
        Enum(Criticidad, name="criticidad_enum"), default=Criticidad.ESTANDAR, nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    familia: Mapped[Familia] = relationship()

    __table_args__ = (
        UniqueConstraint("sku", "centro_costo_id", name="uq_catalogo_items_sku_cc"),
    )
