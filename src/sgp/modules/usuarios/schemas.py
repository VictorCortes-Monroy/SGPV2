"""Schemas Pydantic para usuarios."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class RolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None = None


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clerk_user_id: str
    email: EmailStr
    nombre: str
    activo: bool
    roles: list[RolRead] = []
    created_at: datetime
