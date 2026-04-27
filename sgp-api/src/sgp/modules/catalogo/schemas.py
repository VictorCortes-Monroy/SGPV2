"""Schemas Pydantic para el catálogo maestro."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from sgp.modules.catalogo.models import Criticidad, UnidadMedida


class FamiliaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    nivel: int
    parent_id: int | None = None
    activo: bool


class CatalogoItemBase(BaseModel):
    sku: str = Field(..., min_length=3, max_length=100)
    nombre: str = Field(..., min_length=3, max_length=255)
    familia_id: int
    unidad_medida: UnidadMedida
    especificacion_tecnica: str | None = None
    precio_referencia: Decimal | None = Field(None, ge=0)
    criticidad: Criticidad = Criticidad.ESTANDAR


class CatalogoItemCreate(CatalogoItemBase):
    pass


class CatalogoItemRead(CatalogoItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: bool
    familia: FamiliaRead


class CatalogoItemSearch(BaseModel):
    """Resultado de búsqueda predictiva (Sec 8.1 del PRD)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    nombre: str
    familia_nombre: str
    unidad_medida: UnidadMedida
