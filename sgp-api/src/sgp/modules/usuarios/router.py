"""Endpoints HTTP de usuarios."""

from fastapi import APIRouter, Depends

from sgp.core.auth import get_current_user
from sgp.modules.usuarios.models import Usuario
from sgp.modules.usuarios.schemas import UsuarioRead

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/me", response_model=UsuarioRead)
async def get_me(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Devuelve el usuario autenticado actual."""
    return user
