"""Schemas Pydantic para empresas y centros de costo."""

from pydantic import BaseModel, ConfigDict


class CentroCostoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    activo: bool


class EmpresaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rut: str
    razon_social: str
    nombre_corto: str
    activo: bool
